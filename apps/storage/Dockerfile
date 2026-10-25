FROM python:3.11-slim-bookworm AS builder
RUN apt-get update && apt-get install -y --no-install-recommends g++ libleveldb-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/requirements.txt
RUN pip wheel --no-cache-dir --no-binary=plyvel --wheel-dir=/wheels -r /tmp/requirements.txt

FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PHONENDO_VERBOSE=true PHONENDO_LOGS_DIR=/tmp/phonendo-logs \
    PHONENDO_DB_PATH=/data/phonendo
RUN apt-get update && apt-get install -y --no-install-recommends libleveldb1d \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /wheels /wheels
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r /tmp/requirements.txt \
    && rm -rf /wheels
WORKDIR /app/storage
COPY . .
EXPOSE 5000
VOLUME ["/data"]
CMD ["python", "main.py"]
