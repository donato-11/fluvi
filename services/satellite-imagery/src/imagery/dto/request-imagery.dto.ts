export class RequestImageryDto {
  bbox: [number, number, number, number];
  from: string;
  to: string;
  maxCloud?: number;
  width?: number;
  height?: number;
}