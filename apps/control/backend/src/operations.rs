// Registro de operaciones administrativas en SQLite.
use chrono::DateTime;
use rusqlite::{params, Connection, OptionalExtension, Row};

use crate::model::{now, Action, ApiError, Operation, OperationStatus, Timestamp};

const COLUMNS: &str = "id, deployment_id, instance_id, action, status, requested_at, started_at, finished_at, error";

fn time(value: Option<String>) -> Option<Timestamp> {
    value.and_then(|v| DateTime::parse_from_rfc3339(&v).ok()).map(|t| t.to_utc())
}

fn from_row(row: &Row) -> rusqlite::Result<Operation> {
    let action: String = row.get(3)?;
    let status: String = row.get(4)?;
    let error: Option<String> = row.get(8)?;
    Ok(Operation {
        operation_id: row.get(0)?,
        deployment_id: row.get(1)?,
        instance_id: row.get(2)?,
        action: Action::parse(&action).unwrap_or(Action::Restart),
        status: OperationStatus::parse(&status).unwrap_or(OperationStatus::Failed),
        requested_at: time(row.get(5)?).unwrap_or_else(now),
        started_at: time(row.get(6)?),
        finished_at: time(row.get(7)?),
        error: error.and_then(|e| serde_json::from_str(&e).ok()),
    })
}

fn text(value: Option<Timestamp>) -> Option<String> {
    value.map(|t| t.to_rfc3339_opts(chrono::SecondsFormat::Millis, true))
}

pub fn save(conn: &Connection, op: &Operation) -> rusqlite::Result<()> {
    conn.execute(
        &format!("INSERT INTO operations ({COLUMNS}) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)
                  ON CONFLICT(id) DO UPDATE SET status = excluded.status, started_at = excluded.started_at,
                  finished_at = excluded.finished_at, error = excluded.error"),
        params![
            op.operation_id,
            op.deployment_id,
            op.instance_id,
            op.action.as_str(),
            op.status.as_str(),
            text(Some(op.requested_at)),
            text(op.started_at),
            text(op.finished_at),
            op.error.as_ref().and_then(|e| serde_json::to_string(e).ok()),
        ],
    )?;
    Ok(())
}

pub fn get(conn: &Connection, id: &str) -> rusqlite::Result<Option<Operation>> {
    conn.query_row(&format!("SELECT {COLUMNS} FROM operations WHERE id = ?1"), [id], from_row)
        .optional()
}

pub fn list(conn: &Connection, deployment_id: Option<&str>, limit: usize) -> rusqlite::Result<Vec<Operation>> {
    let mut statement = conn.prepare(&format!(
        "SELECT {COLUMNS} FROM operations WHERE ?1 IS NULL OR deployment_id = ?1
         ORDER BY requested_at DESC, id LIMIT ?2"
    ))?;
    let rows = statement.query_map(params![deployment_id, limit as i64], from_row)?;
    rows.collect()
}

/// Operación pendiente o en curso sobre la instancia, si la hay.
pub fn active(conn: &Connection, instance_id: &str) -> rusqlite::Result<Option<Operation>> {
    conn.query_row(
        &format!("SELECT {COLUMNS} FROM operations
                  WHERE instance_id = ?1 AND status IN ('pending', 'running') LIMIT 1"),
        [instance_id],
        from_row,
    )
    .optional()
}

/// Al arrancar, las operaciones sin terminar se marcan como fallidas: su resultado se perdió.
pub fn fail_interrupted(conn: &Connection) -> rusqlite::Result<usize> {
    let error = ApiError::new("interrupted", "El backend se reinició antes de terminar la operación", true);
    conn.execute(
        "UPDATE operations SET status = 'failed', finished_at = ?1, error = ?2
         WHERE status IN ('pending', 'running')",
        params![text(Some(now())), serde_json::to_string(&error).unwrap_or_default()],
    )
}
