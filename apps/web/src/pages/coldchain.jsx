import { createRoot } from 'react-dom/client';
import { FrostBackground } from '../components/FrostBackground.jsx';
import { IconSprite } from '../components/Icon.jsx';
import { PageShell } from '../components/PageShell.jsx';
import { chill } from '../lib/chill.js';
import { I18nProvider } from '../providers/I18nProvider.jsx';
import { PaymentsProvider } from '../providers/PaymentsProvider.jsx';
import { ToastProvider } from '../providers/ToastProvider.jsx';
import { ColdChainView } from '../views/ColdChainView.jsx';

// Cada pulsación enfría el termómetro y, un poco, la escarcha de las esquinas.
window.addEventListener('pointerdown', () => chill.press());

createRoot(document.getElementById('root')).render(
  <>
    <IconSprite />
    <FrostBackground />
    <I18nProvider defaultLang="en">
      <ToastProvider>
        <PaymentsProvider>
          <PageShell><ColdChainView /></PageShell>
        </PaymentsProvider>
      </ToastProvider>
    </I18nProvider>
  </>,
);
