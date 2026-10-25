pub mod actions;
pub mod api;
pub mod collector;
pub mod config;
pub mod docker;
pub mod inventory;
pub mod model;
pub mod operations;
pub mod probe;
pub mod views;

use std::{
    collections::HashMap,
    sync::{Arc, Mutex},
};

use rusqlite::Connection;
use tokio::sync::{broadcast, RwLock};

use crate::{config::Config, docker::DockerAdapter, inventory::Inventory, model::Operation, probe::Probe};

/// Cambios que se avisan a los navegadores conectados por SSE.
#[derive(Debug, Clone)]
pub enum Update {
    Topology(String),
    Operation(Operation),
}

/// Estado compartido: inventario, últimas observaciones, base SQLite y aviso de cambios.
#[derive(Clone)]
pub struct AppState {
    pub config: Arc<Config>,
    pub inventory: Arc<Inventory>,
    pub observations: Arc<RwLock<views::Observations>>,
    pub updates: broadcast::Sender<Update>,
    pub probe: Probe,
    pub docker: DockerAdapter,
    pub db: Arc<Mutex<Connection>>,
}

impl AppState {
    /// Estado con una base SQLite en memoria.
    pub fn new(config: Config, inventory: Inventory, docker: DockerAdapter) -> Self {
        let db = inventory::open(":memory:").expect("SQLite en memoria");
        Self::with_db(config, inventory, docker, db)
    }

    pub fn with_db(config: Config, inventory: Inventory, docker: DockerAdapter, db: Connection) -> Self {
        let inventory = Arc::new(inventory);
        let probe = if config.mock { Probe::Mock(inventory.clone()) } else { Probe::http(config.timeout) };
        let (updates, _) = broadcast::channel(16);
        Self {
            config: Arc::new(config),
            inventory,
            observations: Arc::new(RwLock::new(HashMap::new())),
            updates,
            probe,
            docker,
            db: Arc::new(Mutex::new(db)),
        }
    }
}
