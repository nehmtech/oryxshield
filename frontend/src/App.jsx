import { lazy, useEffect } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Layout from './components/layout/Layout'
import PublicLayout from './components/layout/PublicLayout'
import PrivateRoute from './components/common/PrivateRoute'
import RoleRoute from './components/common/RoleRoute'
import Login from './pages/auth/Login'
import ResetPassword from './pages/auth/ResetPassword'

// ─── Public pages ─────────────────────────────────────────────────────────────
const Home           = lazy(() => import('./pages/public/Home'))
const About          = lazy(() => import('./pages/public/About'))
const Contact        = lazy(() => import('./pages/public/Contact'))
const PrivacyPolicy  = lazy(() => import('./pages/public/PrivacyPolicy'))
const TermsOfService = lazy(() => import('./pages/public/TermsOfService'))
const NotFound       = lazy(() => import('./pages/public/NotFound'))

// ─── Phase 2 ──────────────────────────────────────────────────────────────────
const Dashboard = lazy(() => import('./pages/dashboard/Dashboard'))
const Alerts    = lazy(() => import('./pages/alerts/Alerts'))

// ─── Phase 3 ──────────────────────────────────────────────────────────────────
const Surveillance     = lazy(() => import('./pages/surveillance/Surveillance'))
const SurveillanceById = lazy(() => import('./pages/surveillance/SurveillanceDetail'))

// ─── Phase 4 ──────────────────────────────────────────────────────────────────
const Risk       = lazy(() => import('./pages/risk/Risk'))
const RiskAlerts = lazy(() => import('./pages/risk/RiskAlerts'))

// ─── Phase 5 ──────────────────────────────────────────────────────────────────
const Response       = lazy(() => import('./pages/response/Response'))
const ResponseDetail = lazy(() => import('./pages/response/ResponseDetail'))

// ─── Phase 6 ──────────────────────────────────────────────────────────────────
const Coordination       = lazy(() => import('./pages/coordination/Coordination'))
const CoordinationDetail = lazy(() => import('./pages/coordination/CoordinationDetail'))

// ─── Phase 7 ──────────────────────────────────────────────────────────────────
const Resources      = lazy(() => import('./pages/resources/Resources'))
const ResourceDetail = lazy(() => import('./pages/resources/ResourceDetail'))

// ─── Phase 8 — Communications ────────────────────────────────────────────────
const Communications      = lazy(() => import('./pages/communications/Communications'))
const CommunicationDetail = lazy(() => import('./pages/communications/CommunicationDetail'))
const Compose             = lazy(() => import('./pages/communications/Compose'))

// ─── Phase 9 — Analytics ─────────────────────────────────────────────────────
const Analytics        = lazy(() => import('./pages/analytics/Analytics'))
const AnalyticsDetail  = lazy(() => import('./pages/analytics/AnalyticsDetail'))
const AnalyticsReports = lazy(() => import('./pages/analytics/AnalyticsReports'))

// ─── Phase 10 — Operations ───────────────────────────────────────────────────
const Operations       = lazy(() => import('./pages/operations/Operations'))
const OperationsDetail = lazy(() => import('./pages/operations/OperationsDetail'))

// ─── Phase 11 — Admin ────────────────────────────────────────────────────────
const AdminUsers    = lazy(() => import('./pages/admin/AdminUsers'))
const AdminSettings = lazy(() => import('./pages/admin/AdminSettings'))
const AuditLogs     = lazy(() => import('./pages/admin/AuditLogs'))
const Locations     = lazy(() => import('./pages/admin/Locations'))

// ─── Phase 12 — Profile ──────────────────────────────────────────────────────
const Profile = lazy(() => import('./pages/profile/Profile'))

// ─── Notifications ───────────────────────────────────────────────────────────
const Notifications = lazy(() => import('./pages/notifications/Notifications'))

// ─── Integrations hub (admin-only) ───────────────────────────────────────────
const Integrations = lazy(() => import('./pages/integrations/Integrations'))

