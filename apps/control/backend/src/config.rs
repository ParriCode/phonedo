use std::{env, time::Duration};

// Sin `Debug`: contiene el token de administración.
#[derive(Clone)]
pub struct Config {
    pub addr: String,
    pub db_path: String,
    pub seed_path: String,
    /// Datos simulados en lugar de consultar servicios y Docker.
    pub mock: bool,
    pub poll: Duration,
    pub timeout: Duration,
    pub stale_after: Duration,
    pub docker: bool,
    /// Token para las acciones administrativas; sin él están desactivadas.
    pub admin_token: Option<String>,
    /// Tokens de rol. Si se define alguno, los datos privados exigen autenticación.
    pub patient_token: Option<String>,
    pub insurer_token: Option<String>,
    pub stellar_rpc: String,
    pub stellar_network: String,
    /// Contrato `adherence`; sin él no se consultan sesiones.
    pub contract_id: Option<String>,
    pub asset: String,
    pub stellar_poll: Duration,
    /// Ledgers hacia atrás en la primera lectura (~5 s por ledger).
    pub stellar_lookback: u32,
}

impl Config {
    pub fn auth_required(&self) -> bool {
        self.patient_token.is_some() || self.insurer_token.is_some()
    }
}

impl Default for Config {
    fn default() -> Self {
        Self {
            addr: "127.0.0.1:7200".into(),
            db_path: "control.db".into(),
            seed_path: "seed.json".into(),
            mock: false,
            poll: Duration::from_secs(3),
            timeout: Duration::from_millis(1500),
            stale_after: Duration::from_secs(9),
            docker: true,
            admin_token: None,
            patient_token: None,
            insurer_token: None,
            stellar_rpc: "https://soroban-testnet.stellar.org".into(),
            stellar_network: "testnet".into(),
            contract_id: None,
            asset: "XLM".into(),
            stellar_poll: Duration::from_secs(10),
            stellar_lookback: 120_000,
        }
    }
}

fn non_empty(name: &str) -> Option<String> {
    env::var(name).ok().filter(|t| !t.is_empty())
}

fn millis(name: &str, default: Duration, min: u64, max: u64) -> Result<Duration, String> {
    match env::var(name) {
        Err(_) => Ok(default),
        Ok(value) => {
            let ms: u64 = value.parse().map_err(|_| format!("{name} debe ser un número de ms"))?;
            if !(min..=max).contains(&ms) {
                return Err(format!("{name} debe estar entre {min} y {max} ms"));
            }
            Ok(Duration::from_millis(ms))
        }
    }
}

impl Config {
    pub fn from_env() -> Result<Self, String> {
        let default = Self::default();
        let mode = env::var("CONTROL_MODE").unwrap_or_else(|_| "live".into());
        let mock = match mode.as_str() {
            "live" => false,
            "mock" => true,
            other => return Err(format!("CONTROL_MODE desconocido: {other} (live|mock)")),
        };
        let poll = millis("CONTROL_POLL_MS", default.poll, 500, 60_000)?;
        let docker = match env::var("CONTROL_DOCKER").as_deref() {
            Err(_) | Ok("auto") => true,
            Ok("off") => false,
            Ok(other) => return Err(format!("CONTROL_DOCKER desconocido: {other} (auto|off)")),
        };
        Ok(Self {
            addr: env::var("CONTROL_ADDR").unwrap_or(default.addr),
            db_path: env::var("CONTROL_DB").unwrap_or(default.db_path),
            seed_path: env::var("CONTROL_SEED").unwrap_or(default.seed_path),
            mock,
            poll,
            timeout: millis("CONTROL_TIMEOUT_MS", default.timeout, 100, 30_000)?,
            stale_after: millis("CONTROL_STALE_MS", poll * 3, 1_000, 600_000)?,
            docker,
            admin_token: non_empty("CONTROL_ADMIN_TOKEN"),
            patient_token: non_empty("CONTROL_PATIENT_TOKEN"),
            insurer_token: non_empty("CONTROL_INSURER_TOKEN"),
            stellar_rpc: env::var("CONTROL_STELLAR_RPC").unwrap_or(default.stellar_rpc),
            stellar_network: env::var("CONTROL_STELLAR_NETWORK").unwrap_or(default.stellar_network),
            contract_id: non_empty("CONTROL_CONTRACT_ID"),
            asset: env::var("CONTROL_ASSET").unwrap_or(default.asset),
            stellar_poll: millis("CONTROL_STELLAR_POLL_MS", default.stellar_poll, 2_000, 600_000)?,
            stellar_lookback: match env::var("CONTROL_STELLAR_LOOKBACK") {
                Err(_) => default.stellar_lookback,
                Ok(v) => v.parse().map_err(|_| "CONTROL_STELLAR_LOOKBACK debe ser un número de ledgers".to_string())?,
            },
        })
    }
}
