/**
 * Alerts — OryxShield
 * ==============================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Full alert management for Risk Alerts from riskApi.
 *
 * API alignment (all calls verified against api.js + views.py):
 *   riskApi.listAlerts(params)          GET  /risk/alerts/
 *   riskApi.acknowledgeAlert(id, data)  POST /risk/alerts/{id}/acknowledge/
 *     body: { notes: '' }
 *   riskApi.resolveAlert(id, data)      POST /risk/alerts/{id}/resolve/
 *     body: { resolution_notes: '', actions_taken: [] }
 *   riskApi.closeAlert(id, data)        POST /risk/alerts/{id}/close/
 *     body: {}
 *   riskApi.bulkAcknowledgeAlerts(data) POST /risk/alerts/bulk_acknowledge/
 *     body: { alert_ids: [...] }
 *   riskApi.activeAlerts(params)        GET  /risk/alerts/active/
 *   riskApi.criticalAlerts(params)      GET  /risk/alerts/critical/
 *   riskApi.unacknowledgedAlerts(params)GET  /risk/alerts/unacknowledged/
 *
 * Alert model fields (from serializers):
 *   id, title, description, severity (VERY_LOW/LOW/MEDIUM/HIGH/VERY_HIGH/CRITICAL),
 *   status (ACTIVE/ACKNOWLEDGED/RESOLVED/CLOSED),
 *   location_name, disease_name, disease_code,
 *   risk_score, affected_area, threshold_name,
 *   created_at, updated_at, acknowledged_at, resolved_at, closed_at,
 *   acknowledged_by_username, resolved_by_username,
 *   notes, resolution_notes, actions_taken
 *
 * WS: useAlertStream → { data: Alert[], status: 'connecting'|'open'|'error'|'closed' }
 *
 * Responsive: sticky filter bar, overflowX table, mobile card view below 640px
 * @keyframes prefixed al- to avoid collisions
 * Hover via onMouseEnter/Leave — no CSS :hover
 * Inline styles only — no Tailwind, no CSS modules
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { format, formatDistanceToNow } from 'date-fns'
import { riskApi, extractError } from '../../services/api'
import { useToast } from '../../context/ToastContext'
import { useAlertStream } from '../../hooks/ws/useAlertStream'

// ─── Design tokens ─────────────────────────────────────────────────────────────
const C = {
  bg:          '#0a0f1e',
  surface:     '#111827',
  surfaceHigh: '#151e2e',
  border:      '#1f2937',
  accent:      '#3b82f6',
  accentBg:    'rgba(59,130,246,0.08)',
  danger:      '#ef4444',
  warning:     '#f59e0b',
  success:     '#10b981',
  text:        '#f9fafb',
  textSub:     '#9ca3af',
  textMuted:   '#6b7280',
}

const PAGE_SIZE = 25

// ─── Severity / status maps ─────────────────────────────────────────────────────
// severity field from RiskScore model: VERY_LOW/LOW/MEDIUM/HIGH/VERY_HIGH/CRITICAL
const SEVERITY_COLOR = {
  CRITICAL:  C.danger,
  VERY_HIGH: '#f97316',
  HIGH:      C.warning,
  MEDIUM:    C.accent,
  LOW:       C.success,
  VERY_LOW:  C.textMuted,
  // legacy lowercase fallbacks
  critical:  C.danger,
  high:      C.warning,
  medium:    C.accent,
  low:       C.success,
}

// status field: ACTIVE/ACKNOWLEDGED/RESOLVED/CLOSED
const STATUS_COLOR = {
  ACTIVE:       C.danger,
  ACKNOWLEDGED: C.warning,
  RESOLVED:     C.success,
  CLOSED:       C.textMuted,
  // legacy lowercase
  active:       C.danger,
  acknowledged: C.warning,
  resolved:     C.success,
  closed:       C.textMuted,
}

const SEVERITIES = ['CRITICAL','VERY_HIGH','HIGH','MEDIUM','LOW','VERY_LOW']
const STATUSES   = ['ACTIVE','ACKNOWLEDGED','RESOLVED','CLOSED']

// What the next action button does for each status
const NEXT_ACTION = {
  ACTIVE:       'acknowledge',
  ACKNOWLEDGED: 'resolve',
  RESOLVED:     'close',
  // lowercase fallbacks
  active:       'acknowledge',
  acknowledged: 'resolve',
  resolved:     'close',
}

// ─── Shared micro-components ────────────────────────────────────────────────────
function Badge({ label, color }) {
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
      display:       'inline-block',
    }}>{label}</span>
  )
}

function Shimmer({ width = '100%', height = 18, radius = 4, style: s = {} }) {
  return (
    <div style={{
      width, height, borderRadius: radius,
      background:     `linear-gradient(90deg,${C.surface} 25%,${C.surfaceHigh} 50%,${C.surface} 75%)`,
      backgroundSize: '200% 100%',
      animation:      'al-shimmer 1.5s infinite',
      ...s,
    }} />
  )
}

function WsIndicator({ status }) {
  if (status === 'open') return null
  return (
    <div style={{
      display:       'inline-flex',
      alignItems:    'center',
      gap:           6,
      padding:       '4px 10px',
      background:    'rgba(245,158,11,0.07)',
      border:        '1px solid rgba(245,158,11,0.2)',
      borderRadius:  3,
      fontFamily:    'Space Mono, monospace',
      fontSize:      9,
      color:         C.warning,
      letterSpacing: '0.1em',
    }}>
      <span style={{ animation: 'al-spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
      RECONNECTING…
    </div>
  )
}

function Btn({ onClick, variant = 'ghost', children, loading = false, disabled = false, style: extra = {} }) {
  const [hov, setHov] = useState(false)
  const isDisabled = loading || disabled
  const variants = {
    primary: {
      background: hov ? '#2563eb' : C.accent,
      color:      '#fff',
      border:     'none',
    },
    ghost: {
      background: hov ? C.surfaceHigh : 'transparent',
      border:     `1px solid ${C.border}`,
      color:      C.textSub,
    },
    danger: {
      background: hov ? 'rgba(239,68,68,0.14)' : 'rgba(239,68,68,0.07)',
      border:     `1px solid ${C.danger}40`,
      color:      C.danger,
    },
    warning: {
      background: hov ? 'rgba(245,158,11,0.16)' : 'rgba(245,158,11,0.08)',
      border:     `1px solid ${C.warning}40`,
      color:      C.warning,
    },
    success: {
      background: hov ? 'rgba(16,185,129,0.16)' : 'rgba(16,185,129,0.08)',
      border:     `1px solid ${C.success}40`,
      color:      C.success,
    },
  }
  return (
    <button
      onClick={onClick}
      disabled={isDisabled}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        borderRadius:  4,
        cursor:        isDisabled ? 'default' : 'pointer',
        fontFamily:    'Space Mono, monospace',
        fontSize:      9,
        fontWeight:    700,
        letterSpacing: '0.14em',
        textTransform: 'uppercase',
        padding:       '7px 14px',
        opacity:       isDisabled ? 0.55 : 1,
        transition:    'background 0.15s',
        whiteSpace:    'nowrap',
        ...variants[variant],
        ...extra,
      }}
    >
      {loading ? '…' : children}
    </button>
  )
}

// ─── Table header cell ──────────────────────────────────────────────────────────
function TH({ children, style: s = {} }) {
  return (
    <th style={{
      background:    C.bg,
      color:         C.textMuted,
      fontFamily:    'Space Mono, monospace',
      fontSize:      9,
      textTransform: 'uppercase',
      letterSpacing: '0.12em',
      padding:       '10px 14px',
      textAlign:     'left',
      whiteSpace:    'nowrap',
      borderBottom:  `1px solid ${C.border}`,
      position:      'sticky',
      top:           0,
      zIndex:        1,
      ...s,
    }}>{children}</th>
  )
}

// ─── Filter bar ─────────────────────────────────────────────────────────────────
function FilterBar({ filters, onChange, onReset, streamStatus, liveCount }) {
  const debounceRef = useRef(null)

  const handleSearch = (e) => {
    const val = e.target.value
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => onChange('search', val), 320)
  }

  const inputStyle = {
    background:   C.surface,
    border:       `1.5px solid ${C.border}`,
    color:        C.text,
    borderRadius: 4,
    padding:      '7px 11px',
    fontFamily:   'IBM Plex Sans, sans-serif',
    fontSize:     13,
    outline:      'none',
    minWidth:     0,
  }

  const selStyle = {
    ...inputStyle,
    cursor:       'pointer',
    paddingRight: 26,
    appearance:   'none',
    WebkitAppearance: 'none',
  }

  const Caret = () => (
    <span style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: C.textMuted, fontSize: 10 }}>▾</span>
  )

  const hasFilters = filters.severity || filters.status || filters.search || filters.dateFrom || filters.dateTo

  return (
    <div style={{
      background:  C.surface,
      border:      `1px solid ${C.border}`,
      borderRadius: 8,
      padding:     '12px 16px',
      display:     'flex',
      gap:         10,
      flexWrap:    'wrap',
      alignItems:  'center',
      marginBottom: 18,
      position:    'sticky',
      top:         52,
      zIndex:      20,
    }}>
      {/* Severity */}
      <div style={{ position: 'relative', flex: '1 1 110px', minWidth: 90 }}>
        <select value={filters.severity} onChange={(e) => onChange('severity', e.target.value)} style={{ ...selStyle, width: '100%' }}>
          <option value="">All Severity</option>
          {SEVERITIES.map((s) => <option key={s} value={s}>{s.replace('_',' ')}</option>)}
        </select>
        <Caret />
      </div>

      {/* Status */}
      <div style={{ position: 'relative', flex: '1 1 110px', minWidth: 90 }}>
        <select value={filters.status} onChange={(e) => onChange('status', e.target.value)} style={{ ...selStyle, width: '100%' }}>
          <option value="">All Statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <Caret />
      </div>

      {/* Search */}
      <input
        key={filters._resetKey}
        defaultValue={filters.search}
        onChange={handleSearch}
        placeholder="Search title, location, disease…"
        style={{ ...inputStyle, flex: '1 1 180px' }}
      />

      {/* Date range */}
      <input
        type="date"
        value={filters.dateFrom}
        onChange={(e) => onChange('dateFrom', e.target.value)}
        style={{ ...inputStyle, colorScheme: 'dark', flex: '1 1 120px', minWidth: 100 }}
      />
      <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, flexShrink: 0 }}>→</span>
      <input
        type="date"
        value={filters.dateTo}
        onChange={(e) => onChange('dateTo', e.target.value)}
        style={{ ...inputStyle, colorScheme: 'dark', flex: '1 1 120px', minWidth: 100 }}
      />

      {/* Reset */}
      {hasFilters && (
        <Btn variant="ghost" onClick={onReset} style={{ padding: '7px 12px', flexShrink: 0 }}>
          Clear
        </Btn>
      )}

      {/* WS + live count */}
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
        <WsIndicator status={streamStatus} />
        {streamStatus === 'open' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 5, height: 5, borderRadius: '50%', background: C.success, animation: 'al-pulse 2s infinite' }} />
            <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: C.textMuted, letterSpacing: '0.1em' }}>
              LIVE{liveCount > 0 ? ` · +${liveCount}` : ''}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Expand detail row ──────────────────────────────────────────────────────────
