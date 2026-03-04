FROM node:22-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv curl supervisor procps git \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g openclaw@latest opencami@latest

WORKDIR /app
COPY services/doubao-stt-proxy/requirements.txt /app/services/doubao-stt-proxy/
RUN python3 -m venv /app/.venv \
    && /app/.venv/bin/pip install --no-cache-dir -r /app/services/doubao-stt-proxy/requirements.txt

COPY . /app/

RUN chmod +x /app/services/doubao-stt-proxy/transcribe.sh \
    && chmod +x /app/openclaw/sync.sh \
    && chmod +x /app/docker/entrypoint.sh

EXPOSE 8787 18789 3000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
