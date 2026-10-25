use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};

use axum::{
    body::Body,
    http::{Request, StatusCode},
    routing::post,
    Json, Router,
};
use http_body_util::BodyExt;
use phonendo_control::{
    api,
    config::Config,
    docker::DockerAdapter,
    inventory::{Inventory, Seed},
    model::{SessionStatus, SessionsResponse},
    stellar::{self, explorer_url, format_amount, parse_event},
    AppState,
};
use serde_json::{json, Value};
use tower::ServiceExt;

const CONTRACT: &str = "CAPZ2O7LPTRGJ2Q7TTHMCHOKRZ4T7KU5I4E74M2U3YUTC3XONIQDOP2D";
const PATIENT: &str = "GBBO4ZD2YNV3ZBUIBIQAH3VK73Y2RHTSMURUR5LYEK5JMXACK24YN3BC";
const TX: &str = "891b2fe1504a9d9c0a34146828e9caac9527a41e3d467eaecf5a994c145c0aa1";

/// Evento real del primer cobro en testnet, tal como lo devuelve `getEvents`.
fn paid_event() -> Value {
    json!({
        "type": "contract", "ledger": 5381362, "ledgerClosedAt": "2026-10-25T12:13:17Z",
        "contractId": CONTRACT, "id": "0023112773797957632-0000000001",
        "operationIndex": 0, "transactionIndex": 5, "txHash": TX,
        "topicJson": [{ "symbol": "session_paid" }, { "u64": "20261025001" }],
        "valueJson": { "map": [
            { "key": { "symbol": "amount" }, "val": { "i128": "50000000" } },
            { "key": { "symbol": "patient" }, "val": { "address": PATIENT } }
        ]}
    })
}

/// RPC falso: un evento en la primera página, nada en las siguientes.
async fn fake_rpc(fail: Arc<AtomicBool>) -> String {
    let app = Router::new().route("/", post(move |Json(body): Json<Value>| {
        let fail = fail.clone();
        async move {
            if fail.load(Ordering::SeqCst) {
                return Json(json!({ "jsonrpc": "2.0", "id": 1, "error": { "code": -32600, "message": "caído" } }));
            }
            let params = &body["params"];
            let result = match body["method"].as_str().unwrap() {
                "getHealth" => json!({ "status": "healthy", "latestLedger": 5383156, "oldestLedger": 5262197 }),
                "getEvents" if params.get("startLedger").is_some() => json!({
                    "events": [paid_event(), { "topicJson": [{ "symbol": "otro_evento" }], "valueJson": {} }],
                    "cursor": "0023112773797957632-0000000001", "latestLedger": 5383156
                }),
                "getEvents" => json!({
                    "events": [], "cursor": "0023120509034037247-4294967295", "latestLedger": 5383156
                }),
                "getTransaction" if params["hash"] == TX => json!({
                    "status": "SUCCESS", "ledger": 5381362, "createdAt": "1792930397", "latestLedger": 5383162
                }),
                "getTransaction" => json!({ "status": "NOT_FOUND", "latestLedger": 5383162 }),
                _ => json!({}),
            };
            Json(json!({ "jsonrpc": "2.0", "id": 1, "result": result }))
        }
    }));
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    format!("http://{addr}/")
}

fn inventory() -> Inventory {
    let seed: Seed = serde_json::from_value(json!({ "deployments": [{ "id": "a", "name": "A", "instances": [
        { "instanceId": "a-storage", "kind": "storage", "name": "Storage", "url": "http://127.0.0.1:9" }
    ]}]}))
    .unwrap();
    Inventory::from_seed(seed).unwrap()
}

fn config(rpc: Option<&str>) -> Config {
    Config {
        contract_id: rpc.map(|_| CONTRACT.to_string()),
        stellar_rpc: rpc.unwrap_or_default().to_string(),
        ..Config::default()
    }
}

fn with_roles(mut config: Config) -> Config {
    config.admin_token = Some("tk-admin".into());
    config.patient_token = Some("tk-paciente".into());
    config.insurer_token = Some("tk-aseguradora".into());
    config
}

