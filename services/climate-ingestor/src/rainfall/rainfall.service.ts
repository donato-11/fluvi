import { Injectable } from '@nestjs/common';

@Injectable()
export class RainfallService {
    generateRain(): number {
        return Number((Math.random() * 30).toFixed(2));
    }

}
