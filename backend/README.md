# OryxShield — Backend

Public health emergency management platform for national health authorities and Africa CDC.
Built with Django 5.2 + Django REST Framework + Django Channels.

**Company:** NEHMTECH INNOVATIONS LIMITED · **Author:** Nehemiah

---

## Table of Contents

1. [Tech Stack](#1-tech-stack)
2. [Project Layout](#2-project-layout)
3. [Getting Started](#3-getting-started)
4. [Environment Variables](#4-environment-variables)
5. [Settings Structure](#5-settings-structure)
6. [API Reference](#6-api-reference)
7. [Authentication](#7-authentication)
8. [Apps at a Glance](#8-apps-at-a-glance)
9. [WebSockets](#9-websockets)
10. [Celery Tasks](#10-celery-tasks)
11. [Middleware Stack](#11-middleware-stack)
12. [Model Conventions](#12-model-conventions)
13. [Seed Data](#13-seed-data)
14. [PDF Report Generation](#14-pdf-report-generation)
15. [Health Checks](#15-health-checks)
16. [Known Fixes Applied](#16-known-fixes-applied)

---

## 1. Tech Stack

| Concern | Technology | Version |
|---------|-----------|---------|
| Framework | Django + Django REST Framework | 5.2 / 3.16 |
| Language | Python | 3.12 |
| ASGI server | Daphne | 4.x |
| WebSocket layer | Django Channels | 4.3 |
| Task queue | Celery | 5.6 |
| Message broker / cache | Redis | — |
| Database | PostgreSQL (prod) · SQLite (dev) | — |
| Auth | SimpleJWT + pyotp (TOTP) + python-social-auth | — |
| API docs | drf-spectacular (Swagger / ReDoc) | — |
| PDF generation | ReportLab | 4.4.9 |
| Data science | scipy, statsmodels, scikit-learn, numpy, pandas | — |
| Geospatial | geopy, shapely, pyproj | — |
| Object storage | boto3 (AWS S3) | — |


---

## 2. Project Layout

```
backend/
├── config/                   # Django project package
│   ├── settings/
│   │   ├── base.py           # Shared settings (installed apps, middleware, DRF config)
│   │   ├── development.py    # DEBUG=True, SQLite, relaxed CORS
│   │   ├── production.py     # PostgreSQL, S3, HSTS, strict CORS
│   │   └── testing.py        # Fast password hasher, in-memory channel layer
│   ├── urls.py               # Root URL config — all apps mounted under /api/v1/
│   ├── asgi.py               # ASGI entry point (Daphne + Channels)
│   ├── wsgi.py               # WSGI entry point (Gunicorn — non-WS workloads)
│   └── celery.py             # Celery app ("oryxshield")
│
├── core/                     # Users, auth, audit, notifications, API keys, system config
├── surveillance/             # Data ingestion, anomaly detection, hotspots
├── risk_assessment/          # Risk scoring, thresholds, outbreak alerts
├── response/                 # Response levels, protocols, activations, action items
├── coordination/             # Agencies, teams, tasks, meetings
├── resources/                # Inventory, requests, allocations
├── communications/           # Campaigns, broadcasts, SMS, push, public feedback
├── analytics/                # Epi models, dashboards, exports, PDF reports
├── operations/               # Contact tracing, quarantine, vaccination, field logs
├── integrations/             # DHIS2, SORMAS, WHO EIOS, HL7 FHIR connectors
├── websockets/               # Channels consumers, channel groups, presence tracking
├── mobile/                   # Device tokens, push delivery, CHW endpoints
│
├── manage.py
├── requirements.txt
├── requirements-lock.txt
├── Dockerfile
└── Procfile
```

---

## 3. Getting Started

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Fill in: SECRET_KEY, DATABASE_URL, REDIS_URL, and any external API keys

# 3. Run migrations (auto-seeds ChannelGroup rows for WebSocket consumers)
python manage.py migrate

# 4. Seed all development data
python manage.py seed_data
# Create an admin account:  python manage.py createsuperuser
# Seeded demo users share SEED_USER_PASSWORD (a random one is printed if unset)
# Seeds all 12 apps with realistic records

# 5. Start the ASGI server (required for WebSocket support)
daphne -b 0.0.0.0 -p 8000 config.asgi:application

# 6. Celery worker — separate terminal
celery -A config worker --loglevel=info

# 7. Celery beat — scheduled tasks — separate terminal
celery -A config beat --loglevel=info
```

---

## 4. Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Django secret key |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis URL for Celery broker and channel layer |
| `DJANGO_SETTINGS_MODULE` | Yes | e.g. `config.settings.development` |
| `ALLOWED_HOSTS` | Prod | Comma-separated host list |
| `CORS_ALLOWED_ORIGINS` | Prod | Frontend origin(s) |
| `AWS_ACCESS_KEY_ID` | Prod | S3 media storage |
| `AWS_SECRET_ACCESS_KEY` | Prod | S3 media storage |
| `AWS_STORAGE_BUCKET_NAME` | Prod | S3 bucket name |
| `SENDGRID_API_KEY` | Optional | Email delivery |
| `AFRICAS_TALKING_API_KEY` | Optional | SMS (Southern Africa) |
| `TWILIO_AUTH_TOKEN` | Optional | SMS (global fallback) |
| `FCM_SERVER_KEY` | Optional | Android push notifications |

---

## 5. Settings Structure

Settings are split by environment in `config/settings/`:

- `base.py` — all shared config: installed apps, middleware order, DRF defaults, Celery config, logging
- `development.py` — `DEBUG=True`, SQLite, in-process channel layer, relaxed CORS, console email backend
- `production.py` — PostgreSQL, Redis channel layer, S3 storage, HSTS, strict CORS, Sentry
- `testing.py` — fast password hasher, in-memory SQLite, in-memory channel layer, disabled Celery

Set via:
```bash
export DJANGO_SETTINGS_MODULE=config.settings.development
```

Or in `.env`:
```
DJANGO_SETTINGS_MODULE=config.settings.development
```

---

## 6. API Reference

**Base URL:** `http://localhost:8000/api/v1/`

**Documentation:**
- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`
- Schema: `http://localhost:8000/api/schema/`

### URL Map

| Prefix | App | Notes |
|--------|-----|-------|
| `/api/v1/auth/` | core | Login, logout, 2FA, token refresh, me |
| `/api/v1/users/` | core | User CRUD, profile management |
| `/api/v1/notifications/` | core | List, mark read, mark all read, delete |
| `/api/v1/audit-logs/` | core | Read-only, immutable records |
| `/api/v1/configurations/` | core | System config key/value pairs |
| `/api/v1/api-keys/` | core | API key management |
| `/api/v1/locations/` | core | Geographic location tree |
| `/api/v1/surveillance/` | surveillance | Health data, anomalies, hotspots, reports |
| `/api/v1/risk/` | risk_assessment | Risk scores, alerts, thresholds, forecasts |
| `/api/v1/response/` | response | Protocols, activations, action items, triggers |
| `/api/v1/coordination/` | coordination | Agencies, teams, tasks, meetings |
| `/api/v1/resources/` | resources | Inventory, facilities, allocations, requests |
| `/api/v1/communications/` | communications | Campaigns, broadcasts, announcements, feedback |
| `/api/v1/analytics/` | analytics | Reports, dashboards, epi models, exports |
| `/api/v1/operations/` | operations | Incidents, contacts, quarantine, vaccination |
| `/api/v1/mobile/` | mobile | CHW tools, offline sync, field officer endpoints |
| `/api/v1/integrations/` | integrations | External systems, jobs, webhooks, data transfers |
| `/api/v1/ws-mgmt/` | websockets | Channel groups, connection audit, broadcasts |

### Pagination

All list endpoints return:

```json
{
  "count": 142,
  "next": "http://localhost:8000/api/v1/surveillance/health-data/?page=2",
  "previous": null,
  "results": [ ... ]
}
```

Default `page_size` is 50. Override with `?page_size=N&page=N`.

Some time-series endpoints use `CursorPagination` — these return `next` and `previous` cursor URLs instead of page numbers.

### Error Responses

DRF returns structured errors in one of these shapes:

```json
{ "detail": "Not found." }
{ "message": "Custom message." }
{ "field_name": ["This field is required."] }
{ "non_field_errors": ["Invalid credentials."] }
```

---

## 7. Authentication

### JWT Flow

```
POST /api/v1/auth/login/
  → { access, refresh, user }

POST /api/v1/auth/token/refresh/
  → { access }

GET /api/v1/auth/me/
  → { id, username, email, role, first_name, last_name, profile, ... }
```

Access tokens expire in 15 minutes. The frontend auto-refreshes using the stored refresh token, queuing concurrent requests during the refresh cycle.

### 2FA Flow

```
POST /api/v1/auth/login/   → { requires_2fa: true, session_token, method }
POST /api/v1/auth/2fa/verify/  (body: { code, session_token })
  → { access, refresh, user }
```

Methods: `totp` (authenticator app), `sms`, `email`.

### API Key Auth

Include `X-API-Key: <key>` in the request header. Keys are hashed with SHA-256; the raw key is returned only once at creation time.

### Roles

Roles are stored as a string field on `UserProfile`. Role-based permission classes (`IsAdmin`, `IsAnalyst`, etc.) are applied at the ViewSet level.

---

## 8. Apps at a Glance

### core

Models: `UserProfile`, `Location`, `Notification`, `AuditLog`, `SystemConfiguration`, `APIKey`

Key endpoints:
- `POST /auth/login/` — login with optional 2FA
- `POST /auth/logout/` — blacklist refresh token
- `GET /auth/me/` — current user with profile
- `POST /notifications/{id}/mark_read/` — mark single notification read
- `POST /notifications/mark_all_read/` — bulk mark read
- `GET /audit-logs/` — paginated immutable audit trail
- `GET /locations/tree/` — full geographic hierarchy

### surveillance

Models: `DataSource`, `HealthData`, `DiseaseProfile`, `AnomalyDetection`, `CaseCluster`, `Hotspot`, `SurveillanceReport`, `DataQualityCheck`

Key endpoints:
- `GET /surveillance/health-data/` — paginated health data (cursor pagination)
- `POST /surveillance/health-data/bulk_upload/` — batch ingestion
- `GET /surveillance/anomalies/` — detected anomalies with severity
- `GET /surveillance/hotspots/` — geographic hotspot records

### risk_assessment

Models: `RiskScore`, `ThreatClassification`, `Alert`, `Threshold`, `RiskFactor`, `PredictiveModel`

Key endpoints:
- `GET /risk/scores/` — risk scores by location/disease
- `POST /risk/scores/{id}/recalculate/` — trigger score recalculation
- `GET /risk/alerts/` — outbreak risk alerts

### analytics

Models: `EpidemiologicalModel`, `SpatialAnalysis`, `TimeSeriesAnalysis`, `StatisticalReport`, `Dashboard`, `DataExport`, `Indicator`, `IndicatorValue`, `ReportTemplate`

Key endpoints:
- `GET /analytics/reports/` — paginated statistical reports
- `GET /analytics/reports/{id}/download/` — download report as PDF (generated via ReportLab if no file uploaded)
- `GET /analytics/reports/published/` — published reports only
- `POST /analytics/templates/{id}/generate/` — generate report from template
- `POST /analytics/exports/request_export/` — async export (returns task ID)

### integrations

Models: `ExternalSystem`, `DataMapping`, `IntegrationJob`, `Webhook`, `WebhookLog`, `APIKey`, `IntegrationLog`, `DataTransfer`

Key endpoints:
- `GET /integrations/systems/` — registered external systems with health status
- `POST /integrations/jobs/trigger/` — trigger a sync job
- `POST /integrations/webhooks/{id}/verify/` — verify webhook signature
- `GET /integrations/transfers/` — data transfer records

### communications

Models: `MessageTemplate`, `Campaign`, `Message`, `Broadcast`, `ContactList`, `PublicAnnouncement`, `SocialMediaPost`, `FeedbackResponse`

Public (no auth required):
- `GET /communications/announcements/published/` — public announcements for home page
- `POST /communications/feedback/` — public contact/feedback submission

---

## 9. WebSockets

WebSocket URL format: `ws://localhost:8000/ws/<group>/`

Authentication is passed as a query parameter: `?token=<access_token>`

All consumers extend `BaseConsumer` which handles JWT authentication, presence tracking, and group subscribe/unsubscribe.

| Consumer | URL | Group | Purpose |
|----------|-----|-------|---------|
| `AlertConsumer` | `/ws/alerts/` | `alerts` | Live alert feed |
| `SurveillanceConsumer` | `/ws/surveillance/` | `surveillance` | Incoming case data stream |
| `ResponseConsumer` | `/ws/response/` | `response_coordination` | Activation status updates |
| `ResourceConsumer` | `/ws/resources/` | `resources` | Inventory change events |
| `OperationsConsumer` | `/ws/operations/` | `operations` | Field team status |
| `DashboardConsumer` | `/ws/dashboard/` | `system_status` | Aggregated dashboard snapshot (staff only) |
| `NotificationConsumer` | `/ws/notifications/` | `user_{user_id}` | Personal notifications per user |

The six shared `ChannelGroup` rows are seeded by migration `websockets/0002_seed_channel_groups`. To re-seed manually:

```bash
python manage.py seed_channel_groups
```

---

## 10. Celery Tasks

Celery app name: `oryxshield` (configured in `config/celery.py`).

Run the worker:
```bash
celery -A config worker --loglevel=info
```

Run the scheduler (periodic tasks):
```bash
celery -A config beat --loglevel=info
```

All tasks follow these conventions:
- `bind=True` — access to retry context
- `max_retries=3`, explicit `default_retry_delay`
- Multi-model writes wrapped in `transaction.atomic()`
- Counter updates use `F()` expressions — never read-then-write

Key periodic tasks:

| Task | Schedule | Purpose |
|------|----------|---------|
| `run_anomaly_detection` | Every 60 s | Check health data against baseline thresholds |
| `recalculate_risk_scores` | Every 5 min | Update risk scores after new anomalies |
| `send_scheduled_campaigns` | Every 5 min | Dispatch queued communication campaigns |
| `sync_external_systems` | Per-system interval | Poll DHIS2, SORMAS, and other external sources |
| `cleanup_expired_tokens` | Daily | Remove expired JWT blacklist entries |

---

## 11. Middleware Stack

Applied in this order (configured in `config/settings/base.py`):

| Middleware | Purpose |
|-----------|---------|
| `HealthCheckBypassMiddleware` | Short-circuits `/health/` before all other middleware |
| `MaintenanceModeMiddleware` | Returns 503 when `MAINTENANCE_MODE=True` in settings |
| `CorrelationIdMiddleware` | Generates `X-Correlation-ID`, attaches to request and response |
| `RequestTimingMiddleware` | Adds `X-Response-Time` header to every response |
| `SecurityHeadersMiddleware` | CSP, HSTS, X-Frame-Options, X-Content-Type-Options |
| `RateLimitMiddleware` | Per-IP and per-user Redis-backed throttling |
| `AuditLoggingMiddleware` | Auto-creates `AuditLog` entries for all mutating requests |
| `ExceptionLoggingMiddleware` | Catches unhandled exceptions, returns structured JSON |
| `UserActivityMiddleware` | Updates `last_activity` via `F()` on every authenticated request |

---

## 12. Model Conventions

**Every model:**
- Inherits `TimeStampedModel` → auto `id` (UUID primary key), `created_at`, `updated_at`
- Has `is_deleted = BooleanField(default=False)` — rows are never hard-deleted
- All base querysets filter `.filter(is_deleted=False)`
- Soft-delete via `obj.soft_delete()` which calls `save(update_fields=['is_deleted', 'updated_at'])`

**Every `save()` on an existing row:**
- Always pass `update_fields` — never a bare `.save()` on an existing object
- Counter increments/decrements always use `F()` expressions

**UUIDs as primary keys:**
- `UUIDField(primary_key=True, default=uuid.uuid4)` — UUID is generated on object instantiation, before `save()`
- Never use `if self.pk:` to detect new records — use `if not self._state.adding:` instead

**AuditLog:**
- Immutable — `save()` raises `ValidationError` when `not self._state.adding` is False
- All ViewSets write an `AuditLog` entry on create, update, and destroy

**Serializer field overrides for Django 5.2 compatibility:**
- `GenericIPAddressField` fields must be declared explicitly as `serializers.CharField(read_only=True, allow_null=True, default=None)` in serializers — Django 5.2 changed the `ip_address_validators` return value, breaking DRF's automatic field mapping

**Related name conventions (cross-app FK references from `User`):**

```
user.profile               →  core.UserProfile (OneToOne)
user.core_api_keys         →  core.APIKey
user.notifications         →  core.Notification
user.audit_logs            →  core.AuditLog
user.statistical_reports   →  analytics.StatisticalReport
user.dashboards            →  analytics.Dashboard
user.team_memberships      →  coordination.TeamMembership
user.resource_requests     →  resources.ResourceRequest
user.sent_messages         →  communications.Message
user.presence_records      →  websockets.PresenceRecord
user.device_tokens         →  mobile.DeviceToken
```

No `related_name` collisions exist across all 13 apps.

---

## 13. Seed Data

The `seed_data` management command populates all apps with realistic development records:

```bash
# Seed everything
python manage.py seed_data

# Seed a specific app only
python manage.py seed_data --app surveillance

# Wipe and re-seed
python manage.py seed_data --flush

# Available app targets:
#   core, surveillance, risk, response, coordination,
#   resources, communications, analytics, operations,
#   integrations, triggers_and_quality
```

**Demo users created** (`admin`, `analyst1`, `coordinator1`, `field1`, `analyst2`, `coordinator2`):
all share one password taken from the `SEED_USER_PASSWORD` environment variable. If it is not set, a random
password is generated and printed once at the end of the seed run. Never seed a production database.

**Approximate record counts after full seed:**

| App | Records seeded |
|-----|---------------|
| core — locations | 18 |
| core — notifications | 249 |
| core — audit logs | 30 |
| surveillance — health data | 150 |
| surveillance — anomalies | 25 |
| risk — risk scores | 30 |
| risk — alerts | 25 |
| response — activations | 15 |
| coordination — teams/tasks | 20 / 30 |
| resources — inventory | 30 |
| analytics — reports | 10 |
| integrations — systems/jobs | 5 / 17 |

---

## 14. PDF Report Generation

Statistical reports can be downloaded as PDFs via:

```
GET /api/v1/analytics/reports/{id}/download/
```

If the report has an uploaded `report_file`, that file is served directly. Otherwise, a PDF is generated on the fly from the report's stored data fields using **ReportLab 4.4.9**.

The generated PDF includes:
- Report type badge, title, and metadata table (author, period, status, generation timestamp)
- Blue rule divider matching the OryxShield dark theme palette
- Executive summary (paragraph-split)
- Key findings as a bulleted list
- Results as a key/value table
- Data tables with styled headers and alternating row backgrounds
- OryxShield branding footer

The `Content-Disposition` header on the response carries the filename — the frontend reads this to save with the correct `.pdf` extension.

---

## 15. Health Checks

| Endpoint | Purpose |
|----------|---------|
| `GET /health/` | Simple liveness — returns `{ status: "ok" }` |
| `GET /health/detailed/` | Full system check (DB, Redis, Celery, storage) |
| `GET /health/ready/` | Kubernetes readiness probe |
| `GET /health/live/` | Kubernetes liveness probe |

All health endpoints bypass authentication middleware and are handled before the rest of the middleware stack by `HealthCheckBypassMiddleware`.

---

## 16. Known Fixes Applied

These bugs were found and fixed during active development. Documented here so they are not re-introduced.

| # | Component | Bug | Fix |
|---|-----------|-----|-----|
| 1 | `core/models.py` | `AuditLog.save()` used `if self.pk:` to detect existing rows. UUID primary keys are assigned on instantiation (before `save()`), so `self.pk` is always truthy — every new log creation raised a `ValidationError` | Changed to `if not self._state.adding:` |
| 2 | `core/serializers.py` | `AuditLog.ip_address` and `UserProfile.last_login_ip` are `GenericIPAddressField`. Django 5.2 changed `ip_address_validators` from returning a 2-tuple to a list, breaking DRF's automatic serializer field construction | Declared both as explicit `serializers.CharField(read_only=True, allow_null=True, default=None)` |
| 3 | `integrations/serializers.py` | `APIKeySerializer` had `key_hash` in both `read_only_fields` and `extra_kwargs {'write_only': True}` — DRF raises `AssertionError: May not set both read_only and write_only` | Removed `key_hash` from `read_only_fields`; kept only in `extra_kwargs` |
| 4 | `integrations/serializers.py` | `APIKey.last_used_ip` is `GenericIPAddressField` — same Django 5.2 DRF incompatibility as fix 2 | Declared as explicit `serializers.CharField` |
| 5 | `surveillance/views.py` | `HealthDataViewSet` used both `TimeBasedPagination` (a `CursorPagination` subclass with fixed ordering) and `filters.OrderingFilter`. When no explicit `?ordering=` param was passed, DRF raised `AssertionError: CursorPagination returned None ordering` | Removed `filters.OrderingFilter` from `HealthDataViewSet.filter_backends` |
| 6 | `communications/views.py` | `MessageTemplate` queryset used `.select_related('created_by')` but the model has no `created_by` FK — Django raised `FieldError: Invalid field name(s) given in select_related: 'created_by'` | Removed `.select_related('created_by')` |
| 7 | `websockets/0002` | Six `ChannelGroup` rows required by consumers were missing — presence tracking silently returned zero | Added data migration to seed them; also available via `python manage.py seed_channel_groups` |
| 8 | `core/models.py` | `Notification` model was missing a `read_at` field — `NotificationConsumer._mark_read()` raised `FieldError` | Added `read_at = DateTimeField(null=True, blank=True)` + migration |
| 9 | `analytics/views.py` | `StatisticalReport.download` returned 404 when no `report_file` was attached — seeded reports have no uploaded files | Now generates a styled PDF from the report's data fields using ReportLab |
| 10 | `core/management/commands/seed_data.py` | `IntegrationJob` seeder used wrong field names (`records_created`, `records_failed`, etc.) | Updated to correct model fields: `total_records`, `processed_records`, `successful_records`, `failed_records`, `error_log`, `job_id` |
