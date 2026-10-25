/* Consola local. Las acciones confirmadas vienen de /api/local, nunca de una simulación visual. */
import { connectServiceNetwork } from './service_network/index.js';
import { requestLocal } from './service_network/api.js';
import { renderServiceDetails, renderContainerControls } from './service_network/sidebar.js';

const operatorState = {
  readers: {}, containers: {}, logs: [], seen: {}, cursors: {}, busy: false, bridge: null,
  active: {}, paid: {}, stage: 'all', tokens: new Map(), errors: {}, polling: false,
  stored: new Set(),
};
const opText = (es, en) => state.lang === 'es' ? es : en;
const STAGES = [
  ['reader', 'cpu', 'Captura', 'Capture'], ['manager', 'hub', 'Coordinación', 'Routing'],
  ['verifier', 'shield', 'Verificación', 'Verification'], ['storage', 'db', 'Guardado', 'Storage'],
  ['publisher', 'send', 'Prueba y publicación', 'Proof & publication'],
];

async function localAPI(path, body, method = 'POST') {
  const result = await requestLocal(path, body, method);
  operatorState.bridge = true;
  return result;
}

function appendOperatorLog(node, message, fields = {}) {
  operatorState.logs.unshift({ id: crypto.randomUUID(), node: node.id, name: node.name, kind: node.kind, message, ...fields });
  operatorState.logs.length = Math.min(operatorState.logs.length, 300);
  if (!fields.historical && /observation|event_|batch_|session_|verified|accepted/.test(message)) operatorState.active[node.id] = Date.now();
  if (!fields.historical && message === 'publisher_session_paid') operatorState.paid[node.id] = Date.now();
}

function acceptReader(node, snapshot) {
  const restarted = operatorState.readers[node.id]?.bootId !== snapshot.bootId;
  operatorState.readers[node.id] = snapshot;
  const cursor = restarted ? 0 : operatorState.cursors[node.id] || 0;
  for (const event of snapshot.events) {
    if (event.sequence > cursor) appendOperatorLog(node, event.message, { detail: event });
  }
  operatorState.cursors[node.id] = snapshot.events.at(-1)?.sequence || cursor;
  node.url = snapshot.url;
  state.status[node.id] = 'up';
}

async function readerCommand(node, body) {
  const snapshot = await localAPI('readers/' + encodeURIComponent(node.id), body);
  acceptReader(node, snapshot);
  saveNetwork();
  return snapshot;
}

function acceptContainer(node, snapshot) {
  operatorState.containers[node.id] = snapshot;
  node.dockerUrl = snapshot.dockerUrl;
  node.image = snapshot.image;
  node.url = snapshot.url;
  if (node.kind === 'reader' && snapshot.config) acceptReader(node, snapshot);
  else delete operatorState.readers[node.id];
  state.status[node.id] = snapshot.state === 'running' && !snapshot.error ? 'up' : 'down';
}

async function dockerOperation(operation) {
  while (operation.state === 'running') {
    const progress = $('#op-deploy-progress');
    if (progress) progress.textContent = operation.message;
    await new Promise((resolve) => setTimeout(resolve, 1000));
    operation = await localAPI('operations/' + operation.id, undefined, 'GET');
  }
  if (operation.state !== 'succeeded') throw new Error(operation.error || 'Error de Docker');
  return operation.result;
}

const inspectorContext = () => ({ state, operatorState, nodeById, opText, ic, esc, t, configFor, field });
function containerControls(node) { return renderContainerControls(node, inspectorContext()); }

function field(label, key, value = '', type = 'text', extra = '') {
  return `<label class="op-field"><span>${esc(label)}</span><input name="${key}" type="${type}" value="${esc(value)}" ${extra}></label>`;
}

function lifecyclePanel() {
  return `<div class="lifecycle" aria-label="${opText('Ciclo de vida de los datos', 'Data lifecycle')}">${STAGES.map(([kind, icon, es, en], index) => {
    const active = state.network.some((node) => node.kind === kind && Date.now() - (operatorState.active[node.id] || 0) < 6000);
    return `<button class="life-stage ${active ? 'is-active' : ''}" data-stage="${kind}" aria-pressed="${operatorState.stage === kind}">
      <span class="life-icon">${ic(icon)}</span><small>0${index + 1}</small><b>${state.lang === 'es' ? es : en}</b>
      <span>${active ? opText('Actividad reciente', 'Recent activity') : opText('En espera', 'Waiting')}</span></button>`;
  }).join('')}</div>`;
}

