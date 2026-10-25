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

export async function fetchPayments() {
  const health = await rpc('getHealth', {});
  const filters = [{ type: 'contract', contractIds: CONFIG.contracts.map((c) => c.id) }];
  let params = { startLedger: health.oldestLedger, filters, pagination: { limit: 200 }, xdrFormat: 'json' };
  const found = [];
  for (let page = 0; page < 10; page++) {
    const result = await rpc('getEvents', params);
    const events = result.events ?? [];
    found.push(...events.map(parseEvent).filter(Boolean));
    if (events.length < 200 || !result.cursor) break;
    params = { filters, pagination: { limit: 200, cursor: result.cursor }, xdrFormat: 'json' };
  }
  return found.sort((a, b) => (b.ledger ?? 0) - (a.ledger ?? 0));
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

/** Totales por activo con USDC primero. */
export function sortedTotals(totals) {
  return Object.entries(totals).sort(([a], [b]) => (a === 'USDC' ? -1 : b === 'USDC' ? 1 : 0));
}
