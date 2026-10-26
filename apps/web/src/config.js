// Configuración compartida por todas las páginas. Los pagos salen en directo del RPC de Stellar testnet.
export const CONFIG = {
  rpc: 'https://soroban-testnet.stellar.org',
  explorer: 'https://stellar.expert/explorer/testnet',
  contracts: [
    { id: 'CDH7PZQYQCYBCRO56F4WJP5BMEFPIBAEAQUAHKENXRYHZCTZPEH6UW3E', asset: 'XLM', useCase: 'rehab' },
    { id: 'CALYXI6MEJMR5HFBFSGVATUFZDCUPQSNVBQEVWFHREJH4DVOCQ5QMP6N', asset: 'XLM', useCase: 'cold-chain' },
    { id: 'CCLQFKRWBLRSPLVAFWBLG22LPRGP3GEV47CGXA6C3VAGPQ2QITE3DNYL', asset: 'USDC', useCase: 'rehab' },
    { id: 'CACUZG5V45NPFFB5JSLHMTF6NHEP5GMGZ5QJKJPET4ZIRTWOW6VS2VQS', asset: 'USDC', useCase: 'cold-chain' },
    { id: 'CD3ZLDTB7QKJLMAIBSCL75TRHE6IUZ27RW5FLWNB4F3GUQENZZZSM45H', asset: 'USDC', useCase: 'rehab' },
    { id: 'CDNPBN6HZP4PZKRFOOA2PYC772KF4THXTJNKHBS5Y33HCAVDWCVO5SRE', asset: 'USDC', useCase: 'cold-chain' },
    { id: 'CBF2MBQ6W4S6LD3JSIM3NNZET5KBUKOADRZSKIYZRZBAXRM6OJZCNSFI', asset: 'USDC', useCase: 'rehab' },
    { id: 'CAPZ2O7LPTRGJ2Q7TTHMCHOKRZ4T7KU5I4E74M2U3YUTC3XONIQDOP2D', asset: 'XLM', useCase: 'rehab' },
  ],
  policy: { min: 90, max: 130, minCount: 4, batch: 5, payout: 0.1 },
  coldPolicy: { min: 2, max: 8, minCount: 5, batch: 5, payout: 0.1 },
  demoPatient: 'GBBO4ZD2YNV3ZBUIBIQAH3VK73Y2RHTSMURUR5LYEK5JMXACK24YN3BC',
  // Cada panel es una página independiente; mañana cada dirección puede ser un servicio aparte.
  panels: { operator: 'operator.html', patient: 'patient.html', company: 'company.html' },
  refreshMs: 15000,
  decimals: 7,
};

// Cobros reales ya confirmados, para cuando el RPC no responde (se avisa en pantalla).
export const KNOWN = [
  { txHash: '084d4e8223cb1a2db2d040920c59b19aa10968352815839e4134836f70fbb1ed', asset: 'USDC', amount: 0.1, sessionId: '1792953089828', contractId: CONFIG.contracts[0].id },
  { txHash: 'a9466f1ea47b3f0662322988721a5da954487cb31be31bb9d64fae266e90a986', asset: 'USDC', amount: 0.1, sessionId: '1792953122318', contractId: CONFIG.contracts[1].id },
  { txHash: '2a345e9fdf594fc385107a2e1a2e973d3cb16f5274fc14e763bbe9dc0406ef47', asset: 'USDC', amount: 5, sessionId: null, contractId: CONFIG.contracts[2].id },
  { txHash: '0ba0adb7ca42e09350f71eec15c09d252dcfacf13b6cc3672afab8017ce78033', asset: 'USDC', amount: 5, sessionId: '20261025001', contractId: CONFIG.contracts[2].id },
  { txHash: '891b2fe1504a9d9c0a34146828e9caac9527a41e3d467eaecf5a994c145c0aa1', asset: 'XLM', amount: 5, sessionId: null, contractId: CONFIG.contracts[3].id },
].map((e) => ({ ...e, id: e.txHash, patient: CONFIG.demoPatient, paidAt: null }));

export const KINDS = ['reader', 'manager', 'verifier', 'storage', 'publisher'];
export const KIND_ICON = { reader: 'cpu', manager: 'hub', verifier: 'shield', storage: 'db', publisher: 'send' };
export const TEMPLATES = { pulse: 'pulse', temperature: 'thermo' };
export const ORGS = ['hospital', 'insurer', 'lab'];
