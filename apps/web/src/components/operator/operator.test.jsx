import { describe, expect, it } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { PageShell } from '../PageShell.jsx';
import { I18nProvider } from '../../providers/I18nProvider.jsx';
import { NetworkProvider } from '../../providers/NetworkProvider.jsx';
import { OperatorProvider } from '../../providers/OperatorProvider.jsx';
import { PaymentsProvider } from '../../providers/PaymentsProvider.jsx';
import { ToastProvider } from '../../providers/ToastProvider.jsx';
import { mockFetch as baseMockFetch } from '../../test/fakes.js';
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

const pointer = async (find) => {
  const element = await waitFor(() => {
    const found = find();
    expect(found).toBeTruthy();
    return found;
  });
  fireEvent.pointerDown(element, { button: 0, pointerId: 1 });
  fireEvent.pointerUp(element, { button: 0, pointerId: 1 });
};

const services = ['reader', 'manager', 'verifier', 'storage', 'publisher'];
const ports = [7101, 7102, 7103, 7104, 7105];
const inventory = services.map((kind, index) => ({ id: `${kind}-1`, kind, name: kind === 'reader' ? 'reader-docker' : kind,
  image: `phonendo-${kind}:local`, state: 'running', url: `http://localhost:${ports[index]}`,
  dockerUrl: `http://${kind}:${[3002, 3003, 5000, 5000, 3005][index]}`,
  serviceConfig: kind === 'reader' ? { services: { managers: [{ url: 'http://manager:3003', token: '' }] } }
    : kind === 'publisher' ? { subscriptions: { managers: ['http://manager:3003'] } }
      : kind === 'manager' ? { services: { verifiers: ['http://verifier:5000'], storages: ['http://storage:5000'] } } : {} }));

function mockFetch({ local = () => [], inventory: available = inventory, ...rest } = {}) {
  return baseMockFetch({ ...rest, local: (path, body, method) => {
    if (path === 'containers' && method === 'GET') {
      const reply = local(path, body, method);
      return Array.isArray(reply) && reply.length ? reply : available;
    }
    const snapshot = available.find((item) => path === `containers/${item.id}` || path === `containers/${item.id}/logs`);
    if (snapshot && path.endsWith('/logs')) return local('probe', { url: snapshot.url, path: '/logs' }, 'POST');
    if (snapshot && method === 'GET') return snapshot;
    return local(path, body, method);
  } });
}

