import { useMemo } from 'react';
import { networkModel } from '../../../service_network/models.js';
import { CONFIG } from '../../config.js';
import { useNetwork } from '../../providers/NetworkProvider.jsx';
import { useOperator } from '../../providers/OperatorProvider.jsx';
import { usePayments } from '../../providers/PaymentsProvider.jsx';

const PROBLEM_LEVELS = new Set(['warning', 'error', 'critical']);

/** Une topología, sondeo, actividad y Stellar en un modelo listo para pintar. */
export function useSystemView() {
  const { network, status } = useNetwork();
  const { readers, logs, errors, active, checkedAt } = useOperator();
  const payments = usePayments();
  return useMemo(() => {
    const now = Date.now();
    const chainStatus = payments.net === 'live' ? 'up' : payments.net === 'error' ? 'down' : 'checking';
    const model = networkModel({ services: network, statuses: status, readers, contracts: CONFIG.contracts, rpc: CONFIG.rpc, chainStatus });
    const health = {};
    const activity = {};
    const problems = {};
    const stream = {};
    for (const node of model.nodes) {
      const nodeLogs = logs.filter((log) => log.node === node.id);
      const recentProblem = nodeLogs.find((log) => PROBLEM_LEVELS.has(log.level) && now - log.at < 60_000);
      const down = node.kind === 'stellar' ? payments.net === 'error' : node.status === 'down' || Boolean(errors[node.id]);
      const checked = node.kind === 'stellar' ? payments.net !== 'checking' : checkedAt[node.id];
      health[node.id] = down ? 'error' : recentProblem ? 'degraded' : checked ? (now - checked > 15_000 ? 'stale' : 'healthy') : 'unknown';
      if (node.kind === 'stellar' && payments.net === 'live') health[node.id] = 'healthy';
      const recent = nodeLogs.filter((log) => !log.historical && now - log.at < 60_000);
      activity[node.id] = { perMinute: recent.length, receiving: now - (active[node.id] || 0) < 6_000, payments: payments.events.length };
      if (down) problems[node.id] = { level: 'error', log: { message: errors[node.id] || 'Servicio no disponible' } };
      else if (recentProblem) problems[node.id] = { level: recentProblem.level, log: recentProblem };
      stream[node.id] = node.kind === 'reader' ? Boolean(readers[node.id]?.config?.streamEnabled) : node.kind === 'publisher';
    }
    const edges = {};
    for (const edge of model.connections) {
      if (health[edge.sourceId] === 'error' || health[edge.targetId] === 'error') edges[edge.id] = 'error';
      else if (activity[edge.sourceId]?.receiving || activity[edge.targetId]?.receiving) edges[edge.id] = 'active';
      else if (health[edge.sourceId] === 'healthy' && health[edge.targetId] === 'healthy') edges[edge.id] = 'idle';
      else edges[edge.id] = 'unknown';
    }
    const counts = model.nodes.reduce((result, node) => ({ ...result, [health[node.id]]: (result[health[node.id]] || 0) + 1 }), {});
    return { model, health, activity, problems, stream, edges, counts, now, payments };
  }, [active, checkedAt, errors, logs, network, payments, readers, status]);
}
