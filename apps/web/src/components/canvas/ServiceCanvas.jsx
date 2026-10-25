import { useCallback, useEffect, useLayoutEffect, useReducer, useRef, useState } from 'react';
import { CanvasState } from '../../../service_network/state.js';
import { browserStorage } from '../../lib/storage.js';
import { CanvasEdges } from './CanvasEdges.jsx';
import { CanvasNode } from './CanvasNode.jsx';
import { useCanvasInteractions } from './useCanvasInteractions.js';

/**
 * Lienzo de servicios: la forma principal de entender el sistema. Posiciones y viewport
 * viven en CanvasState (fuera de React, persistidos por despliegue); el estado de cada
 * nodo y conexión llega ya calculado en `views` y `edgeStates`.
 */
export function ServiceCanvas({
  model, views, edgeStates, selectedId, selectedEdgeId, onSelect, onSelectEdge, onAdd,
  summary, sidebar, text, label, edgeLabel, storageKey,
}) {
  const stateRef = useRef(null);
  if (!stateRef.current) stateRef.current = new CanvasState({ storage: browserStorage(), key: storageKey });
  const canvas = stateRef.current;
  const viewportRef = useRef(null);
  const [, paint] = useReducer((tick) => tick + 1, 0);
  const [space, setSpace] = useState(false);
  const interacted = useRef(false);

  canvas.sync(model.nodes, model.connections);
  canvas.selectedId = model.nodes.some((node) => node.id === selectedId) ? selectedId : null;

  const fit = useCallback(() => {
    const viewport = viewportRef.current;
    canvas.fit(viewport.clientWidth, viewport.clientHeight);
    paint();
    canvas.save();
  }, [canvas]);

  const zoom = (factor) => {
    const viewport = viewportRef.current;
    canvas.zoomAt({ x: viewport.clientWidth / 2, y: viewport.clientHeight / 2 }, canvas.viewport.zoom * factor);
    paint();
    canvas.save();
  };

  useCanvasInteractions(viewportRef, canvas, {
    paint,
    select: (id) => { canvas.selectedId = id; onSelect(id); paint(); },
    selectEdge: (id) => { canvas.selectedId = null; onSelectEdge(id); paint(); },
    interaction: () => { interacted.current = true; },
    space: setSpace,
  });

  // Encuadre inicial cuando el lienzo ya tiene tamaño, y al cambiarlo si nunca se movió.
  useLayoutEffect(() => {
    if (!canvas.hasViewport && viewportRef.current.clientWidth) fit();
  });
  useEffect(() => {
    const viewport = viewportRef.current;
    const observer = new ResizeObserver(() => { if (!canvas.hasViewport && viewport.clientWidth) fit(); });
    observer.observe(viewport);
    return () => { observer.disconnect(); canvas.save(); };
  }, [canvas, fit]);

  const { x, y, zoom: scale } = canvas.viewport;
  const viewportClass = `canvas${canvas.interacting ? ' canvas--dragging' : ''}${canvas.panMode || space ? ' canvas--pan' : ''}`;

  return (
    <div data-service-network-root="" className="service-network" data-interacting={interacted.current ? String(canvas.interacting) : undefined}>
      <section className="canvas-panel card"><header className="canvas__toolbar"><div className="canvas__heading"><h2>{text('Mapa del sistema', 'System map')}</h2>{summary}</div>
        <div className="canvas__controls"><button type="button" className="btn btn-line btn-sm" data-canvas-action="layout" onClick={() => { canvas.layout(model.nodes, model.connections); fit(); }}>{text('Ordenar', 'Auto layout')}</button><button type="button" className="btn btn-line btn-sm" data-canvas-action="fit" onClick={fit}>{text('Encuadrar', 'Fit view')}</button><button type="button" className="btn btn-dark btn-sm" data-canvas-action="add" onClick={onAdd}>{text('+ Añadir servicio', '+ Add service')}</button></div></header>
        <div className={viewportClass} tabIndex={0} role="region" aria-label={text('Lienzo libre de servicios', 'Free service canvas')} ref={viewportRef}>
          <div className="canvas__world" style={{ transform: `translate(${x}px, ${y}px) scale(${scale})` }}>
            <CanvasEdges connections={model.connections} positions={canvas.positions} states={edgeStates} selectedEdgeId={selectedEdgeId} label={edgeLabel} />
            <div className="canvas__nodes">{model.nodes.map((node) => (
              <CanvasNode key={node.id} node={node} position={canvas.positions[node.id]} selected={node.id === canvas.selectedId} label={label} view={views[node.id]} />
            ))}</div>
          </div>
          <div className="canvas__empty" hidden={model.nodes.length > 0}>{text('Añade el primer servicio con + Añadir servicio', 'Add your first service with + Add service')}</div>
        </div>
        <footer className="canvas__footer"><div className="canvas__legend"><span className="canvas__legend-item canvas__legend-item--http">HTTP</span><span className="canvas__legend-item canvas__legend-item--sse">Stream</span><span className="canvas__legend-item canvas__legend-item--error">{text('Caída', 'Down')}</span><span className="canvas__legend-item canvas__legend-item--stellar">Stellar</span></div>
          <span className="canvas__hint">{text('Arrastra · Rueda para zoom · Espacio para mover', 'Drag · Scroll to zoom · Space to pan')}</span><div className="canvas__zoom-controls"><button type="button" className="canvas__icon-button" data-canvas-action="pan" aria-pressed={canvas.panMode} aria-label={text('Mover lienzo', 'Pan canvas')} onClick={() => { canvas.panMode = !canvas.panMode; paint(); }}>✥</button><button type="button" className="canvas__icon-button" data-canvas-action="out" aria-label={text('Alejar', 'Zoom out')} onClick={() => zoom(1 / 1.2)}>−</button><output className="canvas__zoom-label" aria-live="off">{`${Math.round(scale * 100)}%`}</output><button type="button" className="canvas__icon-button" data-canvas-action="in" aria-label={text('Acercar', 'Zoom in')} onClick={() => zoom(1.2)}>+</button></div></footer></section>
      <aside className="service-network__sidebar" aria-label={text('Detalle de lo seleccionado', 'Selection details')}>{sidebar}</aside>
    </div>
  );
}
