/**
 * Dashboard — OryxShield
 * =================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Fully responsive operational overview dashboard.
 * Pulls data from: riskApi, responseApi, surveillanceApi,
 *   operationsApi, analyticsApi, coreApi, coordinationApi, resourcesApi
 *
 * API calls aligned to corrected api.js:
 *   - riskApi.riskDashboardOverview()          → /risk/dashboard/overview/
 *   - riskApi.listRiskScores(params)            → /risk/scores/
 *   - riskApi.criticalAlerts(params)            → /risk/alerts/critical/
 *   - responseApi.getDashboard()                → /response/dashboard/overview/
 *   - responseApi.activeActivations()           → /response/activations/active/
 *   - surveillanceApi.surveillanceDashboard()   → /surveillance/dashboard/
 *   - surveillanceApi.listHotspots(params)      → /surveillance/hotspots/
 *   - operationsApi.getDashboard()              → /operations/dashboard/overview/
 *   - analyticsApi.getDashboardOverview()       → /analytics/overview/overview/
 *   - coreApi.unreadCount()                     → /notifications/unread_count/
 *   - coordinationApi.coordinationDashboard()   → /coordination/dashboard/overview/
 *   - resourcesApi.resourcesDashboard()         → /resources/dashboard/overview/
 *
 * Design tokens: bg #0a0f1e, surface #111827, surfaceHigh #151e2e,
 *   border #1f2937, accent #3b82f6, danger #ef4444, warning #f59e0b,
 *   success #10b981, text #f9fafb, textSub #9ca3af, textMuted #6b7280
 * Fonts: Bebas Neue (headings), Space Mono (badges/labels), IBM Plex Sans (body)
 * Inline styles only — no Tailwind, no CSS modules
 * @keyframes prefixed db- to avoid collisions
 * Hover via onMouseEnter/Leave (no :hover CSS)
 * useAlertStream → {data, status} from src/hooks/ws/useAlertStream
 */

import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { formatDistanceToNow } from 'date-fns'
import {
  riskApi, responseApi, surveillanceApi, operationsApi,
  analyticsApi, coreApi, coordinationApi, resourcesApi,
} from '../../services/api'
import { useToast } from '../../context/ToastContext'
import { useAuth }  from '../../context/AuthContext'
import { useAlertStream }     from '../../hooks/ws/useAlertStream'
import { useDashboardStream } from '../../hooks/ws/useDashboardStream'

// ─── Design tokens ─────────────────────────────────────────────────────────────
const C = {
  bg:          '#0a0f1e',
  surface:     '#111827',
  surfaceHigh: '#151e2e',
  border:      '#1f2937',
  accent:      '#3b82f6',
  danger:      '#ef4444',
  warning:     '#f59e0b',
  success:     '#10b981',
  purple:      '#a78bfa',
  text:        '#f9fafb',
  textSub:     '#9ca3af',
  textMuted:   '#6b7280',
}

const gridBg = {
  backgroundImage: `
    linear-gradient(rgba(59,130,246,0.018) 1px, transparent 1px),
    linear-gradient(90deg, rgba(59,130,246,0.018) 1px, transparent 1px)
  `,
  backgroundSize: '48px 48px',
}

const fadeUp = (delay = 0) => ({
  initial:    { opacity: 0, y: 14 },
  animate:    { opacity: 1, y: 0 },
  transition: { duration: 0.3, ease: 'easeOut', delay },
})

// ─── Africa map projection ──────────────────────────────────────────────────────
const MAP_W = 700, MAP_H = 420
const LAT_MIN = -35, LAT_MAX = 38, LNG_MIN = -18, LNG_MAX = 52

function latLngToSvg(lat, lng) {
  return {
    x: ((lng - LNG_MIN) / (LNG_MAX - LNG_MIN)) * MAP_W,
    y: ((LAT_MAX - lat) / (LAT_MAX - LAT_MIN)) * MAP_H,
  }
}

function scoreToColor(score) {
  const s = Number(score)
  if (s >= 75) return C.danger
  if (s >= 50) return C.warning
  return C.success
}

// ─── Shared micro components ───────────────────────────────────────────────────

function Badge({ label, color = C.accent }) {
  return (
    <span style={{
      background:    `${color}18`,
      border:        `1px solid ${color}30`,
      color,
      borderRadius:  2,
      padding:       '2px 8px',
      fontFamily:    'Space Mono, monospace',
      fontSize:      9,
      letterSpacing: '0.14em',
      textTransform: 'uppercase',
      whiteSpace:    'nowrap',
    }}>{label}</span>
  )
}

function Shimmer({ height = 20, radius = 4, style = {} }) {
  return (
    <div style={{
      width:          '100%',
      height,
      borderRadius:   radius,
      background:     `linear-gradient(90deg,${C.surface} 25%,${C.surfaceHigh} 50%,${C.surface} 75%)`,
      backgroundSize: '200% 100%',
      animation:      'db-shimmer 1.5s infinite',
      ...style,
    }} />
  )
}

function RetryBtn({ onClick }) {
  const [hov, setHov] = useState(false)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background:    hov ? C.surfaceHigh : 'transparent',
        border:        `1px solid ${C.border}`,
        color:         C.textSub,
        borderRadius:  4,
        cursor:        'pointer',
        fontFamily:    'Space Mono, monospace',
        fontSize:      9,
        fontWeight:    700,
        letterSpacing: '0.14em',
        textTransform: 'uppercase',
        padding:       '5px 12px',
        transition:    'background 0.15s',
      }}
    >Retry</button>
  )
}

function SectionLabel({ children }) {
  return (
    <div style={{
      fontFamily:    'Space Mono, monospace',
      fontSize:      9,
      color:         C.textMuted,
      letterSpacing: '0.14em',
      textTransform: 'uppercase',
      marginBottom:  12,
    }}>{children}</div>
  )
}

function Panel({ children, style = {} }) {
  return (
    <div style={{
      background:   C.surface,
      border:       `1px solid ${C.border}`,
      borderRadius: 8,
      ...style,
    }}>{children}</div>
  )
}

