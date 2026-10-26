import { useEffect, useRef } from 'react';
import { TRANSPORTS, edgeGeometry } from '../../../service_network/edge.js';
import { PULSE_DURATION } from './useMessagePulses.js';

/** Bolita que recorre el cable; SMIL insertado tarde no arranca solo, así que se lanza a mano. */
function EdgePulse({ pulse, path }) {
  const ref = useRef(null);
  useEffect(() => {
    const timer = setTimeout(() => {
      const group = ref.current;
      if (!group) return;
      group.classList.add('edge__pulse--running');
      group.querySelectorAll('animateMotion').forEach((motion) => motion.beginElement?.());
    }, pulse.delay);
    return () => clearTimeout(timer);
  }, [pulse.delay]);
  const motion = (lag = 0) => <animateMotion begin="indefinite" dur={`${PULSE_DURATION + lag}ms`} fill="freeze" path={path} keyPoints={pulse.reverse ? '1;0' : '0;1'} keyTimes="0;1" calcMode="spline" keySplines=".4 0 .6 1" />;
  return (
    <g ref={ref} className={`edge__pulse edge__pulse--${pulse.level}`}>
      <circle className="edge__pulse-trail" r="5">{motion(120)}</circle>
      <circle className="edge__pulse-glow" r="13">{motion()}</circle>
      <circle className="edge__pulse-core" r="5">{motion()}</circle>
    </g>
  );
}

/**
 * Conexiones en coordenadas del mundo. El trazo comunica el estado:
 * HTTP línea fija · Stream con puntos que fluyen cuando hay datos · error en rojo con ✕.
 */
export function CanvasEdges({ connections, positions, states, selectedEdgeId, label, draft, onToggle, text, pulses = [] }) {
  return (
    <svg className="canvas__edges" role="group" aria-label={text('Conexiones del sistema', 'System connections')}>
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
            {pulses.filter((pulse) => pulse.edgeId === edge.id).map((pulse) => <EdgePulse key={pulse.id} pulse={pulse} path={geometry.path} />)}
            {state === 'error'
              ? <g className="edge__break" transform={`translate(${geometry.x} ${geometry.y + 9})`}><circle r="11" /><path d="M -4 -4 L 4 4 M 4 -4 L -4 4" /></g>
              : null}
            <foreignObject className="edge__control" x={geometry.x - 38} y={geometry.y - 16} width="76" height="32">
              <button type="button" className={`edge__switch edge__switch--${transport}`} data-edge-action="toggle" data-edge-toggle={edge.id}
                aria-label={text(`Cambiar transporte de ${label(edge, state)}`, `Change transport for ${label(edge, state)}`)}
                title={text('Pulsa para alternar HTTP y Stream', 'Click to switch between HTTP and Stream')}
                disabled={edge.targetKind === 'publisher'}
                onClick={() => onToggle(edge.sourceId, edge.targetId, transport === 'sse' ? 'http' : 'sse')}>
                <span className="edge__switch-dot" />{transport === 'sse' ? 'STREAM' : 'HTTP'}
              </button>
            </foreignObject>
          </g>
        );
      })}
      {draft ? <g className="edge edge--draft"><path className="edge__draft" d={`M ${draft.start.x} ${draft.start.y} C ${draft.start.x + 90} ${draft.start.y}, ${draft.end.x - 90} ${draft.end.y}, ${draft.end.x} ${draft.end.y}`} /><circle className="edge__draft-end" cx={draft.end.x} cy={draft.end.y} r="8" /></g> : null}
    </svg>
  );
}
