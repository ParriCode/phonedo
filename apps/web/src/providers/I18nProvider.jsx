import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { I18N } from '../messages.js';
import { storageGet, storageSet } from '../lib/storage.js';

const I18nContext = createContext(null);

/** Idioma de la página. La consola del operador abre en español; el resto, en inglés. */
function initialLang(defaultLang) {
  const stored = storageGet('phonendo.lang');
  if (defaultLang === 'es') return stored === 'en' ? 'en' : 'es';
  return stored === 'es' ? 'es' : 'en';
}

export function I18nProvider({ defaultLang = 'en', children }) {
  const [lang, setLang] = useState(() => initialLang(defaultLang));

  useEffect(() => {
    storageSet('phonendo.lang', lang);
    document.documentElement.lang = lang;
  }, [lang]);

  const value = useMemo(() => ({
    lang,
    setLang,
    t: (key) => I18N[lang][key] ?? I18N.en[key] ?? key,
    opText: (es, en) => (lang === 'es' ? es : en),
  }), [lang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) throw new Error('useI18n necesita un I18nProvider');
  return context;
}
