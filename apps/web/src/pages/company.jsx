import { createRoot } from 'react-dom/client';
import { IconSprite } from '../components/Icon.jsx';
import { PageShell } from '../components/PageShell.jsx';
import { CONFIG } from '../config.js';
import { I18nProvider } from '../providers/I18nProvider.jsx';
import { PaymentsProvider } from '../providers/PaymentsProvider.jsx';
import { ToastProvider } from '../providers/ToastProvider.jsx';
import { CompanyView } from '../views/CompanyView.jsx';

createRoot(document.getElementById('root')).render(
  <>
    <IconSprite />
    <I18nProvider defaultLang="en">
      <ToastProvider>
        <PaymentsProvider>
          <PageShell nav={[{ href: CONFIG.panels.operator, label: 'nav.control', icon: 'hub' }]}><CompanyView /></PageShell>
        </PaymentsProvider>
      </ToastProvider>
    </I18nProvider>
  </>,
);