viewOperator = function () {
  return `<section class="page-body operator-body"><div class="wrap-wide">
    <div data-service-network-root></div>
    ${operatorLogs()}<section class="card panel operator-contracts"><div class="op-section-title"><h2>${opText('Contratos', 'Contracts')}</h2><span class="chip">${t('net.' + state.net)}</span></div>
      <div class="contract-grid">${CONFIG.contracts.map((contract) => `<a class="contract-tile" href="${CONFIG.explorer}/contract/${esc(contract.id)}" target="_blank" rel="noopener">${ic('contract')}<b>${esc(contract.asset)} · adherence</b><span class="mono">${esc(short(contract.id, 12, 8))}</span>${ic('external')}</a>`).join('')}</div>
      ${state.events.length ? `<ul class="feed-list">${state.events.slice(0,4).map((event)=>`<li>${ic('check')}<span><b>${formatAmount(event.amount)} ${esc(event.asset)}</b><small><a href="${txUrl(event.txHash)}" target="_blank" rel="noopener">${esc(short(event.txHash,10,6))}</a></small></span></li>`).join('')}</ul>` : `<p class="op-caption">${opText('Sin pagos nuevos.', 'No new payouts.')}</p>`}
      ${state.net==='error'?`<p class="op-caption">${opText('Explorador sin conexión: se muestran pagos históricos conocidos.', 'Explorer offline: showing known historical payouts.')}</p>`:''}</section>
  </div></section>`;
};

function operatorDetail() { return renderServiceDetails(inspectorContext()); }

function operatorLogs() {
  const logs = operatorState.logs.filter((log) => operatorState.stage === 'all' || log.kind === operatorState.stage);
  return `<section class="card operator-log-panel"><div class="op-section-title panel"><h2>${opText('Actividad y logs', 'Activity & logs')} <span class="live-indicator"></span></h2>
    <div class="toolbar"><select id="op-log-filter" aria-label="${opText('Filtrar logs', 'Filter logs')}"><option value="all">${opText('Todos los servicios', 'All services')}</option>${KINDS.map((kind) => `<option value="${kind}" ${operatorState.stage === kind ? 'selected' : ''}>${t('kind.' + kind)}</option>`).join('')}</select><button class="btn btn-line btn-sm" data-op="clear-logs">${opText('Limpiar vista', 'Clear view')}</button></div></div>
    <div class="activity-summary">${lifecyclePanel()}${observationJourney()}</div>
    <div class="op-terminal" role="log" aria-label="${opText('Últimos mensajes de los servicios', 'Latest service messages')}">${logs.map((log) => `<div class="log-row ${/failed|rejected|unreachable|error/.test(log.message) ? 'log-error' : ''}"><span class="log-kind">${esc(log.kind)}</span><b>${esc(log.name)}</b><code>${esc(log.message)}</code>${log.detail ? `<details class="log-detail"><summary>${opText('Detalle', 'Details')}</summary><small>${esc(Object.entries(log.detail).filter(([key]) => !['sequence', 'message'].includes(key)).map(([key, value]) => `${key}=${value}`).join(' · '))}</small></details>` : ''}</div>`).join('') || `<div class="log-empty">${ic('pulse')}<h3>${opText('Esperando actividad', 'Waiting for activity')}</h3><p>${opText('Despliega un Reader y emite su primer pulso.', 'Deploy a Reader and send its first pulse.')}</p></div>`}</div></section>`;
}

function observationJourney() {
  const created = operatorState.logs.filter((log) => log.message === 'observation_created').slice(0, 4);
  if (!created.length) return '';
  return `<section class="journeys"><h3>${opText('Últimas observaciones', 'Latest observations')}</h3>${created.map((log) => {
    const id = log.detail.observationId;
    const related = operatorState.logs.filter((item) => item.detail?.observationId === id);
    const done = [true, related.some((item) => item.message === 'manager_http_accepted'),
      related.some((item) => item.message === 'manager_reports_verified' || item.message === 'storage_observation_confirmed'),
      related.some((item) => item.message === 'storage_observation_confirmed'), false];
    return `<div class="journey-row"><div><b>${esc(log.detail.value)} <small>${esc(log.detail.sensorId)}</small></b><span class="mono" title="${esc(id)}">${esc(short(id, 6, 4))}</span></div><ol>${STAGES.map(([kind]) => `<li class="${done[STAGES.findIndex((item) => item[0] === kind)] ? 'confirmed' : ''}"><i></i><span>${t('kind.' + kind)}</span></li>`).join('')}</ol></div>`;
  }).join('')}<p class="op-caption">${opText('Verde = confirmado por una respuesta o registro real. Gris = aún sin evidencia. El pago se confirma abajo con los eventos de Stellar.', 'Green = confirmed by a real response or record. Grey = no evidence yet. Payouts are confirmed below using Stellar events.')}</p></section>`;
}

