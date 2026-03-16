# Local Development with Docker Compose

This document explains how to run the full fhir_web stack locally using Docker Compose.

---

## Services

| Service    | Host URL                      | Purpose                              |
|------------|-------------------------------|--------------------------------------|
| frontend   | http://localhost:5173         | React / Vite dev server              |
| backend    | http://localhost:8000         | FastAPI application + REST API       |
| hapi-fhir  | http://localhost:8090/fhir    | Local HAPI FHIR R4 server            |

---

## Getting Started

### First run (builds all images)

```bash
docker compose up --build
```

This will:
1. Build the backend image (installs Python deps via `uv sync`)
2. Build the frontend image (runs `npm install`)
3. Pull the `hapiproject/hapi:latest` image from Docker Hub
4. Start all three services

HAPI takes 60–90 seconds to fully start on its first boot. The backend service waits for HAPI's healthcheck to pass before it starts.

### Subsequent runs (uses cached images)

```bash
docker compose up
```

### Stop and remove containers

```bash
docker compose down
```

DuckDB data is preserved in the `backend-data` named volume.

### Stop and remove containers AND delete DuckDB data

```bash
docker compose down -v
```

---

## How the Webhook Flow Works

HAPI subscriptions use a "REST-hook" pattern: when a matching FHIR resource is created or updated, HAPI makes an HTTP POST to a registered callback URL.

```
Browser                  Docker Network
   |                          |
   |  POST /fhir/ServiceRequest  |
   |------------------------->| hapi-fhir:8080
   |                          |   (creates resource)
   |                          |
   |                          |  POST /api/webhooks/hapi/ServiceRequest/{id}
   |                          |-------------------------> backend:8000
   |                          |                              |
   |  GET /api/...            |                              | (reads from HAPI)
   |<---------------------------------------------------------|
```

Key point: HAPI needs to reach the backend *via the Docker network*, not via `localhost`. That's why the compose file sets:

```
WEBHOOK_BASE_URL=http://backend:8000
```

`backend` is the Docker Compose service name, which resolves automatically via Docker's internal DNS. If this were set to `http://localhost:8000`, HAPI would try to connect to its *own* container's port 8000 (which doesn't exist) and every webhook delivery would fail.

---

## Two URLs for the Same HAPI Server

The frontend browser and the backend container reach HAPI at different URLs:

| Who         | URL                            | Why                                         |
|-------------|--------------------------------|---------------------------------------------|
| Browser     | `http://localhost:8090/fhir`   | Host machine port mapping (8090 → 8080)     |
| Backend     | `http://hapi-fhir:8080/fhir`   | Docker network (service name DNS)           |

The frontend's FHIR server dropdown includes a **"HAPI Local (Docker)"** preset that uses `http://localhost:8090/fhir`. The "Create Test Referral" button posts directly from the browser to this URL, which works because port 8090 is mapped to the host. Meanwhile, the backend's `WEBHOOK_FHIR_URL` uses the internal Docker hostname. Both URLs point to the same HAPI container.

---

## Testing the Webhook Pipeline

1. Open `http://localhost:5173` in your browser.
2. Navigate to the **Pipeline Board**.
3. In the server selector, choose **"HAPI Local (Docker)"** (`http://localhost:8090/fhir`).
4. Click **"Subscribe"** — this calls the backend, which registers a REST-hook subscription on HAPI using `WEBHOOK_BASE_URL`.
5. Click **"Create Test Referral"** — the browser POSTs a `ServiceRequest` resource directly to `http://localhost:8090/fhir/ServiceRequest`.
6. HAPI fires the subscription and POSTs to `http://backend:8000/api/webhooks/hapi/ServiceRequest/{id}` via the Docker network.
7. The backend fetches the full resource from HAPI, stores it in DuckDB, and the Pipeline Board refreshes to show the new referral.

---

## Rebuilding After Dependency Changes

If you change `pyproject.toml` or `package.json`, rebuild the relevant image:

```bash
# Backend only
docker compose build backend

# Frontend only
docker compose build frontend

# Then restart
docker compose up
```

---

## Logs

View logs for all services:

```bash
docker compose logs -f
```

View logs for a specific service:

```bash
docker compose logs -f backend
docker compose logs -f hapi-fhir
docker compose logs -f frontend
```

---

## Environment Variables

Environment variables for the containers are set inline in `docker-compose.yml`. The `.env` file at the project root is used for local (non-Docker) development and is **not** loaded by Docker Compose by default.

To override a variable for Docker without editing `docker-compose.yml`, create a `.env` file at the project root with `COMPOSE_`-prefixed overrides, or use:

```bash
WEBHOOK_BASE_URL=https://my-tunnel.ngrok.io docker compose up
```
