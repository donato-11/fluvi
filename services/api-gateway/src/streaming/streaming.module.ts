import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { StreamingGateway } from './streaming.gateway';
import { StreamingController } from './streaming.controller';

@Module({
  imports: [HttpModule],
  providers: [StreamingGateway],
  controllers: [StreamingController]
})
export class StreamingModule {}
