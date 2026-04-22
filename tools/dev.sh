#!/usr/bin/env bash
set -euo pipefail

ROJO="\033[0;31m"
VERDE="\033[0;32m"
AMARILLO="\033[0;33m"
AZUL="\033[0;34m"
CIAN="\033[0;36m"
NC="\033[0m"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

SERVICES=(storage verifier manager reader) # publisher aún no implementado

MODO_PYTHON=false
MODO_JAVASCRIPT=false

# Aquí guardamos los PIDs de los procesos lanzados en background
PIDS=()

print_info() {
    echo -e "${AZUL}[INFO]${NC} $1"
}

print_ok() {
    echo -e "${VERDE}[OK]${NC} $1"
}

print_warn() {
    echo -e "${AMARILLO}[WARN]${NC} $1"
}

print_error() {
    echo -e "${ROJO}[ERROR]${NC} $1"
}

usage() {
    cat <<EOF
Uso: $0 [opciones]

Opciones:
  --help         Muestra esta ayuda
  --python       Ejecuta Phonendo en Python
  --javascript   Ejecuta Phonendo en JavaScript

Si no se especifica nada, se ejecuta en Python.
EOF
}

get_service_port() {
    local service="$1"
    local env_file="$ROOT_DIR/apps/$service/config.env"

    if [[ ! -f "$env_file" ]]; then
        echo "desconocido"
        return
    fi

    #carga las variables de PORT del config.env , un poco marronero , pero bueno , 
    local port
    port="$(grep -E '^PORT_' "$env_file" | head -n1 | cut -d'=' -f2- | tr -d '[:space:]' || true)"

    if [[ -z "$port" ]]; then
        echo "desconocido"
    else
        echo "$port"
    fi
}

print_service_status() {
    local service="$1"
    local pid="$2"
    local port="$3"
    local process_cmd="$4"

    echo -e "${VERDE}[OK]${NC} ${CIAN}${service}${NC}"
    echo -e "     PID: ${pid}"
    echo -e "     Puerto: ${port}"
    echo -e "     Proceso: ${process_cmd}"
}

cleanup() {
    print_info "Deteniendo todos los servicios..."

    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done

    wait 2>/dev/null || true
    print_ok "Servicios detenidos"
}

# Para que cuando se haga ctrl+C se ejecute clean UP y muertan todos los procesos hijos
trap cleanup EXIT INT TERM

python_up() {
    local service="$1"

    print_info "Ejecutando servicio Python: $service"

    # Rutas del servicio
    local service_dir="$ROOT_DIR/apps/$service/python"
    local venv_dir="$service_dir/.venv"
    local activate_file="$venv_dir/bin/activate"
    local python_bin="$venv_dir/bin/python"
    local pip_bin="$venv_dir/bin/pip"
    local req_file="$service_dir/requirements.txt"
    local py_file="$service_dir/main.py"

    # Comprobar que existe el directorio del servicio
    if [[ ! -d "$service_dir" ]]; then
        print_error "No existe el directorio Python para $service en $service_dir"
        exit 1
    fi

    # Crear el venv si no existe
    if [[ ! -f "$activate_file" ]]; then
        print_warn "No existe entorno virtual para $service en $venv_dir"
        print_info "Creando venv..."
        python3 -m venv "$venv_dir"
        print_ok "Entorno virtual creado para $service"
    fi

    # Comprobar que existe el script principal
    if [[ ! -f "$py_file" ]]; then
        print_error "No existe el archivo main.py en $service_dir"
        exit 1
    fi

    # Instalar dependencias si existe requirements.txt
    if [[ -f "$req_file" ]]; then
        print_info "Instalando dependencias para $service..."
        "$pip_bin" install -r "$req_file" > /dev/null
        print_ok "Dependencias instaladas para $service"
    else
        print_warn "No existe requirements.txt en $service_dir"
    fi

    # Lanzar el servicio en una subshell con un PID distinto
    # No hace falta usar 'source activate'; basta con ejecutar el python del venv.
    (
        cd "$service_dir"
        exec "$python_bin" "$py_file"
    ) 2>&1 | sed "s/^/[${service^^}] /" &

    # Guardamos el PID del proceso en background
    PIDS+=("$!")

    print_ok "Servicio $service levantado con PID ${PIDS[-1]}"
    

    port="$(get_service_port "$service")"

    print_service_status \
        "$service" \
        "${PIDS[-1]}" \
        "$port" \
        "$python_bin $py_file"
}

javascript_up() {
    local service="$1"

    print_info "Ejecutando servicio JavaScript: $service"

    local service_dir="$ROOT_DIR/apps/$service/js"
    local main_file="$service_dir/index.js"

    if [[ ! -d "$service_dir" ]]; then
        print_error "No existe el directorio JavaScript para $service en $service_dir"
        exit 1
    fi

    if [[ ! -f "$main_file" ]]; then
        print_error "No existe el archivo index.js en $service_dir"
        exit 1
    fi

    if [[ ! -d "$service_dir/node_modules" ]]; then
        print_info "Instalando dependencias npm para $service..."
        (
            cd "$service_dir"
            npm install > /dev/null
        )
        print_ok "Dependencias npm instaladas para $service"
    fi

    (
        cd "$service_dir"
        exec node "$main_file"
    ) >/dev/null 2>&1 &

    PIDS+=("$!")
    print_ok "Servicio $service levantado con PID ${PIDS[-1]}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)
            usage
            exit 0
            ;;
        --python)
            MODO_PYTHON=true
            shift
            ;;
        --javascript)
            MODO_JAVASCRIPT=true
            shift
            ;;
        *)
            print_error "Argumento desconocido: $1"
            exit 1
            ;;
    esac
done

# Si no se especifica modo, usamos Python por defecto
if [[ "$MODO_PYTHON" == false && "$MODO_JAVASCRIPT" == false ]]; then
    print_warn "No se especificó ningún modo; ejecutando en Python por defecto"
    MODO_PYTHON=true
fi

# No permitimos ambos modos a la vez
if [[ "$MODO_PYTHON" == true && "$MODO_JAVASCRIPT" == true ]]; then
    print_error "No se pueden ejecutar Python y JavaScript al mismo tiempo"
    exit 1
fi

if [[ "$MODO_PYTHON" == true ]]; then
    print_info "Ejecutando Phonendo en Python..."
    for service in "${SERVICES[@]}"; do
        python_up "$service"
    done
fi

if [[ "$MODO_JAVASCRIPT" == true ]]; then
    print_info "Ejecutando Phonendo en JavaScript..."
    for service in "${SERVICES[@]}"; do
        javascript_up "$service"
    done
fi

print_ok "Todos los servicios han sido lanzados"
print_info "Pulsa Ctrl+C para detenerlos"

# Espera a que terminen los procesos en background
wait