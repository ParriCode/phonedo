// Sesiones cobradas: eventos `SessionPaid` del contrato `adherence` leídos del RPC de Stellar.
use std::time::Duration;

use chrono::DateTime;
use serde_json::{json, Value};

use crate::{
    model::{
        now, ApiError, SessionPayment, SessionStatus, Timestamp, TransactionStatus, TransactionView,
    },
    AppState, Update,
};

/// Decimales del token del contrato (XLM y USDC en Soroban usan 7).
const DECIMALS: u32 = 7;
const MAX_SESSIONS: usize = 1000;
/// Páginas de `getEvents` por recogida; cada una cubre hasta ~10 000 ledgers.
const MAX_PAGES: usize = 20;

#[derive(Clone)]
pub struct StellarSource {
    client: reqwest::Client,
    pub rpc_url: String,
    pub network: String,
    pub contract_id: String,
    pub asset: String,
    pub lookback: u32,
}

#[derive(Debug, Default, Clone)]
pub struct SessionsCache {
    pub items: Vec<SessionPayment>,
    pub cursor: Option<String>,
    pub observed_at: Option<Timestamp>,
    pub last_error: Option<ApiError>,
}

pub fn explorer_url(network: &str, tx_hash: &str) -> String {
    let network = if network == "mainnet" || network == "public" { "public" } else { network };
    format!("https://stellar.expert/explorer/{network}/tx/{tx_hash}")
}

/// `50000000` con 7 decimales -> `"5"`; `12345678` -> `"1.2345678"`.
pub fn format_amount(units: i128, decimals: u32) -> String {
    let scale = 10i128.pow(decimals);
    let sign = if units < 0 { "-" } else { "" };
    let (whole, fraction) = (units.abs() / scale, units.abs() % scale);
    if fraction == 0 {
        return format!("{sign}{whole}");
    }
    let fraction = format!("{fraction:0width$}", width = decimals as usize);
    format!("{sign}{whole}.{}", fraction.trim_end_matches('0'))
}

fn rpc_error(message: impl Into<String>) -> ApiError {
    ApiError::new("stellar_rpc", message, true)
}

/// Ledger de un cursor de `getEvents` (TOID: ledger en los 32 bits altos).
fn cursor_ledger(cursor: &str) -> Option<u32> {
    let toid: u64 = cursor.split('-').next()?.parse().ok()?;
    Some((toid >> 32) as u32)
}

fn map_entry<'a>(map: &'a Value, key: &str) -> Option<&'a Value> {
    map.get("map")?
        .as_array()?
        .iter()
        .find(|e| e.pointer("/key/symbol").and_then(Value::as_str) == Some(key))
        .and_then(|e| e.get("val"))
}

/// Convierte un evento de `getEvents` (`xdrFormat: json`) en sesión cobrada.
pub fn parse_event(event: &Value, network: &str, asset: &str) -> Option<SessionPayment> {
    let topics = event.get("topicJson")?.as_array()?;
    if topics.first()?.get("symbol")?.as_str()? != "session_paid" {
        return None;
    }
    let session_id = topics.get(1)?.get("u64")?.as_str()?.parse().ok()?;
    let value = event.get("valueJson")?;
    let units: i128 = map_entry(value, "amount")?.get("i128")?.as_str()?.parse().ok()?;
    let patient = map_entry(value, "patient")?.get("address")?.as_str()?.to_string();
    let tx_hash = event.get("txHash").and_then(Value::as_str).map(str::to_string);
    Some(SessionPayment {
        session_id,
        status: SessionStatus::Confirmed,
        patient,
        amount: format_amount(units, DECIMALS),
        amount_units: units.to_string(),
        asset: asset.to_string(),
        contract_id: event.get("contractId").and_then(Value::as_str).unwrap_or_default().to_string(),
        explorer_url: tx_hash.as_deref().map(|h| explorer_url(network, h)),
        tx_hash,
        ledger: event.get("ledger").and_then(Value::as_u64).map(|l| l as u32),
        paid_at: event
            .get("ledgerClosedAt")
            .and_then(Value::as_str)
            .and_then(|t| DateTime::parse_from_rfc3339(t).ok())
            .map(|t| t.to_utc()),
        event_id: event.get("id").and_then(Value::as_str).map(str::to_string),
    })
}

impl StellarSource {
    pub fn new(rpc_url: String, network: String, contract_id: String, asset: String, lookback: u32, timeout: Duration) -> Self {
        let client = reqwest::Client::builder()
            .timeout(timeout)
            .user_agent(concat!("phonendo-control/", env!("CARGO_PKG_VERSION")))
            .build()
            .expect("cliente HTTP");
        Self { client, rpc_url, network, contract_id, asset, lookback }
    }

    async fn call(&self, method: &str, params: Value) -> Result<Value, ApiError> {
        let body = json!({ "jsonrpc": "2.0", "id": 1, "method": method, "params": params });
        let response = self
            .client
            .post(&self.rpc_url)
            .json(&body)
            .send()
            .await
            .map_err(|e| if e.is_timeout() { rpc_error("El RPC de Stellar no respondió a tiempo") }
                         else { rpc_error(format!("Sin conexión con el RPC: {}", e.without_url())) })?;
        if !response.status().is_success() {
            return Err(rpc_error(format!("RPC respondió HTTP {}", response.status().as_u16())));
        }
        let mut reply: Value = response.json().await.map_err(|e| rpc_error(format!("Respuesta no válida: {e}")))?;
        if let Some(error) = reply.get("error") {
            let message = error.get("message").and_then(Value::as_str).unwrap_or("error desconocido");
            return Err(rpc_error(format!("{method}: {message}")));
        }
        reply.get_mut("result").map(Value::take).ok_or_else(|| rpc_error("Respuesta sin result"))
    }

