import { renderConfiguration } from './configuration/editor.js';

/** Inspector de servicios y controles existentes; recibe sus datos y acciones del adaptador. */
export function renderSidebar(container, selected, { details, empty, force = false }) {
  if (!force && container.contains(document.activeElement)) return;
  const content = selected ? details(selected) : empty();
  if (container.innerHTML !== content) container.innerHTML = content;
}

export function renderContainerControls(node, { state, operatorState, opText, esc }) {
  const snapshot = operatorState.containers[node.id];
  if (!snapshot) return '';
  return `<div class="card panel"><div class="op-section-title"><h3>Docker</h3><span class="chip ${snapshot.state === 'running' ? 'chip-ok' : 'chip-warn'}">${esc(snapshot.state)}</span></div>
    <p class="mono op-url">${esc(snapshot.image)}</p><p class="op-caption">${opText('Dirección entre contenedores', 'Container network address')}</p><code class="op-url">${esc(snapshot.dockerUrl)}</code>
    <div class="panel-actions">${['start', 'stop', 'restart'].map((action) => `<button class="btn btn-line btn-sm" data-op="docker-${action}" data-id="${esc(node.id)}">${({start:opText('Arrancar','Start'),stop:opText('Parar','Stop'),restart:opText('Reiniciar','Restart')})[action]}</button>`).join('')}</div>
    ${node.kind !== 'reader' ? renderConfiguration({id:node.id,kind:node.kind,lang:state.lang,config:snapshot.serviceConfig,managed:true,environment:snapshot.environment}) : ''}
    <button class="btn btn-danger btn-sm" data-op="docker-remove" data-id="${esc(node.id)}">${opText('Eliminar contenedor', 'Remove container')}</button><p class="op-caption">${opText('Los datos se conservan en .run/web-docker. Cerrar la web no para los contenedores.', 'Data is kept in .run/web-docker. Closing the web does not stop containers.')}</p></div>`;
}

