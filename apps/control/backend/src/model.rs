// Tipos del contrato compartido con el frontend (apps/control/contracts).
use chrono::{DateTime, SubsecRound, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;

pub type Timestamp = DateTime<Utc>;

/// Hora actual en UTC con precisión de milisegundos.
pub fn now() -> Timestamp {
    Utc::now().trunc_subsecs(3)
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ServiceStatus {
    #[default]
    Unknown,
    Healthy,
    Degraded,
    Offline,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ConnectionState {
    Configured,
    Connecting,
    Connected,
    Disconnected,
    Blocked,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Transport {
    Http,
    Sse,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ApiError {
    pub code: String,
    pub message: String,
    pub retryable: bool,
}

impl ApiError {
    pub fn new(code: &str, message: impl Into<String>, retryable: bool) -> Self {
        Self { code: code.into(), message: message.into(), retryable }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Deployment {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub description: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Instance {
    pub instance_id: String,
    #[serde(default)]
    pub deployment_id: String,
    pub kind: String,
    pub name: String,
    /// Dirección desde la que el backend consulta el servicio.
    pub url: String,
    /// Otros nombres con los que lo citan los demás servicios en `/info`.
    #[serde(default)]
    pub aliases: Vec<String>,
    #[serde(default)]
    pub container: Option<String>,
    #[serde(default)]
    pub reader_id: Option<String>,
    /// Nombre de la variable de entorno con el token; nunca su valor.
    #[serde(default, skip_serializing)]
    pub token_env: Option<String>,
}

fn normalize(value: &str) -> String {
    value.trim().trim_end_matches('/').to_ascii_lowercase()
}

impl Instance {
    pub fn matches(&self, peer: &str) -> bool {
        let peer = normalize(peer);
        normalize(&self.url) == peer
            || normalize(&self.instance_id) == peer
            || self.aliases.iter().any(|alias| normalize(alias) == peer)
            || self.reader_id.as_deref().map(normalize).as_deref() == Some(peer.as_str())
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DesiredConnection {
    #[serde(default, skip_serializing)]
    pub deployment_id: String,
    pub source_id: String,
    pub target_id: String,
    pub transport: Transport,
    pub reported_by: String,
}

/// Entrada de `GET /info` de los servicios Phonendo.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Peer {
    pub peer: String,
    pub transport: Transport,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PortInfo {
    pub private_port: u16,
    pub public_port: Option<u16>,
    pub host_ip: Option<String>,
    pub protocol: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DockerInfo {
    pub container_id: String,
    pub name: String,
    pub image: Option<String>,
    pub state: Option<String>,
    pub health: Option<String>,
    pub ports: Vec<PortInfo>,
    pub cpu_percent: Option<f64>,
    pub memory_bytes: Option<u64>,
    pub memory_limit_bytes: Option<u64>,
}

/// Último estado conocido de una instancia, compartido por todas las pestañas.
#[derive(Debug, Clone, Default)]
pub struct Observation {
    pub status: ServiceStatus,
    pub observed_at: Option<Timestamp>,
    pub last_success_at: Option<Timestamp>,
    pub last_error: Option<ApiError>,
    pub peers: Vec<Peer>,
    pub logs: Vec<String>,
    pub devices: Option<Value>,
    pub docker: Option<DockerInfo>,
    pub docker_error: Option<ApiError>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DeploymentSummary {
    pub id: String,
    pub name: String,
    pub description: String,
    pub instances: usize,
    pub simulated: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct NodeView {
    pub instance_id: String,
    pub kind: String,
    pub name: String,
    pub reader_id: Option<String>,
    pub status: ServiceStatus,
    pub stale: bool,
    pub observed_at: Option<Timestamp>,
    pub last_success_at: Option<Timestamp>,
    pub last_error: Option<ApiError>,
    pub container_state: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConnectionView {
    pub source_id: String,
    pub target_id: String,
    pub reported_by: String,
    pub transport: Transport,
    pub state: ConnectionState,
    /// `false` si aparece en `/info` pero no está en el inventario.
    pub desired: bool,
    pub observed_at: Option<Timestamp>,
    pub last_success_at: Option<Timestamp>,
    pub events_received: Option<u64>,
    pub last_error: Option<ApiError>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Topology {
    pub deployment_id: String,
    pub simulated: bool,
    pub generated_at: Timestamp,
    pub nodes: Vec<NodeView>,
    pub connections: Vec<ConnectionView>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct InstanceDetail {
    #[serde(flatten)]
    pub instance: Instance,
    pub simulated: bool,
    pub status: ServiceStatus,
    pub stale: bool,
    pub observed_at: Option<Timestamp>,
    pub last_success_at: Option<Timestamp>,
    pub last_error: Option<ApiError>,
    pub peers: Vec<Peer>,
    pub devices: Option<Value>,
    pub docker: Option<DockerInfo>,
    pub docker_error: Option<ApiError>,
    pub connections: Vec<ConnectionView>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LogsResponse {
    pub instance_id: String,
    pub simulated: bool,
    pub stale: bool,
    pub observed_at: Option<Timestamp>,
    pub lines: Vec<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ReadingKind {
    Simulated,
    Captured,
    Verified,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Reading {
    pub event_id: String,
    pub kind: ReadingKind,
    pub reader_id: Option<String>,
    pub device_id: Option<String>,
    pub created_at: Option<Timestamp>,
    pub payload_format: Option<String>,
    pub payload: Value,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Action {
    Start,
    Stop,
    Restart,
}

impl Action {
    pub fn as_str(self) -> &'static str {
        match self {
            Action::Start => "start",
            Action::Stop => "stop",
            Action::Restart => "restart",
        }
    }

    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "start" => Some(Action::Start),
            "stop" => Some(Action::Stop),
            "restart" => Some(Action::Restart),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum OperationStatus {
    Pending,
    Running,
    Succeeded,
    Failed,
}

impl OperationStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            OperationStatus::Pending => "pending",
            OperationStatus::Running => "running",
            OperationStatus::Succeeded => "succeeded",
            OperationStatus::Failed => "failed",
        }
    }

    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "pending" => Some(OperationStatus::Pending),
            "running" => Some(OperationStatus::Running),
            "succeeded" => Some(OperationStatus::Succeeded),
            "failed" => Some(OperationStatus::Failed),
            _ => None,
        }
    }

    pub fn is_finished(self) -> bool {
        matches!(self, OperationStatus::Succeeded | OperationStatus::Failed)
    }
}

/// Acción administrativa sobre una instancia y su resultado real.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Operation {
    pub operation_id: String,
    pub deployment_id: String,
    pub instance_id: String,
    pub action: Action,
    pub status: OperationStatus,
    pub requested_at: Timestamp,
    pub started_at: Option<Timestamp>,
    pub finished_at: Option<Timestamp>,
    pub error: Option<ApiError>,
}

/// `confirmed`: evento `SessionPaid` en la red. `simulated`: dato del modo simulado,
/// nunca se presenta como pago real.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SessionStatus {
    Confirmed,
    Simulated,
}

/// Sesión cobrada: lo que ve la aseguradora. No incluye lecturas.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionPayment {
    pub session_id: u64,
    pub status: SessionStatus,
    pub patient: String,
    /// Importe en unidades del activo (p. ej. "5" = 5 XLM).
    pub amount: String,
    /// Importe en la unidad mínima del contrato (7 decimales).
    pub amount_units: String,
    pub asset: String,
    pub contract_id: String,
    pub tx_hash: Option<String>,
    pub explorer_url: Option<String>,
    pub ledger: Option<u32>,
    pub paid_at: Option<Timestamp>,
    pub event_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionsResponse {
    pub simulated: bool,
    pub source: String,
    pub network: String,
    pub contract_id: Option<String>,
    pub observed_at: Option<Timestamp>,
    pub stale: bool,
    pub last_error: Option<ApiError>,
    pub items: Vec<SessionPayment>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TransactionStatus {
    Success,
    Failed,
    #[serde(rename = "not_found")]
    NotFound,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TransactionView {
    pub tx_hash: String,
    pub network: String,
    pub status: TransactionStatus,
    pub ledger: Option<u32>,
    pub created_at: Option<Timestamp>,
    pub explorer_url: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    Admin,
    Patient,
    Insurer,
    /// Sin token, solo cuando el backend no exige autenticación.
    Anonymous,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WhoAmI {
    pub role: Role,
    pub auth_required: bool,
    pub can_read_private: bool,
    pub can_act: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ReadingsResponse {
    pub deployment_id: String,
    pub simulated: bool,
    pub source: String,
    pub items: Vec<Reading>,
}