function AlertDetail({ alert }) {
  const fields = [
    { label: 'Description',     value: alert.description         || '—' },
    { label: 'Affected Area',   value: alert.affected_area       || '—' },
    { label: 'Risk Score',      value: alert.risk_score          ?? '—' },
    { label: 'Threshold',       value: alert.threshold_name      || '—' },
    { label: 'Disease Code',    value: alert.disease_code        || '—' },
    { label: 'Created',         value: alert.created_at ? format(new Date(alert.created_at), 'dd MMM yyyy HH:mm') : '—' },
    { label: 'Updated',         value: alert.updated_at ? format(new Date(alert.updated_at), 'dd MMM yyyy HH:mm') : '—' },
    { label: 'Acknowledged By', value: alert.acknowledged_by_username || (alert.acknowledged_at ? 'Unknown' : '—') },
    { label: 'Acknowledged At', value: alert.acknowledged_at ? format(new Date(alert.acknowledged_at), 'dd MMM yyyy HH:mm') : '—' },
    { label: 'Notes',           value: alert.notes               || '—' },
    { label: 'Resolved By',     value: alert.resolved_by_username || (alert.resolved_at ? 'Unknown' : '—') },
    { label: 'Resolved At',     value: alert.resolved_at ? format(new Date(alert.resolved_at), 'dd MMM yyyy HH:mm') : '—' },
    { label: 'Resolution',      value: alert.resolution_notes    || '—' },
  ]

  return (
    <motion.tr
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
    >
      <td colSpan={9} style={{
        background:   C.surfaceHigh,
        borderBottom: `1px solid ${C.border}`,
        padding:      '16px 22px',
      }}>
        <div style={{
          display:             'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap:                 14,
        }}>
          {fields.map(({ label, value }) => (
            <div key={label}>
              <div style={{
                fontFamily:    'Space Mono, monospace',
                fontSize:      9,
                color:         C.textMuted,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                marginBottom:  4,
              }}>{label}</div>
              <div style={{
                fontFamily: 'IBM Plex Sans, sans-serif',
                fontSize:   13,
                color:      C.text,
                wordBreak:  'break-word',
              }}>{value}</div>
            </div>
          ))}
        </div>

        {/* Actions taken list */}
        {Array.isArray(alert.actions_taken) && alert.actions_taken.length > 0 && (
          <div style={{ marginTop: 14 }}>
            <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 8 }}>
              Actions Taken
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {alert.actions_taken.map((a, i) => (
                <div key={i} style={{
                  fontFamily:  'IBM Plex Sans, sans-serif',
                  fontSize:    12,
                  color:       C.textSub,
                  padding:     '4px 10px',
                  background:  C.surface,
                  borderRadius: 3,
                  borderLeft:  `2px solid ${C.success}`,
                }}>
                  {typeof a === 'string' ? a : JSON.stringify(a)}
                </div>
              ))}
            </div>
          </div>
        )}
      </td>
    </motion.tr>
  )
}

