#!/bin/sh
# Crea el alias de Stellar con la clave secreta recibida por entorno (nunca va en la imagen).
set -e
if [ -n "$STELLAR_SECRET_KEY" ]; then
    identity_dir="${XDG_CONFIG_HOME:-$HOME/.config}/stellar/identity"
    mkdir -p "$identity_dir"
    printf 'secret_key = "%s"\n' "$STELLAR_SECRET_KEY" > "$identity_dir/${STELLAR_SOURCE:-alex}.toml"
    chmod 600 "$identity_dir/${STELLAR_SOURCE:-alex}.toml"
fi
exec "$@"
