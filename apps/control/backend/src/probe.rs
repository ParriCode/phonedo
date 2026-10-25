// Consultas a los servicios Phonendo (`/info`, `/logs`, `/devices`, `/raw`)
// o datos simulados cuando CONTROL_MODE=mock.
use std::{env, sync::Arc, time::Duration};

use serde::de::DeserializeOwned;
use serde_json::{json, Value};

use crate::{
    inventory::Inventory,
    model::{ApiError, Instance, Peer, ServiceStatus},
};

#[derive(Debug, Clone, PartialEq)]
pub enum ProbeError {
    Timeout,
    Unreachable(String),
    Status(u16),
    Invalid(String),
}

impl ProbeError {
    /// Estado del servicio que implica el fallo: sin respuesta = offline;
    /// responde pero no cumple el contrato = degraded.
    pub fn status(&self) -> ServiceStatus {
        match self {
            ProbeError::Timeout | ProbeError::Unreachable(_) => ServiceStatus::Offline,
            ProbeError::Status(_) | ProbeError::Invalid(_) => ServiceStatus::Degraded,
        }
    }

    pub fn to_api(&self) -> ApiError {
        match self {
            ProbeError::Timeout => ApiError::new("timeout", "El servicio no respondió a tiempo", true),
            ProbeError::Unreachable(e) => ApiError::new("unreachable", format!("Sin conexión: {e}"), true),
            ProbeError::Status(code) => ApiError::new("http_status", format!("Respuesta HTTP {code}"), true),
            ProbeError::Invalid(e) => ApiError::new("invalid_response", format!("Respuesta no válida: {e}"), false),
        }
    }
}

#[derive(Clone)]
pub enum Probe {
    Http(reqwest::Client),
    Mock(Arc<Inventory>),
}

impl Probe {
    pub fn http(timeout: Duration) -> Self {
        let client = reqwest::Client::builder()
            .timeout(timeout)
            .connect_timeout(timeout)
            .build()
            .expect("cliente HTTP");
        Probe::Http(client)
    }

    async fn get<T: DeserializeOwned>(client: &reqwest::Client, instance: &Instance, path: &str) -> Result<T, ProbeError> {
        let url = format!("{}{}", instance.url.trim_end_matches('/'), path);
        let mut request = client.get(&url);
        if let Some(token) = instance.token_env.as_deref().and_then(|name| env::var(name).ok()) {
            request = request.bearer_auth(token);
        }
        let map_err = |e: reqwest::Error| {
            if e.is_timeout() {
                ProbeError::Timeout
            } else {
                ProbeError::Unreachable(e.without_url().to_string())
            }
        };
        let response = request.send().await.map_err(map_err)?;
        if !response.status().is_success() {
            return Err(ProbeError::Status(response.status().as_u16()));
        }
        let body = response.text().await.map_err(map_err)?;
        serde_json::from_str(&body).map_err(|e| ProbeError::Invalid(e.to_string()))
    }

    pub async fn info(&self, instance: &Instance) -> Result<Vec<Peer>, ProbeError> {
        match self {
            Probe::Http(client) => Self::get(client, instance, "/info").await,
            Probe::Mock(inventory) => Ok(mock_peers(inventory, instance)),
        }
    }

    pub async fn logs(&self, instance: &Instance) -> Result<Vec<String>, ProbeError> {
        match self {
            Probe::Http(client) => {
                let lines: Vec<Value> = Self::get(client, instance, "/logs").await?;
                Ok(lines
                    .into_iter()
                    .map(|line| match line {
                        Value::String(s) => s,
                        other => other.to_string(),
                    })
                    .collect())
            }
            Probe::Mock(_) => Ok(vec![
                format!("{}_started (simulado)", instance.kind),
                "event_received (simulado)".into(),
            ]),
        }
    }

    pub async fn devices(&self, instance: &Instance) -> Result<Value, ProbeError> {
        match self {
            Probe::Http(client) => Self::get(client, instance, "/devices").await,
            Probe::Mock(_) => Ok(json!([{ "deviceId": "sim-hr-01", "sensors": ["heartRate"] }])),
        }
    }

    /// Eventos de Storage. Falta una consulta filtrada y paginada en Storage,
    /// así que por ahora se lee `/raw` y se filtra aquí.
    pub async fn storage_events(&self, instance: &Instance) -> Result<Value, ProbeError> {
        match self {
            Probe::Http(client) => Self::get(client, instance, "/raw").await,
            Probe::Mock(_) => Ok(json!({})),
        }
    }

    pub fn is_mock(&self) -> bool {
        matches!(self, Probe::Mock(_))
    }
}

/// En modo simulado cada instancia informa de las conexiones del inventario.
fn mock_peers(inventory: &Inventory, instance: &Instance) -> Vec<Peer> {
    inventory
        .connections_of(&instance.deployment_id)
        .filter(|c| c.reported_by == instance.instance_id)
        .filter_map(|c| {
            let other = if c.source_id == instance.instance_id { &c.target_id } else { &c.source_id };
            inventory.instance(other).map(|o| Peer { peer: o.url.clone(), transport: c.transport })
        })
        .collect()
}