function PanelHeader({ title, right }) {
  return (
    <div style={{
      display:       'flex',
      alignItems:    'center',
      justifyContent:'space-between',
      padding:       '14px 18px',
      borderBottom:  `1px solid ${C.border}`,
    }}>
      <span style={{
        fontFamily:    'Space Mono, monospace',
        fontSize:      9,
        color:         C.textMuted,
        letterSpacing: '0.14em',
        textTransform: 'uppercase',
      }}>{title}</span>
      {right}
    </div>
  )
}

function EmptyState({ icon, label }) {
  return (
    <div style={{
      display:        'flex',
      flexDirection:  'column',
      alignItems:     'center',
      justifyContent: 'center',
      gap:            12,
      padding:        '36px 20px',
    }}>
      {icon}
      <span style={{
        fontFamily:    'Space Mono, monospace',
        fontSize:      9,
        color:         C.textMuted,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
      }}>{label}</span>
    </div>
  )
}

// ─── WS reconnect indicator ─────────────────────────────────────────────────────
function WsIndicator({ status }) {
  if (status === 'open') return null
  return (
    <div style={{
      display:       'flex',
      alignItems:    'center',
      gap:           6,
      padding:       '4px 12px',
      background:    'rgba(245,158,11,0.07)',
      border:        '1px solid rgba(245,158,11,0.18)',
      borderRadius:  3,
      fontFamily:    'Space Mono, monospace',
      fontSize:      9,
      color:         C.warning,
      letterSpacing: '0.1em',
      marginBottom:  8,
    }}>
      <span style={{ animation: 'db-spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
      RECONNECTING…
    </div>
  )
}

// ─── Stat Card ──────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, color = C.accent, loading, error, onRetry, to }) {
  const inner = (
    <div style={{
      background:   C.surface,
      border:       `1px solid ${C.border}`,
      borderRadius: 8,
      padding:      '20px 22px',
      flex:         1,
      minWidth:     0,
      cursor:       to ? 'pointer' : 'default',
      transition:   'border-color 0.15s',
    }}>
      {loading ? (
        <>
          <Shimmer height={44} style={{ marginBottom: 10, width: '60%' }} />
          <Shimmer height={10} style={{ width: '40%' }} />
        </>
      ) : error ? (
        <div style={{ textAlign: 'center' }}>
          <div style={{ color: C.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, marginBottom: 8 }}>
            Failed
          </div>
          <RetryBtn onClick={onRetry} />
        </div>
      ) : (
        <>
          <div style={{
            fontFamily: 'Bebas Neue, sans-serif',
            fontSize:   46,
            color,
            lineHeight: 1,
            letterSpacing: '0.02em',
          }}>{value ?? '—'}</div>
          <div style={{
            fontFamily:    'Space Mono, monospace',
            fontSize:      9,
            color:         C.textMuted,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            marginTop:     6,
          }}>{label}</div>
          {sub && (
            <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, color: C.textSub, marginTop: 4 }}>
              {sub}
            </div>
          )}
        </>
      )}
    </div>
  )

  if (to) {
    return (
      <Link to={to} style={{ flex: 1, minWidth: 0, textDecoration: 'none', display: 'flex' }}>
        {inner}
      </Link>
    )
  }
  return <div style={{ flex: 1, minWidth: 0, display: 'flex' }}>{inner}</div>
}

// ─── Live Alert Feed ────────────────────────────────────────────────────────────
const ALERT_LEVEL_COLORS = {
  EMERGENCY: '#dc2626',
  CRITICAL:  C.danger,
  ALERT:     C.warning,
  WARNING:   '#fb923c',
  INFO:      C.accent,
}

function LiveAlertFeed({ streamData, streamStatus, onAcknowledge }) {
  const items = (streamData || []).slice(0, 40)

  return (
    <Panel style={{ display: 'flex', flexDirection: 'column', minHeight: 320 }}>
      <PanelHeader
        title="Live Alert Feed"
        right={
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{
              width:      6,
              height:     6,
              borderRadius: '50%',
              background: streamStatus === 'open' ? C.success : C.warning,
              animation:  streamStatus === 'open' ? 'db-pulse 2s infinite' : 'none',
            }} />
            <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: C.textMuted, letterSpacing: '0.1em' }}>
              {streamStatus === 'open' ? 'LIVE' : 'OFFLINE'}
            </span>
          </div>
        }
      />
      <div style={{ padding: '10px 14px 0' }}>
        <WsIndicator status={streamStatus} />
      </div>
      {items.length === 0 ? (
        <EmptyState
          icon={
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="16" r="13" stroke={C.textMuted} strokeWidth="1.2" />
              <circle cx="16" cy="16" r="7"  stroke={C.textMuted} strokeWidth="1.2" />
              <circle cx="16" cy="16" r="2"  fill={C.textMuted} />
              <line x1="16" y1="3" x2="16" y2="16" stroke={C.accent} strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          }
          label="No active alerts"
        />
      ) : (
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 0 }}>
          {items.map((alert, i) => {
            const sev = alert.severity || alert.level || 'INFO'
            const color = ALERT_LEVEL_COLORS[sev.toUpperCase()] || C.textMuted
            return (
              <motion.div
                key={alert.id || i}
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.2 }}
                style={{
                  display:      'flex',
                  alignItems:   'center',
                  gap:          10,
                  padding:      '9px 14px',
                  borderBottom: `1px solid ${C.border}`,
                  background:   i === 0 ? `${color}07` : 'transparent',
                }}
              >
                <div style={{ width: 2, alignSelf: 'stretch', borderRadius: 1, background: color, flexShrink: 0 }} />
                <Badge label={sev} color={color} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontFamily:    'IBM Plex Sans, sans-serif',
                    fontSize:      12,
                    color:         C.text,
                    overflow:      'hidden',
                    textOverflow:  'ellipsis',
                    whiteSpace:    'nowrap',
                  }}>
                    {alert.title || alert.message || alert.description || '—'}
                  </div>
                  <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, marginTop: 2, letterSpacing: '0.06em' }}>
                    {alert.location_name || alert.location?.name || '—'}
                    {alert.created_at && ` · ${formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}`}
                  </div>
                </div>
                {(alert.status === 'ACTIVE' || alert.status === 'open') && (
                  <button
                    onClick={() => onAcknowledge(alert.id)}
                    style={{
                      background:    'transparent',
                      border:        `1px solid ${C.border}`,
                      color:         C.textSub,
                      borderRadius:  3,
                      cursor:        'pointer',
                      fontFamily:    'Space Mono, monospace',
                      fontSize:      8,
                      fontWeight:    700,
                      letterSpacing: '0.12em',
                      textTransform: 'uppercase',
                      padding:       '3px 7px',
                      flexShrink:    0,
                    }}
                  >ACK</button>
                )}
              </motion.div>
            )
          })}
        </div>
      )}
    </Panel>
  )
}

