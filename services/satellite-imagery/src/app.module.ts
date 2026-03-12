import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { ImageryModule } from './imagery/imagery.module';
import { ConfigModule } from '@nestjs/config/dist/config.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
    }),
    ImageryModule,
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
