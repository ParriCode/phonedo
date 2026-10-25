FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PHONENDO_VERBOSE=true PHONENDO_LOGS_DIR=/tmp/phonendo-logs
WORKDIR /app/manager
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY . .
EXPOSE 3003
CMD ["python", "manager.py"]