// ─── Active Responses Panel ─────────────────────────────────────────────────────
const LEVEL_COLORS = ['', C.success, '#34d399', C.warning, '#f97316', C.danger]

function ActiveResponses({ activations, loading, error, onRetry }) {
  return (
    <Panel>
      <PanelHeader title="Active Responses" right={
        activations.length > 0 && (
          <Link to="/dashboard/response" style={{
            fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.accent,
            textDecoration: 'none', letterSpacing: '0.1em',
          }}>View all →</Link>
        )
      } />
      <div style={{ padding: 14 }}>
        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[...Array(3)].map((_, i) => <Shimmer key={i} height={66} radius={6} />)}
          </div>
        ) : error ? (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <div style={{ color: C.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, marginBottom: 8 }}>
              Failed to load
            </div>
            <RetryBtn onClick={onRetry} />
          </div>
        ) : activations.length === 0 ? (
          <EmptyState
            icon={
              <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
                <circle cx="14" cy="14" r="12" stroke={C.textMuted} strokeWidth="1.2" />
                <path d="M9 14h10M14 9v10" stroke={C.textMuted} strokeWidth="1.4" strokeLinecap="round" />
              </svg>
            }
            label="No active responses"
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {activations.map((act, i) => {
              const lvl = act.current_level || act.response_level || act.level
              const color = LEVEL_COLORS[lvl] || C.accent
              return (
                <motion.div key={act.id} {...fadeUp(i * 0.04)} style={{
                  background:   C.surfaceHigh,
                  border:       `1px solid ${C.border}`,
                  borderRadius: 6,
                  padding:      '11px 14px',
                  display:      'flex',
                  alignItems:   'center',
                  gap:          10,
                }}>
                  <div style={{ width: 3, alignSelf: 'stretch', borderRadius: 2, background: color, flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontFamily:   'IBM Plex Sans, sans-serif',
                      fontSize:     13,
                      color:        C.text,
                      fontWeight:   600,
                      marginBottom: 4,
                      overflow:     'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace:   'nowrap',
                    }}>
                      {act.protocol?.name || act.protocol_name || act.name || `Activation #${String(act.id).slice(0,8)}`}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <Badge label={`Level ${lvl ?? '?'}`} color={color} />
                      {act.status && <Badge label={act.status} color={C.accent} />}
                      <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, letterSpacing: '0.06em' }}>
                        {act.activated_at ? formatDistanceToNow(new Date(act.activated_at), { addSuffix: true }) : '—'}
                      </span>
                    </div>
                  </div>
                  <Link to={`/dashboard/response/${act.id}`} style={{
                    color:         C.accent,
                    textDecoration:'none',
                    fontFamily:    'Space Mono, monospace',
                    fontSize:      9,
                    letterSpacing: '0.1em',
                    whiteSpace:    'nowrap',
                    flexShrink:    0,
                  }}>View →</Link>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>
    </Panel>
  )
}

// ─── Risk Score Map ─────────────────────────────────────────────────────────────
function AfricaRiskMap({ riskScores, loading, error, onRetry }) {
  const [tooltip, setTooltip] = useState(null)
  const scores = riskScores || []

  return (
    <Panel style={{ position: 'relative', overflow: 'hidden' }}>
      <PanelHeader
        title="Risk Map — Africa"
        right={
          <Link to="/dashboard/risk" style={{
            fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.accent,
            textDecoration: 'none', letterSpacing: '0.1em',
          }}>Full map →</Link>
        }
      />
      <div style={{ padding: '16px 20px 20px' }}>
        {loading && <Shimmer height={300} radius={6} />}

        {error && !loading && (
          <div style={{ textAlign: 'center', padding: '60px 0' }}>
            <div style={{ color: C.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, marginBottom: 8 }}>
              Failed to load risk data
            </div>
            <RetryBtn onClick={onRetry} />
          </div>
        )}

        {!loading && !error && (
          <>
            <svg
              viewBox={`0 0 ${MAP_W} ${MAP_H}`}
              style={{ width: '100%', height: 'auto', display: 'block', borderRadius: 4, ...gridBg }}
            >
              {/* Africa outline */}
              <path d={`
                M 210 10 L 310 8 L 390 30 L 450 60 L 500 90 L 540 130
                L 570 180 L 580 230 L 570 280 L 540 320 L 500 360 L 450 395
                L 400 410 L 350 408 L 300 400 L 260 380 L 220 350
                L 180 310 L 150 270 L 130 230 L 120 185 L 125 140
                L 140 100 L 160 65 L 185 35 Z
              `}
                fill="none" stroke={C.border} strokeWidth={1.5} opacity={0.6}
              />
              {/* Madagascar */}
              <path d="M 558 230 L 568 215 L 582 220 L 585 250 L 575 270 L 558 260 Z"
                fill="none" stroke={C.border} strokeWidth={1} opacity={0.4}
              />

              {scores.map((rs, i) => {
                const lat = parseFloat(rs.latitude ?? rs.location?.latitude ?? 0)
                const lng = parseFloat(rs.longitude ?? rs.location?.longitude ?? 0)
                if (!lat && !lng) return null
                const { x, y } = latLngToSvg(lat, lng)
                const score = Number(rs.score ?? rs.risk_score ?? 0)
                const r = 4 + (score / 100) * 10
                const color = scoreToColor(score)
                return (
                  <g key={rs.id || i}>
                    <circle cx={x} cy={y} r={r + 5} fill={`${color}10`} style={{ cursor: 'pointer' }} />
                    <circle
                      cx={x} cy={y} r={r}
                      fill={`${color}55`} stroke={color} strokeWidth={1}
                      style={{ cursor: 'pointer' }}
                      onMouseEnter={(e) => setTooltip({
                        x: e.clientX, y: e.clientY,
                        name:    rs.location?.name || rs.location_name || `${lat.toFixed(1)},${lng.toFixed(1)}`,
                        score,
                        disease: rs.disease?.name || rs.disease_name || rs.disease_code || '—',
                        level:   rs.risk_level || rs.level || '—',
                      })}
                      onMouseLeave={() => setTooltip(null)}
                    />
                  </g>
                )
              })}
            </svg>

            {/* Legend */}
            <div style={{ display: 'flex', gap: 20, marginTop: 12, flexWrap: 'wrap' }}>
              {[
                { label: 'Critical ≥75', color: C.danger },
                { label: 'High 50–74',   color: C.warning },
                { label: 'Moderate <50', color: C.success },
              ].map(({ label, color }) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
                  <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, letterSpacing: '0.1em' }}>
                    {label}
                  </span>
                </div>
              ))}
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, marginLeft: 'auto', letterSpacing: '0.1em' }}>
                {scores.length} LOCATIONS
              </span>
            </div>
          </>
        )}
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div style={{
          position:      'fixed',
          left:          Math.min(tooltip.x + 14, window.innerWidth - 150),
          top:           Math.max(8, tooltip.y - 12),
          zIndex:        9999,
          background:    C.surfaceHigh,
          border:        `1px solid ${C.border}`,
          borderRadius:  4,
          padding:       '8px 12px',
          pointerEvents: 'none',
          minWidth:      120,
        }}>
          <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: C.text, marginBottom: 4 }}>
            {tooltip.name}
          </div>
          <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: C.textSub }}>
            Score: <strong style={{ color: scoreToColor(tooltip.score) }}>{tooltip.score}</strong>
          </div>
          {tooltip.disease !== '—' && (
            <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, color: C.textSub, marginTop: 2 }}>
              {tooltip.disease}
            </div>
          )}
        </div>
      )}
    </Panel>
  )
}

