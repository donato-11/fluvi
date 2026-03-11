import {
  Injectable,
  BadRequestException,
  InternalServerErrorException,
} from '@nestjs/common';

import { Express } from 'express';
import { spawn } from "child_process";
import * as fs from "fs";
import * as path from "path";
import axios from "axios";

import { createClient } from "@supabase/supabase-js";

import { CreateRegionDto } from "./dto/create-region.dto";

@Injectable()
export class RegionsService {

  private supabase = createClient(
    process.env.SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_KEY!
  );

  private dmsToDecimal(dms: string): number {
    const parts = dms.match(/-?\d+(\.\d+)?/g);
    if (!parts || parts.length < 3) return NaN;

    const deg = parseFloat(parts[0]);
    const min = parseFloat(parts[1]);
    const sec = parseFloat(parts[2]);

    const sign = deg < 0 ? -1 : 1;

    return sign * (Math.abs(deg) + min / 60 + sec / 3600);
  }

  private generateHeightmap(input: string, output: string): Promise<void> {
    return new Promise((resolve, reject) => {

      const process = spawn("gdal_translate", [
        "-outsize", "1024", "1024",
        "-b", "1",
        "-scale",
        "-ot", "UInt16",
        "-of", "PNG",
        input,
        output
      ]);

      process.on("close", (code) => {
        if (code === 0) resolve();
        else reject(new Error("Heightmap conversion failed"));
      });

    });
  }

  async create(dto: CreateRegionDto, file: Express.Multer.File) {

    if (!file) {
      throw new BadRequestException("TIF file is required");
    }

    const north = this.dmsToDecimal(dto.north);
    const south = this.dmsToDecimal(dto.south);
    const east = this.dmsToDecimal(dto.east);
    const west = this.dmsToDecimal(dto.west);

    if (isNaN(north) || isNaN(south) || isNaN(east) || isNaN(west)) {
      throw new BadRequestException("Invalid coordinates");
    }

    if (north <= south) {
      throw new BadRequestException("North must be greater than south");
    }

    if (east <= west) {
      throw new BadRequestException("East must be greater than west");
    }

    try {

      fs.mkdirSync("uploads", { recursive: true });

      const tifPath = `uploads/${Date.now()}_${file.originalname}`;
      fs.writeFileSync(tifPath, file.buffer);

      const heightmapPath = tifPath.replace(/\.tiff?$/i, ".png");

      await this.generateHeightmap(tifPath, heightmapPath);

      const heightmapBuffer = fs.readFileSync(heightmapPath);

      const heightmapName = path.basename(heightmapPath);

      const { data, error } = await this.supabase
        .storage
        .from("heightmaps")
        .upload(heightmapName, heightmapBuffer, {
          contentType: "image/png",
          upsert: true
        });

      if (error || !data) {
        throw error ?? new Error("Upload failed");
      }

      const heightmapUrl =
        `${process.env.SUPABASE_URL}/storage/v1/object/public/heightmaps/${heightmapName}`;

      const imageryResponse = await axios.post(
        "http://localhost:3003/imagery/true-color",
        {
          bbox: [west, south, east, north],
          from: "2018-01-01",
          to: "2026-02-01",
          maxCloud: 10,
          width: 1024,
          height: 1024
        },
        {
          responseType: "arraybuffer"
        }
      );

      const textureBuffer = Buffer.from(imageryResponse.data);
      
      const textureName = `${Date.now()}_texture.png`;

      const { error: textureError } = await this.supabase
        .storage
        .from("color_texture")
        .upload(textureName, textureBuffer, {
          contentType: "image/png",
          upsert: true
        });

      if (textureError) throw textureError;

      const textureUrl =
        `${process.env.SUPABASE_URL}/storage/v1/object/public/color_texture/${textureName}`;
      const { error: dbError } = await this.supabase
        .from("basins")
        .insert({
          name: dto.name,
          heightmap_url: heightmapUrl,
          color_texture_url: textureUrl,
          resolution: 30
        });
        
        if (dbError) throw dbError;
        
        return {
          status: "created",
          region: {
            name: dto.name,
            heightmap_url: heightmapUrl,
            color_texture_url: textureUrl
          }
        };
        
    } catch (error) {

      console.error(error);

      throw new InternalServerErrorException(
        "Region creation failed"
      );

    }

  }

  async searchBasins(query: string) {

    if (!query || query.length < 2) {
      return [];
    }

    const { data, error } = await this.supabase
      .from("basins")
      .select("id, name")
      .ilike("name", `%${query}%`)
      .limit(10);

    if (error) {
      console.error(error);
      throw new InternalServerErrorException("Search failed");
    }

    return data;
  }

  async findOne(id: string) {

    const { data, error } = await this.supabase
      .from("basins")
      .select("*")
      .eq("id", id)
      .single();

    if (error || !data) {
      throw new BadRequestException("Region not found");
    }

    return data;
  }

}
