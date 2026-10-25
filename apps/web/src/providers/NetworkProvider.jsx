import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { DEMO_NETWORK, KINDS, STORE_KEY } from '../config.js';
import { storageGet, storageSet } from '../lib/storage.js';
import { useStateRef } from '../lib/useStateRef.js';

const NetworkContext = createContext(null);

function loadNetwork() {
  try {
    const saved = JSON.parse(storageGet(STORE_KEY));
    if (Array.isArray(saved) && saved.every((n) => KINDS.includes(n.kind))) return saved;
  } catch { /* red guardada no válida */ }
  return structuredClone(DEMO_NETWORK);
}

/** Servicios del despliegue, su estado de acceso y lo seleccionado (un nodo o una conexión). La red se guarda en el navegador. */
export function NetworkProvider({ children }) {
  const [network, setNetwork, networkRef] = useStateRef(loadNetwork);
  const [status, setStatusMap, statusRef] = useStateRef({});
  const [selected, setSelected] = useState(null);
  const [selectedEdge, setSelectedEdge] = useState(null);

  useEffect(() => { storageSet(STORE_KEY, JSON.stringify(network)); }, [network]);

  const actions = useMemo(() => ({
    setNetwork,
    select: (id) => { setSelected(id); setSelectedEdge(null); },
    selectEdge: (id) => { setSelectedEdge(id); setSelected(null); },
    nodeById: (id) => networkRef.current.find((n) => n.id === id),
    addNode: (node) => setNetwork((list) => [...list, node]),
    updateNode: (id, patch) => setNetwork((list) => list.map((n) => (n.id === id ? { ...n, ...patch } : n))),
    removeNode: (id) => {
      setNetwork((list) => list.filter((n) => n.id !== id).map((n) => ({ ...n, managers: n.managers.filter((m) => m !== id) })));
      setSelected(null);
      setSelectedEdge(null);
    },
    setStatus: (id, value) => setStatusMap((map) => ({ ...map, [id]: value })),
  }), [networkRef, setNetwork, setStatusMap]);

  const value = useMemo(() => ({ network, status, selected, selectedEdge, networkRef, statusRef, ...actions }),
    [network, status, selected, selectedEdge, networkRef, statusRef, actions]);

  return <NetworkContext.Provider value={value}>{children}</NetworkContext.Provider>;
}

export function useNetwork() {
  const context = useContext(NetworkContext);
  if (!context) throw new Error('useNetwork necesita un NetworkProvider');
  return context;
}
