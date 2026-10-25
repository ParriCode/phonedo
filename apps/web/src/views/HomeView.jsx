// Portada: consola del operador y casos de uso. Sus estilos están en home.css.
const svg = { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': 'true' };

export function HomeView() {
  return (
    <main className="split-home">
      <a className="half operator" href="operator.html" aria-label="Phonendo operator console">
        <span className="badge"><svg className="icon" {...svg} style={{ width: '28px', height: '28px' }}><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4" /></svg></span>
        <h1>Phonendo</h1>
        <span className="go">Open <svg className="icon" {...svg}><path d="M5 12h14M12 5l7 7-7 7" /></svg></span>
      </a>
      <div className="use-cases">
        <a className="half use-case" href="patient.html" aria-label="Cardiac rehabilitation use case">
          <span className="badge"><svg className="icon" {...svg}><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21l7.8-7.6 1-1.1a5.5 5.5 0 0 0 0-7.7z" /></svg></span>
          <span className="label">Use case</span>
          <h2>Cardiac rehabilitation</h2>
          <p>The insurer pays the patient for each completed session, and never sees the heart-rate readings.</p>
        </a>
        <section className="half use-case">
          <span className="badge"><svg className="icon" {...svg}><path d="M14 14.8V4a2 2 0 0 0-4 0v10.8a4 4 0 1 0 4 0z" /></svg></span>
          <span className="label">Use case</span>
          <h2>Cold-chain transport</h2>
          <p>Payment is released only if the goods stayed within the agreed temperature range during transport.</p>
          <span className="tag">Interface pending</span>
        </section>
        <div className="more" aria-label="More use cases">···</div>
      </div>
    </main>
  );
}
