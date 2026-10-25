use leptos::{html, prelude::*};
use phonendo_control_frontend::{
    demo, Connection, ConnectionState, Log, Node, Scenario, Snapshot, Status, LOG_LIMIT,
};
use wasm_bindgen::prelude::*;

// Cargo debe recompilar el enlace WebAssembly cuando cambia la geometría.
const _: &str = include_str!("graph.mjs");

#[wasm_bindgen(module = "/src/graph.mjs")]
extern "C" {
    #[wasm_bindgen(js_name = observeGraph)]
    fn observe_graph(element: &web_sys::HtmlElement);
    #[wasm_bindgen(js_name = disconnectGraph)]
    fn disconnect_graph(element: &web_sys::HtmlElement);
}

#[component]
pub fn App() -> impl IntoView {
    let scenario = RwSignal::new(Scenario::Degraded);
    let empty_deployment = RwSignal::new(false);
    let selected = RwSignal::new("manager-01".to_string());
    let all_logs = RwSignal::new(false);
    let effective = move || {
        if empty_deployment.get() {
            Scenario::Empty
        } else {
            scenario.get()
        }
    };
    let data = Memo::new(move |_| {
        demo(effective()).expect("El ejemplo de topología debe contener JSON válido")
    });
    view! {
        <a class="pn-skip-link" href="#main">"Saltar al contenido"</a>
        <div class="pn-app">
            <header class="pn-header">
                <a class="pn-brand" href="#main" aria-label="Phonendo, inicio"><span class="pn-brand-icon"><Icon kind="activity"/></span><strong>"phonendo"<span>"."</span></strong></a>
                <span class="pn-brand-divider"></span><span class="pn-header-title">"Observación"</span>
                <div class="pn-header-meta"><label class="pn-deployment"><span class="pn-sr-only">"Despliegue"</span>
                    <select prop:value=move || if empty_deployment.get() { "empty" } else { "local" } on:change=move |ev| empty_deployment.set(event_target_value(&ev) == "empty")><option value="local">"Laboratorio local"</option><option value="empty">"Despliegue vacío"</option></select>
                </label><span class="pn-simulation">"Simulación"</span></div>
            </header>
            <main id="main">
                <div class="pn-heading"><div><p class="pn-eyebrow">"ESPACIO DE TRABAJO"</p><h1>"Red de servicios"</h1></div><span class="pn-heading-note"><span class="pn-status-dot"></span>"Instantánea de ejemplo · "{move || data.get().observed_at}</span></div>
                <Show when=move || !effective().hides_data() fallback=move || view! {
                    <section class="pn-empty-state" aria-busy=move || effective() == Scenario::Loading><Icon kind="network"/><h2>{move || match effective() { Scenario::Loading => "Preparando la vista", Scenario::Empty => "Todavía no hay servicios", _ => "No se pudo cargar la red" }}</h2><p role="status">{move || effective().notice()}</p><button class="pn-primary" on:click=move |_| { scenario.set(Scenario::Degraded); empty_deployment.set(false); }>"Volver al ejemplo inicial"</button></section>
                }>
                    <div class="pn-layout">
                        <aside class="pn-sidebar" aria-label="Servicios y logs">
                            <section class="pn-panel pn-services" aria-labelledby="services-title">
                                <div class="pn-panel-heading"><h2 id="services-title"><Icon kind="layers"/>"Servicios"</h2><span class="pn-count">{move || data.get().nodes.len()}</span></div>
                                <table class="pn-service-table"><thead><tr><th scope="col">"Instancia"</th><th scope="col">"Estado"</th></tr></thead><tbody>{move || { let snapshot = data.get(); snapshot.nodes.iter().cloned().map(|node| { let status = snapshot.visible_status(&node); view! { <ServiceRow node=node status=status selected=selected all_logs=all_logs/> } }).collect_view() }}</tbody></table>
                            </section>
                            <LogsPanel data=data selected=selected all_logs=all_logs/>
                        </aside>
                        <div class="pn-workbench"><Graph data=data selected=selected all_logs=all_logs/>
                            <section class="pn-panel pn-inspector" aria-label="Información del servicio seleccionado" aria-live="polite">{move || { let snapshot = data.get(); snapshot.nodes.iter().find(|node| node.instance_id == selected.get()).cloned().map(|node| { let status = snapshot.visible_status(&node); view! { <NodeDetail node=node status=status snapshot=snapshot/> } }) }}</section>
                        </div>
                    </div>
                </Show>
                <details class="pn-scenarios"><summary>"Escenarios de demostración"</summary><div class="pn-scenario-content"><label>"Escenario"<select prop:value=move || scenario_value(scenario.get()) on:change=move |ev| scenario.set(Scenario::parse(&event_target_value(&ev)))>
                    <option value="degraded">"Guardado pendiente de reintento"</option><option value="normal">"Funcionamiento normal"</option><option value="offline">"Storage sin respuesta"</option><option value="stale">"Datos desactualizados"</option><option value="blocked">"SSE redundante rechazada"</option><option value="unknown">"Estado desconocido"</option><option value="loading">"Cargando"</option><option value="empty">"Sin instancias"</option><option value="error">"Error de carga"</option><option value="disconnected">"Backend desconectado"</option>
                </select></label><p class="pn-scenario-notice" role="status">{move || effective().notice()}</p></div></details>
            </main>
            <footer class="pn-footer"><span>"Phonendo / Panel de observación"</span><span>"Datos simulados · sin conexión a servicios reales"</span></footer>
        </div>
    }
}

