import { useEffect, useRef, useState } from 'react';

export const PULSE_DURATION = 900;
const STAGGER = 180;
const MAX_PULSES = 60;

/** Cada log nuevo de un servicio lanza un pulso por sus conexiones de salida (o de entrada si no tiene). */
export function useMessagePulses(logs = [], connections = []) {
  const [pulses, setPulses] = useState([]);
  const seen = useRef(null);
  useEffect(() => {
    if (!seen.current) { seen.current = new Set(logs.map((log) => log.id)); return; }
    const fresh = logs.filter((log) => !seen.current.has(log.id));
    if (!fresh.length) return;
    fresh.forEach((log) => seen.current.add(log.id));
    const next = [];
    // Los logs llegan por sondeo y en bloque: se escalonan para que se vean pasar uno tras otro.
    const lanes = {};
    for (const log of fresh.reverse()) {
      if (log.historical) continue;
      const out = connections.filter((edge) => edge.sourceId === log.node);
      const edges = out.length ? out : connections.filter((edge) => edge.targetId === log.node);
      for (const edge of edges) {
        const lane = lanes[edge.id] = (lanes[edge.id] ?? -1) + 1;
        next.push({ id: `${log.id}:${edge.id}`, edgeId: edge.id, level: log.level, reverse: !out.length, delay: Math.min(lane, 8) * STAGGER });
      }
    }
    if (!next.length) return;
    setPulses((current) => [...current, ...next].slice(-MAX_PULSES));
    const ids = new Set(next.map((pulse) => pulse.id));
    const last = Math.max(...next.map((pulse) => pulse.delay));
    setTimeout(() => setPulses((current) => current.filter((pulse) => !ids.has(pulse.id))), last + PULSE_DURATION + 200);
  }, [logs, connections]);
  return pulses;
}
