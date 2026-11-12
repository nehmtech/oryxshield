/**
 * Risk Alerts — OryxShield
 * ===================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Fixes applied vs original:
 *   1. useToast() returns {success,error,...} — no .toast sub-key
 *   2. location field in AlertListSerializer is location_name (SerializerMethodField)
 *   3. riskApi.acknowledgeAlert / resolveAlert / closeAlert — correct action endpoints
 *      POST /risk/alerts/{id}/acknowledge/  → { notes: '' }
 *      POST /risk/alerts/{id}/resolve/      → { resolution_notes: '' }
 *      POST /risk/alerts/{id}/close/        → {}
 *   4. Bulk-acknowledge via riskApi.bulkAcknowledgeAlerts (POST /risk/alerts/bulk_acknowledge/)
 *   5. Stats bar: active, unacknowledged, critical counts — from /risk/dashboard/overview/
 *   6. WS new_alert event now reads last?.type === 'new_alert' (matches signals.py send_alert shape)
 *   7. Responsive layout
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { riskApi, extractError } from '../../services/api'
import { useToast } from '../../context/ToastContext'
import { useAlertStream } from '../../hooks/ws/useAlertStream'

// ─── Design tokens ────────────────────────────────────────────────────────────
const SEVERITY_COLORS = {
  INFO:      '#3b82f6',
  WARNING:   '#f59e0b',
  ALERT:     '#f97316',
  CRITICAL:  '#ef4444',
  EMERGENCY: '#dc2626',
}

const STATUS_COLORS = {
  ACTIVE:       '#ef4444',
  ACKNOWLEDGED: '#f59e0b',
  RESOLVED:     '#10b981',
  CLOSED:       '#6b7280',
}

const ALERT_TYPE_COLORS = {
  OUTBREAK:   '#ef4444',
  EPIDEMIC:   '#dc2626',
  THRESHOLD:  '#f59e0b',
  ESCALATION: '#f97316',
  PREDICTION: '#3b82f6',
  ANOMALY:    '#a78bfa',
  CAPACITY:   '#06b6d4',
  SYSTEM:     '#6b7280',
}

const SEVERITIES = ['ALL', 'INFO', 'WARNING', 'ALERT', 'CRITICAL', 'EMERGENCY']
const STATUSES   = ['ALL', 'ACTIVE', 'ACKNOWLEDGED', 'RESOLVED', 'CLOSED']

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

function FilterPills({ options, active, colors, onChange }) {
  return (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      {options.map(opt => {
        const isActive = active === opt
        const color    = opt === 'ALL' ? '#3b82f6' : (colors[opt] ?? '#9ca3af')
        return (
          <button key={opt} onClick={() => onChange(opt)} style={{
            border: isActive ? `1px solid ${color}` : '1px solid #1f2937',
            background: isActive ? color + '22' : 'transparent',
            color: isActive ? color : '#9ca3af',
            borderRadius: 20, padding: '4px 14px',
            fontFamily: 'Space Mono, monospace', fontSize: 10,
            letterSpacing: '0.1em', textTransform: 'uppercase',
            cursor: 'pointer', transition: 'all 0.15s',
          }}>
            {opt.replace('_', ' ')}
          </button>
        )
      })}
    </div>
  )
}

// ─── Alert Row ────────────────────────────────────────────────────────────────
function AlertRow({ alert, onAcknowledge, onResolve, onClose, optimisticStatus }) {
  const [expanded, setExpanded] = useState(false)
  const [isNew, setIsNew]       = useState(alert._isNew ?? false)

  const status    = optimisticStatus ?? alert.status
  const sevColor  = SEVERITY_COLORS[alert.severity]   ?? '#9ca3af'
  const statColor = STATUS_COLORS[status]             ?? '#9ca3af'
  const typeColor = ALERT_TYPE_COLORS[alert.alert_type] ?? '#6b7280'

  useEffect(() => {
    if (!isNew) return
    const t = setTimeout(() => setIsNew(false), 2500)
    return () => clearTimeout(t)
  }, [isNew])

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        borderBottom: '1px solid #1f2937',
        borderLeft: isNew ? '3px solid #3b82f6' : '3px solid transparent',
        transition: 'border-left 0.4s ease',
      }}
    >
      {/* ── Main collapsed row ── */}
      <div
        onClick={() => setExpanded(e => !e)}
        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', cursor: 'pointer' }}
        onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
      >
        {/* Severity dot */}
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: sevColor, flexShrink: 0,
          boxShadow: `0 0 6px ${sevColor}66`,
        }} />

        {/* Content */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
            <span style={{
              fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
              fontWeight: 500, color: '#f9fafb',
            }}>
              {alert.title ?? 'Untitled Alert'}
            </span>
            <Badge label={alert.severity}   color={sevColor} />
            <Badge label={status}           color={statColor} />
            {alert.alert_type && (
              <Badge label={alert.alert_type.replace('_', ' ')} color={typeColor} />
            )}
          </div>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {/* location_name is the correct field from AlertListSerializer */}
            {alert.location_name && (
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: '#6b7280' }}>
                📍 {alert.location_name}
              </span>
            )}
            {alert.disease_name && (
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: '#6b7280' }}>
                {alert.disease_name}
                {alert.disease_code && ` (${alert.disease_code})`}
              </span>
            )}
            {alert.triggered_at && (
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: '#4b5563' }}>
                {new Date(alert.triggered_at).toLocaleString('en-NA', {
                  dateStyle: 'short', timeStyle: 'short',
                })}
              </span>
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }} onClick={e => e.stopPropagation()}>
          {status === 'ACTIVE' && (
            <button
              onClick={() => onAcknowledge(alert.id)}
              style={{
                background: '#f59e0b18', border: '1px solid #f59e0b30', color: '#f59e0b',
                borderRadius: 4, padding: '4px 10px',
                fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, cursor: 'pointer',
              }}
              onMouseEnter={e => e.currentTarget.style.background = '#f59e0b28'}
              onMouseLeave={e => e.currentTarget.style.background = '#f59e0b18'}
            >Acknowledge</button>
          )}
          {(status === 'ACTIVE' || status === 'ACKNOWLEDGED') && (
            <button
              onClick={() => onResolve(alert.id)}
              style={{
                background: '#10b98118', border: '1px solid #10b98130', color: '#10b981',
                borderRadius: 4, padding: '4px 10px',
                fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, cursor: 'pointer',
              }}
              onMouseEnter={e => e.currentTarget.style.background = '#10b98128'}
              onMouseLeave={e => e.currentTarget.style.background = '#10b98118'}
            >Resolve</button>
          )}
          {status === 'RESOLVED' && (
            <button
              onClick={() => onClose(alert.id)}
              style={{
                background: 'transparent', border: '1px solid #1f2937', color: '#6b7280',
                borderRadius: 4, padding: '4px 10px',
                fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, cursor: 'pointer',
              }}
              onMouseEnter={e => e.currentTarget.style.color = '#9ca3af'}
              onMouseLeave={e => e.currentTarget.style.color = '#6b7280'}
            >Close</button>
          )}
        </div>

        {/* Expand caret */}
        <span style={{
          color: '#6b7280', fontSize: 10, fontFamily: 'Space Mono, monospace',
          transform: expanded ? 'rotate(180deg)' : 'rotate(0)',
          transition: 'transform 0.2s', flexShrink: 0,
        }}>▼</span>
      </div>

      {/* ── Expanded detail ── */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{
              padding: '14px 16px 16px 36px',
              background: '#0d1420', borderTop: '1px solid #1f2937',
            }}>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                gap: 20,
              }}>
                {alert.description && (
                  <div>
                    <div style={{
                      fontFamily: 'Space Mono, monospace', fontSize: 9,
                      letterSpacing: '0.15em', textTransform: 'uppercase',
                      color: '#6b7280', marginBottom: 6,
                    }}>Description</div>
                    <div style={{
                      fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12,
                      color: '#9ca3af', lineHeight: 1.65,
                    }}>{alert.description}</div>
                  </div>
                )}
                {alert.recommendation && (
                  <div>
                    <div style={{
                      fontFamily: 'Space Mono, monospace', fontSize: 9,
                      letterSpacing: '0.15em', textTransform: 'uppercase',
                      color: '#6b7280', marginBottom: 6,
                    }}>Recommendations</div>
                    <div style={{
                      fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12,
                      color: '#9ca3af', lineHeight: 1.65,
                    }}>
                      {alert.recommendation.split(' • ').map((rec, i) => (
                        <div key={i} style={{ marginBottom: 4 }}>• {rec}</div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Meta row */}
              <div style={{
                marginTop: 14, paddingTop: 12, borderTop: '1px solid #1f2937',
                display: 'flex', gap: 24, flexWrap: 'wrap',
              }}>
                {alert.expires_at && (
                  <div>
                    <div style={{
                      fontFamily: 'Space Mono, monospace', fontSize: 8,
                      color: '#4b5563', textTransform: 'uppercase',
                      letterSpacing: '0.12em', marginBottom: 3,
                    }}>Expires</div>
                    <span style={{
                      fontFamily: 'Space Mono, monospace', fontSize: 10, color: '#6b7280',
                    }}>
                      {new Date(alert.expires_at).toLocaleString('en-NA', {
                        dateStyle: 'short', timeStyle: 'short',
                      })}
                    </span>
                  </div>
                )}
                {alert.acknowledged_at && (
                  <div>
                    <div style={{
                      fontFamily: 'Space Mono, monospace', fontSize: 8,
                      color: '#4b5563', textTransform: 'uppercase',
                      letterSpacing: '0.12em', marginBottom: 3,
                    }}>Acknowledged</div>
                    <span style={{
                      fontFamily: 'Space Mono, monospace', fontSize: 10, color: '#6b7280',
                    }}>
                      {new Date(alert.acknowledged_at).toLocaleString('en-NA', {
                        dateStyle: 'short', timeStyle: 'short',
                      })}
                    </span>
                  </div>
                )}
                <div>
                  <div style={{
                    fontFamily: 'Space Mono, monospace', fontSize: 8,
                    color: '#4b5563', textTransform: 'uppercase',
                    letterSpacing: '0.12em', marginBottom: 3,
                  }}>Notification Sent</div>
                  <Badge
                    label={alert.notification_sent ? 'Yes' : 'No'}
                    color={alert.notification_sent ? '#10b981' : '#6b7280'}
                  />
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ─── Stats pill strip ─────────────────────────────────────────────────────────
function StatsStrip({ stats, loading }) {
  const items = [
    { label: 'Active',         value: stats?.active_alerts,          color: '#ef4444' },
    { label: 'Unacknowledged', value: stats?.unacknowledged_alerts,   color: '#f59e0b' },
    { label: 'Critical',       value: stats?.critical_risks,          color: '#dc2626' },
    { label: 'Avg Score',      value: stats?.average_risk_score != null
        ? parseFloat(stats.average_risk_score).toFixed(1)
        : undefined,                                                    color: '#3b82f6' },
  ]
  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
      {items.map(({ label, value, color }) => (
        <div key={label} style={{
          background: '#111827', border: '1px solid #1f2937', borderRadius: 6,
          padding: '8px 14px', display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span style={{
            fontFamily: 'Bebas Neue, sans-serif', fontSize: 22,
            color: loading ? '#1f2937' : color, lineHeight: 1,
            minWidth: 28, textAlign: 'right',
          }}>
            {loading ? '—' : (value ?? '—')}
          </span>
          <span style={{
            fontFamily: 'Space Mono, monospace', fontSize: 9,
            letterSpacing: '0.12em', textTransform: 'uppercase', color: '#6b7280',
          }}>{label}</span>
        </div>
      ))}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function RiskAlerts() {
  const { error: toastError, success: toastSuccess } = useToast()
  const { data: wsMessages } = useAlertStream()

  const [alerts, setAlerts]               = useState([])
  const [loading, setLoading]             = useState(true)
  const [error, setError]                 = useState(null)
  const [count, setCount]                 = useState(0)
  const [page, setPage]                   = useState(1)
  const [sevFilter, setSevFilter]         = useState('ALL')
  const [statFilter, setStatFilter]       = useState('ALL')
  const [optimisticStatuses, setOptimisticStatuses] = useState({})

  // Dashboard overview stats for the strip
  const [stats, setStats]               = useState(null)
  const [statsLoading, setStatsLoading] = useState(true)

  // Bulk select
  const [selected, setSelected]         = useState(new Set())

  // ── Fetch alerts ────────────────────────────────────────────────────────────
  const fetchAlerts = useCallback(async (pg = 1, sev = sevFilter, stat = statFilter) => {
    setLoading(true)
    setError(null)
    try {
      const params = { page: pg, page_size: 20 }
      if (sev  !== 'ALL') params.severity = sev
      if (stat !== 'ALL') params.status   = stat
      const res = await riskApi.listAlerts(params)
      setAlerts(res.data.results ?? [])
      setCount(res.data.count ?? 0)
    } catch (err) {
      const msg = extractError(err)
      setError(msg)
      toastError(msg)
    } finally {
      setLoading(false)
    }
  }, [sevFilter, statFilter])

  // ── Fetch stats strip ───────────────────────────────────────────────────────
  const fetchStats = useCallback(async () => {
    try {
      const res = await riskApi.riskDashboard()
      setStats(res.data)
    } catch (_) {
      // stats strip is non-critical
    } finally {
      setStatsLoading(false)
    }
  }, [])

  useEffect(() => { fetchStats() }, [])
  useEffect(() => { fetchAlerts(page, sevFilter, statFilter) }, [page, sevFilter, statFilter])

  // WS: prepend new alerts
  useEffect(() => {
    if (!wsMessages?.length) return
    const last = wsMessages[0]
    // signals.py send_alert shape: { type: 'new_alert', alert_id, title, severity, location }
    if (last?.type === 'new_alert') {
      // Fetch alert detail and prepend
      riskApi.getAlert(last.alert_id).then(res => {
        setAlerts(prev => {
          const exists = prev.some(a => a.id === res.data.id)
          if (exists) return prev
          return [{ ...res.data, _isNew: true }, ...prev.slice(0, 19)]
        })
        setCount(c => c + 1)
      }).catch(() => {
        // fallback: just refetch first page
        fetchAlerts(1, sevFilter, statFilter)
      })
    }
  }, [wsMessages])

  // ── Optimistic handlers ─────────────────────────────────────────────────────
  const handleAcknowledge = async (id) => {
    setOptimisticStatuses(prev => ({ ...prev, [id]: 'ACKNOWLEDGED' }))
    try {
      // POST /risk/alerts/{id}/acknowledge/ → AlertAcknowledgeSerializer: { notes: '' }
      await riskApi.acknowledgeAlert(id, { notes: '' })
      toastSuccess('Alert acknowledged')
    } catch (err) {
      setOptimisticStatuses(prev => { const n = { ...prev }; delete n[id]; return n })
      toastError(extractError(err))
    }
  }

  const handleResolve = async (id) => {
    setOptimisticStatuses(prev => ({ ...prev, [id]: 'RESOLVED' }))
    try {
      // POST /risk/alerts/{id}/resolve/ → AlertResolveSerializer: { resolution_notes, actions_taken }
      await riskApi.resolveAlert(id, { resolution_notes: '', actions_taken: [] })
      toastSuccess('Alert resolved')
    } catch (err) {
      setOptimisticStatuses(prev => { const n = { ...prev }; delete n[id]; return n })
      toastError(extractError(err))
    }
  }

  const handleClose = async (id) => {
    setOptimisticStatuses(prev => ({ ...prev, [id]: 'CLOSED' }))
    try {
      // POST /risk/alerts/{id}/close/
      await riskApi.closeAlert(id)
      toastSuccess('Alert closed')
    } catch (err) {
      setOptimisticStatuses(prev => { const n = { ...prev }; delete n[id]; return n })
      toastError(extractError(err))
    }
  }

  const handleBulkAcknowledge = async () => {
    if (selected.size === 0) return
    try {
      await riskApi.bulkAcknowledgeAlerts({ ids: Array.from(selected) })
      toastSuccess(`${selected.size} alerts acknowledged`)
      setSelected(new Set())
      fetchAlerts(page, sevFilter, statFilter)
    } catch (err) {
      toastError(extractError(err))
    }
  }

  const toggleSelect = (id) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const totalPages = Math.ceil(count / 20)

  return (
    <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', color: '#f9fafb', minHeight: '100vh' }}>
      <style>{`
        @keyframes ra-shimmer {
          0%   { background-position: 200% 0 }
          100% { background-position: -200% 0 }
        }
      `}</style>

      {/* ── Header ── */}
      <motion.div {...fadeUp(0)} style={{ marginBottom: 24 }}>
        <div style={{
          fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.2em',
          textTransform: 'uppercase', color: '#3b82f6', marginBottom: 6,
        }}>Intelligence · Risk Alerts</div>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
          gap: 12, flexWrap: 'wrap' }}>
          <h1 style={{
            fontFamily: 'Bebas Neue, sans-serif', fontSize: 36, margin: 0,
            letterSpacing: '0.04em', color: '#f9fafb',
          }}>Risk Alerts</h1>
          {selected.size > 0 && (
            <button
              onClick={handleBulkAcknowledge}
              style={{
                background: '#f59e0b18', border: '1px solid #f59e0b30', color: '#f59e0b',
                borderRadius: 4, padding: '8px 16px', fontSize: 13,
                fontFamily: 'IBM Plex Sans, sans-serif', cursor: 'pointer',
              }}
            >
              Acknowledge {selected.size} selected
            </button>
          )}
        </div>
      </motion.div>

      {/* ── Stats strip ── */}
      <motion.div {...fadeUp(0.04)} style={{ marginBottom: 22 }}>
        <StatsStrip stats={stats} loading={statsLoading} />
      </motion.div>

      {/* ── Filters ── */}
      <motion.div {...fadeUp(0.07)} style={{
        display: 'flex', gap: 20, marginBottom: 20,
        flexWrap: 'wrap', alignItems: 'flex-start',
      }}>
        <div>
          <div style={{
            fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em',
            textTransform: 'uppercase', color: '#6b7280', marginBottom: 8,
          }}>Severity</div>
          <FilterPills
            options={SEVERITIES} active={sevFilter} colors={SEVERITY_COLORS}
            onChange={v => { setSevFilter(v); setPage(1) }}
          />
        </div>
        <div>
          <div style={{
            fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em',
            textTransform: 'uppercase', color: '#6b7280', marginBottom: 8,
          }}>Status</div>
          <FilterPills
            options={STATUSES} active={statFilter} colors={STATUS_COLORS}
            onChange={v => { setStatFilter(v); setPage(1) }}
          />
        </div>
      </motion.div>

      {/* ── Alerts list ── */}
      <motion.div
        {...fadeUp(0.12)}
        style={{
          background: '#111827', border: '1px solid #1f2937',
          borderRadius: 8, overflow: 'hidden',
        }}
      >
        {/* List header */}
        <div style={{
          padding: '10px 16px', borderBottom: '1px solid #1f2937',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              fontFamily: 'Space Mono, monospace', fontSize: 9,
              letterSpacing: '0.15em', textTransform: 'uppercase', color: '#6b7280',
            }}>Alerts</span>
            <span style={{
              fontFamily: 'Space Mono, monospace', fontSize: 9,
              color: '#374151', background: '#1f2937',
              borderRadius: 10, padding: '2px 8px',
            }}>{count}</span>
          </div>
          {!loading && alerts.length > 0 && statFilter !== 'RESOLVED' && statFilter !== 'CLOSED' && (
            <button
              onClick={() => fetchAlerts(page, sevFilter, statFilter)}
              style={{
                background: 'transparent', border: 'none', color: '#6b7280',
                fontFamily: 'Space Mono, monospace', fontSize: 9,
                letterSpacing: '0.1em', textTransform: 'uppercase', cursor: 'pointer',
              }}
            >↻ Refresh</button>
          )}
        </div>

        {/* Rows */}
        {loading
          ? Array.from({ length: 5 }).map((_, i) => (
            <div key={i} style={{
              padding: '16px', borderBottom: '1px solid #1f2937',
              display: 'flex', gap: 12, alignItems: 'center',
            }}>
              <Shimmer w={8} h={8} />
              <div style={{ flex: 1 }}>
                <Shimmer w="45%" h={13} />
                <div style={{ marginTop: 8 }}><Shimmer w="28%" h={10} /></div>
              </div>
              <Shimmer w={80} h={28} />
            </div>
          ))
          : error
            ? (
              <div style={{
                padding: 40, textAlign: 'center',
                color: '#ef4444', fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
              }}>
                {error}
                <button
                  onClick={() => fetchAlerts(page)}
                  style={{
                    marginLeft: 12, background: '#3b82f6', color: '#fff',
                    border: 'none', borderRadius: 4, padding: '6px 14px',
                    fontSize: 12, cursor: 'pointer',
                  }}
                >Retry</button>
              </div>
            )
            : alerts.length === 0
              ? (
                <div style={{
                  padding: 52, textAlign: 'center',
                  color: '#6b7280', fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
                }}>
                  No alerts match the current filters.
                </div>
              )
              : alerts.map(alert => (
                <AlertRow
                  key={alert.id}
                  alert={alert}
                  onAcknowledge={handleAcknowledge}
                  onResolve={handleResolve}
                  onClose={handleClose}
                  optimisticStatus={optimisticStatuses[alert.id]}
                />
              ))
        }
      </motion.div>

      {/* ── Pagination ── */}
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
    </div>
  )
}