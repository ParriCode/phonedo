// Inventario del panel en SQLite: despliegues, instancias y conexiones deseadas.
// Los eventos verificados siguen en Storage; aquí no se copian.
use std::{collections::HashSet, fs, path::Path};

use rusqlite::{params, Connection};
use serde::Deserialize;

use crate::model::{Deployment, DesiredConnection, Instance, Transport};

#[derive(Debug, Deserialize)]
pub struct Seed {
    pub deployments: Vec<SeedDeployment>,
}

#[derive(Debug, Deserialize)]
pub struct SeedDeployment {
    #[serde(flatten)]
    pub deployment: Deployment,
    #[serde(default)]
    pub instances: Vec<Instance>,
    #[serde(default)]
    pub connections: Vec<DesiredConnection>,
}

#[derive(Debug, Default, Clone)]
pub struct Inventory {
    pub deployments: Vec<Deployment>,
    pub instances: Vec<Instance>,
    pub connections: Vec<DesiredConnection>,
}

impl Inventory {
    /// Construye y valida el inventario a partir de una semilla.
    pub fn from_seed(seed: Seed) -> Result<Self, String> {
        let mut inventory = Inventory::default();
        for item in seed.deployments {
            let deployment_id = item.deployment.id.clone();
            inventory.deployments.push(item.deployment);
            for mut instance in item.instances {
                instance.deployment_id = deployment_id.clone();
                inventory.instances.push(instance);
            }
            for mut connection in item.connections {
                connection.deployment_id = deployment_id.clone();
                inventory.connections.push(connection);
            }
        }
        inventory.validate()?;
        Ok(inventory)
    }

    fn validate(&self) -> Result<(), String> {
        let mut deployments = HashSet::new();
        for deployment in &self.deployments {
            if !deployments.insert(deployment.id.as_str()) {
                return Err(format!("despliegue duplicado: {}", deployment.id));
            }
        }
        let mut instances = HashSet::new();
        for instance in &self.instances {
            if !instances.insert(instance.instance_id.as_str()) {
                return Err(format!("instancia duplicada: {}", instance.instance_id));
            }
        }
        for c in &self.connections {
            for id in [&c.source_id, &c.target_id] {
                match self.instance(id) {
                    Some(i) if i.deployment_id == c.deployment_id => {}
                    _ => return Err(format!("conexión {}->{}: {id} no pertenece a {}",
                                            c.source_id, c.target_id, c.deployment_id)),
                }
            }
            if c.reported_by != c.source_id && c.reported_by != c.target_id {
                return Err(format!("conexión {}->{}: reportedBy debe ser origen o destino",
                                   c.source_id, c.target_id));
            }
        }
        Ok(())
    }

    pub fn deployment(&self, id: &str) -> Option<&Deployment> {
        self.deployments.iter().find(|d| d.id == id)
    }

    pub fn instance(&self, id: &str) -> Option<&Instance> {
        self.instances.iter().find(|i| i.instance_id == id)
    }

    pub fn instances_of<'a>(&'a self, deployment_id: &'a str) -> impl Iterator<Item = &'a Instance> {
        self.instances.iter().filter(move |i| i.deployment_id == deployment_id)
    }

    pub fn connections_of<'a>(&'a self, deployment_id: &'a str) -> impl Iterator<Item = &'a DesiredConnection> {
        self.connections.iter().filter(move |c| c.deployment_id == deployment_id)
    }
}

pub fn read_seed(path: &Path) -> Result<Seed, String> {
    let text = fs::read_to_string(path).map_err(|e| format!("no se pudo leer {}: {e}", path.display()))?;
    serde_json::from_str(&text).map_err(|e| format!("semilla inválida {}: {e}", path.display()))
}

