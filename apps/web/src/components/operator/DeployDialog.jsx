import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { KINDS, KIND_ICON } from '../../config.js';
import { dockerDefaultConfig } from '../../lib/serviceConfig.js';
import { useI18n } from '../../providers/I18nProvider.jsx';
import { useNetwork } from '../../providers/NetworkProvider.jsx';
import { useOperator } from '../../providers/OperatorProvider.jsx';
import { Icon } from '../Icon.jsx';
import { Field } from './Field.jsx';

const DeployDialogContext = createContext(null);
const draftFor = (kind) => ({ kind, name: `${kind}-${Date.now().toString(36)}` });

function DeployForm({ draft, onKind, onClose }) {
  const { t, opText } = useI18n();
  const { networkRef } = useNetwork();
  const { submitForm } = useOperator();
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');
  const { kind, name } = draft;
  const [config] = useState(() => dockerDefaultConfig(kind, name, networkRef.current));

  const onSubmit = async (event) => {
    event.preventDefault();
    try {
      const done = await submitForm({ type: 'deploy-container', form: event.currentTarget, submitter: event.nativeEvent.submitter, kind, onProgress: setProgress });
      if (done) onClose();
    } catch (failure) {
      setError(failure.message);
    }
  };

  return (
    <form data-op-form="deploy-container" data-kind={kind} onSubmit={onSubmit}><div className="dialog-head"><span className="eyebrow">DOCKER / DEPLOY</span><h2 id="node-dialog-title">{opText('Desplegar contenedor', 'Deploy container')}</h2><p>{opText('Imagen, puertos y configuración propios. Los contenedores siguen ejecutándose al cerrar la web.', 'Choose image, ports and configuration. Containers keep running when the web closes.')}</p></div><div className="dialog-body">
      <div className="choice-grid kinds">{KINDS.map((item) => (
        <button key={item} type="button" className="choice" data-deploy-kind={item} aria-pressed={item === kind} onClick={() => onKind(item)}><Icon name={KIND_ICON[item]} /><b>{t(`kind.${item}`)}</b></button>
      ))}</div>
      <Field label={opText('Nombre Docker', 'Docker name')} name="name" defaultValue={name} required pattern="[a-z][a-z0-9-]{0,62}" />
      <Field label={opText('Imagen / tag', 'Image / tag')} name="image" defaultValue={`phonendo-web-${kind}:local`} required />
      <label className="check-line"><input type="checkbox" name="build" defaultChecked />{opText('Construir desde el Dockerfile del repositorio con este tag', 'Build from the repository Dockerfile with this tag')}</label>
      <p className="op-caption">{opText('Desmarca para usar una imagen existente o descargarla. Debe ser compatible con el servicio Phonendo seleccionado.', 'Uncheck to use an existing image or pull it. The image must support the selected Phonendo service.')}</p>
      <div className="field-row"><Field label={opText('Puerto local (0 = libre)', 'Host port (0 = automatic)')} name="port" defaultValue={0} type="number" min="0" max="65535" required /><Field label={opText('Puerto del contenedor', 'Container port')} name="containerPort" defaultValue={config.server.port} type="number" min="1" max="65535" required /></div>
      <label className="op-field"><span>config.json</span><textarea name="config" rows="13" spellCheck={false} required defaultValue={JSON.stringify(config, null, 2)} /></label>
      <p className="op-caption">{opText('Dentro de Docker usa la dirección Docker de cada servicio. Para servicios del equipo: host.docker.internal. Los tokens comunes del panel se inyectan automáticamente.', 'Inside Docker use each service Docker address. For host services use host.docker.internal. Shared panel tokens are injected automatically.')}</p>
      <details><summary>{opText('Variables de entorno y tokens', 'Environment variables & tokens')}</summary><label className="op-field"><span>JSON · API_TOKEN_MANAGER / API_TOKEN_VERIFIER / MANAGER_PASSWORD…</span><textarea name="environment" rows="5" spellCheck={false} defaultValue="{}" /></label></details>
      <p className="op-caption" id="op-deploy-progress" role="status">{progress}</p><p className="form-error" id="op-dialog-error" role="alert">{error}</p></div><div className="dialog-foot"><button className="btn btn-line" type="button" data-op="close-dialog" onClick={onClose}>{t('dlg.cancel')}</button><button className="btn btn-gold" type="submit">{opText('Desplegar Docker', 'Deploy Docker')}</button></div></form>
  );
}

/** Diálogo para desplegar un contenedor. Cualquier componente lo abre con useDeployDialog(). */
export function DeployDialogProvider({ children }) {
  const dialog = useRef(null);
  const { isBusy } = useOperator();
  const [draft, setDraft] = useState(null);
  const [open, setOpen] = useState(false);

  const openDialog = useCallback((kind) => { setDraft(draftFor(kind)); setOpen(true); }, []);
  // Mientras hay una operación en curso el diálogo no se cierra ni cambia de tipo.
  const close = useCallback(() => { if (!isBusy()) setOpen(false); }, [isBusy]);
  const changeKind = useCallback((kind) => { if (!isBusy()) setDraft(draftFor(kind)); }, [isBusy]);

  useEffect(() => {
    const element = dialog.current;
    if (open && !element.open) element.showModal();
    if (!open && element.open) element.close();
  }, [open, draft]);

  const value = useMemo(() => ({ openDialog }), [openDialog]);
  return (
    <DeployDialogContext.Provider value={value}>
      {children}
      <dialog id="node-dialog" aria-labelledby="node-dialog-title" ref={dialog}
        onCancel={(event) => { if (isBusy()) event.preventDefault(); }} onClose={() => setOpen(false)}>
        {draft ? <DeployForm key={draft.name} draft={draft} onKind={changeKind} onClose={close} /> : null}
      </dialog>
    </DeployDialogContext.Provider>
  );
}

export function useDeployDialog() {
  const context = useContext(DeployDialogContext);
  if (!context) throw new Error('useDeployDialog necesita un DeployDialogProvider');
  return context;
}
