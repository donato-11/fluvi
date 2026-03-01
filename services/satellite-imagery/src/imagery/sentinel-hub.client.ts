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
    maxCloud = 20,
    width = 1024,
    height = 1024,
  ): Promise<Buffer> {
    const token = await this.getToken();

    const evalscript = `
      //VERSION=3
      function setup() {
        return {
          input: ["B02", "B03", "B04", "SCL"],
          output: { bands: 3 }
        };
      }

      function evaluatePixel(sample) {
        if ([8, 9, 10].includes(sample.SCL)) {
          return [1, 0, 0];
        } else {
          return [
            2.5 * sample.B04,
            2.5 * sample.B03,
            2.5 * sample.B02
          ];
        }
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