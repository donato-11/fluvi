// services/climate-ingestor/src/rainfall/rainfall.service.ts
import { Injectable, OnModuleInit } from "@nestjs/common"
import { HttpService } from "@nestjs/axios"
import { firstValueFrom } from "rxjs"

const SCENARIO_ENGINE_URL =
  process.env.SCENARIO_ENGINE_URL ?? "http://localhost:8000"

const HEARTBEAT_TIMEOUT_MS = 15_000   // 15s sin heartbeat → nodo caído

interface NodeInfo {
  nodeId: string
  simulationId: string
  socketId: string
  lastHeartbeat: number
}

@Injectable()
export class RainfallService implements OnModuleInit {
  private nodes = new Map<string, NodeInfo>()

  constructor(private readonly http: HttpService) {}

  onModuleInit() {
    // Monitor de heartbeat cada 5s
    setInterval(() => this.checkHeartbeats(), 5_000)
  }

  registerNode(nodeId: string, simulationId: string, socketId: string) {
    this.nodes.set(nodeId, {
      nodeId,
      simulationId,
      socketId,
      lastHeartbeat: Date.now(),
    })
  }

  updateHeartbeat(nodeId: string, timestamp: number) {
    const node = this.nodes.get(nodeId)
    if (node) node.lastHeartbeat = timestamp
  }

  handleNodeDisconnect(socketId: string) {
    for (const [id, node] of this.nodes.entries()) {
      if (node.socketId === socketId) {
        console.warn(`[ingestor] nodo desconectado: ${id}`)
        this.nodes.delete(id)
      }
    }
  }

  async forwardToScenarioEngine(payload: {
    nodeId: string
    simulationId: string
    timestamp: number
    source: string
    data: { intensity_mm_h: number }
  }) {
    // Reenvío HTTP interno al scenario-engine
    await firstValueFrom(
      this.http.post(`${SCENARIO_ENGINE_URL}/ingest/rainfall`, {
        simulation_id: payload.simulationId,
        node_id: payload.nodeId,
        timestamp: payload.timestamp,
        source: payload.source,
        intensity_mm_h: payload.data.intensity_mm_h,
      }),
    )
  }

  private checkHeartbeats() {
    const now = Date.now()
    for (const [id, node] of this.nodes.entries()) {
      if (now - node.lastHeartbeat > HEARTBEAT_TIMEOUT_MS) {
        console.warn(`[ingestor] ⚠ heartbeat perdido: ${id} — nodo marcado down`)
        this.nodes.delete(id)
        // TODO: notificar al api-gateway para activar nodo espejo
      }
    }
  }
}
