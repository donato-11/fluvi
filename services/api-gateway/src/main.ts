import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { execSync } from 'child_process';

async function bootstrap() {
  try {
    const v = execSync('gdalwarp --version 2>&1').toString().trim();
    console.log('[GDAL]', v);
  } catch {
    console.error('[GDAL] NOT FOUND');
  }
  
  const app = await NestFactory.create(AppModule);

  app.enableCors({
    origin: [
      'https://fluvi-web.vercel.app',
      'http://localhost:3000',
    ],
    methods: ['GET', 'HEAD', 'PUT', 'PATCH', 'POST', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'Accept'],
    credentials: true,
  });

  await app.listen(process.env.PORT ?? 3001);
}
bootstrap();
