import { NODE_SIZE } from './models.js';

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

export function renderEdges(svg, connections, positions, { escape, configuredLabel }) {
  const markers = ['http', 'sse', 'stellar'].map((transport) => `<marker id="network-arrow-${transport}" viewBox="0 0 8 8" refX="8" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path class="edge__arrow edge__arrow--${transport}" d="M 0 0 L 8 4 L 0 8 Z"/></marker>`).join('');
  svg.innerHTML = `<defs>${markers}</defs>` + connections.filter((edge) => positions[edge.sourceId] && positions[edge.targetId]).map((edge) => {
    const geometry = edgeGeometry(positions[edge.sourceId], positions[edge.targetId]);
    const transport = ['http', 'sse', 'stellar'].includes(edge.transport) ? edge.transport : 'http';
    const label = transport === 'stellar' ? 'Stellar' : transport.toUpperCase();
    return `<g class="edge edge--${transport}"><title>${escape(label + ' · ' + configuredLabel)}</title><path class="edge__path" marker-end="url(#network-arrow-${transport})" d="${geometry.path}"/><text class="edge__label" x="${geometry.x}" y="${geometry.y}" text-anchor="middle">${label}</text></g>`;
  }).join('');
}
