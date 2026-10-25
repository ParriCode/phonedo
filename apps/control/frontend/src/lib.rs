use serde::{Deserialize, Serialize};

pub const LOG_LIMIT: usize = 50;
pub const READING_LIMIT: usize = 32;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Status {
    Unknown,
    Healthy,
    Degraded,
    Offline,
}

impl Status {
    pub fn label(self) -> &'static str {
        match self {
            Self::Unknown => "Desconocido",
            Self::Healthy => "Disponible",
            Self::Degraded => "Degradado",
            Self::Offline => "Sin respuesta",
        }
    }
    pub fn class(self) -> &'static str {
        match self {
            Self::Unknown => "unknown",
            Self::Healthy => "healthy",
            Self::Degraded => "degraded",
            Self::Offline => "offline",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ServiceError {
    pub code: String,
    pub message: String,
    pub retryable: bool,
}

#[derive(Clone, Debug, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Node {
    pub instance_id: String,
    pub kind: String,
    pub status: Status,
    pub reader_id: Option<String>,
    pub address: String,
    pub container_state: Option<String>,
    pub observed_at: String,
    pub last_activity_at: Option<String>,
    pub devices: Vec<String>,
    pub cpu_percent: Option<f64>,
    pub memory_mb: Option<f64>,
    pub last_error: Option<ServiceError>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Transport {
    Http,
    Sse,
}
impl Transport {
    pub fn label(self) -> &'static str {
        match self {
            Self::Http => "HTTP",
            Self::Sse => "SSE",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum ConnectionState {
    Configured,
    Connecting,
    Connected,
    Disconnected,
    Blocked,
}
impl ConnectionState {
    pub fn label(self, transport: Transport) -> &'static str {
        match self {
            Self::Configured if transport == Transport::Http => "Destino configurado",
            Self::Configured => "Configurada",
            Self::Connecting if transport == Transport::Http => "Petición en curso",
            Self::Connecting => "Conectando",
            Self::Connected if transport == Transport::Http => "Última petición correcta",
            Self::Connected => "Conectada",
            Self::Disconnected if transport == Transport::Http => "Último intento sin respuesta",
            Self::Disconnected => "Desconectada",
            Self::Blocked => "Rechazada",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Connection {
    pub source_id: String,
    pub target_id: String,
    pub reported_by: String,
    pub transport: Transport,
    pub state: ConnectionState,
    pub observed_at: String,
    pub last_success_at: Option<String>,
    pub events_received: u64,
    pub last_error: Option<ServiceError>,
}

#[derive(Clone, Debug, PartialEq, Deserialize, Serialize)]
pub struct Reading {
    pub at: String,
    pub value: u8,
}
#[derive(Clone, Debug, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Log {
    pub instance_id: String,
    pub at: String,
    pub level: String,
    pub message: String,
    #[serde(default)]
    pub related_instance_ids: Vec<String>,
    #[serde(default)]
    pub code: Option<String>,
    #[serde(default)]
    pub detail: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Snapshot {
    pub deployment_id: String,
    pub name: String,
    pub simulated: bool,
    pub observed_at: String,
    pub stale: bool,
    pub nodes: Vec<Node>,
    pub connections: Vec<Connection>,
    pub readings: Vec<Reading>,
    pub logs: Vec<Log>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Scenario {
    Normal,
    Degraded,
    Offline,
    Stale,
    Blocked,
    Unknown,
    Loading,
    Empty,
    Error,
    Disconnected,
}
impl Scenario {
    pub fn parse(value: &str) -> Self {
        match value {
            "degraded" => Self::Degraded,
            "offline" => Self::Offline,
            "stale" => Self::Stale,
            "blocked" => Self::Blocked,
            "unknown" => Self::Unknown,
            "loading" => Self::Loading,
            "empty" => Self::Empty,
            "error" => Self::Error,
            "disconnected" => Self::Disconnected,
            _ => Self::Normal,
        }
    }
    pub fn hides_data(self) -> bool {
        matches!(self, Self::Loading | Self::Empty | Self::Error)
    }
    pub fn notice(self) -> &'static str {
        match self {
            Self::Normal => "Ejemplos estáticos. No hay conexión con los servicios ni con Stellar.",
            Self::Degraded => "Escenario simulado: el último guardado no obtuvo respuesta y el Manager debe reintentarlo.",
            Self::Offline => "Escenario simulado: Storage no responde. Se conserva su última actividad conocida.",
            Self::Stale => "Instantánea antigua: la disponibilidad actual de los servicios es desconocida.",
            Self::Blocked => "Escenario simulado: el Manager rechaza una suscripción SSE redundante; prevalece HTTP.",
            Self::Unknown => "No hay información suficiente para determinar la disponibilidad del Reader.",
            Self::Loading => "Cargando el despliegue… Este estado es una simulación manual.",
            Self::Empty => "No hay instancias en este despliegue de ejemplo.",
            Self::Error => "No se pudo cargar el despliegue de ejemplo. Puedes volver al escenario normal.",
            Self::Disconnected => "Backend desconectado (simulación). Se conserva la última instantánea sin darla por actual.",
        }
    }
}

pub fn demo(scenario: Scenario) -> Result<Snapshot, serde_json::Error> {
    let mut data: Snapshot = serde_json::from_str(include_str!("../examples/topology.json"))?;
    match scenario {
        Scenario::Offline | Scenario::Degraded => {
            if let Some(storage) = data.nodes.iter_mut().find(|n| n.kind == "Storage") {
                storage.status = if scenario == Scenario::Degraded {
                    Status::Degraded
                } else {
                    Status::Offline
                };
                // El estado del contenedor no permite deducir la salud del servicio.
                storage.last_error = Some(ServiceError {
                    code: "TIMEOUT".into(),
                    message: "Sin respuesta en el último intento (ejemplo).".into(),
                    retryable: true,
                });
            }
            for connection in &mut data.connections {
                if connection.target_id == "storage-01" {
                    connection.state = ConnectionState::Disconnected;
                    connection.last_error = Some(ServiceError {
                        code: "TIMEOUT".into(),
                        message: "El último intento HTTP no obtuvo respuesta (ejemplo).".into(),
                        retryable: true,
                    });
                }
            }
            data.logs.push(Log {
                instance_id: "manager-01".into(), at: data.observed_at.clone(), level: "WARN".into(),
                message: "Guardado pendiente de reintento.".into(), related_instance_ids: vec!["storage-01".into()],
                code: Some("STORAGE_TIMEOUT".into()),
                detail: Some("Storage no respondió al último intento HTTP. El Manager conserva el evento para reintentarlo. Escenario simulado.".into()),
            });
        }
        Scenario::Blocked => {
            if let Some(mut connection) = data
                .connections
                .iter()
                .find(|c| c.target_id == "verifier-01")
                .cloned()
            {
                connection.transport = Transport::Sse;
                connection.state = ConnectionState::Blocked;
                connection.last_success_at = None;
                connection.events_received = 0;
                connection.last_error = Some(ServiceError {
                    code: "HTTP_409".into(),
                    message:
                        "SSE redundante: el Manager ya utiliza HTTP con este Verifier (ejemplo)."
                            .into(),
                    retryable: false,
                });
                data.connections.push(connection);
            }
        }
        Scenario::Unknown => {
            data.nodes[0].status = Status::Unknown;
        }
        Scenario::Stale | Scenario::Disconnected => {
            data.stale = true;
        }
        Scenario::Empty => {
            data.nodes.clear();
            data.connections.clear();
            data.readings.clear();
            data.logs.clear();
        }
        _ => {}
    }
    Ok(data)
}

impl Snapshot {
    /// Logs del servicio y de operaciones que lo mencionan, de más reciente a más antiguo.
    pub fn related_logs(&self, instance_id: Option<&str>) -> Vec<Log> {
        self.logs
            .iter()
            .rev()
            .filter(|log| {
                instance_id.is_none_or(|id| {
                    log.instance_id == id
                        || log.related_instance_ids.iter().any(|related| related == id)
                })
            })
            .take(LOG_LIMIT)
            .cloned()
            .collect()
    }

    pub fn visible_status(&self, node: &Node) -> Status {
        if self.stale {
            Status::Unknown
        } else {
            node.status
        }
    }
    pub fn recent_logs(&self, instance_id: &str) -> Vec<Log> {
        let mut logs: Vec<_> = self
            .logs
            .iter()
            .filter(|log| log.instance_id == instance_id)
            .rev()
            .take(LOG_LIMIT)
            .cloned()
            .collect();
        logs.reverse();
        logs
    }
    pub fn chart_points(&self) -> String {
        let readings: Vec<_> = self
            .readings
            .iter()
            .rev()
            .take(READING_LIMIT)
            .rev()
            .collect();
        readings
            .iter()
            .enumerate()
            .map(|(i, reading)| {
                let x = 40.0 + i as f64 * 600.0 / readings.len().saturating_sub(1).max(1) as f64;
                let y = 180.0 - f64::from(reading.value) / 255.0 * 160.0;
                format!("{x:.1},{y:.1}")
            })
            .collect::<Vec<_>>()
            .join(" ")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn example_connections_reference_existing_instances() {
        let snapshot = demo(Scenario::Normal).unwrap();
        assert!(snapshot.simulated);
        for edge in &snapshot.connections {
            for id in [&edge.source_id, &edge.target_id, &edge.reported_by] {
                assert!(snapshot.nodes.iter().any(|node| &node.instance_id == id));
            }
        }
    }
    #[test]
    fn stale_and_disconnected_never_show_healthy() {
        for scenario in [Scenario::Stale, Scenario::Disconnected] {
            let snapshot = demo(scenario).unwrap();
            assert!(snapshot
                .nodes
                .iter()
                .all(|node| snapshot.visible_status(node) == Status::Unknown));
        }
    }
    #[test]
    fn running_container_does_not_imply_healthy_service() {
        let snapshot = demo(Scenario::Offline).unwrap();
        let storage = snapshot.nodes.iter().find(|n| n.kind == "Storage").unwrap();
        assert_eq!(storage.container_state.as_deref(), Some("running"));
        assert_eq!(snapshot.visible_status(storage), Status::Offline);
        assert!(storage.last_activity_at.is_some());
    }
    #[test]
    fn rejected_sse_preserves_working_http() {
        let snapshot = demo(Scenario::Blocked).unwrap();
        let verifier: Vec<_> = snapshot
            .connections
            .iter()
            .filter(|c| c.target_id == "verifier-01")
            .collect();
        assert!(verifier
            .iter()
            .any(|c| c.transport == Transport::Http && c.state == ConnectionState::Connected));
        assert!(verifier.iter().any(|c| c.transport == Transport::Sse
            && c.state == ConnectionState::Blocked
            && c.events_received == 0));
    }
    #[test]
    fn logs_are_filtered_and_bounded() {
        let mut snapshot = demo(Scenario::Normal).unwrap();
        for i in 0..80 {
            snapshot.logs.push(Log {
                instance_id: "reader-01".into(),
                at: i.to_string(),
                level: "INFO".into(),
                message: i.to_string(),
                related_instance_ids: vec![],
                code: None,
                detail: None,
            });
        }
        let logs = snapshot.recent_logs("reader-01");
        assert_eq!(logs.len(), LOG_LIMIT);
        assert_eq!(logs.first().unwrap().message, "30");
        assert_eq!(logs.last().unwrap().message, "79");
        assert!(snapshot.recent_logs("missing").is_empty());
    }
    #[test]
    fn chart_and_empty_deployment_are_bounded() {
        let mut snapshot = demo(Scenario::Normal).unwrap();
        snapshot.readings = vec![
            Reading {
                at: "12:00:00".into(),
                value: 100
            };
            100
        ];
        assert_eq!(
            snapshot.chart_points().split_whitespace().count(),
            READING_LIMIT
        );
        let empty = demo(Scenario::Empty).unwrap();
        assert!(empty.nodes.is_empty() && empty.connections.is_empty());
        assert_eq!(empty.chart_points(), "");
    }

    #[test]
    fn related_logs_include_other_reporters_without_duplicates() {
        let snapshot = demo(Scenario::Degraded).unwrap();
        let manager_logs = snapshot.related_logs(Some("manager-01"));
        assert_eq!(manager_logs.len(), 4);
        assert!(manager_logs
            .iter()
            .any(|log| log.instance_id == "reader-01"));
        assert!(manager_logs
            .iter()
            .any(|log| log.instance_id == "verifier-01"));
        assert_eq!(manager_logs[0].code.as_deref(), Some("STORAGE_TIMEOUT"));
        assert_eq!(snapshot.related_logs(Some("storage-01")).len(), 2);
        assert_eq!(snapshot.related_logs(None).len(), 5);
        assert!(snapshot.related_logs(Some("publisher-01")).is_empty());
    }

    #[test]
    fn degraded_state_preserves_the_last_successful_activity() {
        let snapshot = demo(Scenario::Degraded).unwrap();
        let storage = snapshot.nodes.iter().find(|n| n.kind == "Storage").unwrap();
        assert_eq!(storage.status, Status::Degraded);
        assert_eq!(storage.container_state.as_deref(), Some("running"));
        let edge = snapshot
            .connections
            .iter()
            .find(|c| c.target_id == storage.instance_id)
            .unwrap();
        assert_eq!(edge.state, ConnectionState::Disconnected);
        assert!(edge.last_success_at.is_some());
        assert_eq!(edge.last_error.as_ref().unwrap().code, "TIMEOUT");
    }

    #[test]
    fn unmonitored_publisher_has_no_invented_connections() {
        let snapshot = demo(Scenario::Normal).unwrap();
        let publisher = snapshot
            .nodes
            .iter()
            .find(|n| n.kind == "Publisher")
            .unwrap();
        assert_eq!(publisher.status, Status::Unknown);
        assert!(publisher.container_state.is_none());
        assert!(!snapshot
            .connections
            .iter()
            .any(|c| c.source_id == publisher.instance_id || c.target_id == publisher.instance_id));
    }

    #[test]
    fn all_and_related_logs_remain_bounded_after_filtering() {
        let mut snapshot = demo(Scenario::Normal).unwrap();
        for i in 0..80 {
            snapshot.logs.push(Log {
                instance_id: "reader-01".into(),
                related_instance_ids: vec!["manager-01".into()],
                at: i.to_string(),
                level: "INFO".into(),
                message: i.to_string(),
                code: None,
                detail: None,
            });
        }
        let related = snapshot.related_logs(Some("manager-01"));
        assert_eq!(related.len(), LOG_LIMIT);
        assert_eq!(related[0].message, "79");
        assert_eq!(related[49].message, "30");
        assert_eq!(snapshot.related_logs(None).len(), LOG_LIMIT);
    }

    #[test]
    fn http_labels_describe_requests_instead_of_persistent_connections() {
        assert_eq!(
            ConnectionState::Disconnected.label(Transport::Http),
            "Último intento sin respuesta"
        );
        assert_eq!(
            ConnectionState::Disconnected.label(Transport::Sse),
            "Desconectada"
        );
        assert_eq!(
            ConnectionState::Connecting.label(Transport::Http),
            "Petición en curso"
        );
        assert_eq!(
            ConnectionState::Connected.label(Transport::Http),
            "Última petición correcta"
        );
    }
}
