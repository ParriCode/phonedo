FROM rust:1-slim-bookworm AS build
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY src src
RUN cargo build --release --locked

FROM debian:bookworm-slim
WORKDIR /app
COPY --from=build /src/target/release/phonendo-control /usr/local/bin/phonendo-control
COPY seed.json /app/seed.json
ENV CONTROL_ADDR=0.0.0.0:7200 \
    CONTROL_DB=/data/control.db \
    CONTROL_SEED=/app/seed.json
VOLUME /data
EXPOSE 7200
CMD ["phonendo-control"]
