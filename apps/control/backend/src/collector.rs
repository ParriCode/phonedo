// Recogida periódica: una sola por despliegue, compartida por todas las pestañas.
use futures::future::join_all;
use regex::Regex;
use std::sync::OnceLock;
use tokio::time::{interval, MissedTickBehavior};

use crate::{
    model::{now, ApiError, Instance, Observation, ServiceStatus},
    AppState, Update,
};

pub async fn run(state: AppState, deployment_id: String) {
    let mut ticker = interval(state.config.poll);
    ticker.set_missed_tick_behavior(MissedTickBehavior::Delay);
    loop {
        ticker.tick().await;
        collect_once(&state, &deployment_id).await;
    }
}

/// Consulta todas las instancias del despliegue en paralelo y avisa por SSE.
pub async fn collect_once(state: &AppState, deployment_id: &str) {
    let instances: Vec<Instance> = state.inventory.instances_of(deployment_id).cloned().collect();
    let previous = state.observations.read().await.clone();
    let results = join_all(instances.iter().map(|instance| {
        let prev = previous.get(&instance.instance_id).cloned();
        async move { (instance.instance_id.clone(), observe(state, instance, prev).await) }
    }))
    .await;
    state.observations.write().await.extend(results);
    let _ = state.updates.send(Update::Topology(deployment_id.to_string()));
}

pub async fn observe(state: &AppState, instance: &Instance, previous: Option<Observation>) -> Observation {
    let mut obs = previous.unwrap_or_default();
    let observed = now();
    obs.observed_at = Some(observed);
    if let Some(container) = &instance.container {
        match state.docker.observe(container).await {
            Ok(info) => {
                obs.docker = Some(info);
                obs.docker_error = None;
            }
            Err(e) => {
                obs.docker = None;
                obs.docker_error = Some(e);
            }
        }
    }
    let container_state = obs.docker.as_ref().and_then(|d| d.state.as_deref());
    // En modo simulado el servicio solo responde si su contenedor está en marcha.
    if state.probe.is_mock() && container_state.is_some_and(|s| s != "running") {
        obs.status = ServiceStatus::Offline;
        obs.last_error = Some(ApiError::new("container_not_running", "El contenedor está parado", true));
        return obs;
    }
    match state.probe.info(instance).await {
        Ok(peers) => {
            obs.status = ServiceStatus::Healthy;
            obs.last_success_at = Some(observed);
            obs.last_error = None;
            obs.peers = peers;
            match state.probe.logs(instance).await {
                Ok(lines) => obs.logs = sanitize(lines),
                Err(e) => {
                    obs.status = ServiceStatus::Degraded;
                    obs.last_error = Some(e.to_api());
                }
            }
            if instance.kind == "reader" {
                match state.probe.devices(instance).await {
                    Ok(devices) => obs.devices = Some(devices),
                    Err(e) => {
                        obs.status = ServiceStatus::Degraded;
                        obs.last_error = Some(e.to_api());
                    }
                }
            }
        }
        Err(e) => {
            obs.status = e.status();
            obs.last_error = Some(e.to_api());
        }
    }
    let unhealthy = obs.docker.as_ref().is_some_and(|d| d.health.as_deref() == Some("unhealthy"));
    if unhealthy && obs.status == ServiceStatus::Healthy {
        obs.status = ServiceStatus::Degraded;
    }
    obs
}

/// Oculta tokens, contraseñas y cabeceras Authorization en los logs.
pub fn sanitize(lines: Vec<String>) -> Vec<String> {
    static PATTERNS: OnceLock<(Regex, Regex)> = OnceLock::new();
    let (keys, bearer) = PATTERNS.get_or_init(|| {
        (
            Regex::new(r#"(?i)\b(token|password|secret|authorization|api[_-]?key)("?\s*[=:]\s*)("[^"]*"|[^\s,}]+)"#).unwrap(),
            Regex::new(r"(?i)\bbearer\s+[^\s,}]+").unwrap(),
        )
    });
    lines
        .into_iter()
        .map(|line| {
            let line = bearer.replace_all(&line, "Bearer [oculto]");
            keys.replace_all(&line, "${1}${2}[oculto]").into_owned()
        })
        .collect()
}
