// Piezas compartidas por los paneles de paciente y aseguradora.
import { Fragment } from 'react';
import { CONFIG } from '../config.js';
import { formatAmount, short, timeAgo, txUrl } from '../lib/format.js';
import { sortedTotals } from '../lib/stellar.js';
import { useI18n } from '../providers/I18nProvider.jsx';
import { usePayments } from '../providers/PaymentsProvider.jsx';
import { Icon } from './Icon.jsx';

export function Kpi({ label, value, sub = '', accent = false }) {
  return <div className="card kpi"><span>{label}</span><b className={accent ? 'accent' : ''}>{value}</b>{sub ? <small>{sub}</small> : null}</div>;
}

export function Totals({ totals }) {
  const { lang } = useI18n();
  const parts = sortedTotals(totals);
  if (!parts.length) return '0 USDC';
  return parts.map(([asset, amount], index) => (
    <Fragment key={asset}>{index > 0 && ' · '}{formatAmount(amount, lang)} <small>{asset}</small></Fragment>
  ));
}

export function SnapshotNotice() {
  const { t } = useI18n();
  const { net } = usePayments();
  return net === 'error' ? <div className="notice"><Icon name="alert" /><span>{t('notice.snapshot')}</span></div> : null;
}

function useCaseChip(event, t) {
  const useCase = CONFIG.contracts.find((c) => c.id === event.contractId)?.useCase;
  return useCase ? <span className="chip chip-info">{t(`co.case.${useCase}`)}</span> : '—';
}

export function PaymentsTable({ events, showPatient = true, showCase = false, payee = 'tbl.patient', limit = 50 }) {
  const { t, lang } = useI18n();
  const { fresh } = usePayments();
  if (!events.length) return <div className="empty">{t('tbl.empty')}</div>;
  return (
    <div className="table-scroll"><table>
      <thead><tr><th>{t('tbl.session')}</th>{showCase && <th>{t('tbl.case')}</th>}{showPatient && <th>{t(payee)}</th>}<th>{t('tbl.amount')}</th><th>{t('tbl.when')}</th><th>{t('tbl.proof')}</th><th>{t('tbl.tx')}</th></tr></thead>
      <tbody>{events.slice(0, limit).map((e) => (
        <tr key={e.id} className={fresh.has(e.id) ? 'fresh' : ''}>
          <td className="mono">{e.sessionId ?? '—'}</td>
          {showCase && <td>{useCaseChip(e, t)}</td>}
          {showPatient && <td className="mono" title={e.patient}>{short(e.patient, 5, 4)}</td>}
          <td><b>+{formatAmount(e.amount, lang)}</b> {e.asset}</td>
          <td>{timeAgo(e.paidAt, lang, t)}</td>
          <td><span className="chip chip-ok"><Icon name="check" />{t('tbl.zk')}</span></td>
          <td><a href={txUrl(e.txHash)} target="_blank" rel="noopener">{short(e.txHash, 6, 4)} <Icon name="external" className="icon tiny" /></a></td>
        </tr>
      ))}</tbody></table></div>
  );
}

export function PolicyTiles() {
  const { t } = useI18n();
  const p = CONFIG.policy;
  return (
    <div className="policy">
      <div><b>{p.min}–{p.max}</b><span>bpm · {t('pol.range')}</span></div>
      <div><b>{p.minCount}/{p.batch}</b><span>{t('pol.count')}</span></div>
      <div><b>{p.payout} USDC</b><span>{t('pol.reward')}</span></div>
    </div>
  );
}

export function PageHead({ prefix, children }) {
  const { t } = useI18n();
  return (
    <section className="page-head"><div className="wrap">
      <div><span className="eyebrow">{t(`${prefix}.eyebrow`)}</span><h1>{t(`${prefix}.title`)}</h1><p>{t(`${prefix}.lead`)}</p></div>
      {children}
    </div></section>
  );
}
