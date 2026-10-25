import { createRoot } from 'react-dom/client';
import { IconSprite } from '../components/Icon.jsx';
import { PageShell } from '../components/PageShell.jsx';
import { CONFIG } from '../config.js';
import { DeployDialogProvider } from '../components/operator/DeployDialog.jsx';
import { OperatorView } from '../components/operator/OperatorView.jsx';
import { I18nProvider } from '../providers/I18nProvider.jsx';
import { NetworkProvider } from '../providers/NetworkProvider.jsx';
import { OperatorProvider } from '../providers/OperatorProvider.jsx';
import { PaymentsProvider } from '../providers/PaymentsProvider.jsx';
import { ToastProvider } from '../providers/ToastProvider.jsx';

createRoot(document.getElementById('root')).render(
  <>
    <IconSprite />
    <I18nProvider defaultLang="es">
      <ToastProvider>
        <PaymentsProvider>
          <NetworkProvider>
            <OperatorProvider>
              <DeployDialogProvider>
                <PageShell nav={[{ href: CONFIG.panels.company, label: 'nav.company', icon: 'building' }]}><OperatorView /></PageShell>
              </DeployDialogProvider>
            </OperatorProvider>
          </NetworkProvider>
        </PaymentsProvider>
      </ToastProvider>
    </I18nProvider>
  </>,
);
