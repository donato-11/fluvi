import { IsArray, IsNumber, IsString, IsOptional, ArrayMinSize, ArrayMaxSize, } from 'class-validator';
import { Type } from 'class-transformer';

export class RequestImageryDto {

   @IsArray()
    @ArrayMinSize(4)
    @ArrayMaxSize(4)
    @Type(() => Number)
    bbox: [number, number, number, number];

  @IsString()
  from: string;

  @IsString()
  to: string;

  @IsOptional()
  @IsNumber()
  maxCloud?: number;

  @IsOptional()
  @IsNumber()
  width?: number;

  @IsOptional()
  @IsNumber()
  height?: number;
}