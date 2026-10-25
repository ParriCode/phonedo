import { Icon } from '../Icon.jsx';

export const healthLabel = (health, text) => ({
  healthy: text('Operativo', 'Healthy'), degraded: text('Con avisos', 'Degraded'),
  error: text('Caído', 'Down'), stale: text('Sin datos recientes', 'Stale'),
  unknown: text('Sin comprobar', 'Unknown'),
}[health] || health);

export const edgeLabel = (state, text) => ({
  active: text('Activa', 'Active'), idle: text('Sin actividad', 'Idle'),
  error: text('Interrumpida', 'Broken'), unknown: text('Sin comprobar', 'Unknown'),
}[state] || state);

export const transportLabel = (transport) => ({ http: 'HTTP', sse: 'Stream SSE', stellar: 'Stellar' }[transport] || transport);

export const levelLabel = (level, text) => ({
  success: text('Correcto', 'Success'), warning: text('Aviso', 'Warning'),
  error: 'Error', critical: text('Crítico', 'Critical'), info: 'Info',
}[level] || level);

export function LevelBadge({ level }) {
  return <span className={`level level--${level}`}><i />{level}</span>;
}

export function HealthBadge({ health, text, large = false }) {
  return <span className={`health health--${health}${large ? ' health--large' : ''}`}><i />{healthLabel(health, text)}</span>;
}

export function StreamBadge() {
  return <span className="stream-badge"><Icon name="zap" />Stream</span>;
}
