import { createContext, useContext, useEffect, useRef } from 'react';
import { CONFIG, KNOWN } from '../config.js';
import { fetchPayments, mergePayments } from '../lib/stellar.js';
import { formatAmount } from '../lib/format.js';
import { useStateRef } from '../lib/useStateRef.js';
import { useI18n } from './I18nProvider.jsx';
import { useToast } from './ToastProvider.jsx';

const PaymentsContext = createContext(null);
const signature = ({ net, events }) => `${net}:${events.map((e) => e.id).join()}`;

/**
 * Pagos `session_paid` del contrato, refrescados cada 15 s. Si el RPC no responde
 * antes de la primera carga se muestran los cobros ya confirmados (net = "error").
 */
export function PaymentsProvider({ children }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const [payments, setPayments, current] = useStateRef({ net: 'checking', events: [], fresh: new Set() });
  const latest = useRef({ t, lang, toast });
  latest.current = { t, lang, toast };

  useEffect(() => {
    let active = true;
    // Cada refresco sigue desde el último cursor: solo se piden los pagos nuevos.
    let cursor = null;
    const refresh = async () => {
      const previous = current.current;
      let next = previous;
      try {
        const result = await fetchPayments(cursor);
        cursor = result.cursor;
        const events = mergePayments(previous.net === 'live' ? previous.events : [], result.payments);
        const known = new Set(previous.events.map((e) => e.id));
        const firstLoad = previous.net !== 'live';
        const fresh = new Set(firstLoad ? [] : events.filter((e) => !known.has(e.id)).map((e) => e.id));
        if (fresh.size) {
          const { t: text, lang: language, toast: notify } = latest.current;
          notify(`${text('toast.newPayout')} · +${formatAmount(events[0].amount, language)} ${events[0].asset}`);
        }
        next = { net: 'live', events, fresh };
      } catch (error) {
        console.warn('Phonendo: RPC no disponible', error);
        if (previous.net !== 'live') next = { ...previous, events: KNOWN, net: 'error' };
      }
      // Sin cambios no se repinta: los pagos recién llegados siguen resaltados.
      if (active && signature(next) !== signature(previous)) setPayments(next);
    };
    refresh();
    const timer = setInterval(refresh, CONFIG.refreshMs);
    return () => { active = false; clearInterval(timer); };
  }, [current, setPayments]);

  return <PaymentsContext.Provider value={payments}>{children}</PaymentsContext.Provider>;
}

export function usePayments() {
  const context = useContext(PaymentsContext);
  if (!context) throw new Error('usePayments necesita un PaymentsProvider');
  return context;
}
