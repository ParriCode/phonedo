// Configuración compartida por todas las páginas. Los pagos salen en directo del RPC de Stellar testnet.
export const CONFIG = {
  rpc: 'https://soroban-testnet.stellar.org',
  explorer: 'https://stellar.expert/explorer/testnet',
  contracts: [
    { id: 'CBF2MBQ6W4S6LD3JSIM3NNZET5KBUKOADRZSKIYZRZBAXRM6OJZCNSFI', asset: 'USDC' },
    { id: 'CAPZ2O7LPTRGJ2Q7TTHMCHOKRZ4T7KU5I4E74M2U3YUTC3XONIQDOP2D', asset: 'XLM' },
  ],
  policy: { min: 90, max: 130, minCount: 28, batch: 32, payout: 5 },
  demoPatient: 'GBBO4ZD2YNV3ZBUIBIQAH3VK73Y2RHTSMURUR5LYEK5JMXACK24YN3BC',
  // Cada panel es una página independiente; mañana cada dirección puede ser un servicio aparte.
  panels: { operator: 'operator.html', patient: 'patient.html', insurer: 'insurer.html' },
  refreshMs: 15000,
  decimals: 7,
};

// Cobros reales ya confirmados, para cuando el RPC no responde (se avisa en pantalla).
export const KNOWN = [
  { txHash: '2a345e9fdf594fc385107a2e1a2e973d3cb16f5274fc14e763bbe9dc0406ef47', asset: 'USDC', sessionId: null },
  { txHash: '0ba0adb7ca42e09350f71eec15c09d252dcfacf13b6cc3672afab8017ce78033', asset: 'USDC', sessionId: '20261025001' },
  { txHash: '891b2fe1504a9d9c0a34146828e9caac9527a41e3d467eaecf5a994c145c0aa1', asset: 'XLM', sessionId: null },
].map((e) => ({ ...e, id: e.txHash, amount: CONFIG.policy.payout, patient: CONFIG.demoPatient, paidAt: null, contractId: null }));

export const KINDS = ['reader', 'manager', 'verifier', 'storage', 'publisher'];
export const KIND_ICON = { reader: 'cpu', manager: 'hub', verifier: 'shield', storage: 'db', publisher: 'send' };
export const TEMPLATES = { pulse: 'pulse', temperature: 'thermo' };
export const ORGS = ['hospital', 'insurer', 'lab'];
export const STORE_KEY = 'phonendo.network.v2';

// Despliegue local de deploy/docker/compose.yml.
export const DEMO_NETWORK = [
  { id: 'reader-1', kind: 'reader', name: 'reader-docker', org: 'hospital', url: 'http://localhost:7101', template: 'pulse', managers: ['manager-1'] },
  { id: 'manager-1', kind: 'manager', name: 'manager', org: 'hospital', url: 'http://localhost:7102', managers: [] },
  { id: 'verifier-1', kind: 'verifier', name: 'verifier', org: 'hospital', url: 'http://localhost:7103', managers: ['manager-1'] },
  { id: 'storage-1', kind: 'storage', name: 'storage', org: 'hospital', url: 'http://localhost:7104', managers: ['manager-1'] },
  { id: 'publisher-1', kind: 'publisher', name: 'publisher', org: 'hospital', url: 'http://localhost:7105', managers: ['manager-1'] },
];
