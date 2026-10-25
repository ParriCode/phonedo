import { CONFIG } from '../../config.js';
import { contractUrl, short } from '../../lib/format.js';
import { sinceLabel } from '../../lib/health.js';
import { useI18n } from '../../providers/I18nProvider.jsx';
import { useNetwork } from '../../providers/NetworkProvider.jsx';
import { useOperator } from '../../providers/OperatorProvider.jsx';
import { Icon } from '../Icon.jsx';
import { AdvancedSettings, ReaderDevices } from './ServiceDetails.jsx';
import { edgeLabel, HealthBadge, StreamBadge, transportLabel } from './status.jsx';

const ICONS = { reader: 'cpu', manager: 'hub', verifier: 'shield', storage: 'db', publisher: 'send', stellar: 'contract' };

function Problem({ node, problem, health }) {
  const { opText } = useI18n();
  const { focusLogs } = useOperator();
  if (!problem) return null;
  const tone = health === 'degraded' ? 'warning' : 'error';
  return <div className={`callout callout--${tone}`}><Icon name="alert" /><div><b>{tone === 'warning' ? opText('Requiere revisión', 'Needs review') : opText('Servicio no disponible', 'Service unavailable')}</b><code>{problem.log.message}</code><button type="button" className="link-button" onClick={() => focusLogs(node.id)}>{opText('Ver logs relacionados', 'View related logs')}</button></div></div>;
}

function Connections({ node, view }) {
  const { opText } = useI18n();
  const { select } = useNetwork();
  const edges = view.model.connections.filter((edge) => edge.sourceId === node.id || edge.targetId === node.id);
  if (!edges.length) return <p className="inspector__hint">{opText('Sin conexiones configuradas.', 'No configured connections.')}</p>;
  return <section className="inspector__section"><h3>{opText('Conexiones', 'Connections')}</h3><ul className="link-list">{edges.map((edge) => {
    const outgoing = edge.sourceId === node.id;
    const other = view.model.nodes.find((item) => item.id === (outgoing ? edge.targetId : edge.sourceId));
    return <li key={edge.id}><button type="button" className="link-item" onClick={() => select(other.id)}><span className="link-item__dir">{outgoing ? '→' : '←'}</span><span className="link-item__name">{other.name}<small>{transportLabel(edge.transport)}</small></span><i className={`link-item__state edge-dot--${view.edges[edge.id]}`} /></button></li>;
  })}</ul></section>;
}

export function NodeInspector({ node, view, label }) {
  const { opText } = useI18n();
  const { nodeById } = useNetwork();
  const { readers, containers, checkNode, dockerAction, checkedAt } = useOperator();
  const service = nodeById(node.id) || node;
  const runtime = readers[node.id];
  const snapshot = containers[node.id];
  return <article className="inspector inspector--node">
    <header className="inspector__head"><span className="inspector__kind"><Icon name={ICONS[node.kind] || 'hub'} />{label(node.kind)}</span><h2>{node.name}</h2><div className="inspector__badges"><HealthBadge health={view.health[node.id]} text={opText} large />{view.stream[node.id] ? <StreamBadge /> : null}</div></header>
    <Problem node={node} problem={view.problems[node.id]} health={view.health[node.id]} />
    <dl className="facts"><dt>{opText('Dirección', 'Address')}</dt><dd className="mono">{node.address}</dd><dt>{opText('Runtime', 'Runtime')}</dt><dd>{node.runtime}</dd><dt>{opText('Última consulta', 'Last check')}</dt><dd>{sinceLabel(checkedAt[node.id], view.now, opText)}</dd></dl>
    <div className="panel-actions"><button type="button" className="btn btn-line btn-sm" onClick={() => checkNode(service)}><Icon name="refresh" />{opText('Consultar ahora', 'Check now')}</button>{snapshot ? ['start', 'stop', 'restart'].map((action) => <button type="button" className="btn btn-line btn-sm" key={action} onClick={() => dockerAction(service, action)}>{({ start: opText('Arrancar', 'Start'), stop: opText('Parar', 'Stop'), restart: opText('Reiniciar', 'Restart') })[action]}</button>) : null}</div>
    <Connections node={node} view={view} />
    {runtime ? <ReaderDevices service={service} runtime={runtime} /> : null}
    <AdvancedSettings service={service} />
  </article>;
}