// ─── Inline action sub-row ──────────────────────────────────────────────────────
// acknowledge → POST /risk/alerts/{id}/acknowledge/ { notes }
// resolve     → POST /risk/alerts/{id}/resolve/     { resolution_notes, actions_taken }
// close       → POST /risk/alerts/{id}/close/       {}
function ActionRow({ alertId, action, onConfirm, onCancel }) {
  const [notes,       setNotes]       = useState('')
  const [actionsList, setActionsList] = useState('')  // comma-sep for 'resolve'
  const [loading,     setLoading]     = useState(false)

  const handleConfirm = async () => {
    setLoading(true)
    const payload =
      action === 'acknowledge' ? { notes } :
      action === 'resolve'     ? {
        resolution_notes: notes,
        actions_taken:    actionsList ? actionsList.split(',').map((s) => s.trim()).filter(Boolean) : [],
      } : {}
    await onConfirm(alertId, action, payload)
    setLoading(false)
  }

  const meta = {
    acknowledge: { label: 'Acknowledge', variant: 'warning',  note_label: 'Notes (optional)' },
    resolve:     { label: 'Resolve',     variant: 'success',  note_label: 'Resolution notes' },
    close:       { label: 'Close',       variant: 'ghost',    note_label: null },
  }[action] || { label: action, variant: 'ghost', note_label: null }

  return (
    <motion.tr
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.18 }}
    >
      <td colSpan={9} style={{
        background:   'rgba(59,130,246,0.04)',
        borderTop:    `1px solid ${C.accent}25`,
        borderBottom: `1px solid ${C.accent}25`,
        padding:      '12px 22px',
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
          {meta.note_label && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: '1 1 220px' }}>
              <label style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                {meta.note_label}
              </label>
              <input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={meta.note_label}
                style={{
                  background:  C.surface,
                  border:      `1.5px solid ${C.border}`,
                  color:       C.text,
                  borderRadius: 4,
                  padding:     '7px 11px',
                  fontFamily:  'IBM Plex Sans, sans-serif',
                  fontSize:    13,
                  outline:     'none',
                }}
              />
            </div>
          )}

          {action === 'resolve' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: '1 1 200px' }}>
              <label style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                Actions taken (comma-sep)
              </label>
              <input
                value={actionsList}
                onChange={(e) => setActionsList(e.target.value)}
                placeholder="e.g. Deployed team, Notified region…"
                style={{
                  background:  C.surface,
                  border:      `1.5px solid ${C.border}`,
                  color:       C.text,
                  borderRadius: 4,
                  padding:     '7px 11px',
                  fontFamily:  'IBM Plex Sans, sans-serif',
                  fontSize:    13,
                  outline:     'none',
                }}
              />
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', paddingTop: meta.note_label ? 22 : 0 }}>
            <Btn variant={meta.variant} onClick={handleConfirm} loading={loading}>
              {meta.label}
            </Btn>
            <Btn variant="ghost" onClick={onCancel} style={{ padding: '7px 12px' }}>
              Cancel
            </Btn>
          </div>
        </div>
      </td>
    </motion.tr>
  )
}

