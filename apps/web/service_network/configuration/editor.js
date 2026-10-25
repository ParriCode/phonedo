import { ConfigurationDraft, readPath, writePath } from './model.js';
import { configurationSchema } from './schema.js';

const editors = new Map();
const escape = (value = '') => String(value).replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const text = (context, labels) => labels[context.lang === 'es' ? 0 : 1];
const words = (context, es, en) => text(context, [es, en]);

function input(context, field, value, attributes) {
  const label = escape(text(context, field.label));
  if (field.type === 'boolean') return `<label class="config-toggle"><span>${label}</span><input type="checkbox" role="switch" ${attributes} ${value ? 'checked' : ''} ${field.readonly ? 'disabled' : ''}></label>`;
  return `<label class="config-field"><span>${label}</span><input type="${field.type}" ${attributes} value="${escape(value ?? '')}" ${field.readonly ? 'readonly' : ''} ${field.required ? 'required' : ''} ${field.min !== undefined ? `min="${field.min}"` : ''} ${field.max !== undefined ? `max="${field.max}"` : ''} ${field.step ? `step="${field.step}"` : ''} ${field.type === 'password' ? 'autocomplete="new-password"' : ''}></label>`;
}

function renderField(entry, field, index) {
  const { context, draft } = entry;
  const value = readPath(draft.value, field.path) ?? field.fallback;
  const heading = `<div class="config-list__heading"><b>${escape(text(context, field.label))}</b><button class="btn btn-line btn-sm" type="button" data-config-action="add" data-field="${index}">+ ${words(context,'Añadir','Add')}</button></div>`;
  let content;
  if (field.type === 'destinations') {
    content = heading + draft.destinations(field.path).map((target, row) => `<div class="config-item">
      ${input(context, {type:'url',label:['URL del servicio','Service URL'],required:true}, typeof target === 'string' ? target : target.url, `data-field="${index}" data-row="${row}" data-key="url"`)}
      <details class="config-token"><summary>Token</summary>${input(context, {type:'password',label:['Token de acceso','Access token']}, target?.token || '', `data-field="${index}" data-row="${row}" data-key="token"`)}</details>
      <button type="button" class="config-remove" data-config-action="remove" data-field="${index}" data-row="${row}">${words(context,'Quitar destino','Remove destination')}</button></div>`).join('');
    if (!draft.destinations(field.path).length) content += `<p class="config-hint">${words(context,'Sin destinos configurados.','No destinations configured.')}</p>`;
    else content += `<p class="config-hint">${words(context,'Si cambias la URL, indica el token del nuevo destino.','If you change the URL, enter the new destination token.')}</p>`;
  } else if (field.type === 'mapping') {
    content = heading + draft.mapping(field.path).map((row, rowIndex) => `<div class="config-item">
      ${input(context, {type:'text',label:field.keyLabels,required:true}, row.key, `data-field="${index}" data-row="${rowIndex}" data-key="key"`)}
      ${field.columns.map((column, columnIndex) => input(context,column,column.path[0] === 'value' ? row.value : readPath(row.value,column.path),`data-field="${index}" data-row="${rowIndex}" data-column="${columnIndex}"`)).join('')}
      <button type="button" class="config-remove" data-config-action="remove" data-field="${index}" data-row="${rowIndex}">${words(context,'Quitar','Remove')}</button></div>`).join('');
  } else content = input(context, field, value, `data-field="${index}"`);
  return `<div class="config-setting">${content}${field.hint ? `<p class="config-hint">${escape(text(context,field.hint))}</p>` : ''}</div>`;
}

function markup(entry) {
  const {context,draft,schema,key} = entry;
  let index = 0;
  return `<form class="service-config" data-config-editor="${escape(key)}" novalidate>
    <div class="config-heading"><h3>${words(context,'Configuración','Configuration')}</h3><span class="config-dirty">${draft.dirty ? words(context,'Sin guardar','Unsaved') : ''}</span></div>
    <div class="config-tabs" role="group" aria-label="${words(context,'Editor de configuración','Configuration editor')}">${['visual','json'].map((mode)=>`<button type="button" data-config-action="${mode}" aria-pressed="${draft.mode===mode}">${mode==='visual' ? 'Visual' : 'JSON'}</button>`).join('')}</div>
    ${draft.mode === 'json' ? `<label class="config-field"><span>JSON · ${words(context,'avanzado','advanced')}</span><textarea class="config-json" rows="18" spellcheck="false" data-config-json>${escape(draft.raw)}</textarea></label>` : schema.map((group)=>`<details class="config-group" ${group.open ? 'open' : ''}><summary>${escape(text(context,group.label))}</summary>${group.fields.map((field)=>renderField(entry,field,index++)).join('')}</details>`).join('')}
    ${context.liveReader ? `<label class="config-toggle"><span>${words(context,'Quitar token del Reader','Remove Reader token')}</span><input type="checkbox" data-config-clear-token ${draft.clearToken ? 'checked' : ''}></label>` : ''}
    <p class="config-hint">${context.draftOnly ? words(context,'Servicio externo: descarga la configuración y aplícala en su despliegue.','External service: download the configuration and apply it in its deployment.') : context.liveReader ? words(context,'Los cambios se aplican en directo. Un token vacío conserva el actual.','Changes apply live. An empty token keeps the current one.') : words(context,'Guardar reinicia este contenedor. Los secretos ocultos se conservan.','Saving restarts this container. Masked secrets are preserved.')}</p>
    ${Object.keys(context.environment || {}).length ? `<details class="config-group"><summary>${words(context,'Variables del despliegue','Deployment variables')}</summary><p class="config-hint">${words(context,'Se fijan al crear el contenedor. Para cambiarlas, vuelve a desplegarlo.','These are set when the container is created. Redeploy to change them.')}</p>${Object.keys(context.environment).map((name)=>`<p class="config-hint"><code>${escape(name)}</code> · ••••••</p>`).join('')}</details>` : ''}
    <p class="config-error" role="alert">${escape(entry.error || draft.error)}</p>
    <div class="config-actions"><button type="submit" class="btn btn-dark btn-sm">${context.draftOnly ? words(context,'Descargar configuración','Download configuration') : context.liveReader ? words(context,'Aplicar en directo','Apply live') : words(context,'Guardar y reiniciar','Save & restart')}</button><button type="button" class="btn btn-line btn-sm" data-config-action="reset">${words(context,'Restablecer','Reset')}</button></div>
  </form>`;
}

