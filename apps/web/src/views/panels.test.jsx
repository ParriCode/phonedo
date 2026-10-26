import { describe, expect, it } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { PageShell } from '../components/PageShell.jsx';
import { I18nProvider } from '../providers/I18nProvider.jsx';
import { PaymentsProvider } from '../providers/PaymentsProvider.jsx';
import { ToastProvider } from '../providers/ToastProvider.jsx';
import { CONFIG } from '../config.js';
import { mockFetch, paidEvent } from '../test/fakes.js';
import { ColdChainView } from './ColdChainView.jsx';
import { CompanyView } from './CompanyView.jsx';
import { PatientView } from './PatientView.jsx';

function renderPanel(view, defaultLang = 'en', nav = []) {
  return render(
    <I18nProvider defaultLang={defaultLang}>
      <ToastProvider><PaymentsProvider><PageShell nav={nav}>{view}</PageShell></PaymentsProvider></ToastProvider>
    </I18nProvider>,
  );
}

describe('paneles de pagos', () => {
  it('el logo vuelve a la portada', () => {
    mockFetch();
    const { container } = renderPanel(<CompanyView />);
    expect(container.querySelector('.brand').getAttribute('href')).toBe('index.html');
  });

  it('la empresa ve los pagos en directo con su transacción', async () => {
    mockFetch();
    const { container } = renderPanel(<CompanyView />);
    await waitFor(() => expect(container.querySelectorAll('tbody tr')).toHaveLength(1));
    expect(container.querySelector('#net-pill')).toBeNull();
    const link = container.querySelector('tbody a');
    expect(link.getAttribute('href')).toBe(`https://stellar.expert/explorer/testnet/tx/${paidEvent().txHash}`);
    expect(container.querySelector('tbody td.mono').textContent).toBe('20261025001');
    expect(container.querySelector('.notice')).toBeNull();
  });

  it('sin RPC muestra los cobros confirmados y avisa', async () => {
    mockFetch({ events: null });
    const { container } = renderPanel(<CompanyView />);
    await waitFor(() => expect(container.querySelector('.notice')).toBeTruthy());
    expect(container.querySelector('#net-pill')).toBeNull();
    expect(container.querySelectorAll('tbody tr')).toHaveLength(5);
  });

  it('la paciente valida la cuenta y solo ve sus pagos', async () => {
    mockFetch({ events: [paidEvent(), paidEvent({ id: 'otro', valueJson: { map: [
      { key: { symbol: 'amount' }, val: { i128: '50000000' } },
      { key: { symbol: 'patient' }, val: { address: 'GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5' } },
    ] } })] });
    const { container } = renderPanel(<PatientView />);
    await waitFor(() => expect(container.querySelectorAll('tbody tr')).toHaveLength(1));
    const input = container.querySelector('#patient-account');
    const error = container.querySelector('#patient-error');
    expect(error.hidden).toBe(true);

    fireEvent.change(input, { target: { value: 'no-es-una-cuenta' } });
    fireEvent.submit(container.querySelector('#patient-form'));
    expect(error.hidden).toBe(false);

    fireEvent.change(input, { target: { value: 'GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5' } });
    fireEvent.submit(container.querySelector('#patient-form'));
    expect(container.querySelector('#patient-error').hidden).toBe(true);
    expect(container.querySelectorAll('tbody tr')).toHaveLength(1);
    expect(screen.getByText('GBBD4…FLA5')).toBeTruthy();
  });

  it('el idioma se guarda y cambia toda la página', async () => {
    mockFetch();
    const { container } = renderPanel(<CompanyView />);
    expect(document.documentElement.lang).toBe('en');
    fireEvent.click(container.querySelector('[data-lang="es"]'));
    expect(document.documentElement.lang).toBe('es');
    expect(localStorage.getItem('phonendo.lang')).toBe('es');
    expect(container.querySelector('[data-lang="es"]').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('Pagos verificados')).toBeTruthy();
    expect(container.querySelector('[data-i18n="footer.built"]').textContent).toBe('Construido sobre Stellar testnet');
  });

  it('la consola abre en español salvo que se haya elegido inglés', () => {
    mockFetch();
    renderPanel(<CompanyView />, 'es');
    expect(document.documentElement.lang).toBe('es');
  });
});

describe('panel de rehabilitación', () => {
  it('no cuenta los cobros de la cadena de frío', async () => {
    mockFetch({ events: [paidEvent(), paidEvent({ id: 'frio', contractId: CONFIG.contracts[1].id })] });
    const { container } = renderPanel(<PatientView />);
    await waitFor(() => expect(container.querySelectorAll('tbody tr')).toHaveLength(1));
  });

  it('dibuja el aro de la sesión con las lecturas del lote', () => {
    mockFetch();
    const { container } = renderPanel(<PatientView />);
    expect(container.querySelectorAll('.ring line')).toHaveLength(CONFIG.policy.batch);
  });
});

describe('panel de cadena de frío', () => {
  it('solo muestra los cobros de su contrato y dibuja termómetro y aro', async () => {
    mockFetch({ events: [paidEvent(), paidEvent({ id: 'frio', contractId: CONFIG.contracts[1].id })] });
    const { container } = renderPanel(<ColdChainView />);
    await waitFor(() => expect(container.querySelectorAll('tbody tr')).toHaveLength(1));
    expect(container.querySelector('.thermo')).toBeTruthy();
    expect(container.querySelectorAll('.ring line')).toHaveLength(CONFIG.coldPolicy.batch);
    expect(screen.getByText('Cold-chain transport')).toBeTruthy();
  });
});

describe('panel de empresa', () => {
  it('reparte los pagos por caso de uso y enlaza a cada panel', async () => {
    mockFetch({ events: [paidEvent(), paidEvent({ id: 'frio', contractId: CONFIG.contracts[1].id })] });
    const { container } = renderPanel(<CompanyView />);
    await waitFor(() => expect(container.querySelectorAll('tbody tr')).toHaveLength(2));
    const rehab = container.querySelector('[data-case="rehab"]');
    const cold = container.querySelector('[data-case="cold-chain"]');
    expect(rehab.textContent).toContain('Sessions paid: 1');
    expect(cold.textContent).toContain('Shipments paid: 1');
    expect(rehab.querySelector('a.case-open').getAttribute('href')).toBe('patient.html');
    expect(cold.querySelector('a.case-open').getAttribute('href')).toBe('coldchain.html');
  });

  it('ignora los pagos de contratos que no son suyos', async () => {
    mockFetch({ events: [paidEvent({ contractId: 'CAJENO' })] });
    let container;
    await act(async () => { ({ container } = renderPanel(<CompanyView />)); });
    expect(container.querySelectorAll('tbody tr')).toHaveLength(0);
  });
});

describe('barra superior', () => {
  it('muestra los enlaces a otros paneles', () => {
    mockFetch();
    const { container } = renderPanel(<CompanyView />, 'en', [{ href: 'company.html', label: 'nav.company', icon: 'building' }]);
    const link = container.querySelector('.topbar-link');
    expect(link.getAttribute('href')).toBe('company.html');
    expect(link.textContent).toBe('Companies');
  });
});
