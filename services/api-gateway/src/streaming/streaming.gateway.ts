// services/api-gateway/src/streaming/streaming.gateway.ts
import {
  WebSocketGateway,
  WebSocketServer,
  SubscribeMessage,
  MessageBody,
  ConnectedSocket,
} from '@nestjs/websockets';
import { Server, Socket } from 'socket.io';

export interface WaterLevelUpdate {
  simulationId: string;
  waterLevel: number;
  intensity: number;
  accumulatedRain: number;
  step: number;
  timestamp: number;
}

@WebSocketGateway({ cors: { origin: '*' }, path: '/ws' })
export class StreamingGateway {
  @WebSocketServer() server: Server;

  /** El cliente se une a la room de su simulación */
  @SubscribeMessage('subscribe')
  async handleSubscribe(
    @MessageBody() data: { simulationId: string },
    @ConnectedSocket() client: Socket,
  ) {
    await client.join(data.simulationId);
    client.emit('subscribed', { simulationId: data.simulationId });
  }

  @SubscribeMessage('unsubscribe')
  async handleUnsubscribe(
    @MessageBody() data: { simulationId: string },
    @ConnectedSocket() client: Socket,
  ) {
    await client.leave(data.simulationId);
  }

  /** Llamado por StreamingController cuando llega update del scenario-engine */
  broadcastUpdate(payload: WaterLevelUpdate) {
    this.server.to(payload.simulationId).emit('simulation:update', payload);
  }
}
