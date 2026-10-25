use std::{collections::HashMap, time::Duration};

use axum::{
    body::Body,
    http::{Request, StatusCode},
};
use http_body_util::BodyExt;
use phonendo_control::{
    api,
    config::Config,
    docker::{check_labels, DockerAdapter, LABEL_DEPLOYMENT, LABEL_MANAGED},
    inventory::{self, Inventory, Seed},
    model::{now, Action, Operation, OperationStatus, ServiceStatus, Topology},
    operations, AppState,
};
use serde_json::{json, Value};
use tower::ServiceExt;

const TOKEN: &str = "token-de-prueba";

fn inventory() -> Inventory {
    let seed: Seed = serde_json::from_value(json!({ "deployments": [
        { "id": "a", "name": "A", "instances": [
            { "instanceId": "a-manager", "kind": "manager", "name": "Manager", "url": "http://manager", "container": "a-manager-1" },
            { "instanceId": "a-sin-contenedor", "kind": "verifier", "name": "Verifier", "url": "http://verifier" }
        ]},
        { "id": "b", "name": "B", "instances": [
            { "instanceId": "b-manager", "kind": "manager", "name": "Manager", "url": "http://other", "container": "b-manager-1" }
        ]}
    ]}))
    .unwrap();
    Inventory::from_seed(seed).unwrap()
}

fn state_with(token: Option<&str>, docker: DockerAdapter) -> AppState {
    let config = Config { mock: true, admin_token: token.map(str::to_string), ..Config::default() };
    AppState::new(config, inventory(), docker)
}

fn mock_state() -> AppState {
    state_with(Some(TOKEN), DockerAdapter::mock())
}

async fn send(state: &AppState, request: Request<Body>) -> (StatusCode, Value) {
    let response = api::router(state.clone()).oneshot(request).await.unwrap();
    let status = response.status();
    let body = response.into_body().collect().await.unwrap().to_bytes();
    (status, serde_json::from_slice(&body).unwrap_or(Value::Null))
}

fn action(instance: &str, body: &str, token: Option<&str>) -> Request<Body> {
    let mut request = Request::post(format!("/api/instances/{instance}/actions"))
        .header("content-type", "application/json");
    if let Some(token) = token {
        request = request.header("authorization", format!("Bearer {token}"));
    }
    request.body(Body::from(body.to_string())).unwrap()
}

async fn get(state: &AppState, uri: &str) -> (StatusCode, Value) {
    send(state, Request::get(uri).body(Body::empty()).unwrap()).await
}

/// Espera a que la operación termine y la devuelve.
async fn finished(state: &AppState, id: &str) -> Operation {
    for _ in 0..50 {
        let (_, body) = get(state, &format!("/api/operations/{id}")).await;
        let op: Operation = serde_json::from_value(body).unwrap();
        if op.status.is_finished() {
            return op;
        }
        tokio::time::sleep(Duration::from_millis(20)).await;
    }
    panic!("la operación {id} no terminó");
}

