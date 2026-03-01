import { Injectable } from '@nestjs/common';
import { SentinelHubClient } from './sentinel-hub.client';
import { RequestImageryDto } from './dto/request-imagery.dto';

@Injectable()
export class ImageryService {
  constructor(
    private readonly sentinelHub: SentinelHubClient,
  ) {}

  async getTrueColor(dto: RequestImageryDto): Promise<Buffer> {
    const { bbox, from, to, maxCloud, width, height } = dto;

    return this.sentinelHub.getTrueColorImage(
      bbox,
      from,
      to,
      maxCloud,
      width,
      height,
    );
  }
}
