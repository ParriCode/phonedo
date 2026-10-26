import { Icon } from '../Icon.jsx';

const ICONS = { reader: 'cpu', manager: 'hub', verifier: 'shield', storage: 'db', publisher: 'send', stellar: 'contract' };

/** Tarjeta compacta; el nombre completo y los detalles quedan en el inspector. */
export function CanvasNode({ node, position, selected, connectTarget, label, view, managed, onDeploy, onDockerAction, onImageAction, onPortStart, onPortMove, onPortEnd, onPortTarget, text }) {
  const className = `service-node service-node--${view.health}${selected ? ' service-node--selected' : ''}${connectTarget ? ' service-node--connect-target' : ''}${node.kind === 'stellar' ? ' service-node--stellar' : ''}`;
  const action = (name) => {
    if (name === 'remove' && !window.confirm(text(`¿Eliminar el contenedor ${node.name}?`, `Remove container ${node.name}?`))) return;
    onDockerAction(node, name);
  };
  const image = managed?.image || node.image;
  const imageSource = managed?.compose ? 'compose' : node.imageSource;
  const dockerName = node.name.startsWith('phonendo-') ? node.name.slice(9) : node.name;
  const shortName = (dockerName.length > 10 ? dockerName.replace(/-\d+$/, '') : dockerName).slice(0, 10);
  const actionButton = (name, icon, title, handler) => <button type="button" data-node-action={name} aria-label={title} title={title} onClick={handler}><Icon name={icon} /></button>;
  return (
    <div role="button" tabIndex={0} className={className} data-service-id={node.id} aria-pressed={selected}
      aria-label={`${node.name}, ${label(node.kind)}, ${view.healthText}${managed ? `, Docker ${managed.state}` : ''}`} title={node.name}
      style={{ transform: `translate(${position.x}px, ${position.y}px)` }}>
      <span className="service-node__top"><Icon name={ICONS[node.kind] || 'hub'} className="service-node__kind-icon" /><i className="service-node__status" data-status={node.status} data-health={view.health} aria-hidden="true" /></span>
      <strong className="service-node__name" title={node.name}>{shortName}</strong>
      <span className="service-node__signal">
        {view.line?.tone === 'error' || view.line?.tone === 'warning' ? <span className={`service-node__activity service-node__activity--${view.line.tone}`} title={view.line.text}><Icon name="alert" />{view.line.text}</span> : null}
        {view.stream ? <span className="service-node__stream" title="Stream"><Icon name="zap" /></span> : null}
      </span>
      <button type="button" className="service-node__port-handle service-node__port-handle--in" data-node-action="port-in" data-port-in={node.id}
        aria-label={text(`Conectar hacia ${node.name}`, `Connect to ${node.name}`)} title={text('Entrada', 'Input')}
        onClick={() => onPortTarget(node.id)} />
      <button type="button" className="service-node__port-handle service-node__port-handle--out" data-node-action="port-out" data-port-out={node.id}
        aria-label={text(`Conectar desde ${node.name}`, `Connect from ${node.name}`)} title={text('Arrastra para conectar', 'Drag to connect')}
        onPointerDown={(event) => onPortStart(event, node.id)} onPointerMove={onPortMove} onPointerUp={onPortEnd} onPointerCancel={onPortEnd} />
      {node.kind !== 'stellar' ? <span className="service-node__actions">
        {managed ? <>
          {managed.state === 'running' ? actionButton('stop', 'stop', text('Parar', 'Stop'), () => action('stop')) : actionButton('start', 'play', text('Arrancar', 'Start'), () => action('start'))}
          {actionButton('restart', 'refresh', text('Reiniciar', 'Restart'), () => action('restart'))}
          {actionButton('remove', 'trash', text('Eliminar contenedor', 'Remove container'), () => action('remove'))}
        </> : actionButton('deploy', 'play', text('Crear contenedor', 'Create container'), () => onDeploy(node.kind, node.imageOnly ? image : null))}
        {actionButton('build-image', 'layers', text('Crear imagen', 'Build image'), () => onImageAction(node.kind, 'build', imageSource))}
        {!managed ? actionButton('remove-image', 'trash', text('Borrar imagen', 'Remove image'), () => {
          if (window.confirm(text(`¿Eliminar la imagen Docker ${image || label(node.kind)}?`, `Remove Docker image ${image || label(node.kind)}?`))) onImageAction(node.kind, 'remove', imageSource, image);
        }) : null}
      </span> : null}
    </div>
  );
}
