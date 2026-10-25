import { NODE_SIZE } from './models.js';

export const TRANSPORTS = Object.freeze(['http', 'sse', 'stellar']);

/** Geometría en coordenadas del mundo: permanece estable durante pan/zoom. */
export function edgeGeometry(source, target) {
  const forward = target.x >= source.x;
  const x1 = source.x + (forward ? NODE_SIZE.width : 0);
  const x2 = target.x + (forward ? 0 : NODE_SIZE.width);
  const y1 = source.y + NODE_SIZE.height / 2;
  const y2 = target.y + NODE_SIZE.height / 2;
  const direction = forward ? 1 : -1;
  const bend = Math.max(64, Math.abs(x2 - x1) / 2);
  return { path: `M ${x1} ${y1} C ${x1 + bend * direction} ${y1} ${x2 - bend * direction} ${y2} ${x2} ${y2}`, x: (x1 + x2) / 2, y: (y1 + y2) / 2 - 9 };
}
