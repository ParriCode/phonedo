use std::{path::Path, process::ExitCode};

use phonendo_control::{api, collector, config::Config, docker::DockerAdapter, inventory, operations, AppState};
use tracing::{error, info, warn};

#[tokio::main]
async fn main() -> ExitCode {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .init();
    match run().await {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            error!("{e}");
            ExitCode::FAILURE
        }
    }
}

async fn run() -> Result<(), String> {
    let config = Config::from_env()?;
    let mut db = inventory::open(&config.db_path).map_err(|e| format!("SQLite {}: {e}", config.db_path))?;
    if inventory::is_empty(&db).map_err(|e| e.to_string())? {
        let seed = inventory::read_seed(Path::new(&config.seed_path))?;
        let initial = inventory::Inventory::from_seed(seed)?;
        inventory::save(&mut db, &initial).map_err(|e| format!("no se pudo guardar la semilla: {e}"))?;
        info!("inventario inicial cargado desde {}", config.seed_path);
    }
    let inventory = inventory::load(&db).map_err(|e| e.to_string())?;
    let interrupted = operations::fail_interrupted(&db).map_err(|e| e.to_string())?;
    if interrupted > 0 {
        warn!("{interrupted} operaciones sin terminar marcadas como fallidas");
    }
    if config.admin_token.is_none() {
        warn!("CONTROL_ADMIN_TOKEN sin definir: acciones administrativas desactivadas");
    }

    let docker = DockerAdapter::connect(config.docker, config.mock);
    let addr = config.addr.clone();
    let mode = if config.mock { "simulado" } else { "real" };
    let state = AppState::with_db(config, inventory, docker, db);
    for deployment in &state.inventory.deployments {
        tokio::spawn(collector::run(state.clone(), deployment.id.clone()));
    }

    let listener = tokio::net::TcpListener::bind(&addr).await.map_err(|e| format!("{addr}: {e}"))?;
    info!("panel escuchando en http://{addr} (modo {mode})");
    axum::serve(listener, api::router(state))
        .with_graceful_shutdown(async {
            let _ = tokio::signal::ctrl_c().await;
        })
        .await
        .map_err(|e| e.to_string())
}
