// Estado, puertos, recursos y acciones de los contenedores. El navegador nunca accede a Docker.
use std::{
    collections::{HashMap, HashSet},
    sync::{Arc, Mutex},
    time::Duration,
};

use bollard::{
    container::{InspectContainerOptions, RestartContainerOptions, StartContainerOptions, StatsOptions, StopContainerOptions},
    errors::Error as DockerError,
    Docker,
};
use futures::StreamExt;
use tokio::time::timeout;

use crate::model::{Action, ApiError, DockerInfo, PortInfo};

const DOCKER_TIMEOUT: Duration = Duration::from_secs(4);
/// Segundos que Docker espera a que el servicio pare antes de matarlo.
const STOP_GRACE_SECONDS: i64 = 10;
const ACTION_TIMEOUT: Duration = Duration::from_secs(40);

/// Solo se actúa sobre contenedores con estas etiquetas.
pub const LABEL_MANAGED: &str = "phonendo.control.managed";
pub const LABEL_DEPLOYMENT: &str = "phonendo.control.deployment";

#[derive(Clone)]
pub enum DockerAdapter {
    Off,
    Unavailable(String),
    Engine(Docker),
    /// Contenedores simulados; guarda cuáles están parados.
    Mock(Arc<Mutex<HashSet<String>>>),
}

/// Comprueba que el contenedor lo gestiona el panel y pertenece al despliegue.
pub fn check_labels(labels: Option<&HashMap<String, String>>, container: &str, deployment_id: &str) -> Result<(), ApiError> {
    let label = |key: &str| labels.and_then(|l| l.get(key)).map(String::as_str);
    if label(LABEL_MANAGED) != Some("true") {
        return Err(ApiError::new(
            "container_not_managed",
            format!("{container} no tiene la etiqueta {LABEL_MANAGED}=true"),
            false,
        ));
    }
    if label(LABEL_DEPLOYMENT) != Some(deployment_id) {
        return Err(ApiError::new(
            "container_not_managed",
            format!("{container} no pertenece al despliegue {deployment_id}"),
            false,
        ));
    }
    Ok(())
}

impl DockerAdapter {
    pub fn mock() -> Self {
        DockerAdapter::Mock(Arc::new(Mutex::new(HashSet::new())))
    }

    pub fn connect(enabled: bool, mock: bool) -> Self {
        if mock {
            return Self::mock();
        }
        if !enabled {
            return DockerAdapter::Off;
        }
        match Docker::connect_with_local_defaults() {
            Ok(docker) => DockerAdapter::Engine(docker),
            Err(e) => DockerAdapter::Unavailable(e.to_string()),
        }
    }

    pub async fn observe(&self, container: &str) -> Result<DockerInfo, ApiError> {
        match self {
            DockerAdapter::Off => Err(ApiError::new("docker_disabled", "Consulta a Docker desactivada", false)),
            DockerAdapter::Unavailable(e) => Err(unavailable(e)),
            DockerAdapter::Mock(stopped) => {
                let running = !stopped.lock().unwrap().contains(container);
                Ok(mock_info(container, running))
            }
            DockerAdapter::Engine(docker) => match timeout(DOCKER_TIMEOUT, inspect(docker, container)).await {
                Ok(result) => result,
                Err(_) => Err(docker_timeout()),
            },
        }
    }

    /// Valida antes de aceptar la acción, para responder el error al momento.
    pub async fn check_managed(&self, container: &str, deployment_id: &str) -> Result<(), ApiError> {
        match self {
            DockerAdapter::Off => Err(ApiError::new("docker_disabled", "Consulta a Docker desactivada", false)),
            DockerAdapter::Unavailable(e) => Err(unavailable(e)),
            DockerAdapter::Mock(_) => Ok(()),
            DockerAdapter::Engine(docker) => {
                let inspect = docker.inspect_container(container, None::<InspectContainerOptions>);
                let data = timeout(DOCKER_TIMEOUT, inspect)
                    .await
                    .map_err(|_| docker_timeout())?
                    .map_err(|e| map_error(container, e))?;
                check_labels(data.config.as_ref().and_then(|c| c.labels.as_ref()), container, deployment_id)
            }
        }
    }

