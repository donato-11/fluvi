import {
  Controller,
  Post,
  Body,
  UploadedFile,
  UseInterceptors
} from '@nestjs/common';

import { FileInterceptor } from '@nestjs/platform-express';

import { RegionsService } from './regions.service';
import { CreateRegionDto } from './dto/create-region.dto';

@Controller('regions')
export class RegionsController {

  constructor(private readonly regionsService: RegionsService) {}

    @Post()
    @UseInterceptors(FileInterceptor('tif'))
    create(
    @UploadedFile() file: Express.Multer.File,
    @Body() dto: CreateRegionDto
    ) {
  
    return this.regionsService.create(dto, file);
    }

}

