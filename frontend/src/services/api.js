/**
 * OryxShield — API Service Layer
 * ========================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Single Axios instance with JWT interceptor + silent refresh queue.
 * Covers ALL 13 Django apps: core, surveillance, risk_assessment, response,
 * coordination, resources, communications, analytics, operations, mobile,
 * integrations, websockets (REST management side).
 *
 * Naming convention: api.<method>(id?, data?, params?)
 *   - GET list  → listX(params)
 *   - GET one   → getX(id)
 *   - POST      → createX(data) or verbX(id, data)
 *   - PATCH     → updateX(id, data)
 *   - DELETE    → deleteX(id)
 *   - Actions   → verbX(id, data?) — e.g. acknowledgeAlert, escalate, admit
 *
 * FIXES applied:
 *   1. BASE_URL now ends with /api/v1  (was /api — caused 404 on every request)
 *   2. authApi.login remaps { email } → { username } to match Django authenticate()
 *   3. authApi.me / updateMe point to /users/me/ (router URL, not /auth/me/)
 *   4. analyticsApi fully corrected (APP 9 section below for full notes)
 */
import axios from 'axios'

// ─────────────────────────────────────────────────────────────────────────────
// Base URL  — MUST match Django's api/v1/ mount point
// ─────────────────────────────────────────────────────────────────────────────
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

// ─────────────────────────────────────────────────────────────────────────────
// Axios Instance
// ─────────────────────────────────────────────────────────────────────────────
const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})

// ─────────────────────────────────────────────────────────────────────────────
// Token Storage
// ─────────────────────────────────────────────────────────────────────────────
export const tokenStorage = {
  getAccess:  ()     => sessionStorage.getItem('os_access'),
  getRefresh: ()     => sessionStorage.getItem('os_refresh'),
  setAccess:  (t)    => sessionStorage.setItem('os_access', t),
  setRefresh: (t)    => sessionStorage.setItem('os_refresh', t),
  setTokens:  (a, r) => { sessionStorage.setItem('os_access', a); sessionStorage.setItem('os_refresh', r) },
  clear:      ()     => { sessionStorage.removeItem('os_access'); sessionStorage.removeItem('os_refresh') },
}

// ─────────────────────────────────────────────────────────────────────────────
// Request Interceptor — attach Bearer token + CSRF token
// ─────────────────────────────────────────────────────────────────────────────
function getCsrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return match ? match[1] : null
}

api.interceptors.request.use(
  (config) => {
    const token = tokenStorage.getAccess()
    if (token) config.headers.Authorization = `Bearer ${token}`

    // Attach CSRF token for mutating requests (Django's CsrfViewMiddleware)
    if (!['get', 'head', 'options'].includes((config.method || '').toLowerCase())) {
      const csrf = getCsrfToken()
      if (csrf) config.headers['X-CSRFToken'] = csrf
    }

    return config
  },
  (error) => Promise.reject(error)
)

// ─────────────────────────────────────────────────────────────────────────────
// Response Interceptor — silent 401 refresh with request queue
// ─────────────────────────────────────────────────────────────────────────────
let isRefreshing = false
let failedQueue  = []

const processQueue = (error, token = null) => {
  failedQueue.forEach((p) => { error ? p.reject(error) : p.resolve(token) })
  failedQueue = []
}

// Only redirect to /login when already on a protected (dashboard) route
const redirectToLogin = () => {
  if (window.location.pathname.startsWith('/dashboard')) {
    window.location.href = '/login'
  }
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      const refresh = tokenStorage.getRefresh()
      if (!refresh) {
        tokenStorage.clear()
        redirectToLogin()
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => failedQueue.push({ resolve, reject }))
          .then((token) => { original.headers.Authorization = `Bearer ${token}`; return api(original) })
          .catch((e) => Promise.reject(e))
      }

      original._retry = true
      isRefreshing    = true
      try {
        const res = await axios.post(`${BASE_URL}/auth/token/refresh/`, { refresh })
        const { access } = res.data
        tokenStorage.setAccess(access)
        processQueue(null, access)
        original.headers.Authorization = `Bearer ${access}`
        return api(original)
      } catch (e) {
        processQueue(e, null)
        tokenStorage.clear()
        redirectToLogin()
        return Promise.reject(e)
      } finally {
        isRefreshing = false
      }
    }
    return Promise.reject(error)
  }
)

// ─────────────────────────────────────────────────────────────────────────────
// Error Extractor
// ─────────────────────────────────────────────────────────────────────────────
export const extractError = (err) => {
  if (err.response?.data) {
    const d = err.response.data
    // Custom exception handler wraps errors under d.error.details
    if (d.error?.details) {
      const details = d.error.details
      if (typeof details === 'string')    return details
      if (details.detail)                 return details.detail
      if (details.non_field_errors)       return details.non_field_errors[0]
      const first = Object.keys(details)[0]
      if (first) { const v = details[first]; return `${first}: ${Array.isArray(v) ? v[0] : v}` }
    }
    if (d.error?.message)               return d.error.message
    if (typeof d === 'string')           return d
    if (d.detail)                        return d.detail
    if (d.message)                       return d.message
    if (d.non_field_errors)              return d.non_field_errors[0]
    const first = Object.keys(d)[0]
    if (first) { const v = d[first]; return `${first}: ${Array.isArray(v) ? v[0] : v}` }
  }
  return err.message || 'An unexpected error occurred.'
}

// ─────────────────────────────────────────────────────────────────────────────
// APP 1 — AUTH  (/auth/... and /users/me/)
// ─────────────────────────────────────────────────────────────────────────────
export const authApi = {
  // JWT
  // FIX: Django's authenticate() uses the "username" kwarg — remap email → username
  login:                ({ email, password, ...rest }) =>
                          api.post('/auth/login/', { username: email, password, ...rest }),
  logout:               (data)   => api.post('/auth/logout/', data),
  tokenRefresh:         (data)   => api.post('/auth/token/refresh/', data),
  tokenVerify:          (data)   => api.post('/auth/token/verify/', data),

  // Current user — FIX: lives at /users/me/ (UserViewSet router), not /auth/me/
  me:                   ()       => api.get('/users/me/'),
  updateMe:             (data)   => api.patch('/users/me/', data),

  // Registration
  register:             (data)   => api.post('/auth/register/', data),

  // 2FA (TOTP / SMS / Email)
  setup2fa:             ()       => api.get('/profiles/enable_2fa/'),
  confirm2fa:           (data)   => api.post('/profiles/enable_2fa/', data),
  disable2fa:           (data)   => api.post('/profiles/disable_2fa/', data),
  verify2fa:            (data)   => api.post('/auth/2fa/verify/', data),
  resend2fa:            (data)   => api.post('/auth/2fa/resend/', data),

  // Password
  changePassword:       (data)   => api.post('/auth/change-password/', data),
  resetPasswordRequest: (data)   => api.post('/auth/password/reset/', data),
  resetPasswordConfirm: (data)   => api.post('/auth/password/reset/confirm/', data),

  // API Keys (user-scoped)
  listApiKeys:          (params) => api.get('/api-keys/', { params }),
  createApiKey:         (data)   => api.post('/api-keys/', data),
  getApiKey:            (id)     => api.get(`/api-keys/${id}/`),
  revokeApiKey:         (id)     => api.post(`/api-keys/${id}/revoke/`),
  regenerateApiKey:     (id)     => api.post(`/api-keys/${id}/regenerate/`),
  apiKeyUsageStats:     (id)     => api.get(`/api-keys/${id}/usage_stats/`),

  // Social auth
  socialCallback:       (data)   => api.post('/auth/social/callback/', data),
}

