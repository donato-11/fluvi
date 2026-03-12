// services/climate-ingestor/src/rainfall/rainfall.gateway.ts
import {
  WebSocketGateway,
  SubscribeMessage,
  MessageBody,
  ConnectedSocket,
  OnGatewayDisconnect,
} from "@nestjs/websockets"
import { Socket, Server } from "socket.io"
import { WebSocketServer } from "@nestjs/websockets"
import { RainfallService } from "./rainfall.service"

@WebSocketGateway({ cors: true, path: "/rainfall" })
export class RainfallGateway implements OnGatewayDisconnect {
  @WebSocketServer() server: Server

  constructor(private readonly rainfallService: RainfallService) {}

  // Registro del nodo simulador
  @SubscribeMessage("node:register")
  handleRegister(
    @MessageBody() data: { nodeId: string; simulationId: string },
    @ConnectedSocket() client: Socket,
  ) {
    this.rainfallService.registerNode(data.nodeId, data.simulationId, client.id)
    console.log(`[ingestor] nodo registrado: ${data.nodeId}`)
  }

  // Datos de lluvia provenientes del simulador (o sensor real — agnóstico)
  @SubscribeMessage("rainfall:data")
  async handleRainfallData(
    @MessageBody()
    payload: {
      nodeId: string
      simulationId: string
      timestamp: number
      source: "simulator" | "sensor"   // ← agnóstico
      data: { intensity_mm_h: number }
    },
  ) {
    await this.rainfallService.forwardToScenarioEngine(payload)
  }

  // Heartbeat del nodo
  @SubscribeMessage("heartbeat")
  handleHeartbeat(
    @MessageBody() data: { nodeId: string; simulationId: string; timestamp: number },
  ) {
    this.rainfallService.updateHeartbeat(data.nodeId, data.timestamp)
  }

  handleDisconnect(client: Socket) {
    this.rainfallService.handleNodeDisconnect(client.id)
  }
}