// ─── Table skeleton ─────────────────────────────────────────────────────────────
function TableSkeleton() {
  return (
    <>
      {[...Array(8)].map((_, i) => (
        <tr key={i} style={{ borderBottom: `1px solid ${C.border}` }}>
          <td style={{ padding: '13px 14px' }}><Shimmer width={16} height={16} radius={2} /></td>
          <td style={{ padding: '13px 14px' }}><Shimmer width={66} height={16} /></td>
          <td style={{ padding: '13px 14px' }}><Shimmer width={180} height={14} /></td>
          <td style={{ padding: '13px 14px' }}><Shimmer width={100} height={14} /></td>
          <td style={{ padding: '13px 14px' }}><Shimmer width={100} height={14} /></td>
          <td style={{ padding: '13px 14px' }}><Shimmer width={110} height={14} /></td>
          <td style={{ padding: '13px 14px' }}><Shimmer width={80}  height={14} /></td>
          <td style={{ padding: '13px 14px' }}><Shimmer width={76}  height={16} /></td>
          <td style={{ padding: '13px 14px' }}><Shimmer width={80}  height={28} /></td>
        </tr>
      ))}
    </>
  )
}

// ─── Mobile card ────────────────────────────────────────────────────────────────
function MobileAlertCard({ alert, onAction, onExpand, expanded }) {
  const sev   = alert.severity || alert.level || 'MEDIUM'
  const stat  = alert.status   || 'ACTIVE'
  const sevColor  = SEVERITY_COLOR[sev]  || C.textMuted
  const statColor = STATUS_COLOR[stat]   || C.textMuted
  const nextAction = NEXT_ACTION[stat]

  return (
    <div style={{
      background:   C.surface,
      border:       `1px solid ${C.border}`,
      borderRadius: 6,
      overflow:     'hidden',
      marginBottom: 10,
    }}>
      {/* Card header */}
      <div
        onClick={onExpand}
        style={{
          display:    'flex',
          alignItems: 'center',
          gap:        10,
          padding:    '12px 14px',
          cursor:     'pointer',
        }}
      >
        <div style={{ width: 3, alignSelf: 'stretch', borderRadius: 1, background: sevColor, flexShrink: 0 }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontFamily:   'IBM Plex Sans, sans-serif',
            fontSize:     13,
            color:        C.text,
            fontWeight:   600,
            overflow:     'hidden',
            textOverflow: 'ellipsis',
            whiteSpace:   'nowrap',
            marginBottom: 5,
          }}>
            {alert.title || '—'}
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <Badge label={sev} color={sevColor} />
            <Badge label={stat} color={statColor} />
            <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted }}>
              {alert.location_name || alert.location?.name || '—'}
            </span>
          </div>
        </div>
        <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, flexShrink: 0 }}>
          {expanded ? '▲' : '▼'}
        </span>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{ padding: '10px 14px 14px', borderTop: `1px solid ${C.border}` }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
            {[
              { label: 'Disease',  value: alert.disease_name || alert.disease_code || '—' },
              { label: 'Score',    value: alert.risk_score ?? '—' },
              { label: 'Opened',   value: alert.created_at ? formatDistanceToNow(new Date(alert.created_at), { addSuffix: true }) : '—' },
              { label: 'Updated',  value: alert.updated_at ? formatDistanceToNow(new Date(alert.updated_at), { addSuffix: true }) : '—' },
            ].map(({ label, value }) => (
              <div key={label}>
                <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 2 }}>{label}</div>
                <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: C.text }}>{value}</div>
              </div>
            ))}
          </div>
          {alert.description && (
            <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: C.textSub, marginBottom: 12, lineHeight: 1.5 }}>
              {alert.description}
            </div>
          )}
          {nextAction && (
            <Btn
              variant={nextAction === 'acknowledge' ? 'warning' : nextAction === 'resolve' ? 'success' : 'ghost'}
              onClick={() => onAction(alert.id, nextAction)}
              style={{ width: '100%', textAlign: 'center' }}
            >
              {nextAction.charAt(0).toUpperCase() + nextAction.slice(1)}
            </Btn>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Main page ──────────────────────────────────────────────────────────────────
export default function Alerts() {
  const toast = useToast()

  // ── Data state ──────────────────────────────────────────────────────────────
  const [alerts,  setAlerts]  = useState([])
  const [count,   setCount]   = useState(0)
  const [page,    setPage]    = useState(1)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(false)

  // ── Filter state ────────────────────────────────────────────────────────────
  const [filters, setFilters] = useState({
    severity: '', status: '', search: '',
    dateFrom: '', dateTo: '',
    _resetKey: 0,   // increment to force input remount on reset
  })

  // ── Table UI state ──────────────────────────────────────────────────────────
  const [expanded,     setExpanded]     = useState(null)    // alert.id with open detail
  const [actionRow,    setActionRow]    = useState(null)    // { id, action }
  const [selected,     setSelected]     = useState(new Set())
  const [bulkLoading,  setBulkLoading]  = useState(false)
  const [bulkConfirm,  setBulkConfirm]  = useState(false)   // confirmation step for bulk-ack
  const [mobileExpanded, setMobileExpanded] = useState(null)

  // ── WS new-alert tracking ───────────────────────────────────────────────────
  const [newCount,   setNewCount]   = useState(0)
  const [newAlertId, setNewAlertId] = useState(null)
  const tableTopRef = useRef(null)
  const knownIds    = useRef(new Set())

  // ── WS stream ───────────────────────────────────────────────────────────────
  const { data: streamData, status: streamStatus } = useAlertStream()

  // ── Responsive breakpoint ───────────────────────────────────────────────────
  const [isMobile, setIsMobile] = useState(false)
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 640)
    check()
    window.addEventListener('resize', check, { passive: true })
    return () => window.removeEventListener('resize', check)
  }, [])

  // ── Fetch ────────────────────────────────────────────────────────────────────
  const fetchAlerts = useCallback(async (pg, flt) => {
    setLoading(true)
    setError(false)
    try {
      const params = {
        page: pg,
        page_size: PAGE_SIZE,
        ...(flt.severity && { severity:        flt.severity }),
        ...(flt.status   && { status:          flt.status   }),
        ...(flt.search   && { search:          flt.search   }),
        ...(flt.dateFrom && { created_at__gte: flt.dateFrom }),
        ...(flt.dateTo   && { created_at__lte: flt.dateTo   }),
        ordering: '-created_at',
      }
      const res = await riskApi.listAlerts(params)
      const rows = res.data?.results ?? res.data ?? []
      setAlerts(rows)
      setCount(res.data?.count ?? rows.length)
      rows.forEach((a) => knownIds.current.add(a.id))
      setSelected(new Set())
    } catch (err) {
      setError(true)
      toast.error(extractError(err) || 'Failed to load alerts')
    } finally {
      setLoading(false)
    }
  }, [page, filters]) // eslint-disable-line

  useEffect(() => { fetchAlerts(page, filters) }, [page, filters]) // eslint-disable-line

  // ── Prepend WS alerts ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!streamData?.length) return
    const latest = streamData[0]
    if (!latest?.id || knownIds.current.has(latest.id)) return
    knownIds.current.add(latest.id)
    setNewCount((p) => p + 1)
    setAlerts((prev) => [latest, ...prev.slice(0, PAGE_SIZE - 1)])
    setCount((p) => p + 1)
    setNewAlertId(latest.id)
    setTimeout(() => setNewAlertId(null), 2000)
  }, [streamData])

  // ── Filter helpers ───────────────────────────────────────────────────────────
  const handleFilterChange = (key, val) => {
    setPage(1)
    setFilters((p) => ({ ...p, [key]: val }))
    setExpanded(null)
    setActionRow(null)
    setBulkConfirm(false)
  }

  const handleReset = () => {
    setPage(1)
    setFilters({ severity: '', status: '', search: '', dateFrom: '', dateTo: '', _resetKey: filters._resetKey + 1 })
    setExpanded(null)
    setActionRow(null)
    setBulkConfirm(false)
  }

  // ── Row action confirm ───────────────────────────────────────────────────────
  // Correct payloads per api.js:
  //   acknowledge → { notes: '' }
  //   resolve     → { resolution_notes: '', actions_taken: [] }
  //   close       → {}
  const handleActionConfirm = useCallback(async (alertId, action, payload) => {
    try {
      if (action === 'acknowledge') {
        await riskApi.acknowledgeAlert(alertId, payload)
      } else if (action === 'resolve') {
        await riskApi.resolveAlert(alertId, payload)
      } else if (action === 'close') {
        await riskApi.closeAlert(alertId, {})
      }

      // Optimistic status update
      const newStatus = action === 'acknowledge' ? 'ACKNOWLEDGED'
                      : action === 'resolve'     ? 'RESOLVED'
                      :                            'CLOSED'
      setAlerts((prev) =>
        prev.map((a) => a.id === alertId ? { ...a, status: newStatus } : a)
      )
      toast.success(`Alert ${action}d`)
    } catch (err) {
      toast.error(extractError(err) || `Failed to ${action} alert`)
    } finally {
      setActionRow(null)
    }
  }, [])

  // ── Bulk acknowledge ─────────────────────────────────────────────────────────
  // Two-step: click → show confirmation banner → confirm → execute
  const handleBulkAcknowledge = useCallback(async () => {
    if (!selected.size) return
    setBulkLoading(true)
    setBulkConfirm(false)
    try {
      await riskApi.bulkAcknowledgeAlerts({ ids: [...selected] })
      setAlerts((prev) =>
        prev.map((a) => selected.has(a.id) ? { ...a, status: 'ACKNOWLEDGED' } : a)
      )
      toast.success(`${selected.size} alert(s) acknowledged`)
      setSelected(new Set())
    } catch (err) {
      toast.error(extractError(err) || 'Bulk acknowledge failed')
    } finally {
      setBulkLoading(false)
    }
  }, [selected])

  // ── Select helpers ───────────────────────────────────────────────────────────
  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    setSelected(
      selected.size === alerts.length
        ? new Set()
        : new Set(alerts.map((a) => a.id))
    )
  }

  // ── Pagination ───────────────────────────────────────────────────────────────
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE))

  // ── Mobile quick-action handler ──────────────────────────────────────────────
  const handleMobileAction = useCallback(async (alertId, action) => {
    const payload =
      action === 'acknowledge' ? { notes: '' } :
      action === 'resolve'     ? { resolution_notes: '', actions_taken: [] } :
                                  {}
    await handleActionConfirm(alertId, action, payload)
  }, [handleActionConfirm])

  // ─────────────────────────────────────────────────────────────────────────────
  return (
    <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', color: C.text }}>
      <style>{`
        @keyframes al-shimmer { to { background-position: -200% 0 } }
        @keyframes al-spin    { to { transform: rotate(360deg) } }
        @keyframes al-pulse   { 0%,100% { opacity:1 } 50% { opacity:0.35 } }
        @keyframes al-flash   {
          0%   { box-shadow: inset 0 0 0 2px ${C.accent} }
          100% { box-shadow: none }
        }
      `}</style>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        style={{ marginBottom: 22 }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{
              fontFamily:    'Bebas Neue, sans-serif',
              fontSize:      30,
              color:         C.text,
              letterSpacing: '0.04em',
              lineHeight:    1,
              marginBottom:  4,
            }}>Alert Management</div>
            <div style={{
              fontFamily:    'Space Mono, monospace',
              fontSize:      9,
              color:         C.textMuted,
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
            }}>
              {loading ? 'Loading…' : `${count} alerts · Page ${page} of ${totalPages}`}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            {selected.size > 0 && !bulkConfirm && (
              <Btn variant="warning" onClick={() => setBulkConfirm(true)} loading={bulkLoading}>
                Acknowledge {selected.size} selected
              </Btn>
            )}
            {bulkConfirm && (
              <>
                <span style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: C.warning }}>
                  Acknowledge {selected.size} alert{selected.size > 1 ? 's' : ''}?
                </span>
                <Btn variant="warning" onClick={handleBulkAcknowledge} loading={bulkLoading}>Confirm</Btn>
                <Btn variant="ghost" onClick={() => setBulkConfirm(false)}>Cancel</Btn>
              </>
            )}
            <Btn variant="ghost" onClick={() => fetchAlerts(page, filters)} style={{ padding: '7px 12px' }}>
              Refresh
            </Btn>
          </div>
        </div>
      </motion.div>

      {/* ── Filter bar ─────────────────────────────────────────────────────── */}
      <FilterBar
        filters={filters}
        onChange={handleFilterChange}
        onReset={handleReset}
        streamStatus={streamStatus}
        liveCount={newCount}
      />

      {/* ── New alert banner ────────────────────────────────────────────────── */}
      <AnimatePresence>
        {newCount > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            onClick={() => {
              tableTopRef.current?.scrollIntoView({ behavior: 'smooth' })
              setNewCount(0)
            }}
            style={{
              background:    'rgba(245,158,11,0.07)',
              border:        '1px solid rgba(245,158,11,0.22)',
              borderRadius:  4,
              padding:       '8px 16px',
              marginBottom:  12,
              cursor:        'pointer',
              fontFamily:    'Space Mono, monospace',
              fontSize:      9,
              color:         C.warning,
              letterSpacing: '0.1em',
              textAlign:     'center',
              textTransform: 'uppercase',
            }}
          >
            ↑ {newCount} new alert{newCount !== 1 ? 's' : ''} received — click to scroll to top
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Mobile card view ────────────────────────────────────────────────── */}
      {isMobile && (
        <div>
          {loading && [...Array(5)].map((_, i) => (
            <div key={i} style={{ marginBottom: 10 }}>
              <Shimmer height={72} radius={6} />
            </div>
          ))}
          {!loading && error && (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <div style={{ color: C.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, marginBottom: 12 }}>
                Failed to load alerts
              </div>
              <Btn variant="ghost" onClick={() => fetchAlerts(page, filters)}>Retry</Btn>
            </div>
          )}
          {!loading && !error && alerts.length === 0 && (
            <div style={{ textAlign: 'center', padding: '60px 0', color: C.textMuted, fontFamily: 'Space Mono, monospace', fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
              No alerts match your filters
            </div>
          )}
          {!loading && !error && alerts.map((alert) => (
            <MobileAlertCard
              key={alert.id}
              alert={alert}
              onAction={handleMobileAction}
              onExpand={() => setMobileExpanded(mobileExpanded === alert.id ? null : alert.id)}
              expanded={mobileExpanded === alert.id}
            />
          ))}

          {/* Mobile pagination */}
          {!loading && !error && totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 12 }}>
              <Btn variant="ghost" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>← Prev</Btn>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted }}>
                {page} / {totalPages}
              </span>
              <Btn variant="ghost" disabled={page === totalPages} onClick={() => setPage((p) => p + 1)}>Next →</Btn>
            </div>
          )}
        </div>
      )}

      {/* ── Desktop table view ──────────────────────────────────────────────── */}
      {!isMobile && (
        <div style={{
          background:   C.surface,
          border:       `1px solid ${C.border}`,
          borderRadius: 8,
          overflow:     'hidden',
        }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'auto' }}>
              <thead>
                <tr ref={tableTopRef}>
                  {/* Select all */}
                  <TH style={{ width: 42, padding: '10px 14px' }}>
                    <input
                      type="checkbox"
                      checked={alerts.length > 0 && selected.size === alerts.length}
                      onChange={toggleSelectAll}
                      style={{ cursor: 'pointer', accentColor: C.accent }}
                    />
                  </TH>
                  <TH>Severity</TH>
                  <TH style={{ minWidth: 220 }}>Title</TH>
                  <TH>Location</TH>
                  <TH>Disease</TH>
                  <TH>Opened</TH>
                  <TH>Updated</TH>
                  <TH>Status</TH>
                  <TH style={{ width: 130 }}>Action</TH>
                </tr>
              </thead>
              <tbody>
                {loading && <TableSkeleton />}

                {!loading && error && (
                  <tr>
                    <td colSpan={9} style={{ padding: '60px 0', textAlign: 'center' }}>
                      <div style={{ color: C.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, marginBottom: 12 }}>
                        Failed to load alerts
                      </div>
                      <Btn variant="ghost" onClick={() => fetchAlerts(page, filters)}>Retry</Btn>
                    </td>
                  </tr>
                )}

                {!loading && !error && alerts.length === 0 && (
                  <tr>
                    <td colSpan={9} style={{ padding: '60px 0', textAlign: 'center' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
                        <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                          <circle cx="16" cy="16" r="13" stroke={C.textMuted} strokeWidth="1.4" />
                          <path d="M10 22l4-4 3 3 6-8" stroke={C.textMuted} strokeWidth="1.4" strokeLinecap="round" />
                        </svg>
                        <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                          No alerts match your filters
                        </span>
                      </div>
                    </td>
                  </tr>
                )}

                {!loading && !error && alerts.map((alert, i) => {
                  const sev         = alert.severity || alert.level || 'MEDIUM'
                  const stat        = alert.status   || 'ACTIVE'
                  const sevColor    = SEVERITY_COLOR[sev]  || C.textMuted
                  const statColor   = STATUS_COLOR[stat]   || C.textMuted
                  const isExpanded  = expanded === alert.id
                  const hasAction   = actionRow?.id === alert.id
                  const isNew       = newAlertId === alert.id
                  const isSelected  = selected.has(alert.id)
                  const nextAction  = NEXT_ACTION[stat]

                  const baseBg = isSelected ? C.accentBg : isNew ? `${C.accent}10` : C.surface

                  return (
                    <AnimatePresence key={alert.id} mode="sync">
                      <tr
                        style={{
                          background:   baseBg,
                          borderBottom: `1px solid ${C.border}`,
                          cursor:       'pointer',
                          animation:    isNew ? 'al-flash 1.5s ease-out' : 'none',
                          transition:   'background 0.15s',
                        }}
                        onMouseEnter={(e) => {
                          if (!isSelected && !isNew)
                            e.currentTarget.style.background = C.surfaceHigh
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = baseBg
                        }}
                      >
                        {/* Checkbox */}
                        <td style={{ padding: '12px 14px' }} onClick={(e) => { e.stopPropagation(); toggleSelect(alert.id) }}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSelect(alert.id)}
                            onClick={(e) => e.stopPropagation()}
                            style={{ cursor: 'pointer', accentColor: C.accent }}
                          />
                        </td>

                        {/* Severity */}
                        <td style={{ padding: '12px 14px' }} onClick={() => { setExpanded(isExpanded ? null : alert.id); setActionRow(null) }}>
                          <Badge label={sev} color={sevColor} />
                        </td>

                        {/* Title */}
                        <td
                          style={{ padding: '12px 14px', fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: C.text, maxWidth: 260, overflow: 'hidden' }}
                          onClick={() => { setExpanded(isExpanded ? null : alert.id); setActionRow(null) }}
                        >
                          <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 260 }}>
                            {alert.title || '—'}
                          </div>
                        </td>

                        {/* Location */}
                        <td
                          style={{ padding: '12px 14px', fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: C.textSub }}
                          onClick={() => { setExpanded(isExpanded ? null : alert.id); setActionRow(null) }}
                        >
                          {alert.location_name || alert.location?.name || '—'}
                        </td>

                        {/* Disease */}
                        <td
                          style={{ padding: '12px 14px', fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: C.textSub }}
                          onClick={() => { setExpanded(isExpanded ? null : alert.id); setActionRow(null) }}
                        >
                          {alert.disease_name || alert.disease_code || '—'}
                        </td>

                        {/* Opened */}
                        <td
                          style={{ padding: '12px 14px', fontFamily: 'Space Mono, monospace', fontSize: 10, color: C.textSub, whiteSpace: 'nowrap' }}
                          onClick={() => { setExpanded(isExpanded ? null : alert.id); setActionRow(null) }}
                        >
                          {alert.created_at ? format(new Date(alert.created_at), 'dd MMM yy HH:mm') : '—'}
                        </td>

                        {/* Updated */}
                        <td
                          style={{ padding: '12px 14px', fontFamily: 'Space Mono, monospace', fontSize: 10, color: C.textMuted, whiteSpace: 'nowrap' }}
                          onClick={() => { setExpanded(isExpanded ? null : alert.id); setActionRow(null) }}
                        >
                          {alert.updated_at ? formatDistanceToNow(new Date(alert.updated_at), { addSuffix: true }) : '—'}
                        </td>

                        {/* Status */}
                        <td
                          style={{ padding: '12px 14px' }}
                          onClick={() => { setExpanded(isExpanded ? null : alert.id); setActionRow(null) }}
                        >
                          <Badge label={stat} color={statColor} />
                        </td>

                        {/* Action button */}
                        <td style={{ padding: '12px 14px' }} onClick={(e) => e.stopPropagation()}>
                          {nextAction ? (
                            <Btn
                              variant={
                                nextAction === 'acknowledge' ? 'warning' :
                                nextAction === 'resolve'     ? 'success' :
                                                               'ghost'
                              }
                              style={{ padding: '5px 11px' }}
                              onClick={() => {
                                setExpanded(null)
                                setActionRow(hasAction ? null : { id: alert.id, action: nextAction })
                              }}
                            >
                              {hasAction ? 'Cancel' : nextAction}
                            </Btn>
                          ) : (
                            <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, letterSpacing: '0.1em' }}>
                              CLOSED
                            </span>
                          )}
                        </td>
                      </tr>

                      {/* Action sub-row */}
                      <AnimatePresence>
                        {hasAction && (
                          <ActionRow
                            key={`action-${alert.id}`}
                            alertId={alert.id}
                            action={actionRow.action}
                            onConfirm={handleActionConfirm}
                            onCancel={() => setActionRow(null)}
                          />
                        )}
                      </AnimatePresence>

                      {/* Detail expansion */}
                      <AnimatePresence>
                        {isExpanded && !hasAction && (
                          <AlertDetail key={`detail-${alert.id}`} alert={alert} />
                        )}
                      </AnimatePresence>
                    </AnimatePresence>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {!loading && !error && alerts.length > 0 && (
            <div style={{
              display:        'flex',
              alignItems:     'center',
              justifyContent: 'space-between',
              padding:        '11px 18px',
              borderTop:      `1px solid ${C.border}`,
              flexWrap:       'wrap',
              gap:            10,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                  Page {page} of {totalPages} · {count} total
                </span>
                {selected.size > 0 && (
                  <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.accent, letterSpacing: '0.1em' }}>
                    {selected.size} selected
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <Btn
                  variant="ghost"
                  disabled={page === 1}
                  style={{ padding: '6px 14px' }}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  ← Prev
                </Btn>

                {/* Page number pills — show up to 5 around current */}
                {Array.from({ length: totalPages }, (_, i) => i + 1)
                  .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 2)
                  .reduce((acc, p, idx, arr) => {
                    if (idx > 0 && p - arr[idx - 1] > 1) acc.push('…')
                    acc.push(p)
                    return acc
                  }, [])
                  .map((p, i) =>
                    p === '…' ? (
                      <span key={`ellipsis-${i}`} style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMuted, padding: '6px 4px', alignSelf: 'center' }}>…</span>
                    ) : (
                      <Btn
                        key={p}
                        variant={p === page ? 'primary' : 'ghost'}
                        style={{ padding: '6px 11px', minWidth: 34, textAlign: 'center' }}
                        onClick={() => setPage(p)}
                      >
                        {p}
                      </Btn>
                    )
                  )
                }

                <Btn
                  variant="ghost"
                  disabled={page === totalPages}
                  style={{ padding: '6px 14px' }}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next →
                </Btn>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}