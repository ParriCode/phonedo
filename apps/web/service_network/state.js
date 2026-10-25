import { autoLayout, freePosition, fitViewport } from './layout.js';

export const ZOOM_LIMITS = Object.freeze({ min: .15, max: 2.5 });
const finitePoint = (point) => point && Number.isFinite(point.x) && Number.isFinite(point.y) && Math.abs(point.x) < 1e7 && Math.abs(point.y) < 1e7;

export class CanvasState {
  constructor({ storage = null, key = 'phonendo.canvas.local.v1' } = {}) {
    this.storage = storage;
    this.key = key;
    this.positions = Object.create(null);
    this.viewport = { x: 0, y: 0, zoom: 1 };
    this.selectedId = null;
    this.panMode = false;
    this.interacting = false;
    this.hasViewport = false;
    try {
      const saved = JSON.parse(storage?.getItem(key) || 'null');
      for (const [id, point] of Object.entries(saved?.positions || {})) {
        if (finitePoint(point)) Object.defineProperty(this.positions, id, { value: { ...point }, writable: true, enumerable: true, configurable: true });
      }
      if (finitePoint(saved?.viewport) && Number.isFinite(saved.viewport.zoom)) {
        this.viewport = { ...saved.viewport, zoom: this.clampZoom(saved.viewport.zoom) };
        this.hasViewport = true;
      }
    } catch { /* Un almacenamiento bloqueado o antiguo no impide usar el lienzo. */ }
  }

  clampZoom(value) { return Math.max(ZOOM_LIMITS.min, Math.min(ZOOM_LIMITS.max, value)); }

  sync(nodes, connections) {
    const known = new Set(nodes.map((node) => node.id));
    for (const id of Object.keys(this.positions)) if (!known.has(id)) delete this.positions[id];
    const initial = !Object.keys(this.positions).length;
    if (initial) this.positions = autoLayout(nodes, connections);
    else for (const node of nodes) {
      if (!Object.hasOwn(this.positions, node.id)) Object.defineProperty(this.positions, node.id, {
        value: freePosition(this.positions), writable: true, enumerable: true, configurable: true,
      });
    }
    if (!known.has(this.selectedId)) this.selectedId = null;
  }

  move(id, position) {
    if (Object.hasOwn(this.positions, id) && finitePoint(position)) this.positions[id] = { ...position };
  }

  zoomAt(point, zoom) {
    const previous = this.viewport;
    zoom = this.clampZoom(zoom);
    this.viewport = { zoom, x: point.x - (point.x - previous.x) / previous.zoom * zoom,
      y: point.y - (point.y - previous.y) / previous.zoom * zoom };
    this.hasViewport = true;
  }

  fit(width, height) { this.viewport = fitViewport(this.positions, width, height); this.hasViewport = true; }
  layout(nodes, edges) { this.positions = autoLayout(nodes, edges); }
  save() {
    try { this.storage?.setItem(this.key, JSON.stringify({ positions: this.positions, viewport: this.viewport })); }
    catch { /* La sesión sigue funcionando sin persistencia. */ }
  }
}
