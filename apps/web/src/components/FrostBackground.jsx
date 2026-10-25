import { useEffect, useRef } from 'react';
import { chill } from '../lib/chill.js';
import { frostAlpha, sideAlpha } from '../lib/frost.js';

const CALM = 0.3; // opacidad de las esquinas en reposo; suben hasta 1 al enfriarse
const SIDES = 0.9; // opacidad máxima de la escarcha que se extiende por los laterales
const TOPBAR = 57; // alto de la barra superior: la escarcha de arriba nace justo debajo
const CORNERS = [[0, 0, 1, 1, 11], [1, 0, -1, 1, 23], [0, 1, 1, -1, 37], [1, 1, -1, -1, 51]];

/** Pinta en `layer` una textura de `size` x `high` px con la opacidad que da `alphaAt`. */
function texture(size, high, alphaAt) {
  const tile = new ImageData(size, high);
  for (let y = 0; y < high; y += 1) {
    for (let x = 0; x < size; x += 1) tile.data.set([238, 248, 255, Math.round(alphaAt(x, y) * 255)], (y * size + x) * 4);
  }
  const layer = document.createElement('canvas');
  layer.width = size;
  layer.height = high;
  layer.getContext('2d').putImageData(tile, 0, 0);
  return layer;
}

/**
 * Escarcha en las esquinas, dibujada una vez con ruido procedural. Al enfriarse el termómetro
 * se intensifica y se extiende por los laterales de la pantalla.
 */
export function FrostBackground() {
  const corners = useRef(null);
  const sides = useRef(null);

  useEffect(() => {
    const cornerContext = corners.current?.getContext?.('2d');
    const sideContext = sides.current?.getContext?.('2d');
    if (!cornerContext || !sideContext) return undefined;

    const paint = () => {
      const ratio = window.devicePixelRatio || 1;
      const width = window.innerWidth;
      const height = window.innerHeight;
      const reach = Math.min(420, Math.max(width, height) * 0.28);
      const span = Math.min(260, width * 0.2);
      for (const canvas of [corners.current, sides.current]) {
        canvas.width = width * ratio;
        canvas.height = height * ratio;
      }
      // La textura se calcula en px CSS y se amplía al dibujarla.
      for (const [cx, cy, sx, sy, seed] of CORNERS) {
        const layer = texture(Math.round(reach), Math.round(reach), (x, y) => frostAlpha(x, y, reach, seed));
        cornerContext.save();
        cornerContext.translate(cx * width * ratio, cy ? height * ratio : TOPBAR * ratio);
        cornerContext.scale(sx, sy);
        cornerContext.drawImage(layer, 0, 0, reach * ratio, reach * ratio);
        cornerContext.restore();
      }
      const band = texture(Math.round(span), Math.round(height - TOPBAR), (x, y) => sideAlpha(x, y, span, 77));
      for (const [at, direction] of [[0, 1], [width, -1]]) {
        sideContext.save();
        sideContext.translate(at * ratio, TOPBAR * ratio);
        sideContext.scale(direction, 1);
        sideContext.drawImage(band, 0, 0, span * ratio, (height - TOPBAR) * ratio);
        sideContext.restore();
      }
    };

    const tint = setInterval(() => {
      const level = chill.ratio();
      corners.current.style.opacity = String(CALM + (1 - CALM) * level);
      sides.current.style.opacity = String(SIDES * level ** 1.5);
    }, 100);
    // Calcular la textura tarda ~1 s: se hace tras pintar la página y sin repetirla en cada resize.
    let timer = setTimeout(paint, 50);
    const onResize = () => { clearTimeout(timer); timer = setTimeout(paint, 250); };
    window.addEventListener('resize', onResize);
    return () => { clearTimeout(timer); clearInterval(tint); window.removeEventListener('resize', onResize); };
  }, []);

  return (
    <>
      <canvas ref={corners} className="frost" aria-hidden="true" />
      <canvas ref={sides} className="frost frost-sides" aria-hidden="true" />
    </>
  );
}