#[component]
fn ServiceRow(
    node: Node,
    status: Status,
    selected: RwSignal<String>,
    all_logs: RwSignal<bool>,
) -> impl IntoView {
    let id = node.instance_id.clone();
    let active_id = id.clone();
    let pressed_id = id.clone();
    let label = status_label(&node, status);
    view! { <tr data-active=move || (selected.get() == active_id).to_string()><td><button class="pn-service-button" aria-pressed=move || (selected.get() == pressed_id).to_string() on:click=move |_| { selected.set(id.clone()); all_logs.set(false); }><Icon kind=icon_for(&node.kind)/><span>{node.kind}<small>{node.instance_id}</small></span></button></td><td><span class=format!("pn-status {}", status.class())>{label}</span></td></tr> }
}

#[component]
fn Graph(
    data: Memo<Snapshot>,
    selected: RwSignal<String>,
    all_logs: RwSignal<bool>,
) -> impl IntoView {
    let stage = NodeRef::<html::Div>::new();
    Effect::new(move |_| {
        if let Some(element) = stage.get() {
            observe_graph(&element);
            on_cleanup(move || disconnect_graph(&element));
        }
    });
    view! {
        <section class="pn-panel pn-graph-panel" aria-labelledby="graph-title">
            <div class="pn-panel-heading"><h2 id="graph-title"><Icon kind="network"/>"Topología del despliegue"</h2><span class="pn-graph-caption">"Flujo de datos"</span></div>
            <div class="pn-graph" node_ref=stage>
                <svg class="pn-edges" aria-hidden="true"><defs><marker id="pn-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 9 5 L 0 9 Z"/></marker></defs>
                    {move || { let snapshot = data.get(); let selection = selected.get(); snapshot.connections.iter().enumerate().map(|(index,edge)| {
                        let parallel = snapshot.connections[..index].iter().filter(|other| other.source_id == edge.source_id && other.target_id == edge.target_id).count();
                        let active = edge.source_id == selection || edge.target_id == selection;
                        let class = if snapshot.stale { "pn-edge-unknown" } else { match edge.state { ConnectionState::Blocked => "pn-edge-blocked", ConnectionState::Disconnected => "pn-edge-warning", ConnectionState::Configured | ConnectionState::Connecting => "pn-edge-unknown", ConnectionState::Connected if active => "pn-edge-active", _ => "" }};
                        let label = edge_label(edge, snapshot.stale);
                        view! { <g data-source=edge.source_id.clone() data-target=edge.target_id.clone() data-offset=(parallel * 30).to_string()><path class=class marker-end="url(#pn-arrow)"/><text>{label}</text></g> }
                    }).collect_view() }}
                </svg>
                {move || { let snapshot = data.get(); snapshot.nodes.iter().cloned().map(|node| { let status = snapshot.visible_status(&node); view! { <GraphNode node=node status=status selected=selected all_logs=all_logs/> } }).collect_view() }}
            </div>
            <div class="pn-graph-footer"><div class="pn-legend"><span><b class="healthy"></b>"Disponible"</span><span><b class="degraded"></b>"Degradado"</span><span><b class="unknown"></b>"Sin datos"</span></div><span>"Selecciona un nodo para ver su información"</span></div>
            <p class="pn-graph-note">"El Manager coordina el guardado tras verificar. HTTP representa la última petición; SSE, el estado del stream."</p>
        </section>
    }
}

