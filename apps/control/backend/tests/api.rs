use std::time::{Duration, Instant};

use axum::{
    body::Body,
    http::{Request, StatusCode},
    routing::get,
    Json, Router,
};
use http_body_util::BodyExt;
use phonendo_control::{
    api, collector,
    config::Config,
    docker::DockerAdapter,
    inventory::{self, Inventory, Seed},
    model::{ConnectionState, InstanceDetail, ServiceStatus, Topology},
    views, AppState,
};
use serde_json::{json, Value};
use tower::ServiceExt;

/// Arranca un servicio falso en un puerto libre y devuelve su URL.
async fn fake_service(router: Router) -> String {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move { axum::serve(listener, router).await.unwrap() });
    format!("http://{addr}")
}

/// URL de un puerto en el que no escucha nadie.
async fn closed_url() -> String {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    drop(listener);
    format!("http://{addr}")
}

fn info(peers: Value) -> Router {
    Router::new()
        .route("/info", get(move || { let p = peers.clone(); async move { Json(p) } }))
        .route("/logs", get(|| async { Json(json!(["started"])) }))
        .route("/devices", get(|| async { Json(json!([{ "deviceId": "hr-01" }])) }))
}

fn seed(value: Value) -> Inventory {
    let seed: Seed = serde_json::from_value(value).unwrap();
    Inventory::from_seed(seed).unwrap()
}

/// Despliegue `a` (reader -> manager por HTTP) y despliegue `b` con un manager.
fn two_deployments(reader: &str, manager: &str, other: &str) -> Inventory {
    seed(json!({ "deployments": [
        { "id": "a", "name": "A", "instances": [
            { "instanceId": "a-reader", "kind": "reader", "name": "Reader", "url": reader,
              "aliases": ["http://manager-alias"], "readerId": "reader-a", "tokenEnv": "READER_TOKEN" },
            { "instanceId": "a-manager", "kind": "manager", "name": "Manager", "url": manager,
              "aliases": ["http://manager:3003"] }
        ], "connections": [
            { "sourceId": "a-reader", "targetId": "a-manager", "transport": "http", "reportedBy": "a-reader" }
        ]},
        { "id": "b", "name": "B", "instances": [
            { "instanceId": "b-manager", "kind": "manager", "name": "Manager", "url": other }
        ]}
    ]}))
}

fn config(timeout_ms: u64) -> Config {
    Config { timeout: Duration::from_millis(timeout_ms), ..Config::default() }
}

fn state(inventory: Inventory, timeout_ms: u64) -> AppState {
    AppState::new(config(timeout_ms), inventory, DockerAdapter::Off)
}

async fn get_json(state: &AppState, uri: &str) -> (StatusCode, Value) {
    let response = api::router(state.clone())
        .oneshot(Request::get(uri).body(Body::empty()).unwrap())
        .await
        .unwrap();
    let status = response.status();
    let body = response.into_body().collect().await.unwrap().to_bytes();
    (status, serde_json::from_slice(&body).unwrap())
}

async fn healthy_pair() -> (String, String) {
    let manager = fake_service(info(json!([{ "peer": "reader-a", "transport": "http" }]))).await;
    let reader = fake_service(info(json!([{ "peer": "http://manager:3003/", "transport": "http" }]))).await;
    (reader, manager)
}

#[tokio::test]
async fn healthy_services_report_their_connections() {
    let (reader, manager) = healthy_pair().await;
    let state = state(two_deployments(&reader, &manager, &closed_url().await), 1000);
    collector::collect_once(&state, "a").await;

    let (status, body) = get_json(&state, "/api/deployments/a/topology").await;
    assert_eq!(status, StatusCode::OK);
    let topology: Topology = serde_json::from_value(body).unwrap();
    assert!(topology.nodes.iter().all(|n| n.status == ServiceStatus::Healthy && !n.stale));
    assert_eq!(topology.connections.len(), 1);
    let connection = &topology.connections[0];
    assert_eq!(connection.state, ConnectionState::Configured);
    assert!(connection.desired);
    assert!(connection.last_success_at.is_some());
}

#[tokio::test]
async fn offline_service_does_not_hide_the_others() {
    let reader = fake_service(info(json!([{ "peer": "http://manager:3003", "transport": "http" }]))).await;
    let state = state(two_deployments(&reader, &closed_url().await, &closed_url().await), 1000);
    collector::collect_once(&state, "a").await;

    let (_, body) = get_json(&state, "/api/deployments/a/topology").await;
    let topology: Topology = serde_json::from_value(body).unwrap();
    let node = |id: &str| topology.nodes.iter().find(|n| n.instance_id == id).unwrap();
    assert_eq!(node("a-reader").status, ServiceStatus::Healthy);
    assert_eq!(node("a-manager").status, ServiceStatus::Offline);
    assert_eq!(node("a-manager").last_error.as_ref().unwrap().code, "unreachable");
    assert_eq!(topology.connections[0].state, ConnectionState::Disconnected);
}