// ─────────────────────────────────────────────────────────────────────────────
// APP 2 — CORE  (/users/, /profiles/, /locations/, /notifications/, etc.)
// ─────────────────────────────────────────────────────────────────────────────
export const coreApi = {
  // Users (admin management)
  listUsers:            (params) => api.get('/users/', { params }),
  getUser:              (id)     => api.get(`/users/${id}/`),
  createUser:           (data)   => api.post('/users/', data),
  updateUser:           (id, d)  => api.patch(`/users/${id}/`, d),
  deleteUser:           (id)     => api.delete(`/users/${id}/`),
  activateUser:         (id)     => api.post(`/users/${id}/activate/`),
  deactivateUser:       (id)     => api.post(`/users/${id}/deactivate/`),
  assignRole:           (id, role) => api.post(`/users/${id}/assign_role/`, { role }),
  userStatistics:       ()       => api.get('/users/statistics/'),

  // User Profiles
  myProfile:            ()       => api.get('/profiles/my_profile/'),
  updateMyProfile:      (data)   => api.patch('/profiles/my_profile/', data),
  uploadAvatar:         (data)   => api.patch('/profiles/my_profile/', data, {
                                      headers: { 'Content-Type': 'multipart/form-data' },
                                    }),

  // Notifications
  listNotifications:    (params) => api.get('/notifications/', { params }),
  getNotification:      (id)     => api.get(`/notifications/${id}/`),
  markNotifRead:        (id)     => api.post(`/notifications/${id}/mark_read/`),
  markAllNotifsRead:    ()       => api.post('/notifications/mark_all_read/'),
  deleteNotification:   (id)     => api.delete(`/notifications/${id}/`),
  unreadCount:          ()       => api.get('/notifications/unread_count/'),
  unreadNotifications:  ()       => api.get('/notifications/unread/'),

  // Audit Logs (read-only, superuser)
  listAuditLogs:        (params) => api.get('/audit-logs/', { params }),
  getAuditLog:          (id)     => api.get(`/audit-logs/${id}/`),
  auditActivitySummary: ()       => api.get('/audit-logs/activity_summary/'),
  exportAuditLogs:      ()       => api.get('/audit-logs/export_csv/', { responseType: 'blob' }),

  // System Configuration (admin)
  listConfigurations:   (params) => api.get('/configurations/', { params }),
  getConfiguration:     (id)     => api.get(`/configurations/${id}/`),
  createConfiguration:  (data)   => api.post('/configurations/', data),
  updateConfiguration:  (id, d)  => api.patch(`/configurations/${id}/`, d),
  deleteConfiguration:  (id)     => api.delete(`/configurations/${id}/`),
  configByCategory:     ()       => api.get('/configurations/by_category/'),
  toggleConfigActive:   (id)     => api.post(`/configurations/${id}/toggle_active/`),

  // Locations (reference data)
  listLocations:        (params) => api.get('/locations/', { params }),
  getLocation:          (id)     => api.get(`/locations/${id}/`),
  createLocation:       (data)   => api.post('/locations/', data),
  updateLocation:       (id, d)  => api.patch(`/locations/${id}/`, d),
  deleteLocation:       (id)     => api.delete(`/locations/${id}/`),
  locationTree:         ()       => api.get('/locations/tree/'),
  locationChildren:     (id)     => api.get(`/locations/${id}/children/`),
  locationAncestors:    (id)     => api.get(`/locations/${id}/ancestors/`),
  locationDescendants:  (id)     => api.get(`/locations/${id}/descendants/`),
  nearbyLocations:      (params) => api.get('/locations/nearby/', { params }),

  // Health
  healthCheck:          ()       => api.get('/health/'),
  healthDetailed:       ()       => api.get('/health/detailed/'),
  systemStatus:         ()       => api.get('/system/status/'),
}

// ─────────────────────────────────────────────────────────────────────────────
// APP 3 — SURVEILLANCE  (/surveillance/...)
// ─────────────────────────────────────────────────────────────────────────────
export const surveillanceApi = {
  // Data Sources
  listDataSources:         (params) => api.get('/surveillance/data-sources/', { params }),
  getDataSource:           (id)     => api.get(`/surveillance/data-sources/${id}/`),
  createDataSource:        (data)   => api.post('/surveillance/data-sources/', data),
  updateDataSource:        (id, d)  => api.patch(`/surveillance/data-sources/${id}/`, d),
  deleteDataSource:        (id)     => api.delete(`/surveillance/data-sources/${id}/`),
  testDataSource:          (id)     => api.post(`/surveillance/data-sources/${id}/test/`),
  syncDataSource:          (id)     => api.post(`/surveillance/data-sources/${id}/sync/`),

  // Health Data
  listHealthData:          (params) => api.get('/surveillance/health-data/', { params }),
  getHealthData:           (id)     => api.get(`/surveillance/health-data/${id}/`),
  createHealthData:        (data)   => api.post('/surveillance/health-data/', data),
  updateHealthData:        (id, d)  => api.patch(`/surveillance/health-data/${id}/`, d),
  deleteHealthData:        (id)     => api.delete(`/surveillance/health-data/${id}/`),
  bulkImportHealthData:    (data)   => api.post('/surveillance/health-data/bulk_upload/', data),

  // Disease Profiles
  listDiseaseProfiles:     (params) => api.get('/surveillance/disease-profiles/', { params }),
  getDiseaseProfile:       (id)     => api.get(`/surveillance/disease-profiles/${id}/`),
  createDiseaseProfile:    (data)   => api.post('/surveillance/disease-profiles/', data),
  updateDiseaseProfile:    (id, d)  => api.patch(`/surveillance/disease-profiles/${id}/`, d),
  deleteDiseaseProfile:    (id)     => api.delete(`/surveillance/disease-profiles/${id}/`),
  diseaseStats:            (id)     => api.get(`/surveillance/disease-profiles/${id}/stats/`),

  // Anomaly Detection
  listAnomalies:           (params) => api.get('/surveillance/anomalies/', { params }),
  getAnomaly:              (id)     => api.get(`/surveillance/anomalies/${id}/`),
  confirmAnomaly:          (id)     => api.post(`/surveillance/anomalies/${id}/verify/`, { is_verified: true, is_false_positive: false, notes: 'Confirmed via UI' }),
  dismissAnomaly:          (id, d)  => api.post(`/surveillance/anomalies/${id}/verify/`, { is_verified: true, is_false_positive: true, notes: d?.notes || 'Dismissed via UI' }),
  runAnomalyDetection:     (data)   => api.post('/surveillance/anomalies/run_detection/', data),

  // Case Clusters
  listClusters:            (params) => api.get('/surveillance/clusters/', { params }),
  getCluster:              (id)     => api.get(`/surveillance/clusters/${id}/`),
  createCluster:           (data)   => api.post('/surveillance/clusters/', data),
  updateCluster:           (id, d)  => api.patch(`/surveillance/clusters/${id}/`, d),
  deleteCluster:           (id)     => api.delete(`/surveillance/clusters/${id}/`),

  // Hotspots
  listHotspots:            (params) => api.get('/surveillance/hotspots/', { params }),
  getHotspot:              (id)     => api.get(`/surveillance/hotspots/${id}/`),
  createHotspot:           (data)   => api.post('/surveillance/hotspots/', data),
  updateHotspot:           (id, d)  => api.patch(`/surveillance/hotspots/${id}/`, d),
  deleteHotspot:           (id)     => api.delete(`/surveillance/hotspots/${id}/`),

  // Surveillance Reports
  listSurvReports:         (params) => api.get('/surveillance/reports/', { params }),
  getSurvReport:           (id)     => api.get(`/surveillance/reports/${id}/`),
  generateSurvReport:      (data)   => api.post('/surveillance/reports/generate/', data),
  downloadSurvReport:      (id)     => api.get(`/surveillance/reports/${id}/download/`, { responseType: 'blob' }),

  // Data Quality
  listDataQuality:         (params) => api.get('/surveillance/quality-checks/', { params }),
  getDataQualityCheck:     (id)     => api.get(`/surveillance/quality-checks/${id}/`),
  runQualityCheck:         (data)   => api.post('/surveillance/quality-checks/', data),

  // Dashboard aggregate
  surveillanceDashboard:   (params) => api.get('/surveillance/dashboard/overview/', { params }),
}

