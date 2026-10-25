import { CONFIG } from '../config.js';
import { contractUrl, short, timeAgo } from '../lib/format.js';
import { groupByUseCase, stats } from '../lib/stellar.js';
import { useI18n } from '../providers/I18nProvider.jsx';
import { usePayments } from '../providers/PaymentsProvider.jsx';
import { Icon } from '../components/Icon.jsx';
import { Kpi, PageHead, PaymentsTable, SnapshotNotice, Totals } from '../components/payments.jsx';

// Mismo panel para todos los casos de uso: cada uno aporta su póliza y su página de detalle.
const USE_CASES = [
  { key: 'rehab', icon: 'heart', page: CONFIG.panels.patient, policy: CONFIG.policy, unit: 'bpm' },
  { key: 'cold-chain', icon: 'thermo', page: 'coldchain.html', policy: CONFIG.coldPolicy, unit: '°C' },
];

function CaseCard({ useCase, events, total }) {
  const { t } = useI18n();
  const { key, icon, page, policy, unit } = useCase;
  const s = stats(events);
  const share = total ? Math.round((events.length / total) * 100) : 0;
  return (
    <article className="card case-card" data-case={key}>
      <header><span className="case-icon"><Icon name={icon} /></span><h3>{t(`co.case.${key}`)}</h3></header>
      <b className="case-total"><Totals totals={s.totals} /></b>
      <span className="case-count">{t(`co.unit.${key}`)}: <b>{events.length}</b></span>
      <div className="share" role="img" aria-label={`${share}%`}><i style={{ width: `${share}%` }} /></div>
      <dl className="kv">
        <dt>{t('co.rule')}</dt><dd>{policy.min}–{policy.max} {unit} · {policy.minCount}/{policy.batch}</dd>
        <dt>{t('co.reward')}</dt><dd>{policy.payout} USDC</dd>
      </dl>
      <a className="case-open" href={page}>{t('co.open')} <Icon name="arrow" className="icon tiny" /></a>
    </article>
  );
}

/** Lo que importa a la empresa que paga: cuánto, por qué caso de uso y con qué prueba. */
export function CompanyView() {
  const { t, lang } = useI18n();
  const { net, events } = usePayments();
  const groups = groupByUseCase(events);
  const known = USE_CASES.flatMap(({ key }) => groups[key] ?? []);
  const s = stats(known);
  return (
    <>
      <PageHead prefix="co" />
      <section className="page-body"><div className="wrap">
        <SnapshotNotice />
        <div className="kpi-row">
          <Kpi label={t('kpi.paid')} value={<Totals totals={s.totals} />} accent />
          <Kpi label={t('kpi.sessions')} value={s.sessions} />
          <Kpi label={t('co.payees')} value={s.patients} />
          <Kpi label={t('kpi.last')} value={s.last ? timeAgo(s.last.paidAt, lang, t) : '—'} />
        </div>
        <div className="case-grid">
          {USE_CASES.map((useCase) => <CaseCard key={useCase.key} useCase={useCase} events={groups[useCase.key] ?? []} total={known.length} />)}
        </div>
        <div className="two-col">
          <div className="card table-card">
            <div className="table-head"><h2>{t('co.table')}</h2><span className={`chip ${net === 'live' ? 'chip-ok' : 'chip-warn'}`}>{t(`net.${net}`)}</span></div>
            <PaymentsTable events={known} showCase payee="co.payee" />
          </div>
          <div className="side">
            <div className="card panel">
              <h3><Icon name="eye-off" className="icon tiny" />{t('co.never')}</h3>
              <ul className="privacy-list">{[1, 2, 3].map((n) => <li key={n}><Icon name="x" className="icon no" /><span>{t(`co.never${n}`)}</span></li>)}</ul>
              <h3 className="spaced"><Icon name="shield" className="icon tiny" />{t('co.get')}</h3>
              <ul className="privacy-list">{[1, 2, 3].map((n) => <li key={n}><Icon name="check" className="icon yes" /><span>{t(`co.get${n}`)}</span></li>)}</ul>
            </div>
            <div className="card panel">
              <h3><Icon name="coin" className="icon tiny" />{t('co.contracts')}</h3>
              <dl className="kv">{CONFIG.contracts.map((c) => [
                <dt key={`${c.id}-t`}>{t(`co.case.${c.useCase}`)} · {c.asset}</dt>,
                <dd key={`${c.id}-d`} className="mono"><a href={contractUrl(c.id)} target="_blank" rel="noopener">{short(c.id, 8, 6)}</a></dd>,
              ])}</dl>
            </div>
          </div>
        </div>
      </div></section>
    </>
  );
}
