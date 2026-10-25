/** Inspector de servicios y controles existentes; recibe sus datos y acciones del adaptador. */
export function renderSidebar(container, selected, { details, empty, force = false }) {
  if (!force && container.contains(document.activeElement)) return;
  const content = selected ? details(selected) : empty();
  if (container.innerHTML !== content) container.innerHTML = content;
}

export function renderContainerControls(node, { operatorState, opText, esc }) {
  const snapshot = operatorState.containers[node.id];
  if (!snapshot) return '';
  return `<div class="card panel"><div class="op-section-title"><h3>Docker</h3><span class="chip ${snapshot.state === 'running' ? 'chip-ok' : 'chip-warn'}">${esc(snapshot.state)}</span></div>
    <p class="mono op-url">${esc(snapshot.image)}</p><p class="op-caption">${opText('Dirección entre contenedores', 'Container network address')}</p><code class="op-url">${esc(snapshot.dockerUrl)}</code>
    <div class="panel-actions">${['start', 'stop', 'restart'].map((action) => `<button class="btn btn-line btn-sm" data-op="docker-${action}" data-id="${esc(node.id)}">${({start:opText('Arrancar','Start'),stop:opText('Parar','Stop'),restart:opText('Reiniciar','Restart')})[action]}</button>`).join('')}</div>
    ${node.kind !== 'reader' ? `<details><summary>${opText('Configuración del contenedor', 'Container configuration')}</summary><form data-op-form="container-config" data-id="${esc(node.id)}"><label class="op-field"><span>config.json</span><textarea name="config" rows="15" spellcheck="false">${esc(JSON.stringify(snapshot.serviceConfig, null, 2))}</textarea></label><p class="op-caption">${opText('Aplicar guarda el JSON y reinicia este contenedor. Los secretos ocultos se conservan.', 'Apply saves JSON and restarts this container. Masked secrets are preserved.')}</p><button class="btn btn-dark btn-sm" type="submit">${opText('Guardar y reiniciar', 'Save & restart')}</button></form></details>` : ''}
    <button class="btn btn-danger btn-sm" data-op="docker-remove" data-id="${esc(node.id)}">${opText('Eliminar contenedor', 'Remove container')}</button><p class="op-caption">${opText('Los datos se conservan en .run/web-docker. Cerrar la web no para los contenedores.', 'Data is kept in .run/web-docker. Closing the web does not stop containers.')}</p></div>`;
}

export function renderServiceDetails({ state, operatorState, nodeById, opText, ic, esc, t, configFor, field }) {
  const node = nodeById(state.selected);
  if (!node) return `<div class="card panel empty-panel">${ic('hub')}<h3>${opText('Selecciona un servicio', 'Select a service')}</h3><p>${opText('Configura un Reader y emite su primera observación.', 'Configure a Reader and send its first observation.')}</p></div>`;
  const runtime = operatorState.readers[node.id];
  if (!runtime && node.managed) return `<div class="card panel"><h3>${esc(node.name)}</h3><p class="mono op-url">${esc(node.url)}</p><p class="op-caption">${opText('Instancia Docker gestionada. Usa los controles del contenedor para editar su JSON o cambiar su estado.', 'Managed Docker instance. Use container controls to edit JSON or change its state.')}</p>${operatorState.errors[node.id] ? `<p class="form-error">${esc(operatorState.errors[node.id])}</p>`:''}</div>`;
  if (!runtime) return `<div class="card panel"><h3>${esc(node.name)}</h3><p class="mono op-url">${esc(node.url)}</p>
    <p class="op-caption">${opText('Servicio externo. La edición en directo solo está disponible para Readers creados con este panel.', 'External service. Live editing is available for Readers created in this panel.')}</p>
    <label class="op-field"><span>${opText('Token para consultar este servicio', 'Token for service queries')}</span><input type="password" data-service-token="${esc(node.id)}" autocomplete="off" placeholder="Bearer token"></label>
    <button class="btn btn-line btn-sm" data-action="check" data-id="${esc(node.id)}">${opText('Consultar estado y logs', 'Fetch status & logs')}</button>
    ${operatorState.errors[node.id] ? `<p class="form-error">${esc(operatorState.errors[node.id])}</p>` : ''}
    <details><summary>JSON</summary><pre class="code">${esc(JSON.stringify(configFor(node), null, 2))}</pre></details>
    <button class="btn btn-line btn-sm" data-action="download-config" data-id="${esc(node.id)}">${t('op.download')}</button>
    <button class="btn btn-danger btn-sm" data-action="remove" data-id="${esc(node.id)}">${opText('Quitar de la vista', 'Remove from view')}</button></div>`;
  const config = runtime.config;
  return `<div class="card panel reader-inspector"><div class="op-section-title"><h3>${ic('cpu')} ${esc(node.name)}</h3><span class="chip chip-ok">LIVE</span></div>
    <p class="mono op-url">${esc(runtime.url)}</p><p class="op-caption">${opText('Reader dentro de Docker. Dispositivos, sensores y configuración se conservan al reiniciar.', 'Reader running in Docker. Devices, sensors and configuration survive restarts.')}</p>
    <form data-op-form="settings" data-id="${esc(node.id)}"><details open><summary>${opText('Conexiones y acceso', 'Connections & access')}</summary>
      ${field('Reader ID', 'readerId', config.readerId, 'text', 'readonly')}
      <label class="switch-row"><span><b>HTTP push</b><small>${opText('Enviar lecturas a los Managers', 'Push readings to Managers')}</small></span><input name="httpEnabled" type="checkbox" ${config.httpEnabled ? 'checked' : ''}></label>
      <label class="switch-row"><span><b>SSE stream</b><small>${opText('Permitir suscripciones del Manager', 'Allow Manager subscriptions')}</small></span><input name="streamEnabled" type="checkbox" ${config.streamEnabled ? 'checked' : ''}></label>
      ${field(opText('Capacidad de cola SSE', 'SSE queue capacity'), 'queueSize', config.queueSize, 'number', 'min="1" max="4096" required')}
      <p class="op-caption">${opText('SSE permite conexiones entrantes: configura la suscripción en el Manager. El Manager evita conexiones HTTP/SSE redundantes.', 'SSE allows incoming connections: configure the subscription in the Manager. The Manager prevents redundant HTTP/SSE connections.')}</p>
      ${field(opText('Nuevo token del Reader', 'New Reader token'), 'token', '', 'password', 'autocomplete="new-password" placeholder="•••••• · vacío conserva el actual"')}
      <label class="check-line"><input name="clearToken" type="checkbox">${opText('Quitar token del Reader', 'Remove Reader token')}</label>
      ${field(opText('URLs de Managers (separadas por comas)', 'Manager URLs (comma-separated)'), 'managerUrls', config.managers.map((manager) => manager.url).join(', '))}
      ${field(opText('Token de los Managers', 'Manager token'), 'managerToken', '', 'password', 'autocomplete="new-password"')}
      <label class="check-line"><input name="allowNewDevices" type="checkbox" ${config.allowNewDevices ? 'checked' : ''}>${opText('Aceptar dispositivos nuevos al ingerir', 'Accept new devices on ingest')}</label>
      <label class="check-line"><input name="allowNewSensors" type="checkbox" ${config.allowNewSensors ? 'checked' : ''}>${opText('Aceptar sensores nuevos al ingerir', 'Accept new sensors on ingest')}</label>
      <button class="btn btn-dark" type="submit">${ic('check')} ${opText('Aplicar en directo', 'Apply live')}</button></details></form>
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

