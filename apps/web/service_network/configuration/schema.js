/** Campos que consumen los componentes reales; los desconocidos se conservan en el modelo. */
const field = (path, es, en, type = 'text', extra = {}) => ({ path: path.split('.'), label: [es, en], type, ...extra });
const toggle = (path, es, en, fallback = false) => field(path, es, en, 'boolean', { fallback });
const number = (path, es, en, fallback, min = 1, extra = {}) => field(path, es, en, 'number', { fallback, min, step: 1, ...extra });
const destinations = (path, es, en) => field(path, es, en, 'destinations');
const section = (id, es, en, fields, open = false) => ({ id, label: [es, en], fields, open });
const mapping = (path, es, en, keyLabels, columns) => field(path, es, en, 'mapping', { keyLabels, columns });

export function configurationSchema(kind, { liveReader = false, managed = false, environment = {} } = {}) {
  const server = section('server', 'Servidor', 'Server', [
    field('server.host', 'Host de escucha', 'Listen host', 'text', { fallback: '0.0.0.0', readonly: managed }),
    number('server.port', 'Puerto interno', 'Internal port', {reader:3002,manager:3003,verifier:5000,storage:5000,publisher:3005}[kind], 1, { max: 65535, readonly: managed }),
  ]);
  let sections;
  if (kind === 'reader' && liveReader) return [
    section('reader', 'Reader', 'Reader', [field('readerId', 'Identidad del Reader', 'Reader identity', 'text', { readonly: true })], true),
    section('connections', 'Conexiones', 'Connections', [
      toggle('httpEnabled', 'Enviar por HTTP', 'Send over HTTP', true),
      toggle('streamEnabled', 'Permitir suscripciones SSE', 'Allow SSE subscriptions', true),
      destinations('managers', 'Managers de destino', 'Destination Managers'),
    ], true),
    section('access', 'Acceso y comportamiento', 'Access & behavior', [
      field('token', 'Token del Reader', 'Reader token', 'password', { hint: ['Vacío conserva el token actual.', 'Leave empty to keep the current token.'] }),
      number('queueSize', 'Capacidad de la cola SSE', 'SSE queue capacity', 256, 1, { max: 4096 }),
      toggle('allowNewDevices', 'Aceptar dispositivos nuevos al ingerir', 'Accept new devices on ingest', true),
      toggle('allowNewSensors', 'Aceptar sensores nuevos al ingerir', 'Accept new sensors on ingest', true),
    ]),
  ];
  if (kind === 'reader') sections = [
    section('reader', 'Identidad', 'Identity', [field('readerId', 'Identidad del Reader', 'Reader identity', 'text', { required: true })], true),
    section('connections', 'Conexiones', 'Connections', [toggle('stream.enabled', 'Publicar por SSE', 'Publish over SSE', true), destinations('services.managers', 'Managers HTTP', 'HTTP Managers')], true),
    section('access', 'Acceso', 'Access', [field('server.token', 'Token del Reader', 'Reader token', 'password')]), server,
  ];
  if (kind === 'manager') sections = [
    section('identity', 'Identidad', 'Identity', [field('managerId', 'Identidad del Manager', 'Manager identity')], true),
    section('destinations', 'Destinos HTTP', 'HTTP destinations', [destinations('services.verifiers', 'Verificadores', 'Verifiers'), destinations('services.storages', 'Almacenamiento', 'Storage')], true),
    section('stream', 'Streaming y suscripciones', 'Streaming & subscriptions', [
      toggle('stream.enabled', 'Stream para Publishers', 'Stream for Publishers'),
      toggle('outputStreams.verifiers', 'Stream de salida para Verifiers', 'Output stream for Verifiers'),
      toggle('outputStreams.storages', 'Stream de salida para Storage', 'Output stream for Storage'),
      destinations('subscriptions.readers', 'Suscribirse a Readers', 'Subscribe to Readers'),
      destinations('subscriptions.verifiers', 'Suscribirse a Verifiers', 'Subscribe to Verifiers'),
      destinations('subscriptions.storages', 'Suscribirse a Storage', 'Subscribe to Storage'),
    ]),
    section('queue', 'Cola y reintentos', 'Queue & retries', [number('httpTimeoutSeconds', 'Timeout HTTP (segundos)', 'HTTP timeout (seconds)', 10, .1, { step: .1 }), number('queue.size', 'Eventos pendientes máximos', 'Maximum pending events', 1000), number('queue.retryIntervalSeconds', 'Reintento cada (segundos)', 'Retry every (seconds)', 5, .1, { step: .1 })]), server,
  ];
  if (kind === 'verifier' || kind === 'storage') sections = [
    section('connections', 'Conexiones', 'Connections', [toggle('stream.enabled', 'Publicar resultados por SSE', 'Publish results over SSE', true), field('server.publicUrl', 'URL pública del servicio', 'Public service URL', 'url'), destinations('subscriptions.managers', 'Suscribirse a Managers por SSE', 'Subscribe to Managers over SSE')], true),
    section('data', kind === 'verifier' ? 'Firma' : 'Almacenamiento', kind === 'verifier' ? 'Signing' : 'Storage', [kind === 'verifier'
      ? field('keyPath', 'Archivo de clave del Verifier', 'Verifier key file', 'text', { fallback: '/keys/verifier.json', readonly: managed })
      : field('databasePath', 'Ruta de la base de datos', 'Database path', 'text', { fallback: '/data/phonendo', readonly: managed })]), server,
  ];
  if (kind === 'publisher') sections = [
    section('connections', 'Managers', 'Managers', [destinations('subscriptions.managers', 'Managers de origen (SSE)', 'Source Managers (SSE)'), field('signer.manager', 'Manager para firma (opcional)', 'Signing Manager (optional)', 'url')], true),
    section('policy', 'Política de publicación', 'Publication policy', [
      number('batchSize', 'Lecturas por lote', 'Readings per batch', 32, 32, { max: 32, readonly: managed, hint: ['El circuito actual trabaja con 32 lecturas.', 'The current circuit uses 32 readings.'] }),
      number('policy.minValue', 'Valor mínimo', 'Minimum value', 90, 0, { max: 255 }),
      number('policy.maxValue', 'Valor máximo', 'Maximum value', 130, 0, { max: 255 }),
      number('policy.minCount', 'Lecturas que deben cumplir', 'Required matching readings', 28, 1, { max: 32 }),
    ], true),
    section('contracts', 'Contratos por Verifier', 'Contracts by Verifier', [mapping('contracts', 'Verificadores autorizados', 'Authorized Verifiers', ['Clave pública del Verifier', 'Verifier public key'], [field('value', 'Contrato Stellar', 'Stellar contract')])]),
    section('patients', 'Beneficiarios', 'Beneficiaries', [mapping('patients', 'Cuenta por dispositivo', 'Account by device', ['Dispositivo (default = resto)', 'Device (default = fallback)'], [field('value', 'Cuenta Stellar G…', 'Stellar account G…')])]),
    section('devices', 'Políticas por dispositivo', 'Device policies', [mapping('devices', 'Excepciones por dispositivo', 'Device overrides', ['Dispositivo', 'Device'], [field('contractId', 'Contrato Stellar', 'Stellar contract'), number('policy.minValue', 'Mínimo (opcional)', 'Minimum (optional)', undefined, 0, {max:255}), number('policy.maxValue', 'Máximo (opcional)', 'Maximum (optional)', undefined, 0, {max:255}), number('policy.minCount', 'Lecturas requeridas (opcional)', 'Required readings (optional)', undefined, 1, {max:32})])]),
    section('stellar', 'Stellar', 'Stellar', [field('stellar.source', 'Alias de la cuenta que envía', 'Submitting account alias'), field('stellar.network', 'Red', 'Network'), field('circuitsPath', 'Ruta de los circuitos', 'Circuits path', 'text', {readonly:managed,fallback:'/circuits'})]), server,
  ];
  const overrides = {managerId:'MANAGER_ID',httpTimeoutSeconds:'MANAGER_HTTP_TIMEOUT_SECONDS','queue.size':'MANAGER_QUEUE_SIZE','queue.retryIntervalSeconds':'MANAGER_RETRY_INTERVAL_SECONDS','databasePath':'PHONENDO_DB_PATH','stellar.source':'PUBLISHER_STELLAR_SOURCE'};
  if (kind === 'verifier') overrides['server.publicUrl'] = 'VERIFIER_PUBLIC_URL';
  if (kind === 'storage') overrides['server.publicUrl'] = 'STORAGE_PUBLIC_URL';
  return (sections || [server]).map((group) => ({...group,fields:group.fields.map((item)=>{
    const variable=overrides[item.path.join('.')];
    return variable && Object.hasOwn(environment,variable) ? {...item,readonly:true,hint:[`Fijado por ${variable}.`,`Set by ${variable}.`]} : item;
  })}));
}
