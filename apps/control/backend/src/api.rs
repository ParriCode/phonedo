// Rutas HTTP y SSE que consume el frontend del panel.
use std::{convert::Infallible, time::Duration};

use axum::{
    body::Bytes,
    extract::{Path, Query, State},
    http::{header, HeaderMap, Method, StatusCode},
    response::sse::{Event, KeepAlive, Sse},
    routing::{get, post},
    Json, Router,
};
use chrono::DateTime;
use futures::Stream;
use serde::Deserialize;
use serde_json::{json, Value};
use tokio::sync::broadcast::error::RecvError;
use tower_http::cors::{Any, CorsLayer};

use crate::{
    actions,
    model::{
        now, Action, ApiError, DeploymentSummary, InstanceDetail, LogsResponse, Operation, Reading,
        ReadingKind, ReadingsResponse, Topology,
    },
    operations, views, AppState, Update,
};

const MAX_LOG_LINES: usize = 200;
const MAX_READINGS: usize = 500;
const MAX_OPERATIONS: usize = 200;

type ApiResult<T> = Result<Json<T>, (StatusCode, Json<ApiError>)>;

fn error(status: StatusCode, code: &str, message: impl Into<String>, retryable: bool) -> (StatusCode, Json<ApiError>) {
    (status, Json(ApiError::new(code, message, retryable)))
}

fn deployment_not_found(id: &str) -> (StatusCode, Json<ApiError>) {
    error(StatusCode::NOT_FOUND, "deployment_not_found", format!("No existe el despliegue {id}"), false)
}

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/api/health", get(|| async { Json(json!({ "status": "ok" })) }))
        .route("/api/deployments", get(deployments))
        .route("/api/deployments/{id}/topology", get(topology))
        .route("/api/instances/{id}", get(instance))
        .route("/api/instances/{id}/logs", get(logs))
        .route("/api/instances/{id}/actions", post(instance_action))
        .route("/api/operations", get(list_operations))
        .route("/api/operations/{id}", get(operation))
        .route("/api/readings", get(readings))
        .route("/api/stream", get(stream))
        .layer(
            CorsLayer::new()
                .allow_origin(Any)
                .allow_methods([Method::GET, Method::POST])
                .allow_headers([header::AUTHORIZATION, header::CONTENT_TYPE]),
        )
        .with_state(state)
}

