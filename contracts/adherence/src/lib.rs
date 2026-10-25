#![no_std]

//! Paga en USDC una sesión cuando llega una prueba Groth16 válida de que las
//! lecturas firmadas por el Verifier de Phonendo cumplen la política.

use soroban_sdk::{
    address_payload::AddressPayload,
    contract, contracterror, contractevent, contractimpl, contracttype,
    crypto::bls12_381::{Bls12381Fr, Bls12381G1Affine, Bls12381G2Affine},
    token, Address, Bytes, BytesN, Env, Vec, U256,
};

const DAY_IN_LEDGERS: u32 = 17_280;
const CLAIM_TTL: u32 = 365 * DAY_IN_LEDGERS;

#[contracterror]
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Ord)]
#[repr(u32)]
pub enum Error {
    AlreadyClaimed = 1,
    InvalidProof = 2,
    InvalidPatient = 3,
    MalformedVerificationKey = 4,
}

#[derive(Clone)]
#[contracttype]
pub struct VerificationKey {
    pub alpha: Bls12381G1Affine,
    pub beta: Bls12381G2Affine,
    pub gamma: Bls12381G2Affine,
    pub delta: Bls12381G2Affine,
    pub ic: Vec<Bls12381G1Affine>,
}

#[derive(Clone)]
#[contracttype]
pub struct Proof {
    pub a: Bls12381G1Affine,
    pub b: Bls12381G2Affine,
    pub c: Bls12381G1Affine,
}

/// Condición que acuerda la aseguradora y cantidad pagada por sesión.
#[derive(Clone, Debug, Eq, PartialEq)]
#[contracttype]
pub struct Policy {
    pub min_value: u32,
    pub max_value: u32,
    pub min_count: u32,
    pub payout: i128,
}

#[derive(Clone)]
#[contracttype]
pub struct Config {
    pub admin: Address,
    pub verifier_key: BytesN<32>,
    pub token: Address,
    pub policy: Policy,
}

#[contracttype]
enum DataKey {
    Config,
    VerificationKey,
    Claimed(u64),
}

#[contractevent]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SessionPaid {
    #[topic]
    pub session_id: u64,
    pub patient: Address,
    pub amount: i128,
}

#[contract]
pub struct Adherence;

#[contractimpl]
impl Adherence {
    pub fn __constructor(
        env: Env,
        admin: Address,
        verifier_key: BytesN<32>,
        token: Address,
        policy: Policy,
        verification_key: VerificationKey,
    ) -> Result<(), Error> {
        // 5 entradas públicas: commitment, minValue, maxValue, minCount, sessionId.
        if verification_key.ic.len() != 6 {
            return Err(Error::MalformedVerificationKey);
        }
        let storage = env.storage().instance();
        storage.set(&DataKey::Config, &Config { admin, verifier_key, token, policy });
        storage.set(&DataKey::VerificationKey, &verification_key);
        Ok(())
    }

    /// Cobra una sesión. Cualquiera puede enviarla (por ejemplo el Publisher);
    /// el pago va siempre a `patient`, que está dentro del mensaje firmado.
    pub fn claim(
        env: Env,
        patient: Address,
        session_id: u64,
        commitment: BytesN<32>,
        signature: BytesN<64>,
        proof: Proof,
    ) -> Result<(), Error> {
        let claimed = DataKey::Claimed(session_id);
        if env.storage().persistent().has(&claimed) {
            return Err(Error::AlreadyClaimed);
        }

        let config = Self::config(&env);
        let mut message = signed_message(&env, &commitment, session_id, &patient)?;
        message.append(&Bytes::from_array(&env, &config.verifier_key.to_array()));
        env.crypto()
            .ed25519_verify(&config.verifier_key, &message, &signature);

        let policy = &config.policy;
        let mut inputs = Vec::new(&env);
        inputs.push_back(Bls12381Fr::from_bytes(commitment));
        inputs.push_back(fr(&env, policy.min_value as u128));
        inputs.push_back(fr(&env, policy.max_value as u128));
        inputs.push_back(fr(&env, policy.min_count as u128));
        inputs.push_back(fr(&env, session_id as u128));
        let verification_key = env
            .storage()
            .instance()
            .get(&DataKey::VerificationKey)
            .unwrap();
        if !verify_groth16(&env, &verification_key, &proof, &inputs) {
            return Err(Error::InvalidProof);
        }

        env.storage().persistent().set(&claimed, &true);
        env.storage()
            .persistent()
            .extend_ttl(&claimed, CLAIM_TTL, CLAIM_TTL);
        token::Client::new(&env, &config.token).transfer(
            &env.current_contract_address(),
            &patient,
            &policy.payout,
        );
        SessionPaid { session_id, patient, amount: policy.payout }.publish(&env);
        Ok(())
    }

    pub fn is_claimed(env: Env, session_id: u64) -> bool {
        env.storage().persistent().has(&DataKey::Claimed(session_id))
    }

    pub fn policy(env: Env) -> Policy {
        Self::config(&env).policy
    }

    pub fn set_policy(env: Env, policy: Policy) {
        let mut config = Self::config(&env);
        config.admin.require_auth();
        config.policy = policy;
        env.storage().instance().set(&DataKey::Config, &config);
    }
}

impl Adherence {
    fn config(env: &Env) -> Config {
        env.storage().instance().get(&DataKey::Config).unwrap()
    }
}

/// Mensaje que firma el Verifier: commitment || sessionId (32 bytes BE) ||
/// clave pública ed25519 de la cuenta G de la paciente.
fn signed_message(
    env: &Env,
    commitment: &BytesN<32>,
    session_id: u64,
    patient: &Address,
) -> Result<Bytes, Error> {
    let patient_key = match patient.to_payload() {
        Some(AddressPayload::AccountIdPublicKeyEd25519(key)) => key,
        _ => return Err(Error::InvalidPatient),
    };
    let mut message = Bytes::from_array(env, &commitment.to_array());
    message.append(&U256::from_u128(env, session_id as u128).to_be_bytes());
    message.append(&Bytes::from_array(env, &patient_key.to_array()));
    Ok(message)
}

fn fr(env: &Env, value: u128) -> Bls12381Fr {
    Bls12381Fr::from_u256(U256::from_u128(env, value))
}

fn verify_groth16(
    env: &Env,
    verification_key: &VerificationKey,
    proof: &Proof,
    inputs: &Vec<Bls12381Fr>,
) -> bool {
    let bls = env.crypto().bls12_381();
    let mut vk_x = verification_key.ic.get(0).unwrap();
    for (signal, point) in inputs.iter().zip(verification_key.ic.iter().skip(1)) {
        vk_x = bls.g1_add(&vk_x, &bls.g1_mul(&point, &signal));
    }

    let lhs = soroban_sdk::vec![
        env,
        -proof.a.clone(),
        verification_key.alpha.clone(),
        vk_x,
        proof.c.clone()
    ];
    let rhs = soroban_sdk::vec![
        env,
        proof.b.clone(),
        verification_key.beta.clone(),
        verification_key.gamma.clone(),
        verification_key.delta.clone()
    ];
    bls.pairing_check(lhs, rhs)
}
