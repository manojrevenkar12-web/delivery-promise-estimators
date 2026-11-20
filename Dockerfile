FROM node:22-slim AS web
WORKDIR /web
RUN corepack enable
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DPE_WEB_DIST=/app/web/dist
WORKDIR /app
RUN apt-get update -q && apt-get install -y -q --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY dpe/ dpe/
COPY config/ config/
COPY reports/ reports/
COPY --from=web /web/dist web/dist
RUN useradd -u 10001 -m app
USER 10001
EXPOSE 8080
CMD ["uvicorn", "dpe.service.api:app", "--host", "0.0.0.0", "--port", "8080"]