#[component]
fn GraphNode(
    node: Node,
    status: Status,
    selected: RwSignal<String>,
    all_logs: RwSignal<bool>,
) -> impl IntoView {
    let id = node.instance_id.clone();
    let pressed_id = id.clone();
    let label = status_label(&node, status);
    view! { <button class=format!("pn-node {}", status.class()) data-instance-id=node.instance_id.clone() data-kind=node.kind.to_lowercase() aria-pressed=move || (selected.get() == pressed_id).to_string() on:click=move |_| { selected.set(id.clone()); all_logs.set(false); }><span class="pn-node-top"><Icon kind=icon_for(&node.kind)/><span class="pn-node-indicator"></span></span><strong>{node.kind.clone()}</strong><span class="pn-node-id">{node.instance_id.clone()}</span><span class="pn-node-status">{label}</span></button> }
}

#[component]
fn LogsPanel(
    data: Memo<Snapshot>,
    selected: RwSignal<String>,
    all_logs: RwSignal<bool>,
) -> impl IntoView {
    let logs = Memo::new(move |_| {
        let selection = selected.get();
        data.get().related_logs(if all_logs.get() {
            None
        } else {
            Some(&selection)
        })
    });
    view! {
        <section class="pn-panel pn-logs" aria-labelledby="logs-title">
            <div class="pn-panel-heading"><h2 id="logs-title"><Icon kind="list"/>"Logs relacionados"</h2><span class="pn-count">{move || logs.get().len()}</span></div>
            <div class="pn-log-toolbar"><span class="pn-log-scope" aria-live="polite">{move || if all_logs.get() { "Todos los servicios".to_string() } else { data.get().nodes.iter().find(|n| n.instance_id == selected.get()).map(|n| n.kind.clone()).unwrap_or_else(|| "Sin selección".into()) }}</span><Show when=move || !all_logs.get()><button class="pn-text-button" on:click=move |_| all_logs.set(true)>"Ver todos"</button></Show></div>
            <table class="pn-log-table"><caption class="pn-sr-only">"Eventos de ejemplo relacionados con la selección"</caption><thead><tr><th scope="col">"Hora UTC"</th><th scope="col">"Evento"</th></tr></thead><tbody><Show when=move || !logs.get().is_empty() fallback=|| view! { <tr><td colspan="2">"Sin logs disponibles para esta selección."</td></tr> }>{move || logs.get().into_iter().map(|log| view! { <LogRow log=log/> }).collect_view()}</Show></tbody></table>
            <div class="pn-log-footer"><span class="pn-mini-square"></span>"Datos de ejemplo · máximo "{LOG_LIMIT}" eventos"</div>
        </section>
    }
}

#[component]
fn LogRow(log: Log) -> impl IntoView {
    let clock = log
        .at
        .split('T')
        .nth(1)
        .unwrap_or(&log.at)
        .trim_end_matches('Z')
        .to_string();
    let service = log
        .instance_id
        .split('-')
        .next()
        .unwrap_or(&log.instance_id)
        .to_string();
    view! { <tr><td><time datetime=log.at.clone()>{clock}</time></td><td><div class="pn-log-meta"><strong>{service}</strong><span class=if log.level == "WARN" { "pn-log-level degraded" } else { "pn-log-level" }>{log.level.clone()}</span></div><details><summary>{log.message}</summary><div class="pn-log-extra">{log.code.map(|code| view! { <strong>{code}</strong> })}<p>{log.detail.unwrap_or_else(|| "Sin detalle adicional.".into())}</p><p>"Informado por: "{log.instance_id}</p><p>"Fecha: "{log.at}</p>{(!log.related_instance_ids.is_empty()).then(|| view! { <p>"Relacionado con: "{log.related_instance_ids.join(", ")}</p> })}</div></details></td></tr> }
}

