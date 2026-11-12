/**
 * AuditLogs — OryxShield
 * =================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Read-only audit trail viewer (superuser / admin only).
 *
 * API (coreApi — verified against core URLs):
 *   GET  /audit-logs/                  listAuditLogs(params)
 *   GET  /audit-logs/{id}/             getAuditLog(id)
 *   GET  /audit-logs/activity_summary/ auditActivitySummary()
 *   GET  /audit-logs/export_csv/       exportAuditLogs()  → blob
 */

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { format, formatDistanceToNow } from 'date-fns'
import { coreApi, extractError } from '../../services/api'
import { useToast } from '../../context/ToastContext'

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

const PAGE_SIZE = 50

const ACTION_COLOR = {
  CREATE:          C.success,
  UPDATE:          C.accent,
  DELETE:          C.danger,
  VIEW:            C.textMuted,
  LOGIN:           '#a78bfa',
  LOGOUT:          '#a78bfa',
  LOGIN_FAILED:    C.danger,
  EXPORT:          C.warning,
  IMPORT:          C.warning,
  APPROVE:         C.success,
  REJECT:          C.danger,
  ACTIVATE:        C.success,
  DEACTIVATE:      '#f97316',
  ESCALATE:        '#f97316',
  ALERT:           C.danger,
  CONFIGURE:       C.accent,
  INTEGRATE:       '#a78bfa',
  DOWNLOAD:        C.warning,
  UPLOAD:          C.warning,
  PASSWORD_CHANGE: '#a78bfa',
  PASSWORD_RESET:  '#a78bfa',
}

function LogRow({ log, onExpand }) {
  const [hovered, setHovered] = useState(false)
  const actionColor = log.success === false ? C.danger : (ACTION_COLOR[log.action] || C.textSub)

  return (
    <tr
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => onExpand(log)}
      style={{
        background:  hovered ? C.surfaceHigh : 'transparent',
        cursor:      'pointer',
        transition:  'background 0.12s',
        borderBottom: `1px solid ${C.border}`,
      }}
    >
      <td style={{ padding: '10px 14px', fontSize: 12, color: C.textMuted, whiteSpace: 'nowrap' }}>
        {format(new Date(log.created_at), 'dd MMM yyyy HH:mm:ss')}
      </td>
      <td style={{ padding: '10px 14px', fontSize: 12, color: C.textSub }}>
        {log.username || log.user_display || '—'}
      </td>
      <td style={{ padding: '10px 14px' }}>
        <span style={{
          display:      'inline-block',
          padding:      '2px 8px',
          borderRadius: 10,
          fontSize:     11,
          fontWeight:   700,
          background:   `${actionColor}18`,
          color:        actionColor,
          border:       `1px solid ${actionColor}40`,
          letterSpacing: '0.04em',
        }}>{log.action}</span>
      </td>
      <td style={{ padding: '10px 14px', fontSize: 12, color: C.textSub }}>{log.model_name || '—'}</td>
      <td style={{ padding: '10px 14px', fontSize: 12, color: C.text, maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {log.object_repr || log.object_id || '—'}
      </td>
      <td style={{ padding: '10px 14px', textAlign: 'center' }}>
        {log.success === false
          ? <span style={{ color: C.danger, fontSize: 12 }}>✗</span>
          : <span style={{ color: C.success, fontSize: 12 }}>✓</span>
        }
      </td>
      <td style={{ padding: '10px 14px', fontSize: 12, color: C.textMuted }}>{log.ip_address || '—'}</td>
    </tr>
  )
}

function LogDetail({ log, onClose }) {
  if (!log) return null
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.6)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
      }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        onClick={e => e.stopPropagation()}
        style={{
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 12,
          width: '100%',
          maxWidth: 640,
          maxHeight: '80vh',
          overflowY: 'auto',
          padding: 24,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 style={{ margin: 0, color: C.text, fontSize: 16 }}>Audit Entry Detail</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: C.textMuted, fontSize: 20, cursor: 'pointer' }}>×</button>
        </div>

        {[
          ['ID',          log.id],
          ['Timestamp',   log.created_at ? format(new Date(log.created_at), 'dd MMM yyyy HH:mm:ss') : '—'],
          ['User',        log.username || log.user_display || '—'],
          ['Action',      log.action],
          ['Model',       log.model_name || '—'],
          ['Object ID',   log.object_id || '—'],
          ['Object',      log.object_repr || '—'],
          ['Success',     log.success === false ? 'No' : 'Yes'],
          ['IP Address',  log.ip_address || '—'],
          ['User Agent',  log.user_agent || '—'],
          ['Request',     log.request_method && log.request_path ? `${log.request_method} ${log.request_path}` : '—'],
          ['Error',       log.error_message || '—'],
        ].map(([label, val]) => (
          <div key={label} style={{ display: 'flex', gap: 12, padding: '6px 0', borderBottom: `1px solid ${C.border}` }}>
            <span style={{ width: 110, flexShrink: 0, fontSize: 12, color: C.textMuted }}>{label}</span>
            <span style={{ fontSize: 12, color: C.text, wordBreak: 'break-word' }}>{String(val)}</span>
          </div>
        ))}

        {log.changes && (
          <div style={{ marginTop: 14 }}>
            <p style={{ margin: '0 0 8px', fontSize: 12, color: C.textMuted }}>Changes</p>
            <pre style={{
              background: '#070b17', border: `1px solid ${C.border}`,
              borderRadius: 6, padding: 12,
              fontSize: 11, color: C.textSub,
              overflowX: 'auto', margin: 0,
            }}>{JSON.stringify(log.changes, null, 2)}</pre>
          </div>
        )}

        {log.metadata && (
          <div style={{ marginTop: 14 }}>
            <p style={{ margin: '0 0 8px', fontSize: 12, color: C.textMuted }}>Metadata</p>
            <pre style={{
              background: '#070b17', border: `1px solid ${C.border}`,
              borderRadius: 6, padding: 12,
              fontSize: 11, color: C.textSub,
              overflowX: 'auto', margin: 0,
            }}>{JSON.stringify(log.metadata, null, 2)}</pre>
          </div>
        )}
      </motion.div>
    </div>
  )
}

