# OryxShield

**Integrated Public Health Surveillance & Outbreak Response Platform**
Developed by NEHMTECH INNOVATIONS LIMITED · Author: Nehemiah

---


## Overview
OryxShield is a full-stack digital infrastructure platform for real-time disease surveillance, outbreak detection, and coordinated public health response. It is designed for national and regional health authorities, epidemiologists, field officers, and emergency coordinators operating under high-pressure, time-sensitive conditions.

The platform ingests health data from multiple sources, runs automated anomaly detection and risk scoring, generates alerts, orchestrates multi-agency response workflows, and delivers actionable reports — all in real time.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  React 18 SPA  (Vite · React Router v6 · Axios)     │
│  Dark design system · Role-based routing             │
└─────────────┬──────────────────────┬────────────────┘
              │  REST /api/v1/       │  WSS /ws/
              ▼                      ▼
┌─────────────────────────────────────────────────────┐
│  Django 5.2 + DRF       │  Django Channels (ASGI)   │
│  13 domain apps         │  7 WebSocket consumers    │
│  Daphne ASGI server     │  Redis channel layer      │
└─────────────────────────────────────────────────────┘
              │  Celery tasks
              ▼
┌─────────────────────────────────────────────────────┐
│  PostgreSQL  │  Redis (broker + cache)  │  AWS S3   │
└─────────────────────────────────────────────────────┘
```

### Backend — Django 5.2 + Django REST Framework

Organised into 13 Django applications, each owning a distinct operational domain:

| App | Responsibility |
|-----|----------------|
| `core` | User accounts, roles, JWT auth, 2FA, notifications, audit logs, API keys, system config |
| `surveillance` | Health data ingestion, anomaly detection, disease case management, hotspot mapping |
| `risk_assessment` | Risk scoring engine, outbreak probability models, threshold alerts |
| `response` | Response plan lifecycle, incident management, intervention tracking |
| `coordination` | Multi-agency task management, meetings, coordination threads |
| `resources` | Inventory tracking, resource allocation, supply requests and approvals |
| `communications` | Messaging, announcements, broadcasts, public feedback handling |
| `analytics` | Epi reports, dashboards, data exports, WHO/IHR submissions, PDF generation |
| `operations` | Contact tracing, quarantine management, vaccination tracking, field logs |
| `mobile` | Mobile-optimised endpoints for field officers and CHWs |
| `integrations` | DHIS2, SORMAS, WHO EIOS, HL7 FHIR connectors, inbound webhooks |
| `websockets` | Django Channels consumers for live data streams |
| `ws_mgmt` | WebSocket REST management — connection audit, channel groups, broadcasts |

### Frontend — React 18 + Vite

A single-page application using React Router v6. All dashboard pages are lazy-loaded. The shell (Sidebar + Topbar) stays mounted across route changes. Public pages (Home, About, Contact, Privacy, Terms) are accessible without authentication.

---

## Real-Time Data Flow

```
Health Data Ingestion (REST POST /api/v1/surveillance/health-data/)
        │
        ▼
  Anomaly Detection  ◄── Celery worker (runs every 60 s)
        │                Statistical thresholds + SIR/SEIR models
        ▼
  AnomalyDetection record created
        │
        ▼
  Risk Score Recalculation  ◄── Celery task triggered within 5 s
        │                       ARIMA time-series + spatial hotspot analysis
        ▼
  Alert generated
        │
        ├──► WebSocket push to connected dashboard clients
        │    (Django Channels / Daphne ASGI → /ws/alerts/)
        │
        ├──► SMS  (Africa's Talking / Twilio)
        ├──► Push (Firebase / APNS)
        └──► Email (SendGrid)
                │
                ▼
        ResponseActivation (if severity threshold met)
                │
                ▼
        Coordination tasks assigned to agencies
```

---

## Authentication & Roles

JWT authentication via SimpleJWT. Short-lived access tokens are refreshed transparently by the frontend API service layer. 2FA is supported via TOTP, SMS, and email OTP.

| Role | Access |
|------|--------|
| `admin` | Full system access including user management and settings |
| `analyst` | Surveillance, risk assessment, analytics |
| `coordinator` | Response, coordination, resources, communications |
| `field_officer` | Response detail, operations, mobile endpoints |
| `public` | Dashboard only |

---

## Key Technologies

**Backend**

| Concern | Technology |
|---------|-----------|
| Framework | Django 5.2, DRF 3.16 |
| Language | Python 3.12 |
| ASGI server | Daphne |
| Task queue | Celery 5.6 + Redis |
| Real-time | Django Channels 4.3 |
| Database | PostgreSQL (production), SQLite (development) |
| Auth | SimpleJWT, pyotp, python-social-auth |
| PDF generation | ReportLab 4.4.9 |
| Data science | scipy, statsmodels, scikit-learn, numpy, pandas |
| Geospatial | geopy, shapely, pyproj |
| Storage | boto3 (AWS S3) |

**Frontend**

| Concern | Technology |
|---------|-----------|
| Framework | React 18 |
| Build | Vite 5 |
| Routing | React Router v6 |
| HTTP | Axios |
| Animation | Framer Motion |
| Charts | Recharts |
| Dates | date-fns |
| Styling | Inline styles only — no external UI framework |

**Notifications & Communications**

- Africa's Talking — SMS (Southern Africa primary)
- Twilio — SMS (global fallback)
- Firebase Cloud Messaging — Android push
- APNS — iOS push
- SendGrid — transactional email

---

## Running Locally

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env: SECRET_KEY, DATABASE_URL, REDIS_URL, and external API keys

# Run migrations
python manage.py migrate

# Seed development data (creates users, locations, and records for all 12 apps)
python manage.py seed_data
# Default admin: username=admin  password=Admin1234!

# Start the ASGI server (required for WebSocket support)
daphne -b 0.0.0.0 -p 8000 config.asgi:application

# Celery worker (separate terminal)
celery -A config worker --loglevel=info

# Celery beat — scheduled tasks (separate terminal)
celery -A config beat --loglevel=info
```

API documentation is auto-generated and served at:
- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`

### Frontend

```bash
cd frontend
npm install
npm run dev     # starts at http://localhost:5173
```

Create `frontend/.env`:
```env
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
```

---

## Design System

Fixed dark theme applied consistently across all pages:

| Token | Hex | Usage |
|-------|-----|-------|
| Background | `#0a0f1e` | Page background |
| Surface | `#111827` | Cards, panels |
| Surface High | `#151e2e` | Inputs, hover, shimmer |
| Accent | `#3b82f6` | Primary actions, links, focus |
| Success | `#10b981` | Confirmed, resolved, online |
| Warning | `#f59e0b` | Moderate alerts, pending |
| Danger | `#ef4444` | Critical alerts, destructive actions, errors |
| Text | `#f9fafb` | Primary text |
| Text Sub | `#9ca3af` | Secondary / muted text |

**Typography:**
- **Bebas Neue** — page and section headings
- **Space Mono** — monospace labels, badges, metadata, table headers
- **IBM Plex Sans** — body text, descriptions, form fields

---

## Development Status

The backend API is complete across all 13 modules (83 endpoints, all returning 200). The frontend covers all primary workflows from public landing pages through the full operations platform. The platform is not yet deployed to a production environment.

See [`backend/README.md`](backend/README.md) and [`frontend/README.md`](frontend/README.md) for detailed technical documentation.

---

*NEHMTECH INNOVATIONS LIMITED · OryxShield*