async fn get(state: &AppState, uri: &str, token: Option<&str>) -> (StatusCode, Value) {
    let mut request = Request::get(uri);
    if let Some(token) = token {
        request = request.header("authorization", format!("Bearer {token}"));
    }
    let response = api::router(state.clone()).oneshot(request.body(Body::empty()).unwrap()).await.unwrap();
    let status = response.status();
    let body = response.into_body().collect().await.unwrap().to_bytes();
    (status, serde_json::from_slice(&body).unwrap_or(Value::Null))
}

#[test]
fn real_testnet_event_is_parsed() {
    let session = parse_event(&paid_event(), "testnet", "XLM").unwrap();
    assert_eq!(session.session_id, 20261025001);
    assert_eq!(session.status, SessionStatus::Confirmed);
    assert_eq!(session.patient, PATIENT);
    assert_eq!(session.amount, "5");
    assert_eq!(session.amount_units, "50000000");
    assert_eq!(session.contract_id, CONTRACT);
    assert_eq!(session.ledger, Some(5381362));
    assert_eq!(session.explorer_url.as_deref(), Some(format!("https://stellar.expert/explorer/testnet/tx/{TX}").as_str()));
    assert_eq!(session.paid_at.unwrap().to_rfc3339(), "2026-10-25T12:13:17+00:00");

    let other = json!({ "topicJson": [{ "symbol": "set_policy" }], "valueJson": {} });
    assert!(parse_event(&other, "testnet", "XLM").is_none());
}

#[test]
fn amounts_and_links_are_formatted() {
    assert_eq!(format_amount(50_000_000, 7), "5");
    assert_eq!(format_amount(12_345_678, 7), "1.2345678");
    assert_eq!(format_amount(1, 7), "0.0000001");
    assert_eq!(format_amount(25_000_000, 7), "2.5");
    assert!(explorer_url("mainnet", "ab").contains("/explorer/public/tx/ab"));
}

#[tokio::test]
async fn sessions_come_from_contract_events() {
    let fail = Arc::new(AtomicBool::new(false));
    let rpc = fake_rpc(fail.clone()).await;
    let state = AppState::new(config(Some(&rpc)), inventory(), DockerAdapter::Off);
    let mut updates = state.updates.subscribe();

    stellar::collect_once(&state).await;
    assert!(matches!(updates.try_recv(), Ok(phonendo_control::Update::Sessions)));
    let (status, body) = get(&state, "/api/sessions", None).await;
    assert_eq!(status, StatusCode::OK);
    let response: SessionsResponse = serde_json::from_value(body).unwrap();
    assert!(!response.simulated);
    assert_eq!(response.contract_id.as_deref(), Some(CONTRACT));
    assert_eq!(response.items.len(), 1);
    assert_eq!(response.items[0].tx_hash.as_deref(), Some(TX));

    // La siguiente recogida sigue desde el cursor y no duplica.
    stellar::collect_once(&state).await;
    assert_eq!(state.sessions.read().await.items.len(), 1);
    assert!(updates.try_recv().is_err());

    // Si el RPC falla se conserva lo conocido y se informa del error.
    fail.store(true, Ordering::SeqCst);
    stellar::collect_once(&state).await;
    let (_, body) = get(&state, "/api/sessions", None).await;
    assert_eq!(body["items"].as_array().unwrap().len(), 1);
    assert_eq!(body["lastError"]["code"], "stellar_rpc");

    let (_, body) = get(&state, &format!("/api/sessions?patient={PATIENT}"), None).await;
    assert_eq!(body["items"].as_array().unwrap().len(), 1);
    let (_, body) = get(&state, "/api/sessions?patient=GOTRA", None).await;
    assert!(body["items"].as_array().unwrap().is_empty());
}

#[tokio::test]
async fn transactions_are_checked_on_chain() {
    let rpc = fake_rpc(Arc::new(AtomicBool::new(false))).await;
    let state = AppState::new(config(Some(&rpc)), inventory(), DockerAdapter::Off);

    let (status, body) = get(&state, &format!("/api/transactions/{TX}"), None).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["status"], "success");
    assert_eq!(body["ledger"], 5381362);
    assert!(body["explorerUrl"].as_str().unwrap().ends_with(TX));

    let unknown = "0".repeat(64);
    let (_, body) = get(&state, &format!("/api/transactions/{unknown}"), None).await;
    assert_eq!(body["status"], "not_found");

    let (status, body) = get(&state, "/api/transactions/zz", None).await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert_eq!(body["code"], "invalid_hash");
}

