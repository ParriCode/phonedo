import { useState } from 'react';
import { CONFIG } from '../config.js';
import { isAccount, short, timeAgo } from '../lib/format.js';
import { stats } from '../lib/stellar.js';
import { useI18n } from '../providers/I18nProvider.jsx';
import { usePayments } from '../providers/PaymentsProvider.jsx';
import { Icon } from '../components/Icon.jsx';
import { Kpi, PageHead, PaymentsTable, PolicyTiles, SnapshotNotice, Totals } from '../components/payments.jsx';

/** Pagos recibidos por una cuenta Stellar. */
export function PatientView() {
  const { t, lang } = useI18n();
  const { events } = usePayments();
  const [patient, setPatient] = useState(CONFIG.demoPatient);
  const [invalid, setInvalid] = useState(false);
  const mine = events.filter((e) => e.patient === patient);
  const s = stats(mine);

  const onSubmit = (event) => {
    event.preventDefault();
    const value = event.currentTarget.elements['patient-account'].value.trim();
    if (!isAccount(value)) { setInvalid(true); return; }
    setInvalid(false);
    setPatient(value);
  };

  return (
    <>
      <PageHead prefix="pt">
        <div className="account-wrap"><span className="eyebrow">{t('pt.account')}</span>
          <form className="account-box" id="patient-form" onSubmit={onSubmit}>
            <label className="sr-only" htmlFor="patient-account">{t('pt.account')}</label>
            <input id="patient-account" key={patient} defaultValue={patient} spellCheck={false} autoComplete="off" />
            <button className="btn btn-gold btn-sm" type="submit">{t('pt.view')}</button>
          </form>
          <small id="patient-error" className="form-error" hidden={!invalid}>{t('pt.invalid')}</small></div>
      </PageHead>
      <section className="page-body"><div className="wrap">
        <SnapshotNotice />
        <div className="kpi-row">
          <Kpi label={t('kpi.earned')} value={<Totals totals={s.totals} />} accent />
          <Kpi label={t('kpi.yourSessions')} value={s.sessions} />
          <Kpi label={t('kpi.last')} value={s.last ? timeAgo(s.last.paidAt, lang, t) : '—'} />
          <Kpi label={t('pt.account')} value={<span className="mono">{short(patient, 5, 4)}</span>} />
        </div>
        <div className="two-col">
          <div className="card table-card">
            <div className="table-head"><h2>{t('pt.payouts')}</h2><span className="chip chip-info"><Icon name="star" className="icon tiny" />Stellar</span></div>
            {mine.length ? <PaymentsTable events={mine} showPatient={false} /> : <div className="empty">{t('pt.none')}</div>}
          </div>
          <div className="side">
            <div className="card panel">
              <h3><Icon name="coin" className="icon tiny" />{t('pt.how')}</h3>
              <PolicyTiles />
              <ol className="mini-steps">{[1, 2, 3, 4].map((n) => <li key={n}>{t(`pt.how${n}`)}</li>)}</ol>
            </div>
            <div className="card panel">
              <h3><Icon name="shield" className="icon tiny" />{t('pt.privacy')}</h3>
              <ul className="privacy-list">{[1, 2, 3, 4].map((n) => (
                <li key={n}><Icon name={n === 1 ? 'eye-off' : 'check'} className={`icon ${n === 1 ? 'no' : 'yes'}`} /><span>{t(`pt.priv${n}`)}</span></li>
              ))}</ul>
            </div>
          </div>
        </div>
      </div></section>
    </>
  );
}
