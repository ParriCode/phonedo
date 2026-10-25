// Inspector del servicio seleccionado y controles de su contenedor Docker.
import { configFor } from '../../lib/serviceConfig.js';
import { useI18n } from '../../providers/I18nProvider.jsx';
import { useNetwork } from '../../providers/NetworkProvider.jsx';
import { useOperator } from '../../providers/OperatorProvider.jsx';
import { Icon } from '../Icon.jsx';
import { Field } from './Field.jsx';

/** Envía el formulario al OperatorProvider con el botón que lo disparó. */
function useFormSubmit(type, extra) {
  const { submitForm } = useOperator();
  return (event) => {
    event.preventDefault();
    submitForm({ type, form: event.currentTarget, submitter: event.nativeEvent.submitter, ...extra });
  };
}

function ManagedService({ node }) {
  const { opText } = useI18n();
  const { errors } = useOperator();
  return (
    <div className="card panel"><h3>{node.name}</h3><p className="mono op-url">{node.url}</p><p className="op-caption">{opText('Instancia Docker gestionada. Usa los controles del contenedor para editar su JSON o cambiar su estado.', 'Managed Docker instance. Use container controls to edit JSON or change its state.')}</p>{errors[node.id] ? <p className="form-error">{errors[node.id]}</p> : null}</div>
  );
}

function ExternalService({ node }) {
  const { t, opText } = useI18n();
  const { network } = useNetwork();
  const { errors, checkNode, setToken, downloadConfig, removeFromView } = useOperator();
  // Como el evento change nativo: guarda el token al confirmar el campo y lo borra de la vista.
  const commitToken = (input) => {
    if (!input.value) return;
    setToken(node.id, input.value);
    input.value = '';
  };
  return (
    <div className="card panel"><h3>{node.name}</h3><p className="mono op-url">{node.url}</p>
      <p className="op-caption">{opText('Servicio externo. La edición en directo solo está disponible para Readers creados con este panel.', 'External service. Live editing is available for Readers created in this panel.')}</p>
      <label className="op-field"><span>{opText('Token para consultar este servicio', 'Token for service queries')}</span><input type="password" data-service-token={node.id} autoComplete="off" placeholder="Bearer token"
        onBlur={(event) => commitToken(event.currentTarget)} onKeyDown={(event) => { if (event.key === 'Enter') commitToken(event.currentTarget); }} /></label>
      <button className="btn btn-line btn-sm" data-action="check" data-id={node.id} onClick={() => checkNode(node)}>{opText('Consultar estado y logs', 'Fetch status & logs')}</button>
      {errors[node.id] ? <p className="form-error">{errors[node.id]}</p> : null}
      <details><summary>JSON</summary><pre className="code">{JSON.stringify(configFor(node, network), null, 2)}</pre></details>
      <button className="btn btn-line btn-sm" data-action="download-config" data-id={node.id} onClick={() => downloadConfig(node)}>{t('op.download')}</button>
      <button className="btn btn-danger btn-sm" data-action="remove" data-id={node.id} onClick={() => removeFromView(node)}>{opText('Quitar de la vista', 'Remove from view')}</button></div>
  );
}

function PulseControls({ node, device, sensor }) {
  const { opText } = useI18n();
  const onSubmit = useFormSubmit('pulse', { node, device: device.id, sensor: sensor.id });
  return (
    <form className="pulse-controls" data-op-form="pulse" data-id={node.id} data-device={device.id} data-sensor={sensor.id} onSubmit={onSubmit}>
      <label>{opText('Valor', 'Value')}<input name="value" type="number" step="any" defaultValue="100" required aria-label={opText('Valor del pulso', 'Pulse value')} /></label>
      <button className="btn btn-gold btn-sm" type="submit" name="count" value="1"><Icon name="pulse" /> {opText('Emitir', 'Send')}</button><button className="btn btn-line btn-sm" type="submit" name="count" value="32">×32</button></form>
  );
}

