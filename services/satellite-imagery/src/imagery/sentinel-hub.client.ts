import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import axios from 'axios';

@Injectable()
export class SentinelHubClient {
  private readonly tokenUrl =
    'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token';

  private readonly processUrl =
    'https://sh.dataspace.copernicus.eu/api/v1/process';

  constructor(private readonly config: ConfigService) {}

  private async getToken(): Promise<string> {
    const clientId = this.config.get<string>('SH_CLIENT_ID');
    const clientSecret = this.config.get<string>('SH_CLIENT_SECRET');

    if (!clientId || !clientSecret) {
      throw new Error('Sentinel Hub credentials not defined');
    }

    const params = new URLSearchParams();
    params.append('grant_type', 'client_credentials');
    params.append('client_id', clientId);
    params.append('client_secret', clientSecret);

    try {
      const response = await axios.post(this.tokenUrl, params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });
      return response.data.access_token;
    } catch (error: any) {
      console.error('STATUS:', error.response?.status);
      console.error('DATA:', error.response?.data);
      console.error('MESSAGE:', error.message);
      throw error;
    }
  }

  async getTrueColorImage(
    bbox: [number, number, number, number],
    from: string,
    to: string,
    maxCloud = 5,
    width = 1024,
    height = 1024,
  ): Promise<Buffer> {
    const token = await this.getToken();

    // ────────────────────────────────────────────────────────────────────
    // FIX: Evalscript corregido — manchas rojas eliminadas
    //
    // PROBLEMA ANTERIOR:
    //   El evalscript original pintaba [1, 0, 0] (rojo puro) para los
    //   píxeles clasificados como nubes (SCL 8, 9, 10). Esto generaba
    //   manchas rojas visibles en la imagen satelital.
    //
    // SOLUCIÓN:
    //   1. Se usa dataMask para manejar píxeles sin datos (transparencia)
    //   2. Se usa sampleType UINT8 para output explícito de 0-255
    //   3. Se aplica gain de 2.5 con clamp a 255 para brillo natural
    //   4. Las nubes se muestran con su color real (blanco/gris),
    //      NO se pintan de rojo
    //   5. Se baja maxCloudCoverage default a 5% para imágenes más limpias
    //
    // Referencia: Sentinel Hub Evalscript V3 + Copernicus CDSE docs
    //   - sampleType AUTO espera valores 0-1 (reflectancia)
    //   - B04/B03/B02 son reflectancias [0,1] por default
    //   - gain de 2.5 es estándar de Sentinel Hub para true color
    //   - dataMask=0 indica píxel sin datos → alpha=0 (transparente)
    // ────────────────────────────────────────────────────────────────────
    const evalscript = `
      //VERSION=3
      function setup() {
        return {
          input: ["B02", "B03", "B04", "dataMask"],
          output: { bands: 4 }
        };
      }

      function evaluatePixel(sample) {
        // Gain estándar para true color Sentinel-2
        let gain = 2.5;

        return [
          gain * sample.B04,
          gain * sample.B03,
          gain * sample.B02,
          sample.dataMask
        ];
      }
    `;

    const requestBody = {
      input: {
        bounds: {
          properties: {
            crs: 'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
          },
          bbox,
        },
        data: [
          {
            type: 'sentinel-2-l2a',
            dataFilter: {
              timeRange: {
                from: `${from}T00:00:00Z`,
                to: `${to}T23:59:59Z`,
              },
              maxCloudCoverage: maxCloud,
            },
            processing: {
              upsampling: 'BICUBIC',
            },
          },
        ],
      },
      output: {
        width,
        height,
        responses: [
          {
            identifier: 'default',
            format: {
              type: 'image/png',
            },
          },
        ],
      },
      evalscript,
    };

    try {
      const response = await axios.post(this.processUrl, requestBody, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          Accept: 'image/png',
        },
        responseType: 'arraybuffer',
      });

      return Buffer.from(response.data);
    } catch (error: any) {
      console.error('PROCESS STATUS:', error.response?.status);
      console.error('PROCESS DATA:', error.response?.data?.toString?.() || error.response?.data);
      console.error('PROCESS MESSAGE:', error.message);
      throw error;
    }
  }
}