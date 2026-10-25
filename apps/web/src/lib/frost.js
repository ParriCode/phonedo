// Temperatura simulada del transporte y escarcha procedural de las esquinas, sin React.

/** Temperatura simulada (°C) en el segundo `seconds`: ondula suavemente dentro de 2–8 °C. */
export function reading(seconds) {
  return 5 + 1.9 * Math.sin(seconds * 0.9) + 0.6 * Math.sin(seconds * 2.3 + 1) + 0.3 * Math.sin(seconds * 5.1 + 2);
}

const hash = (x, y, seed) => {
  let h = Math.imul(x, 374761393) ^ Math.imul(y, 668265263) ^ Math.imul(seed, 2147483647);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
};

/** Ruido de valores suave (0 a 1) en (x, y). */
export function noise(x, y, seed) {
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  const fx = x - ix;
  const fy = y - iy;
  const u = fx * fx * (3 - 2 * fx);
  const v = fy * fy * (3 - 2 * fy);
  const top = hash(ix, iy, seed) * (1 - u) + hash(ix + 1, iy, seed) * u;
  const bottom = hash(ix, iy + 1, seed) * (1 - u) + hash(ix + 1, iy + 1, seed) * u;
  return top * (1 - v) + bottom * v;
}

/** Ruido fractal: suma de varias escalas, de 0 a 1. */
export function fbm(x, y, seed, octaves = 4) {
  let sum = 0;
  let amplitude = 0.5;
  let scale = 1;
  for (let i = 0; i < octaves; i += 1) {
    sum += amplitude * noise(x * scale, y * scale, seed + i);
    amplitude /= 2;
    scale *= 2;
  }
  return sum / (1 - 0.5 ** octaves) / 2;
}

/** Textura de escarcha (0 a 1) en (x, y): bruma con venas finas de cristal y grano. */
function texture(x, y, seed) {
  const warpX = fbm(x / 70, y / 70, seed + 3, 3);
  const warpY = fbm(x / 70 + 5.2, y / 70 + 1.3, seed + 4, 3);
  const cloud = fbm(x / 55 + 2.4 * warpX, y / 55 + 2.4 * warpY, seed);
  const vein = (1 - Math.abs(2 * fbm(x / 26 + 3 * warpX, y / 26 + 3 * warpY, seed + 7, 3) - 1)) ** 4;
  const grain = noise(x / 2.2, y / 2.2, seed + 11);
  return Math.min(1, Math.max(0, (0.55 * cloud + 0.7 * vein * cloud + 0.18 * grain - 0.2) * 1.8));
}

/**
 * Opacidad (0 a 1) de la escarcha de una esquina en (x, y), con el origen en la esquina y a
 * `radius` px de alcance: más densa junto a los bordes y desvaneciéndose hacia dentro.
 */
export function frostAlpha(x, y, radius, seed) {
  const distance = Math.hypot(x, y) / radius;
  if (distance >= 1) return 0;
  const edge = 0.55 + 0.45 * (1 - Math.min(x, y) / radius);
  return texture(x, y, seed) * (1 - distance) ** 1.5 * edge;
}

/** Opacidad de la escarcha que crece por un lateral: `x` px desde el borde, hasta `reach` px. */
export function sideAlpha(x, y, reach, seed) {
  if (x >= reach) return 0;
  return texture(x, y, seed) * (1 - x / reach) ** 1.6;
}
