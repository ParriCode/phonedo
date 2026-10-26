import { describe, expect, it, vi } from 'vitest';
import { CONFIG } from '../config.js';
import { paidEvent, PATIENT } from '../test/fakes.js';
import { configFor, configName, connectionsFromSnapshots, dockerDefaultConfig, linkDockerNode } from './serviceConfig.js';
import { contractFilters, cursorLedger, fetchPayments, groupByUseCase, mergePayments, parseEvent, sortedTotals, stats } from './stellar.js';
import { short } from './format.js';

describe('stellar', () => {
  it('convierte un evento session_paid real', () => {
    expect(parseEvent(paidEvent())).toEqual({
      id: '0023112773797957632-0000000001', sessionId: '20261025001', amount: 5, asset: CONFIG.contracts[0].asset, patient: PATIENT,
      txHash: paidEvent().txHash, ledger: 5381362, paidAt: '2026-10-25T12:13:17Z', contractId: CONFIG.contracts[0].id,
    });
    expect(parseEvent({ topicJson: [{ symbol: 'set_policy' }] })).toBeNull();
    expect(parseEvent(paidEvent({ valueJson: { map: [] } }))).toBeNull();
  });

  it('resume pagos con USDC primero', () => {
    const events = [{ asset: 'XLM', amount: 5, patient: 'A' }, { asset: 'USDC', amount: 5, patient: 'A' }, { asset: 'USDC', amount: 2.5, patient: 'B' }];
    const summary = stats(events);
    expect(summary.sessions).toBe(3);
    expect(summary.patients).toBe(2);
    expect(sortedTotals(summary.totals)).toEqual([['USDC', 7.5], ['XLM', 5]]);
  });

  it('reparte los contratos en filtros de 5 como exige el RPC', () => {
    const contracts = Array.from({ length: 8 }, (_, i) => ({ id: `C${i}` }));
    expect(contractFilters(contracts).map((filter) => filter.contractIds.length)).toEqual([5, 3]);
    expect(contractFilters().flatMap((filter) => filter.contractIds)).toEqual(CONFIG.contracts.map((c) => c.id));
  });

  it('agrupa los pagos por caso de uso y descarta contratos desconocidos', () => {
    const [rehab, cold] = CONFIG.contracts;
    const events = [{ contractId: rehab.id }, { contractId: cold.id }, { contractId: rehab.id }, { contractId: 'CAJENO' }];
    const groups = groupByUseCase(events);
    expect(groups.rehab).toHaveLength(2);
    expect(groups['cold-chain']).toHaveLength(1);
    expect(Object.keys(groups)).toEqual(['rehab', 'cold-chain']);
  });

  it('recorre todas las páginas del RPC hasta el último ledger y sigue desde el cursor', async () => {
    const toid = (ledger) => `${(BigInt(ledger) << 32n).toString().padStart(19, '0')}-4294967295`;
    const requests = [];
    globalThis.fetch = vi.fn(async (url, init) => {
      const body = JSON.parse(init.body);
      requests.push(body);
      const reply = (result) => new Response(JSON.stringify({ jsonrpc: '2.0', id: 1, result }));
      if (body.method === 'getHealth') return reply({ oldestLedger: 100, latestLedger: 30_000 });
      const cursor = body.params.pagination.cursor;
      if (!cursor) return reply({ events: [], cursor: toid(10_100), latestLedger: 30_000 });
      if (cursor === toid(10_100)) return reply({ events: [paidEvent()], cursor: toid(30_000), latestLedger: 30_000 });
      return reply({ events: [], cursor: toid(30_000), latestLedger: 30_000 });
    });
    expect(cursorLedger(toid(10_100))).toBe(10_100);
    const first = await fetchPayments();
    expect(first.payments.map((p) => p.sessionId)).toEqual(['20261025001']);
    expect(requests.filter((r) => r.method === 'getEvents')).toHaveLength(2);
    const again = await fetchPayments(first.cursor);
    expect(again.payments).toEqual([]);
    expect(mergePayments(first.payments, [...first.payments, { id: 'nuevo', ledger: 9e9 }]).map((p) => p.id)).toEqual(['nuevo', first.payments[0].id]);
  });

  it('acorta identificadores largos', () => {
    expect(short(PATIENT, 5, 4)).toBe('GBBO4…N3BC');
    expect(short('')).toBe('—');
  });
});

describe('configuración de servicios', () => {
  it('dibuja solo transportes presentes en configuraciones Docker reales', () => {
    const reader = { id: 'r', kind: 'reader', dockerUrl: 'http://reader:3002', serviceConfig: { services: { managers: [] } } };
    const manager = { id: 'm', kind: 'manager', dockerUrl: 'http://manager:3003', serviceConfig: { subscriptions: { readers: ['http://reader:3002'] } } };
    const verifier = { id: 'v', kind: 'verifier', dockerUrl: 'http://verifier:5000', serviceConfig: { subscriptions: { managers: [] } } };
    expect(connectionsFromSnapshots([reader, manager, verifier])).toEqual([{ sourceId: 'r', targetId: 'm', transport: 'sse' }]);
  });
  const network = [
    { id: 'r', kind: 'reader', name: 'Reader Uno', url: 'http://localhost:7101', template: 'pulse', managers: ['m'] },
    { id: 'm', kind: 'manager', name: 'manager', url: 'http://localhost:7102', managers: [] },
    { id: 'v', kind: 'verifier', name: 'verifier', url: 'http://localhost:7103', managers: ['m'] },
  ];

  it('genera los JSON con el formato de deploy/docker', () => {
    expect(configName(network[0])).toBe('reader-reader-uno.json');
    const reader = configFor(network[0], network);
    expect(reader.server).toEqual({ host: '0.0.0.0', port: 7101, enabled: true });
    expect(reader.services.managers).toEqual([{ url: 'http://localhost:7102', token: 'demo-manager' }]);
    expect(reader.simulation).toBe('pulse');
    expect(configFor(network[1], network).services.verifiers).toEqual(['http://localhost:7103']);
  });

  it('enlaza contenedores Docker según su configuración', () => {
    const docker = [
      { id: 'm', kind: 'manager', url: 'http://localhost:9000', dockerUrl: 'http://manager-a:3003', managed: true, managers: [] },
      { id: 'v', kind: 'verifier', url: 'http://localhost:9001', dockerUrl: 'http://verifier-a:5000', managed: true, managers: [] },
      { id: 'r', kind: 'reader', url: 'http://localhost:9002', managed: true, managers: [] },
    ];
    expect(dockerDefaultConfig('reader', 'r', docker).services.managers).toEqual([{ url: 'http://manager-a:3003', token: '' }]);
    const linked = linkDockerNode(docker, 'm', { services: { verifiers: ['http://verifier-a:5000'] } });
    expect(linked.find((n) => n.id === 'v').managers).toEqual(['m']);
    expect(linkDockerNode(linked, 'r', { webSettings: { managers: [{ url: 'http://manager-a:3003' }] } }).find((n) => n.id === 'r').managers).toEqual(['m']);
    expect(docker[1].managers).toEqual([]);
  });
});