#[tokio::test]
async fn slow_service_times_out() {
    let slow = fake_service(Router::new().route("/info", get(|| async {
        tokio::time::sleep(Duration::from_secs(3)).await;
        Json(json!([]))
    })))
    .await;
    let (reader, _) = healthy_pair().await;
    let state = state(two_deployments(&reader, &slow, &closed_url().await), 200);

    let started = Instant::now();
    collector::collect_once(&state, "a").await;
    assert!(started.elapsed() < Duration::from_secs(2));

    let (_, body) = get_json(&state, "/api/instances/a-manager").await;
    let detail: InstanceDetail = serde_json::from_value(body).unwrap();
    assert_eq!(detail.status, ServiceStatus::Offline);
    let error = detail.last_error.unwrap();
    assert_eq!(error.code, "timeout");
    assert!(error.retryable);
}

#[tokio::test]
async fn invalid_json_marks_service_degraded() {
    let broken = fake_service(Router::new().route("/info", get(|| async { "esto no es json" }))).await;
    let (reader, _) = healthy_pair().await;
    let state = state(two_deployments(&reader, &broken, &closed_url().await), 1000);
    collector::collect_once(&state, "a").await;

    let (_, body) = get_json(&state, "/api/instances/a-manager").await;
    let detail: InstanceDetail = serde_json::from_value(body).unwrap();
    assert_eq!(detail.status, ServiceStatus::Degraded);
    assert_eq!(detail.last_error.unwrap().code, "invalid_response");
}

#[tokio::test]
async fn docker_unavailable_keeps_service_status() {
    let (reader, manager) = healthy_pair().await;
    let mut inventory = two_deployments(&reader, &manager, &closed_url().await);
    inventory.instances[1].container = Some("phonendo-manager-1".into());
    let state = AppState::new(config(1000), inventory,
                              DockerAdapter::Unavailable("socket no encontrado".into()));
    collector::collect_once(&state, "a").await;

    let (_, body) = get_json(&state, "/api/instances/a-manager").await;
    let detail: InstanceDetail = serde_json::from_value(body).unwrap();
    assert_eq!(detail.status, ServiceStatus::Healthy);
    assert!(detail.docker.is_none());
    assert_eq!(detail.docker_error.unwrap().code, "docker_unavailable");
}

#[tokio::test]
async fn old_observations_are_marked_stale() {
    let (reader, manager) = healthy_pair().await;
    let state = state(two_deployments(&reader, &manager, &closed_url().await), 1000);
    collector::collect_once(&state, "a").await;
    {
        let mut observations = state.observations.write().await;
        let obs = observations.get_mut("a-manager").unwrap();
        obs.observed_at = Some(obs.observed_at.unwrap() - chrono::TimeDelta::minutes(5));
    }
    let (_, body) = get_json(&state, "/api/deployments/a/topology").await;
    let topology: Topology = serde_json::from_value(body).unwrap();
    let manager = topology.nodes.iter().find(|n| n.instance_id == "a-manager").unwrap();
    assert!(manager.stale);
    assert_eq!(manager.status, ServiceStatus::Healthy);
    assert!(manager.observed_at.is_some());
}

#[tokio::test]
async fn deployments_are_kept_separate() {
    let (reader, manager) = healthy_pair().await;
    let other = fake_service(info(json!([]))).await;
    let state = state(two_deployments(&reader, &manager, &other), 1000);
    collector::collect_once(&state, "a").await;

    let (_, body) = get_json(&state, "/api/deployments").await;
    assert_eq!(body.as_array().unwrap().len(), 2);

    let (_, body) = get_json(&state, "/api/deployments/b/topology").await;
    let topology: Topology = serde_json::from_value(body).unwrap();
    assert_eq!(topology.nodes.len(), 1);
    assert_eq!(topology.nodes[0].instance_id, "b-manager");
    // Solo se ha recogido `a`: `b` sigue sin estado conocido.
    assert_eq!(topology.nodes[0].status, ServiceStatus::Unknown);
    assert!(topology.connections.is_empty());

    let (status, body) = get_json(&state, "/api/deployments/zzz/topology").await;
    assert_eq!(status, StatusCode::NOT_FOUND);
    assert_eq!(body["code"], "deployment_not_found");
    assert_eq!(body["retryable"], false);
}

