import {
  Controller,
  Post,
  Body,
  Res,
  HttpException,
  HttpStatus,
} from '@nestjs/common';
import type { Response } from 'express';
import { ImageryService } from './imagery.service';
import { RequestImageryDto } from './dto/request-imagery.dto';

@Controller('imagery')
export class ImageryController {
  constructor(
    private readonly imageryService: ImageryService,
  ) {}

  @Post('true-color')
  async getTrueColor(
    @Body() dto: RequestImageryDto,
    @Res() res: Response,
  ) {
    try {
      const imageBuffer = await this.imageryService.getTrueColor(dto);

      res.set({
        'Content-Type': 'image/png',
        'Content-Disposition': 'inline; filename="fluvi-image.png"',
      });

      return res.send(imageBuffer);
    } catch (error) {
      throw new HttpException(
        'Failed to fetch satellite imagery',
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }
}
