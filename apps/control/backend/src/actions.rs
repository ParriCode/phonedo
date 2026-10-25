// Acciones sobre instancias: se validan al pedirlas y se ejecutan en segundo plano.
use crate::{
    collector,
    model::{now, Action, ApiError, Operation, OperationStatus},
    operations, AppState, Update,
};

fn storage_error(e: rusqlite::Error) -> ApiError {
    ApiError::new("storage_error", format!("Error del inventario: {e}"), true)
}

/// Registra la operación y la lanza. Devuelve la operación en estado `pending`.
pub async fn request(state: &AppState, instance_id: &str, action: Action) -> Result<Operation, ApiError> {
    let instance = state
        .inventory
        .instance(instance_id)
        .ok_or_else(|| ApiError::new("instance_not_found", format!("No existe la instancia {instance_id}"), false))?
        .clone();
    let container = instance
        .container
        .clone()
        .ok_or_else(|| ApiError::new("no_container", "La instancia no tiene contenedor asociado", false))?;
    state.docker.check_managed(&container, &instance.deployment_id).await?;

    let operation = Operation {
        operation_id: uuid::Uuid::new_v4().to_string(),
        deployment_id: instance.deployment_id.clone(),
        instance_id: instance.instance_id.clone(),
        action,
        status: OperationStatus::Pending,
        requested_at: now(),
        started_at: None,
        finished_at: None,
        error: None,
    };
    {
        // Comprobar y registrar con el mismo bloqueo evita dos acciones a la vez.
        let db = state.db.lock().unwrap();
        if let Some(active) = operations::active(&db, instance_id).map_err(storage_error)? {
            return Err(ApiError::new(
                "operation_in_progress",
                format!("La operación {} sigue en curso", active.operation_id),
                true,
            ));
        }
        operations::save(&db, &operation).map_err(storage_error)?;
    }
    publish(state, &operation);
    tokio::spawn(run(state.clone(), operation.clone(), container));
    Ok(operation)
}

async fn run(state: AppState, mut operation: Operation, container: String) {
    operation.status = OperationStatus::Running;
    operation.started_at = Some(now());
    record(&state, &operation);

    let result = state.docker.act(&container, operation.action).await;
    operation.finished_at = Some(now());
    match result {
        Ok(()) => operation.status = OperationStatus::Succeeded,
        Err(e) => {
            operation.status = OperationStatus::Failed;
            operation.error = Some(e);
        }
    }
    record(&state, &operation);
    // Recoger enseguida para que el panel muestre el efecto real.
    collector::collect_once(&state, &operation.deployment_id).await;
}

fn record(state: &AppState, operation: &Operation) {
    if let Err(e) = operations::save(&state.db.lock().unwrap(), operation) {
        tracing::error!("no se pudo guardar la operación {}: {e}", operation.operation_id);
    }
    publish(state, operation);
}

fn publish(state: &AppState, operation: &Operation) {
    let _ = state.updates.send(Update::Operation(operation.clone()));
}