#[tokio::test]
async fn actions_are_disabled_without_admin_token() {
    let state = state_with(None, DockerAdapter::mock());
    let (status, body) = send(&state, action("a-manager", r#"{"action":"restart"}"#, Some(TOKEN))).await;
    assert_eq!(status, StatusCode::FORBIDDEN);
    assert_eq!(body["code"], "admin_disabled");
}

#[tokio::test]
async fn actions_require_the_right_token() {
    let state = mock_state();
    for token in [None, Some("otro-token"), Some("token-de-prueb")] {
        let (status, body) = send(&state, action("a-manager", r#"{"action":"restart"}"#, token)).await;
        assert_eq!(status, StatusCode::UNAUTHORIZED);
        assert_eq!(body["code"], "unauthorized");
    }
}

#[tokio::test]
async fn invalid_requests_are_rejected() {
    let state = mock_state();
    for body in [r#"{"action":"delete"}"#, "no es json", "{}"] {
        let (status, response) = send(&state, action("a-manager", body, Some(TOKEN))).await;
        assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");
        assert_eq!(response["code"], "invalid_action");
    }
    let (status, body) = send(&state, action("zzz", r#"{"action":"stop"}"#, Some(TOKEN))).await;
    assert_eq!(status, StatusCode::NOT_FOUND);
    assert_eq!(body["code"], "instance_not_found");

    let (status, body) = send(&state, action("a-sin-contenedor", r#"{"action":"stop"}"#, Some(TOKEN))).await;
    assert_eq!(status, StatusCode::CONFLICT);
    assert_eq!(body["code"], "no_container");
}

#[tokio::test]
async fn docker_unavailable_is_reported_before_accepting() {
    let state = state_with(Some(TOKEN), DockerAdapter::Unavailable("sin socket".into()));
    let (status, body) = send(&state, action("a-manager", r#"{"action":"restart"}"#, Some(TOKEN))).await;
    assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
    assert_eq!(body["code"], "docker_unavailable");
    let (_, list) = get(&state, "/api/operations").await;
    assert!(list.as_array().unwrap().is_empty());
}

#[tokio::test]
async fn stop_and_start_change_the_observed_state() {
    let state = mock_state();
    let (status, body) = send(&state, action("a-manager", r#"{"action":"stop"}"#, Some(TOKEN))).await;
    assert_eq!(status, StatusCode::ACCEPTED);
    assert_eq!(body["status"], "pending");
    let op = finished(&state, body["operationId"].as_str().unwrap()).await;
    assert_eq!(op.status, OperationStatus::Succeeded);
    assert!(op.started_at.is_some() && op.finished_at.is_some());

    // La recogida posterior a la acción se lanza en segundo plano.
    tokio::time::sleep(Duration::from_millis(100)).await;
    let (_, body) = get(&state, "/api/deployments/a/topology").await;
    let topology: Topology = serde_json::from_value(body).unwrap();
    let node = topology.nodes.iter().find(|n| n.instance_id == "a-manager").unwrap();
    assert_eq!(node.status, ServiceStatus::Offline);
    assert_eq!(node.container_state.as_deref(), Some("exited"));

    let (_, body) = send(&state, action("a-manager", r#"{"action":"start"}"#, Some(TOKEN))).await;
    finished(&state, body["operationId"].as_str().unwrap()).await;
    tokio::time::sleep(Duration::from_millis(100)).await;
    let (_, body) = get(&state, "/api/instances/a-manager").await;
    assert_eq!(body["status"], "healthy");
    assert_eq!(body["docker"]["state"], "running");
}

#[tokio::test]
async fn only_one_action_per_instance_at_a_time() {
    let state = mock_state();
    let busy = Operation {
        operation_id: "en-curso".into(),
        deployment_id: "a".into(),
        instance_id: "a-manager".into(),
        action: Action::Restart,
        status: OperationStatus::Running,
        requested_at: now(),
        started_at: Some(now()),
        finished_at: None,
        error: None,
    };
    operations::save(&state.db.lock().unwrap(), &busy).unwrap();

    let (status, body) = send(&state, action("a-manager", r#"{"action":"stop"}"#, Some(TOKEN))).await;
    assert_eq!(status, StatusCode::CONFLICT);
    assert_eq!(body["code"], "operation_in_progress");
    assert_eq!(body["retryable"], true);

    // Otra instancia no queda bloqueada.
    let (status, _) = send(&state, action("b-manager", r#"{"action":"stop"}"#, Some(TOKEN))).await;
    assert_eq!(status, StatusCode::ACCEPTED);
}

#[tokio::test]
async fn operations_are_listed_by_deployment() {
    let state = mock_state();
    for instance in ["a-manager", "b-manager"] {
        let (_, body) = send(&state, action(instance, r#"{"action":"restart"}"#, Some(TOKEN))).await;
        finished(&state, body["operationId"].as_str().unwrap()).await;
    }
    let (_, body) = get(&state, "/api/operations?deployment=a").await;
    let list: Vec<Operation> = serde_json::from_value(body).unwrap();
    assert_eq!(list.len(), 1);
    assert_eq!(list[0].instance_id, "a-manager");

    let (_, body) = get(&state, "/api/operations").await;
    assert_eq!(body.as_array().unwrap().len(), 2);

    let (status, body) = get(&state, "/api/operations/no-existe").await;
    assert_eq!(status, StatusCode::NOT_FOUND);
    assert_eq!(body["code"], "operation_not_found");
}

async fn next_event(body: &mut Body) -> String {
    let frame = tokio::time::timeout(Duration::from_secs(5), body.frame()).await.unwrap().unwrap().unwrap();
    String::from_utf8(frame.into_data().unwrap().to_vec()).unwrap()
}

#[tokio::test]
async fn stream_reports_operation_progress() {
    let state = mock_state();
    let mut body = api::router(state.clone())
        .oneshot(Request::get("/api/stream?deployment=a").body(Body::empty()).unwrap())
        .await
        .unwrap()
        .into_body();
    assert!(next_event(&mut body).await.starts_with("event: snapshot"));

    send(&state, action("a-manager", r#"{"action":"restart"}"#, Some(TOKEN))).await;
    let mut seen = Vec::new();
    while !seen.iter().any(|e: &String| e.contains("\"status\":\"succeeded\"")) {
        seen.push(next_event(&mut body).await);
    }
    assert!(seen[0].starts_with("event: operation") && seen[0].contains("\"status\":\"pending\""), "{seen:?}");
    assert!(seen.iter().any(|e| e.contains("\"status\":\"running\"")));
}

#[test]
fn only_labelled_containers_of_the_deployment_are_managed() {
    let labels = |pairs: &[(&str, &str)]| -> HashMap<String, String> {
        pairs.iter().map(|(k, v)| (k.to_string(), v.to_string())).collect()
    };
    assert_eq!(check_labels(None, "c", "a").unwrap_err().code, "container_not_managed");
    let other = labels(&[(LABEL_MANAGED, "true"), (LABEL_DEPLOYMENT, "b")]);
    assert_eq!(check_labels(Some(&other), "c", "a").unwrap_err().code, "container_not_managed");
    let unmanaged = labels(&[(LABEL_MANAGED, "false"), (LABEL_DEPLOYMENT, "a")]);
    assert!(check_labels(Some(&unmanaged), "c", "a").is_err());
    let ok = labels(&[(LABEL_MANAGED, "true"), (LABEL_DEPLOYMENT, "a")]);
    assert!(check_labels(Some(&ok), "c", "a").is_ok());
}

#[test]
fn unfinished_operations_fail_after_restart() {
    let db = inventory::open(":memory:").unwrap();
    let mut op = Operation {
        operation_id: "op-1".into(),
        deployment_id: "a".into(),
        instance_id: "a-manager".into(),
        action: Action::Stop,
        status: OperationStatus::Pending,
        requested_at: now(),
        started_at: None,
        finished_at: None,
        error: None,
    };
    operations::save(&db, &op).unwrap();
    op.operation_id = "op-2".into();
    op.status = OperationStatus::Succeeded;
    operations::save(&db, &op).unwrap();

    assert_eq!(operations::fail_interrupted(&db).unwrap(), 1);
    let failed = operations::get(&db, "op-1").unwrap().unwrap();
    assert_eq!(failed.status, OperationStatus::Failed);
    assert_eq!(failed.error.unwrap().code, "interrupted");
    assert_eq!(operations::get(&db, "op-2").unwrap().unwrap().status, OperationStatus::Succeeded);
}
