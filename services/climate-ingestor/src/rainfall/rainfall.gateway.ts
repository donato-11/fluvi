import { SubscribeMessage, WebSocketGateway } from '@nestjs/websockets';
import { Interval } from '@nestjs/schedule';
import { RainfallService } from './rainfall.service';

@WebSocketGateway()
export class RainfallGateway {
  constructor(private readonly rainfallService: RainfallService) {}

  @SubscribeMessage('message')
  handleMessage(client: any, payload: any): string {
    return 'Hello world!';
  }

  @Interval(1000)
  emitRain() {
    this.server.emit('rainfall', {
      value: this.rainfallService.generateRain(),
      timestamp: Date.now()
    });
  }

}