export function renderConfiguration(context) {
  const key = `${context.id}:${context.liveReader ? 'live' : context.draftOnly ? 'draft' : 'container'}`;
  const entry = editors.get(key) || {key,draft:new ConfigurationDraft(context.config)};
  entry.context = context;
  entry.schema = configurationSchema(context.kind,context);
  entry.fields = entry.schema.flatMap((group)=>group.fields);
  entry.draft.sync(context.config);
  editors.set(key,entry);
  return markup(entry);
}

/** El formulario delega el guardado; los secretos permanecen en memoria. */
export function bindConfigurationEditors({onSave,onSaved}) {
  const entryFor = (target) => {
    const form = target.closest('[data-config-editor]');
    return form ? {form,entry:editors.get(form.dataset.configEditor)} : {};
  };
  const repaint = (form,entry) => { form.outerHTML = markup(entry); };
  document.addEventListener('input',(event)=>{
    const {form,entry} = entryFor(event.target);
    if(!entry)return;
    const {draft,fields} = entry;
    entry.error='';
    const target = event.target;
    if(target.hasAttribute('data-config-json'))draft.setJSON(target.value);
    else if(target.hasAttribute('data-config-clear-token')){draft.clearToken=target.checked;draft.dirty=true;}
    else if(target.hasAttribute('data-field')){
      const field=fields[Number(target.dataset.field)];
      const value=target.type==='checkbox' ? target.checked : target.type==='number' ? (target.value==='' ? undefined : Number(target.value)) : target.value;
      if(field.readonly)return;
      if(field.type==='destinations'){
        draft.setDestination(field.path,Number(target.dataset.row),target.dataset.key,value);
        if(target.dataset.key==='url')target.closest('.config-item').querySelector('input[type="password"]').value=draft.destinations(field.path)[Number(target.dataset.row)]?.token || '';
      }
      else if(field.type==='mapping'){
        const row=draft.mapping(field.path)[Number(target.dataset.row)];
        if(target.dataset.key==='key')row.key=value;
        else {const column=field.columns[Number(target.dataset.column)];if(column.path[0]==='value')row.value=value;else writePath(row.value,column.path,value);}
        draft.commitMapping(field.path);
      }else draft.set(field.path,value);
    }
    form.querySelector('.config-dirty').textContent=words(entry.context,'Sin guardar','Unsaved');
    form.querySelector('.config-error').textContent=draft.error;
  });
  document.addEventListener('click',(event)=>{
    const button=event.target.closest('[data-config-action]');
    if(!button)return;
    const {form,entry}=entryFor(button);
    if(!entry)return;
    const {draft,fields}=entry;
    const action=button.dataset.configAction;
    entry.error='';
    if(action==='reset'){draft.reset(entry.context.config);draft.clearToken=false;}
    else if(action==='visual' || action==='json'){
      if(action==='json' && draft.mode==='visual'){
        for(const [path] of draft.mappings)if(!draft.commitMapping(JSON.parse(path))){form.querySelector('.config-error').textContent=draft.error;return;}
      }
      if(action==='visual' && draft.mode==='json' && !draft.setJSON(draft.raw)){form.querySelector('.config-error').textContent=draft.error;return;}
      draft.mode=action;
    }else{
      const field=fields[Number(button.dataset.field)];
      const rows=field.type==='mapping' ? draft.mapping(field.path) : structuredClone(draft.destinations(field.path));
      if(action==='add')rows.push(field.type==='mapping' ? {key:'',value:field.columns[0].path[0]==='value' ? '' : {}} : {url:'',token:''});
      else rows.splice(Number(button.dataset.row),1);
      if(field.type==='mapping')draft.commitMapping(field.path);else draft.set(field.path,rows);
    }
    repaint(form,entry);
  });
  document.addEventListener('submit',async(event)=>{
    const {form,entry}=entryFor(event.target);
    if(!entry)return;
    event.preventDefault();
    const button=form.querySelector('[type="submit"]');
    if(button.disabled)return;
    button.disabled=true;
    try{
      entry.error='';
      const config=entry.draft.validate(entry.schema,entry.context);
      const saved=await onSave({...entry.context,config,clearToken:entry.draft.clearToken});
      entry.draft.reset(saved || config);entry.draft.clearToken=false;
      repaint(form,entry);onSaved?.();
    }catch(error){entry.error=error.message;form.querySelector('.config-error').textContent=error.message;}
    finally{button.disabled=false;}
  });
}