export function renderServiceDetails({ state, operatorState, nodeById, opText, ic, esc, t, configFor, field }) {
  const node = nodeById(state.selected);
  if (!node) return `<div class="card panel empty-panel">${ic('hub')}<h3>${opText('Selecciona un servicio', 'Select a service')}</h3><p>${opText('Configura un Reader y emite su primera observación.', 'Configure a Reader and send its first observation.')}</p></div>`;
  const runtime = operatorState.readers[node.id];
  if (!runtime && node.managed) return `<div class="card panel"><h3>${esc(node.name)}</h3><p class="mono op-url">${esc(node.url)}</p><p class="op-caption">${opText('Instancia Docker gestionada desde este panel.', 'Docker instance managed from this panel.')}</p>${operatorState.errors[node.id] ? `<p class="form-error">${esc(operatorState.errors[node.id])}</p>`:''}</div>`;
  if (!runtime) return `<div class="card panel"><h3>${esc(node.name)}</h3><p class="mono op-url">${esc(node.url)}</p>
    <p class="op-caption">${opText('Servicio externo: consulta su estado o prepara su configuración.', 'External service: check its status or prepare its configuration.')}</p>
    <label class="op-field"><span>${opText('Token para consultar este servicio', 'Token for service queries')}</span><input type="password" data-service-token="${esc(node.id)}" autocomplete="off" placeholder="Bearer token"></label>
    <button class="btn btn-line btn-sm" data-action="check" data-id="${esc(node.id)}">${opText('Consultar estado y logs', 'Fetch status & logs')}</button>
    ${operatorState.errors[node.id] ? `<p class="form-error">${esc(operatorState.errors[node.id])}</p>` : ''}
    ${renderConfiguration({id:node.id,kind:node.kind,lang:state.lang,config:configFor(node),draftOnly:true})}
    <button class="btn btn-danger btn-sm" data-action="remove" data-id="${esc(node.id)}">${opText('Quitar de la vista', 'Remove from view')}</button></div>`;
  const config = runtime.config;
  return `<div class="card panel reader-inspector"><div class="op-section-title"><h3>${ic('cpu')} ${esc(node.name)}</h3><span class="chip chip-ok">LIVE</span></div>
    <p class="mono op-url">${esc(runtime.url)}</p><p class="op-caption">${opText('Reader dentro de Docker. Dispositivos, sensores y configuración se conservan al reiniciar.', 'Reader running in Docker. Devices, sensors and configuration survive restarts.')}</p>
    ${renderConfiguration({id:node.id,kind:node.kind,lang:state.lang,config,liveReader:true,managed:true})}
    <div class="op-section-title spaced"><h3>${opText('Dispositivos y sensores', 'Devices & sensors')}</h3><span class="chip">${runtime.devices.length}</span></div>
    ${runtime.devices.map((device) => `<article class="device-tile"><div class="op-section-title"><b>${ic('cpu')} ${esc(device.id)}</b><button class="icon-button" data-op="remove-device" data-id="${esc(node.id)}" data-device="${esc(device.id)}" aria-label="${opText('Eliminar dispositivo', 'Remove device')}">${ic('trash')}</button></div>
      ${device.sensors.map((sensor) => `<div class="sensor-tile"><span class="sensor-status"></span><div><b>${esc(sensor.id)}</b><small>${esc(sensor.property)} · ${esc(sensor.unit || '—')}</small></div>
        <button class="icon-button" data-op="remove-sensor" data-id="${esc(node.id)}" data-device="${esc(device.id)}" data-sensor="${esc(sensor.id)}" aria-label="${opText('Eliminar sensor', 'Remove sensor')}">${ic('x')}</button>
        ${sensor.procedure === 'manual-pulse' ? `<form class="pulse-controls" data-op-form="pulse" data-id="${esc(node.id)}" data-device="${esc(device.id)}" data-sensor="${esc(sensor.id)}">
          <label>${opText('Valor', 'Value')}<input name="value" type="number" step="any" value="100" required aria-label="${opText('Valor del pulso', 'Pulse value')}"></label>
          <button class="btn btn-gold btn-sm" type="submit" name="count" value="1">${ic('pulse')} ${opText('Emitir', 'Send')}</button><button class="btn btn-line btn-sm" type="submit" name="count" value="32">×32</button></form>` : ''}</div>`).join('') || `<p class="op-caption">${opText('Sin sensores todavía', 'No sensors yet')}</p>`}
      <details><summary>+ ${opText('Añadir sensor', 'Add sensor')}</summary><form data-op-form="sensor" data-id="${esc(node.id)}" data-device="${esc(device.id)}">
        ${field('Sensor ID', 'sensorId', '', 'text', 'required')}${field(opText('Propiedad', 'Property'), 'property', 'heart-rate', 'text', 'required')}${field(opText('Unidad', 'Unit'), 'unit', 'bpm')}
        ${field('Feature of interest', 'featureOfInterest', device.id)}<label class="op-field"><span>${opText('Tipo de emisión', 'Emission type')}</span><select name="procedure"><option value="manual-pulse">${opText('Pulsos manuales', 'Manual pulses')}</option><option value="measurement">${opText('Medición externa', 'External measurement')}</option></select></label>
        <button class="btn btn-dark btn-sm" type="submit">${opText('Crear sensor', 'Create sensor')}</button></form></details></article>`).join('')}
    <details><summary>+ ${opText('Añadir dispositivo', 'Add device')}</summary><form data-op-form="device" data-id="${esc(node.id)}">${field('Device ID', 'deviceId', '', 'text', 'required')}${field(opText('Tipo', 'Type'), 'deviceType', 'pulse-band')}<button class="btn btn-dark btn-sm" type="submit">${opText('Crear dispositivo', 'Create device')}</button></form></details>
    </div>`;
}

