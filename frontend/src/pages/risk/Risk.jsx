/**
 * Risk Assessment — OryxShield
 * ======================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Fixes applied vs original:
 *   1. riskApi.getDashboard() → riskApi.riskDashboard()
 *   2. Dashboard endpoint is /risk/dashboard/overview/ — uses overview action
 *   3. Field names corrected: overall_score, location_name, disease_name, assessment_date
 *   4. Threshold fields: threshold_type, warning_value, alert_value, critical_value
 *   5. useToast() returns {success,error,warning,info,dismiss} — no .toast sub-key
 *   6. Stats mapped from RiskDashboardSerializer shape:
 *      critical_risks, high_risks, active_alerts, average_risk_score
 *   7. Router routes: /risk/scores/, /risk/alerts/, /risk/thresholds/
 *      (NOT /risk/risk-scores/ etc. — matches urls.py registration)
 *   8. Responsive layout: stacks on smaller screens
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { riskApi, extractError } from '../../services/api'
import { useToast } from '../../context/ToastContext'
import { useAlertStream } from '../../hooks/ws/useAlertStream'

// ─── Design tokens ────────────────────────────────────────────────────────────
const RISK_COLORS = {
  VERY_LOW:  '#10b981',
  LOW:       '#34d399',
  MEDIUM:    '#f59e0b',
  HIGH:      '#f97316',
  VERY_HIGH: '#ef4444',
  CRITICAL:  '#dc2626',
}

const RISK_LEVELS = ['ALL', 'VERY_LOW', 'LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH', 'CRITICAL']

// ─── Micro components ─────────────────────────────────────────────────────────
function Badge({ label, color }) {
  return (
    <span style={{
      background: color + '18', border: `1px solid ${color}30`, borderRadius: 2,
      padding: '2px 8px', fontFamily: 'Space Mono, monospace', fontSize: 9,
      letterSpacing: '0.15em', textTransform: 'uppercase', color, whiteSpace: 'nowrap',
    }}>
      {label}
    </span>
  )
}

function Shimmer({ w = '100%', h = 14 }) {
  return (
    <div style={{
      width: w, height: h,
      background: 'linear-gradient(90deg,#111827 25%,#151e2e 50%,#111827 75%)',
      backgroundSize: '200% 100%', animation: 'ra-shimmer 1.5s infinite', borderRadius: 4,
    }} />
  )
}

const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3, ease: 'easeOut', delay },
})

function StatCard({ label, value, sub, color = '#f9fafb', loading, delay = 0 }) {
  return (
    <motion.div {...fadeUp(delay)} style={{
      background: '#111827', border: '1px solid #1f2937', borderRadius: 8,
      padding: '20px 24px', flex: 1, minWidth: 140,
    }}>
      <div style={{
        fontFamily: 'Space Mono, monospace', fontSize: 9,
        letterSpacing: '0.15em', textTransform: 'uppercase',
        color: '#6b7280', marginBottom: 10,
      }}>{label}</div>
      {loading
        ? <Shimmer w="60%" h={32} />
        : <div style={{
            fontFamily: 'Bebas Neue, sans-serif', fontSize: 32,
            color, lineHeight: 1,
          }}>{value ?? '—'}</div>
      }
      {sub && !loading && (
        <div style={{
          fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12,
          color: '#9ca3af', marginTop: 4,
        }}>{sub}</div>
      )}
    </motion.div>
  )
}

// ─── Main page ─────────────────────────────────────────────────────────────────
export default function Risk() {
  const navigate = useNavigate()
  const { error: toastError } = useToast()
  const { data: wsMessages } = useAlertStream()

  // ── Stats (from /risk/dashboard/overview/) ──────────────────────────────────
  const [stats, setStats]               = useState(null)
  const [statsLoading, setStatsLoading] = useState(true)

  // ── Risk Scores (from /risk/scores/) ────────────────────────────────────────
  const [scores, setScores]               = useState([])
  const [scoresLoading, setScoresLoading] = useState(true)
  const [scoresError, setScoresError]     = useState(null)
  const [count, setCount]                 = useState(0)
  const [page, setPage]                   = useState(1)
  const [levelFilter, setLevelFilter]     = useState('ALL')
  const [search, setSearch]               = useState('')

  // ── Thresholds sidebar (from /risk/thresholds/) ─────────────────────────────
  const [thresholds, setThresholds]               = useState([])
  const [thresholdsLoading, setThresholdsLoading] = useState(true)

  // ── Trending threats sidebar (from dashboard overview) ──────────────────────
  const [threats, setThreats] = useState([])

  const searchTimer = useRef(null)

  // ── Fetch dashboard stats ───────────────────────────────────────────────────
  const fetchStats = useCallback(async () => {
    setStatsLoading(true)
    try {
      // ViewSet: RiskDashboardViewSet → action 'overview' → GET /risk/dashboard/overview/
      const res = await riskApi.riskDashboard({ action: 'overview' })
      // riskApi.riskDashboard calls /risk/dashboard/ — the overview action is a
      // list-route action so it's at /risk/dashboard/overview/
      setStats(res.data)
      setThreats(res.data.trending_threats ?? [])
    } catch (err) {
      toastError(extractError(err))
    } finally {
      setStatsLoading(false)
    }
  }, [])

  // ── Fetch risk scores ───────────────────────────────────────────────────────
  // Router: router.register(r"scores", RiskScoreViewSet) → /risk/scores/
  // api.js riskApi.listRiskScores → /risk/risk-scores/ ← WRONG in api.js
  // Fix: use the correct URL directly via the api instance OR update api.js
  // We call it through riskApi but we note the URL mismatch — see api.js fix below.
  // The corrected api.js (in this PR) maps listRiskScores → /risk/scores/
  const fetchScores = useCallback(async (pg = 1, level = levelFilter, q = search) => {
    setScoresLoading(true)
    setScoresError(null)
    try {
      const params = { page: pg, page_size: 20, is_active: true }
      if (level !== 'ALL') params.risk_level = level
      if (q.trim())        params.search = q.trim()
      const res = await riskApi.listRiskScores(params)
      setScores(res.data.results ?? [])
      setCount(res.data.count ?? 0)
    } catch (err) {
      const msg = extractError(err)
      setScoresError(msg)
      toastError(msg)
    } finally {
      setScoresLoading(false)
    }
  }, [levelFilter, search])

  // ── Fetch thresholds ────────────────────────────────────────────────────────
  // Router: router.register(r"thresholds", ThresholdViewSet) → /risk/thresholds/
  const fetchThresholds = useCallback(async () => {
    try {
      const res = await riskApi.listThresholds({ is_active: true, page_size: 8 })
      setThresholds(res.data.results ?? [])
    } catch (err) {
      toastError(extractError(err))
    } finally {
      setThresholdsLoading(false)
    }
  }, [])

  // ── Lifecycle ───────────────────────────────────────────────────────────────
  useEffect(() => { fetchStats(); fetchThresholds() }, [])
  useEffect(() => { fetchScores(page, levelFilter, search) }, [page, levelFilter])

  // Debounced search
  useEffect(() => {
    clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => {
      setPage(1)
      fetchScores(1, levelFilter, search)
    }, 350)
    return () => clearTimeout(searchTimer.current)
  }, [search])

  // WS: react to high_risk_detected / risk_score updates
  useEffect(() => {
    if (!wsMessages?.length) return
    const last = wsMessages[0]
    if (last?.type === 'high_risk_detected' || last?.type === 'high_risk') {
      fetchScores(page, levelFilter, search)
      fetchStats()
    }
  }, [wsMessages])

  // ── Handlers ────────────────────────────────────────────────────────────────
  const handleLevelFilter = (level) => { setLevelFilter(level); setPage(1) }
  const totalPages = Math.ceil(count / 20)

  const scoreBar = (score) => {
    const pct = Math.min(100, parseFloat(score ?? 0) * 10)
    const lvl = Object.entries({ CRITICAL: 9, VERY_HIGH: 7.5, HIGH: 6, MEDIUM: 4, LOW: 2 })
      .find(([, v]) => parseFloat(score) >= v)?.[0] ?? 'VERY_LOW'
    return { pct, color: RISK_COLORS[lvl] ?? '#9ca3af' }
  }

  // ── Threshold status helper ─────────────────────────────────────────────────
  // Backend Threshold has warning_value / alert_value / critical_value
  // We show the critical_value as "threshold" and indicate type
  const thresholdTypeLabel = (t) => {
    const map = {
      CASE_COUNT:     'Case Count',
      INCIDENCE_RATE: 'Incidence / 100k',
      MORTALITY_RATE: 'Mortality %',
      R_NAUGHT:       'R₀',
      RISK_SCORE:     'Risk Score',
      CAPACITY:       'Capacity %',
    }
    return map[t.threshold_type] ?? t.threshold_type
  }

  return (
    <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', color: '#f9fafb', minHeight: '100vh' }}>
      <style>{`
        @keyframes ra-shimmer {
          0%   { background-position: 200% 0 }
          100% { background-position: -200% 0 }
        }
        .ra-row:hover { background: rgba(255,255,255,0.025) !important; cursor: pointer; }
        .ra-row td { padding: 12px 16px; vertical-align: middle; }
        @media (max-width: 900px) {
          .ra-layout { flex-direction: column !important; }
          .ra-sidebar { width: 100% !important; }
          .ra-stats   { flex-wrap: wrap !important; }
        }
      `}</style>

      {/* ── Header ── */}
      <motion.div {...fadeUp(0)} style={{ marginBottom: 28 }}>
        <div style={{
          fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.2em',
          textTransform: 'uppercase', color: '#3b82f6', marginBottom: 6,
        }}>Intelligence · Risk Assessment</div>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
          gap: 12, flexWrap: 'wrap' }}>
          <h1 style={{
            fontFamily: 'Bebas Neue, sans-serif', fontSize: 36, margin: 0,
            letterSpacing: '0.04em', color: '#f9fafb',
          }}>Risk Assessment</h1>
          <button
            onClick={() => navigate('/dashboard/risk/alerts')}
            style={{
              background: '#ef444418', border: '1px solid #ef444430', color: '#ef4444',
              borderRadius: 4, padding: '8px 16px', fontSize: 13, fontWeight: 500,
              fontFamily: 'IBM Plex Sans, sans-serif', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <span style={{ fontSize: 15 }}>⚠</span> View Risk Alerts
          </button>
        </div>
      </motion.div>

      {/* ── Stat Cards ── */}
      {/* Mapped from RiskDashboardSerializer:
          critical_risks, high_risks, active_alerts, unacknowledged_alerts, average_risk_score */}
      <div className="ra-stats" style={{ display: 'flex', gap: 16, marginBottom: 28, flexWrap: 'wrap' }}>
        <StatCard
          label="Critical Risks" delay={0.05}
          value={stats?.critical_risks ?? '—'}
          color="#dc2626" loading={statsLoading}
        />
        <StatCard
          label="High Risks" delay={0.1}
          value={stats?.high_risks ?? '—'}
          color="#f97316" loading={statsLoading}
        />
        <StatCard
          label="Active Alerts" delay={0.15}
          value={stats?.active_alerts ?? '—'}
          color="#f59e0b" loading={statsLoading}
        />
        <StatCard
          label="Avg Risk Score" delay={0.2}
          value={stats?.average_risk_score != null
            ? parseFloat(stats.average_risk_score).toFixed(1)
            : '—'}
          sub="out of 10"
          color="#3b82f6" loading={statsLoading}
        />
      </div>

      {/* ── Main layout: table + sidebar ── */}
      <div className="ra-layout" style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>

        {/* ── Risk Scores Table ── */}
        <motion.div {...fadeUp(0.25)} style={{ flex: 1, minWidth: 0 }}>

          {/* Filters */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {RISK_LEVELS.map(level => {
                const active = levelFilter === level
                const color  = level === 'ALL' ? '#3b82f6' : RISK_COLORS[level]
                return (
                  <button key={level} onClick={() => handleLevelFilter(level)} style={{
                    border: active ? `1px solid ${color}` : '1px solid #1f2937',
                    background: active ? color + '22' : 'transparent',
                    color: active ? color : '#9ca3af',
                    borderRadius: 20, padding: '4px 14px',
                    fontFamily: 'Space Mono, monospace', fontSize: 10,
                    letterSpacing: '0.1em', textTransform: 'uppercase',
                    cursor: 'pointer', transition: 'all 0.15s',
                  }}>{level.replace('_', ' ')}</button>
                )
              })}
            </div>
            <input
              placeholder="Search disease or location…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                background: '#111827', border: '1px solid #1f2937', borderRadius: 6,
                color: '#f9fafb', fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
                padding: '6px 12px', outline: 'none', minWidth: 200, flex: 1,
              }}
            />
          </div>

          {/* Table */}
          <div style={{
            background: '#111827', border: '1px solid #1f2937',
            borderRadius: 8, overflow: 'hidden',
          }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 560 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #1f2937' }}>
                    {['Disease', 'Location', 'Risk Level', 'Score (0–10)', 'R₀', 'CFR %', 'Assessed', ''].map(h => (
                      <th key={h} style={{
                        padding: '10px 16px', textAlign: 'left',
                        fontFamily: 'Space Mono, monospace', fontSize: 9,
                        letterSpacing: '0.15em', textTransform: 'uppercase', color: '#6b7280',
                        whiteSpace: 'nowrap',
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {scoresLoading
                    ? Array.from({ length: 6 }).map((_, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #1f2937' }}>
                        {Array.from({ length: 8 }).map((_, j) => (
                          <td key={j} style={{ padding: '12px 16px' }}>
                            <Shimmer w={j === 2 ? 80 : '80%'} h={13} />
                          </td>
                        ))}
                      </tr>
                    ))
                    : scoresError
                      ? (
                        <tr>
                          <td colSpan={8} style={{
                            padding: 32, textAlign: 'center',
                            color: '#ef4444', fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
                          }}>
                            {scoresError}
                            <button onClick={() => fetchScores(page)} style={{
                              marginLeft: 12, background: '#3b82f6', color: '#fff',
                              border: 'none', borderRadius: 4, padding: '6px 14px',
                              fontSize: 12, cursor: 'pointer',
                            }}>Retry</button>
                          </td>
                        </tr>
                      )
                      : scores.length === 0
                        ? (
                          <tr>
                            <td colSpan={8} style={{
                              padding: 40, textAlign: 'center',
                              color: '#6b7280', fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
                            }}>
                              No risk scores found for the selected filter.
                            </td>
                          </tr>
                        )
                        : scores.map((s, i) => {
                          // Correct serializer fields:
                          //   disease_name, location_name, risk_level, overall_score,
                          //   r_naught, case_fatality_rate, assessment_date
                          const lvlColor = RISK_COLORS[s.risk_level] ?? '#9ca3af'
                          const { pct }  = scoreBar(s.overall_score)
                          const score    = parseFloat(s.overall_score ?? 0)
                          return (
                            <motion.tr
                              key={s.id}
                              className="ra-row"
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              transition={{ delay: i * 0.025 }}
                              onClick={() => navigate('/dashboard/risk')}
                              style={{ borderBottom: '1px solid #1f2937' }}
                            >
                              {/* Disease */}
                              <td>
                                <div style={{
                                  fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
                                  color: '#f9fafb', fontWeight: 500,
                                }}>
                                  {s.disease_name ?? '—'}
                                </div>
                                {s.disease_code && (
                                  <div style={{ fontSize: 10, fontFamily: 'Space Mono, monospace',
                                    color: '#6b7280', marginTop: 2 }}>{s.disease_code}</div>
                                )}
                              </td>

                              {/* Location */}
                              <td style={{
                                fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12,
                                color: '#9ca3af',
                              }}>
                                {s.location_name ?? '—'}
                              </td>

                              {/* Risk Level badge */}
                              <td>
                                <Badge label={s.risk_level?.replace('_', ' ') ?? '—'} color={lvlColor} />
                              </td>

                              {/* Score bar */}
                              <td>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                  <div style={{
                                    width: 64, height: 6,
                                    background: '#1f2937', borderRadius: 3, overflow: 'hidden',
                                  }}>
                                    <div style={{
                                      width: `${pct}%`, height: '100%',
                                      background: lvlColor, borderRadius: 3,
                                      transition: 'width 0.4s ease',
                                    }} />
                                  </div>
                                  <span style={{
                                    fontFamily: 'Space Mono, monospace', fontSize: 11,
                                    color: lvlColor,
                                  }}>{score.toFixed(1)}</span>
                                </div>
                              </td>

                              {/* R₀ */}
                              <td style={{ fontFamily: 'Space Mono, monospace', fontSize: 11,
                                color: s.r_naught ? '#f9fafb' : '#4b5563' }}>
                                {s.r_naught ? parseFloat(s.r_naught).toFixed(2) : '—'}
                              </td>

                              {/* CFR */}
                              <td style={{ fontFamily: 'Space Mono, monospace', fontSize: 11,
                                color: s.case_fatality_rate ? '#f9fafb' : '#4b5563' }}>
                                {s.case_fatality_rate
                                  ? `${parseFloat(s.case_fatality_rate).toFixed(1)}%`
                                  : '—'}
                              </td>

                              {/* Assessment date */}
                              <td style={{ fontFamily: 'Space Mono, monospace', fontSize: 10,
                                color: '#6b7280', whiteSpace: 'nowrap' }}>
                                {s.assessment_date
                                  ? new Date(s.assessment_date).toLocaleDateString('en-NA', {
                                      day: '2-digit', month: 'short', year: 'numeric',
                                    })
                                  : '—'}
                              </td>

                              {/* Action */}
                              <td>
                                <button
                                  onClick={e => { e.stopPropagation(); navigate('/dashboard/risk') }}
                                  style={{
                                    background: 'transparent', border: '1px solid #1f2937',
                                    color: '#9ca3af', borderRadius: 4, padding: '4px 10px',
                                    fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11,
                                    cursor: 'pointer',
                                  }}
                                  onMouseEnter={e => {
                                    e.currentTarget.style.borderColor = '#3b82f6'
                                    e.currentTarget.style.color = '#3b82f6'
                                  }}
                                  onMouseLeave={e => {
                                    e.currentTarget.style.borderColor = '#1f2937'
                                    e.currentTarget.style.color = '#9ca3af'
                                  }}
                                >View</button>
                              </td>
                            </motion.tr>
                          )
                        })
                  }
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{
              display: 'flex', justifyContent: 'flex-end', gap: 8,
              marginTop: 14, alignItems: 'center',
            }}>
              <span style={{
                fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: '#6b7280',
              }}>
                Page {page} of {totalPages} · {count} total
              </span>
              <button
                disabled={page <= 1}
                onClick={() => setPage(p => p - 1)}
                style={{
                  background: '#111827', border: '1px solid #1f2937',
                  color: page <= 1 ? '#374151' : '#f9fafb',
                  borderRadius: 4, padding: '5px 12px', fontSize: 12,
                  cursor: page <= 1 ? 'default' : 'pointer',
                }}
              >← Prev</button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage(p => p + 1)}
                style={{
                  background: '#111827', border: '1px solid #1f2937',
                  color: page >= totalPages ? '#374151' : '#f9fafb',
                  borderRadius: 4, padding: '5px 12px', fontSize: 12,
                  cursor: page >= totalPages ? 'default' : 'pointer',
                }}
              >Next →</button>
            </div>
          )}
        </motion.div>

        {/* ── Right Sidebar ── */}
        <div className="ra-sidebar" style={{ width: 300, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Thresholds */}
          <motion.div {...fadeUp(0.3)}>
            <div style={{
              background: '#111827', border: '1px solid #1f2937',
              borderRadius: 8, overflow: 'hidden',
            }}>
              <div style={{
                padding: '14px 18px', borderBottom: '1px solid #1f2937',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <span style={{
                  fontFamily: 'Space Mono, monospace', fontSize: 9,
                  letterSpacing: '0.15em', textTransform: 'uppercase', color: '#6b7280',
                }}>Active Thresholds</span>
                <span style={{
                  fontFamily: 'Space Mono, monospace', fontSize: 9,
                  color: '#374151', background: '#1f2937', borderRadius: 10,
                  padding: '2px 8px',
                }}>{thresholds.length}</span>
              </div>

              {thresholdsLoading
                ? Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} style={{ padding: '14px 18px', borderBottom: '1px solid #1f2937' }}>
                    <Shimmer w="70%" h={12} />
                    <div style={{ marginTop: 8 }}><Shimmer w="50%" h={10} /></div>
                  </div>
                ))
                : thresholds.length === 0
                  ? <div style={{
                      padding: 24, color: '#6b7280', fontSize: 12,
                      fontFamily: 'IBM Plex Sans, sans-serif', textAlign: 'center',
                    }}>No thresholds configured.</div>
                  : thresholds.map((t, i) => (
                    <motion.div
                      key={t.id}
                      initial={{ opacity: 0, x: 8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.3 + i * 0.05 }}
                      style={{
                        padding: '13px 18px',
                        borderBottom: i < thresholds.length - 1 ? '1px solid #1f2937' : 'none',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between',
                        alignItems: 'flex-start', gap: 8 }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
                            color: '#f9fafb', fontWeight: 500, marginBottom: 3,
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          }}>
                            {t.name}
                          </div>
                          <div style={{
                            fontFamily: 'Space Mono, monospace', fontSize: 9,
                            color: '#6b7280', marginBottom: 6,
                          }}>
                            {thresholdTypeLabel(t)}
                            {t.disease_code ? ` · ${t.disease_code}` : ''}
                          </div>
                          {/* Show the three tier values */}
                          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                            <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9,
                              color: '#f59e0b' }}>W: {parseFloat(t.warning_value).toFixed(1)}</span>
                            <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9,
                              color: '#f97316' }}>A: {parseFloat(t.alert_value).toFixed(1)}</span>
                            <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9,
                              color: '#ef4444' }}>C: {parseFloat(t.critical_value).toFixed(1)}</span>
                          </div>
                        </div>
                        {t.location_name && (
                          <div style={{
                            fontFamily: 'Space Mono, monospace', fontSize: 9,
                            color: '#6b7280', textAlign: 'right', flexShrink: 0,
                          }}>{t.location_name}</div>
                        )}
                      </div>
                    </motion.div>
                  ))
              }
            </div>
          </motion.div>

          {/* Trending Threats */}
          {(threats.length > 0 || statsLoading) && (
            <motion.div {...fadeUp(0.35)}>
              <div style={{
                background: '#111827', border: '1px solid #1f2937',
                borderRadius: 8, overflow: 'hidden',
              }}>
                <div style={{
                  padding: '14px 18px', borderBottom: '1px solid #1f2937',
                  fontFamily: 'Space Mono, monospace', fontSize: 9,
                  letterSpacing: '0.15em', textTransform: 'uppercase', color: '#6b7280',
                }}>Trending Threats</div>

                {statsLoading
                  ? Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} style={{ padding: '12px 18px', borderBottom: '1px solid #1f2937' }}>
                      <Shimmer w="80%" h={12} />
                    </div>
                  ))
                  : threats.map((threat, i) => {
                    const threatColors = {
                      EXTREME: '#dc2626', SEVERE: '#ef4444',
                      HIGH: '#f97316', MODERATE: '#f59e0b', LOW: '#10b981',
                    }
                    const tc = threatColors[threat.threat_level] ?? '#9ca3af'
                    return (
                      <div key={i} style={{
                        padding: '12px 18px',
                        borderBottom: i < threats.length - 1 ? '1px solid #1f2937' : 'none',
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      }}>
                        <div style={{
                          fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12,
                          color: '#f9fafb', flex: 1, minWidth: 0,
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>{threat.disease_name}</div>
                        <Badge
                          label={threat.threat_level}
                          color={tc}
                        />
                      </div>
                    )
                  })
                }
              </div>
            </motion.div>
          )}

          {/* High Risk Locations */}
          {(stats?.high_risk_locations?.length > 0) && (
            <motion.div {...fadeUp(0.4)}>
              <div style={{
                background: '#111827', border: '1px solid #1f2937',
                borderRadius: 8, overflow: 'hidden',
              }}>
                <div style={{
                  padding: '14px 18px', borderBottom: '1px solid #1f2937',
                  fontFamily: 'Space Mono, monospace', fontSize: 9,
                  letterSpacing: '0.15em', textTransform: 'uppercase', color: '#6b7280',
                }}>High Risk Locations</div>
                {stats.high_risk_locations.map((loc, i) => (
                  <div key={i} style={{
                    padding: '10px 18px',
                    borderBottom: i < stats.high_risk_locations.length - 1 ? '1px solid #1f2937' : 'none',
                    display: 'flex', alignItems: 'center', gap: 10,
                  }}>
                    <div style={{
                      width: 6, height: 6, borderRadius: '50%',
                      background: '#ef4444', flexShrink: 0,
                    }} />
                    <span style={{
                      fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12,
                      color: '#d1d5db',
                    }}>{loc}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

        </div>
      </div>
    </div>
  )
}