#[tokio::test]
async fn undeclared_connections_are_reported_as_not_desired() {
    let manager = fake_service(info(json!([{ "peer": "reader-a", "transport": "sse" }]))).await;
    let reader = fake_service(info(json!([{ "peer": "http://manager:3003", "transport": "http" }]))).await;
    let state = state(two_deployments(&reader, &manager, &closed_url().await), 1000);
    collector::collect_once(&state, "a").await;

    let (_, body) = get_json(&state, "/api/deployments/a/topology").await;
    let topology: Topology = serde_json::from_value(body).unwrap();
    let extra = topology.connections.iter().find(|c| !c.desired).unwrap();
    assert_eq!(extra.reported_by, "a-manager");
    assert_eq!(extra.state, ConnectionState::Connected);
}

async fn next_event(body: &mut Body) -> String {
    let frame = tokio::time::timeout(Duration::from_secs(5), body.frame()).await.unwrap().unwrap().unwrap();
    String::from_utf8(frame.into_data().unwrap().to_vec()).unwrap()
}

#[tokio::test]
async fn stream_sends_snapshot_then_updates_and_again_on_reconnect() {
    let (reader, manager) = healthy_pair().await;
    let state = state(two_deployments(&reader, &manager, &closed_url().await), 1000);

    let open = || async {
        api::router(state.clone())
            .oneshot(Request::get("/api/stream?deployment=a").body(Body::empty()).unwrap())
            .await
            .unwrap()
            .into_body()
    };
    let mut first = open().await;
    let snapshot = next_event(&mut first).await;
    assert!(snapshot.starts_with("event: snapshot"), "{snapshot}");
    assert!(snapshot.contains("\"status\":\"unknown\""));

    collector::collect_once(&state, "b").await; // otro despliegue: no se envía
    collector::collect_once(&state, "a").await;
    let update = next_event(&mut first).await;
    assert!(update.starts_with("event: topology"), "{update}");
    assert!(update.contains("\"status\":\"healthy\""));
    drop(first);

    // Reconexión: el navegador recibe una instantánea completa, sin replay.
    let mut second = open().await;
    let snapshot = next_event(&mut second).await;
    assert!(snapshot.starts_with("event: snapshot"));
    assert!(snapshot.contains("\"status\":\"healthy\""));

    let (status, _) = get_json(&state, "/api/stream?deployment=zzz").await;
    assert_eq!(status, StatusCode::NOT_FOUND);
}

#[tokio::test]
async fn readings_come_from_storage_filtered_and_limited() {
    let raw = json!({
        "e1": { "status": "Verified", "deviceId": "hr-01", "readerId": "reader-a", "creationDatetime": 1000, "payload": { "bpm": 100 } },
        "e2": { "status": "Verified", "deviceId": "hr-01", "readerId": "reader-a", "creationDatetime": 3000, "payload": { "bpm": 110 } },
        "e3": { "status": "Verified", "deviceId": "hr-02", "readerId": "reader-a", "creationDatetime": 2000, "payload": { "bpm": 120 } },
        "e4": { "status": "Captured", "deviceId": "hr-01", "creationDatetime": 4000, "payload": { "bpm": 130 } }
    });
    let storage = fake_service(Router::new().route("/raw", get(move || { let r = raw.clone(); async move { Json(r) } }))).await;
    let inventory = seed(json!({ "deployments": [{ "id": "a", "name": "A", "instances": [
        { "instanceId": "a-storage", "kind": "storage", "name": "Storage", "url": storage }
    ]}]}));
    let state = state(inventory, 1000);

    let (status, body) = get_json(&state, "/api/readings?deployment=a&deviceId=hr-01&limit=1").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["source"], "storage");
    let items = body["items"].as_array().unwrap();
    assert_eq!(items.len(), 1);
    assert_eq!(items[0]["eventId"], "e2");
    assert_eq!(items[0]["kind"], "verified");
    assert_eq!(items[0]["createdAt"], "1970-01-01T00:00:03Z");

    let (_, body) = get_json(&state, "/api/readings?deployment=a").await;
    assert_eq!(body["items"].as_array().unwrap().len(), 3);
}

#[tokio::test]
async fn readings_report_storage_failure() {
    let inventory = seed(json!({ "deployments": [{ "id": "a", "name": "A", "instances": [
        { "instanceId": "a-storage", "kind": "storage", "name": "Storage", "url": closed_url().await }
    ]}]}));
    let state = state(inventory, 500);
    let (status, body) = get_json(&state, "/api/readings?deployment=a").await;
    assert_eq!(status, StatusCode::BAD_GATEWAY);
    assert_eq!(body["code"], "unreachable");
    assert_eq!(body["retryable"], true);
}

