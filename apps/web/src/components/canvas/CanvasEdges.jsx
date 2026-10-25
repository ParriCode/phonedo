import { TRANSPORTS, edgeGeometry } from '../../../service_network/edge.js';

/**
 * Conexiones en coordenadas del mundo. El trazo comunica el estado:
 * HTTP línea fija · Stream con puntos que fluyen cuando hay datos · error en rojo con ✕.
 */
export function CanvasEdges({ connections, positions, states, selectedEdgeId, label }) {
  return (
    <svg className="canvas__edges" aria-hidden="true">
      <defs>{[...TRANSPORTS, 'error'].map((kind) => (
        <marker key={kind} id={`network-arrow-${kind}`} viewBox="0 0 8 8" refX="8" refY="4" markerUnits="userSpaceOnUse" markerWidth="11" markerHeight="11" orient="auto-start-reverse"><path className={`edge__arrow edge__arrow--${kind}`} d="M 0 0 L 8 4 L 0 8 Z" /></marker>
      ))}</defs>
      {connections.filter((edge) => positions[edge.sourceId] && positions[edge.targetId]).map((edge) => {
        const geometry = edgeGeometry(positions[edge.sourceId], positions[edge.targetId]);
        const transport = TRANSPORTS.includes(edge.transport) ? edge.transport : 'http';
        const state = states[edge.id] ?? 'unknown';
        const marker = state === 'error' ? 'error' : transport;
        return (
          <g key={edge.id} data-edge-id={edge.id} className={`edge edge--${transport} edge--${state}${edge.id === selectedEdgeId ? ' edge--selected' : ''}`}>
            <title>{label(edge, state)}</title>
            <path className="edge__hit" d={geometry.path} />
            <path className="edge__path" markerEnd={`url(#network-arrow-${marker})`} d={geometry.path} />
            {transport === 'sse' && state === 'active' ? <path className="edge__flow" d={geometry.path} /> : null}
            {state === 'error'
              ? <g className="edge__break" transform={`translate(${geometry.x} ${geometry.y + 9})`}><circle r="11" /><path d="M -4 -4 L 4 4 M 4 -4 L -4 4" /></g>
              : <text className="edge__label" x={geometry.x} y={geometry.y} textAnchor="middle">{transport === 'sse' ? 'STREAM' : transport === 'stellar' ? 'Stellar' : 'HTTP'}</text>}
          </g>
        );
      })}
    </svg>
  );
}
