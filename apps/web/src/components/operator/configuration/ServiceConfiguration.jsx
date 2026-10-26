import { useReducer, useState } from 'react';
import { ConfigurationDraft, readPath } from '../../../../service_network/configuration/model.js';
import { configurationSchema } from '../../../../service_network/configuration/schema.js';
import '../../../../service_network/configuration/styles.css';
import { useI18n } from '../../../providers/I18nProvider.jsx';
import { useOperator } from '../../../providers/OperatorProvider.jsx';
import { Icon } from '../../Icon.jsx';
import { ConfigurationField } from './ConfigurationField.jsx';

const GROUP_ICONS = { reader: 'cpu', identity: 'cpu', connections: 'hub', destinations: 'hub', stream: 'zap', access: 'lock', queue: 'layers', policy: 'heart', contracts: 'contract', patients: 'user', devices: 'cpu', stellar: 'star', server: 'db', data: 'shield' };

function changedSettings(draft, schema) {
  if (!draft.dirty) return [];
  const original = JSON.parse(draft.original);
  const fields = schema.flatMap((group) => group.fields);
  const changed = fields.filter((field) => JSON.stringify(readPath(original, field.path)) !== JSON.stringify(readPath(draft.value, field.path)));
  return changed.length ? changed : [{ label: ['JSON', 'JSON'] }];
}

/** Un borrador por servicio, compartido por Visual y JSON; no se persiste en disco. */
export function ServiceConfiguration({ node, config, liveReader = false, draftOnly = false, environment = {} }) {
  const { opText } = useI18n();
  const { configurationDrafts, saveConfiguration } = useOperator();
  const [, repaint] = useReducer((value) => value + 1, 0);
  const [saving, setSaving] = useState(false);
  const key = `${node.id}:${liveReader ? 'live' : draftOnly ? 'draft' : 'container'}`;
  if (!configurationDrafts.current.has(key)) configurationDrafts.current.set(key, { draft: new ConfigurationDraft(config), error: '' });
  const entry = configurationDrafts.current.get(key);
  const { draft } = entry;
  draft.sync(config);
  const context = { kind: node.kind, liveReader, managed: Boolean(node.managed), environment };
  const schema = configurationSchema(node.kind, context);
  const changes = changedSettings(draft, schema);
  const change = (callback) => { entry.error = ''; callback(); repaint(); };
  const setMode = (mode) => change(() => {
    if (mode === 'json' && draft.mode === 'visual') {
      for (const [path] of draft.mappings) if (!draft.commitMapping(JSON.parse(path))) return;
    }
    if (mode === 'visual' && draft.mode === 'json' && !draft.setJSON(draft.raw)) return;
    draft.mode = mode;
  });
  const submit = async (event) => {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    try {
      entry.error = '';
      const value = draft.validate(schema, context);
      const saved = await saveConfiguration({ node, config: value, liveReader, draftOnly, clearToken: draft.clearToken });
      draft.reset(saved); draft.clearToken = false;
    } catch (error) { entry.error = error.message; }
    finally { setSaving(false); repaint(); }
  };
  return <form className="service-config" data-config-editor={key} noValidate onSubmit={submit}>
    <div className="config-heading"><span className="config-intro">{opText('Ajusta este servicio desde sus valores reales.', 'Edit this service using its real values.')}</span>{draft.dirty ? <span className="config-dirty">{opText('Sin guardar', 'Unsaved')}</span> : null}</div>
    <div className="config-tabs" role="group" aria-label={opText('Editor de configuración', 'Configuration editor')}>{['visual', 'json'].map((mode) => <button type="button" key={mode} aria-pressed={draft.mode === mode} onClick={() => setMode(mode)}>{mode === 'visual' ? 'Visual' : 'JSON'}</button>)}</div>
    <fieldset disabled={saving} className="config-content">
      {draft.mode === 'json' ? <label className="config-field"><span>JSON · {opText('avanzado', 'advanced')}</span><textarea className="config-json" rows="18" spellCheck={false} value={draft.raw} onChange={(event) => change(() => draft.setJSON(event.target.value))} /></label>
        : schema.map((group) => <details className="config-group" key={group.id} open={group.open || group.fields.some((field) => entry.error.startsWith(`${field.label[0]}:`))}><summary><span className="config-group__icon"><Icon name={GROUP_ICONS[group.id] || 'layers'} /></span><span>{opText(...group.label)}</span><span className="config-group__count">{group.fields.length}</span></summary><div className="config-group__content">{group.fields.map((field) => <ConfigurationField key={field.path.join('.')} field={field} draft={draft} change={change} error={entry.error.startsWith(`${field.label[0]}:`) ? entry.error : ''} />)}</div></details>)}
      {liveReader ? <label className="config-toggle"><span>{opText('Quitar token del Reader', 'Remove Reader token')}</span><input type="checkbox" checked={draft.clearToken} onChange={(event) => change(() => { draft.clearToken = event.target.checked; draft.dirty = true; })} /></label> : null}
      <p className="config-hint">{draftOnly ? opText('Servicio externo: descarga la configuración y aplícala en su despliegue.', 'External service: download the configuration and apply it in its deployment.') : liveReader ? opText('Los cambios se aplican en directo. Un token vacío conserva el actual.', 'Changes apply live. An empty token keeps the current one.') : opText('Guardar reinicia este contenedor. Los secretos ocultos se conservan.', 'Saving restarts this container. Masked secrets are preserved.')}</p>
      {Object.keys(environment).length ? <details className="config-group"><summary>{opText('Variables del despliegue', 'Deployment variables')}</summary><p className="config-hint">{opText('Se fijan al crear el contenedor. Para cambiarlas, vuelve a desplegarlo.', 'These are set when the container is created. Redeploy to change them.')}</p>{Object.keys(environment).map((name) => <p className="config-hint" key={name}><code>{name}</code> · ••••••</p>)}</details> : null}
      <p className="config-error" role="alert">{entry.error || draft.error}</p>
      <div className="config-save"><div className="config-save__summary"><b>{draft.dirty ? opText(`${changes.length} ${changes.length === 1 ? 'ajuste pendiente' : 'ajustes pendientes'}`, `${changes.length} pending ${changes.length === 1 ? 'setting' : 'settings'}`) : opText('Todo guardado', 'All saved')}</b>{draft.dirty ? <span>{changes.slice(0, 3).map((field) => opText(...field.label)).join(' · ')}{changes.length > 3 ? '…' : ''}</span> : null}</div><div className="config-actions"><button type="submit" className="btn btn-dark btn-sm" disabled={!draft.dirty && !draft.clearToken}>{saving ? opText('Aplicando…', 'Applying…') : draftOnly ? opText('Descargar configuración', 'Download configuration') : liveReader ? opText('Aplicar en directo', 'Apply live') : opText('Guardar y reiniciar', 'Save & restart')}</button>{draft.dirty ? <button type="button" className="btn btn-line btn-sm" onClick={() => change(() => { draft.reset(config); draft.clearToken = false; })}>{opText('Descartar', 'Discard')}</button> : null}</div></div>
    </fieldset>
  </form>;
}
