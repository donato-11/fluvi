import { IsString, IsNumber, IsArray } from 'class-validator';

export class CreateRegionDto {
    @IsString()
    name: string;

    @IsString()
    north: string;

    @IsString()
    south: string;

    @IsString()
    east: string;

    @IsString()
    west: string;
}