// ─── Recent Risk Alerts ─────────────────────────────────────────────────────────
const RISK_ALERT_SEVERITY_COLORS = {
  EMERGENCY: '#dc2626', CRITICAL: C.danger, HIGH: C.warning,
  MEDIUM: C.accent, LOW: C.success, VERY_HIGH: '#f97316',
}

function RecentRiskAlerts({ alerts, loading, error, onRetry, onAck }) {
  return (
    <Panel>
      <PanelHeader title="Risk Alerts" right={
        <Link to="/dashboard/risk/alerts" style={{
          fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.accent,
          textDecoration: 'none', letterSpacing: '0.1em',
        }}>View all →</Link>
      } />
      <div>
        {loading ? (
          <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[...Array(4)].map((_, i) => <Shimmer key={i} height={54} radius={4} />)}
          </div>
        ) : error ? (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <div style={{ color: C.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, marginBottom: 8 }}>Failed</div>
            <RetryBtn onClick={onRetry} />
          </div>
        ) : alerts.length === 0 ? (
          <EmptyState icon={null} label="No critical alerts" />
        ) : (
          alerts.slice(0, 6).map((a, i) => {
            const sev   = a.severity || a.level || 'MEDIUM'
            const color = RISK_ALERT_SEVERITY_COLORS[sev.toUpperCase()] || C.textMuted
            return (
              <div key={a.id || i} style={{
                display:      'flex',
                alignItems:   'flex-start',
                gap:          10,
                padding:      '10px 16px',
                borderBottom: i < Math.min(alerts.length, 6) - 1 ? `1px solid ${C.border}` : 'none',
              }}>
                <div style={{ width: 2, alignSelf: 'stretch', background: color, borderRadius: 1, flexShrink: 0, marginTop: 2 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontFamily:   'IBM Plex Sans, sans-serif',
                    fontSize:     12,
                    color:        C.text,
                    overflow:     'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace:   'nowrap',
                    marginBottom: 4,
                  }}>
                    {a.title || a.message || a.description || '—'}
                  </div>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Badge label={sev} color={color} />
                    <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, letterSpacing: '0.06em' }}>
                      {a.location_name || a.location?.name || '—'}
                    </span>
                    <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, letterSpacing: '0.06em' }}>
                      {a.created_at ? formatDistanceToNow(new Date(a.created_at), { addSuffix: true }) : ''}
                    </span>
                  </div>
                </div>
                {a.status === 'ACTIVE' && (
                  <button
                    onClick={() => onAck(a.id)}
                    style={{
                      background:    'transparent',
                      border:        `1px solid ${C.border}`,
                      color:         C.textSub,
                      borderRadius:  3,
                      cursor:        'pointer',
                      fontFamily:    'Space Mono, monospace',
                      fontSize:      8,
                      fontWeight:    700,
                      letterSpacing: '0.1em',
                      textTransform: 'uppercase',
                      padding:       '3px 7px',
                      flexShrink:    0,
                    }}
                  >ACK</button>
                )}
              </div>
            )
          })
        )}
      </div>
    </Panel>
  )
}

