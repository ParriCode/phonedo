import { KIND_ORDER, NODE_SIZE } from './models.js';

/** Disposición inicial por relaciones; las coordenadas son libres tras colocar los nodos. */
export function autoLayout(nodes, connections) {
  const ranks = new Map(nodes.map((node) => [node.id, KIND_ORDER[node.kind] ?? 0]));
  const incoming = new Map(nodes.map((node) => [node.id, 0]));
  const outgoing = new Map(nodes.map((node) => [node.id, []]));
  for (const edge of connections) {
    if (!incoming.has(edge.targetId) || !outgoing.has(edge.sourceId) || edge.sourceId === edge.targetId) continue;
    incoming.set(edge.targetId, incoming.get(edge.targetId) + 1);
    outgoing.get(edge.sourceId).push(edge.targetId);
  }
  const queue = [...incoming].filter(([, count]) => count === 0).map(([id]) => id);
  while (queue.length) {
    const source = queue.shift();
    for (const target of outgoing.get(source)) {
      ranks.set(target, Math.max(ranks.get(target), ranks.get(source) + 1));
      incoming.set(target, incoming.get(target) - 1);
      if (incoming.get(target) === 0) queue.push(target);
    }
  }
  const groups = new Map();
  for (const node of nodes) {
    const rank = ranks.get(node.id);
    if (!groups.has(rank)) groups.set(rank, []);
    groups.get(rank).push(node);
  }
  const maxRows = Math.max(1, ...[...groups.values()].map((group) => group.length));
  const positions = Object.create(null);
  [...groups.keys()].sort((a, b) => a - b).forEach((rank, column) => {
    const group = groups.get(rank).sort((a, b) => `${a.organization}:${a.name}:${a.id}`.localeCompare(`${b.organization}:${b.name}:${b.id}`));
    group.forEach((node, row) => {
      positions[node.id] = { x: 64 + column * (NODE_SIZE.width + 92), y: 64 + (row + (maxRows - group.length) / 2) * (NODE_SIZE.height + 40) };
    });
  });
  return positions;
}

export function freePosition(positions) {
  const values = Object.values(positions);
  return { x: values.length ? Math.max(...values.map((point) => point.x)) + NODE_SIZE.width + 56 : 64, y: 64 };
}

export function fitViewport(positions, width, height, padding = 48) {
  const values = Object.values(positions);
  if (!values.length || width <= 0 || height <= 0) return { x: 0, y: 0, zoom: 1 };
  const left = Math.min(...values.map((point) => point.x));
  const top = Math.min(...values.map((point) => point.y));
  const right = Math.max(...values.map((point) => point.x + NODE_SIZE.width));
  const bottom = Math.max(...values.map((point) => point.y + NODE_SIZE.height));
  const zoom = Math.max(.15, Math.min(1.2, (width - padding * 2) / (right - left), (height - padding * 2) / (bottom - top)));
  return { zoom, x: (width - (right - left) * zoom) / 2 - left * zoom, y: (height - (bottom - top) * zoom) / 2 - top * zoom };
}
