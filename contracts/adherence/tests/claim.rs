use adherence::{Adherence, AdherenceClient, Error, Policy, Proof, VerificationKey};
use ed25519_dalek::{Signer, SigningKey};
use serde_json::Value;
use soroban_sdk::{
    address_payload::AddressPayload,
    contract, contractimpl,
    crypto::bls12_381::{Bls12381G1Affine, Bls12381G2Affine},
    testutils::Address as _,
    Address, BytesN, Env, Vec,
};

const PAYOUT: i128 = 50_0000000;

/// Token mínimo para los tests: en el entorno de pruebas las cuentas G no
/// tienen trustline de USDC, así que no se puede usar el contrato del activo.
#[contract]
pub struct MockToken;

#[contractimpl]
impl MockToken {
    pub fn mint(env: Env, to: Address, amount: i128) {
        let balance = Self::balance(env.clone(), to.clone());
        env.storage().persistent().set(&to, &(balance + amount));
    }

    pub fn balance(env: Env, id: Address) -> i128 {
        env.storage().persistent().get(&id).unwrap_or(0)
    }

    pub fn transfer(env: Env, from: Address, to: Address, amount: i128) {
        from.require_auth();
        Self::mint(env.clone(), from, -amount);
        Self::mint(env, to, amount);
    }
}

struct Setup<'a> {
    env: Env,
    client: AdherenceClient<'a>,
    token: MockTokenClient<'a>,
    verifier: SigningKey,
    patient_key: [u8; 32],
    patient: Address,
    args: Value,
}

fn hex_array<const N: usize>(value: &Value) -> [u8; N] {
    hex::decode(value.as_str().unwrap()).unwrap().try_into().unwrap()
}

fn g1(env: &Env, value: &Value) -> Bls12381G1Affine {
    Bls12381G1Affine::from_array(env, &hex_array::<96>(value))
}

fn g2(env: &Env, value: &Value) -> Bls12381G2Affine {
    Bls12381G2Affine::from_array(env, &hex_array::<192>(value))
}

fn session_id(args: &Value) -> u64 {
    args["session_id"].as_str().unwrap().parse().unwrap()
}

fn proof(env: &Env, args: &Value) -> Proof {
    let proof = &args["proof"];
    Proof { a: g1(env, &proof["a"]), b: g2(env, &proof["b"]), c: g1(env, &proof["c"]) }
}

fn setup<'a>(policy: Policy) -> Setup<'a> {
    let env = Env::default();
    env.mock_all_auths();
    let args: Value = serde_json::from_str(include_str!("data/soroban_args.json")).unwrap();

    let vk = &args["verification_key"];
    let mut ic = Vec::new(&env);
    for point in vk["ic"].as_array().unwrap() {
        ic.push_back(g1(&env, point));
    }
    let verification_key = VerificationKey {
        alpha: g1(&env, &vk["alpha"]),
        beta: g2(&env, &vk["beta"]),
        gamma: g2(&env, &vk["gamma"]),
        delta: g2(&env, &vk["delta"]),
        ic,
    };

    let admin = Address::generate(&env);
    let usdc = env.register(MockToken, ());
    let verifier = SigningKey::from_bytes(&[7; 32]);
    let contract_id = env.register(
        Adherence,
        (
            admin,
            BytesN::from_array(&env, &verifier.verifying_key().to_bytes()),
            usdc.clone(),
            policy,
            verification_key,
        ),
    );
    let token = MockTokenClient::new(&env, &usdc);
    token.mint(&contract_id, &(10 * PAYOUT));

    let patient_key = [9; 32];
    let patient = AddressPayload::AccountIdPublicKeyEd25519(BytesN::from_array(&env, &patient_key))
        .to_address(&env);

    Setup {
        client: AdherenceClient::new(&env, &contract_id),
        token,
        env,
        verifier,
        patient_key,
        patient,
        args,
    }
}

fn default_policy() -> Policy {
    Policy { min_value: 90, max_value: 130, min_count: 28, payout: PAYOUT }
}

fn sign(s: &Setup, commitment: &[u8; 32], session_id: u64, patient_key: &[u8; 32]) -> BytesN<64> {
    let mut message = commitment.to_vec();
    message.extend_from_slice(&[0; 24]);
    message.extend_from_slice(&session_id.to_be_bytes());
    message.extend_from_slice(patient_key);
    BytesN::from_array(&s.env, &s.verifier.sign(&message).to_bytes())
}

fn claim(s: &Setup, session_id: u64, signature: &BytesN<64>) -> Result<(), Error> {
    let commitment = BytesN::from_array(&s.env, &hex_array::<32>(&s.args["commitment"]));
    s.client
        .try_claim(&s.patient, &session_id, &commitment, signature, &proof(&s.env, &s.args))
        .map(|_| ())
        .map_err(|err| err.unwrap())
}

#[test]
fn pays_valid_session_once() {
    let s = setup(default_policy());
    let session = session_id(&s.args);
    let signature = sign(&s, &hex_array(&s.args["commitment"]), session, &s.patient_key);

    assert_eq!(claim(&s, session, &signature), Ok(()));
    assert_eq!(s.token.balance(&s.patient), PAYOUT);
    assert!(s.client.is_claimed(&session));

    assert_eq!(claim(&s, session, &signature), Err(Error::AlreadyClaimed));
    assert_eq!(s.token.balance(&s.patient), PAYOUT);
}

#[test]
fn rejects_proof_for_other_policy() {
    let s = setup(Policy { min_count: 30, ..default_policy() });
    let session = session_id(&s.args);
    let signature = sign(&s, &hex_array(&s.args["commitment"]), session, &s.patient_key);

    assert_eq!(claim(&s, session, &signature), Err(Error::InvalidProof));
    assert_eq!(s.token.balance(&s.patient), 0);
}

#[test]
fn rejects_proof_for_other_session() {
    let s = setup(default_policy());
    let other = session_id(&s.args) + 1;
    let signature = sign(&s, &hex_array(&s.args["commitment"]), other, &s.patient_key);

    assert_eq!(claim(&s, other, &signature), Err(Error::InvalidProof));
}

#[test]
#[should_panic]
fn rejects_signature_for_other_patient() {
    let s = setup(default_policy());
    let session = session_id(&s.args);
    let signature = sign(&s, &hex_array(&s.args["commitment"]), session, &[1; 32]);

    let _ = claim(&s, session, &signature);
}

#[test]
fn rejects_tampered_proof() {
    let s = setup(default_policy());
    let session = session_id(&s.args);
    let commitment = BytesN::from_array(&s.env, &hex_array::<32>(&s.args["commitment"]));
    let signature = sign(&s, &hex_array(&s.args["commitment"]), session, &s.patient_key);
    let mut tampered = proof(&s.env, &s.args);
    tampered.a = tampered.c.clone();

    let result = s.client.try_claim(&s.patient, &session, &commitment, &signature, &tampered);
    assert_eq!(result.map(|_| ()).map_err(|err| err.unwrap()), Err(Error::InvalidProof));
    assert!(!s.client.is_claimed(&session));
}
