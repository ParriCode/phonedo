import { CONFIG } from '../config.js';
import { short, timeAgo } from '../lib/format.js';
import { sortedTotals, stats } from '../lib/stellar.js';
import { useI18n } from '../providers/I18nProvider.jsx';
import { usePayments } from '../providers/PaymentsProvider.jsx';
import { Icon } from '../components/Icon.jsx';
import { ColdPolicyTiles, Thermometer } from '../components/cold.jsx';
import { Kpi, PageHead, PaymentsTable, SnapshotNotice } from '../components/payments.jsx';
import { CountUp, SessionRing } from '../components/rehab.jsx';

const COLD = new Set(CONFIG.contracts.filter((c) => c.useCase === 'cold-chain').map((c) => c.id));
const LABELS = { count: 'ct.count', reward: 'ct.reward' };

function Paid({ totals }) {
  const parts = sortedTotals(totals);
  if (!parts.length) return <div className="earned"><CountUp value={0} digits={2} /> <small>USDC</small></div>;
  return parts.map(([asset, amount]) => (
    <div className="earned" key={asset}><CountUp value={amount} digits={2} /> <small>{asset}</small></div>
  ));
}

/** Pagos de cadena de frío: cada envío que se mantuvo dentro de la franja de temperatura. */
export function ColdChainView() {
  const { t, lang } = useI18n();
  const { events } = usePayments();
  const shipments = events.filter((e) => COLD.has(e.contractId));
  const s = stats(shipments);

  return (
    <>
      <PageHead prefix="ct">
        <div className="gauges"><Thermometer /><SessionRing policy={CONFIG.coldPolicy} labels={LABELS} /></div>
      </PageHead>
      <section className="page-body"><div className="wrap">
        <SnapshotNotice />
        <div className="kpi-row">
          <Kpi label={t('ct.paid')} value={<Paid totals={s.totals} />} accent />
          <Kpi label={t('ct.shipments')} value={<CountUp value={s.sessions} />} />
          <Kpi label={t('kpi.last')} value={s.last ? timeAgo(s.last.paidAt, lang, t) : '—'} />
          <Kpi label={t('ct.payee')} value={<span className="mono">{s.last ? short(s.last.patient, 5, 4) : '—'}</span>} />
        </div>
        <div className="two-col">
          <div className="card table-card">
            <div className="table-head"><h2>{t('ct.payouts')}</h2><span className="chip chip-info"><Icon name="star" className="icon tiny" />Stellar</span></div>
            {shipments.length ? <PaymentsTable events={shipments} /> : <div className="empty">{t('ct.none')}</div>}
          </div>
          <div className="side">
            <div className="card panel">
              <h3><Icon name="coin" className="icon tiny" />{t('ct.how')}</h3>
              <ColdPolicyTiles />
              <ol className="mini-steps">{[1, 2, 3, 4].map((n) => <li key={n}>{t(`ct.how${n}`)}</li>)}</ol>
            </div>
            <div className="card panel">
              <h3><Icon name="shield" className="icon tiny" />{t('ct.privacy')}</h3>
              <ul className="privacy-list">{[1, 2, 3, 4].map((n) => (
                <li key={n}><Icon name={n === 1 ? 'eye-off' : 'check'} className={`icon ${n === 1 ? 'no' : 'yes'}`} /><span>{t(`ct.priv${n}`)}</span></li>
              ))}</ul>
            </div>
          </div>
        </div>
      </div></section>
    </>
  );
}