// ─── Active Cases Snapshot ──────────────────────────────────────────────────────
function CasesSnapshot({ data, loading, error, onRetry }) {
  const items = [
    { label: 'Active Cases',     value: data?.active_cases      ?? data?.total_active_cases },
    { label: 'Under Monitoring', value: data?.contacts_monitoring ?? data?.under_monitoring  },
    { label: 'Testing Today',    value: data?.appointments_today ?? data?.tests_today        },
    { label: 'In Quarantine',    value: data?.quarantine_count   ?? data?.in_quarantine      },
  ]

  return (
    <Panel>
      <PanelHeader title="Operations Snapshot" right={
        <Link to="/dashboard/operations" style={{
          fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.accent,
          textDecoration: 'none', letterSpacing: '0.1em',
        }}>Details →</Link>
      } />
      <div style={{ padding: 14 }}>
        {loading ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            {[...Array(4)].map((_, i) => <Shimmer key={i} height={60} radius={6} />)}
          </div>
        ) : error ? (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div style={{ color: C.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, marginBottom: 8 }}>Failed</div>
            <RetryBtn onClick={onRetry} />
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            {items.map(({ label, value }) => (
              <div key={label} style={{
                background:   C.surfaceHigh,
                border:       `1px solid ${C.border}`,
                borderRadius: 6,
                padding:      '12px 14px',
              }}>
                <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 32, color: C.text, lineHeight: 1 }}>
                  {value ?? '—'}
                </div>
                <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, letterSpacing: '0.1em', textTransform: 'uppercase', marginTop: 4 }}>
                  {label}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Panel>
  )
}

// ─── Early Warning ──────────────────────────────────────────────────────────────
const EW_STATUS_COLORS = {
  ALERT: C.danger, WARNING: '#f97316', WATCH: C.warning, NORMAL: C.success, INSUFFICIENT_DATA: C.textMuted,
}

function Sparkline({ data, color, width = 96, height = 28 }) {
  if (!data || data.length < 2) return null
  const max = Math.max(...data, 1)
  const step = width / (data.length - 1)
  const pts = data.map((v, i) => `${(i * step).toFixed(1)},${(height - 2 - (v / max) * (height - 4)).toFixed(1)}`).join(' ')
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  )
}

function EarlyWarningPanel() {
  const [items, setItems]     = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError(false)
    try {
      const res = await surveillanceApi.earlyWarningOverview({ limit: 6 })
      setItems(res.data?.results ?? [])
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 5 * 60 * 1000)   // refresh every 5 minutes
    return () => clearInterval(id)
  }, [load])

  return (
    <Panel>
      <PanelHeader title="Early Warning" right={
        <Link to="/dashboard/surveillance" style={{
          fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.accent,
          textDecoration: 'none', letterSpacing: '0.1em',
        }}>All anomalies →</Link>
      } />
      <div style={{ padding: 14 }}>
        {loading ? (
          [...Array(3)].map((_, i) => <Shimmer key={i} height={44} radius={6} style={{ marginBottom: 8 }} />)
        ) : error ? (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div style={{ color: C.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, marginBottom: 8 }}>Failed</div>
            <RetryBtn onClick={load} />
          </div>
        ) : items.length === 0 ? (
          <EmptyState icon="✓" label="Not enough surveillance data to analyse yet" />
        ) : items.map(a => {
          const color = EW_STATUS_COLORS[a.status] || C.accent
          return (
            <div key={`${a.location}-${a.disease_code}`} style={{
              background: C.surfaceHigh, border: `1px solid ${C.border}`, borderRadius: 6,
              padding: '10px 12px', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{
                    fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: C.text,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>{a.disease_name} · {a.location_name}</span>
                  <Badge label={a.status} color={color} />
                </div>
                <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, marginTop: 4, letterSpacing: '0.06em' }}>
                  {a.last_7_days} cases / 7d{a.rt != null ? ` · Rt ${a.rt}` : ''}
                </div>
              </div>
              <Sparkline data={a.series} color={color} />
            </div>
          )
        })}
      </div>
    </Panel>
  )
}

// ─── Analytics Quick Stats ──────────────────────────────────────────────────────
function AnalyticsQuickStats({ data, loading, error, onRetry }) {
  const items = [
    { label: 'Epi Models',       value: data?.total_models,     color: C.accent  },
    { label: 'Analyses',         value: data?.total_analyses,   color: C.success  },
    { label: 'Reports',          value: data?.total_reports,    color: C.warning  },
    { label: 'Active Dashboards', value: data?.active_dashboards, color: C.purple },
  ]

  return (
    <Panel>
      <PanelHeader title="Analytics" right={
        <Link to="/dashboard/analytics" style={{
          fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.accent,
          textDecoration: 'none', letterSpacing: '0.1em',
        }}>Open →</Link>
      } />
      <div style={{ padding: 14 }}>
        {loading ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 10 }}>
            {[...Array(4)].map((_, i) => <Shimmer key={i} height={56} radius={6} />)}
          </div>
        ) : error ? (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div style={{ color: C.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, marginBottom: 8 }}>Failed</div>
            <RetryBtn onClick={onRetry} />
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 10 }}>
            {items.map(({ label, value, color }) => (
              <div key={label} style={{
                background:   C.surfaceHigh,
                border:       `1px solid ${C.border}`,
                borderRadius: 6,
                padding:      '12px 14px',
              }}>
                <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 30, color, lineHeight: 1 }}>
                  {value ?? '—'}
                </div>
                <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, letterSpacing: '0.1em', textTransform: 'uppercase', marginTop: 4 }}>
                  {label}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Panel>
  )
}

