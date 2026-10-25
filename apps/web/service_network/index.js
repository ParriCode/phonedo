import { ServiceCanvas } from './canvas.js';
import { networkModel } from './models.js';

/** Adaptador de la consola existente al componente independiente del lienzo. */
export function connectServiceNetwork(options) {
  let canvas = null;
  const update = () => {
    const root = document.querySelector('[data-service-network-root]');
    if (!root) return;
    if (!canvas || canvas.root !== root) {
      canvas?.destroy();
      canvas = new ServiceCanvas(root, options);
    }
    const snapshot = options.snapshot();
    canvas.update(networkModel(snapshot), snapshot.selectedId);
  };
  document.addEventListener('phonendo:operator-render', update);
  update();
  return { update, destroy() { document.removeEventListener('phonendo:operator-render', update); canvas?.destroy(); } };
}
