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

  // ── Normalización de nombre ───────────────────────────────────────────────
  /**
   * Elimina acentos y convierte a minúsculas para comparaciones
   * independientes de mayúsculas y diacríticos.
   * Ej: "Pánuco" → "panuco", "PANUCO" → "panuco"
   */
  private normalizeName(str: string): string {
    return str
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .trim();
  }

  /**
   * Comprueba si ya existe una región con el mismo nombre,
   * ignorando mayúsculas/minúsculas y acentos.
   *
   * Estrategia de dos pasos:
   *  1. ilike en Supabase → eficiente para coincidencias case-insensitive exactas.
   *  2. Comparación JS con normalización de acentos → atrapa casos como
   *     "Pánuco" vs "Panuco" que ilike no detectaría.
   */
  private async checkDuplicateName(name: string): Promise<boolean> {
    const normalizedInput = this.normalizeName(name);

    // Paso 1: coincidencia case-insensitive directa (rápida, usa índice)
    const { data: ilikeData, error: ilikeError } = await this.supabase
      .from('basins')
      .select('name')
      .ilike('name', name.trim());

    if (!ilikeError && ilikeData && ilikeData.length > 0) {
      return true;
    }

    // Paso 2: normalización de acentos en JS sobre todos los registros
    // Solo se ejecuta si ilike no encontró nada (conjunto pequeño en proyectos académicos)
    const { data: allData, error: allError } = await this.supabase
      .from('basins')
      .select('name');

    if (allError || !allData) return false;

    return allData.some(
      (row) => this.normalizeName(row.name) === normalizedInput,
    );
  }

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

    const sideM = Math.min(widthM, heightM);

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

  private clipToSquare(input: string, output: string, sq: SquareBbox): Promise<void> {
    return new Promise((resolve, reject) => {
      const proc = spawn('gdalwarp', [
        '-te', String(sq.west), String(sq.south), String(sq.east), String(sq.north),
        '-ts', '1024', '1024',
        '-r', 'bilinear',
        '-overwrite',
        input, output,
      ]);

      proc.on('error', (err) => reject(err)); // ← captura ENOENT y similares

      let stderr = '';
      proc.stderr.on('data', (d) => { stderr += d.toString(); });
      proc.on('close', (code) => {
        if (code === 0) resolve();
        else reject(new Error(`gdalwarp falló (code ${code}): ${stderr}`));
      });
    });
  }

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

      proc.on('error', (err) => reject(err)); //

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

    // ── Validación de nombre duplicado ────────────────────────────────────────
    const duplicate = await this.checkDuplicateName(dto.name);
    if (duplicate) {
      throw new BadRequestException(
        `Ya existe una región con el nombre "${dto.name}". Elige un nombre diferente.`,
      );
    }

    // Coordenadas del bbox del usuario (rectangulares)
    const north = this.dmsToDecimal(dto.north);
    const south = this.dmsToDecimal(dto.south);
    const east  = this.dmsToDecimal(dto.east);
    const west  = this.dmsToDecimal(dto.west);

    if ([north, south, east, west].some(isNaN))
      throw new BadRequestException('Invalid coordinates');
    if (north <= south) throw new BadRequestException('North must be greater than south');
    if (east  <= west)  throw new BadRequestException('East must be greater than west');

    const sq = this.computeSquareBbox(north, south, east, west);

    console.log(
      `[regions] "${dto.name}" — bbox original: ` +
      `${(Math.abs(east-west)*Math.PI/180*EARTH_RADIUS_M*Math.cos((north+south)/2*Math.PI/180)).toFixed(0)} × ` +
      `${(Math.abs(north-south)*Math.PI/180*EARTH_RADIUS_M).toFixed(0)} m` +
      ` → cuadrado: ${sq.sideM.toFixed(0)} × ${sq.sideM.toFixed(0)} m`,
    );

    try {
      fs.mkdirSync('uploads', { recursive: true });

      const ts            = Date.now();
      const tifOriginal   = `uploads/${ts}_original.tif`;
      const tifSquare     = `uploads/${ts}_square.tif`;
      const heightmapPath = `uploads/${ts}_heightmap.png`;

      fs.writeFileSync(tifOriginal, file.buffer);

      await this.clipToSquare(tifOriginal, tifSquare, sq);

      const { minElevation, maxElevation } = this.extractElevationRange(tifSquare);
      const verticalScale = maxElevation - minElevation;

      await this.convertToHeightmapPng(tifSquare, heightmapPath, minElevation, maxElevation);

      const heightmapName   = `${ts}_heightmap.png`;
      const heightmapBuffer = fs.readFileSync(heightmapPath);

      const { error: hmError } = await this.supabase.storage
        .from('heightmaps')
        .upload(heightmapName, heightmapBuffer, { contentType: 'image/png', upsert: true });

      if (hmError) throw hmError;

      const heightmapUrl =
        `${process.env.SUPABASE_URL}/storage/v1/object/public/heightmaps/${heightmapName}`;

      const imageryResponse = await axios.post(
        `${process.env.SATELLITE_IMAGERY_API}imagery/true-color`,
        {
          bbox:     [sq.west, sq.south, sq.east, sq.north],
          from:     '2012-01-01',
          to:       '2026-02-01',
          maxCloud: 5,
          width:    1024,
          height:   1024,
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
      // Re-lanzar BadRequestException tal cual (ej: el duplicado detectado
      // justo antes del insert si hubo race condition)
      if (err instanceof BadRequestException) throw err;
      console.error('[regions] create error:', err);
      throw new InternalServerErrorException('Region creation failed');
    } finally {
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

    return {
      ...data,
      north: data.bbox_north,
      south: data.bbox_south,
      east:  data.bbox_east,
      west:  data.bbox_west,
    };
  }
}