import { Test, TestingModule } from '@nestjs/testing';
import { ImageryService } from './imagery.service';

describe('ImageryService', () => {
  let service: ImageryService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [ImageryService],
    }).compile();

    service = module.get<ImageryService>(ImageryService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });
});
