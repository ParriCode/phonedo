import { useCallback, useRef, useState } from 'react';

/**
 * Estado de React con una referencia siempre actualizada. Las tareas asíncronas
 * (sondeos, operaciones Docker) leen y modifican el último valor sin cierres obsoletos.
 */
export function useStateRef(initial) {
  const [state, setState] = useState(initial);
  const ref = useRef(state);
  const set = useCallback((update) => {
    ref.current = typeof update === 'function' ? update(ref.current) : update;
    setState(ref.current);
  }, []);
  return [state, set, ref];
}
