import { describe, expect, it } from 'vitest';
import { createChill } from './chill.js';

describe('enfriamiento por pulsaciones', () => {
  it('cada pulsación enfría, tiene tope y se recupera con el tiempo', () => {
    let time = 0;
    const chill = createChill({ drop: 1, recovery: 0.5, max: 3 }, () => time);
    expect(chill.level()).toBe(0);
    chill.press();
    chill.press();
    expect(chill.level()).toBe(2);
    time += 2000;
    expect(chill.level()).toBeCloseTo(1, 6);
    for (let i = 0; i < 10; i += 1) chill.press();
    expect(chill.level()).toBe(3);
    expect(chill.ratio()).toBe(1);
    time += 60000;
    expect(chill.level()).toBe(0);
  });
});
