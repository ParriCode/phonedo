const observers = new WeakMap();

// Solo calcula la geometría; los datos, estados y eventos pertenecen a Leptos.
export function edgeGeometry(source, target, vertical = false, offset = 0) {
  const a = { x: source.left + source.width / 2, y: source.top + source.height / 2 };
  const b = { x: target.left + target.width / 2, y: target.top + target.height / 2 };
  const n = value => Math.round(value * 100) / 100;
  if (vertical) {
    const direction = b.y >= a.y ? 1 : -1;
    const y1 = a.y + direction * (source.height / 2 + 3);
    const y2 = b.y - direction * (target.height / 2 + 5);
    const low = Math.min(y1, y2), high = Math.max(y1, y2);
    const middle = high - low > 12
      ? Math.max(low + 6, Math.min(high - 6, (y1 + y2) / 2 + offset))
      : (y1 + y2) / 2;
    const labelX = Math.abs(b.x - a.x) < 10 ? a.x + 22 : (a.x + b.x) / 2;
    return {
      d: `M ${n(a.x)} ${n(y1)} L ${n(a.x)} ${n(middle)} L ${n(b.x)} ${n(middle)} L ${n(b.x)} ${n(y2)}`,
      x: n(labelX), y: n(middle - 8),
    };
  }
  const direction = b.x >= a.x ? 1 : -1;
  const x1 = a.x + direction * (source.width / 2 + 3);
  const x2 = b.x - direction * (target.width / 2 + 5);
  const middle = (x1 + x2) / 2;
  if (offset && Math.abs(a.y - b.y) < 10) {
    return {
      d: `M ${n(x1)} ${n(a.y)} L ${n(x1 + direction * 6)} ${n(a.y)} L ${n(x1 + direction * 6)} ${n(a.y + offset)} L ${n(x2 - direction * 6)} ${n(b.y + offset)} L ${n(x2 - direction * 6)} ${n(b.y)} L ${n(x2)} ${n(b.y)}`,
      x: n(middle), y: n((a.y + b.y) / 2 + offset - 8),
    };
  }
  return {
    d: `M ${n(x1)} ${n(a.y)} L ${n(middle + offset)} ${n(a.y)} L ${n(middle + offset)} ${n(b.y)} L ${n(x2)} ${n(b.y)}`,
    x: n(middle + offset), y: n((a.y + b.y) / 2 - 10),
  };
}

export function labelPosition(proposed, size, obstacles, bounds) {
  const shifts = [0, 16, -16, 30, -30, 44, -44, 60, -60, 78, -78];
  const candidates = shifts.flatMap(dx => shifts.map(dy => ({ dx, dy })))
    .sort((a, b) => a.dx * a.dx + a.dy * a.dy - b.dx * b.dx - b.dy * b.dy);
  const clampX = value => Math.max(size.width / 2 + 8, Math.min(bounds.width - size.width / 2 - 8, value));
  for (const { dx, dy } of candidates) {
    const x = clampX(proposed.x + dx);
    const y = Math.max(8 - size.topOffset, Math.min(bounds.height - 8 - size.topOffset - size.height, proposed.y + dy));
    const rect = { left: x - size.width / 2, top: y + size.topOffset, width: size.width, height: size.height };
    if (!obstacles.some(other => rect.left < other.left + other.width + 4 && rect.left + rect.width > other.left - 4
        && rect.top < other.top + other.height + 4 && rect.top + rect.height > other.top - 4)) return { x, y };
  }
  return { x: clampX(proposed.x), y: proposed.y };
}

export function observeGraph(element) {
  disconnectGraph(element);
  let frame;
  const draw = () => {
    frame = undefined;
    if (!element.isConnected) return;
    const bounds = element.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;
    const svg = element.querySelector('.pn-edges');
    if (!svg) return;
    svg.setAttribute('viewBox', `0 0 ${bounds.width} ${bounds.height}`);
    const nodes = new Map(Array.from(element.querySelectorAll('.pn-node'), node => [node.dataset.instanceId, node]));
    const localRect = node => {
      const rect = node.getBoundingClientRect();
      return { left: rect.left - bounds.left, top: rect.top - bounds.top, width: rect.width, height: rect.height };
    };
    const obstacles = Array.from(nodes.values(), localRect);
    const vertical = getComputedStyle(element).getPropertyValue('--graph-direction').trim() === 'vertical';
    for (const edge of svg.querySelectorAll('g[data-source]')) {
      const source = nodes.get(edge.dataset.source);
      const target = nodes.get(edge.dataset.target);
      if (!source || !target) continue;
      const geometry = edgeGeometry(localRect(source), localRect(target), vertical, Number(edge.dataset.offset) || 0);
      edge.querySelector('path').setAttribute('d', geometry.d);
      const label = edge.querySelector('text');
      label.setAttribute('x', geometry.x);
      label.setAttribute('y', geometry.y);
      const measured = label.getBBox();
      const size = { width: measured.width, height: measured.height, topOffset: measured.y - geometry.y };
      const position = labelPosition(geometry, size, obstacles, bounds);
      label.setAttribute('x', position.x);
      label.setAttribute('y', position.y);
      obstacles.push({ left: position.x - size.width / 2, top: position.y + size.topOffset, width: size.width, height: size.height });
    }
  };
  const schedule = () => { if (frame === undefined) frame = requestAnimationFrame(draw); };
  const resize = new ResizeObserver(schedule);
  const mutations = new MutationObserver(schedule);
  resize.observe(element);
  mutations.observe(element, { subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'data-instance-id', 'data-source', 'data-target', 'data-offset'] });
  observers.set(element, () => {
    resize.disconnect();
    mutations.disconnect();
    if (frame !== undefined) cancelAnimationFrame(frame);
  });
  schedule();
}

export function disconnectGraph(element) {
  observers.get(element)?.();
  observers.delete(element);
}