#[tokio::test]
async fn without_contract_sessions_report_it() {
    let state = AppState::new(config(None), inventory(), DockerAdapter::Off);
    let (status, body) = get(&state, "/api/sessions", None).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["lastError"]["code"], "stellar_disabled");
    assert!(body["items"].as_array().unwrap().is_empty());
}

#[tokio::test]
async fn simulated_sessions_are_never_confirmed() {
    let state = AppState::new(Config { mock: true, ..Config::default() }, inventory(), DockerAdapter::mock());
    let (_, body) = get(&state, "/api/sessions", None).await;
    let response: SessionsResponse = serde_json::from_value(body).unwrap();
    assert!(response.simulated);
    assert!(!response.items.is_empty());
    for session in response.items {
        assert_eq!(session.status, SessionStatus::Simulated);
        assert!(session.tx_hash.is_none() && session.explorer_url.is_none());
    }
}

#[tokio::test]
async fn insurer_sees_payments_but_never_readings_or_logs() {
    let state = AppState::new(with_roles(Config { mock: true, ..Config::default() }), inventory(), DockerAdapter::mock());
    let insurer = Some("tk-aseguradora");

    let (status, _) = get(&state, "/api/sessions", insurer).await;
    assert_eq!(status, StatusCode::OK);
    for uri in ["/api/readings?deployment=a", "/api/instances/a-storage/logs", "/api/instances/a-storage"] {
        let (status, body) = get(&state, uri, insurer).await;
        assert_eq!(status, StatusCode::FORBIDDEN, "{uri}");
        assert_eq!(body["code"], "role_forbidden");
    }
    let (_, body) = get(&state, "/api/me", insurer).await;
    assert_eq!(body["role"], "insurer");
    assert_eq!(body["canReadPrivate"], false);
    assert_eq!(body["canAct"], false);
}

#[tokio::test]
async fn patient_and_admin_read_private_data() {
    let state = AppState::new(with_roles(Config { mock: true, ..Config::default() }), inventory(), DockerAdapter::mock());
    for token in ["tk-paciente", "tk-admin"] {
        let (status, body) = get(&state, "/api/readings?deployment=a", Some(token)).await;
        assert_eq!(status, StatusCode::OK, "{token}");
        assert!(!body["items"].as_array().unwrap().is_empty());
    }
    let (_, body) = get(&state, "/api/me", Some("tk-admin")).await;
    assert_eq!(body["role"], "admin");
    assert_eq!(body["canAct"], true);

    // Una paciente no puede ejecutar acciones.
    let request = Request::post("/api/instances/a-storage/actions")
        .header("authorization", "Bearer tk-paciente")
        .body(Body::from(r#"{"action":"stop"}"#))
        .unwrap();
    let response = api::router(state.clone()).oneshot(request).await.unwrap();
    assert_eq!(response.status(), StatusCode::FORBIDDEN);
}

#[tokio::test]
async fn private_data_requires_a_token_when_roles_are_configured() {
    let state = AppState::new(with_roles(Config { mock: true, ..Config::default() }), inventory(), DockerAdapter::mock());
    for uri in ["/api/readings?deployment=a", "/api/sessions", "/api/me"] {
        let (status, body) = get(&state, uri, None).await;
        assert_eq!(status, StatusCode::UNAUTHORIZED, "{uri}");
        assert_eq!(body["code"], "unauthorized");
    }
    let (status, _) = get(&state, "/api/readings?deployment=a", Some("inventado")).await;
    assert_eq!(status, StatusCode::UNAUTHORIZED);
    // El mapa no contiene datos privados y sigue abierto.
    let (status, _) = get(&state, "/api/deployments/a/topology", None).await;
    assert_eq!(status, StatusCode::OK);

    // Sin roles configurados (desarrollo), todo se puede consultar sin token.
    let open = AppState::new(Config { mock: true, ..Config::default() }, inventory(), DockerAdapter::mock());
    let (_, body) = get(&open, "/api/me", None).await;
    assert_eq!(body["role"], "anonymous");
    assert_eq!(body["authRequired"], false);
}