function DeviceTile({ node, device }) {
  const { opText } = useI18n();
  const { readerAction } = useOperator();
  const onAddSensor = useFormSubmit('sensor', { node, device: device.id });
  return (
    <article className="device-tile"><div className="op-section-title"><b><Icon name="cpu" /> {device.id}</b><button className="icon-button" data-op="remove-device" data-id={node.id} data-device={device.id} aria-label={opText('Eliminar dispositivo', 'Remove device')} onClick={() => readerAction(node, 'remove-device', device.id)}><Icon name="trash" /></button></div>
      {device.sensors.length ? device.sensors.map((sensor) => (
        <div key={sensor.id} className="sensor-tile"><span className="sensor-status" /><div><b>{sensor.id}</b><small>{sensor.property} · {sensor.unit || '—'}</small></div>
          <button className="icon-button" data-op="remove-sensor" data-id={node.id} data-device={device.id} data-sensor={sensor.id} aria-label={opText('Eliminar sensor', 'Remove sensor')} onClick={() => readerAction(node, 'remove-sensor', device.id, sensor.id)}><Icon name="x" /></button>
          {sensor.procedure === 'manual-pulse' ? <PulseControls node={node} device={device} sensor={sensor} /> : null}</div>
      )) : <p className="op-caption">{opText('Sin sensores todavía', 'No sensors yet')}</p>}
      <details><summary>+ {opText('Añadir sensor', 'Add sensor')}</summary><form data-op-form="sensor" data-id={node.id} data-device={device.id} onSubmit={onAddSensor}>
        <Field label="Sensor ID" name="sensorId" required /><Field label={opText('Propiedad', 'Property')} name="property" defaultValue="heart-rate" required /><Field label={opText('Unidad', 'Unit')} name="unit" defaultValue="bpm" />
        <Field label="Feature of interest" name="featureOfInterest" defaultValue={device.id} /><label className="op-field"><span>{opText('Tipo de emisión', 'Emission type')}</span><select name="procedure"><option value="manual-pulse">{opText('Pulsos manuales', 'Manual pulses')}</option><option value="measurement">{opText('Medición externa', 'External measurement')}</option></select></label>
        <button className="btn btn-dark btn-sm" type="submit">{opText('Crear sensor', 'Create sensor')}</button></form></details></article>
  );
}

function ReaderInspector({ node, runtime }) {
  const { opText } = useI18n();
  const onSettings = useFormSubmit('settings', { node });
  const onAddDevice = useFormSubmit('device', { node });
  const config = runtime.config;
  return (
    <div className="card panel reader-inspector"><div className="op-section-title"><h3><Icon name="cpu" /> {node.name}</h3><span className="chip chip-ok">LIVE</span></div>
      <p className="mono op-url">{runtime.url}</p><p className="op-caption">{opText('Reader dentro de Docker. Dispositivos, sensores y configuración se conservan al reiniciar.', 'Reader running in Docker. Devices, sensors and configuration survive restarts.')}</p>
      <form data-op-form="settings" data-id={node.id} onSubmit={onSettings}><details open><summary>{opText('Conexiones y acceso', 'Connections & access')}</summary>
        <Field label="Reader ID" name="readerId" defaultValue={config.readerId} readOnly />
        <label className="switch-row"><span><b>HTTP push</b><small>{opText('Enviar lecturas a los Managers', 'Push readings to Managers')}</small></span><input name="httpEnabled" type="checkbox" defaultChecked={config.httpEnabled} /></label>
        <label className="switch-row"><span><b>SSE stream</b><small>{opText('Permitir suscripciones del Manager', 'Allow Manager subscriptions')}</small></span><input name="streamEnabled" type="checkbox" defaultChecked={config.streamEnabled} /></label>
        <Field label={opText('Capacidad de cola SSE', 'SSE queue capacity')} name="queueSize" defaultValue={config.queueSize} type="number" min="1" max="4096" required />
        <p className="op-caption">{opText('SSE permite conexiones entrantes: configura la suscripción en el Manager. El Manager evita conexiones HTTP/SSE redundantes.', 'SSE allows incoming connections: configure the subscription in the Manager. The Manager prevents redundant HTTP/SSE connections.')}</p>
        <Field label={opText('Nuevo token del Reader', 'New Reader token')} name="token" type="password" autoComplete="new-password" placeholder="•••••• · vacío conserva el actual" />
        <label className="check-line"><input name="clearToken" type="checkbox" />{opText('Quitar token del Reader', 'Remove Reader token')}</label>
        <Field label={opText('URLs de Managers (separadas por comas)', 'Manager URLs (comma-separated)')} name="managerUrls" defaultValue={config.managers.map((manager) => manager.url).join(', ')} />
        <Field label={opText('Token de los Managers', 'Manager token')} name="managerToken" type="password" autoComplete="new-password" />
        <label className="check-line"><input name="allowNewDevices" type="checkbox" defaultChecked={config.allowNewDevices} />{opText('Aceptar dispositivos nuevos al ingerir', 'Accept new devices on ingest')}</label>
        <label className="check-line"><input name="allowNewSensors" type="checkbox" defaultChecked={config.allowNewSensors} />{opText('Aceptar sensores nuevos al ingerir', 'Accept new sensors on ingest')}</label>
        <button className="btn btn-dark" type="submit"><Icon name="check" /> {opText('Aplicar en directo', 'Apply live')}</button></details></form>
      <div className="op-section-title spaced"><h3>{opText('Dispositivos y sensores', 'Devices & sensors')}</h3><span className="chip">{runtime.devices.length}</span></div>
      {runtime.devices.map((device) => <DeviceTile key={device.id} node={node} device={device} />)}
      <details><summary>+ {opText('Añadir dispositivo', 'Add device')}</summary><form data-op-form="device" data-id={node.id} onSubmit={onAddDevice}><Field label="Device ID" name="deviceId" required /><Field label={opText('Tipo', 'Type')} name="deviceType" defaultValue="pulse-band" /><button className="btn btn-dark btn-sm" type="submit">{opText('Crear dispositivo', 'Create device')}</button></form></details>
    </div>
  );
}

