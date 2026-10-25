import { CanvasState } from './state.js';
import { createNode, updateNode, positionNode } from './node.js';
import { renderEdges } from './edge.js';
import { renderSidebar } from './sidebar.js';
import { bindInteractions } from './interactions.js';

/** Controlador de vista; la topología y las acciones del backend llegan por un adaptador. */
export class ServiceCanvas {
  constructor(root, options) {
    this.root = root;
    this.options = options;
    this.state = new CanvasState({ storage: options.storage, key: options.storageKey });
    this.nodes = new Map();
    this.model = { nodes: [], connections: [] };
    this.abort = new AbortController();
    root.className = 'service-network';
    root.innerHTML = `<section class="canvas-panel card"><header class="canvas__toolbar"><div class="canvas__heading"><h2>Canvas View</h2><span class="canvas__node-count"></span></div>
      <div class="canvas__controls"><button type="button" class="btn btn-line btn-sm" data-canvas-action="layout">Auto layout</button><button type="button" class="btn btn-line btn-sm" data-canvas-action="fit">Fit view</button><button type="button" class="btn btn-gold btn-sm" data-canvas-action="add">+ Add service</button></div></header>
      <div class="canvas" tabindex="0" role="region" aria-label="Service network canvas"><div class="canvas__world"><svg class="canvas__edges" aria-hidden="true"></svg><div class="canvas__nodes"></div></div><div class="canvas__empty" hidden></div></div>
      <footer class="canvas__footer"><div class="canvas__legend"><span class="canvas__legend-item canvas__legend-item--http">HTTP</span><span class="canvas__legend-item canvas__legend-item--sse">SSE</span><span class="canvas__legend-item canvas__legend-item--stellar">Stellar</span></div>
      <span class="canvas__hint"></span><div class="canvas__zoom-controls"><button type="button" class="canvas__icon-button" data-canvas-action="pan" aria-pressed="false">✥</button><button type="button" class="canvas__icon-button" data-canvas-action="out">−</button><output class="canvas__zoom-label" aria-live="off">100%</output><button type="button" class="canvas__icon-button" data-canvas-action="in">+</button></div></footer></section>
      <aside class="service-network__sidebar" aria-label="Service details"></aside>`;
    this.viewport = root.querySelector('.canvas');
    this.world = root.querySelector('.canvas__world');
    this.nodeLayer = root.querySelector('.canvas__nodes');
    this.svg = root.querySelector('.canvas__edges');
    this.sidebar = root.querySelector('.service-network__sidebar');
    this.disposeInteractions = bindInteractions(this.viewport, this.state, {
      paint: () => this.paint(), select: (id) => this.select(id),
      interaction: (active) => { root.dataset.interacting = String(active); },
      settled: () => options.onSettled?.(),
    });
    root.addEventListener('click', (event) => {
      const control = event.target.closest('[data-canvas-action]');
      if (!control) return;
      event.stopPropagation();
      switch (control.dataset.canvasAction) {
        case 'add': options.onAdd(); break;
        case 'layout': this.state.layout(this.model.nodes, this.model.connections); this.fit(); break;
        case 'fit': this.fit(); break;
        case 'in': this.zoom(1.2); break;
        case 'out': this.zoom(1 / 1.2); break;
        case 'pan': this.state.panMode = !this.state.panMode; this.paint(); break;
      }
    }, { signal: this.abort.signal });
    this.resize = new ResizeObserver(() => {
      if (!this.state.hasViewport && this.viewport.clientWidth) this.fit();
    });
    this.resize.observe(this.viewport);
  }

  update(model, selectedId) {
    this.model = model;
    this.state.sync(model.nodes, model.connections);
    this.state.selectedId = model.nodes.some((node) => node.id === selectedId) ? selectedId : null;
    const present = new Set(model.nodes.map((node) => node.id));
    for (const [id, element] of this.nodes) if (!present.has(id)) { element.remove(); this.nodes.delete(id); }
    for (const node of model.nodes) {
      if (!this.nodes.has(node.id)) { const element = createNode(); this.nodes.set(node.id, element); this.nodeLayer.append(element); }
    }
    const text = this.options.text;
    this.root.querySelector('.canvas__node-count').textContent = `${model.nodes.length} ${text('servicios', 'services')}`;
    this.root.querySelector('.canvas__hint').textContent = text('Arrastra · Rueda para zoom · Espacio para mover', 'Drag · Scroll to zoom · Space to pan');
    this.viewport.setAttribute('aria-label', text('Lienzo libre de servicios', 'Free service canvas'));
    const labels = { pan: text('Mover lienzo', 'Pan canvas'), in: text('Acercar', 'Zoom in'), out: text('Alejar', 'Zoom out') };
    for (const [action, label] of Object.entries(labels)) this.root.querySelector(`[data-canvas-action="${action}"]`).setAttribute('aria-label', label);
    const empty = this.root.querySelector('.canvas__empty');
    empty.hidden = model.nodes.length > 0;
    empty.textContent = text('Añade el primer servicio con + Add service', 'Add your first service with + Add service');
    if (!this.state.hasViewport && this.viewport.clientWidth) this.fit();
    this.paint();
    this.updateSidebar();
  }

  paint() {
    const { x, y, zoom } = this.state.viewport;
    this.world.style.transform = `translate(${x}px, ${y}px) scale(${zoom})`;
    for (const node of this.model.nodes) {
      const element = this.nodes.get(node.id);
      updateNode(element, node, { ...this.options, selected: node.id === this.state.selectedId });
      positionNode(element, this.state.positions[node.id]);
    }
    renderEdges(this.svg, this.model.connections, this.state.positions, {
      escape: this.options.escape, configuredLabel: this.options.text('Relación configurada', 'Configured relationship'),
    });
    this.root.querySelector('.canvas__zoom-label').textContent = `${Math.round(zoom * 100)}%`;
    this.viewport.classList.toggle('canvas--dragging', this.state.interacting);
    this.viewport.classList.toggle('canvas--pan', this.state.panMode);
    this.root.querySelector('[data-canvas-action="pan"]').setAttribute('aria-pressed', String(this.state.panMode));
  }

  select(id) {
    this.state.selectedId = id;
    this.options.onSelect(id);
    this.paint();
    this.updateSidebar(true);
  }

  updateSidebar(force = false) {
    renderSidebar(this.sidebar, this.model.nodes.find((node) => node.id === this.state.selectedId), {
      details: this.options.details, empty: this.options.empty, force,
    });
  }

  fit() { this.state.fit(this.viewport.clientWidth, this.viewport.clientHeight); this.paint(); this.state.save(); }
  zoom(factor) {
    this.state.zoomAt({ x: this.viewport.clientWidth / 2, y: this.viewport.clientHeight / 2 }, this.state.viewport.zoom * factor);
    this.paint(); this.state.save();
  }
  destroy() { this.disposeInteractions(); this.abort.abort(); this.resize.disconnect(); this.state.save(); }
}
