import { Icon } from '../Icon.jsx';

const ICONS = { reader: 'cpu', manager: 'hub', verifier: 'shield', storage: 'db', publisher: 'send', stellar: 'contract' };

/**
 * Tarjeta de un servicio: solo lo esencial (tipo, nombre, estado, Stream, actividad y puerto).
 * La selección y el arrastre llegan por Pointer Events del lienzo.
 */
export function CanvasNode({ node, position, selected, label, view }) {
  const className = `service-node service-node--${view.health} service-node--${node.kind}${selected ? ' service-node--selected' : ''}${node.kind === 'stellar' ? ' service-node--stellar' : ''}`;
  return (
    <button type="button" className={className} data-service-id={node.id} aria-pressed={selected}
      aria-label={`${node.name}, ${label(node.kind)}, ${view.healthText}`} title={node.name}
      style={{ transform: `translate(${position.x}px, ${position.y}px)` }}>
      <span className="service-node__kind"><Icon name={ICONS[node.kind] || 'hub'} className="icon tiny" />{label(node.kind)}</span>
      <strong className="service-node__name">{node.name}</strong>
      <span className="service-node__state"><i className="service-node__status" data-status={node.status} data-health={view.health} />{view.healthText}</span>
      <span className="service-node__meta">
        {view.stream ? <span className="service-node__stream"><Icon name="zap" className="icon tiny" />Stream</span> : null}
        {view.line ? <span className={`service-node__activity service-node__activity--${view.line.tone}`}>{view.line.text}</span> : null}
      </span>
      <span className="service-node__port">{view.port}</span>
    </button>
  );
}
