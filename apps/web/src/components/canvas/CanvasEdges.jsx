import { TRANSPORTS, edgeGeometry } from '../../../service_network/edge.js';

/** Conexiones configuradas entre servicios, en coordenadas del mundo. */
export function CanvasEdges({ connections, positions, configuredLabel }) {
  return (
    <svg className="canvas__edges" aria-hidden="true">
      <defs>{TRANSPORTS.map((transport) => (
        <marker key={transport} id={`network-arrow-${transport}`} viewBox="0 0 8 8" refX="8" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path className={`edge__arrow edge__arrow--${transport}`} d="M 0 0 L 8 4 L 0 8 Z" /></marker>
      ))}</defs>
      {connections.filter((edge) => positions[edge.sourceId] && positions[edge.targetId]).map((edge) => {
        const geometry = edgeGeometry(positions[edge.sourceId], positions[edge.targetId]);
        const transport = TRANSPORTS.includes(edge.transport) ? edge.transport : 'http';
        const label = transport === 'stellar' ? 'Stellar' : transport.toUpperCase();
        return (
          <g key={edge.id} className={`edge edge--${transport}`}><title>{`${label} · ${configuredLabel}`}</title><path className="edge__path" markerEnd={`url(#network-arrow-${transport})`} d={geometry.path} /><text className="edge__label" x={geometry.x} y={geometry.y} textAnchor="middle">{label}</text></g>
        );
      })}
    </svg>
  );
}
