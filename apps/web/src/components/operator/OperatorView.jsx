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
    else if (health === 'degraded' && problem) line = { tone: problem.level === 'warning' ? 'warning' : 'error', text: problem.log.message };
    else if (health !== 'error' && activity.receiving) line = { tone: 'live', text: opText('Recibiendo datos', 'Receiving data') };
    else if (health !== 'error' && activity.perMinute) line = { tone: 'info', text: opText(`${activity.perMinute} eventos/min`, `${activity.perMinute} events/min`) };
    views[node.id] = {
      health, healthText: healthLabel(health, opText), stream: Boolean(view.stream[node.id]), line,
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
  const { epoch } = useOperator();
  const view = useSystemView();
  const label = (kind) => (kind === 'stellar' ? 'Stellar' : t(`kind.${kind}`));
  const names = Object.fromEntries(view.model.nodes.map((node) => [node.id, node.name]));

  const node = view.model.nodes.find((item) => item.id === selected);
  const edge = view.model.connections.find((item) => item.id === selectedEdge);
  let sidebar = <SystemSummary view={view} label={label} />;
  if (node?.kind === 'stellar') sidebar = <StellarInspector node={node} view={view} />;
  else if (node) sidebar = <NodeInspector key={`${node.id}:${epoch}`} node={node} view={view} label={label} />;
  else if (edge) sidebar = <EdgeInspector edge={edge} view={view} label={label} />;

  return (
    <section className="page-body operator-body"><div className="wrap-wide">
      <ServiceCanvas
        model={view.model} views={nodeViews(view, opText)} edgeStates={view.edges}
        selectedId={selected} selectedEdgeId={selectedEdge} onSelect={select} onSelectEdge={selectEdge}
        onAdd={() => openDialog('reader')} summary={<HealthSummary view={view} />}
        storageKey="phonendo.canvas.local.v1" text={opText} label={label}
        edgeLabel={(item, state) => `${names[item.sourceId]} → ${names[item.targetId]} · ${transportLabel(item.transport)} · ${edgeLabel(state, opText)}`}
        sidebar={sidebar}
      />
      <OperatorLogs view={view} />
    </div></section>
  );
}