function dockerEndpoint(node) {
  return node.dockerUrl || node.url.replace(/localhost|127\.0\.0\.1/, 'host.docker.internal');
}

function dockerDefaultConfig(kind, name) {
  const server = { host: '0.0.0.0', port: { reader:3002, manager:3003, verifier:5000, storage:5000, publisher:3005 }[kind] };
  const managers = state.network.filter((node) => node.kind === 'manager' && node.managed).map(dockerEndpoint);
  if (kind === 'reader') return { server:{...server,enabled:true}, readerId:name, services:{managers:managers.slice(0,1).map((url)=>({url,token:''}))}, stream:{enabled:false} };
  if (kind === 'manager') return { server,managerId:name,services:{verifiers:state.network.filter((node)=>node.kind==='verifier' && node.managed).map(dockerEndpoint),storages:state.network.filter((node)=>node.kind==='storage' && node.managed).map(dockerEndpoint)},stream:{enabled:true},subscriptions:{readers:[],verifiers:[],storages:[]},outputStreams:{verifiers:true,storages:true} };
  if (kind === 'publisher') return { server,subscriptions:{managers:managers.slice(0,1)},contracts:{},batchSize:32,policy:{minValue:90,maxValue:130,minCount:28},patients:{default:CONFIG.demoPatient},circuitsPath:'/circuits',stellar:{source:'phonendo',network:'testnet'} };
  return { server,services:{},subscriptions:{managers:[]},stream:{enabled:true} };
}

function syncDockerLinks(node, config) {
  const targets = [...(config.services?.managers || []), ...(config.subscriptions?.managers || []), ...(config.webSettings?.managers || [])].map((target)=>typeof target==='string'?target:target.url);
  node.managers = state.network.filter((item)=>item.kind==='manager' && targets.includes(dockerEndpoint(item))).map((item)=>item.id);
  if (node.kind === 'manager') {
    const peers = [...(config.services?.verifiers || []), ...(config.services?.storages || [])].map((target)=>typeof target==='string'?target:target.url);
    state.network.filter((item)=>peers.includes(dockerEndpoint(item))).forEach((item)=>{item.managers=[...new Set([...item.managers,node.id])];});
  }
}

