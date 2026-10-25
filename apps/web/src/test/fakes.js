// Respuestas falsas del RPC de Stellar y del panel local (/api/local).
import { vi } from 'vitest';
import { CONFIG } from '../config.js';

export const PATIENT = 'GBBO4ZD2YNV3ZBUIBIQAH3VK73Y2RHTSMURUR5LYEK5JMXACK24YN3BC';

/** Evento real del primer cobro en USDC en testnet. */
export function paidEvent(overrides = {}) {
  return {
    type: 'contract', ledger: 5381362, ledgerClosedAt: '2026-10-25T12:13:17Z',
    contractId: CONFIG.contracts[0].id, id: '0023112773797957632-0000000001',
    txHash: '0ba0adb7ca42e09350f71eec15c09d252dcfacf13b6cc3672afab8017ce78033',
    topicJson: [{ symbol: 'session_paid' }, { u64: '20261025001' }],
    valueJson: { map: [
      { key: { symbol: 'amount' }, val: { i128: '50000000' } },
      { key: { symbol: 'patient' }, val: { address: PATIENT } },
    ] },
    ...overrides,
  };
}

const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });

/**
 * Sustituye fetch. `events` alimenta getEvents (o null para simular el RPC caído);
 * `local(path, body, method)` responde a /api/local.
 */
export function mockFetch({ events = [paidEvent()], local = () => [] } = {}) {
  const calls = [];
  globalThis.fetch = vi.fn(async (url, init = {}) => {
    const body = init.body ? JSON.parse(init.body) : undefined;
    calls.push({ url: String(url), method: init.method || 'GET', body });
    if (String(url) === CONFIG.rpc) {
      if (events === null) throw new TypeError('Failed to fetch');
      if (body.method === 'getHealth') return json({ jsonrpc: '2.0', id: 1, result: { oldestLedger: 5262197, latestLedger: 5383156 } });
      return json({ jsonrpc: '2.0', id: 1, result: { events, cursor: null } });
    }
    const path = String(url).replace('/api/local/', '');
    try {
      return json(await local(path, body, init.method || 'GET'));
    } catch (error) {
      return json({ error: error.message }, 500);
    }
  });
  return calls;
}
