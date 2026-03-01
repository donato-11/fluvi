import { Injectable } from '@nestjs/common';
import { exec } from 'child_process';
import { promisify } from 'util';

@Injectable()
export class ProcessingService {
  private readonly execPromise = promisify(exec);

  async reproject(input: string, output: string): Promise<void> {
    await this.execPromise(
      `gdalwarp -t_srs EPSG:4326 ${input} ${output}`
    );
  }

  async clip(input: string, bbox: [number, number, number, number], output: string): Promise<void> {
    const [west, south, east, north] = bbox;

    await this.execPromise(
      `gdal_translate -projwin ${west} ${north} ${east} ${south} ${input} ${output}`
    );
  }

  async convertToPNG(input: string, output: string): Promise<void> {
    await this.execPromise(
      `gdal_translate -of PNG ${input} ${output}`
    );
  }
}