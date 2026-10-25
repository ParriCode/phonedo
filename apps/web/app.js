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
    'launch.eyebrow': 'Choose your panel', 'launch.title': 'Verifiable sensor data, <em>without exposing the data</em>',
    'launch.lead': 'Phonendo connects sensors to Stellar through hospital-controlled services and zero-knowledge proofs. Pick a panel to start.',
    'launch.op.tag': 'Main panel', 'launch.op.t': 'Operator console',
    'launch.op.p': 'Design, check and export the whole sensor network of your organisation: readers, managers, verifiers, storage and publishers, wired to the Stellar contract.',
    'launch.op.b1': 'Add any number of nodes, per organisation', 'launch.op.b2': 'Live reachability check of every service', 'launch.op.b3': 'Download ready-to-run configuration files',
    'launch.op.btn': 'Open the console',
    'launch.uc.eyebrow': 'Use case', 'launch.uc.t': 'Cardiac rehabilitation', 'launch.uc.p': 'Two independent views of the same payout.',
    'launch.pt.t': 'Patient panel', 'launch.pt.p': 'Rewards received for completed sessions.',
    'launch.in.t': 'Insurer panel', 'launch.in.p': 'Verified payments, without health data.', 'launch.open': 'Open',
    'op.laneDesc.reader': 'Collect sensor data', 'op.laneDesc.manager': 'Route and retry events', 'op.laneDesc.verifier': 'Check and sign, keep history',
    'op.laneDesc.publisher': 'Prove and claim', 'op.laneDesc.chain': 'Verify and pay',
    'op.filter': 'Organisation', 'op.filter.all': 'All', 'op.nodes': 'nodes',
    'op.live': 'On-chain activity', 'op.liveEmpty': 'No payouts yet.', 'op.hintTitle': 'Select a node',
    'op.configHint': 'Its ready-to-run configuration appears here.', 'op.how': 'How data flows',
    'op.how1': 'Readers collect sensor data and push it to a Manager.', 'op.how2': 'The Manager routes each event and retries on failure.',
    'op.how3': 'Verifiers check and sign it. Storage keeps the history.', 'op.how4': 'The Publisher proves the session and calls the contract.',
    'op.how5': 'The Stellar contract verifies the proof and pays.',
    'nav.home': 'Panels', 'nav.operator': 'Operator console', 'nav.patient': 'Patient', 'nav.insurer': 'Insurer',
    'footer.built': 'Built on Stellar testnet', 'footer.contract': 'View the contract on Stellar Expert',
    'net.checking': 'Connecting to testnet…', 'net.live': 'Stellar testnet · live', 'net.error': 'Testnet unreachable · snapshot',
    'hero.eyebrow': 'Proof of care on Stellar',
    'hero.title': 'Rewards for real recovery. <em>Zero</em> health data exposed.',
    'hero.lead': 'Phonendo turns a heart sensor into a private, verifiable proof that a patient completed their cardiac rehab session, and pays them in USDC on Stellar. The insurer gets the proof. The readings never leave the hospital.',
    'hero.cta1': 'See live payouts', 'hero.cta2': 'Open the operator console',
    'hero.p1': 'Groth16 proofs on BLS12-381', 'hero.p2': 'ed25519-signed readings', 'hero.p3': 'Live on Stellar testnet',
    'flow.private': 'Heart rate · private', 'flow.stays': 'Stays inside the hospital', 'flow.chain': 'On Stellar', 'flow.verified': 'Proof verified',
    'flow.s1': 'readings in range', 'flow.s2': 'readings on-chain', 'flow.s3': 'per session',
    'problem.eyebrow': 'The problem', 'problem.title': 'Cardiac rehab works. Patients just don’t finish it.',
    'problem.lead': 'Payers would gladly reward adherence, but proving it today means handing over raw health data or trusting a self-report.',
    'problem.1t': 'Patients drop out', 'problem.1p': 'Sessions are long, repetitive and unrewarded. Motivation fades after the first weeks.',
    'problem.2t': 'Privacy blocks incentives', 'problem.2p': 'Sending heart-rate streams to an insurer is a GDPR and trust problem nobody wants.',
    'problem.3t': 'Nothing is verifiable', 'problem.3p': 'Self-reported attendance can’t be audited, and a paper form can’t pay anyone.',
    'how.eyebrow': 'How it works', 'how.title': 'From heartbeat to payout in five steps',
    'how.lead': 'Every step runs on infrastructure the hospital controls, until a single proof reaches Stellar.',
    'how.1t': 'Sense', 'how.1p': 'A pulse band streams heart rate to the hospital’s Reader.',
    'how.2t': 'Sign', 'how.2p': 'The Verifier checks every reading and signs the batch with ed25519.',
    'how.3t': 'Prove', 'how.3p': 'A zero-knowledge proof shows 28 of 32 readings were within 90–130 bpm, revealing none of them.',
    'how.4t': 'Verify', 'how.4p': 'The Soroban contract checks the Groth16 proof and the hospital signature on-chain.',
    'how.5t': 'Pay', 'how.5p': 'The contract pays the patient 5 USDC and emits a public SessionPaid event.',
    'ledger.eyebrow': 'Privacy by design', 'ledger.title': 'What goes on-chain, and what never does',
    'ledger.on': 'Public on Stellar', 'ledger.off': 'Never leaves the hospital',
    'ledger.on1': 'A yes/no proof that the session met the policy', 'ledger.on2': 'The session id, so it can never be paid twice',
    'ledger.on3': 'The payout and the patient’s wallet address', 'ledger.on4': 'The policy: heart-rate range, minimum readings, reward',
    'ledger.off1': 'Every single heart-rate reading', 'ledger.off2': 'Device identifiers and exact timestamps',
    'ledger.off3': 'Medical history and diagnosis', 'ledger.off4': 'Anything linking the wallet to a real identity',
    'stellar.eyebrow': 'Why Stellar', 'stellar.title': 'Native cryptography, real dollars, public audit trail',
    'stellar.1p': 'Groth16 proofs are verified natively in the contract with the BLS12-381 pairing host function.',
    'stellar.1t': 'Zero-knowledge on-chain',
    'stellar.2t': 'Hospital signature', 'stellar.2p': 'The contract proves the batch came from the hospital’s Verifier key.',
    'stellar.3t': 'Pays real USDC', 'stellar.3p': 'Payouts go through the USDC Stellar Asset Contract, settled in seconds for a fraction of a cent.',
    'stellar.4t': 'Anti-replay', 'stellar.4p': 'Each paid session id is stored on-chain: the same proof can never pay twice.',
    'stellar.5t': 'Auditable events', 'stellar.5p': 'Every payout emits session_paid. This website reads them live from the RPC.',
    'stellar.6t': 'Transparent policy', 'stellar.6p': 'Range, minimum count and reward are stored by the payer and visible to everyone.',
    'live.eyebrow': 'Live on testnet', 'live.title': 'Real payouts, read straight from the ledger',
    'live.lead': 'No database in between: these numbers come from the contract events on Stellar testnet.',
    'live.all': 'Open the insurer view',
    'kpi.paid': 'Paid out', 'kpi.sessions': 'Verified sessions', 'kpi.patients': 'Patients rewarded', 'kpi.last': 'Last payout',
    'kpi.readings': 'Readings disclosed', 'kpi.readingsSub': 'the insurer never sees them',
    'kpi.earned': 'Total earned', 'kpi.yourSessions': 'Sessions completed', 'kpi.onchain': 'Your data on-chain', 'kpi.onchainSub': 'only proofs and payouts',
    'cases.eyebrow': 'Use cases', 'cases.title': 'One private-proof engine, many payers',
    'cases.live': 'Live demo', 'cases.next': 'Next',
    'case1.t': 'Cardiac rehab adherence', 'case1.p': 'An insurer rewards patients who actually complete supervised exercise sessions.',
    'case2.t': 'Cold-chain compliance', 'case2.p': 'A distributor releases payment only if vaccines stayed between 2 and 8 °C the whole trip.',
    'case.signal': 'Signal', 'case.rule': 'Rule', 'case.payer': 'Payer', 'case.reward': 'Reward',
    'case1.signal': 'Heart rate (pulse band)', 'case1.rule': '28 of 32 readings in 90–130 bpm', 'case1.payer': 'Health insurer', 'case1.reward': '5 USDC per session',
    'case2.signal': 'Temperature (DHT11)', 'case2.rule': 'All readings in 2–8 °C', 'case2.payer': 'Pharma distributor', 'case2.reward': 'Payment on delivery',
    'cta.title': 'Deploy Phonendo in your hospital', 'cta.lead': 'Add readers, verifiers and publishers for every organisation, export ready-to-run configs, and start paying for verified care.',
    'cta.btn': 'Design your network',
    'op.eyebrow': 'Operator console', 'op.title': 'Hospital network', 'op.lead': 'Add as many readers, managers, verifiers, storages and publishers as you need, give each one to an organisation, and export ready-to-run configuration.',
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
    'tpl.esp32': 'ESP32 pulse band', 'tpl.esp32d': 'Real heart-rate sensor', 'tpl.pulse': 'Simulated pulse', 'tpl.pulsed': 'For demos and tests',
    'tpl.dht11': 'DHT11 cold chain', 'tpl.dht11d': 'Temperature sensor',
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
    'launch.eyebrow': 'Elige tu panel', 'launch.title': 'Datos de sensores verificables, <em>sin exponer los datos</em>',
    'launch.lead': 'Phonendo conecta sensores con Stellar mediante servicios que controla el hospital y pruebas de conocimiento cero. Elige un panel para empezar.',
    'launch.op.tag': 'Panel principal', 'launch.op.t': 'Consola del operador',
    'launch.op.p': 'Diseña, comprueba y exporta toda la red de sensores de tu organización: readers, managers, verifiers, storage y publishers, conectados al contrato de Stellar.',
    'launch.op.b1': 'Añade tantos nodos como quieras, por organización', 'launch.op.b2': 'Comprobación en vivo de cada servicio', 'launch.op.b3': 'Descarga las configuraciones listas para usar',
    'launch.op.btn': 'Abrir la consola',
    'launch.uc.eyebrow': 'Caso de uso', 'launch.uc.t': 'Rehabilitación cardíaca', 'launch.uc.p': 'Dos vistas independientes del mismo pago.',
    'launch.pt.t': 'Panel del paciente', 'launch.pt.p': 'Premios recibidos por las sesiones completadas.',
    'launch.in.t': 'Panel de la aseguradora', 'launch.in.p': 'Pagos verificados, sin datos de salud.', 'launch.open': 'Abrir',
    'op.laneDesc.reader': 'Recogen datos del sensor', 'op.laneDesc.manager': 'Reparten y reintentan eventos', 'op.laneDesc.verifier': 'Comprueban y firman, guardan histórico',
    'op.laneDesc.publisher': 'Prueban y cobran', 'op.laneDesc.chain': 'Verifica y paga',
    'op.filter': 'Organización', 'op.filter.all': 'Todas', 'op.nodes': 'nodos',
    'op.live': 'Actividad en cadena', 'op.liveEmpty': 'Aún no hay pagos.', 'op.hintTitle': 'Selecciona un nodo',
    'op.configHint': 'Aquí aparece su configuración lista para usar.', 'op.how': 'Cómo viajan los datos',
    'op.how1': 'Los Readers recogen datos del sensor y los envían a un Manager.', 'op.how2': 'El Manager reparte cada evento y reintenta si falla.',
    'op.how3': 'Los Verifiers lo comprueban y firman. Storage guarda el histórico.', 'op.how4': 'El Publisher prueba la sesión y llama al contrato.',
    'op.how5': 'El contrato de Stellar verifica la prueba y paga.',
    'nav.home': 'Paneles', 'nav.operator': 'Consola del operador', 'nav.patient': 'Paciente', 'nav.insurer': 'Aseguradora',
    'footer.built': 'Construido sobre Stellar testnet', 'footer.contract': 'Ver el contrato en Stellar Expert',
    'net.checking': 'Conectando con testnet…', 'net.live': 'Stellar testnet · en directo', 'net.error': 'Testnet sin conexión · copia',
    'hero.eyebrow': 'Prueba de cuidado en Stellar',
    'hero.title': 'Premios por recuperarte de verdad. <em>Cero</em> datos de salud expuestos.',
    'hero.lead': 'Phonendo convierte un sensor cardíaco en una prueba privada y verificable de que el paciente completó su sesión de rehabilitación cardíaca, y le paga en USDC sobre Stellar. La aseguradora recibe la prueba. Las lecturas nunca salen del hospital.',
    'hero.cta1': 'Ver pagos en directo', 'hero.cta2': 'Abrir la consola del operador',
    'hero.p1': 'Pruebas Groth16 sobre BLS12-381', 'hero.p2': 'Lecturas firmadas con ed25519', 'hero.p3': 'En directo en Stellar testnet',
    'flow.private': 'Pulso · privado', 'flow.stays': 'Se queda en el hospital', 'flow.chain': 'En Stellar', 'flow.verified': 'Prueba verificada',
    'flow.s1': 'lecturas en rango', 'flow.s2': 'lecturas en cadena', 'flow.s3': 'por sesión',
    'problem.eyebrow': 'El problema', 'problem.title': 'La rehabilitación cardíaca funciona. Pero los pacientes la abandonan.',
    'problem.lead': 'Las aseguradoras premiarían la constancia, pero hoy demostrarla exige entregar datos de salud en bruto o fiarse de lo que dice el paciente.',
    'problem.1t': 'Los pacientes abandonan', 'problem.1p': 'Las sesiones son largas, repetitivas y sin recompensa. La motivación cae tras las primeras semanas.',
    'problem.2t': 'La privacidad frena los incentivos', 'problem.2p': 'Enviar el pulso a una aseguradora es un problema de RGPD y de confianza.',
    'problem.3t': 'Nada es verificable', 'problem.3p': 'La asistencia declarada no se puede auditar, y un formulario en papel no paga a nadie.',
    'how.eyebrow': 'Cómo funciona', 'how.title': 'Del latido al pago en cinco pasos',
    'how.lead': 'Todo ocurre en infraestructura que controla el hospital, hasta que una única prueba llega a Stellar.',
    'how.1t': 'Medir', 'how.1p': 'Una banda de pulso envía la frecuencia cardíaca al Reader del hospital.',
    'how.2t': 'Firmar', 'how.2p': 'El Verifier comprueba cada lectura y firma el lote con ed25519.',
    'how.3t': 'Probar', 'how.3p': 'Una prueba de conocimiento cero demuestra que 28 de 32 lecturas estaban entre 90 y 130 lpm, sin revelar ninguna.',
    'how.4t': 'Verificar', 'how.4p': 'El contrato Soroban comprueba en cadena la prueba Groth16 y la firma del hospital.',
    'how.5t': 'Pagar', 'how.5p': 'El contrato paga 5 USDC al paciente y emite un evento público SessionPaid.',
    'ledger.eyebrow': 'Privacidad desde el diseño', 'ledger.title': 'Qué va a la cadena y qué nunca sale',
    'ledger.on': 'Público en Stellar', 'ledger.off': 'Nunca sale del hospital',
    'ledger.on1': 'Una prueba sí/no de que la sesión cumple la póliza', 'ledger.on2': 'El id de sesión, para que nunca se pague dos veces',
    'ledger.on3': 'El pago y la dirección de la cartera del paciente', 'ledger.on4': 'La póliza: rango de pulso, lecturas mínimas, recompensa',
    'ledger.off1': 'Cada una de las lecturas de pulso', 'ledger.off2': 'Identificadores del dispositivo y horas exactas',
    'ledger.off3': 'Historial médico y diagnóstico', 'ledger.off4': 'Cualquier vínculo entre la cartera y una identidad real',
    'stellar.eyebrow': 'Por qué Stellar', 'stellar.title': 'Criptografía nativa, dólares reales y auditoría pública',
    'stellar.1t': 'Conocimiento cero en cadena', 'stellar.1p': 'Las pruebas Groth16 se verifican dentro del contrato con la función nativa de emparejamiento BLS12-381.',
    'stellar.2t': 'Firma del hospital', 'stellar.2p': 'El contrato comprueba que el lote viene de la clave del Verifier del hospital.',
    'stellar.3t': 'Paga USDC reales', 'stellar.3p': 'Los pagos usan el contrato del activo USDC de Stellar: segundos y fracciones de céntimo.',
    'stellar.4t': 'Sin pagos repetidos', 'stellar.4p': 'Cada sesión pagada se guarda en cadena: la misma prueba nunca cobra dos veces.',
    'stellar.5t': 'Eventos auditables', 'stellar.5p': 'Cada pago emite session_paid. Esta web los lee en directo del RPC.',
    'stellar.6t': 'Póliza transparente', 'stellar.6p': 'El rango, el mínimo y la recompensa los fija el pagador y cualquiera puede verlos.',
    'live.eyebrow': 'En directo en testnet', 'live.title': 'Pagos reales, leídos directamente del ledger',
    'live.lead': 'Sin base de datos intermedia: estas cifras salen de los eventos del contrato en Stellar testnet.',
    'live.all': 'Abrir la vista de aseguradora',
    'kpi.paid': 'Pagado', 'kpi.sessions': 'Sesiones verificadas', 'kpi.patients': 'Pacientes premiados', 'kpi.last': 'Último pago',
    'kpi.readings': 'Lecturas reveladas', 'kpi.readingsSub': 'la aseguradora nunca las ve',
    'kpi.earned': 'Total ganado', 'kpi.yourSessions': 'Sesiones completadas', 'kpi.onchain': 'Tus datos en cadena', 'kpi.onchainSub': 'solo pruebas y pagos',
    'cases.eyebrow': 'Casos de uso', 'cases.title': 'Un motor de pruebas privadas, muchos pagadores',
    'cases.live': 'Demo en directo', 'cases.next': 'Siguiente',
    'case1.t': 'Constancia en rehabilitación cardíaca', 'case1.p': 'Una aseguradora premia a los pacientes que completan de verdad sus sesiones de ejercicio supervisado.',
    'case2.t': 'Cadena de frío', 'case2.p': 'Un distribuidor solo libera el pago si las vacunas se mantuvieron entre 2 y 8 °C todo el viaje.',
    'case.signal': 'Señal', 'case.rule': 'Regla', 'case.payer': 'Pagador', 'case.reward': 'Recompensa',
    'case1.signal': 'Pulso (banda)', 'case1.rule': '28 de 32 lecturas entre 90 y 130 lpm', 'case1.payer': 'Aseguradora de salud', 'case1.reward': '5 USDC por sesión',
    'case2.signal': 'Temperatura (DHT11)', 'case2.rule': 'Todas las lecturas entre 2 y 8 °C', 'case2.payer': 'Distribuidor farmacéutico', 'case2.reward': 'Pago a la entrega',
    'cta.title': 'Despliega Phonendo en tu hospital', 'cta.lead': 'Añade readers, verifiers y publishers para cada organización, exporta configuraciones listas para arrancar y empieza a pagar por cuidados verificados.',
    'cta.btn': 'Diseña tu red',
    'op.eyebrow': 'Consola del operador', 'op.title': 'Red del hospital', 'op.lead': 'Añade todos los readers, managers, verifiers, storages y publishers que necesites, asígnalos a una organización y exporta su configuración lista para usar.',
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
    'tpl.esp32': 'Banda de pulso ESP32', 'tpl.esp32d': 'Sensor cardíaco real', 'tpl.pulse': 'Pulso simulado', 'tpl.pulsed': 'Para demos y pruebas',
    'tpl.dht11': 'Cadena de frío DHT11', 'tpl.dht11d': 'Sensor de temperatura',
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
const TEMPLATES = { esp32: 'heart', pulse: 'pulse', dht11: 'thermo' };
const ORGS = ['hospital', 'insurer', 'lab'];
const STORE_KEY = 'phonendo.network.v1';

