import { createRoot } from 'react-dom/client';
import { IconSprite } from '../components/Icon.jsx';
import { PageShell } from '../components/PageShell.jsx';
import { I18nProvider } from '../providers/I18nProvider.jsx';
import { PaymentsProvider } from '../providers/PaymentsProvider.jsx';
import { ToastProvider } from '../providers/ToastProvider.jsx';
import { InsurerView } from '../views/InsurerView.jsx';

createRoot(document.getElementById('root')).render(
  <>
    <IconSprite />
    <I18nProvider defaultLang="en">
      <ToastProvider>
        <PaymentsProvider>
          <PageShell><InsurerView /></PageShell>
        </PaymentsProvider>
      </ToastProvider>
    </I18nProvider>
  </>,
);
