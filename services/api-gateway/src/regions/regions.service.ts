import {
  Injectable,
  BadRequestException,
  InternalServerErrorException,
} from '@nestjs/common';
import { Express } from 'express';
import { spawn, execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import axios from 'axios';
import { createClient } from '@supabase/supabase-js';
import { CreateRegionDto } from './dto/create-region.dto';

// ── Constantes geográficas ────────────────────────────────────────────────────

const EARTH_RADIUS_M = 6_371_000;

// ── Tipos internos ────────────────────────────────────────────────────────────

interface SquareBbox {
  north: number;
  south: number;
  east: number;
  west: number;
  /** Lado del cuadrado en metros (ancho = alto real). */
  sideM: number;
}

interface ElevationRange {
  minElevation: number;
  maxElevation: number;
}

// ── Servicio ──────────────────────────────────────────────────────────────────

@Injectable()
export class RegionsService {

  private supabase = createClient(
    process.env.SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_KEY!,
  );

  // ── DMS → decimal ───────────────────────────────────────────────────────────

  private dmsToDecimal(dms: string): number {
    const parts = dms.match(/-?\d+(\.\d+)?/g);
    if (!parts || parts.length < 3) return NaN;
    const deg  = parseFloat(parts[0]);
    const min  = parseFloat(parts[1]);
    const sec  = parseFloat(parts[2]);
    const sign = deg < 0 ? -1 : 1;
    return sign * (Math.abs(deg) + min / 60 + sec / 3600);
  }

  /**
   * Calcula el bounding box cuadrado centrado en el bbox original.
   *
   * El lado del cuadrado = lado menor del bbox original, garantizando
   * que el recorte siempre esté dentro del TIF original sin NODATA.
   *
   * La conversión grados ↔ metros usa la latitud central para corregir
   * la convergencia de meridianos (los grados de longitud son más cortos
   * cerca de los polos).
   */
  private computeSquareBbox(
    north: number, south: number,
    east:  number, west:  number,
  ): SquareBbox {
    const latCenter = (north + south) / 2;
    const lonCenter = (east  + west)  / 2;

    const cosLat  = Math.cos(latCenter * Math.PI / 180);
    const degToM  = Math.PI / 180 * EARTH_RADIUS_M;

    const widthM  = Math.abs(east - west) * degToM * cosLat;
    const heightM = Math.abs(north - south) * degToM;

    // Lado del cuadrado = lado menor para evitar zonas sin datos (NODATA)
    const sideM = Math.min(widthM, heightM);

    // Convertir el semilado de metros a grados en cada eje
    const halfLat = (sideM / 2) / degToM;
    const halfLon = (sideM / 2) / (degToM * cosLat);

    return {
      north:  latCenter + halfLat,
      south:  latCenter - halfLat,
      east:   lonCenter + halfLon,
      west:   lonCenter - halfLon,
      sideM,
    };
  }

  /**
   * Paso 1 — Recortar el TIF original al bbox cuadrado.
   *
   * Se usa `gdalwarp` con `-te` (target extent) en grados y `-ts 1024 1024`
   * para forzar píxeles cuadrados. Esto garantiza que el heightmap resultante
   * cubra exactamente el mismo área que la textura satelital.
   *
   * ¿Por qué antes de la conversión a PNG?
   *   - gdalwarp trabaja sobre GeoTIFF y respeta la proyección original.
   *   - Asegura que min/max de elevación (gdalinfo) correspondan solo al
   *     área cuadrada, no al bbox rectangular original.
   *   - La textura satelital se pide con el mismo bbox cuadrado → coherencia.
   */
  private clipToSquare(
    input: string,
    output: string,
    sq: SquareBbox,
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      const proc = spawn('gdalwarp', [
        '-te',    String(sq.west), String(sq.south),
                  String(sq.east), String(sq.north),
        '-ts',    '1024', '1024',   // píxeles cuadrados
        '-r',     'bilinear',        // remuestreo suave
        '-overwrite',
        input,
        output,
      ]);

      let stderr = '';
      proc.stderr.on('data', (d) => { stderr += d.toString(); });
      proc.on('close', (code) => {
        if (code === 0) resolve();
        else reject(new Error(`gdalwarp falló (code ${code}): ${stderr}`));
      });
    });
  }

  /**
   * Paso 2 — Extraer min/max de elevación del TIF YA RECORTADO.
   *
   * Se llama sobre el TIF cuadrado (no el original) para que los valores
   * correspondan exactamente al área que se va a renderizar.
   */
  private extractElevationRange(tifPath: string): ElevationRange {
    try {
      const output = execSync(`gdalinfo -mm "${tifPath}" 2>&1`, { encoding: 'utf8' });
      const match  = output.match(/Computed Min\/Max\s*=\s*([-\d.]+)\s*,\s*([-\d.]+)/);

      if (!match) throw new Error('gdalinfo no devolvió Computed Min/Max');

      const minElevation = parseFloat(match[1]);
      const maxElevation = parseFloat(match[2]);

      if (isNaN(minElevation) || isNaN(maxElevation))
        throw new Error(`Elevaciones inválidas: ${match[1]}, ${match[2]}`);

      if (maxElevation <= minElevation)
        throw new Error(`max (${maxElevation}) debe ser > min (${minElevation})`);

      return { minElevation, maxElevation };
    } catch (err: any) {
      throw new BadRequestException(
        `No se pudo extraer elevación del TIF recortado: ${err.message}`,
      );
    }
  }

  /**
   * Paso 3 — Convertir TIF cuadrado a PNG heightmap UInt16.
   *
   * `-scale minElev maxElev 0 65535` escala de forma explícita y absoluta:
   *   pixel 0     → min_elevation metros
   *   pixel 65535 → max_elevation metros
   *
   * Esto permite reconstruir la elevación real en el shader:
   *   elevation_m = (pixel / 65535) × vertical_scale + min_elevation
   */
  private convertToHeightmapPng(
    input: string,
    output: string,
    min: number,
    max: number,
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      const proc = spawn('gdal_translate', [
        '-b',      '1',
        '-scale',  String(min), String(max), '0', '65535',
        '-ot',     'UInt16',
        '-of',     'PNG',
        input,
        output,
      ]);

      let stderr = '';
      proc.stderr.on('data', (d) => { stderr += d.toString(); });
      proc.on('close', (code) => {
        if (code === 0) resolve();
        else reject(new Error(`gdal_translate falló (code ${code}): ${stderr}`));
      });
    });
  }

  // ── Crear región ─────────────────────────────────────────────────────────────

  async create(dto: CreateRegionDto, file: Express.Multer.File) {
    if (!file) throw new BadRequestException('TIF file is required');

    // Coordenadas del bbox del usuario (rectangulares)
    const north = this.dmsToDecimal(dto.north);
    const south = this.dmsToDecimal(dto.south);
    const east  = this.dmsToDecimal(dto.east);
    const west  = this.dmsToDecimal(dto.west);

    if ([north, south, east, west].some(isNaN))
      throw new BadRequestException('Invalid coordinates');
    if (north <= south) throw new BadRequestException('North must be greater than south');
    if (east  <= west)  throw new BadRequestException('East must be greater than west');

    // Calcular bbox cuadrado centrado
    const sq = this.computeSquareBbox(north, south, east, west);

    console.log(
      `[regions] "${dto.name}" — bbox original: ` +
      `${(Math.abs(east-west)*Math.PI/180*EARTH_RADIUS_M*Math.cos((north+south)/2*Math.PI/180)).toFixed(0)} × ` +
      `${(Math.abs(north-south)*Math.PI/180*EARTH_RADIUS_M).toFixed(0)} m` +
      ` → cuadrado: ${sq.sideM.toFixed(0)} × ${sq.sideM.toFixed(0)} m`,
    );
    console.log(
      `[regions] Bbox cuadrado: N${sq.north.toFixed(6)} S${sq.south.toFixed(6)} ` +
      `E${sq.east.toFixed(6)} W${sq.west.toFixed(6)}`,
    );

    try {
      fs.mkdirSync('uploads', { recursive: true });

      const ts            = Date.now();
      const tifOriginal   = `uploads/${ts}_original.tif`;
      const tifSquare     = `uploads/${ts}_square.tif`;
      const heightmapPath = `uploads/${ts}_heightmap.png`;

      fs.writeFileSync(tifOriginal, file.buffer);

      // ── 1. Recortar a cuadrado ────────────────────────────────────────────
      await this.clipToSquare(tifOriginal, tifSquare, sq);

      // ── 2. Extraer elevaciones del TIF cuadrado ───────────────────────────
      const { minElevation, maxElevation } = this.extractElevationRange(tifSquare);
      const verticalScale = maxElevation - minElevation;

      console.log(
        `[regions] Elevación: ${minElevation}–${maxElevation} m ` +
        `(rango ${verticalScale.toFixed(1)} m)`,
      );

      // ── 3. Convertir a PNG heightmap ──────────────────────────────────────
      await this.convertToHeightmapPng(tifSquare, heightmapPath, minElevation, maxElevation);

      // ── 4. Subir heightmap a Supabase Storage ─────────────────────────────
      const heightmapName   = `${ts}_heightmap.png`;
      const heightmapBuffer = fs.readFileSync(heightmapPath);

      const { error: hmError } = await this.supabase.storage
        .from('heightmaps')
        .upload(heightmapName, heightmapBuffer, { contentType: 'image/png', upsert: true });

      if (hmError) throw hmError;

      const heightmapUrl =
        `${process.env.SUPABASE_URL}/storage/v1/object/public/heightmaps/${heightmapName}`;

      // ── 5. Solicitar textura satelital con el bbox CUADRADO ───────────────
      //
      // El bbox que se envía al imagery service es el mismo cuadrado que se
      // usó para recortar el TIF, garantizando que textura y heightmap
      // cubran exactamente el mismo territorio.
      const imageryResponse = await axios.post(
        'http://localhost:3003/imagery/true-color',
        {
          bbox:     [sq.west, sq.south, sq.east, sq.north],
          from:     '2012-01-01',
          to:       '2026-02-01',
          maxCloud: 5,
          width:    1024,
          height:   1024,   // cuadrada, igual que el heightmap
        },
        { responseType: 'arraybuffer' },
      );

      const textureBuffer = Buffer.from(imageryResponse.data);
      const textureName   = `${ts}_texture.png`;

      const { error: txError } = await this.supabase.storage
        .from('color_texture')
        .upload(textureName, textureBuffer, { contentType: 'image/png', upsert: true });

      if (txError) throw txError;

      const textureUrl =
        `${process.env.SUPABASE_URL}/storage/v1/object/public/color_texture/${textureName}`;

      // ── 6. Guardar en base de datos ───────────────────────────────────────
      //
      // Se guardan las coordenadas del bbox CUADRADO (no el original del usuario).
      // Son los valores que usa Scene.tsx para calcular displacementScale y
      // los que representan el área real del heightmap y la textura.
      const { error: dbError } = await this.supabase.from('basins').insert({
        name:              dto.name,
        heightmap_url:     heightmapUrl,
        color_texture_url: textureUrl,
        resolution:        30,
        min_elevation:     minElevation,
        max_elevation:     maxElevation,
        vertical_scale:    verticalScale,
        bbox_north:        sq.north,
        bbox_south:        sq.south,
        bbox_east:         sq.east,
        bbox_west:         sq.west,
        // side_m es redundante (calculable) pero útil para debug y consultas
        side_m:            sq.sideM,
      });

      if (dbError) throw dbError;

      return {
        status: 'created',
        region: {
          name:              dto.name,
          heightmap_url:     heightmapUrl,
          color_texture_url: textureUrl,
          min_elevation:     minElevation,
          max_elevation:     maxElevation,
          vertical_scale:    verticalScale,
          north:             sq.north,
          south:             sq.south,
          east:              sq.east,
          west:              sq.west,
          side_m:            sq.sideM,
        },
      };

    } catch (err) {
      console.error('[regions] create error:', err);
      throw new InternalServerErrorException('Region creation failed');
    } finally {
      // Limpiar todos los archivos temporales
      try {
        const dir = path.join(process.cwd(), 'uploads');
        if (fs.existsSync(dir)) {
          for (const f of fs.readdirSync(dir)) {
            fs.unlinkSync(path.join(dir, f));
          }
        }
      } catch (e: any) {
        console.error('[cleanup]', e.message);
      }
    }
  }

  // ── Búsqueda y consulta ───────────────────────────────────────────────────

  async searchBasins(query: string) {
    if (!query || query.length < 2) return [];
    const { data, error } = await this.supabase
      .from('basins')
      .select('id, name')
      .ilike('name', `%${query}%`)
      .limit(10);
    if (error) throw new InternalServerErrorException('Search failed');
    return data;
  }

  async findOne(id: string) {
    const { data, error } = await this.supabase
      .from('basins')
      .select(`
        id, name, heightmap_url, color_texture_url, resolution, created_at,
        min_elevation, max_elevation, vertical_scale, side_m,
        bbox_north, bbox_south, bbox_east, bbox_west
      `)
      .eq('id', id)
      .single();

    if (error || !data) throw new BadRequestException('Region not found');

    // Normalizar nombres de campo para que Scene.tsx reciba north/south/east/west
    return {
      ...data,
      north: data.bbox_north,
      south: data.bbox_south,
      east:  data.bbox_east,
      west:  data.bbox_west,
    };
  }
}