# OryxShield

**Integrated Public Health Surveillance & Outbreak Response Platform**

Built by NEHMTECH INNOVATIONS LIMITED · Author: Nehemiah

OryxShield gives national and regional health authorities one place to **detect outbreaks early, assess risk, and coordinate the response**. It ingests surveillance data, flags anomalies, scores risk, raises alerts, and drives multi-agency response workflows, with live updates pushed to every connected dashboard.

---

## What it does

| Capability | Details |
|---|---|
| **Surveillance** | Health-data ingestion, disease cases, anomaly detection, hotspot mapping, **statistical early warning** (EARS C1/C2/C3, CUSUM, Poisson exceedance, Rt estimate), run hourly by Celery and raising deduplicated anomalies automatically, also available on demand via `GET /api/v1/surveillance/dashboard/early-warning/?disease_code=...&location=...&days=60` |
| **Risk assessment** | Risk scoring, outbreak probability, threshold-based alerts |
| **Response** | Response plans, activations, incidents, interventions, decision support |
| **Coordination** | Multi-agency tasks, teams, meetings, escalation |
| **Resources** | Inventory, allocations, supply requests and approvals |
| **Communications** | Messaging, broadcasts, announcements; SMS, push and email delivery; geo-targeting; translation |
| **Analytics** | Epidemiological models (SIR/SEIR, time series), spatial analysis, reports, PDF/CSV/XLSX export |
| **Operations** | Contact tracing, quarantine, vaccination tracking, field logs |
| **Mobile** | Field-officer and CHW endpoints, device tokens, offline sync |
| **Integrations** | DHIS2, SORMAS, WHO reporting, Africa CDC, LIS/EMR connectors, webhooks, encrypted credential storage |
| **Real time** | Django Channels WebSockets: alerts, notifications, surveillance, dashboard, response, resources, operations, system status |
| **Security** | JWT auth, TOTP/SMS/email 2FA, role and location-based permissions, API keys, audit logging, Fernet-encrypted integration secrets |

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  React 18 SPA (Vite · React Router 6 · Axios)        │
│  Lazy-loaded pages · role-based routing              │
└───────────────┬───────────────────────┬──────────────┘
                │ REST  /api/v1/        │ WS  /ws/...
                ▼                       ▼
┌──────────────────────────────────────────────────────┐
│  Django + DRF   │   Django Channels (Daphne ASGI)    │
│  12 domain apps │   8 WebSocket consumers            │
└───────────────┬──────────────────────────────────────┘
                │ Celery tasks
                ▼
┌──────────────────────────────────────────────────────┐
│  PostgreSQL · Redis (broker, cache, channel layer)   │
│  S3-compatible storage (optional)                    │
└──────────────────────────────────────────────────────┘
```

**Data flow:** data ingested → anomaly detection (Celery) → risk recalculation → alert → WebSocket push + SMS/push/email → response activation → coordination tasks.

### Repository layout

```
backend/    Django project (config/, core/, surveillance/, risk_assessment/, response/,
            coordination/, resources/, communications/, analytics/, operations/,
            mobile/, integrations/, websockets/, tests/)
frontend/   React SPA (src/pages, components, context, hooks/ws, services/api.js)
oryxshield/ Earlier standalone frontend prototype (kept for reference)
```

Details: [backend/README.md](backend/README.md) · [frontend/README.md](frontend/README.md)

## Roles

| Role | Access |
|---|---|
| `admin` | Everything, including users, locations, settings, audit logs |
| `analyst` | Surveillance, risk, analytics |
| `coordinator` | Response, coordination, resources, communications |
| `field_officer` | Response detail, operations, mobile |
| `public` | Dashboard only |

## Quick start

**Requirements:** Python 3.12 (matches the Dockerfile and pinned requirements), Node 18+, Redis, PostgreSQL (SQLite works for development).

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # then fill in your own values
python manage.py migrate
python manage.py createsuperuser                      # create your own admin
python manage.py seed_data                            # optional demo data (development only)
daphne -b 0.0.0.0 -p 8000 config.asgi:application
celery -A config worker -l info                       # separate terminal
celery -A config beat   -l info                       # separate terminal

# Frontend
cd frontend
npm install
npm run dev                                           # http://localhost:5173
```

`frontend/.env`:
```env
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
```

API docs: Swagger `http://localhost:8000/api/docs/`, ReDoc `http://localhost:8000/api/redoc/`.

> Demo users from `seed_data` share the password in `SEED_USER_PASSWORD`; if unset, a random one is printed once. There are no default credentials. Never run the seed command against production.

## Configuration & secrets

All configuration comes from environment variables; see [backend/.env.example](backend/.env.example) for the full list. **Never commit `.env`**: it is git-ignored. Set at minimum `SECRET_KEY`, database and Redis settings, and an integration encryption key. Integration credentials are encrypted at rest. If a secret is ever exposed, rotate it.

## Testing

```bash
cd backend
pytest                      # settings: config.settings.testing (in-memory SQLite, eager Celery)
cd ../frontend && npm run build
```

Current suite (~1,250 tests) covers authentication, 2FA, permissions, credential encryption, the early-warning engine and API, a smoke test of every parameter-less GET route, and negative-path tests of every write route (bad bodies and unknown IDs never cause a 5xx; anonymous users cannot modify data). GitHub Actions (`.github/workflows/ci.yml`) runs the backend tests and frontend build on every push. The frontend production build passes.

## Deployment

- `backend/Dockerfile` (multi-stage, non-root) and `backend/Procfile` (gunicorn + uvicorn worker, Celery worker, Celery beat, migrate on release) target Railway or any container host.
- Use `config.settings.production`: set `DEBUG=False`, `ALLOWED_HOSTS`, secure-cookie and HTTPS flags, and `DATABASE_URL`/`REDIS_URL`.

## Technology

**Backend:** Django 5.2, DRF, SimpleJWT, Channels + Daphne, Celery + Redis, django-otp, django-allauth, drf-spectacular, scikit-learn / pandas / numpy, ReportLab, boto3.
**Frontend:** React 18, Vite 5, React Router 6, Axios, Recharts, Framer Motion, date-fns.
**Messaging:** Africa's Talking and Twilio (SMS), Firebase/APNS (push), SMTP/SendGrid (email).

## Status

Backend modules and frontend workflows are implemented; the frontend builds and the backend test suite passes. Not yet deployed to production. Pending work: broaden automated test coverage across the domain apps and a staging deployment.

---

*NEHMTECH INNOVATIONS LIMITED · OryxShield*