export function EdgeInspector({ edge, view, label }) {
  const { opText } = useI18n();
  const { select } = useNetwork();
  const source = view.model.nodes.find((node) => node.id === edge.sourceId);
  const target = view.model.nodes.find((node) => node.id === edge.targetId);
  const state = view.edges[edge.id];
  return <article className="inspector inspector--edge"><header className="inspector__head"><span className="inspector__kind">{opText('Conexión', 'Connection')}</span><h2>{source.name} → {target.name}</h2><div className="inspector__badges"><span className={`edge-badge edge-badge--${state}`}><i />{edgeLabel(state, opText)}</span>{edge.transport === 'sse' ? <StreamBadge /> : <span className={`transport transport--${edge.transport}`}>{transportLabel(edge.transport)}</span>}</div></header>
    <section className="inspector__section"><h3>{opText('Extremos', 'Endpoints')}</h3><ul className="link-list"><li><button className="link-item" type="button" onClick={() => select(source.id)}><span className="link-item__dir">←</span><span className="link-item__name">{source.name}<small>{label(source.kind)}</small></span></button></li><li><button className="link-item" type="button" onClick={() => select(target.id)}><span className="link-item__dir">→</span><span className="link-item__name">{target.name}<small>{label(target.kind)}</small></span></button></li></ul></section>
  </article>;
}

export function SystemSummary({ view, label }) {
  const { opText } = useI18n();
  const { select } = useNetwork();
  const attention = view.model.nodes.filter((node) => ['error', 'degraded'].includes(view.health[node.id]));
  return <article className="inspector inspector--summary"><header className="inspector__head"><span className="inspector__kind">Phonendo</span><h2>{attention.length ? opText('Necesita atención', 'Needs attention') : opText('Sistema operativo', 'System operational')}</h2><p className="inspector__hint">{opText('Selecciona un servicio o una conexión para ver sus detalles.', 'Select a service or connection to inspect it.')}</p></header>
    <ul className="summary-counts">{['healthy', 'degraded', 'error', 'unknown'].filter((health) => view.counts[health]).map((health) => <li key={health} className={`summary-counts__item health--${health}`}><b>{view.counts[health]}</b><span><i />{health}</span></li>)}</ul>
    {attention.length ? <section className="inspector__section"><h3>{opText('Atención', 'Attention')}</h3><ul className="attention-list">{attention.map((node) => <li key={node.id}><button type="button" className="attention-item" onClick={() => select(node.id)}><span><b>{node.name}</b><small>{label(node.kind)}</small></span><HealthBadge health={view.health[node.id]} text={opText} /><code>{view.problems[node.id]?.log.message}</code></button></li>)}</ul></section> : null}
  </article>;
}

export function StellarInspector({ node, view }) {
  const { opText } = useI18n();
  return <article className="inspector inspector--stellar"><header className="inspector__head"><span className="inspector__kind"><Icon name="contract" />Stellar</span><h2>{node.name}</h2><div className="inspector__badges"><HealthBadge health={view.health[node.id]} text={opText} large /></div></header><p className="inspector__lead">{opText('Contratos y pagos observados en testnet.', 'Contracts and payouts observed on testnet.')}</p><dl className="facts"><dt>{opText('Pagos', 'Payouts')}</dt><dd>{view.payments.events.length}</dd><dt>{opText('Red', 'Network')}</dt><dd>testnet</dd></dl><ul className="link-list">{CONFIG.contracts.map((contract) => <li key={contract.id}><a className="link-item" href={contractUrl(contract.id)} target="_blank" rel="noopener"><span className="link-item__name">{contract.asset}<small className="mono">{short(contract.id, 9, 6)}</small></span><Icon name="external" /></a></li>)}</ul></article>;
}
