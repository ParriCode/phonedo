import { describe, expect, it } from 'vitest';
import { fbm, frostAlpha, noise, reading, sideAlpha } from './frost.js';

describe('escarcha y temperatura simulada', () => {
  it('la temperatura simulada nunca sale de 2–8 °C', () => {
    for (let second = 0; second < 600; second += 0.37) {
      const degrees = reading(second);
      expect(degrees).toBeGreaterThan(2);
      expect(degrees).toBeLessThan(8);
    }
  });

  it('el ruido es determinista y se queda entre 0 y 1', () => {
    expect(noise(3.3, 8.1, 5)).toBe(noise(3.3, 8.1, 5));
    expect(noise(3.3, 8.1, 5)).not.toBe(noise(3.3, 8.1, 6));
    for (let i = 0; i < 200; i += 1) {
      const value = fbm(i * 0.37, i * 0.91, 11);
      expect(value).toBeGreaterThanOrEqual(0);
      expect(value).toBeLessThanOrEqual(1);
    }
  });

  it('la escarcha se desvanece al alejarse de la esquina y no pasa de su radio', () => {
    const average = (from, to) => {
      let sum = 0;
      let count = 0;
      for (let step = 0; step < 400; step += 1) {
        const angle = ((step % 20) / 20) * (Math.PI / 2);
        const distance = from + ((to - from) * Math.floor(step / 20)) / 20;
        sum += frostAlpha(Math.cos(angle) * distance, Math.sin(angle) * distance, 300, 11);
        count += 1;
      }
      return sum / count;
    };
    expect(average(10, 90)).toBeGreaterThan(average(180, 260));
    expect(frostAlpha(300, 0, 300, 11)).toBe(0);
    expect(frostAlpha(250, 250, 300, 11)).toBe(0);
    for (let i = 0; i < 100; i += 1) expect(frostAlpha(i, i / 2, 300, 11)).toBeLessThanOrEqual(1);
  });

  it('la escarcha lateral nace en el borde y no pasa de su alcance', () => {
    expect(sideAlpha(200, 100, 200, 3)).toBe(0);
    expect(sideAlpha(300, 100, 200, 3)).toBe(0);
    let near = 0;
    let far = 0;
    for (let y = 0; y < 300; y += 3) {
      near += sideAlpha(6, y, 200, 3);
      far += sideAlpha(150, y, 200, 3);
      expect(sideAlpha(30, y, 200, 3)).toBeLessThanOrEqual(1);
    }
    expect(near).toBeGreaterThan(far);
  });
});
