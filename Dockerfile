FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends     curl procps ffmpeg git     && rm -rf /var/lib/apt/lists/*     && ARCH=$(dpkg --print-architecture)     && curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${ARCH}"        -o /usr/local/bin/cloudflared     && chmod +x /usr/local/bin/cloudflared

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app/
RUN chmod +x /app/implementation/ops/docker/entrypoint.sh

EXPOSE 8787 3001

ENTRYPOINT ["/app/implementation/ops/docker/entrypoint.sh"]
