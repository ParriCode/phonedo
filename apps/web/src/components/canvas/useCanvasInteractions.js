import { useEffect, useRef } from 'react';

/**
 * Arrastre, pan, zoom y teclado del lienzo con Pointer Events, sin librerías.
 * Se enlaza con listeners nativos: la rueda necesita `passive: false`.
 */
export function useCanvasInteractions(viewportRef, state, callbacks) {
  const latest = useRef(callbacks);
  latest.current = callbacks;

  useEffect(() => {
    const viewport = viewportRef.current;
    const abort = new AbortController();
    const options = { signal: abort.signal };
    const call = (name, ...args) => latest.current[name](...args);
    let gesture = null;
    let space = false;
    let suppressClick = false;
    const point = (event) => {
      const rect = viewport.getBoundingClientRect();
      return { x: event.clientX - rect.left, y: event.clientY - rect.top };
    };
    const editable = (target) => target instanceof Element && target.closest('input,textarea,select,[contenteditable]');
    const setSpace = (value) => { space = value; call('space', value); };

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
      call('interaction', true);
      viewport.setPointerCapture(event.pointerId);
      if (!pan) call('select', id);
      call('paint');
    }, options);

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
      call('paint');
    }, options);

    const finish = (event) => {
      if (!gesture || event.pointerId !== gesture.pointerId) return;
      const previous = gesture;
      gesture = null;
      state.interacting = false;
      call('interaction', false);
      suppressClick = previous.moved;
      if (event.type === 'pointerup' && !previous.moved && !previous.id && !space && !state.panMode) call('select', null);
      state.save();
      call('paint');
    };
    viewport.addEventListener('pointerup', finish, options);
    viewport.addEventListener('pointercancel', finish, options);
    viewport.addEventListener('lostpointercapture', finish, options);

    viewport.addEventListener('click', (event) => {
      // El click sintetizado al terminar un drag nunca debe seleccionar otro nodo.
      event.stopPropagation();
      if (suppressClick) { suppressClick = false; return; }
      if (event.detail === 0) {
        const node = event.target.closest('[data-service-id]');
        if (node) call('select', node.dataset.serviceId);
      }
    }, options);

    viewport.addEventListener('wheel', (event) => {
      if (gesture) return;
      event.preventDefault();
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? viewport.clientHeight : 1);
      state.zoomAt(point(event), state.viewport.zoom * Math.exp(-Math.max(-300, Math.min(300, delta)) * .002));
      call('paint');
      state.save();
    }, { passive: false, signal: abort.signal });

    viewport.addEventListener('keydown', (event) => {
      if (editable(event.target)) return;
      if (event.code === 'Space') { event.preventDefault(); setSpace(true); }
      if (event.key === 'Escape') call('select', null);
      const node = event.target.closest('[data-service-id]');
      const offset = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key];
      if (node && offset && Object.hasOwn(state.positions, node.dataset.serviceId)) {
        event.preventDefault();
        const id = node.dataset.serviceId;
        const position = state.positions[id];
        const step = event.shiftKey ? 48 : 16;
        state.move(id, { x: position.x + offset[0] * step, y: position.y + offset[1] * step });
        call('select', id); call('paint'); state.save();
      }
    }, options);
    window.addEventListener('keyup', (event) => { if (event.code === 'Space') setSpace(false); }, options);
    window.addEventListener('blur', () => setSpace(false), options);
    return () => abort.abort();
  }, [viewportRef, state]);
}
