import { hostLabel } from './models.js';

const ICONS = { reader:'cpu', manager:'hub', verifier:'shield', storage:'db', publisher:'send', stellar:'contract' };

export function createNode() {
  const element = document.createElement('button');
  element.type = 'button';
  element.className = 'service-node';
  return element;
}

export function updateNode(element, node, { selected, label, statusLabel, organizationLabel, icon, escape }) {
  element.dataset.serviceId = node.id;
  element.className = `service-node${selected ? ' service-node--selected' : ''}${node.kind === 'stellar' ? ' service-node--stellar' : ''}`;
  element.setAttribute('aria-pressed', String(selected));
  element.setAttribute('aria-label', `${node.name}, ${label(node.kind)}, ${statusLabel(node.status)}`);
  element.title = node.name;
  const content = `<span class="service-node__header"><span class="service-node__icon">${icon(ICONS[node.kind] || 'hub')}</span><span class="service-node__identity"><strong>${escape(node.name)}</strong><span class="service-node__type">${escape(label(node.kind))}</span></span><i class="service-node__status" data-status="${escape(node.status)}" title="${escape(statusLabel(node.status))}"></i></span>
    <span class="service-node__address" title="${escape(node.address)}">${escape(hostLabel(node.address))}</span>
    <span class="service-node__footer"><span class="service-node__tag">${escape(organizationLabel(node.organization))}</span><span class="service-node__status-label">${escape(statusLabel(node.status))}</span></span>`;
  if (element.innerHTML !== content) element.innerHTML = content;
}

export function positionNode(element, point) {
  element.style.transform = `translate(${point.x}px, ${point.y}px)`;
}
