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

Ejecuta Phonendo en Python.
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

get_service_dir() {
    local service="$1"

    if [[ "$service" == "reader" ]]; then
        echo "$ROOT_DIR/apps/reader/implementations/linux"
    else
        echo "$ROOT_DIR/apps/$service"
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

service_up() {
    local service="$1"

    print_info "Ejecutando servicio: $service"

    # Rutas del servicio
    local service_dir
    service_dir="$(get_service_dir "$service")"
    local venv_dir="$service_dir/.venv"
    local activate_file="$venv_dir/bin/activate"
    local python_bin="$venv_dir/bin/python"
    local req_file="$service_dir/requirements.txt"
    local py_file="$service_dir/main.py"

    # Comprobar que existe el directorio del servicio
    if [[ ! -d "$service_dir" ]]; then
        print_error "No existe el directorio para $service en $service_dir"
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
        "$python_bin" -m pip install -r "$req_file" > /dev/null
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

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)
            usage
            exit 0
            ;;
        *)
            print_error "Argumento desconocido: $1"
            exit 1
            ;;
    esac
done

print_info "Ejecutando Phonendo..."
for service in "${SERVICES[@]}"; do
    service_up "$service"
done

print_ok "Todos los servicios han sido lanzados"
print_info "Pulsa Ctrl+C para detenerlos"

# Espera a que terminen los procesos en background
wait