describe('consola del operador', () => {
  it('no inventa tarjetas si Docker no devuelve contenedores', () => {
    mockFetch({ inventory: [] });
    const { container } = renderOperator();
    expect(container.querySelectorAll('.service-node')).toHaveLength(0);
    expect(container.querySelector('.canvas__empty').hidden).toBe(false);
  });

  it('no confunde imágenes sin contenedor con servicios del canvas', async () => {
    const calls = mockFetch({ inventory: [], local: (path) => path === 'images' ? [{
      id: 'image-reader', kind: 'reader', name: 'phonendo-reader:latest', image: 'phonendo-reader:latest',
      imageSource: 'compose', imageOnly: true, state: 'image',
    }] : [] });
    const { container } = renderOperator();
    await waitFor(() => expect(container.querySelectorAll('.service-node')).toHaveLength(0));
    expect(calls.some((call) => call.url === '/api/local/images')).toBe(false);
  });

  it('construye la imagen desde la tarjeta del contenedor real', async () => {
    const calls = mockFetch({ local: (path) => {
      return path.startsWith('images/') ? { id: 'image-op', state: 'succeeded', result: {} } : [];
    } });
    const { container } = renderOperator();
    const card = await waitFor(() => {
      const found = container.querySelector('[data-service-id="verifier-1"]');
      expect(found).toBeTruthy();
      return found;
    });
    await act(async () => { fireEvent.click(card.querySelector('[data-node-action="build-image"]')); });
    expect(calls.some((call) => call.url === '/api/local/images/verifier' && call.method === 'POST')).toBe(true);
    expect(container.querySelector('.inspector--summary')).toBeTruthy();
  });

  it('muestra nombres breves, estado en el borde y controles accesibles por icono', async () => {
    mockFetch({ inventory: [{ ...inventory[0], name: 'phonendo-reader-1' }] });
    const { container } = renderOperator();
    const card = await waitFor(() => {
      const found = container.querySelector('[data-service-id="reader-1"]');
      expect(found).toBeTruthy(); return found;
    });
    expect(card.querySelector('.service-node__name').textContent).toBe('reader-1');
    expect(card.textContent).not.toContain('Operativo');
    expect(card.querySelector('.service-node__docker-state')).toBeNull();
    expect(card.querySelector('[data-node-action="stop"]').getAttribute('aria-label')).toBe('Parar');
    expect(card.querySelector('[data-node-action="restart"] svg')).toBeTruthy();
    expect(card.className).toContain('service-node--healthy');
    expect(card.getAttribute('aria-label')).toContain('phonendo-reader-1');
  });

  it('une tarjetas desde sus conectores y cambia HTTP por Stream en el cable', async () => {
    const calls = mockFetch({ local: (path) => path === 'connections' ? { id: 'connection-op', state: 'succeeded', result: {} } : [] });
    const { container } = renderOperator();
    const source = await waitFor(() => {
      const found = container.querySelector('[data-service-id="reader-1"] [data-port-out]');
      expect(found).toBeTruthy(); return found;
    });
    fireEvent.pointerDown(source, { button: 0, pointerId: 1, clientX: 20, clientY: 20 });
    fireEvent.click(container.querySelector('[data-service-id="manager-1"] [data-port-in]'));
    await waitFor(() => expect(calls.some((call) => call.url === '/api/local/connections' &&
      call.body?.sourceId === 'reader-1' && call.body?.targetId === 'manager-1' && call.body?.transport === 'http')).toBe(true));
    const toggle = container.querySelector('[data-edge-toggle="reader-1:manager-1:http"]');
    await act(async () => { fireEvent.click(toggle); });
    expect(calls.some((call) => call.url === '/api/local/connections' && call.body?.transport === 'sse')).toBe(true);
  });

  it('muestra el cable mientras se arrastra y conecta al soltar sobre otra tarjeta', async () => {
    const calls = mockFetch({ local: (path) => path === 'connections' ? { id: 'connection-op', state: 'succeeded', result: {} } : [] });
    const { container } = renderOperator();
    const source = await waitFor(() => {
      const found = container.querySelector('[data-service-id="reader-1"] [data-port-out]');
      expect(found).toBeTruthy(); return found;
    });
    const target = container.querySelector('[data-service-id="manager-1"]');
    const previous = document.elementFromPoint;
    document.elementFromPoint = () => target;
    try {
      fireEvent.pointerDown(source, { button: 0, pointerId: 2, clientX: 50, clientY: 50 });
      fireEvent.pointerMove(source, { pointerId: 2, clientX: 120, clientY: 90 });
      expect(container.querySelector('.edge__draft')).toBeTruthy();
      fireEvent.pointerUp(source, { pointerId: 2, clientX: 120, clientY: 90 });
      await waitFor(() => expect(calls.some((call) => call.url === '/api/local/connections' &&
        call.body?.sourceId === 'reader-1' && call.body?.targetId === 'manager-1')).toBe(true));
      expect(container.querySelector('.edge__draft')).toBeNull();
    } finally { document.elementFromPoint = previous; }
  });

  it('mueve un servicio desde el primer píxel del arrastre', async () => {
    mockFetch();
    const { container } = renderOperator();
    const card = await waitFor(() => {
      const found = container.querySelector('[data-service-id="reader-1"]');
      expect(found).toBeTruthy(); return found;
    });
    const before = card.style.transform;
    fireEvent.pointerDown(card, { button: 0, pointerId: 4, clientX: 50, clientY: 50 });
    fireEvent.pointerMove(card, { pointerId: 4, clientX: 51, clientY: 50 });
    expect(card.style.transform).not.toBe(before);
    fireEvent.pointerUp(card, { pointerId: 4, clientX: 51, clientY: 50 });
  });

  it('el interruptor del inspector revisa el transporte antes de aplicarlo', async () => {
    const calls = mockFetch({ local: (path) => path === 'connections' ? { id: 'connection-op', state: 'succeeded', result: {} } : [] });
    const { container } = renderOperator();
    await pointer(() => container.querySelector('[data-edge-id="reader-1:manager-1:http"] .edge__hit'));
    const inspector = container.querySelector('.inspector--edge');
    expect(inspector).toBeTruthy();
    fireEvent.click(within(inspector).getByRole('switch', { name: /Stream/ }));
    expect(inspector.textContent).toContain('Cambio pendiente: Stream SSE');
    expect(calls.some((call) => call.url === '/api/local/connections')).toBe(false);
    await act(async () => { fireEvent.click(within(inspector).getByRole('button', { name: 'Guardar cambio' })); });
    expect(calls.some((call) => call.url === '/api/local/connections' && call.body?.transport === 'sse')).toBe(true);
  });

  it('permite parar y eliminar desde la tarjeta de un contenedor gestionado', async () => {
    const snapshot = { id: 'managed-reader', kind: 'reader', name: 'managed-reader', state: 'running', url: 'http://localhost:9100', dockerUrl: 'http://managed-reader:3002', image: 'phonendo-web-reader:local' };
    const calls = mockFetch({ local: (path, body) => {
      if (path === 'containers') return [snapshot];
      if (path === 'containers/managed-reader') return { id: 'op-1', state: 'succeeded', result: body.action === 'remove' ? { removed: true } : { ...snapshot, state: 'exited' } };
      return [];
    } });
    const { container } = renderOperator();
    const card = () => container.querySelector('[data-service-id="managed-reader"]');
    await waitFor(() => expect(card()).toBeTruthy());
    fireEvent.click(card().querySelector('[data-node-action="stop"]'));
    await waitFor(() => expect(calls.some((call) => call.url === '/api/local/containers/managed-reader' && call.body?.action === 'stop')).toBe(true));
    await waitFor(() => expect(card().querySelector('[data-node-action="start"]')).toBeTruthy());
    const confirm = window.confirm;
    window.confirm = () => true;
    try {
      fireEvent.click(card().querySelector('[data-node-action="remove"]'));
      await waitFor(() => expect(card()).toBeNull());
    } finally { window.confirm = confirm; }
  });

  it('pinta el inventario Docker, consulta cada servicio y muestra sus logs', async () => {
    const calls = mockFetch({ local: (path, body) => (path === 'probe' && body.path === '/logs' ? [`${body.url} started`] : []) });
    const { container } = renderOperator();
    const nodes = () => [...container.querySelectorAll('.service-node')].map((n) => n.dataset.serviceId);
    await waitFor(() => expect(nodes()).toEqual(['reader-1', 'manager-1', 'verifier-1', 'storage-1', 'publisher-1']));
    expect(container.querySelectorAll('.canvas__edges g')).toHaveLength(4);

    await waitFor(() => expect(container.querySelectorAll('.service-node__status[data-status="up"]').length).toBeGreaterThanOrEqual(5));
    expect(calls.some((c) => c.url === '/api/local/containers/publisher-1/logs')).toBe(true);
    expect(container.querySelector('.op-terminal').textContent).toContain('http://localhost:7101 started');
    expect(screen.getByText('5 servicios')).toBeTruthy();
  });

  it('seleccionar un contenedor muestra su inspector sin guardar nodos falsos', async () => {
    mockFetch({ local: () => [] });
    const { container } = renderOperator();
    expect(container.querySelector('.inspector--summary')).toBeTruthy();

    await waitFor(() => expect(container.querySelector('[data-service-id="verifier-1"]')).toBeTruthy());
    await pointer(() => container.querySelector('[data-service-id="verifier-1"]'));
    const sidebar = container.querySelector('.service-network__sidebar');
    expect(sidebar.querySelector('.inspector__head h2').textContent).toBe('verifier');
    expect(container.querySelector('[data-service-id="verifier-1"]').getAttribute('aria-pressed')).toBe('true');

    expect(localStorage.getItem('phonendo.network.v2')).toBeNull();
  });

  it('permite revisar cambios visuales de un contenedor Compose antes de guardarlos', async () => {
    const snapshot = { ...inventory[1], id: 'compose-manager', name: 'phonendo-manager-1', compose: true,
      serviceConfig: { managerId: 'original', services: { verifiers: [] } } };
    const calls = mockFetch({ inventory: [snapshot], local: (path, body, method) => {
      if (path === 'containers/compose-manager' && method === 'POST') return { state: 'succeeded', result: { ...snapshot, serviceConfig: body.config } };
      return [];
    } });
    const { container } = renderOperator();
    await pointer(() => container.querySelector('[data-service-id="compose-manager"]'));
    const form = container.querySelector('[data-config-editor]');
    expect(form).toBeTruthy();
    const save = within(form).getByRole('button', { name: 'Guardar y reiniciar' });
    expect(save.disabled).toBe(true);
    fireEvent.change(within(form).getByLabelText('Identidad del Manager'), { target: { value: 'editado' } });
    expect(form.querySelector('.config-save__summary').textContent).toContain('1 ajuste pendiente');
    expect(save.disabled).toBe(false);
    await act(async () => { fireEvent.click(save); });
    expect(calls.some((call) => call.url === '/api/local/containers/compose-manager' && call.body?.config?.managerId === 'editado')).toBe(true);
  });

  it('consulta los logs Docker del servicio seleccionado', async () => {
    const calls = mockFetch({ local: () => [] });
    const { container } = renderOperator();
    await pointer(() => container.querySelector('[data-service-id="storage-1"]'));
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Consultar ahora' })); });
    await waitFor(() => expect(calls.some((c) => c.url === '/api/local/containers/storage-1/logs')).toBe(true));
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
      if (body.url.endsWith('7105')) return failed ? ['started', JSON.stringify({ level: 'ERROR', message: 'publisher_session_failed', error: 'Saldo insuficiente' })] : ['started'];
      return ['started'];
    } });
    const { container } = renderOperator();
    const publisher = () => container.querySelector('[data-service-id="publisher-1"]');
    await waitFor(() => expect(publisher().className).toContain('service-node--healthy'));
    await pointer(publisher);
    failed = true;
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Consultar ahora' })); });
    await waitFor(() => expect(publisher().className).toContain('service-node--degraded'));
    expect(publisher().querySelector('.service-node__activity--error').textContent).toBe('Saldo insuficiente');
    const callout = container.querySelector('.callout--warning');
    expect(callout.textContent).toContain('publisher_session_failed');
    expect(callout.textContent).toContain('Saldo insuficiente');
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
    await pointer(() => container.querySelector('[data-edge-id="manager-1:publisher-1:sse"] .edge__hit'));
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
    for (const kind of ['manager', 'verifier', 'storage', 'publisher']) {
      await pointer(() => container.querySelector(`[data-service-id="${kind}-1"]`));
      const form = container.querySelector('[data-config-editor]');
      expect(within(form).getByRole('button', { name: 'Visual' }).getAttribute('aria-pressed')).toBe('true');
      expect(form.querySelector('textarea')).toBeNull();
      fireEvent.click(within(form).getByRole('button', { name: 'JSON' }));
      const json = form.querySelector('textarea');
      fireEvent.change(json, { target: { value: JSON.stringify({ readerId: '<script>', managerId: '<script>' }) } });
      fireEvent.click(within(form).getByRole('button', { name: 'Visual' }));
      expect(form.querySelector('script')).toBeNull();
      if (kind === 'manager') expect([...form.querySelectorAll('input')].some((input) => input.value === '<script>')).toBe(true);
    }
  });

  it('Visual y JSON conservan el borrador al cambiar de nodo y rechazan JSON inválido', async () => {
    mockFetch({ local: () => [] });
    const { container } = renderOperator();
    await pointer(() => container.querySelector('[data-service-id="manager-1"]'));
    let form = container.querySelector('[data-config-editor]');
    fireEvent.change(within(form).getByLabelText('Identidad del Manager'), { target: { value: 'sin guardar' } });
    fireEvent.click(within(form).getByRole('button', { name: 'JSON' }));
    expect(JSON.parse(form.querySelector('textarea').value).managerId).toBe('sin guardar');
    await pointer(() => container.querySelector('[data-service-id="storage-1"]'));
    await pointer(() => container.querySelector('[data-service-id="manager-1"]'));
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
    await pointer(() => container.querySelector('[data-service-id="managed-config"]'));
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
    expect(localStorage.getItem('phonendo.network.v2')).toBeNull();
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
    await pointer(() => container.querySelector('[data-service-id="live-reader"]'));
    const form = container.querySelector('[data-config-editor]');
    fireEvent.click(within(form).getByLabelText('Enviar por HTTP'));
    fireEvent.change(within(form).getByLabelText('Token de acceso'), { target: { value: 'peer-token' } });
    await act(async () => { fireEvent.submit(form); });
    const request = calls.find((call) => call.url === '/api/local/readers/live-reader');
    expect(request.body.config.httpEnabled).toBe(false);
    expect(request.body.config.managers[0].token).toBe('peer-token');
    expect(container.querySelector('.device-tile').textContent).toContain('band');
    expect(localStorage.getItem('phonendo.network.v2')).toBeNull();
  });
});
