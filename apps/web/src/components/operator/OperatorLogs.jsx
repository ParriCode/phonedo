// Actividad del despliegue: recorrido de las últimas observaciones y logs filtrables.
// Cada registro enlaza con el nodo que lo generó.
import { LOG_LEVELS, sinceLabel } from '../../lib/health.js';
import { short } from '../../lib/format.js';
import { useI18n } from '../../providers/I18nProvider.jsx';
import { useNetwork } from '../../providers/NetworkProvider.jsx';
import { useOperator } from '../../providers/OperatorProvider.jsx';
import { Icon } from '../Icon.jsx';
import { LevelBadge, levelLabel } from './status.jsx';

export const STAGES = ['reader', 'manager', 'verifier', 'storage', 'publisher'];
const MAX_ROWS = 200;

function ObservationJourney() {
  const { t, opText } = useI18n();
  const { logs } = useOperator();
  const created = logs.filter((log) => log.message === 'observation_created').slice(0, 3);
  if (!created.length) return null;
  return (
    <section className="journeys"><h3>{opText('Recorrido de las últimas observaciones', 'Latest observations journey')}</h3>{created.map((log) => {
      const id = log.detail.observationId;
      const related = logs.filter((item) => item.detail?.observationId === id);
      const done = [true, related.some((item) => item.message === 'manager_http_accepted'),
        related.some((item) => item.message === 'manager_reports_verified' || item.message === 'storage_observation_confirmed'),
        related.some((item) => item.message === 'storage_observation_confirmed'), false];
      return (
        <div key={log.id} className="journey-row"><div><b>{log.detail.value} <small>{log.detail.sensorId}</small></b><span className="mono" title={id}>{short(id, 6, 4)}</span></div><ol>{STAGES.map((kind, index) => (
          <li key={kind} className={done[index] ? 'confirmed' : ''}><i /><span>{t(`kind.${kind}`)}</span></li>
        ))}</ol></div>
      );
    })}</section>
  );
}

const detailEntries = (detail) => Object.entries(detail).filter(([key]) => !['sequence', 'message', 'level', 'ts'].includes(key));
// Peticiones HTTP de rutina: se ocultan salvo que se pidan, para que destaque lo importante.
const isRoutine = (log) => log.message === 'request';

/** Agrupa mensajes iguales seguidos del mismo servicio en una sola fila con su número. */
export function groupRepeats(logs) {
  const rows = [];
  for (const log of logs) {
    const last = rows.at(-1);
    if (last && last.node === log.node && last.message === log.message && last.level === log.level && !log.detail && !last.detail) last.count += 1;
    else rows.push({ ...log, count: 1 });
  }
  return rows;
}