nodeDialog = function (kind) {
  const dialog = $('#node-dialog');
  const name = `${kind}-${Date.now().toString(36)}`;
  const paint = () => {
    const config = dockerDefaultConfig(kind, name);
    dialog.innerHTML = `<form data-op-form="deploy-container" data-kind="${kind}"><div class="dialog-head"><span class="eyebrow">DOCKER / DEPLOY</span><h2 id="node-dialog-title">${opText('Desplegar contenedor', 'Deploy container')}</h2><p>${opText('Imagen, puertos y configuración propios. Los contenedores siguen ejecutándose al cerrar la web.', 'Choose image, ports and configuration. Containers keep running when the web closes.')}</p></div><div class="dialog-body">
      <div class="choice-grid kinds">${KINDS.map((item)=>`<button type="button" class="choice" data-deploy-kind="${item}" aria-pressed="${item===kind}">${ic(KIND_ICON[item])}<b>${t('kind.'+item)}</b></button>`).join('')}</div>
      ${field(opText('Nombre Docker', 'Docker name'), 'name', name, 'text', 'required pattern="[a-z][a-z0-9-]{0,62}"')}
      ${field(opText('Imagen / tag', 'Image / tag'), 'image', `phonendo-web-${kind}:local`, 'text', 'required')}
      <label class="check-line"><input type="checkbox" name="build" checked>${opText('Construir desde el Dockerfile del repositorio con este tag', 'Build from the repository Dockerfile with this tag')}</label>
      <p class="op-caption">${opText('Desmarca para usar una imagen existente o descargarla. Debe ser compatible con el servicio Phonendo seleccionado.', 'Uncheck to use an existing image or pull it. The image must support the selected Phonendo service.')}</p>
      <div class="field-row">${field(opText('Puerto local (0 = libre)', 'Host port (0 = automatic)'), 'port', 0, 'number', 'min="0" max="65535" required')}${field(opText('Puerto del contenedor', 'Container port'), 'containerPort', config.server.port, 'number', 'min="1" max="65535" required')}</div>
      <label class="op-field"><span>config.json</span><textarea name="config" rows="13" spellcheck="false" required>${esc(JSON.stringify(config,null,2))}</textarea></label>
      <p class="op-caption">${opText('Dentro de Docker usa la dirección Docker de cada servicio. Para servicios del equipo: host.docker.internal. Los tokens comunes del panel se inyectan automáticamente.', 'Inside Docker use each service Docker address. For host services use host.docker.internal. Shared panel tokens are injected automatically.')}</p>
      <details><summary>${opText('Variables de entorno y tokens', 'Environment variables & tokens')}</summary><label class="op-field"><span>JSON · API_TOKEN_MANAGER / API_TOKEN_VERIFIER / MANAGER_PASSWORD…</span><textarea name="environment" rows="5" spellcheck="false">{}</textarea></label></details>
      ${kind==='publisher'?`<label class="check-line"><input type="checkbox" name="stellarIdentity">${opText('Montar mi configuración local de Stellar (solo lectura)', 'Mount my local Stellar configuration (read-only)')}</label>`:''}
      <p class="op-caption" id="op-deploy-progress" role="status"></p><p class="form-error" id="op-dialog-error" role="alert"></p></div><div class="dialog-foot"><button class="btn btn-line" type="button" data-op="close-dialog">${t('dlg.cancel')}</button><button class="btn btn-gold" type="submit">${opText('Desplegar Docker', 'Deploy Docker')}</button></div></form>`;
  };
  paint();
  dialog.onclick = (event) => {
    if (operatorState.busy) return;
    const choice=event.target.closest('[data-deploy-kind]');
    if(choice){kind=choice.dataset.deployKind;nodeDialog(kind);return;}
    if(event.target.closest('[data-op="close-dialog"]'))dialog.close();
  };
  dialog.oncancel=(event)=>{if(operatorState.busy)event.preventDefault();};
  dialog.onsubmit = onOperatorForm;
  if(!dialog.open)dialog.showModal();
};

async function onOperatorForm(event) {
  const form = event.target.closest('[data-op-form]');
  if (!form) return;
  event.preventDefault();
  if (operatorState.busy) return;
  operatorState.busy = true;
  const submit = event.submitter;
  if (submit) submit.disabled = true;
  const data = Object.fromEntries(new FormData(form));
  const node = nodeById(form.dataset.id);
  try {
    switch (form.dataset.opForm) {
      case 'deploy-container': {
        const identifier = crypto.randomUUID();
        const config = JSON.parse(data.config);
        const body={ id:identifier,kind:form.dataset.kind,name:data.name,image:data.image,port:Number(data.port),containerPort:Number(data.containerPort),build:data.build==='on',config,environment:JSON.parse(data.environment),stellarIdentity:data.stellarIdentity==='on' };
        const snapshot = await dockerOperation(await localAPI('containers', body));
        const created = { id: identifier, kind: body.kind, name: data.name, org: 'lab', url: snapshot.url, managers: [], template: 'pulse', managed: true };
        state.network.push(created);
        state.selected = identifier;
        acceptContainer(created, snapshot);
        syncDockerLinks(created, config);
        saveNetwork();
        $('#node-dialog').close();
        break;
      }
      case 'container-config': {
        const snapshot = await dockerOperation(await localAPI('containers/'+encodeURIComponent(node.id), {action:'config',config:JSON.parse(data.config)}));
        acceptContainer(node,snapshot);syncDockerLinks(node,snapshot.serviceConfig);saveNetwork();break;
      }
      case 'settings': {
        const current = operatorState.readers[node.id].config;
        const config = { ...current, readerId: data.readerId, queueSize: Number(data.queueSize), httpEnabled: data.httpEnabled === 'on', streamEnabled: data.streamEnabled === 'on', token: data.token,
          allowNewDevices: data.allowNewDevices === 'on', allowNewSensors: data.allowNewSensors === 'on',
          managers: data.managerUrls.split(',').map((url) => url.trim()).filter(Boolean).map((url) => ({ url, token: data.managerToken })) };
        await readerCommand(node, { action: 'config', config, clearToken: data.clearToken === 'on' });
        node.managers = state.network.filter((item) => item.kind === 'manager' && config.managers.some((target) => target.url === dockerEndpoint(item))).map((item) => item.id);
        saveNetwork();
        break;
      }
      case 'device': await readerCommand(node, { action: 'device', ...data }); break;
      case 'sensor': await readerCommand(node, { action: 'sensor', deviceId: form.dataset.device, ...data }); break;
      case 'pulse': await readerCommand(node, { action: 'pulse', deviceId: form.dataset.device, sensorId: form.dataset.sensor, value: Number(data.value), count: Number(submit?.value || 1) }); break;
    }
    toast(opText('Acción aplicada', 'Action applied'));
    render();
  } catch (error) {
    const inline = $('#op-dialog-error');
    if (inline && $('#node-dialog').open) inline.textContent = error.message;
    else toast(error.message);
  } finally {
    operatorState.busy = false;
    if (submit) submit.disabled = false;
  }
}

