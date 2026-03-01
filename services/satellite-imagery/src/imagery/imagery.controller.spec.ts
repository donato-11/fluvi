import { Test, TestingModule } from '@nestjs/testing';
import { ImageryController } from './imagery.controller';

describe('ImageryController', () => {
  let controller: ImageryController;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      controllers: [ImageryController],
    }).compile();

    controller = module.get<ImageryController>(ImageryController);
  });

  it('should be defined', () => {
    expect(controller).toBeDefined();
  });
});