// ─────────────────────────────────────────────────────────────────────────────
// APP 4 — RISK ASSESSMENT  (/risk/...)
// ─────────────────────────────────────────────────────────────────────────────
export const riskApi = {
  // ── Risk Scores  /risk/scores/ ────────────────────────────────────────────
  listRiskScores:        (params) => api.get('/risk/scores/', { params }),
  getRiskScore:          (id)     => api.get(`/risk/scores/${id}/`),
  createRiskScore:       (data)   => api.post('/risk/scores/', data),
  updateRiskScore:       (id, d)  => api.patch(`/risk/scores/${id}/`, d),
  deleteRiskScore:       (id)     => api.delete(`/risk/scores/${id}/`),
  activeRiskScores:      (params) => api.get('/risk/scores/active/', { params }),
  criticalRiskScores:    (params) => api.get('/risk/scores/critical/', { params }),
  riskScoresByLocation:  (locationId) => api.get('/risk/scores/by_location/', { params: { location_id: locationId } }),
  riskScoreTrends:       (params) => api.get('/risk/scores/trends/', { params }),
  calculateRiskScore:    (data)   => api.post('/risk/scores/calculate/', data),

  // ── Threat Classifications  /risk/threats/ ───────────────────────────────
  listThreats:           (params) => api.get('/risk/threats/', { params }),
  getThreat:             (id)     => api.get(`/risk/threats/${id}/`),
  createThreat:          (data)   => api.post('/risk/threats/', data),
  updateThreat:          (id, d)  => api.patch(`/risk/threats/${id}/`, d),
  deleteThreat:          (id)     => api.delete(`/risk/threats/${id}/`),
  pandemicThreats:       (params) => api.get('/risk/threats/pandemic_threats/', { params }),
  severThreats:          (params) => api.get('/risk/threats/severe/', { params }),

  // ── Alerts  /risk/alerts/ ────────────────────────────────────────────────
  listAlerts:            (params) => api.get('/risk/alerts/', { params }),
  getAlert:              (id)     => api.get(`/risk/alerts/${id}/`),
  createAlert:           (data)   => api.post('/risk/alerts/', data),
  updateAlert:           (id, d)  => api.patch(`/risk/alerts/${id}/`, d),
  deleteAlert:           (id)     => api.delete(`/risk/alerts/${id}/`),
  // State transitions
  // POST /risk/alerts/{id}/acknowledge/ → { notes: '' }
  acknowledgeAlert:      (id, d)  => api.post(`/risk/alerts/${id}/acknowledge/`, d ?? {}),
  // POST /risk/alerts/{id}/resolve/     → { resolution_notes: '', actions_taken: [] }
  resolveAlert:          (id, d)  => api.post(`/risk/alerts/${id}/resolve/`, d ?? {}),
  // POST /risk/alerts/{id}/close/       → {}
  closeAlert:            (id, d)  => api.post(`/risk/alerts/${id}/close/`, d ?? {}),
  bulkAcknowledgeAlerts: (data)   => api.post('/risk/alerts/bulk_acknowledge/', data),
  activeAlerts:          (params) => api.get('/risk/alerts/active/', { params }),
  unacknowledgedAlerts:  (params) => api.get('/risk/alerts/unacknowledged/', { params }),
  criticalAlerts:        (params) => api.get('/risk/alerts/critical/', { params }),
  alertsByLocation:      (locationId) => api.get('/risk/alerts/by_location/', { params: { location_id: locationId } }),

  // ── Thresholds  /risk/thresholds/ ────────────────────────────────────────
  listThresholds:        (params) => api.get('/risk/thresholds/', { params }),
  getThreshold:          (id)     => api.get(`/risk/thresholds/${id}/`),
  createThreshold:       (data)   => api.post('/risk/thresholds/', data),
  updateThreshold:       (id, d)  => api.patch(`/risk/thresholds/${id}/`, d),
  deleteThreshold:       (id)     => api.delete(`/risk/thresholds/${id}/`),
  activeThresholds:      ()       => api.get('/risk/thresholds/active/'),
  // POST /risk/thresholds/{id}/check/ → { current_value: <decimal> }
  checkThreshold:        (id, d)  => api.post(`/risk/thresholds/${id}/check/`, d),

  // ── Risk Factors  /risk/factors/ ─────────────────────────────────────────
  listRiskFactors:       (params) => api.get('/risk/factors/', { params }),
  getRiskFactor:         (id)     => api.get(`/risk/factors/${id}/`),
  createRiskFactor:      (data)   => api.post('/risk/factors/', data),
  updateRiskFactor:      (id, d)  => api.patch(`/risk/factors/${id}/`, d),
  deleteRiskFactor:      (id)     => api.delete(`/risk/factors/${id}/`),
  riskFactorsByCategory: (cat)    => api.get('/risk/factors/by_category/', { params: { category: cat } }),

  // ── Predictive Models  /risk/models/ ─────────────────────────────────────
  listPredictiveModels:  (params) => api.get('/risk/models/', { params }),
  getPredictiveModel:    (id)     => api.get(`/risk/models/${id}/`),
  createPredictiveModel: (data)   => api.post('/risk/models/', data),
  updatePredictiveModel: (id, d)  => api.patch(`/risk/models/${id}/`, d),
  deletePredictiveModel: (id)     => api.delete(`/risk/models/${id}/`),
  deployedModels:        ()       => api.get('/risk/models/deployed/'),
  // POST /risk/models/{id}/predict/ → OutbreakPredictionSerializer
  runPrediction:         (id, d)  => api.post(`/risk/models/${id}/predict/`, d),

  // ── Dashboard  /risk/dashboard/ ──────────────────────────────────────────
  // RiskDashboardViewSet is a ViewSet (not ModelViewSet) so its list-route actions
  // are accessed at: /risk/dashboard/overview/ and /risk/dashboard/comparative/
  riskDashboard:         ()       => api.get('/risk/dashboard/overview/'),
  riskDashboardOverview: ()       => api.get('/risk/dashboard/overview/'),
  riskComparative:       ()       => api.get('/risk/dashboard/comparative/'),
}

// ─────────────────────────────────────────────────────────────────────────────
// APP 5 — RESPONSE  (/response/...)
// ─────────────────────────────────────────────────────────────────────────────
export const responseApi = {
  // ── Response Levels (/response/levels/) ──────────────────────────────────
  listLevels:                (params) => api.get('/response/levels/', { params }),
  getLevel:                  (id)     => api.get(`/response/levels/${id}/`),
  createLevel:               (data)   => api.post('/response/levels/', data),
  updateLevel:               (id, d)  => api.patch(`/response/levels/${id}/`, d),
  activeLevels:              ()       => api.get('/response/levels/active/'),

  // ── Response Protocols (/response/protocols/) ────────────────────────────
  listProtocols:             (params) => api.get('/response/protocols/', { params }),
  getProtocol:               (id)     => api.get(`/response/protocols/${id}/`),
  createProtocol:            (data)   => api.post('/response/protocols/', data),
  updateProtocol:            (id, d)  => api.patch(`/response/protocols/${id}/`, d),
  deleteProtocol:            (id)     => api.delete(`/response/protocols/${id}/`),
  activeProtocols:           ()       => api.get('/response/protocols/active/'),
  protocolsByDisease:        (code)   => api.get('/response/protocols/by_disease/', { params: { disease_code: code } }),

  // ── Response Activations (/response/activations/) ────────────────────────
  //    State machine: PENDING → ACTIVE → ESCALATED ↔ DEESCALATED → COMPLETED | SUSPENDED | CANCELLED
  listActivations:           (params) => api.get('/response/activations/', { params }),
  getActivation:             (id)     => api.get(`/response/activations/${id}/`),
  createActivation:          (data)   => api.post('/response/activations/', data),
  updateActivation:          (id, d)  => api.patch(`/response/activations/${id}/`, d),
  // State transitions
  escalate:                  (id, d)  => api.post(`/response/activations/${id}/escalate/`, d),
  deescalate:                (id, d)  => api.post(`/response/activations/${id}/deescalate/`, d),
  complete:                  (id, d)  => api.post(`/response/activations/${id}/complete/`, d),
  suspend:                   (id, d)  => api.post(`/response/activations/${id}/suspend/`, d),
  // Extra list actions
  activeActivations:         ()       => api.get('/response/activations/active/'),
  level5Activations:         ()       => api.get('/response/activations/level_5/'),
  // Detail computed actions
  activationTimeline:        (id)     => api.get(`/response/activations/${id}/timeline/`),
  activationActions:         (id, p)  => api.get(`/response/activations/${id}/actions/`, { params: p }),
  activationEffectiveness:   (id)     => api.get(`/response/activations/${id}/effectiveness/`),
  escalationRecommendation:  (id)     => api.get(`/response/activations/${id}/escalation_recommendation/`),
  resourceSuggestions:       (id)     => api.get(`/response/activations/${id}/resource_suggestions/`),

  // ── Escalation Triggers (/response/triggers/) ────────────────────────────
  listEscalationTriggers:    (params) => api.get('/response/triggers/', { params }),
  getEscalationTrigger:      (id)     => api.get(`/response/triggers/${id}/`),
  createEscalationTrigger:   (data)   => api.post('/response/triggers/', data),
  updateEscalationTrigger:   (id, d)  => api.patch(`/response/triggers/${id}/`, d),
  deleteEscalationTrigger:   (id)     => api.delete(`/response/triggers/${id}/`),
  activeTriggers:            ()       => api.get('/response/triggers/active/'),

  // ── Action Items (/response/actions/) ────────────────────────────────────
  listActionItems:           (params) => api.get('/response/actions/', { params }),
  getActionItem:             (id)     => api.get(`/response/actions/${id}/`),
  createActionItem:          (data)   => api.post('/response/actions/', data),
  updateActionItem:          (id, d)  => api.patch(`/response/actions/${id}/`, d),
  // State transitions
  startActionItem:           (id)     => api.post(`/response/actions/${id}/start/`),
  completeActionItem:        (id, d)  => api.post(`/response/actions/${id}/complete/`, d),
  blockActionItem:           (id, d)  => api.post(`/response/actions/${id}/block/`, d),
  // Filtered lists
  pendingActions:            (p)      => api.get('/response/actions/pending/', { params: p }),
  overdueActions:            (p)      => api.get('/response/actions/overdue/', { params: p }),
  myActions:                 (p)      => api.get('/response/actions/my_actions/', { params: p }),
  criticalPendingActions:    (p)      => api.get('/response/actions/critical_pending/', { params: p }),

  // ── Decision Logs (/response/decisions/) ─────────────────────────────────
  listDecisionLogs:          (params) => api.get('/response/decisions/', { params }),
  getDecisionLog:            (id)     => api.get(`/response/decisions/${id}/`),
  createDecisionLog:         (data)   => api.post('/response/decisions/', data),
  markDecisionReviewed:      (id, d)  => api.post(`/response/decisions/${id}/mark_reviewed/`, d),

  // ── Response Reports (/response/reports/) ────────────────────────────────
  listResponseReports:       (params) => api.get('/response/reports/', { params }),
  getResponseReport:         (id)     => api.get(`/response/reports/${id}/`),
  createResponseReport:      (data)   => api.post('/response/reports/', data),
  updateResponseReport:      (id, d)  => api.patch(`/response/reports/${id}/`, d),
  publishReport:             (id)     => api.post(`/response/reports/${id}/publish/`),
  publishedReports:          (p)      => api.get('/response/reports/published/', { params: p }),

  // ── Dashboard (/response/dashboard/) ─────────────────────────────────────
  getDashboard:              ()       => api.get('/response/dashboard/overview/'),
  getStatistics:             ()       => api.get('/response/dashboard/statistics/'),
}