const previousOperatorClick = onOperatorClick;
onOperatorClick = function (event) {
  const stage = event.target.closest('[data-stage]');
  if (stage) { operatorState.stage = operatorState.stage === stage.dataset.stage ? 'all' : stage.dataset.stage; render(); return; }
  const button = event.target.closest('[data-op]');
  if (!button) return previousOperatorClick(event);
  const node = nodeById(button.dataset.id);
  if (button.dataset.op === 'clear-logs') { operatorState.logs = []; render(); return; }
  if (operatorState.busy) return;
  operatorState.busy = true;
  if (button.dataset.op.startsWith('docker-')) {
    const action=button.dataset.op.slice(7);
    toast(opText('Ejecutando operación Docker…', 'Running Docker operation…'));
    (async()=>{
      const snapshot=await dockerOperation(await localAPI('containers/'+encodeURIComponent(node.id), {action}));
      if(snapshot.removed){delete operatorState.containers[node.id];delete operatorState.readers[node.id];state.network=state.network.filter((item)=>item.id!==node.id);state.network.forEach((item)=>{item.managers=item.managers.filter((id)=>id!==node.id);});state.selected=null;}
      else acceptContainer(node,snapshot);
      saveNetwork();render();
    })().catch((error)=>toast(error.message)).finally(()=>{operatorState.busy=false;});
    return;
  }
  const operation = button.dataset.op === 'stop'
    ? localAPI('readers/' + encodeURIComponent(node.id), undefined, 'DELETE').then(() => {
      delete operatorState.readers[node.id]; state.network = state.network.filter((item) => item.id !== node.id); state.selected = null; saveNetwork();
    })
    : readerCommand(node, { action: button.dataset.op, deviceId: button.dataset.device, sensorId: button.dataset.sensor });
  operation.then(render).catch((error) => toast(error.message)).finally(() => { operatorState.busy = false; });
};

const previousOperatorChange = onOperatorChange;
onOperatorChange = function (event) {
  if (event.target.id === 'op-log-filter') { operatorState.stage = event.target.value; render(); return; }
  if (event.target.dataset.serviceToken) { operatorState.tokens.set(event.target.dataset.serviceToken, event.target.value); event.target.value = ''; return; }
  if (event.target.closest('[data-op-form]')) return;
  previousOperatorChange(event);
};

