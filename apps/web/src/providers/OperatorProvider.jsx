/* Consola local. Las acciones confirmadas vienen de /api/local, nunca de una simulación visual. */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { requestLocal } from '../../service_network/api.js';
import { configFor, configName, dockerEndpoint, linkDockerNode } from '../lib/serviceConfig.js';
import { download } from '../lib/format.js';
import { useStateRef } from '../lib/useStateRef.js';
import { useI18n } from './I18nProvider.jsx';
import { useNetwork } from './NetworkProvider.jsx';
import { useToast } from './ToastProvider.jsx';

const OperatorContext = createContext(null);
const without = (map, key) => { const next = { ...map }; delete next[key]; return next; };
const encode = encodeURIComponent;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export function OperatorProvider({ children }) {
  const { t, opText } = useI18n();
  const toast = useToast();
  const { nodeById, addNode, updateNode, removeNode, setNetwork, setStatus, select, networkRef, statusRef } = useNetwork();

  const [readers, setReaders, readersRef] = useStateRef({});
  const [containers, setContainers, containersRef] = useStateRef({});
  const [logs, setLogs, logsRef] = useStateRef([]);
  const [errors, setErrors] = useState({});
  const [active, setActive] = useState({});
  const [stage, setStage] = useState('all');
  // Tras cada acción confirmada los formularios del inspector vuelven a sus valores reales.
  const [epoch, setEpoch] = useState(0);

  const seen = useRef({});
  const cursors = useRef({});
  const stored = useRef(new Set());
  const tokens = useRef(new Map());
  const busy = useRef(false);
  const polling = useRef(false);

  const appendLog = useCallback((node, message, fields = {}) => {
    const entry = { id: crypto.randomUUID(), node: node.id, name: node.name, kind: node.kind, message, ...fields };
    setLogs((list) => [entry, ...list].slice(0, 300));
    if (!fields.historical && /observation|event_|batch_|session_|verified|accepted/.test(message)) {
      setActive((map) => ({ ...map, [node.id]: Date.now() }));
    }
  }, [setLogs]);

  const acceptReader = useCallback((node, snapshot) => {
    const restarted = readersRef.current[node.id]?.bootId !== snapshot.bootId;
    setReaders((map) => ({ ...map, [node.id]: snapshot }));
    const cursor = restarted ? 0 : cursors.current[node.id] || 0;
    for (const event of snapshot.events) {
      if (event.sequence > cursor) appendLog(node, event.message, { detail: event });
    }
    cursors.current[node.id] = snapshot.events.at(-1)?.sequence || cursor;
    updateNode(node.id, { url: snapshot.url });
    setStatus(node.id, 'up');
  }, [appendLog, readersRef, setReaders, setStatus, updateNode]);

  const acceptContainer = useCallback((node, snapshot) => {
    setContainers((map) => ({ ...map, [node.id]: snapshot }));
    updateNode(node.id, { dockerUrl: snapshot.dockerUrl, image: snapshot.image, url: snapshot.url });
    if (node.kind === 'reader' && snapshot.config) acceptReader(node, snapshot);
    else setReaders((map) => without(map, node.id));
    setStatus(node.id, snapshot.state === 'running' && !snapshot.error ? 'up' : 'down');
  }, [acceptReader, setContainers, setReaders, setStatus, updateNode]);

  const readerCommand = useCallback(async (node, body) => {
    const snapshot = await requestLocal('readers/' + encode(node.id), body);
    acceptReader(node, snapshot);
    return snapshot;
  }, [acceptReader]);

  const dockerOperation = useCallback(async (operation, onProgress) => {
    while (operation.state === 'running') {
      onProgress?.(operation.message);
      await sleep(1000);
      operation = await requestLocal('operations/' + operation.id, undefined, 'GET');
    }
    if (operation.state !== 'succeeded') throw new Error(operation.error || 'Error de Docker');
    return operation.result;
  }, []);

  const checkNode = useCallback(async (node) => {
    try {
      let lines;
      if (node.managed) {
        const snapshot = await requestLocal('containers/' + encode(node.id), undefined, 'GET');
        acceptContainer(node, snapshot);
        node = nodeById(node.id) ?? node;
        if (snapshot.error) setErrors((map) => ({ ...map, [node.id]: snapshot.error }));
        lines = await requestLocal('containers/' + encode(node.id) + '/logs', undefined, 'GET');
      } else {
        lines = await requestLocal('probe', { url: node.url, path: '/logs', token: tokens.current.get(node.id) || '' });
      }
      if (!Array.isArray(lines)) throw new Error('Formato de logs inválido');
      const previous = seen.current[node.id] || [];
      let overlap = Math.min(lines.length, previous.length);
      while (overlap && !previous.slice(-overlap).every((message, index) => message === lines[index])) overlap--;
      const historical = !Object.hasOwn(seen.current, node.id);
      lines.slice(overlap).filter((message) => typeof message === 'string').forEach((line) => {
        let parsed;
        try { parsed = JSON.parse(line.replace(/\u001b\[[0-9;]*m/g, '')); } catch { parsed = null; }
        if (node.kind === 'reader' && node.managed && parsed?.sequence) return;
        appendLog(node, parsed?.message || line, { historical, ...(parsed ? { detail: parsed } : {}) });
      });
      seen.current[node.id] = lines;
      if (node.kind === 'storage' && statusRef.current[node.id] !== 'down' && logsRef.current.some((log) => log.message === 'observation_created')) {
        const records = await requestLocal('probe', { url: node.url, path: '/raw', token: tokens.current.get(node.id) || '' });
        const observed = new Set(logsRef.current.filter((log) => log.message === 'observation_created').map((log) => log.detail.observationId));
        for (const [key, record] of Object.entries(records)) {
          if (record.status === 'Verified' && record.verifierSign && observed.has(record.observationId) && !stored.current.has(key)) {
            stored.current.add(key);
            appendLog(node, 'storage_observation_confirmed', { detail: { observationId: record.observationId, eventId: key, verifierId: record.verifierId } });
          }
        }
      }
      if (!node.managed) setStatus(node.id, 'up');
      if (!containersRef.current[node.id]?.error) setErrors((map) => without(map, node.id));
    } catch (error) {
      setStatus(node.id, 'down');
      setErrors((map) => ({ ...map, [node.id]: error.message }));
    }
  }, [acceptContainer, appendLog, containersRef, logsRef, nodeById, setStatus, statusRef]);

  const poll = useCallback(async () => {
    if (polling.current || busy.current || document.hidden) return;
    polling.current = true;
    try { await Promise.all(networkRef.current.map(checkNode)); } finally { polling.current = false; }
  }, [checkNode, networkRef]);

  const pollRef = useRef(poll);
  pollRef.current = poll;

  // Al abrir: recupera los contenedores que siguen ejecutándose y empieza a sondear cada 3 s.
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return undefined;
    started.current = true;
    (async () => {
      try {
        const list = await requestLocal('containers', undefined, 'GET');
        for (const snapshot of list) {
          if (!nodeById(snapshot.id)) addNode({ id: snapshot.id, kind: snapshot.kind, name: snapshot.name, org: 'lab', url: snapshot.url, managers: [], managed: true, template: 'pulse' });
          acceptContainer(nodeById(snapshot.id), snapshot);
          setNetwork((list) => linkDockerNode(list, snapshot.id, snapshot.serviceConfig || {}));
        }
      } catch (error) { toast(error.message); }
      poll();
    })();
    const timer = setInterval(() => pollRef.current(), 3000);
    return () => clearInterval(timer);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /** Envía un formulario del operador. Devuelve true si la acción se confirmó. */
  const submitForm = useCallback(async ({ type, form, submitter, node, device, sensor, kind, onProgress }) => {
    if (busy.current) return false;
    busy.current = true;
    if (submitter) submitter.disabled = true;
    const data = Object.fromEntries(new FormData(form));
    try {
      switch (type) {
        case 'deploy-container': {
          const identifier = crypto.randomUUID();
          const config = JSON.parse(data.config);
          const body = { id: identifier, kind, name: data.name, image: data.image, port: Number(data.port), containerPort: Number(data.containerPort), build: data.build === 'on', config, environment: JSON.parse(data.environment), stellarIdentity: data.stellarIdentity === 'on' };
          const snapshot = await dockerOperation(await requestLocal('containers', body), onProgress);
          const created = { id: identifier, kind, name: data.name, org: 'lab', url: snapshot.url, managers: [], template: 'pulse', managed: true };
          addNode(created);
          select(identifier);
          acceptContainer(created, snapshot);
          setNetwork((list) => linkDockerNode(list, identifier, config));
          break;
        }
        case 'container-config': {
          const snapshot = await dockerOperation(await requestLocal('containers/' + encode(node.id), { action: 'config', config: JSON.parse(data.config) }));
          acceptContainer(node, snapshot);
          setNetwork((list) => linkDockerNode(list, node.id, snapshot.serviceConfig));
          break;
        }
        case 'settings': {
          const current = readersRef.current[node.id].config;
          const config = { ...current, readerId: data.readerId, queueSize: Number(data.queueSize), httpEnabled: data.httpEnabled === 'on', streamEnabled: data.streamEnabled === 'on', token: data.token,
            allowNewDevices: data.allowNewDevices === 'on', allowNewSensors: data.allowNewSensors === 'on',
            managers: data.managerUrls.split(',').map((url) => url.trim()).filter(Boolean).map((url) => ({ url, token: data.managerToken })) };
          await readerCommand(node, { action: 'config', config, clearToken: data.clearToken === 'on' });
          updateNode(node.id, { managers: networkRef.current.filter((item) => item.kind === 'manager' && config.managers.some((target) => target.url === dockerEndpoint(item))).map((item) => item.id) });
          break;
        }
        case 'device': await readerCommand(node, { action: 'device', ...data }); break;
        case 'sensor': await readerCommand(node, { action: 'sensor', deviceId: device, ...data }); break;
        case 'pulse': await readerCommand(node, { action: 'pulse', deviceId: device, sensorId: sensor, value: Number(data.value), count: Number(submitter?.value || 1) }); break;
        default: break;
      }
      toast(opText('Acción aplicada', 'Action applied'));
      setEpoch((value) => value + 1);
      return true;
    } catch (error) {
      if (type === 'deploy-container') throw error;
      toast(error.message);
      return false;
    } finally {
      busy.current = false;
      if (submitter) submitter.disabled = false;
    }
  }, [acceptContainer, addNode, dockerOperation, networkRef, opText, readerCommand, readersRef, select, setNetwork, toast, updateNode]);

  const dockerAction = useCallback(async (node, action) => {
    if (busy.current) return;
    busy.current = true;
    toast(opText('Ejecutando operación Docker…', 'Running Docker operation…'));
    try {
      const snapshot = await dockerOperation(await requestLocal('containers/' + encode(node.id), { action }));
      if (snapshot.removed) {
        setContainers((map) => without(map, node.id));
        setReaders((map) => without(map, node.id));
        removeNode(node.id);
      } else acceptContainer(node, snapshot);
    } catch (error) {
      toast(error.message);
    } finally {
      busy.current = false;
    }
  }, [acceptContainer, dockerOperation, opText, removeNode, setContainers, setReaders, toast]);

  const readerAction = useCallback(async (node, action, deviceId, sensorId) => {
    if (busy.current) return;
    busy.current = true;
    try { await readerCommand(node, { action, deviceId, sensorId }); } catch (error) { toast(error.message); } finally { busy.current = false; }
  }, [readerCommand, toast]);

  const actions = useMemo(() => ({
    checkNode,
    submitForm,
    dockerAction,
    readerAction,
    isBusy: () => busy.current,
    setStage,
    toggleStage: (kind) => setStage((value) => (value === kind ? 'all' : kind)),
    clearLogs: () => setLogs([]),
    setToken: (id, value) => tokens.current.set(id, value),
    downloadConfig: (node) => download(configName(node), JSON.stringify(configFor(node, networkRef.current), null, 2)),
    removeFromView: (node) => { removeNode(node.id); toast(t('toast.removed')); },
  }), [checkNode, dockerAction, networkRef, readerAction, removeNode, setLogs, submitForm, t, toast]);

  const value = useMemo(() => ({ readers, containers, logs, errors, active, stage, epoch, ...actions }),
    [readers, containers, logs, errors, active, stage, epoch, actions]);

  return <OperatorContext.Provider value={value}>{children}</OperatorContext.Provider>;
}

export function useOperator() {
  const context = useContext(OperatorContext);
  if (!context) throw new Error('useOperator necesita un OperatorProvider');
  return context;
}