export function OperatorLogs({ view, onShowMap = () => {} }) {
  const { t, opText } = useI18n();
  const { selected, select } = useNetwork();
  const { logs, logFilter, setLogFilter, clearLogs } = useOperator();
  const services = view.model.nodes.filter((node) => node.kind !== 'stellar');
  const byService = logs.filter((log) => logFilter.node === 'all' || log.node === logFilter.node);
  const routine = byService.filter(isRoutine).length;
  const scoped = logFilter.routine ? byService : byService.filter((log) => !isRoutine(log));
  const counts = Object.fromEntries(LOG_LEVELS.map((level) => [level, scoped.filter((log) => log.level === level).length]));
  const query = logFilter.query.trim().toLowerCase();
  const visible = groupRepeats(scoped
    .filter((log) => logFilter.level === 'all' || log.level === logFilter.level)
    .filter((log) => !query || `${log.name} ${log.message} ${log.detail ? JSON.stringify(log.detail) : ''}`.toLowerCase().includes(query)));
  const filteredNode = services.find((node) => node.id === logFilter.node);

  return (
    <section className="card logs" id="activity">
      <header className="logs__head">
        <div className="logs__title"><h2>{opText('Actividad', 'Activity')}</h2><span className="live-indicator" title={opText('En directo', 'Live')} /></div>
        <div className="logs__tools">
          <label className="logs__search"><span className="sr-only">{opText('Buscar en los logs', 'Search logs')}</span>
            <input type="search" placeholder={opText('Buscar…', 'Search…')} value={logFilter.query} onChange={(event) => setLogFilter({ query: event.target.value })} /></label>
          <select id="op-log-filter" aria-label={opText('Filtrar por servicio', 'Filter by service')} value={logFilter.node} onChange={(event) => setLogFilter({ node: event.target.value })}>
            <option value="all">{opText('Todos los servicios', 'All services')}</option>
            {services.map((node) => <option key={node.id} value={node.id}>{node.name} · {t(`kind.${node.kind}`)}</option>)}
          </select>
          <button type="button" className="btn btn-line btn-sm" data-op="clear-logs" onClick={clearLogs}>{opText('Limpiar vista', 'Clear view')}</button>
        </div>
      </header>
      <div className="logs__levels" role="group" aria-label={opText('Filtrar por nivel', 'Filter by level')}>
        <button type="button" className="level-filter" aria-pressed={logFilter.level === 'all'} onClick={() => setLogFilter({ level: 'all' })}>{opText('Todos', 'All')} <b>{scoped.length}</b></button>
        {LOG_LEVELS.map((level) => (
          <button key={level} type="button" className={`level-filter level--${level}`} data-level={level} aria-pressed={logFilter.level === level} disabled={!counts[level]}
            onClick={() => setLogFilter({ level: logFilter.level === level ? 'all' : level })}><i />{levelLabel(level, opText)} <b>{counts[level]}</b></button>
        ))}
        {filteredNode ? <button type="button" className="filter-chip" onClick={() => setLogFilter({ node: 'all' })}>{filteredNode.name} <Icon name="x" className="icon tiny" /></button> : null}
        {routine ? <button type="button" className="routine-toggle" aria-pressed={Boolean(logFilter.routine)} onClick={() => setLogFilter({ routine: !logFilter.routine })}>
          {logFilter.routine ? opText('Ocultar peticiones HTTP', 'Hide HTTP requests') : opText(`Mostrar ${routine} peticiones HTTP`, `Show ${routine} HTTP requests`)}</button> : null}
      </div>
      <ObservationJourney />
      {visible.length ? (
        <ol className="op-terminal logs__list" role="log" aria-label={opText('Últimos mensajes de los servicios', 'Latest service messages')}>
          {visible.slice(0, MAX_ROWS).map((log) => (
            <li key={log.id} className={`log-row log-row--${log.level}${log.node === selected ? ' is-related' : ''}`}>
              <LevelBadge level={log.level} />
              <button type="button" className="log-row__service" onClick={() => { select(log.node); onShowMap(); }} title={opText('Ver en el mapa', 'Show on the map')}>{log.name}<small>{t(`kind.${log.kind}`)}</small></button>
              <code className="log-row__message">{log.message}{log.count > 1 ? <span className="log-row__count">×{log.count}</span> : null}</code>
              <small className="log-row__time">{log.historical ? opText('anterior', 'earlier') : sinceLabel(log.at, view.now, opText)}</small>
              {log.detail && detailEntries(log.detail).length ? (
                <details className="log-detail"><summary>{opText('Detalle', 'Details')}</summary>
                  <dl>{detailEntries(log.detail).map(([key, value]) => [<dt key={`${key}-k`}>{key}</dt>, <dd key={`${key}-v`}>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd>])}</dl>
                </details>
              ) : null}
            </li>
          ))}
        </ol>
      ) : (
        <div className="op-terminal log-empty"><Icon name="pulse" /><h3>{logs.length ? opText('Nada coincide con el filtro', 'Nothing matches the filter') : opText('Esperando actividad', 'Waiting for activity')}</h3>
          <p>{logs.length ? opText('Cambia el nivel, el servicio o la búsqueda.', 'Change the level, service or search.') : opText('Despliega un Reader y emite su primer pulso.', 'Deploy a Reader and send its first pulse.')}</p></div>
      )}
    </section>
  );
}