// ─────────────────────────────────────────────────────────────────────────────
// APP 6 — COORDINATION  (/coordination/...)
// ─────────────────────────────────────────────────────────────────────────────
export const coordinationApi = {
  // Agencies
  listAgencies:            (params) => api.get('/coordination/agencies/', { params }),
  getAgency:               (id)     => api.get(`/coordination/agencies/${id}/`),
  createAgency:            (data)   => api.post('/coordination/agencies/', data),
  updateAgency:            (id, d)  => api.patch(`/coordination/agencies/${id}/`, d),
  deleteAgency:            (id)     => api.delete(`/coordination/agencies/${id}/`),

  // Teams
  listTeams:               (params) => api.get('/coordination/teams/', { params }),
  getTeam:                 (id)     => api.get(`/coordination/teams/${id}/`),
  createTeam:              (data)   => api.post('/coordination/teams/', data),
  updateTeam:              (id, d)  => api.patch(`/coordination/teams/${id}/`, d),
  deleteTeam:              (id)     => api.delete(`/coordination/teams/${id}/`),
  activateTeam:            (id)     => api.post(`/coordination/teams/${id}/activate/`),
  deactivateTeam:          (id)     => api.post(`/coordination/teams/${id}/deactivate/`),
  teamMembers:             (id)     => api.get(`/coordination/teams/${id}/members/`),
  addTeamMember:           (id, d)  => api.post(`/coordination/teams/${id}/members/add/`, d),
  removeTeamMember:        (id, d)  => api.delete(`/coordination/memberships/${id}/`, d),

  // Memberships
  listMemberships:         (params) => api.get('/coordination/memberships/', { params }),
  updateMembership:        (id, d)  => api.patch(`/coordination/memberships/${id}/`, d),
  deleteMembership:        (id)     => api.delete(`/coordination/memberships/${id}/`),

  // Tasks
  listTasks:               (params) => api.get('/coordination/tasks/', { params }),
  getTask:                 (id)     => api.get(`/coordination/tasks/${id}/`),
  createTask:              (data)   => api.post('/coordination/tasks/', data),
  updateTask:              (id, d)  => api.patch(`/coordination/tasks/${id}/`, d),
  deleteTask:              (id)     => api.delete(`/coordination/tasks/${id}/`),
  acceptTask:              (id)     => api.post(`/coordination/tasks/${id}/accept/`),
  startTask:               (id)     => api.post(`/coordination/tasks/${id}/start/`),
  completeTask:            (id, d)  => api.post(`/coordination/tasks/${id}/complete/`, d),
  cancelTask:              (id, d)  => api.post(`/coordination/tasks/${id}/cancel/`, d),

  // Meetings
  listMeetings:            (params) => api.get('/coordination/meetings/', { params }),
  getMeeting:              (id)     => api.get(`/coordination/meetings/${id}/`),
  createMeeting:           (data)   => api.post('/coordination/meetings/', data),
  updateMeeting:           (id, d)  => api.patch(`/coordination/meetings/${id}/`, d),
  deleteMeeting:           (id)     => api.delete(`/coordination/meetings/${id}/`),
  commenceMeeting:         (id)     => api.post(`/coordination/meetings/${id}/commence/`),
  closeMeeting:            (id, d)  => api.post(`/coordination/meetings/${id}/close/`, d),
  cancelMeeting:           (id, d)  => api.post(`/coordination/meetings/${id}/cancel/`, d),
  meetingAttendance:       (id)     => api.get(`/coordination/meetings/${id}/attendance/`),

  // Communication Channels
  listChannels:            (params) => api.get('/coordination/channels/', { params }),
  getChannel:              (id)     => api.get(`/coordination/channels/${id}/`),
  createChannel:           (data)   => api.post('/coordination/channels/', data),
  updateChannel:           (id, d)  => api.patch(`/coordination/channels/${id}/`, d),
  deleteChannel:           (id)     => api.delete(`/coordination/channels/${id}/`),

  // Information Products
  listInfoProducts:        (params) => api.get('/coordination/products/', { params }),
  getInfoProduct:          (id)     => api.get(`/coordination/products/${id}/`),
  createInfoProduct:       (data)   => api.post('/coordination/products/', data),
  updateInfoProduct:       (id, d)  => api.patch(`/coordination/products/${id}/`, d),
  deleteInfoProduct:       (id)     => api.delete(`/coordination/products/${id}/`),
  supersedeInfoProduct:    (id, d)  => api.post(`/coordination/products/${id}/supersede/`, d),

  // Dashboard
  coordinationDashboard:   (params) => api.get('/coordination/dashboard/overview/', { params }),
}

// ─────────────────────────────────────────────────────────────────────────────
// APP 7 — RESOURCES  (/resources/...)
// ─────────────────────────────────────────────────────────────────────────────
export const resourcesApi = {
  // Facilities
  listFacilities:           (params) => api.get('/resources/facilities/', { params }),
  getFacility:              (id)     => api.get(`/resources/facilities/${id}/`),
  createFacility:           (data)   => api.post('/resources/facilities/', data),
  updateFacility:           (id, d)  => api.patch(`/resources/facilities/${id}/`, d),
  deleteFacility:           (id)     => api.delete(`/resources/facilities/${id}/`),
  decommissionFacility:     (id)     => api.post(`/resources/facilities/${id}/decommission/`),
  facilityInventory:        (id, p)  => api.get(`/resources/facilities/${id}/inventory/`, { params: p }),

  // Inventory
  listInventory:            (params) => api.get('/resources/inventory/', { params }),
  getInventoryItem:         (id)     => api.get(`/resources/inventory/${id}/`),
  createInventoryItem:      (data)   => api.post('/resources/inventory/', data),
  updateInventoryItem:      (id, d)  => api.patch(`/resources/inventory/${id}/`, d),
  deleteInventoryItem:      (id)     => api.delete(`/resources/inventory/${id}/`),
  expiringSoon:             (params) => api.get('/resources/inventory/expiring_soon/', { params }),

  // Stock Movements  — router basename: movements  (/resources/movements/)
  listStockMovements:       (params) => api.get('/resources/movements/', { params }),
  getStockMovement:         (id)     => api.get(`/resources/movements/${id}/`),
  createStockMovement:      (data)   => api.post('/resources/movements/', data),
  recentStockMovements:     ()       => api.get('/resources/movements/recent/'),
  stockMovementsToday:      (params) => api.get('/resources/movements/today/', { params }),

  // Inventory extra actions (DRF uses underscores in action URLs)
  inventoryLowStock:        (params) => api.get('/resources/inventory/low_stock/', { params }),
  inventoryExpiringSoon:    (params) => api.get('/resources/inventory/expiring_soon/', { params }),
  adjustInventory:          (id, d)  => api.post(`/resources/inventory/${id}/adjust/`, d),

  // Procurement Requests
  listProcurement:          (params) => api.get('/resources/procurement/', { params }),
  getProcurement:           (id)     => api.get(`/resources/procurement/${id}/`),
  createProcurement:        (data)   => api.post('/resources/procurement/', data),
  updateProcurement:        (id, d)  => api.patch(`/resources/procurement/${id}/`, d),
  pendingProcurement:       (params) => api.get('/resources/procurement/pending/', { params }),
  submitProcurement:        (id)     => api.post(`/resources/procurement/${id}/submit/`),
  approveProcurement:       (id, d)  => api.post(`/resources/procurement/${id}/approve/`, d ?? {}),
  rejectProcurement:        (id, d)  => api.post(`/resources/procurement/${id}/reject/`, d),
  cancelProcurement:        (id, d)  => api.post(`/resources/procurement/${id}/cancel/`, d ?? {}),
  markProcurementDelivered: (id, d)  => api.post(`/resources/procurement/${id}/mark_delivered/`, d ?? {}),
  procurementItems:         (id)     => api.get(`/resources/procurement/${id}/items/`),

  // Demand Forecasts
  listForecasts:            (params) => api.get('/resources/forecasts/', { params }),
  getForecast:              (id)     => api.get(`/resources/forecasts/${id}/`),
  currentForecasts:         (params) => api.get('/resources/forecasts/current/', { params }),

  // Capacity Metrics
  listCapacity:             (params) => api.get('/resources/capacity/', { params }),
  highOccupancy:            (params) => api.get('/resources/capacity/high_occupancy/', { params }),

  // Resource Items
  listResourceItems:        (params) => api.get('/resources/items/', { params }),
  getResourceItem:          (id)     => api.get(`/resources/items/${id}/`),
  criticalItems:            (params) => api.get('/resources/items/critical/', { params }),
  lowStockSummary:          ()       => api.get('/resources/items/low_stock_summary/'),

  // Suppliers
  listSuppliers:            (params) => api.get('/resources/suppliers/', { params }),
  getSupplier:              (id)     => api.get(`/resources/suppliers/${id}/`),
  approveSupplier:          (id)     => api.post(`/resources/suppliers/${id}/approve/`),
  deactivateSupplier:       (id)     => api.post(`/resources/suppliers/${id}/deactivate/`),

  // Resource Categories
  listCategories:           (params) => api.get('/resources/categories/', { params }),

  // Dashboard — ResourceDashboardViewSet @action detail=False → /resources/dashboard/overview/
  resourcesDashboard:       ()       => api.get('/resources/dashboard/overview/'),
}