#[component]
fn NodeDetail(node: Node, status: Status, snapshot: Snapshot) -> impl IntoView {
    let edges: Vec<_> = snapshot
        .connections
        .iter()
        .filter(|edge| edge.source_id == node.instance_id || edge.target_id == node.instance_id)
        .cloned()
        .collect();
    let unmonitored = node.kind == "Publisher";
    let is_reader = node.kind == "Reader";
    let label = status_label(&node, status);
    let resources = if node.cpu_percent.is_none() && node.memory_mb.is_none() {
        "No disponible".to_string()
    } else {
        format!(
            "{} / {}",
            metric(node.cpu_percent, "%"),
            metric(node.memory_mb, "MB")
        )
    };
    view! {
        <div class="pn-inspector-heading"><div class="pn-selected-icon"><Icon kind=icon_for(&node.kind)/></div><div><p class="pn-eyebrow">"SERVICIO SELECCIONADO"</p><h2>{node.kind.clone()}</h2><span class="pn-id">{node.instance_id.clone()}</span></div><span class=format!("pn-status pn-detail-status {}",status.class())>{label}</span></div>
        <p class="pn-service-description">{description(&node.kind)}</p>
        <dl class="pn-info-grid"><div><dt>"Dirección configurada"</dt><dd class="pn-mono">{if node.address.is_empty() { "Sin dirección de monitorización".into() } else { node.address }}</dd></div><div><dt>"Contenedor · ejemplo"</dt><dd>{node.container_state.map(|state| if state == "running" { "En ejecución".into() } else { state }).unwrap_or_else(|| "Sin información".into())}</dd></div><div><dt>"Última actividad · UTC"</dt><dd>{node.last_activity_at.unwrap_or_else(|| "Sin actividad registrada".into())}</dd></div><div><dt>"CPU / memoria"</dt><dd>{resources}</dd></div></dl>
        <div class="pn-relation-box"><h3 class="pn-eyebrow">"RELACIONES"</h3>{if edges.is_empty() { view! { <p>"Sin conexiones registradas en esta instantánea de ejemplo."</p> }.into_any() } else { edges.into_iter().map(|edge| view! { <ConnectionDetail edge=edge stale=snapshot.stale/> }).collect_view().into_any() }}</div>
        {node.reader_id.map(|id| view! { <p class="pn-reader-id">"Reader ID: "{id}</p> })}
        {(!node.devices.is_empty()).then(|| view! { <div class="pn-device-box"><h3>"Dispositivos conocidos"</h3><ul>{node.devices.into_iter().map(|device| view! { <li>{device}</li> }).collect_view()}</ul><p>"El inventario no confirma una conexión física."</p></div> })}
        {node.last_error.map(|error| view! { <div class="pn-node-notice" role="status"><strong>{error.code}</strong><p>{error.message}</p><span>{if error.retryable { "El intento se puede repetir." } else { "Revisar la configuración antes de reintentar." }}</span></div> })}
        {unmonitored.then(|| view! { <p class="pn-node-notice">"Publisher ya tiene implementación. Esta demo todavía no dispone de datos de su monitorización; no se deducen conexiones ni pagos."</p> })}
        <p class="pn-detail-note">"Observado: "{node.observed_at}". Un contenedor en ejecución no garantiza la disponibilidad del servicio."</p>
        {is_reader.then(|| view! { <Readings snapshot=snapshot/> })}
    }
}

#[component]
fn ConnectionDetail(edge: Connection, stale: bool) -> impl IntoView {
    let label = if stale {
        "Estado actual desconocido"
    } else {
        edge.state.label(edge.transport)
    };
    view! { <details class="pn-connection-detail"><summary>{edge.source_id}" → "{edge.target_id}" · "{edge.transport.label()}" · "{label}</summary><dl><dt>"Informado por"</dt><dd>{edge.reported_by}</dd><dt>"Observado (UTC)"</dt><dd>{edge.observed_at}</dd><dt>"Último éxito (UTC)"</dt><dd>{edge.last_success_at.unwrap_or_else(|| "Sin éxito registrado".into())}</dd><dt>"Contador del ejemplo"</dt><dd>{edge.events_received}</dd></dl>{edge.last_error.map(|error| view! { <p class="pn-connection-error">{error.code}": "{error.message}</p> })}</details> }
}