export function ServiceDetails() {
  const { opText } = useI18n();
  const { selected, nodeById } = useNetwork();
  const { readers } = useOperator();
  const node = nodeById(selected);
  if (!node) return <div className="card panel empty-panel"><Icon name="hub" /><h3>{opText('Selecciona un servicio', 'Select a service')}</h3><p>{opText('Configura un Reader y emite su primera observación.', 'Configure a Reader and send its first observation.')}</p></div>;
  const runtime = readers[node.id];
  if (!runtime && node.managed) return <ManagedService node={node} />;
  if (!runtime) return <ExternalService node={node} />;
  // Si cambia la configuración real, el formulario vuelve a sus valores.
  return <ReaderInspector key={JSON.stringify(runtime.config)} node={node} runtime={runtime} />;
}

export function ContainerControls({ node }) {
  const { opText } = useI18n();
  const { containers, dockerAction } = useOperator();
  const onConfig = useFormSubmit('container-config', { node });
  const snapshot = node && containers[node.id];
  if (!snapshot) return null;
  const labels = { start: opText('Arrancar', 'Start'), stop: opText('Parar', 'Stop'), restart: opText('Reiniciar', 'Restart') };
  return (
    <div className="card panel"><div className="op-section-title"><h3>Docker</h3><span className={`chip ${snapshot.state === 'running' ? 'chip-ok' : 'chip-warn'}`}>{snapshot.state}</span></div>
      <p className="mono op-url">{snapshot.image}</p><p className="op-caption">{opText('Dirección entre contenedores', 'Container network address')}</p><code className="op-url">{snapshot.dockerUrl}</code>
      <div className="panel-actions">{['start', 'stop', 'restart'].map((action) => (
        <button key={action} className="btn btn-line btn-sm" data-op={`docker-${action}`} data-id={node.id} onClick={() => dockerAction(node, action)}>{labels[action]}</button>
      ))}</div>
      {node.kind !== 'reader' ? <details><summary>{opText('Configuración del contenedor', 'Container configuration')}</summary><form data-op-form="container-config" data-id={node.id} onSubmit={onConfig}><label className="op-field"><span>config.json</span><textarea name="config" rows="15" spellCheck={false} defaultValue={JSON.stringify(snapshot.serviceConfig, null, 2)} /></label><p className="op-caption">{opText('Aplicar guarda el JSON y reinicia este contenedor. Los secretos ocultos se conservan.', 'Apply saves JSON and restarts this container. Masked secrets are preserved.')}</p><button className="btn btn-dark btn-sm" type="submit">{opText('Guardar y reiniciar', 'Save & restart')}</button></form></details> : null}
      <button className="btn btn-danger btn-sm" data-op="docker-remove" data-id={node.id} onClick={() => dockerAction(node, 'remove')}>{opText('Eliminar contenedor', 'Remove container')}</button><p className="op-caption">{opText('Los datos se conservan en .run/web-docker. Cerrar la web no para los contenedores.', 'Data is kept in .run/web-docker. Closing the web does not stop containers.')}</p></div>
  );
}