// ─────────────────────────────────────────────────────────────────────────────
// APP 8 — COMMUNICATIONS  (/communications/...)
// ─────────────────────────────────────────────────────────────────────────────
export const communicationsApi = {
  // Message Templates
  listTemplates:           (params) => api.get('/communications/templates/', { params }),
  getTemplate:             (id)     => api.get(`/communications/templates/${id}/`),
  createTemplate:          (data)   => api.post('/communications/templates/', data),
  updateTemplate:          (id, d)  => api.patch(`/communications/templates/${id}/`, d),
  deleteTemplate:          (id)     => api.delete(`/communications/templates/${id}/`),

  // Campaigns
  listCampaigns:           (params) => api.get('/communications/campaigns/', { params }),
  getCampaign:             (id)     => api.get(`/communications/campaigns/${id}/`),
  createCampaign:          (data)   => api.post('/communications/campaigns/', data),
  updateCampaign:          (id, d)  => api.patch(`/communications/campaigns/${id}/`, d),
  deleteCampaign:          (id)     => api.delete(`/communications/campaigns/${id}/`),
  launchCampaign:          (id)     => api.post(`/communications/campaigns/${id}/launch/`),
  pauseCampaign:           (id)     => api.post(`/communications/campaigns/${id}/pause/`),
  completeCampaign:        (id)     => api.post(`/communications/campaigns/${id}/complete/`),
  campaignMetrics:         (id)     => api.get(`/communications/campaigns/${id}/metrics/`),

  // Messages
  listMessages:            (params) => api.get('/communications/messages/', { params }),
  getMessage:              (id)     => api.get(`/communications/messages/${id}/`),
  sendMessage:             (data)   => api.post('/communications/messages/send/', data),

  // Broadcasts
  listBroadcasts:          (params) => api.get('/communications/broadcasts/', { params }),
  getBroadcast:            (id)     => api.get(`/communications/broadcasts/${id}/`),
  createBroadcast:         (data)   => api.post('/communications/broadcasts/', data),
  updateBroadcast:         (id, d)  => api.patch(`/communications/broadcasts/${id}/`, d),
  approveBroadcast:        (id)     => api.post(`/communications/broadcasts/${id}/approve/`),
  cancelBroadcast:         (id, d)  => api.post(`/communications/broadcasts/${id}/cancel/`, d),

  // Contact Lists  (router basename: contacts → /communications/contacts/)
  listContactLists:        (params) => api.get('/communications/contacts/', { params }),
  getContactList:          (id)     => api.get(`/communications/contacts/${id}/`),
  createContactList:       (data)   => api.post('/communications/contacts/', data),
  updateContactList:       (id, d)  => api.patch(`/communications/contacts/${id}/`, d),
  deleteContactList:       (id)     => api.delete(`/communications/contacts/${id}/`),

  // Public Announcements (AllowAny — public endpoint)
  listAnnouncements:       (params) => api.get('/communications/announcements/', { params }),
  getAnnouncement:         (id)     => api.get(`/communications/announcements/${id}/`),
  createAnnouncement:      (data)   => api.post('/communications/announcements/', data),
  updateAnnouncement:      (id, d)  => api.patch(`/communications/announcements/${id}/`, d),
  deleteAnnouncement:      (id)     => api.delete(`/communications/announcements/${id}/`),
  publishedAnnouncements:  (params) => api.get('/communications/announcements/published/', { params }),

  // Social Media Posts  (router basename: social → /communications/social/)
  listSocialPosts:         (params) => api.get('/communications/social/', { params }),
  getSocialPost:           (id)     => api.get(`/communications/social/${id}/`),
  createSocialPost:        (data)   => api.post('/communications/social/', data),
  updateSocialPost:        (id, d)  => api.patch(`/communications/social/${id}/`, d),
  publishSocialPost:       (id)     => api.post(`/communications/social/${id}/publish/`),
  deleteSocialPost:        (id)     => api.delete(`/communications/social/${id}/`),

  // Feedback / Responses (AllowAny POST — public endpoint)
  listFeedback:            (params) => api.get('/communications/feedback/', { params }),
  getFeedback:             (id)     => api.get(`/communications/feedback/${id}/`),
  submitFeedback:          (data)   => api.post('/communications/feedback/', data),
  assignFeedback:          (id, d)  => api.post(`/communications/feedback/${id}/assign/`, d),
  respondFeedback:         (id, d)  => api.post(`/communications/feedback/${id}/respond/`, d),
  resolveFeedback:         (id)     => api.post(`/communications/feedback/${id}/resolve/`),
  escalateFeedback:        (id, d)  => api.post(`/communications/feedback/${id}/escalate/`, d),

  // Dashboard summary
  getDashboard:            ()       => api.get('/communications/dashboard/overview/'),
}

