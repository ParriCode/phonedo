FROM node:20-bookworm-slim AS node

WORKDIR /circuits
COPY circuits/package.json circuits/package-lock.json ./
RUN npm ci

FROM python:3.11-slim-bookworm

ARG TARGETARCH
ARG STELLAR_CLI_VERSION=28.1.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl libdbus-1-3 \
    && case "$TARGETARCH" in \
         amd64) stellar_arch=x86_64-unknown-linux-gnu ;; \
         arm64) stellar_arch=aarch64-unknown-linux-gnu ;; \
         *) echo "Arquitectura no soportada: $TARGETARCH" >&2; exit 1 ;; \
       esac \
    && curl -fsSL "https://github.com/stellar/stellar-cli/releases/download/v${STELLAR_CLI_VERSION}/stellar-cli-${STELLAR_CLI_VERSION}-${stellar_arch}.tar.gz" \
       | tar -xz -C /usr/local/bin stellar \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /circuits/node_modules /circuits/node_modules

WORKDIR /app/publisher
COPY apps/publisher/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/publisher/ ./

EXPOSE 3005
CMD ["python", "publisher.py"]
