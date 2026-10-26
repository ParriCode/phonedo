// Piezas animadas de los paneles de rehabilitación cardiaca y cadena de frío.
import { useEffect, useRef, useState } from 'react';
import { CONFIG } from '../config.js';
import { useI18n } from '../providers/I18nProvider.jsx';

/** Número que cuenta hasta su valor cada vez que cambia. */
export function CountUp({ value, digits = 0, duration = 900 }) {
  const { lang } = useI18n();
  const [shown, setShown] = useState(0);
  const from = useRef(0);

  useEffect(() => {
    const start = performance.now();
    const origin = from.current;
    let frame = requestAnimationFrame(function step(now) {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - progress) ** 3;
      from.current = origin + (value - origin) * eased;
      setShown(from.current);
      if (progress < 1) frame = requestAnimationFrame(step);
    });
    return () => cancelAnimationFrame(frame);
  }, [value, duration]);

  return shown.toLocaleString(lang, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

const TICK_MS = 140;

/** Una sesión son 5 lecturas: se encienden una a una y hacen falta las de la política. */
export function SessionRing({ policy = CONFIG.policy, labels = { count: 'pol.count', reward: 'pol.reward' } }) {
  const { t } = useI18n();
  const { minCount, batch, payout } = policy;
  const [lit, setLit] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setLit((n) => (n >= batch + 8 ? 0 : n + 1)), TICK_MS);
    return () => clearInterval(timer);
  }, [batch]);

  const paid = lit >= minCount;
  return (
    <div className={paid ? 'ring paid' : 'ring'} role="img" aria-label={`${minCount}/${batch} ${t(labels.count)}`}>
      <svg viewBox="-60 -60 120 120">
        {Array.from({ length: batch }, (_, i) => {
          const angle = (i / batch) * Math.PI * 2 - Math.PI / 2;
          const required = i < minCount;
          return (
            <line key={i} x1={Math.cos(angle) * 40} y1={Math.sin(angle) * 40} x2={Math.cos(angle) * 54} y2={Math.sin(angle) * 54}
              className={`${i < lit ? 'on' : ''} ${required ? '' : 'spare'}`} />
          );
        })}
      </svg>
      <div className="ring-center">
        <b>{paid ? `+${payout} USDC` : `${Math.min(lit, minCount)}/${minCount}`}</b>
        <span>{paid ? t(labels.reward) : t(labels.count)}</span>
      </div>
    </div>
  );
}