#[tokio::test]
async fn logs_are_limited_and_sanitized() {
    let service = fake_service(
        Router::new()
            .route("/info", get(|| async { Json(json!([])) }))
            .route("/logs", get(|| async {
                Json(json!(["uno", "token=abc123 enviado", "Authorization: Bearer xyz", r#"{"password": "1234"}"#]))
            })),
    )
    .await;
    let inventory = seed(json!({ "deployments": [{ "id": "a", "name": "A", "instances": [
        { "instanceId": "a-verifier", "kind": "verifier", "name": "Verifier", "url": service }
    ]}]}));
    let state = state(inventory, 1000);
    collector::collect_once(&state, "a").await;

    let (_, body) = get_json(&state, "/api/instances/a-verifier/logs?limit=3").await;
    let lines: Vec<String> = serde_json::from_value(body["lines"].clone()).unwrap();
    assert_eq!(lines.len(), 3);
    let joined = lines.join("\n");
    for secret in ["abc123", "xyz", "1234"] {
        assert!(!joined.contains(secret), "{joined}");
    }
}

#[test]
fn inventory_round_trips_through_sqlite_without_exposing_secrets() {
    let inventory = two_deployments("http://r", "http://m", "http://o");
    let mut db = inventory::open(":memory:").unwrap();
    assert!(inventory::is_empty(&db).unwrap());
    inventory::save(&mut db, &inventory).unwrap();
    let loaded = inventory::load(&db).unwrap();

    assert_eq!(loaded.deployments.len(), 2);
    assert_eq!(loaded.instances.len(), 3);
    assert_eq!(loaded.connections.len(), 1);
    let reader = loaded.instance("a-reader").unwrap();
    assert_eq!(reader.token_env.as_deref(), Some("READER_TOKEN"));
    assert_eq!(reader.aliases, vec!["http://manager-alias".to_string()]);

    let detail = views::instance_detail(&loaded, &Default::default(), "a-reader",
                                        phonendo_control::model::now(), Duration::from_secs(9), false).unwrap();
    let text = serde_json::to_string(&detail).unwrap();
    assert!(!text.contains("tokenEnv") && !text.contains("READER_TOKEN"), "{text}");
}

#[test]
fn invalid_inventory_is_rejected() {
    let seed: Seed = serde_json::from_value(json!({ "deployments": [
        { "id": "a", "name": "A", "instances": [{ "instanceId": "x", "kind": "manager", "name": "X", "url": "http://x" }] },
        { "id": "b", "name": "B", "instances": [{ "instanceId": "y", "kind": "manager", "name": "Y", "url": "http://y" }],
          "connections": [{ "sourceId": "x", "targetId": "y", "transport": "http", "reportedBy": "x" }] }
    ]}))
    .unwrap();
    assert!(Inventory::from_seed(seed).is_err());
}

#[test]
fn bundled_seed_is_valid() {
    let seed = inventory::read_seed(std::path::Path::new(concat!(env!("CARGO_MANIFEST_DIR"), "/seed.json"))).unwrap();
    assert!(Inventory::from_seed(seed).is_ok());
}

#[test]
fn contract_examples_match_the_api_types() {
    let examples = concat!(env!("CARGO_MANIFEST_DIR"), "/../contracts/examples");
    let read = |name: &str| -> Value {
        serde_json::from_str(&std::fs::read_to_string(format!("{examples}/{name}")).unwrap()).unwrap()
    };
    let _: Vec<phonendo_control::model::DeploymentSummary> = serde_json::from_value(read("deployments.json")).unwrap();
    for name in ["topology-normal.json", "topology-service-down.json", "topology-stale.json", "topology-redundant-rejected.json"] {
        let _: Topology = serde_json::from_value(read(name)).unwrap_or_else(|e| panic!("{name}: {e}"));
    }
    let _: InstanceDetail = serde_json::from_value(read("instance.json")).unwrap();
    let _: phonendo_control::model::LogsResponse = serde_json::from_value(read("logs.json")).unwrap();
    let _: phonendo_control::model::ReadingsResponse = serde_json::from_value(read("readings.json")).unwrap();
    let _: phonendo_control::model::ApiError = serde_json::from_value(read("error.json")).unwrap();
    let _: phonendo_control::model::Operation = serde_json::from_value(read("operation.json")).unwrap();
    let _: phonendo_control::model::SessionsResponse = serde_json::from_value(read("sessions.json")).unwrap();
    let _: phonendo_control::model::TransactionView = serde_json::from_value(read("transaction.json")).unwrap();
    let _: phonendo_control::model::WhoAmI = serde_json::from_value(read("me.json")).unwrap();
}