const DEMO_NETWORK = [
  { id: 'reader-1', kind: 'reader', name: 'Rehab band 1', org: 'hospital', url: 'http://localhost:7101', template: 'pulse', managers: ['manager-1'] },
  { id: 'manager-1', kind: 'manager', name: 'Hospital manager', org: 'hospital', url: 'http://localhost:7102', managers: [] },
  { id: 'verifier-1', kind: 'verifier', name: 'Hospital verifier', org: 'hospital', url: 'http://localhost:7103', managers: ['manager-1'] },
  { id: 'storage-1', kind: 'storage', name: 'Clinical storage', org: 'hospital', url: 'http://localhost:7104', managers: ['manager-1'] },
  { id: 'publisher-1', kind: 'publisher', name: 'Rehab publisher', org: 'hospital', url: 'http://localhost:3005', managers: ['manager-1'] },
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
// Esquema fijo de la red para la portada: reader, manager, verifier/storage, publisher y contrato.
function miniNetwork() {
  const boxes = [['cpu', 'Reader', 14, 56], ['hub', 'Manager', 112, 56], ['shield', 'Verifier', 210, 22], ['db', 'Storage', 210, 90], ['send', 'Publisher', 308, 56], ['contract', 'Stellar', 406, 56]];
  const edges = [[0, 1], [1, 2], [1, 3], [1, 4], [4, 5]];
  const at = (i, side) => [boxes[i][2] + (side ? 82 : 0), boxes[i][3] + 20];
  return `<svg class="mini-net" viewBox="0 0 500 160" aria-hidden="true">
    ${edges.map(([f, t2], i) => { const [x1, y1] = at(f, 1); const [x2, y2] = at(t2, 0); const m = (x1 + x2) / 2; const d = `M${x1},${y1} C${m},${y1} ${m},${y2} ${x2},${y2}`;
      return `<path d="${d}" class="${t2 === 5 ? 'chain' : ''}"/><circle r="3.2" class="${t2 === 5 ? 'chain' : ''}"><animateMotion dur="${2 + i * 0.4}s" repeatCount="indefinite" path="${d}"/></circle>`; }).join('')}
    ${boxes.map(([icon, label, x, y], i) => `<g transform="translate(${x} ${y})"><rect width="82" height="40" rx="9" class="${i === 5 ? 'contract' : ''}"/><text x="41" y="25" text-anchor="middle">${label}</text></g>`).join('')}
  </svg>`;
}

function viewHome() {
  const s = stats(state.events);
  const steps = [['heart', 1], ['shield', 2], ['lock', 3], ['contract', 4], ['coin', 5]];
  const features = [
    ['bls12_381.pairing_check', 1], ['ed25519_verify', 2], ['token::Client · USDC SAC', 3],
    ['storage().persistent()', 4], ['events: session_paid', 5], ['set_policy()', 6],
  ];
  return `
  <section class="hero launcher"><div class="wrap">
    <span class="eyebrow">${t('launch.eyebrow')}</span>
    <h1>${t('launch.title')}</h1>
    <p class="lead">${t('launch.lead')}</p>
    <div class="launch-grid">
      <a class="launch-main" href="#/operator">
        <div class="launch-main-top"><span class="chip chip-hot">${ic('star', 'icon tiny')}${t('launch.op.tag')}</span></div>
        <div class="launch-main-body">
          <div>
            <h2>${t('launch.op.t')}</h2>
            <p>${t('launch.op.p')}</p>
            <ul class="tick-list">${[1, 2, 3].map((n) => `<li>${ic('check')}${t(`launch.op.b${n}`)}</li>`).join('')}</ul>
            <span class="btn btn-gold">${t('launch.op.btn')} ${ic('arrow')}</span>
          </div>
          ${miniNetwork()}
        </div>
      </a>
      <div class="launch-side">
        <div class="launch-uc-head"><span class="eyebrow">${t('launch.uc.eyebrow')}</span><b>${t('launch.uc.t')}</b><small>${t('launch.uc.p')}</small></div>
        <a class="launch-small" href="#/patient">${ic('user')}<span><b>${t('launch.pt.t')}</b><small>${t('launch.pt.p')}</small></span><em>${t('launch.open')} ${ic('arrow', 'icon tiny')}</em></a>
        <a class="launch-small" href="#/insurer">${ic('building')}<span><b>${t('launch.in.t')}</b><small>${t('launch.in.p')}</small></span><em>${t('launch.open')} ${ic('arrow', 'icon tiny')}</em></a>
      </div>
    </div>
  </div></section>

  <section class="section"><div class="wrap">
    <div class="section-head"><span class="eyebrow dark">${t('problem.eyebrow')}</span><h2>${t('problem.title')}</h2><p>${t('problem.lead')}</p></div>
    <div class="problem-grid">
      ${[['clock', 'coral'], ['eye', 'gold'], ['alert', 'sky']].map(([icon, tone], i) => `
        <article class="card problem"><div class="badge tone-${tone}">${ic(icon)}</div><h3>${t(`problem.${i + 1}t`)}</h3><p>${t(`problem.${i + 1}p`)}</p></article>`).join('')}
    </div>
  </div></section>

  <section class="section dark" id="how"><div class="wrap">
    <div class="section-head"><span class="eyebrow">${t('how.eyebrow')}</span><h2>${t('how.title')}</h2><p>${t('how.lead')}</p></div>
    <div class="steps">
      ${steps.map(([icon, n]) => `<article class="step">${ic(icon)}<h3>${t(`how.${n}t`)}</h3><p>${t(`how.${n}p`)}</p></article>`).join('')}
    </div>
  </div></section>

  <section class="section alt"><div class="wrap">
    <div class="section-head"><span class="eyebrow dark">${t('ledger.eyebrow')}</span><h2>${t('ledger.title')}</h2></div>
    <div class="split">
      <div class="card ledger-col onchain"><h3>${ic('star')}${t('ledger.on')}</h3><ul>
        ${[1, 2, 3, 4].map((n) => `<li>${ic('check')}<span>${t(`ledger.on${n}`)}</span></li>`).join('')}
      </ul></div>
      <div class="card ledger-col offchain"><h3>${ic('building')}${t('ledger.off')}</h3><ul>
        ${[1, 2, 3, 4].map((n) => `<li>${ic('eye-off')}<span>${t(`ledger.off${n}`)}</span></li>`).join('')}
      </ul></div>
    </div>
  </div></section>

  <section class="section"><div class="wrap">
    <div class="section-head"><span class="eyebrow dark">${t('stellar.eyebrow')}</span><h2>${t('stellar.title')}</h2></div>
    <div class="stellar-grid">
      ${features.map(([code, n]) => `<article class="card feature"><code>${esc(code)}</code><h3>${t(`stellar.${n}t`)}</h3><p>${t(`stellar.${n}p`)}</p></article>`).join('')}
    </div>
  </div></section>

  <section class="section alt"><div class="wrap">
    <div class="section-head"><span class="eyebrow dark">${t('live.eyebrow')}</span><h2>${t('live.title')}</h2><p>${t('live.lead')}</p></div>
    ${snapshotNotice()}
    <div class="live-strip">
      ${kpi(t('kpi.paid'), totalsText(s.totals), '', true)}
      ${kpi(t('kpi.sessions'), s.sessions)}
      ${kpi(t('kpi.patients'), s.patients)}
      ${kpi(t('kpi.readings'), '0', t('kpi.readingsSub'))}
    </div>
    <div class="card table-card">
      <div class="table-head"><h2>${t('in.table')}</h2><a class="btn btn-line btn-sm" href="#/insurer">${t('live.all')} ${ic('arrow', 'icon tiny')}</a></div>
      ${paymentsTable(state.events, { limit: 5 })}
    </div>
  </div></section>

  <section class="section"><div class="wrap">
    <div class="section-head"><span class="eyebrow dark">${t('cases.eyebrow')}</span><h2>${t('cases.title')}</h2></div>
    <div class="cases">
      ${[[1, 'heart', 'chip-ok', 'cases.live'], [2, 'thermo', 'chip-info', 'cases.next']].map(([n, icon, chip, label]) => `
        <article class="card case">
          <div class="case-top"><div class="node-icon big">${ic(icon)}</div><span class="chip ${chip}">${t(label)}</span></div>
          <h3>${t(`case${n}.t`)}</h3><p>${t(`case${n}.p`)}</p>
          <dl>${['signal', 'rule', 'payer', 'reward'].map((k) => `<dt>${t(`case.${k}`)}</dt><dd>${t(`case${n}.${k}`)}</dd>`).join('')}</dl>
        </article>`).join('')}
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
        <dt>${t('in.policy')}</dt><dd>${CONFIG.policy.min}–${CONFIG.policy.max} bpm · ${CONFIG.policy.minCount}/${CONFIG.policy.batch} · ${CONFIG.policy.payout}</dd>
        <dt>${t('kpi.sessions')}</dt><dd>${state.events.length}</dd>
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
      if (node.template === 'dht11') config.simulation = 'temperature';
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
      if (node.kind === 'reader') edges.push([node.id, managerId, 'http']);
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
    const active = type === 'chain' ? state.net === 'live' && state.status[from] === 'up' : state.status[from] === 'up';
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
          <div class="field"><label for="f-name">${t('dlg.name')}</label><input id="f-name" required value="${esc(`${t(`kind.${draft.kind}`)} ${count}`)}"></div>
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
      ${kpi(t('kpi.onchain'), '0', t('kpi.onchainSub'))}
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
      ${kpi(t('kpi.readings'), '0', t('kpi.readingsSub'))}
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

function route() {
  const name = location.hash.replace(/^#\/?/, '').split('/')[0];
  return VIEWS[name] ? name : 'home';
}

let lastRoute = null;
function render() {
  const name = route();
  const app = $('#app');
  const scroll = window.scrollY;
  app.innerHTML = VIEWS[name]();
  document.querySelectorAll('[data-route]').forEach((a) => {
    if (a.dataset.route === name) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
  if (name === lastRoute) window.scrollTo(0, scroll);
  else { window.scrollTo(0, 0); lastRoute = name; }
  if (name === 'operator') requestAnimationFrame(drawLinks);
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
  const menu = $('#menu-toggle');
  menu.addEventListener('click', () => {
    const open = $('#nav').classList.toggle('open');
    menu.setAttribute('aria-expanded', open);
  });
  window.addEventListener('hashchange', () => { $('#nav').classList.remove('open'); render(); });
  window.addEventListener('resize', () => { if (route() === 'operator') drawLinks(); });
  applyLang(storageGet('phonendo.lang') === 'es' ? 'es' : 'en');
  refresh();
  setInterval(refresh, CONFIG.refreshMs);
  checkAll();
}

init();
