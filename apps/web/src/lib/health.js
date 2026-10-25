// Reglas puras de presentación del estado y los logs del operador.
export const LOG_LEVELS = ['success', 'warning', 'error', 'critical'];

const CRITICAL = /private_key|seed|secret_leak|compromised|fatal|panic/i;
const ERROR = /failed|failure|error|exception|invalid|denied|unauthori[sz]ed/i;
const WARNING = /warning|warn|rejected|timeout|retry|missing|not_met|not_found|duplicate|conflict/i;
const SUCCESS = /paid|verified|accepted|created|stored|connected|started|ready|signed|completed/i;

export function logLevel(message, detail = {}) {
  const explicit = String(detail?.level || '').toLowerCase();
  if (LOG_LEVELS.includes(explicit)) return explicit;
  const text = `${message || ''} ${detail?.error || ''}`;
  if (CRITICAL.test(text)) return 'critical';
  if (ERROR.test(text)) return 'error';
  if (WARNING.test(text)) return 'warning';
  if (SUCCESS.test(text)) return 'success';
  return 'info';
}

export function sinceLabel(at, now, text = (es) => es) {
  if (!Number.isFinite(at)) return text('sin hora', 'no time');
  const seconds = Math.max(0, Math.floor((now - at) / 1000));
  if (seconds < 5) return text('ahora', 'now');
  if (seconds < 60) return text(`hace ${seconds} s`, `${seconds}s ago`);
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return text(`hace ${minutes} min`, `${minutes}m ago`);
  const hours = Math.floor(minutes / 60);
  return text(`hace ${hours} h`, `${hours}h ago`);
}

export function portLabel(address) {
  try {
    const url = new URL(address);
    return url.port ? `:${url.port}` : url.protocol === 'https:' ? ':443' : ':80';
  } catch { return '—'; }
}
