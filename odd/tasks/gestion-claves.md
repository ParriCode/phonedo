# Gestión de claves para producción

Rama: `feature/gestion-claves` (desde `desarrollo`). Sin KMS: las claves viven en un archivo local y el panel las inyecta.

## Objetivo
Dejar las claves ordenadas y poder ir a producción sin secretos en git, sin claves temporales y sin que la clave privada pase por el navegador.

## Decisiones tomadas (usuario)
- **No se usa KMS ni Vault.** Almacén = archivo de claves en el equipo del operador.
- El panel web inyecta las claves en los servicios, por referencia (`id`), nunca mostrando la privada.
- Las claves de cartera se configuran desde la web al configurar el contrato / el paso hacia otros servicios.

## Hechos que condicionan el plan (path:línea)
- `deploy/env/dev.env` está versionado con tokens de prueba (`.gitignore:6` solo ignora `.env`); lo lee `tools/generate_configs.sh:5,63`.
- `apps/reader/examples/wearos/` tiene versionado `.android/debug.keystore(.lock)`, `secrets.properties`, `local.properties`, `.gradle/`, `.devenv/` y `app/.cxx/` (142 archivos de compilación). `secrets.properties` no tiene tokens reales (READER_TOKEN, MANAGER_URLS y MANAGER_TOKEN vacíos), aunque su cabecera dice «ignorado por git».
- El verifier, sin `signing_key.json`, genera una clave temporal y solo avisa (`apps/verifier/verifier.py:102-110`). Es lo que rompe al publisher.
- El contrato guarda **una sola** `verifier_key` fijada en el constructor y no tiene setter (`contracts/adherence/src/lib.rs:84-97`): rotar exige redesplegar.
- El despliegue del contrato es manual (`contracts/README.md:47-71`); firma la cuenta `--source`.
- `tools/web_docker.py:195-201` pasa secretos con `-e` (visibles en `docker inspect`); `:206-210` monta todo `~/.config/stellar` en el publisher; el verifier genera su clave dentro de `/data` (`:230-238`).
- La redacción de logs usa solo nombres de clave (`token|password|secret|seed`) y no cubre variables de entorno (`web_docker.py:17-22, 290-300`).
- El panel escucha en `127.0.0.1` pero no tiene autenticación, solo cabecera de origen (`web_runtime.py:190-197`).
- No hay CI ni pre-commit.

## Tres claves, tres funciones (no se mezclan)
| Rol | Lo usa | Se inyecta en un servicio |
|---|---|---|
| `verifier` (Ed25519) | verifier | sí, en el verifier |
| `publisher` (cuenta Stellar que paga) | publisher | sí, en el publisher |
| `deployer` (admin del contrato) | operador, al desplegar | **no, nunca** |

## Formato del almacén (propuesta)
`~/.phonendo/keys.json`, permisos 0600, fuera del repo. Una entrada por clave: `id`, `rol`, `red` (`testnet|mainnet`), `publica`, `privada`. El panel rechaza inyectar una clave de `testnet` en un servicio `mainnet`.

## Tareas
- [x] **T1 Higiene del repositorio** (commit `14b76c4`, ruta inline). `dev.env` → `dev.env.example` y generado con tokens aleatorios si falta; `secrets.properties` → `.example`; dejar de versionar keystore, `local.properties`, `.gradle/`, `.devenv/`, `app/.cxx/`; ampliar `.gitignore` (`*.keystore`, `*.jks`, `*.pem`, `*.key`, `signing_key*.json`, claves del almacén). Check: `git ls-files` sin secretos ni basura de build; `generate_configs.sh` sigue funcionando desde cero.
- [ ] **T2 Almacén de claves.** `tools/keys.py` (genera, lista, exporta públicas; Ed25519 para verifier y par Stellar para publisher y deployer) con tests. Check: tests del script; el archivo se crea con 0600; nunca imprime privadas.
- [ ] **T3 Verifier sin clave temporal en producción.** Con `PHONENDO_ENV=production` el verifier falla al arrancar si falta la clave; en desarrollo mantiene el aviso. Test RED/GREEN en `tests/app_tests/test_verifier_keys.py`.
- [ ] **T4 Inyección desde el panel.** El backend (`web_docker.py`, `web_runtime.py`) lee el almacén, monta la clave del verifier y la identidad del publisher como archivos de solo lectura, sin `-e`; deja de montar todo `~/.config/stellar`; endpoint que lista solo claves públicas; el selector del panel elige por `id`. Ampliar la redacción a variables de entorno y valores.
- [ ] **T5 Despliegue del contrato.** `tools/deploy_contract.sh` con la clave `deployer` y la pública del verifier del almacén; guarda el id del contrato. Decidir si se añade `set_verifier_key` (solo admin) al contrato para poder rotar sin redesplegar.
- [ ] **T6 Autenticación del panel.** Token local obligatorio para operaciones que muevan claves.
- [ ] **T7 Escáner de secretos.** `gitleaks` en pre-commit.

