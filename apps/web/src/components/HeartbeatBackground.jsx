import { useEffect, useRef } from 'react';
import { entryX, signalAt } from '../lib/ecg.js';

const SPEED = 150; // px por segundo
const EXTRA_GAIN = 1.35;
const FLASH_MS = 700;

/**
 * Electrocardiograma a pantalla completa que no se detiene. Cada pulsación en la
 * página lanza al instante un latido extra desde el lateral derecho que cruza la pantalla.
 */
export function HeartbeatBackground() {
  const canvas = useRef(null);

  useEffect(() => {
    const element = canvas.current;
    const context = element?.getContext?.('2d');
    if (!context) return undefined;
    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const extras = [];
    const flashes = [];
    let width = 0;
    let height = 0;
    let frame = 0;
    let last = performance.now();
    let travelled = 0;
    const period = () => Math.max(640, width / 1.9);

    const resize = () => {
      const ratio = window.devicePixelRatio || 1;
      width = window.innerWidth;
      height = window.innerHeight;
      element.width = width * ratio;
      element.height = height * ratio;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
    };

    const onPress = () => {
      // Aparece al instante junto al borde derecho, en un hueco entre latidos, y se desplaza como el resto.
      extras.push({ x: entryX({ period: period(), offset: travelled, width, extras }), gain: EXTRA_GAIN });
      flashes.push(performance.now());
    };

    const draw = (now) => {
      const elapsed = Math.min(0.1, (now - last) / 1000);
      last = now;
      if (!still) travelled += SPEED * elapsed;
      for (const extra of extras) extra.x -= SPEED * elapsed * (still ? 0 : 1);
      while (extras.length && extras[0].x < -width * 0.7) extras.shift();

      const span = period();
      const base = height * 0.5;
      const amplitude = height * 0.26;
      context.clearRect(0, 0, width, height);

      const gradient = context.createLinearGradient(0, 0, width, 0);
      gradient.addColorStop(0, 'rgb(255 70 80 / 0%)');
      gradient.addColorStop(0.55, 'rgb(255 70 80 / 45%)');
      gradient.addColorStop(1, 'rgb(255 110 120 / 95%)');
      context.strokeStyle = gradient;
      context.lineWidth = 3;
      context.lineJoin = 'round';
      context.shadowColor = 'rgb(255 60 70 / 90%)';
      context.shadowBlur = 14;
      context.beginPath();
      let head = base;
      for (let x = 0; x <= width; x += 2) {
        head = base - amplitude * signalAt(x, { period: span, offset: travelled, extras });
        if (x === 0) context.moveTo(x, head); else context.lineTo(x, head);
      }
      context.stroke();
      context.shadowBlur = 24;
      context.fillStyle = '#ffe3e5';
      context.beginPath();
      context.arc(width - 2, head, 5, 0, Math.PI * 2);
      context.fill();

      context.shadowBlur = 0;
      for (let i = flashes.length - 1; i >= 0; i -= 1) {
        const progress = (now - flashes[i]) / FLASH_MS;
        if (progress >= 1) { flashes.splice(i, 1); continue; }
        const glow = context.createLinearGradient(width, 0, width - 320, 0);
        glow.addColorStop(0, `rgb(255 70 80 / ${Math.round((1 - progress) * 45)}%)`);
        glow.addColorStop(1, 'rgb(255 70 80 / 0%)');
        context.fillStyle = glow;
        context.fillRect(width - 320, 0, 320, height);
      }
      frame = requestAnimationFrame(draw);
    };

    resize();
    frame = requestAnimationFrame(draw);
    window.addEventListener('resize', resize);
    window.addEventListener('pointerdown', onPress);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointerdown', onPress);
    };
  }, []);

  return <canvas ref={canvas} className="heartbeat" aria-hidden="true" />;
}
