import { portLabel } from '../../lib/health.js';
import { useI18n } from '../../providers/I18nProvider.jsx';
import { useNetwork } from '../../providers/NetworkProvider.jsx';
import { useOperator } from '../../providers/OperatorProvider.jsx';
import { ServiceCanvas } from '../canvas/ServiceCanvas.jsx';
import { useDeployDialog } from './DeployDialog.jsx';
import { EdgeInspector, NodeInspector, StellarInspector, SystemSummary } from './Inspector.jsx';
import { OperatorLogs } from './OperatorLogs.jsx';
import { edgeLabel, healthLabel, transportLabel } from './status.jsx';
import { useSystemView } from './useSystemView.js';

/** Lo que muestra cada tarjeta del lienzo: estado, Stream y una sola línea de actividad. */
function nodeViews(view, opText) {
  const views = {};
  for (const node of view.model.nodes) {
    const health = view.health[node.id];
    const activity = view.activity[node.id];
    const problem = view.problems[node.id];
    let line = null;
    if (node.kind === 'stellar') line = { tone: 'info', text: opText(`${activity.payments} pagos`, `${activity.payments} payouts`) };
    else if (health === 'degraded' && problem) line = { tone: problem.level === 'warning' ? 'warning' : 'error', text: problem.log.detail?.error || problem.log.message };
    else if (health !== 'error' && activity.receiving) line = { tone: 'live', text: opText('Recibiendo datos', 'Receiving data') };
    else if (health !== 'error' && activity.perMinute) line = { tone: 'info', text: opText(`${activity.perMinute} eventos/min`, `${activity.perMinute} events/min`) };
    views[node.id] = {
      health, healthText: node.imageOnly ? opText('Imagen disponible', 'Image available') : healthLabel(health, opText), stream: Boolean(view.stream[node.id]), line,
      port: node.kind === 'stellar' ? 'testnet' : portLabel(node.address),
    };
  }
  return views;
}

function HealthSummary({ view }) {
  const { opText } = useI18n();
  const order = ['error', 'degraded', 'stale', 'healthy', 'unknown'];
  return (
    <span className="canvas__summary">
      <span className="canvas__node-count">{`${view.model.nodes.length} ${opText('servicios', 'services')}`}</span>
      {order.filter((health) => view.counts[health]).map((health) => (
        <span key={health} className={`summary-pill health--${health}`} title={healthLabel(health, opText)}><i />{view.counts[health]} {healthLabel(health, opText).toLowerCase()}</span>
      ))}
    </span>
  );
}

/** Consola del operador: mapa vivo del sistema, detalle contextual y actividad. */
export function OperatorView() {
  const { t, opText } = useI18n();
  const { selected, selectedEdge, select, selectEdge } = useNetwork();
  const { openDialog } = useDeployDialog();
  // Tras cada acción confirmada el inspector se vuelve a montar con los valores reales.
  const { epoch, containers, dockerAction, imageAction, connectionAction, inventoryError } = useOperator();
  const view = useSystemView();
  const label = (kind) => (kind === 'stellar' ? 'Stellar' : t(`kind.${kind}`));
  const names = Object.fromEntries(view.model.nodes.map((node) => [node.id, node.name]));
  const connect = (sourceId, targetId, transport) => {
    const target = view.model.nodes.find((item) => item.id === targetId);
    connectionAction(sourceId, targetId, transport || (target?.kind === 'publisher' ? 'sse' : 'http'));
  };

  const node = view.model.nodes.find((item) => item.id === selected);
  const edge = view.model.connections.find((item) => item.id === selectedEdge);
  let sidebar = <SystemSummary view={view} label={label} />;
  if (node?.imageOnly) sidebar = <article className="inspector inspector--image"><header className="inspector__head"><span className="inspector__kind">Docker</span><h2>{node.name}</h2><p className="inspector__hint">{opText('Imagen local sin contenedor. Usa los botones de su tarjeta para desplegarla o borrarla.', 'Local image without a container. Use its card to deploy or remove it.')}</p></header><dl className="facts"><dt>{opText('Imagen', 'Image')}</dt><dd className="mono">{node.image}</dd><dt>{opText('Servicio', 'Service')}</dt><dd>{label(node.kind)}</dd></dl></article>;
  else if (node?.kind === 'stellar') sidebar = <StellarInspector node={node} view={view} />;
  else if (node) sidebar = <NodeInspector key={`${node.id}:${epoch}`} node={node} view={view} label={label} />;
  else if (edge) sidebar = <EdgeInspector key={edge.id} edge={edge} view={view} label={label} />;

  return (
    <section className="page-body operator-body"><div className="wrap-wide">
      <ServiceCanvas
        model={view.model} views={nodeViews(view, opText)} edgeStates={view.edges}
        selectedId={selected} selectedEdgeId={selectedEdge} onSelect={select} onSelectEdge={selectEdge}
        onAdd={() => openDialog('reader')} onDeploy={openDialog} onDockerAction={dockerAction} onImageAction={imageAction} onConnect={connect} containers={containers} inventoryError={inventoryError} summary={<HealthSummary view={view} />}
        storageKey="phonendo.canvas.local.v1" text={opText} label={label}
        edgeLabel={(item, state) => `${names[item.sourceId]} → ${names[item.targetId]} · ${transportLabel(item.transport)} · ${edgeLabel(state, opText)}`}
        sidebar={sidebar}
      />
      <OperatorLogs view={view} />
    </div></section>
  );
}
