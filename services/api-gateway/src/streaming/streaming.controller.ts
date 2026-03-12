// services/api-gateway/src/streaming/streaming.controller.ts
import {
  Controller,
  Post,
  Delete,
  Param,
  Body,
  HttpCode,
} from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';
import { StreamingGateway} from './streaming.gateway';
import type { WaterLevelUpdate } from './streaming.gateway';

const SCENARIO_ENGINE =
  process.env.SCENARIO_ENGINE_URL ?? 'http://localhost:8000';

@Controller()
export class StreamingController {
  constructor(
    private readonly gateway: StreamingGateway,
    private readonly http: HttpService,
  ) {}

  // ── Proxy lifecycle → scenario-engine ────────────────────────────────────

  @Post('scenarios')
  async startSimulation(@Body() body: any) {
    const { data } = await firstValueFrom(
      this.http.post(`${SCENARIO_ENGINE}/scenarios`, body),
    );
    return data; // { simulation_id, status, region_id }
  }

  @Post('scenarios/:id/pause')
  @HttpCode(200)
  async pauseSimulation(@Param('id') id: string) {
    const { data } = await firstValueFrom(
      this.http.post(`${SCENARIO_ENGINE}/scenarios/${id}/pause`, {}),
    );
    return data;
  }

  @Post('scenarios/:id/resume')
  @HttpCode(200)
  async resumeSimulation(@Param('id') id: string) {
    const { data } = await firstValueFrom(
      this.http.post(`${SCENARIO_ENGINE}/scenarios/${id}/resume`, {}),
    );
    return data;
  }

  @Post('scenarios/:id/reset')
  @HttpCode(200)
  async resetSimulation(@Param('id') id: string) {
    const { data } = await firstValueFrom(
      this.http.post(`${SCENARIO_ENGINE}/scenarios/${id}/reset`, {}),
    );
    // Notificar al frontend que los valores volvieron a 0
    this.gateway.broadcastUpdate({
      simulationId: id,
      waterLevel: 0,
      intensity: 0,
      accumulatedRain: 0,
      step: 0,
      timestamp: Date.now(),
    });
    return data;
  }

  @Delete('scenarios/:id')
  @HttpCode(204)
  async stopSimulation(@Param('id') id: string) {
    await firstValueFrom(
      this.http.delete(`${SCENARIO_ENGINE}/scenarios/${id}`),
    );
  }

  // ── Receptor de updates desde scenario-engine ─────────────────────────────

  @Post('streaming/update')
  @HttpCode(200)
  handleUpdate(@Body() payload: WaterLevelUpdate) {
    this.gateway.broadcastUpdate(payload);
    return { ok: true };
  }
}
