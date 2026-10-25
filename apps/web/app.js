// Phonendo web: sin compilación ni dependencias. Los pagos salen en directo del RPC de Stellar testnet.
'use strict';

const CONFIG = {
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
const KNOWN = [
  { txHash: '2a345e9fdf594fc385107a2e1a2e973d3cb16f5274fc14e763bbe9dc0406ef47', asset: 'USDC', sessionId: null },
  { txHash: '0ba0adb7ca42e09350f71eec15c09d252dcfacf13b6cc3672afab8017ce78033', asset: 'USDC', sessionId: '20261025001' },
  { txHash: '891b2fe1504a9d9c0a34146828e9caac9527a41e3d467eaecf5a994c145c0aa1', asset: 'XLM', sessionId: null },
].map((e) => ({ ...e, id: e.txHash, amount: CONFIG.policy.payout, patient: CONFIG.demoPatient, paidAt: null, contractId: null }));

const I18N = {
  en: {
    'launch.eyebrow': 'Phonendo on Stellar', 'launch.title': 'Choose a panel',
    'launch.lead': 'Sensor readings are verified and signed by services the hospital runs. A Stellar smart contract then checks a zero-knowledge proof of those readings and pays, without the readings ever being published.',
    'launch.panels': 'Panels', 'launch.open': 'Open',
    'stage.reader.t': 'Reader', 'stage.reader.p': 'Collects sensor readings',
    'stage.manager.t': 'Manager', 'stage.manager.p': 'Routes events, retries failures',
    'stage.verifier.t': 'Verifier', 'stage.verifier.p': 'Checks and signs readings',
    'stage.publisher.t': 'Publisher', 'stage.publisher.p': 'Builds the proof, calls claim()',
    'stage.contract.t': 'Stellar contract', 'stage.contract.p': 'Verifies the proof and pays',
    'panel.operator.t': 'Operator console', 'panel.operator.p': 'The services of a deployment: map, reachability check of each one, and their configuration files.',
    'panel.patient.t': 'Patient panel', 'panel.patient.p': 'Payouts received by a Stellar account, read from the contract events.',
    'panel.insurer.t': 'Insurer panel', 'panel.insurer.p': 'Payouts made by the contract, each with its transaction on the explorer.',
    'launch.note': 'Each panel is an independent page that does not link to the others; they will be deployed as separate services. Payout data comes live from the Stellar testnet RPC.',
    'launch.proof': 'Real transactions on testnet:',
    'op.laneDesc.reader': 'Collect sensor data', 'op.laneDesc.manager': 'Route and retry events', 'op.laneDesc.verifier': 'Check and sign, keep history',
    'op.laneDesc.publisher': 'Prove and claim', 'op.laneDesc.chain': 'Verify and pay',
    'op.filter': 'Organisation', 'op.filter.all': 'All', 'op.nodes': 'nodes',
    'op.live': 'Contract events', 'op.liveEmpty': 'No session_paid events yet.', 'op.hintTitle': 'Select a node',
    'op.configHint': 'Its ready-to-run configuration appears here.', 'op.how': 'How data flows',
    'op.how1': 'Readers collect sensor data and push it to a Manager.', 'op.how2': 'The Manager routes each event and retries on failure.',
    'op.how3': 'Verifiers check and sign it. Storage keeps the history.', 'op.how4': 'The Publisher proves the session and calls the contract.',
    'op.how5': 'The Stellar contract verifies the proof and pays.',
    'footer.built': 'Built on Stellar testnet', 'footer.contract': 'View the contract on Stellar Expert',
    'net.checking': 'Connecting to testnet…', 'net.live': 'Stellar testnet · live', 'net.error': 'Testnet unreachable · snapshot',
    'kpi.paid': 'Paid out', 'kpi.sessions': 'Verified sessions', 'kpi.patients': 'Patients rewarded', 'kpi.last': 'Last payout',
        'kpi.earned': 'Total earned', 'kpi.yourSessions': 'Sessions completed', 
    'op.eyebrow': 'Operator console', 'op.title': 'Network', 'op.lead': 'Readers, managers, verifiers, storages and publishers of the deployment, wired to the Stellar contract. Add nodes, check them and export their configuration.',
    'op.check': 'Check all', 'op.export': 'Export deployment', 'op.reset': 'Reset to demo',
    'op.canvas': 'Network map', 'op.legend.http': 'HTTP push', 'op.legend.sse': 'SSE subscription', 'op.legend.chain': 'Stellar transaction',
    'op.lane.reader': 'Readers', 'op.lane.manager': 'Managers', 'op.lane.verifier': 'Verifiers & storage', 'op.lane.publisher': 'Publishers', 'op.lane.chain': 'Stellar',
    'op.add': 'Add', 'op.summary': 'Deployment', 'op.reachable': 'reachable', 'op.select': 'Select a node on the map to see its details and configuration.',
    'op.details': 'Details', 'op.url': 'Address', 'op.org': 'Organisation', 'op.status': 'Status', 'op.template': 'Profile', 'op.links': 'Sends to / listens to',
    'op.config': 'Configuration', 'op.copy': 'Copy', 'op.download': 'Download', 'op.remove': 'Remove', 'op.checkOne': 'Check',
    'op.tip': 'Status is a reachability check from your browser. Open this page from the same machine as the services for the most accurate result.',
    'op.contractTip': 'The contract holds the policy and the reward pool. Events are read live from the RPC.',
    'op.managers': 'Connected managers', 'op.noManagers': 'Add a manager first.',
    'status.up': 'Reachable', 'status.down': 'Unreachable', 'status.checking': 'Checking…', 'status.unknown': 'Not checked',
    'kind.reader': 'Reader', 'kind.manager': 'Manager', 'kind.verifier': 'Verifier', 'kind.storage': 'Storage', 'kind.publisher': 'Publisher',
    'kindDesc.reader': 'Collects sensor readings', 'kindDesc.manager': 'Routes and retries events', 'kindDesc.verifier': 'Checks and signs readings',
    'kindDesc.storage': 'Keeps verified history', 'kindDesc.publisher': 'Proves and claims on Stellar',
    'org.hospital': 'Hospital', 'org.insurer': 'Insurer', 'org.lab': 'Lab',
    'tpl.pulse': 'Simulated pulse', 'tpl.pulsed': 'simulation: pulse', 'tpl.temperature': 'Simulated temperature', 'tpl.temperatured': 'simulation: temperature',
    'dlg.title': 'Add a node', 'dlg.lead': 'It appears on the map and gets its own configuration file.', 'dlg.kind': 'Type', 'dlg.template': 'Sensor profile',
    'dlg.name': 'Name', 'dlg.url': 'Address (URL)', 'dlg.urlHelp': 'Where the service listens, e.g. http://192.168.1.20:3002', 'dlg.urlError': 'Enter a URL starting with http:// or https://',
    'dlg.cancel': 'Cancel', 'dlg.add': 'Add node',
    'toast.added': 'Node added', 'toast.removed': 'Node removed', 'toast.copied': 'Copied to clipboard', 'toast.reset': 'Demo network restored',
    'toast.newPayout': 'New payout on Stellar', 'toast.exported': 'Deployment exported',
    'pt.eyebrow': 'Patient', 'pt.title': 'Your rehab rewards', 'pt.lead': 'Every completed session pays you automatically. Your heart readings stay with your hospital.',
    'pt.account': 'Stellar account', 'pt.view': 'View', 'pt.invalid': 'A Stellar account starts with G and has 56 characters.',
    'pt.payouts': 'Your payouts', 'pt.none': 'No payouts for this account yet.',
    'pt.how': 'How you earn', 'pt.how1': 'Wear the pulse band during your session', 'pt.how2': 'Keep your heart rate in the target zone',
    'pt.how3': 'The hospital proves it, without sharing readings', 'pt.how4': 'USDC lands in your wallet',
    'pt.privacy': 'Your privacy', 'pt.priv1': 'Your insurer never sees a single reading', 'pt.priv2': 'Readings are signed and kept by the hospital',
    'pt.priv3': 'Only a yes/no proof reaches Stellar', 'pt.priv4': 'You can audit every payout on the explorer',
    'pol.range': 'target heart rate', 'pol.count': 'readings in range', 'pol.reward': 'per session',
    'in.eyebrow': 'Insurer', 'in.title': 'Verified adherence, without the data', 'in.lead': 'Pay only for sessions that really happened. Every payout below carries a zero-knowledge proof checked on-chain.',
    'in.table': 'Verified payments', 'in.policy': 'Your policy on-chain', 'in.never': 'What you never see',
    'in.never1': 'Heart-rate values or curves', 'in.never2': 'When exactly the patient exercised', 'in.never3': 'Device or hospital internals',
    'in.get': 'What you get', 'in.get1': 'A proof that the policy was met', 'in.get2': 'The hospital’s signature', 'in.get3': 'An immutable, public receipt',
    'in.contracts': 'Reward pools',
    'tbl.session': 'Session', 'tbl.patient': 'Patient', 'tbl.amount': 'Amount', 'tbl.when': 'When', 'tbl.proof': 'Proof', 'tbl.tx': 'Transaction',
    'tbl.zk': 'Verified', 'tbl.view': 'View', 'tbl.empty': 'No payouts found yet.',
    'notice.snapshot': 'Stellar testnet RPC is unreachable from this network. Showing confirmed transactions instead; open them on the explorer to check.',
    'time.now': 'just now', 'time.unknown': '25 Oct 2026',
  },
  es: {
    'launch.eyebrow': 'Phonendo sobre Stellar', 'launch.title': 'Elige un panel',
    'launch.lead': 'Las lecturas de los sensores las verifican y firman servicios que ejecuta el hospital. Un contrato inteligente de Stellar comprueba después una prueba de conocimiento cero de esas lecturas y paga, sin que las lecturas se publiquen nunca.',
    'launch.panels': 'Paneles', 'launch.open': 'Abrir',
    'stage.reader.t': 'Reader', 'stage.reader.p': 'Recoge lecturas de sensores',
    'stage.manager.t': 'Manager', 'stage.manager.p': 'Reparte eventos y reintenta fallos',
    'stage.verifier.t': 'Verifier', 'stage.verifier.p': 'Comprueba y firma lecturas',
    'stage.publisher.t': 'Publisher', 'stage.publisher.p': 'Crea la prueba y llama a claim()',
    'stage.contract.t': 'Contrato Stellar', 'stage.contract.p': 'Verifica la prueba y paga',
    'panel.operator.t': 'Consola del operador', 'panel.operator.p': 'Los servicios de un despliegue: mapa, comprobación de cada uno y sus archivos de configuración.',
    'panel.patient.t': 'Panel del paciente', 'panel.patient.p': 'Pagos recibidos por una cuenta Stellar, leídos de los eventos del contrato.',
    'panel.insurer.t': 'Panel de la aseguradora', 'panel.insurer.p': 'Pagos realizados por el contrato, cada uno con su transacción en el explorador.',
    'launch.note': 'Cada panel es una página independiente que no enlaza con las demás; se desplegarán como servicios separados. Los pagos se leen en directo del RPC de Stellar testnet.',
    'launch.proof': 'Transacciones reales en testnet:',
    'op.laneDesc.reader': 'Recogen datos del sensor', 'op.laneDesc.manager': 'Reparten y reintentan eventos', 'op.laneDesc.verifier': 'Comprueban y firman, guardan histórico',
    'op.laneDesc.publisher': 'Prueban y cobran', 'op.laneDesc.chain': 'Verifica y paga',
    'op.filter': 'Organización', 'op.filter.all': 'Todas', 'op.nodes': 'nodos',
    'op.live': 'Eventos del contrato', 'op.liveEmpty': 'Aún no hay eventos session_paid.', 'op.hintTitle': 'Selecciona un nodo',
    'op.configHint': 'Aquí aparece su configuración lista para usar.', 'op.how': 'Cómo viajan los datos',
    'op.how1': 'Los Readers recogen datos del sensor y los envían a un Manager.', 'op.how2': 'El Manager reparte cada evento y reintenta si falla.',
    'op.how3': 'Los Verifiers lo comprueban y firman. Storage guarda el histórico.', 'op.how4': 'El Publisher prueba la sesión y llama al contrato.',
    'op.how5': 'El contrato de Stellar verifica la prueba y paga.',
    'footer.built': 'Construido sobre Stellar testnet', 'footer.contract': 'Ver el contrato en Stellar Expert',
    'net.checking': 'Conectando con testnet…', 'net.live': 'Stellar testnet · en directo', 'net.error': 'Testnet sin conexión · copia',
    'kpi.paid': 'Pagado', 'kpi.sessions': 'Sesiones verificadas', 'kpi.patients': 'Pacientes premiados', 'kpi.last': 'Último pago',
        'kpi.earned': 'Total ganado', 'kpi.yourSessions': 'Sesiones completadas',
    'op.eyebrow': 'Consola del operador', 'op.title': 'Red', 'op.lead': 'Readers, managers, verifiers, storages y publishers del despliegue, conectados al contrato de Stellar. Añade nodos, compruébalos y exporta su configuración.',
    'op.check': 'Comprobar todo', 'op.export': 'Exportar despliegue', 'op.reset': 'Volver a la demo',
    'op.canvas': 'Mapa de la red', 'op.legend.http': 'Envío HTTP', 'op.legend.sse': 'Suscripción SSE', 'op.legend.chain': 'Transacción Stellar',
    'op.lane.reader': 'Readers', 'op.lane.manager': 'Managers', 'op.lane.verifier': 'Verifiers y storage', 'op.lane.publisher': 'Publishers', 'op.lane.chain': 'Stellar',
    'op.add': 'Añadir', 'op.summary': 'Despliegue', 'op.reachable': 'accesibles', 'op.select': 'Selecciona un nodo del mapa para ver sus datos y su configuración.',
    'op.details': 'Detalle', 'op.url': 'Dirección', 'op.org': 'Organización', 'op.status': 'Estado', 'op.template': 'Perfil', 'op.links': 'Envía a / escucha a',
    'op.config': 'Configuración', 'op.copy': 'Copiar', 'op.download': 'Descargar', 'op.remove': 'Quitar', 'op.checkOne': 'Comprobar',
    'op.tip': 'El estado es una comprobación de acceso desde tu navegador. Abre esta página en la misma máquina que los servicios para que sea más fiable.',
    'op.contractTip': 'El contrato guarda la póliza y el fondo de recompensas. Los eventos se leen en directo del RPC.',
    'op.managers': 'Managers conectados', 'op.noManagers': 'Añade primero un manager.',
    'status.up': 'Accesible', 'status.down': 'Sin acceso', 'status.checking': 'Comprobando…', 'status.unknown': 'Sin comprobar',
    'kind.reader': 'Reader', 'kind.manager': 'Manager', 'kind.verifier': 'Verifier', 'kind.storage': 'Storage', 'kind.publisher': 'Publisher',
    'kindDesc.reader': 'Recoge lecturas del sensor', 'kindDesc.manager': 'Reparte y reintenta eventos', 'kindDesc.verifier': 'Comprueba y firma lecturas',
    'kindDesc.storage': 'Guarda el histórico verificado', 'kindDesc.publisher': 'Prueba y cobra en Stellar',
    'org.hospital': 'Hospital', 'org.insurer': 'Aseguradora', 'org.lab': 'Laboratorio',
    'tpl.pulse': 'Pulso simulado', 'tpl.pulsed': 'simulation: pulse', 'tpl.temperature': 'Temperatura simulada', 'tpl.temperatured': 'simulation: temperature',
    'dlg.title': 'Añadir un nodo', 'dlg.lead': 'Aparece en el mapa con su propio archivo de configuración.', 'dlg.kind': 'Tipo', 'dlg.template': 'Perfil del sensor',
    'dlg.name': 'Nombre', 'dlg.url': 'Dirección (URL)', 'dlg.urlHelp': 'Donde escucha el servicio, p. ej. http://192.168.1.20:3002', 'dlg.urlError': 'Escribe una URL que empiece por http:// o https://',
    'dlg.cancel': 'Cancelar', 'dlg.add': 'Añadir nodo',
    'toast.added': 'Nodo añadido', 'toast.removed': 'Nodo quitado', 'toast.copied': 'Copiado al portapapeles', 'toast.reset': 'Red de demo restaurada',
    'toast.newPayout': 'Nuevo pago en Stellar', 'toast.exported': 'Despliegue exportado',
    'pt.eyebrow': 'Paciente', 'pt.title': 'Tus premios de rehabilitación', 'pt.lead': 'Cada sesión completada te paga automáticamente. Tus lecturas de pulso se quedan en tu hospital.',
    'pt.account': 'Cuenta Stellar', 'pt.view': 'Ver', 'pt.invalid': 'Una cuenta Stellar empieza por G y tiene 56 caracteres.',
    'pt.payouts': 'Tus pagos', 'pt.none': 'Esta cuenta aún no tiene pagos.',
    'pt.how': 'Cómo ganas', 'pt.how1': 'Ponte la banda de pulso durante la sesión', 'pt.how2': 'Mantén el pulso en la zona objetivo',
    'pt.how3': 'El hospital lo prueba sin compartir lecturas', 'pt.how4': 'Los USDC llegan a tu cartera',
    'pt.privacy': 'Tu privacidad', 'pt.priv1': 'Tu aseguradora nunca ve ni una lectura', 'pt.priv2': 'El hospital firma y guarda las lecturas',
    'pt.priv3': 'Solo una prueba sí/no llega a Stellar', 'pt.priv4': 'Puedes auditar cada pago en el explorador',
    'pol.range': 'pulso objetivo', 'pol.count': 'lecturas en rango', 'pol.reward': 'por sesión',
    'in.eyebrow': 'Aseguradora', 'in.title': 'Constancia verificada, sin los datos', 'in.lead': 'Paga solo por sesiones que ocurrieron de verdad. Cada pago lleva una prueba de conocimiento cero comprobada en cadena.',
    'in.table': 'Pagos verificados', 'in.policy': 'Tu póliza en cadena', 'in.never': 'Lo que nunca ves',
    'in.never1': 'Valores o curvas de pulso', 'in.never2': 'Cuándo hizo ejercicio exactamente', 'in.never3': 'Detalles internos del hospital o del dispositivo',
    'in.get': 'Lo que recibes', 'in.get1': 'Una prueba de que se cumplió la póliza', 'in.get2': 'La firma del hospital', 'in.get3': 'Un recibo público e inmutable',
    'in.contracts': 'Fondos de recompensa',
    'tbl.session': 'Sesión', 'tbl.patient': 'Paciente', 'tbl.amount': 'Importe', 'tbl.when': 'Cuándo', 'tbl.proof': 'Prueba', 'tbl.tx': 'Transacción',
    'tbl.zk': 'Verificada', 'tbl.view': 'Ver', 'tbl.empty': 'Todavía no hay pagos.',
    'notice.snapshot': 'No se puede acceder al RPC de Stellar testnet desde esta red. Se muestran transacciones ya confirmadas; ábrelas en el explorador para comprobarlas.',
    'time.now': 'ahora mismo', 'time.unknown': '25 oct 2026',
  },
};

const KINDS = ['reader', 'manager', 'verifier', 'storage', 'publisher'];
const KIND_ICON = { reader: 'cpu', manager: 'hub', verifier: 'shield', storage: 'db', publisher: 'send' };
const LANE_OF = { reader: 0, manager: 1, verifier: 2, storage: 2, publisher: 3 };
const TEMPLATES = { pulse: 'pulse', temperature: 'thermo' };
const ORGS = ['hospital', 'insurer', 'lab'];
const STORE_KEY = 'phonendo.network.v2';

// Despliegue local de deploy/docker/compose.yml.
const DEMO_NETWORK = [
  { id: 'reader-1', kind: 'reader', name: 'reader-docker', org: 'hospital', url: 'http://localhost:7101', template: 'pulse', managers: ['manager-1'] },
  { id: 'manager-1', kind: 'manager', name: 'manager', org: 'hospital', url: 'http://localhost:7102', managers: [] },
  { id: 'verifier-1', kind: 'verifier', name: 'verifier', org: 'hospital', url: 'http://localhost:7103', managers: ['manager-1'] },
  { id: 'storage-1', kind: 'storage', name: 'storage', org: 'hospital', url: 'http://localhost:7104', managers: ['manager-1'] },
  { id: 'publisher-1', kind: 'publisher', name: 'publisher', org: 'hospital', url: 'http://localhost:7105', managers: ['manager-1'] },
];

const state = {
  lang: 'en',
  net: 'checking',
  events: [],
  fresh: new Set(),
  network: loadNetwork(),
  status: {},
  selected: null,
  orgFilter: 'all',
  patient: CONFIG.demoPatient,
};

// ---------- Utilidades ----------
const $ = (sel, root = document) => root.querySelector(sel);
const t = (key) => I18N[state.lang][key] ?? I18N.en[key] ?? key;
const ic = (name, cls = 'icon') => `<svg class="${cls}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const short = (s, a = 4, b = 4) => (s && s.length > a + b + 1 ? `${s.slice(0, a)}…${s.slice(-b)}` : s || '—');
const txUrl = (hash) => `${CONFIG.explorer}/tx/${hash}`;
const isAccount = (s) => /^G[A-Z2-7]{55}$/.test(s);

function storageGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}
function storageSet(key, value) {
  try { localStorage.setItem(key, value); } catch { /* sin almacenamiento: solo se pierde la red editada */ }
}

function loadNetwork() {
  try {
    const saved = JSON.parse(storageGet(STORE_KEY));
    if (Array.isArray(saved) && saved.every((n) => KINDS.includes(n.kind))) return saved;
  } catch { /* red guardada no válida */ }
  return structuredClone(DEMO_NETWORK);
}
function saveNetwork() { storageSet(STORE_KEY, JSON.stringify(state.network)); }

function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove('show'), 2400);
}

function formatAmount(n) {
  return n.toLocaleString(state.lang, { maximumFractionDigits: 2 });
}

function timeAgo(iso) {
  if (!iso) return t('time.unknown');
  const seconds = Math.round((new Date(iso) - Date.now()) / 1000);
  if (Math.abs(seconds) < 45) return t('time.now');
  const rtf = new Intl.RelativeTimeFormat(state.lang, { numeric: 'auto' });
  const units = [['day', 86400], ['hour', 3600], ['minute', 60]];
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
  }
  return rtf.format(seconds, 'second');
}

function download(name, text) {
  const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
  const a = Object.assign(document.createElement('a'), { href: url, download: name });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast(t('toast.copied')); } catch { /* sin permiso de portapapeles */ }
}

// ---------- Stellar: eventos SessionPaid ----------
async function rpc(method, params) {
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
function parseEvent(event) {
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

async function fetchPayments() {
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

async function refresh() {
  const before = `${state.net}:${state.events.map((e) => e.id).join()}`;
  try {
    const events = await fetchPayments();
    const known = new Set(state.events.map((e) => e.id));
    const firstLoad = state.net !== 'live';
    state.fresh = new Set(firstLoad ? [] : events.filter((e) => !known.has(e.id)).map((e) => e.id));
    if (state.fresh.size) toast(`${t('toast.newPayout')} · +${formatAmount(events[0].amount)} ${events[0].asset}`);
    state.events = events;
    state.net = 'live';
  } catch (error) {
    console.warn('Phonendo: RPC no disponible', error);
    if (state.net !== 'live') { state.events = KNOWN; state.net = 'error'; }
  }
  updateNet();
  if (before === `${state.net}:${state.events.map((e) => e.id).join()}`) return;
  if (['home', 'patient', 'insurer'].includes(route()) || (route() === 'operator' && state.selected === 'contract')) render();
}

function updateNet() {
  const pill = $('#net-pill');
  pill.dataset.state = state.net;
  $('#net-label').textContent = t(`net.${state.net}`);
}

function stats(events) {
  const totals = {};
  for (const e of events) totals[e.asset] = (totals[e.asset] ?? 0) + e.amount;
  return {
    totals,
    sessions: events.length,
    patients: new Set(events.map((e) => e.patient)).size,
    last: events[0] ?? null,
  };
}

function totalsText(totals) {
  const parts = Object.entries(totals).sort(([a], [b]) => (a === 'USDC' ? -1 : b === 'USDC' ? 1 : 0));
  if (!parts.length) return `0 USDC`;
  return parts.map(([asset, amount]) => `${formatAmount(amount)} <small>${asset}</small>`).join(' · ');
}

// ---------- Componentes compartidos ----------
function kpi(label, value, sub = '', accent = false) {
  return `<div class="card kpi"><span>${label}</span><b class="${accent ? 'accent' : ''}">${value}</b>${sub ? `<small>${sub}</small>` : ''}</div>`;
}

function snapshotNotice() {
  return state.net === 'error' ? `<div class="notice">${ic('alert')}<span>${t('notice.snapshot')}</span></div>` : '';
}

function paymentsTable(events, { showPatient = true, limit = 50 } = {}) {
  if (!events.length) return `<div class="empty">${t('tbl.empty')}</div>`;
  const rows = events.slice(0, limit).map((e) => `
    <tr class="${state.fresh.has(e.id) ? 'fresh' : ''}">
      <td class="mono">${esc(e.sessionId ?? '—')}</td>
      ${showPatient ? `<td class="mono" title="${esc(e.patient)}">${esc(short(e.patient, 5, 4))}</td>` : ''}
      <td><b>+${formatAmount(e.amount)}</b> ${esc(e.asset)}</td>
      <td>${esc(timeAgo(e.paidAt))}</td>
      <td><span class="chip chip-ok">${ic('check')}${t('tbl.zk')}</span></td>
      <td><a href="${txUrl(e.txHash)}" target="_blank" rel="noopener">${esc(short(e.txHash, 6, 4))} ${ic('external', 'icon tiny')}</a></td>
    </tr>`).join('');
  return `<div class="table-scroll"><table>
    <thead><tr><th>${t('tbl.session')}</th>${showPatient ? `<th>${t('tbl.patient')}</th>` : ''}<th>${t('tbl.amount')}</th><th>${t('tbl.when')}</th><th>${t('tbl.proof')}</th><th>${t('tbl.tx')}</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

function policyTiles() {
  const p = CONFIG.policy;
  return `<div class="policy">
    <div><b>${p.min}–${p.max}</b><span>bpm · ${t('pol.range')}</span></div>
    <div><b>${p.minCount}/${p.batch}</b><span>${t('pol.count')}</span></div>
    <div><b>${p.payout} USDC</b><span>${t('pol.reward')}</span></div>
  </div>`;
}

function pageHead(prefix, extra = '') {
  return `<section class="page-head"><div class="wrap">
    <div><span class="eyebrow">${t(`${prefix}.eyebrow`)}</span><h1>${t(`${prefix}.title`)}</h1><p>${t(`${prefix}.lead`)}</p></div>
    ${extra}
  </div></section>`;
}

// ---------- Inicio ----------
function viewHome() {
  const tx = [['891b2fe1504a9d9c0a34146828e9caac9527a41e3d467eaecf5a994c145c0aa1', '5 XLM'],
    ['0ba0adb7ca42e09350f71eec15c09d252dcfacf13b6cc3672afab8017ce78033', '5 USDC'],
    ['2a345e9fdf594fc385107a2e1a2e973d3cb16f5274fc14e763bbe9dc0406ef47', '5 USDC']];
  const stages = [['cpu', 'reader'], ['hub', 'manager'], ['shield', 'verifier'], ['send', 'publisher'], ['contract', 'contract']];
  const panel = (key, icon) => `<a class="panel-card" href="${CONFIG.panels[key]}">
    <span class="panel-icon">${ic(icon)}</span>
    <h2>${t(`panel.${key}.t`)}</h2>
    <p>${t(`panel.${key}.p`)}</p>
    <span class="panel-open">${t('launch.open')} ${ic('arrow', 'icon tiny')}</span>
  </a>`;
  return `
  <section class="hero launcher"><div class="wrap">
    <span class="eyebrow">${t('launch.eyebrow')}</span>
    <h1>${t('launch.title')}</h1>
    <p class="lead">${t('launch.lead')}</p>
    <ol class="pipeline">${stages.map(([icon, key]) => `<li>${ic(icon)}<b>${t(`stage.${key}.t`)}</b><small>${t(`stage.${key}.p`)}</small></li>`).join('')}</ol>
    <h2 class="launch-h">${t('launch.panels')}</h2>
    <div class="panel-grid">
      ${panel('operator', 'hub')}${panel('patient', 'user')}${panel('insurer', 'building')}
    </div>
    <p class="launch-note">${t('launch.note')}</p>
    <div class="launch-proof">
      <b>${t('launch.proof')}</b>
      ${tx.map(([hash, label]) => `<a href="${txUrl(hash)}" target="_blank" rel="noopener">${label} · <span class="mono">${esc(short(hash, 6, 4))}</span> ${ic('external', 'icon tiny')}</a>`).join('')}
    </div>
  </div></section>`;
}

// ---------- Consola del operador ----------
function nodeById(id) { return state.network.find((n) => n.id === id); }

function nodeCard(node) {
  const status = state.status[node.id] ?? 'unknown';
  const host = node.url.replace(/^https?:\/\//, '');
  const tpl = node.kind === 'reader' && node.template ? ` · ${t(`tpl.${node.template}`)}` : '';
  const dim = state.orgFilter !== 'all' && state.orgFilter !== node.org ? ' dim' : '';
  return `<button type="button" class="node${dim}" data-node="${esc(node.id)}" aria-pressed="${state.selected === node.id}">
    <i class="status-dot" data-status="${status}" title="${esc(t(`status.${status}`))}"></i>
    <span class="node-top"><span class="node-icon">${ic(node.kind === 'reader' ? TEMPLATES[node.template] ?? 'cpu' : KIND_ICON[node.kind])}</span>
      <span><strong>${esc(node.name)}</strong><span class="node-kind">${t(`kind.${node.kind}`)}</span></span></span>
    <small class="mono">${esc(host)}${esc(tpl)}</small>
    <span class="org-tag org-${node.org}">${t(`org.${node.org}`)}</span>
  </button>`;
}

function contractCard() {
  const status = state.net === 'live' ? 'up' : state.net === 'error' ? 'down' : 'checking';
  return `<button type="button" class="node contract" data-node="contract" aria-pressed="${state.selected === 'contract'}">
    <i class="status-dot" data-status="${status}"></i>
    <span class="node-top"><span class="node-icon">${ic('contract')}</span><span><strong>adherence</strong><span class="node-kind">Soroban · testnet</span></span></span>
    <small class="mono">${short(CONFIG.contracts[0].id, 6, 6)}</small>
    <span class="org-tag org-insurer">USDC · XLM</span>
  </button>`;
}

function viewOperator() {
  const LANES = [
    { key: 'reader', kinds: ['reader'] },
    { key: 'manager', kinds: ['manager'] },
    { key: 'verifier', kinds: ['verifier', 'storage'] },
    { key: 'publisher', kinds: ['publisher'] },
  ];
  const counts = KINDS.map((k) => [k, state.network.filter((n) => n.kind === k).length]);
  const up = state.network.filter((n) => state.status[n.id] === 'up').length;
  const filters = ['all', ...ORGS].map((o) => `<button type="button" class="filter" data-org-filter="${o}" aria-pressed="${state.orgFilter === o}">${o === 'all' ? t('op.filter.all') : `<i class="org-dot org-${o}"></i>${t(`org.${o}`)}`}</button>`).join('');
  const tools = `<div class="toolbar">
    <button type="button" class="btn btn-ghost btn-sm" data-action="check-all">${ic('refresh', 'icon tiny')}${t('op.check')}</button>
    <button type="button" class="btn btn-ghost btn-sm" data-action="export">${ic('download', 'icon tiny')}${t('op.export')}</button>
    <button type="button" class="btn btn-gold btn-sm" data-action="add" data-kind="reader">${ic('plus', 'icon tiny')}${t('dlg.title')}</button>
  </div>`;
  const lane = ({ key, kinds }, i) => {
    const nodes = state.network.filter((n) => kinds.includes(n.kind));
    return `<div class="lane">
      <div class="lane-head"><span class="lane-num">${i + 1}</span><div><b>${t(`op.lane.${key}`)}</b><small>${t(`op.laneDesc.${key}`)}</small></div></div>
      ${nodes.map(nodeCard).join('')}
      ${kinds.map((k) => `<button type="button" class="lane-add" data-action="add" data-kind="${k}">${ic('plus', 'icon tiny')} ${t(`kind.${k}`)}</button>`).join('')}
    </div>`;
  };
  return `${pageHead('op', tools)}
  <section class="page-body"><div class="wrap-wide">
    <div class="card canvas-card">
      <div class="canvas-head">
        <div class="canvas-title"><h2>${t('op.canvas')}</h2>
          <div class="summary-inline">${counts.map(([k, c]) => `<span><b>${c}</b> ${t(`kind.${k}`)}</span>`).join('')}<span class="ok"><b>${up}/${state.network.length}</b> ${t('op.reachable')}</span></div></div>
        <div class="filters" role="group" aria-label="${t('op.filter')}">${filters}</div>
      </div>
      <div class="canvas-scroll"><div class="canvas" id="canvas" data-filter="${state.orgFilter}">
        <svg class="links" id="links" aria-hidden="true"></svg>
        ${LANES.map(lane).join('')}
        <div class="lane">
          <div class="lane-head"><span class="lane-num chain">5</span><div><b>${t('op.lane.chain')}</b><small>${t('op.laneDesc.chain')}</small></div></div>
          ${contractCard()}
        </div>
      </div></div>
      <div class="legend">
        <span><i class="lg-http"></i>${t('op.legend.http')}</span><span><i class="lg-sse"></i>${t('op.legend.sse')}</span><span><i class="lg-chain"></i>${t('op.legend.chain')}</span>
        <span class="legend-note">${t('op.tip')}</span>
      </div>
    </div>
    <div class="console-grid">
      ${detailPanel()}
      ${activityPanel()}
    </div>
  </div></section>`;
}

function activityPanel() {
  const items = state.events.slice(0, 5).map((e) => `
    <li class="${state.fresh.has(e.id) ? 'fresh' : ''}"><span class="feed-icon">${ic('coin')}</span>
      <span><b>+${formatAmount(e.amount)} ${esc(e.asset)}</b><small>${esc(timeAgo(e.paidAt))} · <a href="${txUrl(e.txHash)}" target="_blank" rel="noopener">${esc(short(e.txHash, 6, 4))}</a></small></span></li>`).join('');
  return `<div class="card panel feed">
    <h3>${ic('contract', 'icon tiny')}${t('op.live')} <span class="chip ${state.net === 'live' ? 'chip-ok' : 'chip-warn'}">${t(`net.${state.net}`)}</span></h3>
    ${items ? `<ul class="feed-list">${items}</ul>` : `<p class="tip">${t('op.liveEmpty')}</p>`}
    <h3 class="spaced">${ic('layers', 'icon tiny')}${t('op.how')}</h3>
    <ol class="mini-steps">${[1, 2, 3, 4, 5].map((n) => `<li>${t(`op.how${n}`)}</li>`).join('')}</ol>
  </div>`;
}

function detailPanel() {
  if (state.selected === 'contract') {
    return `<div class="detail-cols"><div class="card panel">
      <h3>${ic('contract', 'icon tiny')}adherence · Soroban</h3>
      <dl class="kv">
        ${CONFIG.contracts.map((c) => `<dt>${c.asset}</dt><dd class="mono"><a href="${CONFIG.explorer}/contract/${c.id}" target="_blank" rel="noopener">${short(c.id, 8, 6)}</a></dd>`).join('')}
        <dt>claim()</dt><dd>Groth16 BLS12-381 + ed25519</dd>
        <dt>session_paid</dt><dd>${state.events.length}</dd>
      </dl>
      <p class="tip">${t('op.contractTip')}</p>
    </div></div>`;
  }
  const node = nodeById(state.selected);
  if (!node) {
    return `<div class="detail-cols"><div class="card panel empty-panel">${ic('hub')}<h3>${t('op.hintTitle')}</h3><p>${t('op.select')}</p></div>
      <div class="card panel empty-panel">${ic('contract')}<h3>${t('op.config')}</h3><p>${t('op.configHint')}</p></div></div>`;
  }
  const status = state.status[node.id] ?? 'unknown';
  const chip = { up: 'chip-ok', down: 'chip-bad', checking: 'chip-warn', unknown: '' }[status];
  const managers = state.network.filter((n) => n.kind === 'manager');
  const links = node.kind === 'manager'
    ? ''
    : `<div class="field"><label>${t('op.managers')}</label>${managers.length
      ? `<div class="check-list">${managers.map((m) => `<label><input type="checkbox" data-link="${esc(m.id)}" ${node.managers.includes(m.id) ? 'checked' : ''}> ${esc(m.name)}</label>`).join('')}</div>`
      : `<small>${t('op.noManagers')}</small>`}</div>`;
  const config = JSON.stringify(configFor(node), null, 2);
  return `<div class="detail-cols"><div class="card panel">
    <h3>${ic(KIND_ICON[node.kind], 'icon tiny')}${esc(node.name)}</h3>
    <dl class="kv">
      <dt>${t('op.status')}</dt><dd><span class="chip ${chip}">${t(`status.${status}`)}</span></dd>
      <dt>${t('op.url')}</dt><dd class="mono">${esc(node.url)}</dd>
      <dt>${t('op.org')}</dt><dd><select data-field="org" aria-label="${t('op.org')}">${ORGS.map((o) => `<option value="${o}" ${o === node.org ? 'selected' : ''}>${t(`org.${o}`)}</option>`).join('')}</select></dd>
      ${node.kind === 'reader' ? `<dt>${t('op.template')}</dt><dd>${t(`tpl.${node.template}`)}</dd>` : ''}
    </dl>
    ${links}
    <div class="panel-actions">
      <button type="button" class="btn btn-line btn-sm" data-action="check" data-id="${esc(node.id)}">${ic('refresh', 'icon tiny')}${t('op.checkOne')}</button>
      <button type="button" class="btn btn-danger btn-sm" data-action="remove" data-id="${esc(node.id)}">${ic('trash', 'icon tiny')}${t('op.remove')}</button>
    </div>
  </div>
  <div class="card panel">
    <h3>${ic('contract', 'icon tiny')}${t('op.config')} <span class="mono muted">${esc(configName(node))}</span></h3>
    <pre class="code">${esc(config)}</pre>
    <div class="panel-actions">
      <button type="button" class="btn btn-dark btn-sm" data-action="copy-config" data-id="${esc(node.id)}">${ic('copy', 'icon tiny')}${t('op.copy')}</button>
      <button type="button" class="btn btn-line btn-sm" data-action="download-config" data-id="${esc(node.id)}">${ic('download', 'icon tiny')}${t('op.download')}</button>
    </div>
  </div></div>`;
}

function portOf(url, fallback) {
  try { return Number(new URL(url).port) || fallback; } catch { return fallback; }
}

function slug(text) {
  return text.toLowerCase().normalize('NFD').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'node';
}

function configName(node) {
  return node.kind === 'publisher' ? 'config.json' : `${node.kind}-${slug(node.name)}.json`;
}

// Mismo formato que deploy/docker/*.json y apps/publisher/config.json.
function configFor(node) {
  const urls = (ids) => ids.map(nodeById).filter(Boolean).map((n) => n.url);
  const linked = (kind) => state.network.filter((n) => n.kind === kind && n.managers.includes(node.id)).map((n) => n.url);
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

// Los servicios no envían cabeceras CORS: una petición no-cors solo dice si el servidor responde.
async function checkNode(node) {
  state.status[node.id] = 'checking';
  paintStatus(node.id);
  const path = node.kind === 'reader' ? '/health' : node.kind === 'publisher' ? '/info' : '/';
  try {
    await fetch(node.url.replace(/\/$/, '') + path, { mode: 'no-cors', cache: 'no-store', signal: AbortSignal.timeout(3000) });
    state.status[node.id] = 'up';
  } catch {
    state.status[node.id] = 'down';
  }
  if (route() === 'operator') render();
}

function paintStatus(id) {
  const dot = document.querySelector(`[data-node="${CSS.escape(id)}"] .status-dot`);
  if (dot) dot.dataset.status = state.status[id];
}

function checkAll() { state.network.forEach(checkNode); }

// Dibuja las conexiones entre tarjetas a partir de su posición real en pantalla.
// Un punto recorre cada enlace cuyo origen responde (o la cadena, si el RPC está en directo).
function drawLinks() {
  const canvas = $('#canvas');
  const svg = $('#links');
  if (!canvas || !svg) return;
  const box = canvas.getBoundingClientRect();
  const anchor = (id, side) => {
    const el = canvas.querySelector(`[data-node="${CSS.escape(id)}"]`);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: (side === 'out' ? r.right : r.left) - box.left, y: r.top + r.height / 2 - box.top };
  };
  const edges = [];
  for (const node of state.network) {
    for (const managerId of node.managers) {
    if (node.kind === 'reader') {
      const config = typeof operatorState !== 'undefined' ? operatorState.readers[node.id]?.config : null;
      if (!config || config.httpEnabled) edges.push([node.id, managerId, 'http']);
      else if (config.streamEnabled) edges.push([node.id, managerId, 'sse']);
    }
      else if (node.kind === 'publisher') edges.push([managerId, node.id, 'sse']);
      else edges.push([managerId, node.id, 'http']);
    }
    if (node.kind === 'publisher') edges.push([node.id, 'contract', 'chain']);
  }
  svg.setAttribute('viewBox', `0 0 ${box.width} ${box.height}`);
  svg.innerHTML = edges.map(([from, to, type]) => {
    const a = anchor(from, 'out');
    const b = anchor(to, 'in');
    if (!a || !b) return '';
    const bend = Math.max(30, (b.x - a.x) / 2);
    const d = `M${a.x},${a.y} C${a.x + bend},${a.y} ${b.x - bend},${b.y} ${b.x},${b.y}`;
    const active = typeof operatorState !== 'undefined' && Date.now() - ((type === 'chain' ? operatorState.paid[from] : operatorState.active[from]) || 0) < 6000;
    const dot = active ? `<circle r="3.6" class="${type}"><animateMotion dur="${type === 'chain' ? 2.4 : 1.8}s" repeatCount="indefinite" path="${d}"/></circle>` : '';
    return `<path class="${type}" d="${d}"/>${dot}`;
  }).join('');
}

function nodeDialog(kind) {
  const dialog = $('#node-dialog');
  const managers = state.network.filter((n) => n.kind === 'manager');
  const draft = { kind, template: 'pulse' };
  const defaults = { reader: 3002, manager: 3003, verifier: 5000, storage: 5000, publisher: 3005 };
  const paint = () => {
    const count = state.network.filter((n) => n.kind === draft.kind).length + 1;
    dialog.innerHTML = `<form method="dialog" novalidate>
      <div class="dialog-head"><h2 id="node-dialog-title">${t('dlg.title')}</h2><p>${t('dlg.lead')}</p></div>
      <div class="dialog-body">
        <div class="field"><label>${t('dlg.kind')}</label><div class="choice-grid kinds">
          ${KINDS.map((k) => `<button type="button" class="choice" data-kind="${k}" aria-pressed="${k === draft.kind}">${ic(KIND_ICON[k])}<b>${t(`kind.${k}`)}</b><span>${t(`kindDesc.${k}`)}</span></button>`).join('')}
        </div></div>
        ${draft.kind === 'reader' ? `<div class="field"><label>${t('dlg.template')}</label><div class="choice-grid">
          ${Object.keys(TEMPLATES).map((k) => `<button type="button" class="choice" data-template="${k}" aria-pressed="${k === draft.template}">${ic(TEMPLATES[k])}<b>${t(`tpl.${k}`)}</b><span>${t(`tpl.${k}d`)}</span></button>`).join('')}
        </div></div>` : ''}
        <div class="field-row">
          <div class="field"><label for="f-name">${t('dlg.name')}</label><input id="f-name" required value="${esc(`${draft.kind}-${count}`)}"></div>
          <div class="field"><label for="f-org">${t('op.org')}</label><select id="f-org">${ORGS.map((o) => `<option value="${o}">${t(`org.${o}`)}</option>`).join('')}</select></div>
        </div>
        <div class="field"><label for="f-url">${t('dlg.url')}</label><input id="f-url" inputmode="url" value="http://localhost:${defaults[draft.kind]}"><small id="f-url-help">${t('dlg.urlHelp')}</small></div>
        ${draft.kind !== 'manager' ? `<div class="field"><label>${t('op.managers')}</label>${managers.length
          ? `<div class="check-list">${managers.map((m, i) => `<label><input type="checkbox" name="manager" value="${esc(m.id)}" ${i === 0 ? 'checked' : ''}> ${esc(m.name)}</label>`).join('')}</div>`
          : `<small>${t('op.noManagers')}</small>`}</div>` : ''}
      </div>
      <div class="dialog-foot">
        <button type="button" class="btn btn-line" data-close>${t('dlg.cancel')}</button>
        <button type="submit" class="btn btn-dark">${ic('plus', 'icon tiny')}${t('dlg.add')}</button>
      </div>
    </form>`;
  };
  paint();
  dialog.onclick = (event) => {
    const choice = event.target.closest('[data-kind],[data-template]');
    if (choice?.dataset.kind) { draft.kind = choice.dataset.kind; paint(); }
    else if (choice?.dataset.template) { draft.template = choice.dataset.template; paint(); }
    else if (event.target.closest('[data-close]') || event.target === dialog) dialog.close();
  };
  dialog.onsubmit = (event) => {
    event.preventDefault();
    const name = $('#f-name', dialog).value.trim();
    const url = $('#f-url', dialog).value.trim();
    if (!/^https?:\/\/[^\s/]+/.test(url)) {
      const help = $('#f-url-help', dialog);
      help.textContent = t('dlg.urlError');
      help.classList.add('error');
      $('#f-url', dialog).focus();
      return;
    }
    const node = {
      id: `${draft.kind}-${Date.now().toString(36)}`,
      kind: draft.kind,
      name: name || t(`kind.${draft.kind}`),
      org: $('#f-org', dialog).value,
      url,
      managers: [...dialog.querySelectorAll('input[name=manager]:checked')].map((i) => i.value),
    };
    if (draft.kind === 'reader') node.template = draft.template;
    state.network.push(node);
    state.selected = node.id;
    saveNetwork();
    dialog.close();
    render();
    toast(t('toast.added'));
    checkNode(node);
  };
  dialog.showModal();
}

function onOperatorClick(event) {
  const filter = event.target.closest('[data-org-filter]');
  if (filter) {
    state.orgFilter = filter.dataset.orgFilter;
    render();
    return;
  }
  const nodeEl = event.target.closest('[data-node]');
  if (nodeEl) {
    state.selected = nodeEl.dataset.node;
    render();
    return;
  }
  const button = event.target.closest('[data-action]');
  if (!button) return;
  const node = nodeById(button.dataset.id);
  switch (button.dataset.action) {
    case 'add': nodeDialog(button.dataset.kind); break;
    case 'check-all': checkAll(); break;
    case 'check': if (node) checkNode(node); break;
    case 'remove':
      state.network = state.network.filter((n) => n.id !== node.id);
      state.network.forEach((n) => { n.managers = n.managers.filter((id) => id !== node.id); });
      state.selected = null;
      saveNetwork();
      render();
      toast(t('toast.removed'));
      break;
    case 'copy-config': copy(JSON.stringify(configFor(node), null, 2)); break;
    case 'download-config': download(configName(node), JSON.stringify(configFor(node), null, 2)); break;
    case 'export': {
      const configs = Object.fromEntries(state.network.map((n) => [n.id, { file: configName(n), config: configFor(n) }]));
      download('phonendo-deployment.json', JSON.stringify({ network: state.network, configs }, null, 2));
      toast(t('toast.exported'));
      break;
    }
    case 'reset':
      state.network = structuredClone(DEMO_NETWORK);
      state.selected = null;
      state.status = {};
      saveNetwork();
      render();
      toast(t('toast.reset'));
      checkAll();
      break;
  }
}

function onOperatorChange(event) {
  const node = nodeById(state.selected);
  if (!node) return;
  if (event.target.dataset.field === 'org') node.org = event.target.value;
  if (event.target.dataset.link) {
    const id = event.target.dataset.link;
    node.managers = event.target.checked ? [...new Set([...node.managers, id])] : node.managers.filter((m) => m !== id);
  }
  saveNetwork();
  render();
}

// ---------- Paciente ----------
function viewPatient() {
  const mine = state.events.filter((e) => e.patient === state.patient);
  const s = stats(mine);
  const form = `<form class="account-box" id="patient-form">
    <label class="sr-only" for="patient-account">${t('pt.account')}</label>
    <input id="patient-account" value="${esc(state.patient)}" spellcheck="false" autocomplete="off">
    <button class="btn btn-gold btn-sm" type="submit">${t('pt.view')}</button>
  </form>`;
  return `${pageHead('pt', `<div class="account-wrap"><span class="eyebrow">${t('pt.account')}</span>${form}<small id="patient-error" class="form-error" hidden>${t('pt.invalid')}</small></div>`)}
  <section class="page-body"><div class="wrap">
    ${snapshotNotice()}
    <div class="kpi-row">
      ${kpi(t('kpi.earned'), totalsText(s.totals), '', true)}
      ${kpi(t('kpi.yourSessions'), s.sessions)}
      ${kpi(t('kpi.last'), s.last ? esc(timeAgo(s.last.paidAt)) : '—')}
      ${kpi(t('pt.account'), `<span class="mono">${esc(short(state.patient, 5, 4))}</span>`)}
    </div>
    <div class="two-col">
      <div class="card table-card">
        <div class="table-head"><h2>${t('pt.payouts')}</h2><span class="chip chip-info">${ic('star', 'icon tiny')}Stellar</span></div>
        ${mine.length ? paymentsTable(mine, { showPatient: false }) : `<div class="empty">${t('pt.none')}</div>`}
      </div>
      <div class="side">
        <div class="card panel">
          <h3>${ic('coin', 'icon tiny')}${t('pt.how')}</h3>
          ${policyTiles()}
          <ol class="mini-steps">${[1, 2, 3, 4].map((n) => `<li>${t(`pt.how${n}`)}</li>`).join('')}</ol>
        </div>
        <div class="card panel">
          <h3>${ic('shield', 'icon tiny')}${t('pt.privacy')}</h3>
          <ul class="privacy-list">${[1, 2, 3, 4].map((n) => `<li>${ic(n === 1 ? 'eye-off' : 'check', `icon ${n === 1 ? 'no' : 'yes'}`)}<span>${t(`pt.priv${n}`)}</span></li>`).join('')}</ul>
        </div>
      </div>
    </div>
  </div></section>`;
}

function onPatientSubmit(event) {
  if (event.target.id !== 'patient-form') return;
  event.preventDefault();
  const value = $('#patient-account').value.trim();
  if (!isAccount(value)) { $('#patient-error').hidden = false; return; }
  state.patient = value;
  render();
}

// ---------- Aseguradora ----------
function viewInsurer() {
  const s = stats(state.events);
  return `${pageHead('in')}
  <section class="page-body"><div class="wrap">
    ${snapshotNotice()}
    <div class="kpi-row">
      ${kpi(t('kpi.paid'), totalsText(s.totals), '', true)}
      ${kpi(t('kpi.sessions'), s.sessions)}
      ${kpi(t('kpi.patients'), s.patients)}
      ${kpi(t('kpi.last'), s.last ? esc(timeAgo(s.last.paidAt)) : '—')}
    </div>
    <div class="two-col">
      <div class="card table-card">
        <div class="table-head"><h2>${t('in.table')}</h2><span class="chip ${state.net === 'live' ? 'chip-ok' : 'chip-warn'}">${t(`net.${state.net}`)}</span></div>
        ${paymentsTable(state.events)}
      </div>
      <div class="side">
        <div class="card panel"><h3>${ic('contract', 'icon tiny')}${t('in.policy')}</h3>${policyTiles()}</div>
        <div class="card panel">
          <h3>${ic('eye-off', 'icon tiny')}${t('in.never')}</h3>
          <ul class="privacy-list">${[1, 2, 3].map((n) => `<li>${ic('x', 'icon no')}<span>${t(`in.never${n}`)}</span></li>`).join('')}</ul>
          <h3 class="spaced">${ic('shield', 'icon tiny')}${t('in.get')}</h3>
          <ul class="privacy-list">${[1, 2, 3].map((n) => `<li>${ic('check', 'icon yes')}<span>${t(`in.get${n}`)}</span></li>`).join('')}</ul>
        </div>
        <div class="card panel">
          <h3>${ic('coin', 'icon tiny')}${t('in.contracts')}</h3>
          <dl class="kv">${CONFIG.contracts.map((c) => `<dt>${c.asset}</dt><dd class="mono"><a href="${CONFIG.explorer}/contract/${c.id}" target="_blank" rel="noopener">${short(c.id, 8, 6)}</a></dd>`).join('')}</dl>
        </div>
      </div>
    </div>
  </div></section>`;
}

// ---------- Navegación ----------
const VIEWS = { home: viewHome, operator: viewOperator, patient: viewPatient, insurer: viewInsurer };

// Cada página HTML declara su panel en <body data-panel>: no hay navegación entre paneles.
function route() {
  const name = document.body.dataset.panel;
  return VIEWS[name] ? name : 'home';
}

function render() {
  const scroll = window.scrollY;
  $('#app').innerHTML = VIEWS[route()]();
  window.scrollTo(0, scroll);
  if (route() === 'operator') requestAnimationFrame(drawLinks);
}

function applyLang(lang) {
  state.lang = lang;
  storageSet('phonendo.lang', lang);
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll('[data-lang]').forEach((b) => b.setAttribute('aria-pressed', b.dataset.lang === lang));
  updateNet();
  render();
}

function init() {
  const app = $('#app');
  app.addEventListener('click', (e) => { if (route() === 'operator') onOperatorClick(e); });
  app.addEventListener('change', (e) => { if (route() === 'operator') onOperatorChange(e); });
  app.addEventListener('submit', onPatientSubmit);
  document.querySelectorAll('[data-lang]').forEach((b) => b.addEventListener('click', () => applyLang(b.dataset.lang)));
  window.addEventListener('resize', () => { if (route() === 'operator') drawLinks(); });
  applyLang(storageGet('phonendo.lang') === 'es' ? 'es' : 'en');
  if (route() === 'home') $('#net-pill').hidden = true;
  else {
    refresh();
    setInterval(refresh, CONFIG.refreshMs);
  }
}

init();
