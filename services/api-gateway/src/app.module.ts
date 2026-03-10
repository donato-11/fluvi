import { Module } from '@nestjs/common';
import { ServeStaticModule } from '@nestjs/serve-static';
import { ConfigModule } from '@nestjs/config';
import { join } from 'path';

import { AppController } from './app.controller';
import { AppService } from './app.service';
import { AuthModule } from './auth/auth.module';
import { ScenariosModule } from './scenarios/scenarios.module';
import { StreamingModule } from './streaming/streaming.module';
import { RegionsModule } from './regions/regions.module';


@Module({
  imports: [
    AuthModule, 
    ScenariosModule, 
    StreamingModule, 
    RegionsModule,
    ServeStaticModule.forRoot({
      rootPath: join(__dirname, '..', 'uploads'),
      serveRoot: '/files',
    }),
    ConfigModule.forRoot({
      isGlobal: true
    }),
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
