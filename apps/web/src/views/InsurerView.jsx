import { CONFIG } from '../config.js';
import { contractUrl, short, timeAgo } from '../lib/format.js';
import { stats } from '../lib/stellar.js';
import { useI18n } from '../providers/I18nProvider.jsx';
import { usePayments } from '../providers/PaymentsProvider.jsx';
import { Icon } from '../components/Icon.jsx';
import { Kpi, PageHead, PaymentsTable, PolicyTiles, SnapshotNotice, Totals } from '../components/payments.jsx';

/** Pagos realizados por el contrato, sin lecturas. */
export function InsurerView() {
  const { t, lang } = useI18n();
  const { net, events } = usePayments();
  const s = stats(events);
  return (
    <>
      <PageHead prefix="in" />
      <section className="page-body"><div className="wrap">
        <SnapshotNotice />
        <div className="kpi-row">
          <Kpi label={t('kpi.paid')} value={<Totals totals={s.totals} />} accent />
          <Kpi label={t('kpi.sessions')} value={s.sessions} />
          <Kpi label={t('kpi.patients')} value={s.patients} />
          <Kpi label={t('kpi.last')} value={s.last ? timeAgo(s.last.paidAt, lang, t) : '—'} />
        </div>
        <div className="two-col">
          <div className="card table-card">
            <div className="table-head"><h2>{t('in.table')}</h2><span className={`chip ${net === 'live' ? 'chip-ok' : 'chip-warn'}`}>{t(`net.${net}`)}</span></div>
            <PaymentsTable events={events} />
          </div>
          <div className="side">
            <div className="card panel"><h3><Icon name="contract" className="icon tiny" />{t('in.policy')}</h3><PolicyTiles /></div>
            <div className="card panel">
              <h3><Icon name="eye-off" className="icon tiny" />{t('in.never')}</h3>
              <ul className="privacy-list">{[1, 2, 3].map((n) => <li key={n}><Icon name="x" className="icon no" /><span>{t(`in.never${n}`)}</span></li>)}</ul>
              <h3 className="spaced"><Icon name="shield" className="icon tiny" />{t('in.get')}</h3>
              <ul className="privacy-list">{[1, 2, 3].map((n) => <li key={n}><Icon name="check" className="icon yes" /><span>{t(`in.get${n}`)}</span></li>)}</ul>
            </div>
            <div className="card panel">
              <h3><Icon name="coin" className="icon tiny" />{t('in.contracts')}</h3>
              <dl className="kv">{CONFIG.contracts.map((c) => [
                <dt key={`${c.id}-t`}>{c.asset}</dt>,
                <dd key={`${c.id}-d`} className="mono"><a href={contractUrl(c.id)} target="_blank" rel="noopener">{short(c.id, 8, 6)}</a></dd>,
              ])}</dl>
            </div>
          </div>
        </div>
      </div></section>
    </>
  );
}
