import { useI18n } from '../../../providers/I18nProvider.jsx';
import { readPath, writePath } from '../../../../service_network/configuration/model.js';

/** Campos simples y filas reutilizables; el borrador conserva los campos adicionales. */
export function ConfigurationInput({ field, value, onChange }) {
  const { opText } = useI18n();
  const label = opText(...field.label);
  if (field.type === 'boolean') return <label className="config-toggle"><span>{label}</span><input type="checkbox" role="switch" checked={Boolean(value)} disabled={field.readonly} onChange={(event) => onChange(event.target.checked)} /></label>;
  return <label className="config-field"><span>{label}</span><input type={field.type} value={value ?? ''} readOnly={field.readonly} required={field.required} min={field.min} max={field.max} step={field.step}
    autoComplete={field.type === 'password' ? 'new-password' : undefined}
    onChange={(event) => onChange(field.type === 'number' ? (event.target.value === '' ? undefined : Number(event.target.value)) : event.target.value)} /></label>;
}

export function ConfigurationField({ field, draft, change }) {
  const { opText } = useI18n();
  const update = (callback) => change(() => callback());
  const list = field.type === 'destinations' ? draft.destinations(field.path) : field.type === 'mapping' ? draft.mapping(field.path) : null;
  const changeRows = (rows) => {
    if (field.type === 'mapping') { draft.mappings.set(JSON.stringify(field.path), rows); draft.commitMapping(field.path); }
    else draft.set(field.path, rows);
  };
  if (!list) return <div className="config-setting"><ConfigurationInput field={field} value={readPath(draft.value, field.path) ?? field.fallback} onChange={(value) => update(() => draft.set(field.path, value))} />{field.hint ? <p className="config-hint">{opText(...field.hint)}</p> : null}</div>;
  const mapping = field.type === 'mapping';
  return <div className="config-setting">
    <div className="config-list__heading"><b>{opText(...field.label)}</b><button className="btn btn-line btn-sm" type="button" onClick={() => update(() => changeRows([...list, mapping ? { key: '', value: field.columns[0].path[0] === 'value' ? '' : {} } : { url: '', token: '' }]))}>+ {opText('Añadir', 'Add')}</button></div>
    {list.map((row, index) => <div className="config-item" key={index}>
      {mapping ? <>
        <ConfigurationInput field={{ type: 'text', label: field.keyLabels, required: true }} value={row.key} onChange={(value) => update(() => { row.key = value; draft.commitMapping(field.path); })} />
        {field.columns.map((column) => <ConfigurationInput key={column.path.join('.')} field={column} value={column.path[0] === 'value' ? row.value : readPath(row.value, column.path)} onChange={(value) => update(() => {
          if (column.path[0] === 'value') row.value = value; else writePath(row.value, column.path, value);
          draft.commitMapping(field.path);
        })} />)}
      </> : <>
        <ConfigurationInput field={{ type: 'url', label: ['URL del servicio', 'Service URL'], required: true }} value={typeof row === 'string' ? row : row.url} onChange={(value) => update(() => draft.setDestination(field.path, index, 'url', value))} />
        <details className="config-token"><summary>Token</summary><ConfigurationInput field={{ type: 'password', label: ['Token de acceso', 'Access token'] }} value={row?.token || ''} onChange={(value) => update(() => draft.setDestination(field.path, index, 'token', value))} /></details>
      </>}
      <button type="button" className="config-remove" onClick={() => update(() => changeRows(list.filter((_, current) => current !== index)))}>{opText('Quitar', 'Remove')}</button>
    </div>)}
    {!mapping ? <p className="config-hint">{list.length ? opText('Si cambias la URL, indica el token del nuevo destino.', 'If you change the URL, enter the new destination token.') : opText('Sin destinos configurados.', 'No destinations configured.')}</p> : null}
  </div>;
}
