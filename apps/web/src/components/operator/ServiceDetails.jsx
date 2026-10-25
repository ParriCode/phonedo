// Partes del inspector de un servicio: dispositivos del Reader (acciones de uso diario)
// y la configuración avanzada, plegada por defecto.
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

function PulseControls({ node, device, sensor }) {
  const { opText } = useI18n();
  const onSubmit = useFormSubmit('pulse', { node, device: device.id, sensor: sensor.id });
  return (
    <form className="pulse-controls" data-op-form="pulse" data-id={node.id} data-device={device.id} data-sensor={sensor.id} onSubmit={onSubmit}>
      <label>{opText('Valor', 'Value')}<input name="value" type="number" step="any" defaultValue="100" required aria-label={opText('Valor del pulso', 'Pulse value')} /></label>
      <button className="btn btn-dark btn-sm" type="submit" name="count" value="1"><Icon name="pulse" /> {opText('Emitir', 'Send')}</button><button className="btn btn-line btn-sm" type="submit" name="count" value="32">×32</button></form>
  );
}

function DeviceTile({ node, device }) {
  const { opText } = useI18n();
  const { readerAction } = useOperator();
  const onAddSensor = useFormSubmit('sensor', { node, device: device.id });
  return (
    <article className="device-tile"><div className="op-section-title"><b><Icon name="cpu" /> {device.id}</b><button type="button" className="icon-button" data-op="remove-device" data-id={node.id} data-device={device.id} aria-label={opText('Eliminar dispositivo', 'Remove device')} onClick={() => readerAction(node, 'remove-device', device.id)}><Icon name="trash" /></button></div>
      {device.sensors.length ? device.sensors.map((sensor) => (
        <div key={sensor.id} className="sensor-tile"><span className="sensor-status" /><div><b>{sensor.id}</b><small>{sensor.property} · {sensor.unit || '—'}</small></div>
          <button type="button" className="icon-button" data-op="remove-sensor" data-id={node.id} data-device={device.id} data-sensor={sensor.id} aria-label={opText('Eliminar sensor', 'Remove sensor')} onClick={() => readerAction(node, 'remove-sensor', device.id, sensor.id)}><Icon name="x" /></button>
          {sensor.procedure === 'manual-pulse' ? <PulseControls node={node} device={device} sensor={sensor} /> : null}</div>
      )) : <p className="op-caption">{opText('Sin sensores todavía', 'No sensors yet')}</p>}
      <details><summary>+ {opText('Añadir sensor', 'Add sensor')}</summary><form data-op-form="sensor" data-id={node.id} data-device={device.id} onSubmit={onAddSensor}>
        <Field label="Sensor ID" name="sensorId" required /><Field label={opText('Propiedad', 'Property')} name="property" defaultValue="heart-rate" required /><Field label={opText('Unidad', 'Unit')} name="unit" defaultValue="bpm" />
        <Field label="Feature of interest" name="featureOfInterest" defaultValue={device.id} /><label className="op-field"><span>{opText('Tipo de emisión', 'Emission type')}</span><select name="procedure"><option value="manual-pulse">{opText('Pulsos manuales', 'Manual pulses')}</option><option value="measurement">{opText('Medición externa', 'External measurement')}</option></select></label>
        <button className="btn btn-dark btn-sm" type="submit">{opText('Crear sensor', 'Create sensor')}</button></form></details></article>
  );
}

/** Dispositivos y sensores de un Reader creado con el panel, con sus pulsos manuales. */
export function ReaderDevices({ service, runtime }) {
  const { opText } = useI18n();
  const onAddDevice = useFormSubmit('device', { node: service });
  return (
    <section className="inspector__section reader-devices"><div className="inspector__section-head"><h3>{opText('Dispositivos', 'Devices')}</h3><span className="chip">{runtime.devices.length}</span></div>
      {runtime.devices.map((device) => <DeviceTile key={device.id} node={service} device={device} />)}
      <details><summary>+ {opText('Añadir dispositivo', 'Add device')}</summary><form data-op-form="device" data-id={service.id} onSubmit={onAddDevice}><Field label="Device ID" name="deviceId" required /><Field label={opText('Tipo', 'Type')} name="deviceType" defaultValue="pulse-band" /><button className="btn btn-dark btn-sm" type="submit">{opText('Crear dispositivo', 'Create device')}</button></form></details>
    </section>
  );
}

function ServiceToken({ service }) {
  const { opText } = useI18n();
  const { setToken } = useOperator();
  // Como el evento change nativo: guarda el token al confirmar el campo y lo borra de la vista.
  const commitToken = (input) => {
    if (!input.value) return;
    setToken(service.id, input.value);
    input.value = '';
  };
  return (
    <label className="op-field"><span>{opText('Token para consultar este servicio', 'Token for service queries')}</span><input type="password" data-service-token={service.id} autoComplete="off" placeholder="Bearer token"
      onBlur={(event) => commitToken(event.currentTarget)} onKeyDown={(event) => { if (event.key === 'Enter') commitToken(event.currentTarget); }} /></label>
  );
}

/** Nivel 3: dirección completa, Docker, token, configuración Visual/JSON y eliminar. */
export function AdvancedSettings({ service }) {
  const { opText } = useI18n();
  const { network } = useNetwork();
  const { readers, containers, dockerAction, removeFromView } = useOperator();
  const runtime = readers[service.id];
  const snapshot = containers[service.id];
  let editor = null;
  if (runtime) editor = <ServiceConfiguration key={service.id} node={service} config={runtime.config} liveReader />;
  else if (snapshot && service.kind !== 'reader') editor = <ServiceConfiguration key={service.id} node={service} config={snapshot.serviceConfig} environment={snapshot.environment} />;
  else if (!service.managed) editor = <ServiceConfiguration key={service.id} node={service} config={configFor(service, network)} draftOnly />;
  return (
    <details className="advanced">
      <summary>{opText('Configuración avanzada', 'Advanced settings')}</summary>
      <dl className="facts facts--compact">
        <dt>URL</dt><dd className="mono">{service.url}</dd>
        {snapshot ? <><dt>{opText('Imagen', 'Image')}</dt><dd className="mono">{snapshot.image}</dd><dt>{opText('Red Docker', 'Docker network')}</dt><dd className="mono">{snapshot.dockerUrl}</dd></> : null}
      </dl>
      {service.managed ? null : <ServiceToken service={service} />}
      {editor}
      {service.managed
        ? <><button type="button" className="btn btn-danger btn-sm" data-op="docker-remove" data-id={service.id} onClick={() => dockerAction(service, 'remove')}>{opText('Eliminar contenedor', 'Remove container')}</button><p className="op-caption">{opText('Los datos se conservan en .run/web-docker. Cerrar la web no para los contenedores.', 'Data is kept in .run/web-docker. Closing the web does not stop containers.')}</p></>
        : <button type="button" className="btn btn-danger btn-sm" data-action="remove" data-id={service.id} onClick={() => removeFromView(service)}>{opText('Quitar de la vista', 'Remove from view')}</button>}
    </details>
  );
}
