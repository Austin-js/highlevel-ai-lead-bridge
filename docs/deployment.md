# Deployment

## Local Python

```powershell
Copy-Item .env.example .env
python -m pip install -e .
python -m pip install --group dev
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Set a strong `WEBHOOK_SHARED_SECRET`, production database URL, and only the integrations you intend to enable.

For a production database, set `DATABASE_AUTO_CREATE=false` and apply the versioned schema explicitly:

```powershell
alembic upgrade head
```

## Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The Compose configuration persists SQLite data in `./data`. Back up that path, or point `DATABASE_URL` at managed PostgreSQL for a production deployment.

For the included local PostgreSQL profile, configure `DATABASE_URL=postgresql+asyncpg://highlevel:change-me@postgres:5432/highlevel_lead_bridge`, then run `docker compose --profile postgres up --build` and apply `alembic upgrade head` from the application container.

## VPS and HTTPS

The FastAPI application itself runs well on a small CPU VPS. Place a reverse proxy such as Caddy, Nginx, or Traefik in front of it, terminate TLS there, and expose only HTTPS. Restrict inbound traffic to the proxy, monitor `/health` and `/ready`, centralize logs, and use a secret manager rather than committed environment files.

## LLM deployment

Hosted LLM APIs generally remove GPU operations. If self-hosting inference, deploy the Ollama or OpenAI-compatible server separately from the API service. Larger local models need GPU capacity for production responsiveness; do not treat a small CPU VPS as a production inference host.

## Backup and recovery

Back up the database and preserve application logs. Investigate events with `failed` or `partially_completed` status before replaying them. Keep provider, notification, and HighLevel credentials rotated and scoped to the minimum needed permissions.
