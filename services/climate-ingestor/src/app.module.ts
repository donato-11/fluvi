import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { RainfallModule } from './rainfall/rainfall.module';

@Module({
  imports: [RainfallModule],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