export default function AuditLogs() {
  const { error: toastError, success: toastSuccess } = useToast()

  const [logs, setLogs]       = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage]       = useState(1)
  const [total, setTotal]     = useState(0)
  const [search, setSearch]   = useState('')
  const [action, setAction]   = useState('')
  const [model, setModel]     = useState('')
  const [expanded, setExpanded] = useState(null)
  const [exporting, setExporting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE }
      if (search) params.search = search
      if (action) params.action = action
      if (model)  params.model_name = model
      const res = await coreApi.listAuditLogs(params)
      const data = res.data
      setLogs(data.results || [])
      setTotal(data.count || 0)
    } catch (e) {
      toastError(extractError(e))
    } finally {
      setLoading(false)
    }
  }, [page, search, action, model, toastError])

  useEffect(() => { load() }, [load])

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await coreApi.exportAuditLogs()
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `audit_logs_${format(new Date(), 'yyyyMMdd_HHmm')}.csv`
      a.click()
      URL.revokeObjectURL(url)
      toastSuccess('Audit log exported.')
    } catch (e) {
      toastError(extractError(e))
    } finally {
      setExporting(false)
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const ACTIONS = ['CREATE','UPDATE','DELETE','VIEW','LOGIN','LOGOUT','LOGIN_FAILED',
    'EXPORT','IMPORT','APPROVE','REJECT','ACTIVATE','DEACTIVATE','ESCALATE','ALERT',
    'CONFIGURE','INTEGRATE','DOWNLOAD','UPLOAD','PASSWORD_CHANGE','PASSWORD_RESET']

  return (
    <div style={{ minHeight: '100vh', background: C.bg, padding: '24px 20px' }}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>

        {/* ── Header ──────────────────────────────────────────────────────────── */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: C.text }}>Audit Logs</h1>
            <p style={{ margin: '4px 0 0', fontSize: 13, color: C.textSub }}>
              Complete system audit trail · {total.toLocaleString()} entries
            </p>
          </div>
          <button
            onClick={handleExport}
            disabled={exporting}
            style={{
              padding: '8px 16px', borderRadius: 8,
              border: `1px solid ${C.warning}`,
              background: 'rgba(245,158,11,0.08)',
              color: C.warning, fontSize: 13,
              cursor: exporting ? 'not-allowed' : 'pointer',
              opacity: exporting ? 0.6 : 1,
            }}
          >
            {exporting ? 'Exporting…' : 'Export CSV'}
          </button>
        </div>

        {/* ── Filters ─────────────────────────────────────────────────────────── */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
          <input
            placeholder="Search user / object…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            style={{
              flex: '1 1 200px', padding: '8px 12px',
              background: C.surface, border: `1px solid ${C.border}`,
              borderRadius: 8, color: C.text, fontSize: 13, outline: 'none',
            }}
          />
          <select
            value={action}
            onChange={e => { setAction(e.target.value); setPage(1) }}
            style={{
              padding: '8px 12px', background: C.surface,
              border: `1px solid ${C.border}`, borderRadius: 8,
              color: action ? C.text : C.textMuted, fontSize: 13,
            }}
          >
            <option value="">All Actions</option>
            {ACTIONS.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
          <input
            placeholder="Model name…"
            value={model}
            onChange={e => { setModel(e.target.value); setPage(1) }}
            style={{
              width: 160, padding: '8px 12px',
              background: C.surface, border: `1px solid ${C.border}`,
              borderRadius: 8, color: C.text, fontSize: 13, outline: 'none',
            }}
          />
        </div>

        {/* ── Table ───────────────────────────────────────────────────────────── */}
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: C.surfaceHigh }}>
                  {['Timestamp','User','Action','Model','Object','OK','IP'].map(h => (
                    <th key={h} style={{
                      padding: '10px 14px', textAlign: 'left',
                      fontSize: 11, fontWeight: 700, color: C.textMuted,
                      letterSpacing: '0.06em', textTransform: 'uppercase',
                      borderBottom: `1px solid ${C.border}`,
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={7} style={{ textAlign: 'center', padding: 40, color: C.textMuted, fontSize: 14 }}>Loading…</td></tr>
                ) : logs.length === 0 ? (
                  <tr><td colSpan={7} style={{ textAlign: 'center', padding: 40, color: C.textMuted, fontSize: 14 }}>No audit entries found.</td></tr>
                ) : (
                  logs.map(log => (
                    <LogRow key={log.id} log={log} onExpand={setExpanded} />
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── Pagination ──────────────────────────────────────────────────────── */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', justifyContent: 'center', gap: 10, marginTop: 20 }}>
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
              style={{ padding: '6px 16px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: page <= 1 ? C.textMuted : C.text, cursor: page <= 1 ? 'default' : 'pointer', fontSize: 13 }}>Prev</button>
            <span style={{ padding: '6px 12px', color: C.textSub, fontSize: 13 }}>{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
              style={{ padding: '6px 16px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: page >= totalPages ? C.textMuted : C.text, cursor: page >= totalPages ? 'default' : 'pointer', fontSize: 13 }}>Next</button>
          </div>
        )}
      </div>

      {/* ── Detail modal ────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {expanded && <LogDetail log={expanded} onClose={() => setExpanded(null)} />}
      </AnimatePresence>
    </div>
  )
}
