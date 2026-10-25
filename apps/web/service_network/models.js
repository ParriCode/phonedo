/** Modelos de topología independientes de la interfaz y del runtime local/remoto. */
export const NODE_SIZE = Object.freeze({ width: 236, height: 150 });
export const KIND_ORDER = Object.freeze({ reader: 0, manager: 1, verifier: 2, storage: 2, publisher: 3, stellar: 4 });

/** @typedef {{id:string,kind:string,name:string,status:string,address:string,organization:string,machineId:string|null,runtime:string,tags:string[]}} Service */
/** @typedef {{id:string,sourceId:string,targetId:string,transport:string,state:string}} Connection */

export function serviceModel(source, status = 'unknown') {
  return {
    id: String(source.id), kind: source.kind, name: String(source.name || source.id),
    status, address: String(source.url || ''), organization: String(source.org || 'unassigned'),
    machineId: source.machineId || null, runtime: source.managed ? 'docker' : 'external',
    tags: Array.isArray(source.tags) ? source.tags.map(String) : [],
  };
}

export function networkModel({ services, statuses = {}, readers = {}, contracts = [], rpc, chainStatus }) {
  const nodes = services.map((service) => serviceModel(service, statuses[service.id]));
  if (contracts.length) nodes.push({
    id: 'contract', kind: 'stellar', name: 'Stellar testnet', status: chainStatus,
    address: rpc, organization: 'stellar', machineId: null, runtime: 'remote', tags: ['testnet'],
  });
  const known = new Set(nodes.map((node) => node.id));
  const connections = [];
  const add = (sourceId, targetId, transport) => {
    if (!known.has(sourceId) || !known.has(targetId)) return;
    const id = `${sourceId}:${targetId}:${transport}`;
    if (!connections.some((edge) => edge.id === id)) connections.push({ id, sourceId, targetId, transport, state: 'configured' });
  };
  for (const service of services) {
    for (const manager of service.managers || []) {
      if (service.kind === 'reader') {
        const config = readers[service.id]?.config;
        if (!config || config.httpEnabled) add(service.id, manager, 'http');
        else if (config.streamEnabled) add(service.id, manager, 'sse');
      } else if (service.kind === 'publisher') add(manager, service.id, 'sse');
      else add(manager, service.id, 'http');
    }
    if (service.kind === 'publisher') add(service.id, 'contract', 'stellar');
  }
  return { nodes, connections };
}

export function hostLabel(address) {
  try { return new URL(address).host; } catch { return address || '—'; }
}
