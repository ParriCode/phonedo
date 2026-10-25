import { hostLabel } from '../../../service_network/models.js';
import { Icon } from '../Icon.jsx';

const ICONS = { reader: 'cpu', manager: 'hub', verifier: 'shield', storage: 'db', publisher: 'send', stellar: 'contract' };

/** Tarjeta de un servicio. La selección y el arrastre llegan por Pointer Events del lienzo. */
export function CanvasNode({ node, position, selected, label, statusLabel, organizationLabel }) {
  const className = `service-node${selected ? ' service-node--selected' : ''}${node.kind === 'stellar' ? ' service-node--stellar' : ''}`;
  return (
    <button type="button" className={className} data-service-id={node.id} aria-pressed={selected}
      aria-label={`${node.name}, ${label(node.kind)}, ${statusLabel(node.status)}`} title={node.name}
      style={{ transform: `translate(${position.x}px, ${position.y}px)` }}>
      <span className="service-node__header"><span className="service-node__icon"><Icon name={ICONS[node.kind] || 'hub'} /></span><span className="service-node__identity"><strong>{node.name}</strong><span className="service-node__type">{label(node.kind)}</span></span><i className="service-node__status" data-status={node.status} title={statusLabel(node.status)} /></span>
      <span className="service-node__address" title={node.address}>{hostLabel(node.address)}</span>
      <span className="service-node__footer"><span className="service-node__tag">{organizationLabel(node.organization)}</span><span className="service-node__status-label">{statusLabel(node.status)}</span></span>
    </button>
  );
}