/// Comparación en tiempo constante para no filtrar el token por tiempos de respuesta.
fn same_secret(a: &str, b: &str) -> bool {
    a.len() == b.len() && a.bytes().zip(b.bytes()).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

fn authorize(state: &AppState, headers: &HeaderMap) -> Result<(), (StatusCode, Json<ApiError>)> {
    let Some(expected) = state.config.admin_token.as_deref() else {
        return Err(error(StatusCode::FORBIDDEN, "admin_disabled",
                         "Acciones desactivadas: falta CONTROL_ADMIN_TOKEN en el backend", false));
    };
    let supplied = headers
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .unwrap_or("");
    if !same_secret(supplied, expected) {
        return Err(error(StatusCode::UNAUTHORIZED, "unauthorized", "Token de administración ausente o incorrecto", false));
    }
    Ok(())
}

fn http_status(error: &ApiError) -> StatusCode {
    match error.code.as_str() {
        "instance_not_found" | "container_not_found" => StatusCode::NOT_FOUND,
        "container_not_managed" => StatusCode::FORBIDDEN,
        "no_container" | "operation_in_progress" => StatusCode::CONFLICT,
        "docker_disabled" | "docker_unavailable" | "docker_timeout" => StatusCode::SERVICE_UNAVAILABLE,
        _ => StatusCode::INTERNAL_SERVER_ERROR,
    }
}

#[derive(Deserialize)]
struct ActionRequest {
    action: String,
}

/// `POST /api/instances/{id}/actions` con `{"action": "start|stop|restart"}`.
/// Responde 202 con la operación; su resultado llega por SSE o `GET /api/operations/{id}`.
async fn instance_action(
    State(state): State<AppState>,
    Path(id): Path<String>,
    headers: HeaderMap,
    body: Bytes,
) -> Result<(StatusCode, Json<Operation>), (StatusCode, Json<ApiError>)> {
    authorize(&state, &headers)?;
    let action = serde_json::from_slice::<ActionRequest>(&body)
        .ok()
        .and_then(|r| Action::parse(&r.action))
        .ok_or_else(|| error(StatusCode::BAD_REQUEST, "invalid_action",
                             "Se espera {\"action\": \"start\" | \"stop\" | \"restart\"}", false))?;
    match actions::request(&state, &id, action).await {
        Ok(operation) => Ok((StatusCode::ACCEPTED, Json(operation))),
        Err(e) => Err((http_status(&e), Json(e))),
    }
}

#[derive(Deserialize)]
struct OperationsQuery {
    deployment: Option<String>,
    limit: Option<usize>,
}

fn db_error(e: rusqlite::Error) -> (StatusCode, Json<ApiError>) {
    error(StatusCode::INTERNAL_SERVER_ERROR, "storage_error", format!("Error del inventario: {e}"), true)
}

async fn list_operations(State(state): State<AppState>, Query(query): Query<OperationsQuery>) -> ApiResult<Vec<Operation>> {
    if let Some(id) = &query.deployment {
        if state.inventory.deployment(id).is_none() {
            return Err(deployment_not_found(id));
        }
    }
    let limit = query.limit.unwrap_or(50).clamp(1, MAX_OPERATIONS);
    let db = state.db.lock().unwrap();
    operations::list(&db, query.deployment.as_deref(), limit).map(Json).map_err(db_error)
}

async fn operation(State(state): State<AppState>, Path(id): Path<String>) -> ApiResult<Operation> {
    let db = state.db.lock().unwrap();
    operations::get(&db, &id)
        .map_err(db_error)?
        .map(Json)
        .ok_or_else(|| error(StatusCode::NOT_FOUND, "operation_not_found", format!("No existe la operación {id}"), false))
}

async fn current_topology(state: &AppState, deployment_id: &str) -> Topology {
    let observations = state.observations.read().await;
    views::topology(&state.inventory, &observations, deployment_id, now(),
                    state.config.stale_after, state.config.mock)
}

async fn deployments(State(state): State<AppState>) -> Json<Vec<DeploymentSummary>> {
    Json(
        state
            .inventory
            .deployments
            .iter()
            .map(|d| DeploymentSummary {
                id: d.id.clone(),
                name: d.name.clone(),
                description: d.description.clone(),
                instances: state.inventory.instances_of(&d.id).count(),
                simulated: state.config.mock,
            })
            .collect(),
    )
}

async fn topology(State(state): State<AppState>, Path(id): Path<String>) -> ApiResult<Topology> {
    if state.inventory.deployment(&id).is_none() {
        return Err(deployment_not_found(&id));
    }
    Ok(Json(current_topology(&state, &id).await))
}

async fn instance(State(state): State<AppState>, Path(id): Path<String>) -> ApiResult<InstanceDetail> {
    let observations = state.observations.read().await;
    views::instance_detail(&state.inventory, &observations, &id, now(), state.config.stale_after, state.config.mock)
        .map(Json)
        .ok_or_else(|| error(StatusCode::NOT_FOUND, "instance_not_found", format!("No existe la instancia {id}"), false))
}

#[derive(Deserialize)]
struct LogsQuery {
    limit: Option<usize>,
}

async fn logs(State(state): State<AppState>, Path(id): Path<String>, Query(query): Query<LogsQuery>) -> ApiResult<LogsResponse> {
    if state.inventory.instance(&id).is_none() {
        return Err(error(StatusCode::NOT_FOUND, "instance_not_found", format!("No existe la instancia {id}"), false));
    }
    let limit = query.limit.unwrap_or(100).min(MAX_LOG_LINES);
    let observations = state.observations.read().await;
    let obs = observations.get(&id).cloned().unwrap_or_default();
    let skip = obs.logs.len().saturating_sub(limit);
    Ok(Json(LogsResponse {
        instance_id: id,
        simulated: state.config.mock,
        stale: views::is_stale(&obs, now(), state.config.stale_after),
        observed_at: obs.observed_at,
        lines: obs.logs.into_iter().skip(skip).collect(),
    }))
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct ReadingsQuery {
    deployment: String,
    device_id: Option<String>,
    reader_id: Option<String>,
    limit: Option<usize>,
}

fn text(value: &Value, key: &str) -> Option<String> {
    value.get(key).and_then(Value::as_str).map(str::to_string)
}

/// Lecturas verificadas de Storage, más recientes primero.
pub fn verified_readings(raw: &Value) -> Vec<Reading> {
    let Some(events) = raw.as_object() else { return Vec::new() };
    let mut items: Vec<Reading> = events
        .iter()
        .filter(|(_, v)| v.get("status").and_then(Value::as_str) == Some("Verified"))
        .map(|(key, v)| Reading {
            event_id: key.clone(),
            kind: ReadingKind::Verified,
            reader_id: text(v, "readerId"),
            device_id: text(v, "deviceId"),
            created_at: v.get("creationDatetime").and_then(Value::as_i64).and_then(DateTime::from_timestamp_millis),
            payload_format: text(v, "payloadFormat"),
            payload: v.get("payload").cloned().unwrap_or(Value::Null),
        })
        .collect();
    items.sort_by(|a, b| b.created_at.cmp(&a.created_at).then_with(|| a.event_id.cmp(&b.event_id)));
    items
}

fn mock_readings() -> Vec<Reading> {
    let start = now();
    (0..32i64)
        .map(|i| Reading {
            event_id: format!("sim-{i:02}"),
            kind: ReadingKind::Simulated,
            reader_id: Some("sim-reader".into()),
            device_id: Some("sim-hr-01".into()),
            created_at: Some(start - chrono::TimeDelta::seconds(i * 5)),
            payload_format: Some("json".into()),
            payload: json!({ "heartRate": 95 + (i * 7) % 35 }),
        })
        .collect()
}

async fn readings(State(state): State<AppState>, Query(query): Query<ReadingsQuery>) -> ApiResult<ReadingsResponse> {
    if state.inventory.deployment(&query.deployment).is_none() {
        return Err(deployment_not_found(&query.deployment));
    }
    let limit = query.limit.unwrap_or(50).clamp(1, MAX_READINGS);
    let (source, items) = if state.config.mock {
        ("simulated", mock_readings())
    } else {
        let storage = state
            .inventory
            .instances_of(&query.deployment)
            .find(|i| i.kind == "storage")
            .ok_or_else(|| error(StatusCode::NOT_FOUND, "storage_not_configured", "El despliegue no tiene Storage", false))?;
        let raw = state
            .probe
            .storage_events(storage)
            .await
            .map_err(|e| (StatusCode::BAD_GATEWAY, Json(e.to_api())))?;
        ("storage", verified_readings(&raw))
    };
    let items = items
        .into_iter()
        .filter(|r| query.device_id.is_none() || r.device_id == query.device_id)
        .filter(|r| query.reader_id.is_none() || r.reader_id == query.reader_id)
        .take(limit)
        .collect();
    Ok(Json(ReadingsResponse {
        deployment_id: query.deployment,
        simulated: state.config.mock,
        source: source.into(),
        items,
    }))
}

#[derive(Deserialize)]
struct StreamQuery {
    deployment: Option<String>,
}

/// Al conectar (o reconectar) envía `snapshot`; después, `topology` tras cada recogida
/// y `operation` cuando cambia el estado de una acción.
async fn stream(
    State(state): State<AppState>,
    Query(query): Query<StreamQuery>,
) -> Result<Sse<impl Stream<Item = Result<Event, Infallible>>>, (StatusCode, Json<ApiError>)> {
    let targets: Vec<String> = match &query.deployment {
        Some(id) if state.inventory.deployment(id).is_none() => return Err(deployment_not_found(id)),
        Some(id) => vec![id.clone()],
        None => state.inventory.deployments.iter().map(|d| d.id.clone()).collect(),
    };
    let mut updates = state.updates.subscribe();
    let events = async_stream::stream! {
        for id in &targets {
            yield Ok(event("snapshot", &current_topology(&state, id).await));
        }
        loop {
            match updates.recv().await {
                Ok(Update::Topology(id)) if targets.contains(&id) => {
                    yield Ok(event("topology", &current_topology(&state, &id).await));
                }
                Ok(Update::Operation(op)) if targets.contains(&op.deployment_id) => {
                    yield Ok(event("operation", &op));
                }
                Ok(_) => {}
                // Si el cliente se retrasa, se descarta lo pendiente y se envía el estado actual.
                Err(RecvError::Lagged(_)) => {
                    for id in &targets {
                        yield Ok(event("snapshot", &current_topology(&state, id).await));
                    }
                }
                Err(RecvError::Closed) => break,
            }
        }
    };
    Ok(Sse::new(events).keep_alive(KeepAlive::new().interval(Duration::from_secs(15))))
}

fn event<T: serde::Serialize>(name: &str, data: &T) -> Event {
    Event::default()
        .event(name)
        .json_data(data)
        .unwrap_or_else(|_| Event::default().event("error"))
}
