// Construye las respuestas del panel a partir del inventario y las observaciones.
use std::{collections::HashMap, time::Duration};

use chrono::TimeDelta;

use crate::{
    inventory::Inventory,
    model::{
        ConnectionState, ConnectionView, InstanceDetail, NodeView, Observation, ServiceStatus,
        Timestamp, Topology, Transport,
    },
};

pub type Observations = HashMap<String, Observation>;

pub fn is_stale(obs: &Observation, now: Timestamp, stale_after: Duration) -> bool {
    let limit = TimeDelta::from_std(stale_after).unwrap_or(TimeDelta::MAX);
    obs.observed_at.is_some_and(|at| now - at > limit)
}

fn node(inventory: &Inventory, observations: &Observations, id: &str, now: Timestamp, stale_after: Duration) -> Option<NodeView> {
    let instance = inventory.instance(id)?;
    let obs = observations.get(id).cloned().unwrap_or_default();
    Some(NodeView {
        instance_id: instance.instance_id.clone(),
        kind: instance.kind.clone(),
        name: instance.name.clone(),
        reader_id: instance.reader_id.clone(),
        status: obs.status,
        stale: is_stale(&obs, now, stale_after),
        observed_at: obs.observed_at,
        last_success_at: obs.last_success_at,
        last_error: obs.last_error.clone(),
        container_state: obs.docker.as_ref().and_then(|d| d.state.clone()),
    })
}

/// Cruza las conexiones deseadas con lo que cada servicio declara en `/info`.
/// HTTP no mantiene conexión: si el destino figura se informa `configured`.
pub fn connections(inventory: &Inventory, observations: &Observations, deployment_id: &str) -> Vec<ConnectionView> {
    let empty = Observation::default();
    let mut views = Vec::new();
    for desired in inventory.connections_of(deployment_id) {
        let reporter = observations.get(&desired.reported_by).unwrap_or(&empty);
        let other_id = if desired.reported_by == desired.source_id { &desired.target_id } else { &desired.source_id };
        let other = observations.get(other_id).unwrap_or(&empty);
        let other_instance = inventory.instance(other_id);
        let seen = reporter.peers.iter().any(|p| {
            p.transport == desired.transport && other_instance.is_some_and(|i| i.matches(&p.peer))
        });
        let (state, last_error) = match reporter.status {
            ServiceStatus::Unknown => (ConnectionState::Configured, None),
            ServiceStatus::Offline => (ConnectionState::Disconnected, reporter.last_error.clone()),
            _ if other.status == ServiceStatus::Offline => (ConnectionState::Disconnected, other.last_error.clone()),
            _ if !seen => (ConnectionState::Disconnected, None),
            _ if desired.transport == Transport::Sse => (ConnectionState::Connected, None),
            _ => (ConnectionState::Configured, None),
        };
        views.push(ConnectionView {
            source_id: desired.source_id.clone(),
            target_id: desired.target_id.clone(),
            reported_by: desired.reported_by.clone(),
            transport: desired.transport,
            state,
            desired: true,
            observed_at: reporter.observed_at,
            last_success_at: if seen { reporter.last_success_at } else { None },
            events_received: None,
            last_error,
        });
    }
    // Conexiones que declara un servicio pero no están en el inventario.
    for instance in inventory.instances_of(deployment_id) {
        let Some(obs) = observations.get(&instance.instance_id) else { continue };
        if !matches!(obs.status, ServiceStatus::Healthy | ServiceStatus::Degraded) {
            continue;
        }
        for peer in &obs.peers {
            let Some(other) = inventory.instances_of(deployment_id).find(|o| o.matches(&peer.peer)) else { continue };
            let known = views.iter().any(|v| {
                v.transport == peer.transport
                    && ((v.source_id == instance.instance_id && v.target_id == other.instance_id)
                        || (v.target_id == instance.instance_id && v.source_id == other.instance_id))
            });
            if known {
                continue;
            }
            views.push(ConnectionView {
                source_id: instance.instance_id.clone(),
                target_id: other.instance_id.clone(),
                reported_by: instance.instance_id.clone(),
                transport: peer.transport,
                state: if peer.transport == Transport::Sse { ConnectionState::Connected } else { ConnectionState::Configured },
                desired: false,
                observed_at: obs.observed_at,
                last_success_at: obs.last_success_at,
                events_received: None,
                last_error: None,
            });
        }
    }
    views
}

pub fn topology(
    inventory: &Inventory,
    observations: &Observations,
    deployment_id: &str,
    now: Timestamp,
    stale_after: Duration,
    simulated: bool,
) -> Topology {
    Topology {
        deployment_id: deployment_id.to_string(),
        simulated,
        generated_at: now,
        nodes: inventory
            .instances_of(deployment_id)
            .filter_map(|i| node(inventory, observations, &i.instance_id, now, stale_after))
            .collect(),
        connections: connections(inventory, observations, deployment_id),
    }
}

pub fn instance_detail(
    inventory: &Inventory,
    observations: &Observations,
    instance_id: &str,
    now: Timestamp,
    stale_after: Duration,
    simulated: bool,
) -> Option<InstanceDetail> {
    let instance = inventory.instance(instance_id)?.clone();
    let obs = observations.get(instance_id).cloned().unwrap_or_default();
    let connections = connections(inventory, observations, &instance.deployment_id)
        .into_iter()
        .filter(|c| c.source_id == instance_id || c.target_id == instance_id)
        .collect();
    Some(InstanceDetail {
        instance,
        simulated,
        status: obs.status,
        stale: is_stale(&obs, now, stale_after),
        observed_at: obs.observed_at,
        last_success_at: obs.last_success_at,
        last_error: obs.last_error,
        peers: obs.peers,
        devices: obs.devices,
        docker: obs.docker,
        docker_error: obs.docker_error,
        connections,
    })
}
