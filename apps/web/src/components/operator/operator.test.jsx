import { describe, expect, it } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { PageShell } from '../PageShell.jsx';
import { I18nProvider } from '../../providers/I18nProvider.jsx';
import { NetworkProvider } from '../../providers/NetworkProvider.jsx';
import { OperatorProvider } from '../../providers/OperatorProvider.jsx';
import { PaymentsProvider } from '../../providers/PaymentsProvider.jsx';
import { ToastProvider } from '../../providers/ToastProvider.jsx';
import { mockFetch } from '../../test/fakes.js';
import { DeployDialogProvider } from './DeployDialog.jsx';
import { OperatorView } from './OperatorView.jsx';

function renderOperator() {
  return render(
    <I18nProvider defaultLang="es">
      <ToastProvider><PaymentsProvider><NetworkProvider><OperatorProvider><DeployDialogProvider>
        <PageShell><OperatorView /></PageShell>
      </DeployDialogProvider></OperatorProvider></NetworkProvider></PaymentsProvider></ToastProvider>
    </I18nProvider>,
  );
}

const pointer = (element) => {
  fireEvent.pointerDown(element, { button: 0, pointerId: 1 });
  fireEvent.pointerUp(element, { button: 0, pointerId: 1 });
};

describe('consola del operador', () => {
  it('pinta la red de demo, consulta cada servicio y muestra sus logs', async () => {
    const calls = mockFetch({ local: (path, body) => (path === 'probe' && body.path === '/logs' ? [`${body.url} started`] : []) });
    const { container } = renderOperator();
    const nodes = () => [...container.querySelectorAll('.service-node')].map((n) => n.dataset.serviceId);
    expect(nodes()).toEqual(['reader-1', 'manager-1', 'verifier-1', 'storage-1', 'publisher-1', 'contract']);
    expect(container.querySelectorAll('.canvas__edges g')).toHaveLength(5);

    await waitFor(() => expect(container.querySelectorAll('.service-node__status[data-status="up"]').length).toBeGreaterThanOrEqual(5));
    expect(calls.some((c) => c.url === '/api/local/probe' && c.body.url === 'http://localhost:7105')).toBe(true);
    expect(container.querySelector('.op-terminal').textContent).toContain('http://localhost:7101 started');
    expect(screen.getByText('6 servicios')).toBeTruthy();
  });

  it('seleccionar un nodo muestra su inspector y se puede quitar de la vista', async () => {
    mockFetch({ local: () => [] });
    const { container } = renderOperator();
    expect(container.querySelector('.inspector--summary')).toBeTruthy();

    pointer(container.querySelector('[data-service-id="verifier-1"]'));
    const sidebar = container.querySelector('.service-network__sidebar');
    expect(sidebar.querySelector('.inspector__head h2').textContent).toBe('verifier');
    expect(container.querySelector('[data-service-id="verifier-1"]').getAttribute('aria-pressed')).toBe('true');

    fireEvent.click(screen.getByText('Quitar de la vista'));
    expect(container.querySelector('[data-service-id="verifier-1"]')).toBeNull();
    expect(container.querySelector('#toast').textContent).toBe('Nodo quitado');
    expect(JSON.parse(localStorage.getItem('phonendo.network.v2')).map((n) => n.id)).not.toContain('verifier-1');
  });

  it('el token de un servicio se guarda y no se queda en el campo', async () => {
    const calls = mockFetch({ local: () => [] });
    const { container } = renderOperator();
    pointer(container.querySelector('[data-service-id="storage-1"]'));
    const input = container.querySelector('[data-service-token="storage-1"]');
    fireEvent.change(input, { target: { value: 'secreto' } });
    fireEvent.blur(input);
    expect(input.value).toBe('');
    await act(async () => { fireEvent.click(screen.getByText('Consultar ahora')); });
    await waitFor(() => expect(calls.some((c) => c.body?.token === 'secreto')).toBe(true));
  });

  it('el diálogo despliega un contenedor y lo selecciona', async () => {
    const calls = mockFetch({ local: (path, body, method) => {
      if (path === 'containers' && method === 'POST') return { id: 'op-1', state: 'succeeded', result: { state: 'running', url: 'http://localhost:9100', dockerUrl: 'http://reader-x:3002', image: body.image, serviceConfig: body.config } };
      return [];
    } });
    const { container } = renderOperator();
    fireEvent.click(screen.getByText('+ Añadir servicio'));
    const dialog = container.querySelector('#node-dialog');
    expect(dialog.hasAttribute('open')).toBe(true);
    expect(dialog.querySelector('[data-deploy-kind="reader"]').getAttribute('aria-pressed')).toBe('true');

    fireEvent.click(dialog.querySelector('[data-deploy-kind="manager"]'));
    expect(dialog.querySelector('input[name="containerPort"]').value).toBe('3003');
    expect(dialog.querySelector('input[name="image"]').value).toBe('phonendo-web-manager:local');

    await act(async () => { fireEvent.submit(dialog.querySelector('form')); });
    await waitFor(() => expect(dialog.hasAttribute('open')).toBe(false));
    const request = calls.find((c) => c.url === '/api/local/containers' && c.method === 'POST');
    expect(request.body.kind).toBe('manager');
    expect(request.body.build).toBe(true);
    const created = container.querySelector(`[data-service-id="${request.body.id}"]`);
    expect(created.getAttribute('aria-pressed')).toBe('true');
    expect(container.querySelector('#toast').textContent).toBe('Acción aplicada');
  });

  it('un JSON inválido en el diálogo se explica sin cerrarlo', async () => {
    mockFetch({ local: () => [] });
    const { container } = renderOperator();
    fireEvent.click(screen.getByText('+ Añadir servicio'));
    const dialog = container.querySelector('#node-dialog');
    fireEvent.change(dialog.querySelector('textarea[name="config"]'), { target: { value: '{ roto' } });
    await act(async () => { fireEvent.submit(dialog.querySelector('form')); });
    expect(dialog.hasAttribute('open')).toBe(true);
    expect(dialog.querySelector('#op-dialog-error').textContent).not.toBe('');
  });

  it('los logs se filtran por servicio, nivel y texto, y se pueden limpiar', async () => {
    mockFetch({ local: (path, body) => (path === 'probe' ? [`${body.url.slice(-4)} event_received`, ...(body.url.endsWith('7105') ? ['publisher_session_failed'] : [])] : []) });
    const { container } = renderOperator();
    await waitFor(() => expect(container.querySelectorAll('.log-row')).toHaveLength(6));
    fireEvent.change(container.querySelector('#op-log-filter'), { target: { value: 'verifier-1' } });
    expect(container.querySelectorAll('.log-row')).toHaveLength(1);
    fireEvent.change(container.querySelector('#op-log-filter'), { target: { value: 'all' } });
    fireEvent.click(container.querySelector('[data-level="error"]'));
    expect([...container.querySelectorAll('.log-row__message')].map((row) => row.textContent)).toEqual(['publisher_session_failed']);
    expect(container.querySelector('.log-row--error')).toBeTruthy();
    fireEvent.click(container.querySelector('[data-level="error"]'));
    fireEvent.change(container.querySelector('.logs__search input'), { target: { value: '7102' } });
    expect(container.querySelectorAll('.log-row')).toHaveLength(1);
    fireEvent.change(container.querySelector('.logs__search input'), { target: { value: 'nada que coincida' } });
    expect(container.querySelector('.log-empty h3').textContent).toBe('Nada coincide con el filtro');
    fireEvent.click(screen.getByText('Limpiar vista'));
    expect(container.querySelector('.log-empty h3').textContent).toBe('Esperando actividad');
  });

  it('las peticiones HTTP de rutina se ocultan y los mensajes repetidos se agrupan', async () => {
    mockFetch({ local: (path, body) => (path === 'probe' && body.url.endsWith('7102') ? ['request', 'event_received', 'event_received', 'request'] : []) });
    const { container } = renderOperator();
    await waitFor(() => expect(container.querySelectorAll('.log-row')).toHaveLength(1));
    expect(container.querySelector('.log-row__message').textContent).toBe('event_received×2');
    fireEvent.click(screen.getByText('Mostrar 2 peticiones HTTP'));
    expect([...container.querySelectorAll('.log-row__message')].map((row) => row.textContent)).toEqual(['request', 'event_received×2', 'request']);
    fireEvent.click(screen.getByText('Ocultar peticiones HTTP'));
    expect(container.querySelectorAll('.log-row')).toHaveLength(1);
  });

  it('pulsar el servicio de un log lo selecciona en el mapa', async () => {
    mockFetch({ local: (path, body) => (path === 'probe' ? [`${body.url.slice(-4)} event_received`] : []) });
    const { container } = renderOperator();
    await waitFor(() => expect(container.querySelectorAll('.log-row')).toHaveLength(5));
    const row = [...container.querySelectorAll('.log-row')].find((item) => item.textContent.includes('7103'));
    fireEvent.click(row.querySelector('.log-row__service'));
    expect(container.querySelector('[data-service-id="verifier-1"]').getAttribute('aria-pressed')).toBe('true');
    expect(container.querySelector('.log-row.is-related').textContent).toContain('7103');
  });

  it('un error reciente se ve en el nodo, en el inspector y lleva a sus logs', async () => {
    let failed = false;
    mockFetch({ local: (path, body) => {
      if (path !== 'probe') return [];
      if (body.url.endsWith('7105')) return failed ? ['started', 'publisher_session_failed'] : ['started'];
      return ['started'];
    } });
    const { container } = renderOperator();
    const publisher = () => container.querySelector('[data-service-id="publisher-1"]');
    await waitFor(() => expect(publisher().className).toContain('service-node--healthy'));
    pointer(publisher());
    failed = true;
    await act(async () => { fireEvent.click(screen.getByText('Consultar ahora')); });
    await waitFor(() => expect(publisher().className).toContain('service-node--degraded'));
    expect(publisher().querySelector('.service-node__activity--error').textContent).toBe('publisher_session_failed');
    const callout = container.querySelector('.callout--warning');
    expect(callout.textContent).toContain('publisher_session_failed');
    fireEvent.click(within(callout).getByText(/Ver logs relacionados/));
    expect(container.querySelector('#op-log-filter').value).toBe('publisher-1');
    expect(container.querySelector('.filter-chip').textContent).toContain('publisher');
  });

  it('un servicio caído marca sus conexiones y aparece en el resumen', async () => {
    mockFetch({ local: (path, body) => {
      if (path === 'probe' && body.url.endsWith('7103')) throw new Error('connection refused');
      return path === 'probe' ? ['started'] : [];
    } });
    const { container } = renderOperator();
    await waitFor(() => expect(container.querySelector('[data-service-id="verifier-1"]').className).toContain('service-node--error'));
    const edge = container.querySelector('[data-edge-id="manager-1:verifier-1:http"]');
    expect(edge.getAttribute('class')).toContain('edge--error');
    expect(edge.querySelector('.edge__break')).toBeTruthy();
    expect(container.querySelector('.inspector--summary h2').textContent).toBe('Necesita atención');
    fireEvent.click(within(container.querySelector('.attention-list')).getByText('verifier'));
    expect(container.querySelector('.callout--error').textContent).toContain('connection refused');
  });

  it('seleccionar una conexión muestra su tipo, estado y extremos', async () => {
    mockFetch({ local: (path) => (path === 'probe' ? ['started'] : []) });
    const { container } = renderOperator();
    await waitFor(() => expect(container.querySelectorAll('.service-node--healthy').length).toBeGreaterThanOrEqual(5));
    expect(container.querySelector('[data-edge-id="manager-1:publisher-1:sse"]').getAttribute('class')).toContain('edge--sse');
    pointer(container.querySelector('[data-edge-id="manager-1:publisher-1:sse"] .edge__hit'));
    const inspector = container.querySelector('.service-network__sidebar .inspector');
    expect(inspector.querySelector('h2').textContent).toBe('manager → publisher');
    expect(inspector.querySelector('.stream-badge')).toBeTruthy();
    expect(container.querySelector('[data-edge-id="manager-1:publisher-1:sse"]').getAttribute('class')).toContain('edge--selected');
    fireEvent.click(within(inspector).getByText('publisher'));
    expect(container.querySelector('[data-service-id="publisher-1"]').getAttribute('aria-pressed')).toBe('true');
  });

  it('todos los componentes ofrecen modo visual y JSON con texto escapado', async () => {
    mockFetch({ local: () => [] });
    const { container } = renderOperator();
    for (const kind of ['reader', 'manager', 'verifier', 'storage', 'publisher']) {
      pointer(container.querySelector(`[data-service-id="${kind}-1"]`));
      const form = container.querySelector('[data-config-editor]');
      expect(within(form).getByRole('button', { name: 'Visual' }).getAttribute('aria-pressed')).toBe('true');
      expect(form.querySelector('textarea')).toBeNull();
      fireEvent.click(within(form).getByRole('button', { name: 'JSON' }));
      const json = form.querySelector('textarea');
      fireEvent.change(json, { target: { value: JSON.stringify({ readerId: '<script>', managerId: '<script>' }) } });
      fireEvent.click(within(form).getByRole('button', { name: 'Visual' }));
      expect(form.querySelector('script')).toBeNull();
      if (['reader', 'manager'].includes(kind)) expect([...form.querySelectorAll('input')].some((input) => input.value === '<script>')).toBe(true);
    }
  });

  it('Visual y JSON conservan el borrador al cambiar de nodo y rechazan JSON inválido', async () => {
    mockFetch({ local: () => [] });
    const { container } = renderOperator();
    pointer(container.querySelector('[data-service-id="manager-1"]'));
    let form = container.querySelector('[data-config-editor]');
    fireEvent.change(within(form).getByLabelText('Identidad del Manager'), { target: { value: 'sin guardar' } });
    fireEvent.click(within(form).getByRole('button', { name: 'JSON' }));
    expect(JSON.parse(form.querySelector('textarea').value).managerId).toBe('sin guardar');
    pointer(container.querySelector('[data-service-id="storage-1"]'));
    pointer(container.querySelector('[data-service-id="manager-1"]'));
    form = container.querySelector('[data-config-editor]');
    expect(JSON.parse(form.querySelector('textarea').value).managerId).toBe('sin guardar');
    fireEvent.change(form.querySelector('textarea'), { target: { value: '{ roto' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Visual' }));
    expect(form.querySelector('textarea')).not.toBeNull();
    expect(within(form).getByRole('alert').textContent).not.toBe('');
  });

  it('el Manager guarda la configuración completa y permite reintentar tras un error', async () => {
    const snapshot = { id: 'managed-config', kind: 'manager', name: 'managed-config', state: 'running', url: 'http://localhost:9000', dockerUrl: 'http://managed-config:3003', image: 'test:local',
      serviceConfig: { managerId: 'original', services: { verifiers: [{ url: 'http://verifier:5000', token: '••••••' }] }, extension: { keep: true } } };
    let fail = true;
    const calls = mockFetch({ local: (path, body, method) => {
      if (path === 'containers') return [snapshot];
      if (path === 'containers/managed-config') {
        if (method === 'POST') { if (fail) throw Error('No se pudo reiniciar'); return { state: 'succeeded', result: { ...snapshot, serviceConfig: body.config } }; }
        return snapshot;
      }
      return [];
    } });
    const { container } = renderOperator();
    await waitFor(() => expect(container.querySelector('[data-service-id="managed-config"]')).toBeTruthy());
    pointer(container.querySelector('[data-service-id="managed-config"]'));
    const form = container.querySelector('[data-config-editor]');
    fireEvent.change(within(form).getByLabelText('Identidad del Manager'), { target: { value: 'editado' } });
    await act(async () => { fireEvent.submit(form); });
    expect(within(form).getByRole('alert').textContent).toBe('No se pudo reiniciar');
    expect(within(form).getByLabelText('Identidad del Manager').value).toBe('editado');
    fail = false;
    await act(async () => { fireEvent.submit(form); });
    const request = calls.filter((call) => call.url === '/api/local/containers/managed-config' && call.method === 'POST').at(-1);
    expect(request.body).toEqual({ action: 'config', config: { ...snapshot.serviceConfig, managerId: 'editado' } });
    expect(within(form).getByRole('alert').textContent).toBe('');
    expect(localStorage.getItem('phonendo.network.v2')).not.toContain('••••••');
  });

  it('Reader aplica HTTP y tokens por destino en directo sin perder sus dispositivos', async () => {
    const snapshot = { id: 'live-reader', kind: 'reader', name: 'live-reader', state: 'running', url: 'http://localhost:9001', dockerUrl: 'http://live-reader:3002', image: 'test:local', serviceConfig: {},
      bootId: 'boot', events: [], devices: [{ id: 'band', sensors: [] }], config: { readerId: 'live-reader', httpEnabled: true, streamEnabled: false, queueSize: 256, token: '', managers: [{ url: 'http://manager:3003', token: '' }] } };
    const calls = mockFetch({ local: (path, body, method) => {
      if (path === 'containers') return [snapshot];
      if (path === 'containers/live-reader') return snapshot;
      if (path === 'readers/live-reader' && method === 'POST') return { ...snapshot, config: body.config };
      return [];
    } });
    const { container } = renderOperator();
    await waitFor(() => expect(container.querySelector('[data-service-id="live-reader"]')).toBeTruthy());
    pointer(container.querySelector('[data-service-id="live-reader"]'));
    const form = container.querySelector('[data-config-editor]');
    fireEvent.click(within(form).getByLabelText('Enviar por HTTP'));
    fireEvent.change(within(form).getByLabelText('Token de acceso'), { target: { value: 'peer-token' } });
    await act(async () => { fireEvent.submit(form); });
    const request = calls.find((call) => call.url === '/api/local/readers/live-reader');
    expect(request.body.config.httpEnabled).toBe(false);
    expect(request.body.config.managers[0].token).toBe('peer-token');
    expect(container.querySelector('.device-tile').textContent).toContain('band');
    expect(localStorage.getItem('phonendo.network.v2')).not.toContain('peer-token');
  });
});
