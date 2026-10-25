import { ICON_SYMBOLS } from '../iconSymbols.js';

export function Icon({ name, className = 'icon' }) {
  return <svg className={className} aria-hidden="true"><use href={`#i-${name}`} /></svg>;
}

/** Sprite oculto con todos los símbolos; va al principio de cada página. */
export function IconSprite() {
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true">
      <defs dangerouslySetInnerHTML={{ __html: ICON_SYMBOLS }} />
    </svg>
  );
}