// ─────────────────────────────────────────────────────────────────────────────
// APP 9 — ANALYTICS  (/analytics/...)
// ─────────────────────────────────────────────────────────────────────────────
// URLs verified against analytics/urls.py:
//   /analytics/epi-models/         EpidemiologicalModelViewSet
//   /analytics/spatial/            SpatialAnalysisViewSet
//   /analytics/timeseries/         TimeSeriesAnalysisViewSet      ← NOT /time-series/
//   /analytics/reports/            StatisticalReportViewSet
//   /analytics/dashboards/         DashboardViewSet
//   /analytics/exports/            DataExportViewSet
//   /analytics/indicators/         IndicatorViewSet
//   /analytics/indicator-values/   IndicatorValueViewSet
//   /analytics/templates/          ReportTemplateViewSet
//   /analytics/overview/           AnalyticsDashboardViewSet
//     → GET /analytics/overview/overview/  (@action detail=False name='overview')
//
// Key corrections vs previous version:
//   - Renamed listEpiModels/getEpiModel → listEpidemiologicalModels/getEpidemiologicalModel
//   - runEpiModel /run/ → runSimulation /run_simulation/  (actual @action name)
//   - listTimeSeries /time-series/ → listTimeSeriesAnalyses /timeseries/
//   - Removed non-existent: epiModelResults, runSpatialAnalysis, runTimeSeries,
//     generateStatReport at /reports/generate/
//   - Added: publishedReports, requestExport, getDashboardOverview,
//     full indicator-values CRUD, full templates CRUD, generateFromTemplate
// ─────────────────────────────────────────────────────────────────────────────
export const analyticsApi = {
  // ── Epidemiological Models (SIR / SEIR / SIRS / SEIRS / SIS) ─────────────
  // list → EpidemiologicalModelListSerializer:
  //   id, name, model_type, model_type_display, disease_name, disease_code,
  //   location_name, basic_reproduction_number, is_validated,
  //   simulation_completed_at, created_at
  // detail → EpidemiologicalModelSerializer (adds):
  //   r0_status, attack_rate, peak_day, peak_infections, total_population,
  //   simulation_results{days,susceptible,exposed?,infected,recovered},
  //   parameters, initial_*, model_fit_score, rmse, validated_at
  listEpidemiologicalModels:   (params) => api.get('/analytics/epi-models/', { params }),
  getEpidemiologicalModel:     (id)     => api.get(`/analytics/epi-models/${id}/`),
  createEpidemiologicalModel:  (data)   => api.post('/analytics/epi-models/', data),
  updateEpidemiologicalModel:  (id, d)  => api.patch(`/analytics/epi-models/${id}/`, d),
  deleteEpidemiologicalModel:  (id)     => api.delete(`/analytics/epi-models/${id}/`),
  // POST /analytics/epi-models/{id}/run_simulation/
  // body: { simulation_days: 365, parameters: { beta, gamma, … } }
  // returns: { status, task_id, model_id, simulation_days }  HTTP 202
  runSimulation:               (id, d)  => api.post(`/analytics/epi-models/${id}/run_simulation/`, d ?? {}),

  // ── Spatial Analysis (Moran's I, Gi*, DBSCAN/KMeans) ─────────────────────
  // SpatialAnalysisSerializer fields:
  //   id, name, analysis_type, analysis_type_display, disease_name, disease_code,
  //   location_name, morans_i, p_value, z_score, is_significant,
  //   hotspot_count, cluster_count, hotspots[], clusters[], results,
  //   start_date, end_date, performed_by_username
  listSpatialAnalyses:         (params) => api.get('/analytics/spatial/', { params }),
  getSpatialAnalysis:          (id)     => api.get(`/analytics/spatial/${id}/`),
  createSpatialAnalysis:       (data)   => api.post('/analytics/spatial/', data),
  updateSpatialAnalysis:       (id, d)  => api.patch(`/analytics/spatial/${id}/`, d),
  deleteSpatialAnalysis:       (id)     => api.delete(`/analytics/spatial/${id}/`),

  // ── Time Series Analysis (ARIMA, z-score anomaly) ─────────────────────────
  // Router: r'timeseries' → /analytics/timeseries/  (not /time-series/)
  // TimeSeriesAnalysisSerializer fields:
  //   id, name, analysis_type, analysis_type_display, disease_name, disease_code,
  //   location_name, trend_direction, trend_direction_display, trend_strength,
  //   has_seasonality, seasonal_period, mae, rmse, mape,
  //   has_forecast, forecast_horizon, forecast_days,
  //   start_date, end_date, performed_by_username
  listTimeSeriesAnalyses:      (params) => api.get('/analytics/timeseries/', { params }),
  getTimeSeriesAnalysis:       (id)     => api.get(`/analytics/timeseries/${id}/`),
  createTimeSeriesAnalysis:    (data)   => api.post('/analytics/timeseries/', data),
  updateTimeSeriesAnalysis:    (id, d)  => api.patch(`/analytics/timeseries/${id}/`, d),
  deleteTimeSeriesAnalysis:    (id)     => api.delete(`/analytics/timeseries/${id}/`),

  // ── Statistical Reports (WHO SitRep, IHR, custom) ─────────────────────────
  // list → StatisticalReportListSerializer:
  //   id, title, report_type, author_username, is_published,
  //   published_at, start_date, end_date, created_at
  listStatisticalReports:      (params) => api.get('/analytics/reports/', { params }),
  getStatisticalReport:        (id)     => api.get(`/analytics/reports/${id}/`),
  createStatisticalReport:     (data)   => api.post('/analytics/reports/', data),
  updateStatisticalReport:     (id, d)  => api.patch(`/analytics/reports/${id}/`, d),
  deleteStatisticalReport:     (id)     => api.delete(`/analytics/reports/${id}/`),
  // GET /analytics/reports/published/  @action(detail=False, methods=['get'])
  publishedReports:            (params) => api.get('/analytics/reports/published/', { params }),
  downloadStatReport:          (id)     => api.get(`/analytics/reports/${id}/download/`, { responseType: 'blob' }),

  // ── Analytics Dashboards ──────────────────────────────────────────────────
  listDashboards:              (params) => api.get('/analytics/dashboards/', { params }),
  getDashboard:                (id)     => api.get(`/analytics/dashboards/${id}/`),
  createDashboard:             (data)   => api.post('/analytics/dashboards/', data),
  updateDashboard:             (id, d)  => api.patch(`/analytics/dashboards/${id}/`, d),
  deleteDashboard:             (id)     => api.delete(`/analytics/dashboards/${id}/`),

  // ── Data Exports (CSV / Excel / JSON) ────────────────────────────────────
  // DataExportSerializer fields:
  //   id, name, export_format, status, file_size_display,
  //   row_count, processing_time, created_at, requested_by_username
  listDataExports:             (params) => api.get('/analytics/exports/', { params }),
  getDataExport:               (id)     => api.get(`/analytics/exports/${id}/`),
  createDataExport:            (data)   => api.post('/analytics/exports/', data),
  deleteDataExport:            (id)     => api.delete(`/analytics/exports/${id}/`),
  // POST /analytics/exports/request_export/
  // body: { data_type, export_format, filters?, start_date?, end_date? }
  // returns: { export_id, status, task_id }  HTTP 202
  requestExport:               (data)   => api.post('/analytics/exports/request_export/', data),
  downloadExport:              (id)     => api.get(`/analytics/exports/${id}/download/`, { responseType: 'blob' }),

  // ── Indicators (KPIs) ────────────────────────────────────────────────────
  // IndicatorSerializer fields:
  //   id, name, code, indicator_type, indicator_type_display,
  //   target_value, target_direction, unit_of_measure,
  //   reporting_frequency_display, is_active, value_count
  listIndicators:              (params) => api.get('/analytics/indicators/', { params }),
  getIndicator:                (id)     => api.get(`/analytics/indicators/${id}/`),
  createIndicator:             (data)   => api.post('/analytics/indicators/', data),
  updateIndicator:             (id, d)  => api.patch(`/analytics/indicators/${id}/`, d),
  deleteIndicator:             (id)     => api.delete(`/analytics/indicators/${id}/`),

  // ── Indicator Values ──────────────────────────────────────────────────────
  // IndicatorValueSerializer fields:
  //   id, indicator, indicator_name, indicator_code,
  //   location, location_name, value,
  //   period_start, period_end, target_achieved,
  //   variance_from_target, data_quality_score, recorded_by_username
  listIndicatorValues:         (params) => api.get('/analytics/indicator-values/', { params }),
  getIndicatorValue:           (id)     => api.get(`/analytics/indicator-values/${id}/`),
  createIndicatorValue:        (data)   => api.post('/analytics/indicator-values/', data),
  updateIndicatorValue:        (id, d)  => api.patch(`/analytics/indicator-values/${id}/`, d),
  deleteIndicatorValue:        (id)     => api.delete(`/analytics/indicator-values/${id}/`),

  // ── Report Templates ──────────────────────────────────────────────────────
  // ReportTemplateSerializer fields:
  //   id, name, template_type, template_type_display,
  //   output_format, output_format_display, is_active, required_indicator_names
  listReportTemplates:         (params) => api.get('/analytics/templates/', { params }),
  getReportTemplate:           (id)     => api.get(`/analytics/templates/${id}/`),
  createReportTemplate:        (data)   => api.post('/analytics/templates/', data),
  updateReportTemplate:        (id, d)  => api.patch(`/analytics/templates/${id}/`, d),
  deleteReportTemplate:        (id)     => api.delete(`/analytics/templates/${id}/`),
  // POST /analytics/templates/{id}/generate/
  // returns: { status, task_id, template_id }  HTTP 202
  generateFromTemplate:        (id, d)  => api.post(`/analytics/templates/${id}/generate/`, d ?? {}),

  // ── Analytics Overview Dashboard ──────────────────────────────────────────
  // AnalyticsDashboardViewSet registered at r'overview'
  // @action(detail=False, methods=['get']) → GET /analytics/overview/overview/
  // AnalyticsDashboardSerializer fields:
  //   total_analyses, total_models, total_reports, total_exports,
  //   active_dashboards, recent_models[], recent_exports[], key_indicators[]
  getDashboardOverview:        ()       => api.get('/analytics/overview/overview/'),
}