- [x] **T8 Demo preconfigurada (opción A).** Al clonar y hacer `docker compose up` el sistema cobra solo en testnet. Cuenta de demo `phonendo` (publisher, admin y fuente de despliegue) y clave de verifier de demo, ambas versionadas y marcadas «solo testnet». Requiere: instalar circom 2.2, regenerar `circuits/build` (zkey y claves, versionadas), desplegar contratos de rehabilitación y cadena de frío (pagan XLM nativo), fondearlos y poner sus ids en `deploy/docker/publisher.json`. Autorizado por el usuario: Friendbot, desplegar contratos, fondearlos con XLM, instalar circom. Check: `docker compose up` desde un clon limpio produce un `SessionPaid` en testnet.

- [ ] **T9 `./phonendo` + panel web como único modo (sustituye a Docker Compose).** Decisión del usuario: la web es el panel de configuración y ejecución de todos los contenedores; se elimina `deploy/docker/compose.yml` y el resto de caminos (lab, dev.sh, generate_configs, deploy/env). `./phonendo` prepara lo necesario, arranca el panel, crea al inicio contenedores de ejemplo (reader simulado, manager, verifier con la clave de demo, storage, publisher con la cuenta y los contratos de demo) y desde ahí los gestiona la web. T2–T7 quedan reevaluadas: solo se conserva lo que encaja (secretos como archivos de solo lectura, redacción ampliada en logs). No se reescribe el historial de git: se añaden commits.

## Pendiente de decidir
1. Archivo de claves en claro con 0600 o cifrado con `age` (añade una contraseña a gestionar).
2. Añadir `set_verifier_key` al contrato (T5) o aceptar redesplegar para rotar.
3. Dónde se despliega producción (VPS con Compose, Kubernetes u otro): afecta a cómo se entregan los archivos a los contenedores.
4. Los tokens que alguna vez estuvieron en git (`dev.env`, `compose.yml` con `demo-*`) son de prueba; rotarlos si se reutilizan fuera de desarrollo.

## Estrategia de entrega
`ask-on-risk`. T1 es la primera unidad de trabajo; cada tarea cierra con un commit convencional en esta rama. Push y PR los decide el usuario.

## Ruta por tarea
- Mapa de claves: explorador de solo lectura (más de 5 búsquedas encadenadas). T1: inline (ediciones mecánicas ya entendidas).

## Progreso
- Mirror Engram `odd/gestion-claves/tasks`: **pendiente** (herramientas de memoria no disponibles en esta sesión).
- T1 hecho: `bash -n` correcto; la generación de tokens aleatorios probada aparte (48 car., 0600, mismas variables). No se ejecutó `generate_configs.sh` entero para no tocar tus `config.env`. Tiene `signing_key.json` y `tools/web_docker.py` sin tocar todavía.
- T8 autorizado (testnet con la cuenta phonendo; el usuario aceptó publicar la clave de demo). Cuenta: `GBZCQXYS…EMGJ`.
- Siguiente paso: T8 (worker delegado), luego limpieza T3/T4 según el plan.

## Evidencia T8
- Commit `c8249e3` (demo versionada) y el commit de cierre de este documento. Ruta: trabajador delegado único.
- circom 2.2.3 instalado con cargo; `npm run setup` regeneró `circuits/build` (se versionan zkey, vkey, wasm y `soroban_vk.json`; no los `.ptau`, `.r1cs` ni pruebas). Verifier demo: `b61934e5…031e`.
- Contratos (testnet, token = SAC nativo `CDLZFC3S…CYSC`, 1000 XLM cada uno, pago 0,1 XLM): rehabilitación `CDUDM26CRM5OGGIQGZPBDUR4O27IK5HN3ZBAZXTR65JAWFDLM3CTPTTO`, cadena de frío `CCFO326BTSY5EAUPT5E74C44GVVQRX4HYB6TQQ7YSK647WDW2FM7DXH2`. Script: `deploy/demo/desplegar_demo.sh`.
- Clon limpio + `docker compose up --build -d --wait`: 2 `publisher_session_paid` (rehabilitación `15a1f74e…b44b`, cadena de frío `36538af3…8445`), ambas `tx_success` en testnet; Storage `/raw` con 128 registros; sin `verifier_key_missing`; `down -v` y puertos 7101-7105 libres.
- Nota: se instaló el target `wasm32v1-none` de rustup para compilar el contrato.
