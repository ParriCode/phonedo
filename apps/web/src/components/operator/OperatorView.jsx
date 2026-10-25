import { useMemo } from 'react';
import { networkModel } from '../../../service_network/models.js';
import { CONFIG, ORGS } from '../../config.js';
import { contractUrl, formatAmount, short, txUrl } from '../../lib/format.js';
import { useI18n } from '../../providers/I18nProvider.jsx';
import { useNetwork } from '../../providers/NetworkProvider.jsx';
import { useOperator } from '../../providers/OperatorProvider.jsx';
import { usePayments } from '../../providers/PaymentsProvider.jsx';
import { ServiceCanvas } from '../canvas/ServiceCanvas.jsx';
import { Icon } from '../Icon.jsx';
import { useDeployDialog } from './DeployDialog.jsx';
import { OperatorLogs } from './OperatorLogs.jsx';
import { ContainerControls, ServiceDetails } from './ServiceDetails.jsx';

function StellarDetails() {
  const { opText } = useI18n();
  return (
    <div className="card panel"><h3>Stellar testnet</h3><p className="op-caption">{opText('Contratos configurados. Consulta pagos y transacciones en el explorador.', 'Configured contracts. View payments and transactions in the explorer.')}</p>{CONFIG.contracts.map((contract) => (
      <p key={contract.id}><a className="mono" href={contractUrl(contract.id)} target="_blank" rel="noopener">{contract.asset} · {short(contract.id, 8, 6)}</a></p>
    ))}</div>
  );
}

function Sidebar({ selectedNode }) {
  const { opText } = useI18n();
  const { nodeById } = useNetwork();
  if (!selectedNode) return <div className="card panel service-network__empty-detail"><Icon name="hub" /><h3>{opText('Selecciona un nodo', 'Select a node')}</h3><p>{opText('Sus detalles y controles aparecerán aquí.', 'Its details and controls will appear here.')}</p></div>;
  if (selectedNode.kind === 'stellar') return <StellarDetails />;
  return <><ServiceDetails /><ContainerControls node={nodeById(selectedNode.id)} /></>;
}

function ContractsSection() {
  const { t, lang, opText } = useI18n();
  const { net, events } = usePayments();
  return (
    <section className="card panel operator-contracts"><div className="op-section-title"><h2>{opText('Contratos', 'Contracts')}</h2><span className="chip">{t(`net.${net}`)}</span></div>
      <div className="contract-grid">{CONFIG.contracts.map((contract) => (
        <a key={contract.id} className="contract-tile" href={contractUrl(contract.id)} target="_blank" rel="noopener"><Icon name="contract" /><b>{contract.asset} · adherence</b><span className="mono">{short(contract.id, 12, 8)}</span><Icon name="external" /></a>
      ))}</div>
      {events.length ? <ul className="feed-list">{events.slice(0, 4).map((event) => (
        <li key={event.id}><Icon name="check" /><span><b>{formatAmount(event.amount, lang)} {event.asset}</b><small><a href={txUrl(event.txHash)} target="_blank" rel="noopener">{short(event.txHash, 10, 6)}</a></small></span></li>
      ))}</ul> : <p className="op-caption">{opText('Sin pagos nuevos.', 'No new payouts.')}</p>}
      {net === 'error' ? <p className="op-caption">{opText('Explorador sin conexión: se muestran pagos históricos conocidos.', 'Explorer offline: showing known historical payouts.')}</p> : null}</section>
  );
}

/** Consola del operador: lienzo de servicios, actividad y contratos. */
export function OperatorView() {
  const { t, opText } = useI18n();
  const { network, status, selected, select } = useNetwork();
  const { readers, epoch } = useOperator();
  const { net } = usePayments();
  const { openDialog } = useDeployDialog();
  const chainStatus = net === 'live' ? 'up' : net === 'error' ? 'down' : 'checking';
  const model = useMemo(() => networkModel({ services: network, statuses: status, readers, contracts: CONFIG.contracts, rpc: CONFIG.rpc, chainStatus }),
    [network, status, readers, chainStatus]);
  const selectedNode = model.nodes.find((node) => node.id === selected);

  return (
    <section className="page-body operator-body"><div className="wrap-wide">
      <ServiceCanvas
        model={model} selectedId={selected} onSelect={select} onAdd={() => openDialog('reader')}
        storageKey="phonendo.canvas.local.v1" text={opText}
        label={(kind) => (kind === 'stellar' ? 'Stellar' : t(`kind.${kind}`))}
        statusLabel={(value) => t(`status.${value}`)}
        organizationLabel={(org) => (org === 'stellar' ? 'testnet' : ORGS.includes(org) ? t(`org.${org}`) : org)}
        sidebar={<Sidebar key={epoch} selectedNode={selectedNode} />}
      />
      <OperatorLogs />
      <ContractsSection />
    </div></section>
  );
}