// ─────────────────────────────────────────────────────────────────────────────
// APP 10 — OPERATIONS  (/operations/...)
// Endpoints verified against operations/urls.py + views.py
// ─────────────────────────────────────────────────────────────────────────────
export const operationsApi = {

  // ── Dashboard ────────────────────────────────────────────────────────────
  // OperationsDashboardViewSet  @action detail=False  GET /operations/dashboard/overview/
  getDashboard:                  (opts = {}) => api.get('/operations/dashboard/overview/', opts),

  // ── Cases  (/operations/cases/) ──────────────────────────────────────────
  listCases:                     (params, opts = {}) => api.get('/operations/cases/', { params, ...opts }),
  getCase:                       (id)     => api.get(`/operations/cases/${id}/`),
  createCase:                    (data)   => api.post('/operations/cases/', data),
  updateCase:                    (id, d)  => api.patch(`/operations/cases/${id}/`, d),
  deleteCase:                    (id)     => api.delete(`/operations/cases/${id}/`),
  activeCases:                   (params) => api.get('/operations/cases/active/', { params }),
  confirmedCases:                (params) => api.get('/operations/cases/confirmed/', { params }),
  resolveCase:                   (id, d)  => api.post(`/operations/cases/${id}/resolve/`, d),
  // d = { outcome: 'RECOVERED' | 'DECEASED' | 'NOT_A_CASE' }
  isolateCase:                   (id, d)  => api.post(`/operations/cases/${id}/isolate/`, d),
  // d = { isolation_location: '' }
  getCaseContacts:               (id, p)  => api.get(`/operations/cases/${id}/contacts/`, { params: p }),

  // ── Contacts  (/operations/contacts/) ────────────────────────────────────
  listContacts:                  (params, opts = {}) => api.get('/operations/contacts/', { params, ...opts }),
  getContact:                    (id)     => api.get(`/operations/contacts/${id}/`),
  createContact:                 (data)   => api.post('/operations/contacts/', data),
  updateContact:                 (id, d)  => api.patch(`/operations/contacts/${id}/`, d),
  deleteContact:                 (id)     => api.delete(`/operations/contacts/${id}/`),
  contactsUnderMonitoring:       (params) => api.get('/operations/contacts/under_monitoring/', { params }),
  symptomaticContacts:           (params) => api.get('/operations/contacts/symptomatic/', { params }),
  startMonitoring:               (id, d)  => api.post(`/operations/contacts/${id}/start_monitoring/`, d),
  // d = { period_days: 14 }
  convertToCase:                 (id, d)  => api.post(`/operations/contacts/${id}/convert_to_case/`, d),
  clearContact:                  (id)     => api.post(`/operations/contacts/${id}/clear/`),

  // ── Contact Monitoring  (/operations/monitoring/) ────────────────────────
  listContactMonitoring:         (params) => api.get('/operations/monitoring/', { params }),
  getContactMonitoring:          (id)     => api.get(`/operations/monitoring/${id}/`),
  createContactMonitoring:       (data)   => api.post('/operations/monitoring/', data),
  updateContactMonitoring:       (id, d)  => api.patch(`/operations/monitoring/${id}/`, d),
  deleteContactMonitoring:       (id)     => api.delete(`/operations/monitoring/${id}/`),
  symptomaticToday:              ()       => api.get('/operations/monitoring/symptomatic_today/'),

  // ── Testing Centers  (/operations/testing-centers/) ──────────────────────
  listTestingCenters:            (params, opts = {}) => api.get('/operations/testing-centers/', { params, ...opts }),
  getTestingCenter:              (id)     => api.get(`/operations/testing-centers/${id}/`),
  createTestingCenter:           (data)   => api.post('/operations/testing-centers/', data),
  updateTestingCenter:           (id, d)  => api.patch(`/operations/testing-centers/${id}/`, d),
  deleteTestingCenter:           (id)     => api.delete(`/operations/testing-centers/${id}/`),
  operationalCenters:            (params) => api.get('/operations/testing-centers/operational/', { params }),
  centerCapacityStatus:          (id)     => api.get(`/operations/testing-centers/${id}/capacity_status/`),

  // ── Testing Appointments  (/operations/testing-appointments/) ─────────────
  listTestingAppointments:       (params) => api.get('/operations/testing-appointments/', { params }),
  getTestingAppointment:         (id)     => api.get(`/operations/testing-appointments/${id}/`),
  createTestingAppointment:      (data)   => api.post('/operations/testing-appointments/', data),
  updateTestingAppointment:      (id, d)  => api.patch(`/operations/testing-appointments/${id}/`, d),
  deleteTestingAppointment:      (id)     => api.delete(`/operations/testing-appointments/${id}/`),
  appointmentsToday:             (params) => api.get('/operations/testing-appointments/today/', { params }),
  recordTestResult:              (id, d)  => api.post(`/operations/testing-appointments/${id}/record_result/`, d),
  // d = { result: 'POSITIVE' | 'NEGATIVE' | 'INCONCLUSIVE', lab_reference: '' }
  cancelAppointment:             (id)     => api.post(`/operations/testing-appointments/${id}/cancel/`),

  // ── Vaccination Campaigns  (/operations/vaccination-campaigns/) ───────────
  listVaccinationCampaigns:      (params, opts = {}) => api.get('/operations/vaccination-campaigns/', { params, ...opts }),
  getVaccinationCampaign:        (id)     => api.get(`/operations/vaccination-campaigns/${id}/`),
  createVaccinationCampaign:     (data)   => api.post('/operations/vaccination-campaigns/', data),
  updateVaccinationCampaign:     (id, d)  => api.patch(`/operations/vaccination-campaigns/${id}/`, d),
  deleteVaccinationCampaign:     (id)     => api.delete(`/operations/vaccination-campaigns/${id}/`),
  activeCampaigns:               (params) => api.get('/operations/vaccination-campaigns/active/', { params }),
  activateCampaign:              (id)     => api.post(`/operations/vaccination-campaigns/${id}/activate/`),
  pauseCampaign:                 (id)     => api.post(`/operations/vaccination-campaigns/${id}/pause/`),
  completeCampaign:              (id)     => api.post(`/operations/vaccination-campaigns/${id}/complete/`),
  campaignProgress:              (id)     => api.get(`/operations/vaccination-campaigns/${id}/progress/`),

  // ── Vaccination Records  (/operations/vaccination-records/) ──────────────
  listVaccinationRecords:        (params) => api.get('/operations/vaccination-records/', { params }),
  getVaccinationRecord:          (id)     => api.get(`/operations/vaccination-records/${id}/`),
  createVaccinationRecord:       (data)   => api.post('/operations/vaccination-records/', data),
  updateVaccinationRecord:       (id, d)  => api.patch(`/operations/vaccination-records/${id}/`, d),
  deleteVaccinationRecord:       (id)     => api.delete(`/operations/vaccination-records/${id}/`),
  vaccinationRecordsToday:       (params) => api.get('/operations/vaccination-records/today/', { params }),
  adverseEvents:                 (params) => api.get('/operations/vaccination-records/adverse_events/', { params }),
  reportAdverseEvent:            (id, d)  => api.post(`/operations/vaccination-records/${id}/report_adverse_event/`, d),
  // d = { details: '', severity: 'MILD' | 'MODERATE' | 'SEVERE' }

  // ── Quarantine Facilities  (/operations/quarantine-facilities/) ───────────
  listQuarantineFacilities:      (params) => api.get('/operations/quarantine-facilities/', { params }),
  getQuarantineFacility:         (id)     => api.get(`/operations/quarantine-facilities/${id}/`),
  createQuarantineFacility:      (data)   => api.post('/operations/quarantine-facilities/', data),
  updateQuarantineFacility:      (id, d)  => api.patch(`/operations/quarantine-facilities/${id}/`, d),
  deleteQuarantineFacility:      (id)     => api.delete(`/operations/quarantine-facilities/${id}/`),
  availableFacilities:           ()       => api.get('/operations/quarantine-facilities/available/'),
  facilityOccupancy:             (id)     => api.get(`/operations/quarantine-facilities/${id}/occupancy/`),

  // ── Quarantine Records  (/operations/quarantine-records/) ─────────────────
  listQuarantineRecords:         (params) => api.get('/operations/quarantine-records/', { params }),
  getQuarantineRecord:           (id)     => api.get(`/operations/quarantine-records/${id}/`),
  createQuarantineRecord:        (data)   => api.post('/operations/quarantine-records/', data),
  updateQuarantineRecord:        (id, d)  => api.patch(`/operations/quarantine-records/${id}/`, d),
  deleteQuarantineRecord:        (id)     => api.delete(`/operations/quarantine-records/${id}/`),
  activeQuarantineRecords:       (params) => api.get('/operations/quarantine-records/active/', { params }),
  releasingToday:                ()       => api.get('/operations/quarantine-records/releasing_today/'),
  startQuarantine:               (id)     => api.post(`/operations/quarantine-records/${id}/start_quarantine/`),
  completeQuarantine:            (id)     => api.post(`/operations/quarantine-records/${id}/complete/`),
  releaseEarly:                  (id, d)  => api.post(`/operations/quarantine-records/${id}/release_early/`, d),
  // d = { reason: '' }
  transferQuarantine:            (id, d)  => api.post(`/operations/quarantine-records/${id}/transfer/`, d),
  // d = { facility_id: '', reason: '' }
}