// ─── Resource Status Strip ──────────────────────────────────────────────────────
function ResourcesStrip({ data, loading, error, onRetry }) {
  const items = [
    { label: 'Total Facilities',  value: data?.total_facilities  ?? data?.facilities_count   },
    { label: 'Low Stock Alerts',  value: data?.low_stock_count   ?? data?.low_stock_alerts   },
    { label: 'Pending Procure.',  value: data?.pending_procurement ?? data?.pending_requests },
    { label: 'Critical Items',   value: data?.critical_items    ?? data?.critical_count      },
  ]

  return (
    <Panel>
      <PanelHeader title="Resources" right={
        <Link to="/dashboard/resources" style={{
          fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.accent,
          textDecoration: 'none', letterSpacing: '0.1em',
        }}>View →</Link>
      } />
      <div style={{ padding: 14 }}>
        {loading ? (
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {[...Array(4)].map((_, i) => <Shimmer key={i} height={52} radius={6} style={{ flex: '1 1 100px' }} />)}
          </div>
        ) : error ? (
          <div style={{ textAlign: 'center', padding: '16px 0' }}>
            <div style={{ color: C.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, marginBottom: 8 }}>Failed</div>
            <RetryBtn onClick={onRetry} />
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {items.map(({ label, value }) => (
              <div key={label} style={{
                flex:         '1 1 100px',
                background:   C.surfaceHigh,
                border:       `1px solid ${C.border}`,
                borderRadius: 6,
                padding:      '10px 14px',
              }}>
                <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 28, color: C.text, lineHeight: 1 }}>
                  {value ?? '—'}
                </div>
                <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, letterSpacing: '0.1em', textTransform: 'uppercase', marginTop: 3 }}>
                  {label}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Panel>
  )
}

// ─── Hotspot List ───────────────────────────────────────────────────────────────
function HotspotList({ hotspots, loading, error, onRetry }) {
  return (
    <Panel>
      <PanelHeader title="Active Hotspots" right={
        <Link to="/dashboard/surveillance" style={{
          fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.accent,
          textDecoration: 'none', letterSpacing: '0.1em',
        }}>Surveillance →</Link>
      } />
      <div>
        {loading ? (
          <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[...Array(4)].map((_, i) => <Shimmer key={i} height={48} radius={4} />)}
          </div>
        ) : error ? (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <div style={{ color: C.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, marginBottom: 8 }}>Failed</div>
            <RetryBtn onClick={onRetry} />
          </div>
        ) : hotspots.length === 0 ? (
          <EmptyState icon={null} label="No active hotspots" />
        ) : (
          hotspots.slice(0, 5).map((hs, i) => {
            const intensity = hs.intensity_level || hs.level || hs.risk_level || '—'
            const iColor = intensity === 'HIGH' || intensity === 'CRITICAL' ? C.danger
              : intensity === 'MEDIUM' ? C.warning : C.success
            return (
              <div key={hs.id || i} style={{
                display:      'flex',
                alignItems:   'center',
                gap:          10,
                padding:      '10px 16px',
                borderBottom: i < Math.min(hotspots.length, 5) - 1 ? `1px solid ${C.border}` : 'none',
              }}>
                <div style={{ width: 7, height: 7, borderRadius: '50%', background: iColor, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: C.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {hs.location?.name || hs.location_name || hs.name || '—'}
                  </div>
                  <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, letterSpacing: '0.06em', marginTop: 2 }}>
                    {hs.disease_name || hs.disease_code || '—'}
                    {hs.case_count != null && ` · ${hs.case_count} cases`}
                  </div>
                </div>
                <Badge label={intensity} color={iColor} />
              </div>
            )
          })
        )}
      </div>
    </Panel>
  )
}

// ─── Coordination Quick View ────────────────────────────────────────────────────
function CoordinationStrip({ data, loading, error, onRetry }) {
  const items = [
    { label: 'Active Teams',    value: data?.active_teams    ?? data?.teams_count    },
    { label: 'Open Tasks',      value: data?.pending_tasks   ?? data?.open_tasks     },
    { label: 'Meetings Today',  value: data?.meetings_today  ?? data?.upcoming_meetings },
    { label: 'Agencies',        value: data?.total_agencies  ?? data?.agencies_count },
  ]
  return (
    <Panel>
      <PanelHeader title="Coordination" right={
        <Link to="/dashboard/coordination" style={{
          fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.accent,
          textDecoration: 'none', letterSpacing: '0.1em',
        }}>View →</Link>
      } />
      <div style={{ padding: 14 }}>
        {loading ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 10 }}>
            {[...Array(4)].map((_, i) => <Shimmer key={i} height={54} radius={6} />)}
          </div>
        ) : error ? (
          <div style={{ textAlign: 'center', padding: '16px 0' }}>
            <div style={{ color: C.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, marginBottom: 8 }}>Failed</div>
            <RetryBtn onClick={onRetry} />
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 10 }}>
            {items.map(({ label, value }) => (
              <div key={label} style={{
                background:   C.surfaceHigh,
                border:       `1px solid ${C.border}`,
                borderRadius: 6,
                padding:      '10px 14px',
              }}>
                <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 28, color: C.text, lineHeight: 1 }}>
                  {value ?? '—'}
                </div>
                <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, letterSpacing: '0.1em', textTransform: 'uppercase', marginTop: 4 }}>
                  {label}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Panel>
  )
}