checkNode = async function (node) {
  try {
    let logs;
    if (node.managed) {
      const snapshot=await localAPI('containers/' + encodeURIComponent(node.id), undefined, 'GET');
      acceptContainer(node,snapshot);
      if(snapshot.error)operatorState.errors[node.id]=snapshot.error;
      logs=await localAPI('containers/'+encodeURIComponent(node.id)+'/logs',undefined,'GET');
    } else {
      logs = await localAPI('probe', { url: node.url, path: '/logs', token: operatorState.tokens.get(node.id) || '' });
    }
      if (!Array.isArray(logs)) throw new Error('Formato de logs inválido');
      const previous = operatorState.seen[node.id] || [];
      let overlap = Math.min(logs.length, previous.length);
      while (overlap && !previous.slice(-overlap).every((message, index) => message === logs[index])) overlap--;
      logs.slice(overlap).filter((message) => typeof message === 'string').forEach((line) => {
        let parsed;
        try { parsed=JSON.parse(line.replace(/\u001b\[[0-9;]*m/g,'')); } catch { parsed=null; }
        if(node.kind==='reader' && node.managed && parsed?.sequence)return;
        appendOperatorLog(node,parsed?.message || line,{historical:!Object.hasOwn(operatorState.seen,node.id),...(parsed?{detail:parsed}:{})});
      });
      operatorState.seen[node.id] = logs;
      if (node.kind === 'storage' && state.status[node.id]!=='down' && operatorState.logs.some((log) => log.message === 'observation_created')) {
        const records = await localAPI('probe', { url: node.url, path: '/raw', token: operatorState.tokens.get(node.id) || '' });
        const observed = new Set(operatorState.logs.filter((log) => log.message === 'observation_created').map((log) => log.detail.observationId));
        for (const [key, record] of Object.entries(records)) {
          if (record.status === 'Verified' && record.verifierSign && observed.has(record.observationId) && !operatorState.stored.has(key)) {
            operatorState.stored.add(key);
            appendOperatorLog(node, 'storage_observation_confirmed', { detail: { observationId: record.observationId, eventId: key, verifierId: record.verifierId } });
          }
        }
      }
      if(!node.managed)state.status[node.id] = 'up';
    if(!operatorState.containers[node.id]?.error)delete operatorState.errors[node.id];
  } catch (error) {
    state.status[node.id] = 'down';
    operatorState.errors[node.id] = error.message;
  }
};

async function pollOperator() {
  if (operatorState.polling || operatorState.busy || document.hidden) return;
  operatorState.polling = true;
  try {
    await Promise.all(state.network.map(checkNode));
    // Mantiene el formulario y su foco mientras se escribe.
    if (!document.activeElement?.closest('form') && !document.activeElement?.matches('input,select,textarea') && !$('#node-dialog').open) render();
    else {
      const terminal = $('.operator-log-panel');
      if (terminal && !terminal.contains(document.activeElement)) terminal.outerHTML = operatorLogs();
    }
  } finally { operatorState.polling = false; }
}

async function recoverContainers() {
  try {
    const containers=await localAPI('containers',undefined,'GET');
    for(const snapshot of containers){
      let node=nodeById(snapshot.id);
      if(!node){node={id:snapshot.id,kind:snapshot.kind,name:snapshot.name,org:'lab',url:snapshot.url,managers:[],managed:true,template:'pulse'};state.network.push(node);}
      acceptContainer(node,snapshot);
      syncDockerLinks(node,snapshot.serviceConfig || {});
    }
    saveNetwork();
    if(!$('#node-dialog').open)render();
  }catch(error){toast(error.message);}
  pollOperator();
}

$('#app').addEventListener('submit', onOperatorForm);
VIEWS.operator = viewOperator;
connectServiceNetwork({
  storage: (() => { try { return localStorage; } catch { return null; } })(),
  storageKey: 'phonendo.canvas.local.v1',
  text: opText, escape: esc, icon: ic,
  label: (kind) => kind === 'stellar' ? 'Stellar' : t('kind.' + kind),
  statusLabel: (status) => t('status.' + status),
  organizationLabel: (org) => org === 'stellar' ? 'testnet' : ORGS.includes(org) ? t('org.' + org) : org,
  snapshot: () => ({ services: state.network, statuses: state.status, readers: operatorState.readers,
    contracts: CONFIG.contracts, rpc: CONFIG.rpc, selectedId: state.selected,
    chainStatus: state.net === 'live' ? 'up' : state.net === 'error' ? 'down' : 'checking' }),
  onSelect: (id) => { state.selected = id; },
  onAdd: () => nodeDialog('reader'),
  onSettled: () => render(),
  empty: () => `<div class="card panel service-network__empty-detail">${ic('hub')}<h3>${opText('Selecciona un nodo', 'Select a node')}</h3><p>${opText('Sus detalles y controles aparecerán aquí.', 'Its details and controls will appear here.')}</p></div>`,
  details: (node) => node.kind === 'stellar'
    ? `<div class="card panel"><h3>Stellar testnet</h3><p class="op-caption">${opText('Contratos configurados. Consulta pagos y transacciones en el explorador.', 'Configured contracts. View payments and transactions in the explorer.')}</p>${CONFIG.contracts.map((contract) => `<p><a class="mono" href="${CONFIG.explorer}/contract/${esc(contract.id)}" target="_blank" rel="noopener">${esc(contract.asset)} · ${esc(short(contract.id, 8, 6))}</a></p>`).join('')}</div>`
    : operatorDetail() + containerControls(nodeById(node.id)),
});
applyLang(storageGet('phonendo.lang') === 'en' ? 'en' : 'es');
recoverContainers();
setInterval(pollOperator, 3000);