pub fn open(path: &str) -> rusqlite::Result<Connection> {
    let conn = Connection::open(path)?;
    conn.execute_batch(
        "PRAGMA foreign_keys = ON;
         CREATE TABLE IF NOT EXISTS deployments (
             id TEXT PRIMARY KEY,
             name TEXT NOT NULL,
             description TEXT NOT NULL DEFAULT ''
         );
         CREATE TABLE IF NOT EXISTS instances (
             id TEXT PRIMARY KEY,
             deployment_id TEXT NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
             kind TEXT NOT NULL,
             name TEXT NOT NULL,
             url TEXT NOT NULL,
             aliases TEXT NOT NULL DEFAULT '[]',
             container TEXT,
             reader_id TEXT,
             token_env TEXT
         );
         CREATE TABLE IF NOT EXISTS connections (
             deployment_id TEXT NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
             source_id TEXT NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
             target_id TEXT NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
             transport TEXT NOT NULL CHECK (transport IN ('http', 'sse')),
             reported_by TEXT NOT NULL,
             PRIMARY KEY (deployment_id, source_id, target_id, transport)
         );
         CREATE TABLE IF NOT EXISTS operations (
             id TEXT PRIMARY KEY,
             deployment_id TEXT NOT NULL,
             instance_id TEXT NOT NULL,
             action TEXT NOT NULL,
             status TEXT NOT NULL,
             requested_at TEXT NOT NULL,
             started_at TEXT,
             finished_at TEXT,
             error TEXT
         );
         CREATE INDEX IF NOT EXISTS operations_by_deployment ON operations (deployment_id, requested_at);",
    )?;
    Ok(conn)
}

pub fn is_empty(conn: &Connection) -> rusqlite::Result<bool> {
    let count: i64 = conn.query_row("SELECT COUNT(*) FROM deployments", [], |row| row.get(0))?;
    Ok(count == 0)
}

fn transport_name(transport: Transport) -> &'static str {
    match transport {
        Transport::Http => "http",
        Transport::Sse => "sse",
    }
}

pub fn save(conn: &mut Connection, inventory: &Inventory) -> rusqlite::Result<()> {
    let tx = conn.transaction()?;
    for d in &inventory.deployments {
        tx.execute("INSERT INTO deployments (id, name, description) VALUES (?1, ?2, ?3)",
                   params![d.id, d.name, d.description])?;
    }
    for i in &inventory.instances {
        tx.execute(
            "INSERT INTO instances (id, deployment_id, kind, name, url, aliases, container, reader_id, token_env)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
            params![i.instance_id, i.deployment_id, i.kind, i.name, i.url,
                    serde_json::to_string(&i.aliases).unwrap_or_else(|_| "[]".into()),
                    i.container, i.reader_id, i.token_env],
        )?;
    }
    for c in &inventory.connections {
        tx.execute(
            "INSERT INTO connections (deployment_id, source_id, target_id, transport, reported_by)
             VALUES (?1, ?2, ?3, ?4, ?5)",
            params![c.deployment_id, c.source_id, c.target_id, transport_name(c.transport), c.reported_by],
        )?;
    }
    tx.commit()
}

pub fn load(conn: &Connection) -> rusqlite::Result<Inventory> {
    let deployments = conn
        .prepare("SELECT id, name, description FROM deployments ORDER BY id")?
        .query_map([], |row| Ok(Deployment { id: row.get(0)?, name: row.get(1)?, description: row.get(2)? }))?
        .collect::<Result<_, _>>()?;
    let instances = conn
        .prepare("SELECT id, deployment_id, kind, name, url, aliases, container, reader_id, token_env
                  FROM instances ORDER BY deployment_id, id")?
        .query_map([], |row| {
            let aliases: String = row.get(5)?;
            Ok(Instance {
                instance_id: row.get(0)?,
                deployment_id: row.get(1)?,
                kind: row.get(2)?,
                name: row.get(3)?,
                url: row.get(4)?,
                aliases: serde_json::from_str(&aliases).unwrap_or_default(),
                container: row.get(6)?,
                reader_id: row.get(7)?,
                token_env: row.get(8)?,
            })
        })?
        .collect::<Result<_, _>>()?;
    let connections = conn
        .prepare("SELECT deployment_id, source_id, target_id, transport, reported_by
                  FROM connections ORDER BY deployment_id, source_id, target_id")?
        .query_map([], |row| {
            let transport: String = row.get(3)?;
            Ok(DesiredConnection {
                deployment_id: row.get(0)?,
                source_id: row.get(1)?,
                target_id: row.get(2)?,
                transport: if transport == "sse" { Transport::Sse } else { Transport::Http },
                reported_by: row.get(4)?,
            })
        })?
        .collect::<Result<_, _>>()?;
    Ok(Inventory { deployments, instances, connections })
}