// ─── Scroll to top on every route change ─────────────────────────────────────
function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
  }, [pathname])
  return null
}

// ─── App ──────────────────────────────────────────────────────────────────────
// Route structure:
//   Public  — / /about /contact /privacy /terms /login  (PublicLayout)
//   Private — /dashboard and all sub-routes             (PrivateRoute + Layout)
//
// All protected URLs are prefixed with /dashboard so there is a clean
// separation between public pages and the operations platform.
// The sidebar nav links match these paths.
//
// Short aliases for convenience:
//   /alerts → redirect to /dashboard/alerts  (so mobile nav links still work)

export default function App() {
  return (
    <>
      <ScrollToTop />
      <Routes>

        {/* ── Public routes — PublicLayout (header + footer) ── */}
        <Route element={<PublicLayout />}>
          <Route path="/"        element={<Home />} />
          <Route path="/about"   element={<About />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/privacy" element={<PrivacyPolicy />} />
          <Route path="/terms"   element={<TermsOfService />} />
          {/* Login — handles its own redirect if already authenticated */}
          <Route path="/login"                    element={<Login />} />
          {/* Password reset — public pages */}
          <Route path="/reset-password"           element={<ResetPassword />} />
          <Route path="/reset-password/confirm"   element={<ResetPassword confirm />} />
          <Route path="*"        element={<NotFound />} />
        </Route>

        {/* ── Convenience redirects for top-level short paths ─────────────── */}
        {/* These allow bookmarks / mobile nav links without the /dashboard prefix */}
        <Route path="/notifications"   element={<Navigate to="/dashboard/notifications"  replace />} />
        <Route path="/alerts"          element={<Navigate to="/dashboard/alerts"          replace />} />
        <Route path="/surveillance/*"  element={<Navigate to="/dashboard/surveillance"    replace />} />
        <Route path="/risk/*"          element={<Navigate to="/dashboard/risk"            replace />} />
        <Route path="/response/*"      element={<Navigate to="/dashboard/response"        replace />} />
        <Route path="/coordination/*"  element={<Navigate to="/dashboard/coordination"    replace />} />
        <Route path="/resources/*"     element={<Navigate to="/dashboard/resources"       replace />} />
        <Route path="/communications/*"element={<Navigate to="/dashboard/communications"  replace />} />
        <Route path="/analytics/*"     element={<Navigate to="/dashboard/analytics"       replace />} />
        <Route path="/operations/*"    element={<Navigate to="/dashboard/operations"      replace />} />
        <Route path="/integrations"    element={<Navigate to="/dashboard/integrations"    replace />} />
        <Route path="/admin/*"         element={<Navigate to="/dashboard/admin/users"     replace />} />
        <Route path="/profile"         element={<Navigate to="/dashboard/profile"         replace />} />

        {/* ── Protected routes — PrivateRoute gate + sidebar Layout ── */}
        <Route path="/dashboard" element={<PrivateRoute />}>
          <Route element={<Layout />}>

            {/* Index: /dashboard → Dashboard */}
            <Route index element={
              <RoleRoute roles={['admin', 'analyst', 'coordinator', 'field_officer', 'public']}>
                <Dashboard />
              </RoleRoute>
            } />

            <Route path="alerts" element={
              <RoleRoute roles={['admin', 'analyst', 'coordinator']}>
                <Alerts />
              </RoleRoute>
            } />

            {/* ── Surveillance ── */}
            <Route path="surveillance" element={
              <RoleRoute roles={['admin', 'analyst']}>
                <Surveillance />
              </RoleRoute>
            } />
            <Route path="surveillance/:id" element={
              <RoleRoute roles={['admin', 'analyst']}>
                <SurveillanceById />
              </RoleRoute>
            } />

            {/* ── Risk ── */}
            <Route path="risk" element={
              <RoleRoute roles={['admin', 'analyst']}>
                <Risk />
              </RoleRoute>
            } />
            <Route path="risk/alerts" element={
              <RoleRoute roles={['admin', 'analyst']}>
                <RiskAlerts />
              </RoleRoute>
            } />

            {/* ── Response ── */}
            <Route path="response" element={
              <RoleRoute roles={['admin', 'coordinator']}>
                <Response />
              </RoleRoute>
            } />
            <Route path="response/:id" element={
              <RoleRoute roles={['admin', 'coordinator', 'field_officer']}>
                <ResponseDetail />
              </RoleRoute>
            } />

            {/* ── Coordination ── */}
            <Route path="coordination" element={
              <RoleRoute roles={['admin', 'coordinator']}>
                <Coordination />
              </RoleRoute>
            } />
            <Route path="coordination/:id" element={
              <RoleRoute roles={['admin', 'coordinator']}>
                <CoordinationDetail />
              </RoleRoute>
            } />

            {/* ── Resources ── */}
            <Route path="resources" element={
              <RoleRoute roles={['admin', 'coordinator']}>
                <Resources />
              </RoleRoute>
            } />
            <Route path="resources/:id" element={
              <RoleRoute roles={['admin', 'coordinator']}>
                <ResourceDetail />
              </RoleRoute>
            } />

            {/* ── Communications ── */}
            <Route path="communications" element={
              <RoleRoute roles={['admin', 'coordinator']}>
                <Communications />
              </RoleRoute>
            } />
            <Route path="communications/compose" element={
              <RoleRoute roles={['admin', 'coordinator']}>
                <Compose />
              </RoleRoute>
            } />
            <Route path="communications/:id" element={
              <RoleRoute roles={['admin', 'coordinator']}>
                <CommunicationDetail />
              </RoleRoute>
            } />

            {/* ── Analytics ── */}
            <Route path="analytics" element={
              <RoleRoute roles={['admin', 'analyst']}>
                <Analytics />
              </RoleRoute>
            } />
            <Route path="analytics/reports" element={
              <RoleRoute roles={['admin', 'analyst']}>
                <AnalyticsReports />
              </RoleRoute>
            } />
            <Route path="analytics/:id" element={
              <RoleRoute roles={['admin', 'analyst']}>
                <AnalyticsDetail />
              </RoleRoute>
            } />

            {/* ── Operations ── */}
            <Route path="operations" element={
              <RoleRoute roles={['admin', 'coordinator', 'field_officer']}>
                <Operations />
              </RoleRoute>
            } />
            <Route path="operations/:id" element={
              <RoleRoute roles={['admin', 'coordinator', 'field_officer']}>
                <OperationsDetail />
              </RoleRoute>
            } />

            {/* ── Integrations ── */}
            <Route path="integrations" element={
              <RoleRoute roles={['admin']}>
                <Integrations />
              </RoleRoute>
            } />

            {/* ── Notifications ── */}
            <Route path="notifications" element={
              <RoleRoute roles={['admin', 'analyst', 'coordinator', 'field_officer']}>
                <Notifications />
              </RoleRoute>
            } />

            {/* ── Admin ── */}
            <Route path="admin/users" element={
              <RoleRoute roles={['admin']}>
                <AdminUsers />
              </RoleRoute>
            } />
            <Route path="admin/settings" element={
              <RoleRoute roles={['admin']}>
                <AdminSettings />
              </RoleRoute>
            } />
            <Route path="admin/audit-logs" element={
              <RoleRoute roles={['admin']}>
                <AuditLogs />
              </RoleRoute>
            } />
            <Route path="admin/locations" element={
              <RoleRoute roles={['admin']}>
                <Locations />
              </RoleRoute>
            } />

            {/* ── Profile ── */}
            <Route path="profile" element={
              <RoleRoute roles={['admin', 'analyst', 'coordinator', 'field_officer']}>
                <Profile />
              </RoleRoute>
            } />

          </Route>
        </Route>

      </Routes>
    </>
  )
}