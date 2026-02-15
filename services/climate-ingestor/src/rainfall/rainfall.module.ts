import { Module } from '@nestjs/common';
import { RainfallService } from './rainfall.service';
import { RainfallGateway } from './rainfall.gateway';

@Module({
  providers: [RainfallService, RainfallGateway]
})
export class RainfallModule {}
