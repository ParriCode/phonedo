// Inspector del servicio seleccionado y controles de su contenedor Docker.
import { configFor } from '../../lib/serviceConfig.js';
import { useI18n } from '../../providers/I18nProvider.jsx';
import { useNetwork } from '../../providers/NetworkProvider.jsx';
import { useOperator } from '../../providers/OperatorProvider.jsx';
import { Icon } from '../Icon.jsx';
import { Field } from './Field.jsx';
import { ServiceConfiguration } from './configuration/ServiceConfiguration.jsx';

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
    <div className="card panel"><h3>{node.name}</h3><p className="mono op-url">{node.url}</p><p className="op-caption">{opText('Instancia Docker gestionada desde este panel.', 'Docker instance managed from this panel.')}</p>{errors[node.id] ? <p className="form-error">{errors[node.id]}</p> : null}</div>
  );
}

function ExternalService({ node }) {
  const { opText } = useI18n();
  const { network } = useNetwork();
  const { errors, checkNode, setToken, removeFromView } = useOperator();
  // Como el evento change nativo: guarda el token al confirmar el campo y lo borra de la vista.
  const commitToken = (input) => {
    if (!input.value) return;
    setToken(node.id, input.value);
    input.value = '';
  };
  return (
    <div className="card panel"><h3>{node.name}</h3><p className="mono op-url">{node.url}</p>
      <p className="op-caption">{opText('Servicio externo: consulta su estado o prepara su configuración.', 'External service: check its status or prepare its configuration.')}</p>
      <label className="op-field"><span>{opText('Token para consultar este servicio', 'Token for service queries')}</span><input type="password" data-service-token={node.id} autoComplete="off" placeholder="Bearer token"
        onBlur={(event) => commitToken(event.currentTarget)} onKeyDown={(event) => { if (event.key === 'Enter') commitToken(event.currentTarget); }} /></label>
      <button className="btn btn-line btn-sm" data-action="check" data-id={node.id} onClick={() => checkNode(node)}>{opText('Consultar estado y logs', 'Fetch status & logs')}</button>
      {errors[node.id] ? <p className="form-error">{errors[node.id]}</p> : null}
      <ServiceConfiguration key={node.id} node={node} config={configFor(node, network)} draftOnly />
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
  const onAddDevice = useFormSubmit('device', { node });
  const config = runtime.config;
  return (
    <div className="card panel reader-inspector"><div className="op-section-title"><h3><Icon name="cpu" /> {node.name}</h3><span className="chip chip-ok">LIVE</span></div>
      <p className="mono op-url">{runtime.url}</p><p className="op-caption">{opText('Reader dentro de Docker. Dispositivos, sensores y configuración se conservan al reiniciar.', 'Reader running in Docker. Devices, sensors and configuration survive restarts.')}</p>
      <ServiceConfiguration key={node.id} node={node} config={config} liveReader />
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
  return <ReaderInspector key={node.id} node={node} runtime={runtime} />;
}

export function ContainerControls({ node }) {
  const { opText } = useI18n();
  const { containers, dockerAction } = useOperator();
  const snapshot = node && containers[node.id];
  if (!snapshot) return null;
  const labels = { start: opText('Arrancar', 'Start'), stop: opText('Parar', 'Stop'), restart: opText('Reiniciar', 'Restart') };
  return (
    <div className="card panel"><div className="op-section-title"><h3>Docker</h3><span className={`chip ${snapshot.state === 'running' ? 'chip-ok' : 'chip-warn'}`}>{snapshot.state}</span></div>
      <p className="mono op-url">{snapshot.image}</p><p className="op-caption">{opText('Dirección entre contenedores', 'Container network address')}</p><code className="op-url">{snapshot.dockerUrl}</code>
      <div className="panel-actions">{['start', 'stop', 'restart'].map((action) => (
        <button key={action} className="btn btn-line btn-sm" data-op={`docker-${action}`} data-id={node.id} onClick={() => dockerAction(node, action)}>{labels[action]}</button>
      ))}</div>
      {node.kind !== 'reader' ? <ServiceConfiguration key={node.id} node={node} config={snapshot.serviceConfig} environment={snapshot.environment} /> : null}
      <button className="btn btn-danger btn-sm" data-op="docker-remove" data-id={node.id} onClick={() => dockerAction(node, 'remove')}>{opText('Eliminar contenedor', 'Remove container')}</button><p className="op-caption">{opText('Los datos se conservan en .run/web-docker. Cerrar la web no para los contenedores.', 'Data is kept in .run/web-docker. Closing the web does not stop containers.')}</p></div>
  );
}