    /// Lee eventos nuevos desde `cursor` (o desde `lookback` ledgers atrás) hasta el último ledger.
    pub async fn fetch(&self, cursor: Option<String>) -> Result<(Vec<SessionPayment>, Option<String>), ApiError> {
        let filters = json!([{ "type": "contract", "contractIds": [self.contract_id] }]);
        let mut params = match &cursor {
            Some(c) => json!({ "filters": filters, "pagination": { "limit": 100, "cursor": c }, "xdrFormat": "json" }),
            None => {
                let health = self.call("getHealth", json!({})).await?;
                let latest = health.get("latestLedger").and_then(Value::as_u64).unwrap_or(0) as u32;
                let oldest = health.get("oldestLedger").and_then(Value::as_u64).unwrap_or(0) as u32;
                let start = latest.saturating_sub(self.lookback).max(oldest);
                json!({ "startLedger": start, "filters": filters, "pagination": { "limit": 100 }, "xdrFormat": "json" })
            }
        };
        let mut found = Vec::new();
        let mut cursor = cursor;
        for _ in 0..MAX_PAGES {
            let result = self.call("getEvents", params).await?;
            let events = result.get("events").and_then(Value::as_array).cloned().unwrap_or_default();
            found.extend(events.iter().filter_map(|e| parse_event(e, &self.network, &self.asset)));
            let next = result.get("cursor").and_then(Value::as_str).map(str::to_string);
            let latest = result.get("latestLedger").and_then(Value::as_u64).unwrap_or(0) as u32;
            let done = events.is_empty() && next.as_deref().and_then(cursor_ledger).is_none_or(|l| l >= latest);
            if next.is_none() || next == cursor {
                break;
            }
            cursor = next;
            if done {
                break;
            }
            params = json!({ "filters": filters, "pagination": { "limit": 100, "cursor": cursor }, "xdrFormat": "json" });
        }
        Ok((found, cursor))
    }

    pub async fn transaction(&self, tx_hash: &str) -> Result<TransactionView, ApiError> {
        let result = self.call("getTransaction", json!({ "hash": tx_hash })).await?;
        let status = match result.get("status").and_then(Value::as_str) {
            Some("SUCCESS") => TransactionStatus::Success,
            Some("FAILED") => TransactionStatus::Failed,
            _ => TransactionStatus::NotFound,
        };
        Ok(TransactionView {
            tx_hash: tx_hash.to_string(),
            network: self.network.clone(),
            status,
            ledger: result.get("ledger").and_then(Value::as_u64).map(|l| l as u32),
            created_at: result
                .get("createdAt")
                .and_then(Value::as_str)
                .and_then(|t| t.parse().ok())
                .and_then(|t| DateTime::from_timestamp(t, 0)),
            explorer_url: explorer_url(&self.network, tx_hash),
        })
    }
}

/// Una recogida: añade las sesiones nuevas y avisa por SSE si hay cambios.
pub async fn collect_once(state: &AppState) {
    let Some(source) = &state.stellar else { return };
    let cursor = state.sessions.read().await.cursor.clone();
    let result = source.fetch(cursor).await;
    let mut cache = state.sessions.write().await;
    cache.observed_at = Some(now());
    match result {
        Ok((found, cursor)) => {
            cache.last_error = None;
            cache.cursor = cursor;
            let before = cache.items.len();
            for payment in found {
                if !cache.items.iter().any(|p| p.session_id == payment.session_id && p.event_id == payment.event_id) {
                    cache.items.push(payment);
                }
            }
            cache.items.sort_by(|a, b| b.ledger.cmp(&a.ledger).then(b.session_id.cmp(&a.session_id)));
            cache.items.truncate(MAX_SESSIONS);
            if cache.items.len() != before {
                let _ = state.updates.send(Update::Sessions);
            }
        }
        Err(e) => cache.last_error = Some(e),
    }
}

pub async fn run(state: AppState) {
    let mut ticker = tokio::time::interval(state.config.stellar_poll);
    ticker.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
    loop {
        ticker.tick().await;
        collect_once(&state).await;
    }
}

/// Sesiones del modo simulado: nunca aparecen como confirmadas ni con transacción.
pub fn mock_sessions() -> Vec<SessionPayment> {
    let start = now();
    (0..3u64)
        .map(|i| SessionPayment {
            session_id: 1_000 + i,
            status: SessionStatus::Simulated,
            patient: "GSIMULADA".into(),
            amount: "5".into(),
            amount_units: "50000000".into(),
            asset: "XLM".into(),
            contract_id: String::new(),
            tx_hash: None,
            explorer_url: None,
            ledger: None,
            paid_at: Some(start - chrono::TimeDelta::minutes(30 * i as i64)),
            event_id: None,
        })
        .collect()
}
