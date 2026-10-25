import { useI18n } from '../providers/I18nProvider.jsx';
import { usePayments } from '../providers/PaymentsProvider.jsx';
import { contractUrl } from '../lib/format.js';
import { CONFIG } from '../config.js';
import { Icon } from './Icon.jsx';

function LangSwitch() {
  const { lang, setLang } = useI18n();
  return (
    <div className="lang" role="group" aria-label="Language">
      {['en', 'es'].map((code) => (
        <button key={code} type="button" data-lang={code} aria-pressed={lang === code} onClick={() => setLang(code)}>{code.toUpperCase()}</button>
      ))}
    </div>
  );
}

function NetPill() {
  const { t } = useI18n();
  const { net } = usePayments();
  return (
    <span className="net-pill" id="net-pill" data-state={net} role="status"><i className="net-dot" /><span id="net-label">{t(`net.${net}`)}</span></span>
  );
}

/** Barra superior, contenido y pie comunes a los paneles. `nav` añade enlaces a otros paneles. */
export function PageShell({ children, nav = [] }) {
  const { t } = useI18n();
  return (
    <>
      <header className="topbar">
        <span className="brand"><span className="brand-mark"><svg className="icon"><use href="#i-pulse" /></svg></span><span>Phon<b>endo</b></span></span>
        <div className="topbar-end">
          {nav.map((item) => <a key={item.href} className="topbar-link" href={item.href}><Icon name={item.icon} />{t(item.label)}</a>)}
          <NetPill />
          <LangSwitch />
        </div>
      </header>

      <main id="app" tabIndex={-1}>{children}</main>

      <footer className="footer">
        <div className="wrap">
          <span>Phonendo · HackMeridian 2026 · <span data-i18n="footer.built">{t('footer.built')}</span></span>
          <a href={contractUrl(CONFIG.contracts[0].id)} target="_blank" rel="noopener" data-i18n="footer.contract">{t('footer.contract')}</a>
        </div>
      </footer>
    </>
  );
}