    pub async fn act(&self, container: &str, action: Action) -> Result<(), ApiError> {
        match self {
            DockerAdapter::Off => Err(ApiError::new("docker_disabled", "Consulta a Docker desactivada", false)),
            DockerAdapter::Unavailable(e) => Err(unavailable(e)),
            DockerAdapter::Mock(stopped) => {
                let mut stopped = stopped.lock().unwrap();
                match action {
                    Action::Stop => stopped.insert(container.to_string()),
                    Action::Start | Action::Restart => stopped.remove(container),
                };
                Ok(())
            }
            DockerAdapter::Engine(docker) => {
                let result = match action {
                    Action::Start => timeout(ACTION_TIMEOUT, docker.start_container(container, None::<StartContainerOptions<String>>)).await,
                    Action::Stop => timeout(ACTION_TIMEOUT, docker.stop_container(container, Some(StopContainerOptions { t: STOP_GRACE_SECONDS }))).await,
                    Action::Restart => timeout(ACTION_TIMEOUT, docker.restart_container(container, Some(RestartContainerOptions { t: STOP_GRACE_SECONDS as isize }))).await,
                };
                match result {
                    Err(_) => Err(docker_timeout()),
                    Ok(Ok(())) => Ok(()),
                    // 304: ya estaba en el estado pedido.
                    Ok(Err(DockerError::DockerResponseServerError { status_code: 304, .. })) => Ok(()),
                    Ok(Err(e)) => Err(map_error(container, e)),
                }
            }
        }
    }
}

fn docker_timeout() -> ApiError {
    ApiError::new("docker_timeout", "Docker no respondió a tiempo", true)
}

fn unavailable(message: &str) -> ApiError {
    ApiError::new("docker_unavailable", format!("Docker no disponible: {message}"), true)
}

fn map_error(container: &str, error: DockerError) -> ApiError {
    match error {
        DockerError::DockerResponseServerError { status_code: 404, .. } => ApiError::new(
            "container_not_found",
            format!("No existe el contenedor {container}"),
            true,
        ),
        other => unavailable(&other.to_string()),
    }
}

async fn inspect(docker: &Docker, container: &str) -> Result<DockerInfo, ApiError> {
    let data = docker
        .inspect_container(container, None::<InspectContainerOptions>)
        .await
        .map_err(|e| map_error(container, e))?;
    let state = data.state.as_ref();
    let mut info = DockerInfo {
        container_id: data.id.clone().unwrap_or_default().chars().take(12).collect(),
        name: data.name.clone().unwrap_or_default().trim_start_matches('/').to_string(),
        image: data.config.as_ref().and_then(|c| c.image.clone()),
        state: state.and_then(|s| s.status).map(|s| s.to_string()),
        health: state.and_then(|s| s.health.as_ref()).and_then(|h| h.status).map(|s| s.to_string()),
        ports: Vec::new(),
        cpu_percent: None,
        memory_bytes: None,
        memory_limit_bytes: None,
    };
    if let Some(ports) = data.network_settings.as_ref().and_then(|n| n.ports.as_ref()) {
        for (key, bindings) in ports {
            let (port, protocol) = key.split_once('/').unwrap_or((key.as_str(), "tcp"));
            let Ok(private_port) = port.parse() else { continue };
            let bindings = bindings.clone().unwrap_or_default();
            if bindings.is_empty() {
                info.ports.push(PortInfo { private_port, public_port: None, host_ip: None, protocol: protocol.into() });
            }
            for binding in bindings {
                info.ports.push(PortInfo {
                    private_port,
                    public_port: binding.host_port.and_then(|p| p.parse().ok()),
                    host_ip: binding.host_ip,
                    protocol: protocol.into(),
                });
            }
        }
        info.ports.sort_by_key(|p| (p.private_port, p.public_port));
    }
    if info.state.as_deref() == Some("running") {
        let options = StatsOptions { stream: false, one_shot: false };
        if let Some(Ok(stats)) = docker.stats(container, Some(options)).next().await {
            let cpu = stats.cpu_stats.cpu_usage.total_usage as f64
                - stats.precpu_stats.cpu_usage.total_usage as f64;
            let system = stats.cpu_stats.system_cpu_usage.unwrap_or(0) as f64
                - stats.precpu_stats.system_cpu_usage.unwrap_or(0) as f64;
            let cpus = stats.cpu_stats.online_cpus.unwrap_or(1) as f64;
            if cpu >= 0.0 && system > 0.0 {
                info.cpu_percent = Some((cpu / system * cpus * 100.0 * 100.0).round() / 100.0);
            }
            info.memory_bytes = stats.memory_stats.usage;
            info.memory_limit_bytes = stats.memory_stats.limit;
        }
    }
    Ok(info)
}

fn mock_info(container: &str, running: bool) -> DockerInfo {
    DockerInfo {
        container_id: "000000000000".into(),
        name: container.into(),
        image: Some(format!("{container}:simulado")),
        state: Some(if running { "running" } else { "exited" }.into()),
        health: running.then(|| "healthy".into()),
        ports: Vec::new(),
        cpu_percent: running.then_some(1.5),
        memory_bytes: running.then_some(48 * 1024 * 1024),
        memory_limit_bytes: Some(512 * 1024 * 1024),
    }
}
