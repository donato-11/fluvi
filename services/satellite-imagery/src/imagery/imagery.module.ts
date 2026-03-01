import { Module } from '@nestjs/common';
import { ImageryController } from './imagery.controller';
import { ImageryService } from './imagery.service';
import { SentinelHubClient } from './sentinel-hub.client';

@Module({
  controllers: [ImageryController],
  providers: [
    ImageryService,
    SentinelHubClient
  ],
  exports: [ImageryService],
})
export class ImageryModule {}
