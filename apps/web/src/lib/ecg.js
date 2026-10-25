// Latido de electrocardiograma (solo el complejo QRS, en líneas rectas) y su trazado en el lienzo de fondo.
const QRS = [[0.27, 0], [0.285, -0.12], [0.3, 1], [0.318, -0.28], [0.335, 0]];

/** Altura (de -0,3 a 1) del latido en la fase `phase` (0 a 1): plana salvo en el QRS. */
export function beatShape(phase) {
  if (phase <= QRS[0][0] || phase >= QRS[QRS.length - 1][0]) return 0;
  const next = QRS.findIndex(([at]) => at >= phase);
  const [from, fromHeight] = QRS[next - 1];
  const [to, toHeight] = QRS[next];
  return fromHeight + ((phase - from) / (to - from)) * (toHeight - fromHeight);
}

/**
 * Altura de la señal en `x`: el ritmo constante (un latido cada `period` px, desplazado
 * `offset` px) más los latidos extra, cada uno con su posición `x` y su fuerza `gain`.
 */
export function signalAt(x, { period, offset, extras = [] }) {
  const cycle = (x + offset) / period;
  let value = beatShape(cycle - Math.floor(cycle));
  for (const { x: at, gain } of extras) value += gain * beatShape(0.3 + (x - at) / period);
  return value;
}

/**
 * Posición del latido extra al pulsar: lo más cerca posible del borde derecho (`width`) y a una
 * distancia mínima de los latidos constantes y de los demás extras, para verlo al instante.
 */
export function entryX({ period, offset, width, extras = [], gap = 0.3 }) {
  const apart = (x) => {
    const phase = (x + offset) / period - 0.3;
    const constant = Math.abs(phase - Math.round(phase));
    return constant >= gap && extras.every((extra) => Math.abs(extra.x - x) >= gap * period);
  };
  const start = width * 0.96;
  for (let step = 0; step < 200; step += 1) {
    const x = start + (step % 2 ? 1 : -1) * Math.ceil(step / 2) * 0.01 * period;
    if (x > 0 && apart(x)) return x;
  }
  return start;
}
