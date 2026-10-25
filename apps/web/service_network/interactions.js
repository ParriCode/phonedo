/** Interacciones por Pointer Events: ratón, lápiz y táctil sin librerías externas. */
export function bindInteractions(viewport, state, { paint, select, settled, interaction }) {
  const abort = new AbortController();
  const signal = abort.signal;
  let gesture = null;
  let space = false;
  let suppressClick = false;
  const point = (event) => {
    const rect = viewport.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };
  const editable = (target) => target instanceof Element && target.closest('input,textarea,select,[contenteditable]');
  viewport.addEventListener('pointerdown', (event) => {
    if (gesture || ![0, 1].includes(event.button)) return;
    const element = event.target.closest('[data-service-id]');
    const id = element?.dataset.serviceId;
    const pan = event.button === 1 || space || state.panMode || !id;
    if (id && !pan && !Object.hasOwn(state.positions, id)) return;
    event.preventDefault();
    (pan ? viewport : element).focus({ preventScroll: true });
    gesture = { pointerId: event.pointerId, origin: point(event), viewport: { ...state.viewport },
      id: pan ? null : id, position: id ? { ...state.positions[id] } : null, moved: false };
    state.interacting = true;
    interaction(true);
    viewport.setPointerCapture(event.pointerId);
    if (!pan) select(id);
    paint();
  }, { signal });
  viewport.addEventListener('pointermove', (event) => {
    if (!gesture || event.pointerId !== gesture.pointerId) return;
    const current = point(event);
    const dx = current.x - gesture.origin.x;
    const dy = current.y - gesture.origin.y;
    if (Math.hypot(dx, dy) > 3) gesture.moved = true;
    if (!gesture.moved) return;
    if (gesture.id) state.move(gesture.id, {
      x: gesture.position.x + dx / gesture.viewport.zoom,
      y: gesture.position.y + dy / gesture.viewport.zoom,
    });
    else state.viewport = { ...gesture.viewport, x: gesture.viewport.x + dx, y: gesture.viewport.y + dy };
    paint();
  }, { signal });
  const finish = (event) => {
    if (!gesture || event.pointerId !== gesture.pointerId) return;
    const previous = gesture;
    gesture = null;
    state.interacting = false;
    interaction(false);
    suppressClick = previous.moved;
    if (event.type === 'pointerup' && !previous.moved && !previous.id && !space && !state.panMode) select(null);
    state.save();
    paint();
    settled();
  };
  viewport.addEventListener('pointerup', finish, { signal });
  viewport.addEventListener('pointercancel', finish, { signal });
  viewport.addEventListener('lostpointercapture', finish, { signal });
  viewport.addEventListener('click', (event) => {
    // El click sintetizado al terminar un drag nunca debe seleccionar otro nodo.
    event.stopPropagation();
    if (suppressClick) { suppressClick = false; return; }
    if (event.detail === 0) {
      const node = event.target.closest('[data-service-id]');
      if (node) select(node.dataset.serviceId);
    }
  }, { signal });
  viewport.addEventListener('wheel', (event) => {
    if (gesture) return;
    event.preventDefault();
    const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? viewport.clientHeight : 1);
    state.zoomAt(point(event), state.viewport.zoom * Math.exp(-Math.max(-300, Math.min(300, delta)) * .002));
    paint();
    state.save();
  }, { passive: false, signal });
  viewport.addEventListener('keydown', (event) => {
    if (editable(event.target)) return;
    if (event.code === 'Space') { event.preventDefault(); space = true; viewport.classList.add('canvas--pan'); }
    if (event.key === 'Escape') { select(null); }
    const node = event.target.closest('[data-service-id]');
    const offset = { ArrowLeft:[-1,0], ArrowRight:[1,0], ArrowUp:[0,-1], ArrowDown:[0,1] }[event.key];
    if (node && offset && Object.hasOwn(state.positions, node.dataset.serviceId)) {
      event.preventDefault();
      const id = node.dataset.serviceId;
      const position = state.positions[id];
      const step = event.shiftKey ? 48 : 16;
      state.move(id, { x: position.x + offset[0] * step, y: position.y + offset[1] * step });
      select(id); paint(); state.save();
    }
  }, { signal });
  window.addEventListener('keyup', (event) => {
    if (event.code === 'Space') { space = false; viewport.classList.toggle('canvas--pan', state.panMode); }
  }, { signal });
  window.addEventListener('blur', () => { space = false; viewport.classList.toggle('canvas--pan', state.panMode); }, { signal });
  return () => abort.abort();
}
