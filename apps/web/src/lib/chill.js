// Enfriamiento acumulado por las pulsaciones del panel de cadena de frío; se recupera solo.

/** Nivel de frío en °C que suma cada pulsación y baja con el tiempo (`recovery` °C por segundo). */
export function createChill({ drop = 2.5, recovery = 0.2, max = 5 } = {}, now = () => performance.now()) {
  let amount = 0;
  let stamp = now();
  const settle = () => {
    const current = now();
    amount = Math.max(0, amount - ((current - stamp) / 1000) * recovery);
    stamp = current;
  };
  return {
    press() { settle(); amount = Math.min(max, amount + drop); },
    level() { settle(); return amount; },
    /** Fracción de 0 a 1 respecto al máximo. */
    ratio() { settle(); return amount / max; },
  };
}

export const chill = createChill();
