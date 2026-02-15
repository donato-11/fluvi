import { Test, TestingModule } from '@nestjs/testing';
import { RainfallGateway } from './rainfall.gateway';

describe('RainfallGateway', () => {
  let gateway: RainfallGateway;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [RainfallGateway],
    }).compile();

    gateway = module.get<RainfallGateway>(RainfallGateway);
  });

  it('should be defined', () => {
    expect(gateway).toBeDefined();
  });
});
