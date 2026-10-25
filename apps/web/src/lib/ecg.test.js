import { describe, expect, it } from 'vitest';
import { beatShape, entryX, signalAt } from './ecg.js';

describe('electrocardiograma', () => {
  it('el latido es plano salvo en el QRS, con su pico en la onda R', () => {
    expect(beatShape(0.3)).toBe(1);
    expect(beatShape(0.318)).toBeLessThan(0);
    expect(beatShape(0.12)).toBe(0);
    expect(beatShape(0.9)).toBe(0);
  });

  it('la señal constante se repite cada periodo', () => {
    const options = { period: 400, offset: 37 };
    expect(signalAt(50, options)).toBeCloseTo(signalAt(450, options), 6);
  });

  it('un latido extra suma altura solo cerca de su posición', () => {
    const options = { period: 400, offset: 0, extras: [{ x: 1000, gain: 1.35 }] };
    const plain = { period: 400, offset: 0 };
    expect(signalAt(1000, options)).toBeGreaterThan(signalAt(1000, plain) + 1);
    expect(signalAt(200, options)).toBe(signalAt(200, plain));
  });

  it('el latido extra aparece junto al borde derecho sin pisar a los demás', () => {
    const base = { period: 760, width: 1440 };
    for (const offset of [0, 90, 200, 333, 700]) {
      const first = entryX({ ...base, offset });
      expect(Math.abs(first - base.width)).toBeLessThan(0.5 * base.period);
      const phase = (first + offset) / base.period - 0.3;
      expect(Math.abs(phase - Math.round(phase))).toBeGreaterThanOrEqual(0.3);
      const second = entryX({ ...base, offset, extras: [{ x: first }] });
      expect(Math.abs(second - first)).toBeGreaterThanOrEqual(0.3 * base.period);
    }
  });
});
