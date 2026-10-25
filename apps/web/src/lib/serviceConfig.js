// Archivos de configuración de los servicios y enlaces entre contenedores Docker.
import { CONFIG } from '../config.js';
import { portOf, slug } from './format.js';

export function configName(node) {
  return node.kind === 'publisher' ? 'config.json' : `${node.kind}-${slug(node.name)}.json`;
}

// Mismo formato que deploy/docker/*.json y apps/publisher/config.json.
export function configFor(node, network) {
  const byId = (id) => network.find((n) => n.id === id);
  const urls = (ids) => ids.map(byId).filter(Boolean).map((n) => n.url);
  const linked = (kind) => network.filter((n) => n.kind === kind && n.managers.includes(node.id)).map((n) => n.url);
  const server = (port) => ({ host: '0.0.0.0', port: portOf(node.url, port) });
  switch (node.kind) {
    case 'reader': {
      const config = {
        server: { ...server(3002), enabled: true },
        readerId: slug(node.name),
        services: { managers: urls(node.managers).map((url) => ({ url, token: 'demo-manager' })) },
        subscriptions: {},
        stream: { enabled: true },
      };
      if (node.template === 'pulse') config.simulation = 'pulse';
      if (node.template === 'temperature') config.simulation = 'temperature';
      return config;
    }
    case 'manager':
      return {
        server: server(3003),
        services: { verifiers: linked('verifier'), storages: linked('storage') },
        stream: { enabled: true },
        subscriptions: { readers: [], verifiers: [], storages: [] },
        outputStreams: { verifiers: true, storages: true },
      };
    case 'verifier':
      return { server: server(5000), services: {}, subscriptions: { managers: [] }, stream: { enabled: true } };
    case 'storage':
      return { server: server(5000), services: { managers: [] }, subscriptions: { managers: [] }, stream: { enabled: true } };
    case 'publisher':
      return {
        server: server(3005),
        subscriptions: { managers: urls(node.managers) },
        batchSize: CONFIG.policy.batch,
        policy: { minValue: CONFIG.policy.min, maxValue: CONFIG.policy.max, minCount: CONFIG.policy.minCount },
        patients: { default: CONFIG.demoPatient },
        circuitsPath: '../../circuits',
        stellar: { contractId: CONFIG.contracts[0].id, source: 'alex', network: 'testnet' },
      };
    default:
      return {};
  }
}

export function dockerEndpoint(node) {
  return node.dockerUrl || node.url.replace(/localhost|127\.0\.0\.1/, 'host.docker.internal');
}

export function dockerDefaultConfig(kind, name, network) {
  const server = { host: '0.0.0.0', port: { reader: 3002, manager: 3003, verifier: 5000, storage: 5000, publisher: 3005 }[kind] };
  const managed = (type) => network.filter((node) => node.kind === type && node.managed).map(dockerEndpoint);
  const managers = managed('manager');
  if (kind === 'reader') return { server: { ...server, enabled: true }, readerId: name, services: { managers: managers.slice(0, 1).map((url) => ({ url, token: '' })) }, stream: { enabled: false } };
  if (kind === 'manager') return { server, managerId: name, services: { verifiers: managed('verifier'), storages: managed('storage') }, stream: { enabled: true }, subscriptions: { readers: [], verifiers: [], storages: [] }, outputStreams: { verifiers: true, storages: true } };
  if (kind === 'publisher') return { server, subscriptions: { managers: managers.slice(0, 1) }, contracts: {}, batchSize: 32, policy: { minValue: 90, maxValue: 130, minCount: 28 }, patients: { default: CONFIG.demoPatient }, circuitsPath: '/circuits', stellar: { source: 'phonendo', network: 'testnet' } };
  return { server, services: {}, subscriptions: { managers: [] }, stream: { enabled: true } };
}

const targetUrl = (target) => (typeof target === 'string' ? target : target.url);

/** Enlaza un nodo Docker con los Managers que aparecen en su configuración. Devuelve una red nueva. */
export function linkDockerNode(network, id, config) {
  const node = network.find((item) => item.id === id);
  if (!node) return network;
  const targets = [...(config.services?.managers || []), ...(config.subscriptions?.managers || []), ...(config.webSettings?.managers || [])].map(targetUrl);
  const managers = network.filter((item) => item.kind === 'manager' && targets.includes(dockerEndpoint(item))).map((item) => item.id);
  let next = network.map((item) => (item.id === id ? { ...item, managers } : item));
  if (node.kind === 'manager') {
    const peers = [...(config.services?.verifiers || []), ...(config.services?.storages || [])].map(targetUrl);
    next = next.map((item) => (peers.includes(dockerEndpoint(item)) ? { ...item, managers: [...new Set([...item.managers, id])] } : item));
  }
  return next;
}
