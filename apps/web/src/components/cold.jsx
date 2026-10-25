// Piezas del panel de cadena de frío: termómetro animado y la política acordada.
import { useEffect, useState } from 'react';
import { CONFIG } from '../config.js';
import { chill } from '../lib/chill.js';
import { reading } from '../lib/frost.js';
import { useI18n } from '../providers/I18nProvider.jsx';

const SCALE = { low: 0, high: 10 }; // °C que abarca el tubo

/**
 * Termómetro con la franja acordada. La lectura es simulada (como el Reader de la demo) y
 * baja con cada pulsación en la página (`chill`), para recuperarse después poco a poco.
 */
export function Thermometer() {
  const { t, lang } = useI18n();
  const { min, max } = CONFIG.coldPolicy;
  const [degrees, setDegrees] = useState(() => reading(0));

  useEffect(() => {
    const start = performance.now();
    const timer = setInterval(() => {
      setDegrees(Math.max(SCALE.low, reading((performance.now() - start) / 1000) - chill.level()));
    }, 60);
    return () => clearInterval(timer);
  }, []);

  const y = (value) => 150 - ((value - SCALE.low) / (SCALE.high - SCALE.low)) * 130;
  return (
    <div className="thermo" role="img" aria-label={`${degrees.toFixed(1)} °C`}>
      <svg viewBox="0 0 90 200">
        <rect x="34" y={y(max)} width="22" height={y(min) - y(max)} className="thermo-band" />
        <rect x="38" y="14" width="14" height="150" rx="7" className="thermo-tube" />
        <circle cx="45" cy="170" r="18" className="thermo-bulb" />
        <rect x="41" y={y(degrees)} width="8" height={170 - y(degrees)} className="thermo-mercury" />
        <circle cx="45" cy="170" r="12" className="thermo-mercury" />
        {[min, max].map((mark) => (
          <g key={mark}><line x1="58" x2="70" y1={y(mark)} y2={y(mark)} className="thermo-mark" /><text x="73" y={y(mark) + 4}>{mark}°</text></g>
        ))}
      </svg>
      <div className="thermo-value"><b>{degrees.toLocaleString(lang, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} °C</b><span>{t('ct.simulated')}</span></div>
    </div>
  );
}

export function ColdPolicyTiles() {
  const { t } = useI18n();
  const p = CONFIG.coldPolicy;
  return (
    <div className="policy">
      <div><b>{p.min}–{p.max} °C</b><span>{t('ct.range')}</span></div>
      <div><b>{p.minCount}/{p.batch}</b><span>{t('ct.count')}</span></div>
      <div><b>{p.payout} USDC</b><span>{t('ct.reward')}</span></div>
    </div>
  );
}
