// Actividad del despliegue: etapas del ciclo de vida, recorrido de las observaciones y logs.
import { KINDS } from '../../config.js';
import { short } from '../../lib/format.js';
import { useI18n } from '../../providers/I18nProvider.jsx';
import { useNetwork } from '../../providers/NetworkProvider.jsx';
import { useOperator } from '../../providers/OperatorProvider.jsx';
import { Icon } from '../Icon.jsx';

export const STAGES = [
  ['reader', 'cpu', 'Captura', 'Capture'], ['manager', 'hub', 'Coordinación', 'Routing'],
  ['verifier', 'shield', 'Verificación', 'Verification'], ['storage', 'db', 'Guardado', 'Storage'],
  ['publisher', 'send', 'Prueba y publicación', 'Proof & publication'],
];

function LifecyclePanel() {
  const { lang, opText } = useI18n();
  const { network } = useNetwork();
  const { active, stage, toggleStage } = useOperator();
  return (
    <div className="lifecycle" aria-label={opText('Ciclo de vida de los datos', 'Data lifecycle')}>{STAGES.map(([kind, icon, es, en], index) => {
      const recent = network.some((node) => node.kind === kind && Date.now() - (active[node.id] || 0) < 6000);
      return (
        <button key={kind} className={`life-stage ${recent ? 'is-active' : ''}`} data-stage={kind} aria-pressed={stage === kind} onClick={() => toggleStage(kind)}>
          <span className="life-icon"><Icon name={icon} /></span><small>0{index + 1}</small><b>{lang === 'es' ? es : en}</b>
          <span>{recent ? opText('Actividad reciente', 'Recent activity') : opText('En espera', 'Waiting')}</span></button>
      );
    })}</div>
  );
}

function ObservationJourney() {
  const { t, opText } = useI18n();
  const { logs } = useOperator();
  const created = logs.filter((log) => log.message === 'observation_created').slice(0, 4);
  if (!created.length) return null;
  return (
    <section className="journeys"><h3>{opText('Últimas observaciones', 'Latest observations')}</h3>{created.map((log) => {
      const id = log.detail.observationId;
      const related = logs.filter((item) => item.detail?.observationId === id);
      const done = [true, related.some((item) => item.message === 'manager_http_accepted'),
        related.some((item) => item.message === 'manager_reports_verified' || item.message === 'storage_observation_confirmed'),
        related.some((item) => item.message === 'storage_observation_confirmed'), false];
      return (
        <div key={log.id} className="journey-row"><div><b>{log.detail.value} <small>{log.detail.sensorId}</small></b><span className="mono" title={id}>{short(id, 6, 4)}</span></div><ol>{STAGES.map(([kind], index) => (
          <li key={kind} className={done[index] ? 'confirmed' : ''}><i /><span>{t(`kind.${kind}`)}</span></li>
        ))}</ol></div>
      );
    })}<p className="op-caption">{opText('Verde = confirmado por una respuesta o registro real. Gris = aún sin evidencia. El pago se confirma abajo con los eventos de Stellar.', 'Green = confirmed by a real response or record. Grey = no evidence yet. Payouts are confirmed below using Stellar events.')}</p></section>
  );
}

const detailText = (detail) => Object.entries(detail).filter(([key]) => !['sequence', 'message'].includes(key)).map(([key, value]) => `${key}=${value}`).join(' · ');

export function OperatorLogs() {
  const { t, opText } = useI18n();
  const { logs, stage, setStage, clearLogs } = useOperator();
  const visible = logs.filter((log) => stage === 'all' || log.kind === stage);
  return (
    <section className="card operator-log-panel"><div className="op-section-title panel"><h2>{opText('Actividad y logs', 'Activity & logs')} <span className="live-indicator" /></h2>
      <div className="toolbar"><select id="op-log-filter" aria-label={opText('Filtrar logs', 'Filter logs')} value={stage} onChange={(event) => setStage(event.target.value)}><option value="all">{opText('Todos los servicios', 'All services')}</option>{KINDS.map((kind) => <option key={kind} value={kind}>{t(`kind.${kind}`)}</option>)}</select><button className="btn btn-line btn-sm" data-op="clear-logs" onClick={clearLogs}>{opText('Limpiar vista', 'Clear view')}</button></div></div>
      <div className="activity-summary"><LifecyclePanel /><ObservationJourney /></div>
      <div className="op-terminal" role="log" aria-label={opText('Últimos mensajes de los servicios', 'Latest service messages')}>{visible.length ? visible.map((log) => (
        <div key={log.id} className={`log-row ${/failed|rejected|unreachable|error/.test(log.message) ? 'log-error' : ''}`}><span className="log-kind">{log.kind}</span><b>{log.name}</b><code>{log.message}</code>{log.detail ? <details className="log-detail"><summary>{opText('Detalle', 'Details')}</summary><small>{detailText(log.detail)}</small></details> : null}</div>
      )) : <div className="log-empty"><Icon name="pulse" /><h3>{opText('Esperando actividad', 'Waiting for activity')}</h3><p>{opText('Despliega un Reader y emite su primer pulso.', 'Deploy a Reader and send its first pulse.')}</p></div>}</div></section>
  );
}