#[component]
fn Readings(snapshot: Snapshot) -> impl IntoView {
    view! { <details class="pn-readings"><summary>"Lecturas de ejemplo del Reader"</summary><p>"Pulso sintético · no representa mediciones en directo ni eventos Verified."</p><svg class="pn-reading-chart" viewBox="0 0 680 215" role="img" aria-label="Pulso simulado, entre 0 y 255 pulsaciones por minuto"><line x1="40" y1="20" x2="640" y2="20"/><line x1="40" y1="100" x2="640" y2="100"/><line x1="40" y1="180" x2="640" y2="180"/><text x="0" y="24">"255"</text><text x="0" y="104">"128"</text><text x="15" y="184">"0"</text><polyline points=snapshot.chart_points() fill="none"/><text x="40" y="207">"12:29:44"</text><text x="574" y="207">"12:29:59"</text></svg><table><caption>"Valores del ejemplo"</caption><thead><tr><th>"Hora UTC"</th><th>"Pulso (bpm)"</th></tr></thead><tbody>{snapshot.readings.into_iter().map(|reading| view! { <tr><td>{reading.at}</td><td>{reading.value}</td></tr> }).collect_view()}</tbody></table></details> }
}

fn status_label(node: &Node, status: Status) -> &'static str {
    if node.kind == "Publisher" && status == Status::Unknown {
        "Sin datos"
    } else {
        status.label()
    }
}
fn edge_label(edge: &Connection, stale: bool) -> String {
    let suffix = if stale {
        " · sin actualizar"
    } else {
        match edge.state {
            ConnectionState::Blocked => " · rechazada",
            ConnectionState::Disconnected => " · sin respuesta",
            ConnectionState::Configured => " · configurada",
            ConnectionState::Connecting => " · conectando",
            _ => "",
        }
    };
    format!("{}{suffix}", edge.transport.label())
}
fn scenario_value(scenario: Scenario) -> &'static str {
    match scenario {
        Scenario::Normal => "normal",
        Scenario::Degraded => "degraded",
        Scenario::Offline => "offline",
        Scenario::Stale => "stale",
        Scenario::Blocked => "blocked",
        Scenario::Unknown => "unknown",
        Scenario::Loading => "loading",
        Scenario::Empty => "empty",
        Scenario::Error => "error",
        Scenario::Disconnected => "disconnected",
    }
}
fn description(kind: &str) -> &'static str {
    match kind { "Reader" => "Recoge las observaciones del sensor y las expone por SSE.", "Manager" => "Coordina la verificación, el guardado y los reintentos de las observaciones.", "Verifier" => "Valida los campos, la fecha y la integridad del evento; firma el resultado aceptado.", "Storage" => "Almacena los eventos Verified en LevelDB.", "Publisher" => "Agrupa lecturas Verified del Manager, genera la prueba ZK y solicita el cobro en Stellar.", _ => "Instancia del despliegue seleccionado." }
}
fn metric(value: Option<f64>, unit: &str) -> String {
    value
        .map(|value| format!("{value:.1} {unit}"))
        .unwrap_or_else(|| "No disponible".into())
}
fn icon_for(kind: &str) -> &'static str {
    match kind {
        "Reader" => "radio",
        "Manager" => "workflow",
        "Verifier" => "shield",
        "Storage" => "database",
        "Publisher" => "send",
        _ => "layers",
    }
}

#[component]
fn Icon(kind: &'static str) -> impl IntoView {
    view! { <svg class="pn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{match kind {
        "activity" => view! { <path d="M2 12h4l3-8 6 16 3-8h4"/> }.into_any(),
        "radio" => view! { <g><circle cx="12" cy="12" r="2"/><path d="M8 8a6 6 0 0 0 0 8m8-8a6 6 0 0 1 0 8M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14"/></g> }.into_any(),
        "workflow" => view! { <g><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/><path d="M6 10v5a3 3 0 0 0 3 3h5M10 6h5a3 3 0 0 1 3 3v5"/></g> }.into_any(),
        "shield" => view! { <g><path d="M12 3 4 6v6c0 4 4 7 8 9 4-2 8-5 8-9V6l-8-3Z"/><path d="m8 12 3 3 5-6"/></g> }.into_any(),
        "database" => view! { <g><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/></g> }.into_any(),
        "send" => view! { <path d="m21 3-7 18-4-7-7-4 18-7ZM10 14 21 3"/> }.into_any(),
        "list" => view! { <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/> }.into_any(),
        "network" => view! { <g><rect x="8" y="2" width="8" height="6" rx="1"/><rect x="2" y="16" width="7" height="6" rx="1"/><rect x="15" y="16" width="7" height="6" rx="1"/><path d="M12 8v4M5 16v-4h14v4"/></g> }.into_any(),
        _ => view! { <path d="m12 3-10 5 10 5 10-5-10-5ZM2 12l10 5 10-5M2 16l10 5 10-5"/> }.into_any(),
    }}</svg> }
}
