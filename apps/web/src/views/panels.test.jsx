import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { PageShell } from '../components/PageShell.jsx';
import { I18nProvider } from '../providers/I18nProvider.jsx';
import { PaymentsProvider } from '../providers/PaymentsProvider.jsx';
import { ToastProvider } from '../providers/ToastProvider.jsx';
import { CONFIG } from '../config.js';
import { mockFetch, paidEvent } from '../test/fakes.js';
import { ColdChainView } from './ColdChainView.jsx';
import { InsurerView } from './InsurerView.jsx';
import { PatientView } from './PatientView.jsx';

function renderPanel(view, defaultLang = 'en') {
  return render(
    <I18nProvider defaultLang={defaultLang}>
      <ToastProvider><PaymentsProvider><PageShell>{view}</PageShell></PaymentsProvider></ToastProvider>
    </I18nProvider>,
  );
}

describe('paneles de pagos', () => {
  it('la aseguradora ve los pagos en directo con su transacción', async () => {
    mockFetch();
    const { container } = renderPanel(<InsurerView />);
    await waitFor(() => expect(container.querySelector('#net-pill').dataset.state).toBe('live'));
    expect(container.querySelector('#net-label').textContent).toBe('Stellar testnet · live');
    const link = container.querySelector('tbody a');
    expect(link.getAttribute('href')).toBe(`https://stellar.expert/explorer/testnet/tx/${paidEvent().txHash}`);
    expect(container.querySelector('tbody td.mono').textContent).toBe('20261025001');
    expect(container.querySelector('.notice')).toBeNull();
  });

  it('sin RPC muestra los cobros confirmados y avisa', async () => {
    mockFetch({ events: null });
    const { container } = renderPanel(<InsurerView />);
    await waitFor(() => expect(container.querySelector('#net-pill').dataset.state).toBe('error'));
    expect(container.querySelector('.notice')).toBeTruthy();
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
    const { container } = renderPanel(<InsurerView />);
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
    renderPanel(<InsurerView />, 'es');
    expect(document.documentElement.lang).toBe('es');
  });
});

describe('panel de rehabilitación', () => {
  it('no cuenta los cobros de la cadena de frío', async () => {
    mockFetch({ events: [paidEvent(), paidEvent({ id: 'frio', contractId: CONFIG.contracts[1].id })] });
    const { container } = renderPanel(<PatientView />);
    await waitFor(() => expect(container.querySelectorAll('tbody tr')).toHaveLength(1));
  });

  it('dibuja el aro de la sesión con las 32 lecturas', () => {
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