// ─── Main Dashboard ─────────────────────────────────────────────────────────────
export default function Dashboard() {
  const toast = useToast()
  const { user } = useAuth()
  const { data: alertStream, status: alertStatus } = useAlertStream()
  const { data: dashStream }                       = useDashboardStream()

  // ── State ────────────────────────────────────────────────────────────────────
  // Top-level summary stats
  const [topStats, setTopStats]     = useState(null)
  const [topLoading, setTopLoading] = useState(true)
  const [topError, setTopError]     = useState(false)

  // Active activations (response)
  const [activations, setActivations]         = useState([])
  const [activationsLoading, setActivationsLoading] = useState(true)
  const [activationsError, setActivationsError]     = useState(false)

  // Risk alerts (critical)
  const [riskAlerts, setRiskAlerts]         = useState([])
  const [riskAlertsLoading, setRiskAlertsLoading] = useState(true)
  const [riskAlertsError, setRiskAlertsError]     = useState(false)

  // Risk scores for map
  const [riskScores, setRiskScores]       = useState([])
  const [riskMapLoading, setRiskMapLoading] = useState(true)
  const [riskMapError, setRiskMapError]     = useState(false)

  // Operations
  const [opsData, setOpsData]       = useState(null)
  const [opsLoading, setOpsLoading] = useState(true)
  const [opsError, setOpsError]     = useState(false)

  // Analytics overview
  const [analyticsData, setAnalyticsData]     = useState(null)
  const [analyticsLoading, setAnalyticsLoading] = useState(true)
  const [analyticsError, setAnalyticsError]     = useState(false)

  // Surveillance hotspots
  const [hotspots, setHotspots]       = useState([])
  const [hotspotsLoading, setHotspotsLoading] = useState(true)
  const [hotspotsError, setHotspotsError]     = useState(false)

  // Resources
  const [resourcesData, setResourcesData]     = useState(null)
  const [resourcesLoading, setResourcesLoading] = useState(true)
  const [resourcesError, setResourcesError]     = useState(false)

  // Coordination
  const [coordData, setCoordData]     = useState(null)
  const [coordLoading, setCoordLoading] = useState(true)
  const [coordError, setCoordError]     = useState(false)

  // ── Fetch functions ──────────────────────────────────────────────────────────
  const fetchTopStats = useCallback(async () => {
    setTopLoading(true); setTopError(false)
    try {
      // Parallel: risk dashboard + response dashboard + unread notif count
      const [riskRes, respRes, notifRes] = await Promise.allSettled([
        riskApi.riskDashboardOverview(),
        responseApi.getDashboard(),
        coreApi.unreadCount(),
      ])
      const riskD  = riskRes.status  === 'fulfilled' ? riskRes.value.data  : {}
      const respD  = respRes.status  === 'fulfilled' ? respRes.value.data  : {}
      const notifD = notifRes.status === 'fulfilled' ? notifRes.value.data : {}

      setTopStats({
        openAlerts:      riskD.active_alerts   ?? riskD.open_alerts     ?? riskD.alert_count ?? 0,
        criticalRisks:   riskD.critical_risks  ?? riskD.critical_count  ?? 0,
        activeResponses: respD.active_count    ?? respD.active_activations ?? 0,
        avgRiskScore:    riskD.average_risk_score != null
                           ? Number(riskD.average_risk_score).toFixed(1)
                           : null,
        unreadNotifs:    notifD.unread_count   ?? notifD.count          ?? 0,
        highRisks:       riskD.high_risks      ?? riskD.high_count      ?? 0,
      })
    } catch {
      setTopError(true)
    } finally {
      setTopLoading(false)
    }
  }, [])

  const fetchActivations = useCallback(async () => {
    setActivationsLoading(true); setActivationsError(false)
    try {
      // responseApi.activeActivations() → GET /response/activations/active/
      const res = await responseApi.activeActivations()
      setActivations(res.data?.results ?? res.data ?? [])
    } catch {
      setActivationsError(true)
    } finally {
      setActivationsLoading(false)
    }
  }, [])

  const fetchRiskAlerts = useCallback(async () => {
    setRiskAlertsLoading(true); setRiskAlertsError(false)
    try {
      // riskApi.criticalAlerts() → GET /risk/alerts/critical/
      const res = await riskApi.criticalAlerts({ page_size: 10 })
      setRiskAlerts(res.data?.results ?? res.data ?? [])
    } catch {
      // Fallback: listAlerts with is_active filter
      try {
        const res2 = await riskApi.listAlerts({ page_size: 10, ordering: '-created_at' })
        setRiskAlerts(res2.data?.results ?? res2.data ?? [])
      } catch {
        setRiskAlertsError(true)
      }
    } finally {
      setRiskAlertsLoading(false)
    }
  }, [])

  const fetchRiskMap = useCallback(async () => {
    setRiskMapLoading(true); setRiskMapError(false)
    try {
      const res = await riskApi.listRiskScores({ page_size: 100, ordering: '-score' })
      setRiskScores(res.data?.results ?? res.data ?? [])
    } catch {
      setRiskMapError(true)
    } finally {
      setRiskMapLoading(false)
    }
  }, [])

  const fetchOps = useCallback(async () => {
    setOpsLoading(true); setOpsError(false)
    try {
      const res = await operationsApi.getDashboard()
      setOpsData(res.data)
    } catch {
      setOpsError(true)
    } finally {
      setOpsLoading(false)
    }
  }, [])

  const fetchAnalytics = useCallback(async () => {
    setAnalyticsLoading(true); setAnalyticsError(false)
    try {
      // getDashboardOverview → GET /analytics/overview/overview/
      const res = await analyticsApi.getDashboardOverview()
      setAnalyticsData(res.data)
    } catch {
      setAnalyticsError(true)
    } finally {
      setAnalyticsLoading(false)
    }
  }, [])

  const fetchHotspots = useCallback(async () => {
    setHotspotsLoading(true); setHotspotsError(false)
    try {
      const res = await surveillanceApi.listHotspots({ page_size: 10, ordering: '-created_at' })
      setHotspots(res.data?.results ?? res.data ?? [])
    } catch {
      setHotspotsError(true)
    } finally {
      setHotspotsLoading(false)
    }
  }, [])

  const fetchResources = useCallback(async () => {
    setResourcesLoading(true); setResourcesError(false)
    try {
      const res = await resourcesApi.resourcesDashboard()
      setResourcesData(res.data)
    } catch {
      setResourcesError(true)
    } finally {
      setResourcesLoading(false)
    }
  }, [])

  const fetchCoord = useCallback(async () => {
    setCoordLoading(true); setCoordError(false)
    try {
      const res = await coordinationApi.coordinationDashboard()
      setCoordData(res.data)
    } catch {
      setCoordError(true)
    } finally {
      setCoordLoading(false)
    }
  }, [])

  // ── Initial load ─────────────────────────────────────────────────────────────
  useEffect(() => {
    fetchTopStats()
    fetchActivations()
    fetchRiskAlerts()
    fetchRiskMap()
    fetchOps()
    fetchAnalytics()
    fetchHotspots()
    fetchResources()
    fetchCoord()
  }, [])

  // ── Real-time dashboard stream updates ────────────────────────────────────────
  // The dashboard WS consumer pushes aggregate stat deltas; merge them into topStats
  useEffect(() => {
    if (!dashStream) return
    setTopStats((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        ...(dashStream.open_alerts      != null && { openAlerts:      dashStream.open_alerts }),
        ...(dashStream.critical_risks   != null && { criticalRisks:   dashStream.critical_risks }),
        ...(dashStream.active_responses != null && { activeResponses: dashStream.active_responses }),
        ...(dashStream.average_risk_score != null && {
          avgRiskScore: Number(dashStream.average_risk_score).toFixed(1),
        }),
        ...(dashStream.unread_notifs    != null && { unreadNotifs:    dashStream.unread_notifs }),
      }
    })
  }, [dashStream])

  // ── Acknowledge alert ─────────────────────────────────────────────────────────
  const handleAcknowledge = useCallback(async (alertId) => {
    try {
      await riskApi.acknowledgeAlert(alertId, { notes: '' })
      toast.success('Alert acknowledged')
      fetchRiskAlerts()
    } catch {
      toast.error('Failed to acknowledge alert')
    }
  }, [fetchRiskAlerts])

  // ── Top stat card specs ───────────────────────────────────────────────────────
  const statCards = [
    {
      key:    'openAlerts',
      label:  'Open Alerts',
      color:  C.danger,
      to:     '/dashboard/risk/alerts',
    },
    {
      key:    'criticalRisks',
      label:  'Critical Risks',
      color:  C.warning,
      to:     '/dashboard/risk',
    },
    {
      key:    'activeResponses',
      label:  'Active Responses',
      color:  C.success,
      to:     '/dashboard/response',
    },
    {
      key:    'avgRiskScore',
      label:  'Avg Risk Score',
      color:  C.accent,
      to:     '/dashboard/risk',
    },
    {
      key:    'unreadNotifs',
      label:  'Notifications',
      color:  C.purple,
    },
  ]

  // ─────────────────────────────────────────────────────────────────────────────
  return (
    <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', color: C.text }}>
      <style>{`
        @keyframes db-shimmer { to { background-position: -200% 0 } }
        @keyframes db-spin    { to { transform: rotate(360deg) } }
        @keyframes db-pulse   { 0%,100% { opacity: 1 } 50% { opacity: 0.35 } }
      `}</style>

      {/* ── Page Header ──────────────────────────────────────────────────────── */}
      <motion.div {...fadeUp(0)} style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <div>
            <div style={{
              fontFamily:    'Bebas Neue, sans-serif',
              fontSize:      32,
              color:         C.text,
              letterSpacing: '0.04em',
              lineHeight:    1,
              marginBottom:  4,
            }}>OryxShield</div>
            <div style={{
              fontFamily:    'Space Mono, monospace',
              fontSize:      9,
              color:         C.textMuted,
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
            }}>
              Operational Overview · Real-Time
              {user && (
                <span style={{ marginLeft: 12, color: C.textSub }}>
                  · {user.first_name || user.username}
                </span>
              )}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Link to="/dashboard/analytics" style={{
              background:    C.surface,
              border:        `1px solid ${C.border}`,
              color:         C.textSub,
              borderRadius:  4,
              padding:       '7px 14px',
              fontFamily:    'Space Mono, monospace',
              fontSize:      9,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              textDecoration:'none',
              whiteSpace:    'nowrap',
            }}>Analytics</Link>
            <Link to="/dashboard/risk" style={{
              background:    C.accent,
              border:        `1px solid ${C.accent}`,
              color:         '#fff',
              borderRadius:  4,
              padding:       '7px 14px',
              fontFamily:    'Space Mono, monospace',
              fontSize:      9,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              textDecoration:'none',
              whiteSpace:    'nowrap',
            }}>Risk Center</Link>
          </div>
        </div>
      </motion.div>

      {/* ── Top Stat Cards ──────────────────────────────────────────────────── */}
      <motion.div {...fadeUp(0.04)} style={{
        display:  'flex',
        gap:      14,
        flexWrap: 'wrap',
        marginBottom: 24,
      }}>
        {statCards.map(({ key, label, color, to }) => (
          <StatCard
            key={key}
            label={label}
            value={topStats?.[key]}
            color={color}
            loading={topLoading}
            error={topError}
            onRetry={fetchTopStats}
            to={to}
          />
        ))}
      </motion.div>

      {/* ── Row 1: Active Responses + Live Alert Feed ─────────────────────── */}
      <motion.div {...fadeUp(0.08)} style={{
        display:             'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 280px), 1fr))',
        gap:                 20,
        marginBottom:        20,
      }}>
        <ActiveResponses
          activations={activations}
          loading={activationsLoading}
          error={activationsError}
          onRetry={fetchActivations}
        />
        <LiveAlertFeed
          streamData={alertStream}
          streamStatus={alertStatus}
          onAcknowledge={handleAcknowledge}
        />
      </motion.div>

      {/* ── Row 2: Risk Alerts + Hotspots + Operations ────────────────────── */}
      <motion.div {...fadeUp(0.12)} style={{
        display:             'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 240px), 1fr))',
        gap:                 20,
        marginBottom:        20,
      }}>
        <RecentRiskAlerts
          alerts={riskAlerts}
          loading={riskAlertsLoading}
          error={riskAlertsError}
          onRetry={fetchRiskAlerts}
          onAck={handleAcknowledge}
        />
        <HotspotList
          hotspots={hotspots}
          loading={hotspotsLoading}
          error={hotspotsError}
          onRetry={fetchHotspots}
        />
        <CasesSnapshot
          data={opsData}
          loading={opsLoading}
          error={opsError}
          onRetry={fetchOps}
        />
        <EarlyWarningPanel />
      </motion.div>

      {/* ── Row 3: Analytics + Coordination + Resources ──────────────────── */}
      <motion.div {...fadeUp(0.16)} style={{
        display:             'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 240px), 1fr))',
        gap:                 20,
        marginBottom:        20,
      }}>
        <AnalyticsQuickStats
          data={analyticsData}
          loading={analyticsLoading}
          error={analyticsError}
          onRetry={fetchAnalytics}
        />
        <CoordinationStrip
          data={coordData}
          loading={coordLoading}
          error={coordError}
          onRetry={fetchCoord}
        />
        <ResourcesStrip
          data={resourcesData}
          loading={resourcesLoading}
          error={resourcesError}
          onRetry={fetchResources}
        />
      </motion.div>

      {/* ── Row 4: Africa Risk Map — full width ───────────────────────────── */}
      <motion.div {...fadeUp(0.2)}>
        <AfricaRiskMap
          riskScores={riskScores}
          loading={riskMapLoading}
          error={riskMapError}
          onRetry={fetchRiskMap}
        />
      </motion.div>
    </div>
  )
}