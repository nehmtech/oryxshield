# OryxShield — Frontend

Pandemic surveillance and response infrastructure for public health authorities.
Built with React 18 + Vite. This document is the single source of truth for frontend development.

**Company:** NEHMTECH INNOVATIONS LIMITED · **Author:** Nehemiah

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Getting Started](#3-getting-started)
4. [Environment Variables](#4-environment-variables)
5. [Project Structure](#5-project-structure)
6. [Design System](#6-design-system)
7. [Routing Architecture](#7-routing-architecture)
8. [Auth & Role System](#8-auth--role-system)
9. [API Layer](#9-api-layer)
10. [Context Providers](#10-context-providers)
11. [WebSocket Hooks](#11-websocket-hooks)
12. [Component Patterns](#12-component-patterns)
13. [Page Inventory](#13-page-inventory)
14. [Known Fixes Applied](#14-known-fixes-applied)
15. [Contributing](#15-contributing)

---

## 1. Project Overview

OryxShield is a multi-role web application used by public health authorities to:

- Monitor disease surveillance data in real time
- Score and track outbreak risk across geographic clusters
- Coordinate multi-agency response activations
- Manage field operations (cases, contacts, quarantine, vaccination)
- Communicate via SMS, email, push, and social channels
- Analyse epidemiological trends and download styled PDF reports

The frontend is a single-page React application that connects to a Django REST Framework backend via a versioned JSON API (`/api/v1/`) and a set of WebSocket consumers for live data streams.

Public pages (Home, About, Contact, Privacy Policy, Terms of Service) are fully accessible without authentication.

---

## 2. Tech Stack

| Layer | Library / Tool | Version |
|-------|---------------|---------|
| Framework | React | 18 |
| Build tool | Vite | 5 |
| Routing | React Router | v6 |
| HTTP client | Axios | latest |
| Date formatting | date-fns | latest |
| Animation | Framer Motion | latest |
| Charts | Recharts | latest |
| Styling | Inline styles only (no CSS modules, no Tailwind) | — |
| State management | React Context (no Redux, no Zustand) | — |

There are **no external UI component libraries** (no MUI, no Shadcn, no Ant Design). Every component is hand-rolled against the design system documented in Section 6.

---

## 3. Getting Started

### Prerequisites

- Node.js 18+
- The Django backend running locally (see backend README) or a staging API URL

### Install and run

```bash
cd frontend
npm install
npm run dev        # Vite dev server at http://localhost:5173
npm run build      # Production build → dist/
npm run preview    # Preview production build locally
npm run lint       # ESLint
```

---

## 4. Environment Variables

Create a `.env` file in `frontend/`. All variables must be prefixed with `VITE_`.

```env
# Base URL for all REST API calls (no trailing slash)
VITE_API_URL=http://localhost:8000/api/v1

# Base URL for WebSocket connections
VITE_WS_URL=ws://localhost:8000/ws
```

**Defaults used when variables are absent:**

| Variable | Default |
|----------|---------|
| `VITE_API_URL` | `http://localhost:8000/api/v1` |
| `VITE_WS_URL` | `ws://localhost:8000/ws` |

Never commit `.env` with real credentials.

---

## 5. Project Structure

```
src/
│
├── components/
│   ├── common/
│   │   ├── PrivateRoute.jsx         # Redirects unauthenticated users to /login
│   │   └── RoleRoute.jsx            # Renders 403 for insufficient role
│   └── layout/
│       ├── Layout.jsx               # Authenticated shell (Sidebar + Topbar + Outlet)
│       ├── Sidebar.jsx              # Navigation sidebar with role-filtered items and badge counts
│       ├── Topbar.jsx               # Page title, notification bell, user badge, WS status dot
│       └── PublicLayout.jsx         # Public shell (sticky header + footer + Outlet)
│
├── context/
│   ├── AuthContext.jsx              # Auth state, login/logout, 2FA, role helpers
│   ├── UIContext.jsx                # Sidebar state, mobile/tablet detection, notification count
│   └── ToastContext.jsx             # Global toast notification system
│
├── hooks/
│   └── ws/
│       ├── useAlertStream.js        # WS → /ws/alerts/
│       ├── useDashboardStream.js    # WS → /ws/dashboard/
│       └── useResponseStream.js    # WS → /ws/response/
│
├── pages/
│   ├── public/                      # No auth required (served by PublicLayout)
│   │   ├── Home.jsx                 # Landing page — fetches published announcements
│   │   ├── About.jsx
│   │   ├── Contact.jsx              # POSTs to /communications/feedback/
│   │   ├── PrivacyPolicy.jsx
│   │   ├── TermsOfService.jsx
│   │   └── NotFound.jsx
│   │
│   ├── auth/
│   │   ├── Login.jsx                # Inside PublicLayout — handles full 2FA flow
│   │   └── ResetPassword.jsx        # Password reset (request + confirm)
│   │
│   ├── dashboard/       Dashboard.jsx
│   ├── alerts/          Alerts.jsx
│   ├── notifications/   Notifications.jsx      # Full notification centre
│   ├── surveillance/    Surveillance.jsx · SurveillanceDetail.jsx
│   ├── risk/            Risk.jsx · RiskAlerts.jsx
│   ├── response/        Response.jsx · ResponseDetail.jsx
│   ├── coordination/    Coordination.jsx · CoordinationDetail.jsx
│   ├── resources/       Resources.jsx · ResourceDetail.jsx
│   ├── communications/  Communications.jsx · CommunicationDetail.jsx · Compose.jsx
│   ├── analytics/       Analytics.jsx · AnalyticsDetail.jsx · AnalyticsReports.jsx
│   ├── operations/      Operations.jsx · OperationsDetail.jsx
│   ├── integrations/    Integrations.jsx (admin only — tabbed hub)
│   ├── admin/           AdminUsers.jsx · AdminSettings.jsx · AuditLogs.jsx · Locations.jsx
│   └── profile/         Profile.jsx
│
├── services/
│   └── api.js                       # All Axios calls, token management, extractError
│
├── App.jsx                          # Route tree + ScrollToTop
└── main.jsx                         # Entry — ReactDOM, BrowserRouter, context providers
```

### Naming conventions

| Thing | Convention | Example |
|-------|-----------|---------|
| Pages | PascalCase, domain-named | `SurveillanceDetail.jsx` |
| Components | PascalCase | `PublicLayout.jsx` |
| Context files | `<Name>Context.jsx` | `AuthContext.jsx` |
| WS hooks | `use<Domain>Stream.js` | `useAlertStream.js` |
| API file | single file | `api.js` |

---

## 6. Design System

**All styling is done with inline styles only.** No CSS modules, no Tailwind, no styled-components. This is a hard project constraint — do not introduce external styling libraries.

### Colour tokens

```js
const C = {
  bg:          '#0a0f1e',   // page background
  surface:     '#111827',   // card / table background
  surfaceHigh: '#151e2e',   // elevated surface (inputs, hover highlight)
  border:      '#1f2937',   // all borders
  accent:      '#3b82f6',   // primary blue — buttons, active states, links
  danger:      '#ef4444',   // destructive actions, error states, critical alerts
  warning:     '#f59e0b',   // warnings, moderate severity
  success:     '#10b981',   // success states, active/online indicators
  text:        '#f9fafb',   // primary text
  textSub:     '#9ca3af',   // secondary / muted text
  textMuted:   '#6b7280',   // metadata, timestamps
}
```

Copy this object verbatim at the top of every page or component file. Do not deviate from these values.

### Typography

| Role | Font | Size | Weight | Notes |
|------|------|------|--------|-------|
| Page headings, section titles | Bebas Neue | 22–48px | 400 | `letterSpacing: '0.04–0.06em'` |
| Eyebrow labels, badges, table headers | Space Mono | 8–10px | 400 | `letterSpacing: '0.12–0.18em'`, `textTransform: 'uppercase'` |
| Body text, descriptions, form labels | IBM Plex Sans | 12–16px | 400/500/600 | `lineHeight: 1.5–1.85` |

Fonts are loaded via Google Fonts in `index.html`:

```html
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Sans:wght@400;500;600&family=Space+Mono&display=swap" rel="stylesheet">
```

### Spacing & layout

- Max content width: `900–1160px`, centred with `margin: '0 auto'`
- Page padding: `padding: '24px 20px'` (most pages)
- Card surface: `background: C.surface`, `border: \`1px solid ${C.border}\``, `borderRadius: 8`

### Background grid (applied in `Layout.jsx`)

```js
background: `
  linear-gradient(rgba(59,130,246,0.018) 1px, transparent 1px),
  linear-gradient(90deg, rgba(59,130,246,0.018) 1px, transparent 1px),
  #0a0f1e
`,
backgroundSize: '48px 48px',
```

### Shimmer skeleton (loading states)

```jsx
<div style={{
  width, height, borderRadius: 3,
  background: `linear-gradient(90deg, #111827 25%, #151e2e 50%, #111827 75%)`,
  backgroundSize: '200% 100%',
  animation: 'shimmer 1.5s infinite',
}} />
// <style>{`@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }`}</style>
```

Every page that fetches data must show a shimmer skeleton — never a blank screen.

### Hover state pattern

No `:hover` CSS. Use `onMouseEnter` / `onMouseLeave` with local state:

```jsx
const [hov, setHov] = useState(false)

<button
  onMouseEnter={() => setHov(true)}
  onMouseLeave={() => setHov(false)}
  style={{ background: hov ? '#2563eb' : C.accent }}
>...</button>
```

### Never nest `<button>` inside `<button>`

The browser moves inner buttons outside the outer button in the DOM, breaking click handlers. Use `<span role="button" tabIndex={0} onKeyDown={...}>` for secondary interactive elements inside a button.

---

## 7. Routing Architecture

```
BrowserRouter (main.jsx)
└── App.jsx
    ├── ScrollToTop                           # resets scroll on every pathname change
    │
    ├── <Route element={<PublicLayout />}>    # NO auth gate
    │   ├── /                 → Home
    │   ├── /about            → About
    │   ├── /contact          → Contact
    │   ├── /privacy          → PrivacyPolicy
    │   ├── /terms            → TermsOfService
    │   ├── /login            → Login
    │   ├── /reset-password   → ResetPassword
    │   └── *                 → NotFound
    │
    ├── Convenience redirects (no auth gate)
    │   ├── /notifications   → /dashboard/notifications
    │   ├── /alerts          → /dashboard/alerts
    │   └── /profile         → /dashboard/profile  (etc.)
    │
    └── <Route path="/dashboard" element={<PrivateRoute />}>
        └── <Route element={<Layout />}>
            ├── index                  → Dashboard
            ├── alerts                 → Alerts
            ├── notifications          → Notifications
            ├── surveillance           → Surveillance
            ├── surveillance/:id       → SurveillanceDetail
            ├── risk                   → Risk
            ├── risk/alerts            → RiskAlerts
            ├── response               → Response
            ├── response/:id           → ResponseDetail
            ├── coordination           → Coordination
            ├── coordination/:id       → CoordinationDetail
            ├── resources              → Resources
            ├── resources/:id          → ResourceDetail
            ├── communications         → Communications
            ├── communications/compose → Compose
            ├── communications/:id     → CommunicationDetail
            ├── analytics              → Analytics
            ├── analytics/reports      → AnalyticsReports
            ├── analytics/:id          → AnalyticsDetail
            ├── operations             → Operations
            ├── operations/:id         → OperationsDetail
            ├── integrations           → Integrations (admin only)
            ├── admin/users            → AdminUsers
            ├── admin/settings         → AdminSettings
            ├── admin/audit-logs       → AuditLogs
            ├── admin/locations        → Locations
            └── profile                → Profile
```

### Key routing rules

**`RoleRoute` is a wrapper component, not a layout route.** Always pass the page as `children`:

```jsx
// Correct
<Route path="/dashboard/analytics" element={
  <RoleRoute roles={['admin', 'analyst']}>
    <Analytics />
  </RoleRoute>
} />
```

**Public routes are inside `<PublicLayout />`**, which has no auth check. The Axios 401 interceptor only redirects to `/login` when the current path starts with `/dashboard` — public pages are never redirected even if the API returns 401.

**All protected pages are lazy-loaded** and wrapped in a top-level `<Suspense>` in `main.jsx`. `Login` and `ResetPassword` are also lazy despite being in `PublicLayout`, since `PublicLayout` itself is always eager.

---

## 8. Auth & Role System

### AuthContext API

Provided by `src/context/AuthContext.jsx`. Consume with `useAuth()`.

```js
const {
  user,                    // User object or null
  loading,                 // true while initial auth check is in progress
  login(email, password),  // returns { success, requires2fa, sessionToken, method }
  logout(),
  verify2fa(code, sessionToken),
  resend2fa(sessionToken),
  fetchMe(),               // re-fetches current user from /auth/me/
  hasRole(roles[]),        // true if user.role is in the provided array
  isAdmin(),
  isAnalyst(),
  isCoordinator(),
  isFieldOfficer(),
} = useAuth()
```

### Login flow

```
login(email, password)
  ├── success, no 2FA  → sets user in context → caller navigates to /dashboard
  └── requires_2fa: true
        ├── method: 'totp' | 'sms' | 'email'
        └── caller shows code input → verify2fa(code, sessionToken) → sets user
```

### Roles

| Role | Value | Default access |
|------|-------|---------------|
| Administrator | `admin` | Full access to all routes |
| Analyst | `analyst` | Surveillance, risk, analytics |
| Coordinator | `coordinator` | Response, coordination, resources, communications |
| Field Officer | `field_officer` | Response detail, operations |
| Public | `public` | Dashboard only |

`RoleRoute` renders a 403 screen (without redirecting) when the user's role is not in the allowed list. The user stays logged in and can navigate elsewhere.

### Token storage

Tokens are stored in `localStorage` under `ls_access` and `ls_refresh`. The Axios instance attaches the access token to every request and silently refreshes on 401 using a request queue to prevent race conditions. On refresh failure, all queued requests are rejected and the user is redirected to `/login`.

---

## 9. API Layer

All HTTP calls go through `src/services/api.js`. Do not call Axios or `fetch` directly from components — always use the exported API objects.

### Exports

```js
export const authApi           = { ... }   // login, logout, 2FA, me, password change
export const coreApi           = { ... }   // users, profiles, notifications, audit logs, config, API keys, locations
export const surveillanceApi   = { ... }
export const riskApi           = { ... }
export const responseApi       = { ... }
export const coordinationApi   = { ... }
export const resourcesApi      = { ... }
export const communicationsApi = { ... }
export const analyticsApi      = { ... }
export const operationsApi     = { ... }
export const integrationsApi   = { ... }
export const wsManagementApi   = { ... }
export const mobileApi         = { ... }

export const tokenStorage      = { get, set, clear }
export const extractError      = (err) => string   // any Axios error → display string
```

### extractError

Handles all DRF error shapes:

```js
import { extractError } from '../../services/api'

try {
  await someApi.doThing()
} catch (err) {
  toast.error(extractError(err))
}
// Handles: { detail }, { message }, { field: ['msg'] }, { non_field_errors }, network errors
```

### 401 interceptor behaviour

The interceptor only redirects to `/login` when the current path starts with `/dashboard`. Public pages never get redirected even if the API returns 401 (e.g. when `AuthContext.fetchMe()` runs on mount with no stored token).

### Pagination pattern

```js
const res = await someApi.list({ page: 1, page_size: 20 })
const items = res.data.results   // array
const total = res.data.count     // integer
```

### Public endpoints (no auth)

```js
// Published announcements — displayed on Home page
communicationsApi.publishedAnnouncements({ page_size: 3 })

// Public contact/feedback form — Contact page
communicationsApi.submitFeedback({ feedback_type, sender_name, sender_contact, subject, message })
```

### Report download

```js
// Downloads report as PDF (generated server-side with ReportLab)
analyticsApi.downloadStatReport(id)   // responseType: 'blob'
// Frontend reads Content-Disposition header to extract filename
```

---

## 10. Context Providers

Providers are composed in `main.jsx`. Order matters — `AuthContext` must wrap everything else.

```jsx
<BrowserRouter>
  <AuthProvider>
    <UIProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </UIProvider>
  </AuthProvider>
</BrowserRouter>
```

### AuthContext

See Section 8. Stores user state, handles login/logout/2FA, exposes role helpers.

### UIContext

```js
const {
  sidebarCollapsed, toggleSidebar,
  notifCount, setNotifCount,          // unread notification badge count (kept in sync by Topbar)
  isMobile,                           // true when viewport < 768px
  isTablet,                           // true when 768px ≤ viewport < 1024px
  wsStatus,                           // 'connecting' | 'open' | 'error' | 'closed'
} = useUI()
```

### ToastContext

```js
const toast = useToast()
toast.success('Saved.')
toast.error('Something went wrong.')
toast.warning('Session expiring soon.')
toast.info('3 new alerts.')
```

---

## 11. WebSocket Hooks

All hooks live in `src/hooks/ws/` and follow the same contract:

```js
const { data, status } = useAlertStream()
// status: 'connecting' | 'open' | 'error' | 'closed'
```

All hooks implement exponential backoff reconnection with a 30-second cap. The connection URL is built from `VITE_WS_URL` with `?token=<access_token>` for JWT auth.

| Hook | Endpoint | Data shape |
|------|----------|-----------|
| `useAlertStream` | `/ws/alerts/` | Array of last 200 alert messages |
| `useDashboardStream` | `/ws/dashboard/` | Single merged stats object |
| `useResponseStream` | `/ws/response/` | Array of activations (upserted by `id`, max 100) |

The `wsStatus` from `useDashboardStream` is stored in `UIContext` so the Topbar status dot stays current without drilling props.

---

## 12. Component Patterns

### Page skeleton

```jsx
export default function MyPage() {
  const [items,   setItems]   = useState([])
  const [loading, setLoading] = useState(true)
  const { error: toastError } = useToast()

  useEffect(() => {
    ;(async () => {
      try {
        const res = await someApi.list()
        setItems(res.data.results)
      } catch (err) {
        toastError(extractError(err))
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  return (
    <div style={{ minHeight: '100vh', background: '#0a0f1e', padding: '24px 20px' }}>
      <style>{`
        @keyframes mp-shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
      `}</style>

      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        <h1 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 28, color: '#f9fafb', margin: '0 0 20px' }}>
          Page Title
        </h1>

        {loading ? <ShimmerSkeleton /> : <DataList items={items} />}
      </div>
    </div>
  )
}
```

**Prefix all `@keyframes` names** with a 2–3 letter page abbreviation (e.g. `mp-shimmer`, `sr-fadeUp`) to avoid collisions when multiple components are mounted simultaneously.

### Tables

```js
// Header cell
{ fontFamily: "'Space Mono', monospace", fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#6b7280' }

// Row hover
onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
onMouseLeave={e => e.currentTarget.style.background = 'transparent'}

// Row border
{ borderBottom: `1px solid #1f2937` }
```

### Topbar — notification dropdown

The notification bell polls `/notifications/unread_count/` every 60 seconds. Clicking the bell fetches unread notifications and caches them until a notification is marked read.

Clicking a notification item:
1. Calls `markRead(n.id)`
2. Navigates to `n.action_url` if set, otherwise to `/dashboard/notifications`
3. Closes the dropdown

The `×` dismiss button inside each notification item is a `<span role="button">`, not a `<button>`, to avoid invalid HTML nesting.

---

## 13. Page Inventory

### Public pages

| Route | Component | Notes |
|-------|-----------|-------|
| `/` | `Home.jsx` | Fetches published announcements; silently suppresses errors |
| `/about` | `About.jsx` | Static |
| `/contact` | `Contact.jsx` | POSTs to `/communications/feedback/` |
| `/privacy` | `PrivacyPolicy.jsx` | Static |
| `/terms` | `TermsOfService.jsx` | Static |
| `/login` | `Login.jsx` | Full 2FA flow (TOTP / SMS / email) |
| `/reset-password` | `ResetPassword.jsx` | Request reset link |
| `/reset-password/confirm` | `ResetPassword.jsx` | Confirm with token + new password |
| `*` | `NotFound.jsx` | 404 within PublicLayout |

### Authenticated pages

| Route | Component | Roles |
|-------|-----------|-------|
| `/dashboard` | `Dashboard.jsx` | All |
| `/dashboard/alerts` | `Alerts.jsx` | admin, analyst, coordinator |
| `/dashboard/notifications` | `Notifications.jsx` | admin, analyst, coordinator, field_officer |
| `/dashboard/surveillance` | `Surveillance.jsx` | admin, analyst |
| `/dashboard/surveillance/:id` | `SurveillanceDetail.jsx` | admin, analyst |
| `/dashboard/risk` | `Risk.jsx` | admin, analyst |
| `/dashboard/risk/alerts` | `RiskAlerts.jsx` | admin, analyst |
| `/dashboard/response` | `Response.jsx` | admin, coordinator |
| `/dashboard/response/:id` | `ResponseDetail.jsx` | admin, coordinator, field_officer |
| `/dashboard/coordination` | `Coordination.jsx` | admin, coordinator |
| `/dashboard/coordination/:id` | `CoordinationDetail.jsx` | admin, coordinator |
| `/dashboard/resources` | `Resources.jsx` | admin, coordinator |
| `/dashboard/resources/:id` | `ResourceDetail.jsx` | admin, coordinator |
| `/dashboard/communications` | `Communications.jsx` | admin, coordinator |
| `/dashboard/communications/compose` | `Compose.jsx` | admin, coordinator |
| `/dashboard/communications/:id` | `CommunicationDetail.jsx` | admin, coordinator |
| `/dashboard/analytics` | `Analytics.jsx` | admin, analyst |
| `/dashboard/analytics/reports` | `AnalyticsReports.jsx` | admin, analyst |
| `/dashboard/analytics/:id` | `AnalyticsDetail.jsx` | admin, analyst |
| `/dashboard/operations` | `Operations.jsx` | admin, coordinator, field_officer |
| `/dashboard/operations/:id` | `OperationsDetail.jsx` | admin, coordinator, field_officer |
| `/dashboard/integrations` | `Integrations.jsx` | admin |
| `/dashboard/admin/users` | `AdminUsers.jsx` | admin |
| `/dashboard/admin/settings` | `AdminSettings.jsx` | admin |
| `/dashboard/admin/audit-logs` | `AuditLogs.jsx` | admin |
| `/dashboard/admin/locations` | `Locations.jsx` | admin |
| `/dashboard/profile` | `Profile.jsx` | admin, analyst, coordinator, field_officer |

---

## 14. Known Fixes Applied

| # | Component | Bug | Fix |
|---|-----------|-----|-----|
| 1 | `services/api.js` | Axios 401 interceptor called `window.location.href = '/login'` unconditionally. `AuthContext.fetchMe()` runs on mount for all pages (including public ones) and triggers a 401 when no token is stored — this redirected public pages to `/login` | Added `redirectToLogin()` helper that only redirects when `window.location.pathname.startsWith('/dashboard')` |
| 2 | `components/layout/Topbar.jsx` | Notification items used `n.link` for navigation but the model field is `action_url` — clicks did nothing | Changed to `n.action_url \|\| '/dashboard/notifications'` |
| 3 | `components/layout/Topbar.jsx` | Notification items rendered `<button>` nested inside `<button>` — invalid HTML; browsers restructure the DOM and click handlers break | Replaced inner `<button>×</button>` with `<span role="button" tabIndex={0} onKeyDown={...}>×</span>` |
| 4 | `components/layout/Topbar.jsx` | "View all alerts →" footer linked to `/dashboard/alerts` (health alerts) instead of the notifications page | Changed target to `/dashboard/notifications` |
| 5 | `pages/analytics/AnalyticsReports.jsx` | `handleDownload` hardcoded `.pdf` extension and did not read the `Content-Disposition` header — broke when the server returned a different format | Now reads `Content-Disposition` header from response to extract the actual filename; falls back to `<title>.pdf` |

---

## 15. Contributing

### Branch strategy

```
main           ← production-ready code only
develop        ← integration branch — all PRs merge here
feature/<name> ← individual feature branches
fix/<name>     ← bug fix branches
```

### Before opening a PR

- All pages must follow the page skeleton in Section 12
- All colour values must use the token object — no hardcoded hex in the middle of JSX
- No new npm packages without team agreement — the dependency list is intentionally minimal
- Prefix all `@keyframes` names with a component abbreviation
- No `console.log` left in committed code
- Never nest `<button>` inside `<button>` — use `<span role="button">` for secondary interactive elements

### Adding a new page

1. Create the file at `src/pages/<domain>/<Component>.jsx`
2. Add a `lazy()` import in `App.jsx`
3. Add the route inside the correct route tree (`PublicLayout` or `PrivateRoute + Layout`)
4. If protected, wrap with `<RoleRoute roles={[...]}><Component /></RoleRoute>`
5. Update the Page Inventory table in this README

### Adding a new API method

1. Add the method to the correct named export in `src/services/api.js`
2. Add a comment if the payload shape or auth requirement is non-obvious
3. If the endpoint is public (no auth), note it explicitly

---

*Last updated: 2026-05-28 · OryxShield Frontend · NEHMTECH INNOVATIONS LIMITED*
