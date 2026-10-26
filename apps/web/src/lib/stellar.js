// Stellar: eventos SessionPaid del contrato leídos del RPC público.
import { CONFIG } from '../config.js';

export async function rpc(method, params) {
  const response = await fetch(CONFIG.rpc, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }),
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error(`RPC HTTP ${response.status}`);
  const reply = await response.json();
  if (reply.error) throw new Error(`${method}: ${reply.error.message}`);
  return reply.result;
}

function mapEntry(value, key) {
  return value?.map?.find((e) => e.key?.symbol === key)?.val;
}

// Mismo criterio que el parser del backend: topic[0] = "session_paid", topic[1] = id de sesión.
export function parseEvent(event) {
  const topics = event.topicJson;
  if (!Array.isArray(topics) || topics[0]?.symbol !== 'session_paid') return null;
  const units = mapEntry(event.valueJson, 'amount')?.i128;
  const patient = mapEntry(event.valueJson, 'patient')?.address;
  if (units == null || !patient) return null;
  const contract = CONFIG.contracts.find((c) => c.id === event.contractId);
  return {
    id: event.id,
    sessionId: topics[1]?.u64 ?? null,
    amount: Number(units) / 10 ** CONFIG.decimals,
    asset: contract?.asset ?? '?',
    patient,
    txHash: event.txHash,
    ledger: event.ledger,
    paidAt: event.ledgerClosedAt ?? null,
    contractId: event.contractId,
  };
}

/** Ledger de un cursor de getEvents (TOID: el ledger va en los 32 bits altos). */
export function cursorLedger(cursor) {
  try { return Number(BigInt(String(cursor).split('-')[0]) >> 32n); } catch { return 0; }
}

/**
 * Pagos nuevos desde `cursor` (o desde el ledger más antiguo que guarda el RPC).
 * Cada página cubre como mucho ~10 000 ledgers, así que se avanza hasta el último.
 */
// El RPC acepta como mucho 5 contratos por filtro (y 5 filtros por consulta).
export function contractFilters(contracts = CONFIG.contracts) {
  const filters = [];
  for (let i = 0; i < contracts.length; i += 5) filters.push({ type: 'contract', contractIds: contracts.slice(i, i + 5).map((c) => c.id) });
  return filters;
}

export async function fetchPayments(cursor = null) {
  const filters = contractFilters();
  let params;
  if (cursor) params = { filters, pagination: { limit: 200, cursor }, xdrFormat: 'json' };
  else {
    const health = await rpc('getHealth', {});
    params = { startLedger: health.oldestLedger, filters, pagination: { limit: 200 }, xdrFormat: 'json' };
  }
  const payments = [];
  let next = cursor;
  for (let page = 0; page < 40; page++) {
    const result = await rpc('getEvents', params);
    payments.push(...(result.events ?? []).map(parseEvent).filter(Boolean));
    if (!result.cursor || result.cursor === next) break;
    next = result.cursor;
    if (result.latestLedger && cursorLedger(next) >= result.latestLedger) break;
    params = { filters, pagination: { limit: 200, cursor: next }, xdrFormat: 'json' };
  }
  return { payments, cursor: next };
}

/** Une pagos sin repetir, del más reciente al más antiguo. */
export function mergePayments(previous, incoming) {
  const byId = new Map(previous.map((payment) => [payment.id, payment]));
  for (const payment of incoming) byId.set(payment.id, payment);
  return [...byId.values()].sort((a, b) => (b.ledger ?? 0) - (a.ledger ?? 0));
}

export function stats(events) {
  const totals = {};
  for (const e of events) totals[e.asset] = (totals[e.asset] ?? 0) + e.amount;
  return {
    totals,
    sessions: events.length,
    patients: new Set(events.map((e) => e.patient)).size,
    last: events[0] ?? null,
  };
}

/** Pagos agrupados por caso de uso del contrato que los emitió (los contratos desconocidos se ignoran). */
export function groupByUseCase(events, contracts = CONFIG.contracts) {
  const useCases = new Map(contracts.map((c) => [c.id, c.useCase]));
  const groups = {};
  for (const e of events) {
    const useCase = useCases.get(e.contractId);
    if (useCase) (groups[useCase] ??= []).push(e);
  }
  return groups;
}

/** Totales por activo con USDC primero. */
export function sortedTotals(totals) {
  return Object.entries(totals).sort(([a], [b]) => (a === 'USDC' ? -1 : b === 'USDC' ? 1 : 0));
}
