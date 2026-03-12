// services/climate-ingestor/src/rainfall/rainfall.module.ts
import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';          // ← fix: importar HttpModule
import { RainfallGateway } from './rainfall.gateway';
import { RainfallService } from './rainfall.service';

@Module({
  imports: [HttpModule],                              // ← fix: registrar HttpModule
  providers: [RainfallGateway, RainfallService],
})
export class RainfallModule {}