// ─────────────────────────────────────────────────────────────────────────────
// APP 11 — MOBILE  (/mobile/...)
// ─────────────────────────────────────────────────────────────────────────────
export const mobileApi = {
  // Mobile Devices
  listDevices:             (params) => api.get('/mobile/devices/', { params }),
  getDevice:               (id)     => api.get(`/mobile/devices/${id}/`),
  registerDevice:          (data)   => api.post('/mobile/devices/', data),
  updateDevice:            (id, d)  => api.patch(`/mobile/devices/${id}/`, d),
  deactivateDevice:        (id)     => api.post(`/mobile/devices/${id}/deactivate/`),
  updateDeviceLocation:    (id, d)  => api.post(`/mobile/devices/${id}/update-location/`, d),

  // Field Workers / CHW
  listWorkers:             (params) => api.get('/mobile/workers/', { params }),
  getWorker:               (id)     => api.get(`/mobile/workers/${id}/`),
  workerCaseload:          (id)     => api.get(`/mobile/workers/${id}/caseload/`),
  workerTasks:             (id)     => api.get(`/mobile/workers/${id}/tasks/`),
  workerDashboard:         (id)     => api.get(`/mobile/workers/${id}/dashboard/`),
  workerPerformance:       (id)     => api.get(`/mobile/workers/${id}/performance/`),
  nearbyWorkers:           (params) => api.get('/mobile/workers/nearby/', { params }),

  // Form Submissions
  listFormSubmissions:     (params) => api.get('/mobile/form-submissions/', { params }),
  getFormSubmission:       (id)     => api.get(`/mobile/form-submissions/${id}/`),
  createFormSubmission:    (data)   => api.post('/mobile/form-submissions/', data),
  updateFormSubmission:    (id, d)  => api.patch(`/mobile/form-submissions/${id}/`, d),
  validateSubmission:      (id)     => api.post(`/mobile/form-submissions/${id}/validate/`),
  exportFormSubmissions:   (params) => api.get('/mobile/form-submissions/export/', { params, responseType: 'blob' }),

  // Surveys
  listSurveys:             (params) => api.get('/mobile/surveys/', { params }),
  getSurvey:               (id)     => api.get(`/mobile/surveys/${id}/`),
  createSurvey:            (data)   => api.post('/mobile/surveys/', data),
  updateSurvey:            (id, d)  => api.patch(`/mobile/surveys/${id}/`, d),
  deleteSurvey:            (id)     => api.delete(`/mobile/surveys/${id}/`),

  // Mobile Notifications
  listMobileNotifs:        (params) => api.get('/mobile/notifications/', { params }),
  markMobileNotifRead:     (id)     => api.post(`/mobile/notifications/${id}/mark-read/`),
  markAllMobileNotifsRead: ()       => api.post('/mobile/notifications/mark-all-read/'),
  bulkSendNotifications:   (data)   => api.post('/mobile/notifications/bulk-send/', data),

  // Offline Sync
  deltaSync:               (params) => api.get('/mobile/delta/', { params }),
  batchSync:               (data)   => api.post('/mobile/offline-data/sync/', data),

  // Ping
  ping:                    ()       => api.get('/mobile/ping/'),
}

// ─────────────────────────────────────────────────────────────────────────────
// APP 12 — INTEGRATIONS  (/integrations/...)
// ─────────────────────────────────────────────────────────────────────────────
export const integrationsApi = {
  // External Systems (DHIS2, SORMAS, WHO EIOS, Africa CDC, LIS, etc.)
  listSystems:             (params) => api.get('/integrations/systems/', { params }),
  getSystem:               (id)     => api.get(`/integrations/systems/${id}/`),
  createSystem:            (data)   => api.post('/integrations/systems/', data),
  updateSystem:            (id, d)  => api.patch(`/integrations/systems/${id}/`, d),
  deleteSystem:            (id)     => api.delete(`/integrations/systems/${id}/`),
  testSystemConnection:    (id)     => api.post(`/integrations/systems/${id}/test_connection/`),
  triggerSystemSync:       (id, d)  => api.post(`/integrations/systems/${id}/trigger_sync/`, d),
  systemStats:             (id)     => api.get(`/integrations/systems/${id}/stats/`),

  // Integration Jobs
  listJobs:                (params) => api.get('/integrations/jobs/', { params }),
  getJob:                  (id)     => api.get(`/integrations/jobs/${id}/`),
  cancelJob:               (id)     => api.post(`/integrations/jobs/${id}/cancel/`),
  retryJob:                (id)     => api.post(`/integrations/jobs/${id}/retry/`),

  // Data Mappings (field transformation rules)
  listMappings:            (params) => api.get('/integrations/mappings/', { params }),
  getMapping:              (id)     => api.get(`/integrations/mappings/${id}/`),
  createMapping:           (data)   => api.post('/integrations/mappings/', data),
  updateMapping:           (id, d)  => api.patch(`/integrations/mappings/${id}/`, d),
  deleteMapping:           (id)     => api.delete(`/integrations/mappings/${id}/`),
  testMapping:             (id, d)  => api.post(`/integrations/mappings/${id}/test/`, d),

  // Webhooks (outbound events to external systems)
  listWebhooks:            (params) => api.get('/integrations/webhooks/', { params }),
  getWebhook:              (id)     => api.get(`/integrations/webhooks/${id}/`),
  createWebhook:           (data)   => api.post('/integrations/webhooks/', data),
  updateWebhook:           (id, d)  => api.patch(`/integrations/webhooks/${id}/`, d),
  deleteWebhook:           (id)     => api.delete(`/integrations/webhooks/${id}/`),
  testWebhook:             (id)     => api.post(`/integrations/webhooks/${id}/test/`),
  toggleWebhook:           (id)     => api.post(`/integrations/webhooks/${id}/toggle/`),
  webhookDeliveries:       (id, p)  => api.get(`/integrations/webhooks/${id}/deliveries/`, { params: p }),

  // External API Keys
  listExternalApiKeys:     (params) => api.get('/integrations/api-keys/', { params }),
  getExternalApiKey:       (id)     => api.get(`/integrations/api-keys/${id}/`),
  createExternalApiKey:    (data)   => api.post('/integrations/api-keys/', data),
  revokeExternalApiKey:    (id)     => api.post(`/integrations/api-keys/${id}/revoke/`),
  rotateExternalApiKey:    (id)     => api.post(`/integrations/api-keys/${id}/rotate/`),

  // Integration Logs (audit trail)
  listLogs:                (params) => api.get('/integrations/logs/', { params }),
  getLog:                  (id)     => api.get(`/integrations/logs/${id}/`),

  // Transfer Records (data movement audit trail)
  listTransfers:           (params) => api.get('/integrations/transfers/', { params }),
  getTransfer:             (id)     => api.get(`/integrations/transfers/${id}/`),
}

// ─────────────────────────────────────────────────────────────────────────────
// APP 13 — WEBSOCKETS REST MGMT  (/ws-mgmt/...)
// ─────────────────────────────────────────────────────────────────────────────
export const wsManagementApi = {
  // WebSocket Connections (connection audit log)
  listConnections:         (params) => api.get('/ws-mgmt/connections/', { params }),
  getConnection:           (id)     => api.get(`/ws-mgmt/connections/${id}/`),
  activeConnections:       (params) => api.get('/ws-mgmt/connections/active/', { params }),

  // Channel Groups (group definitions + presence)
  listChannelGroups:       (params) => api.get('/ws-mgmt/channel-groups/', { params }),
  getChannelGroup:         (id)     => api.get(`/ws-mgmt/channel-groups/${id}/`),
  createChannelGroup:      (data)   => api.post('/ws-mgmt/channel-groups/', data),
  updateChannelGroup:      (id, d)  => api.patch(`/ws-mgmt/channel-groups/${id}/`, d),
  channelGroupPresence:    (id)     => api.get(`/ws-mgmt/channel-groups/${id}/presence/`),

  // Broadcast Messages (outbound audit / replay)
  listBroadcastMessages:   (params) => api.get('/ws-mgmt/broadcasts/', { params }),
  getBroadcastMessage:     (id)     => api.get(`/ws-mgmt/broadcasts/${id}/`),
  replayBroadcast:         (id)     => api.post(`/ws-mgmt/broadcasts/${id}/replay/`),
}

export default api