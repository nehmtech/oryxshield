/**
 * Response.jsx — OryxShield
 * ====================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Full response management hub — covers all 7 Django response models:
 *   ResponseLevel · ResponseProtocol · ResponseActivation
 *   EscalationTrigger · ActionItem · ResponseReport · DecisionLog
 *
 * Layout: tabbed, with a collapsing right sidebar for critical items.
 * Responsiveness: stacks to single column below 900 px; sidebar hidden below 1024 px.
 * All padding uses clamp(); tables scroll horizontally on small screens.
 * WS: useResponseStream auto-refreshes the Activations tab on matching events.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { responseApi, extractError } from '../../services/api'
import { useResponseStream } from '../../hooks/ws/useResponseStream'
import { useToast } from '../../context/ToastContext'

// ─── Design tokens ────────────────────────────────────────────────────────────
const T = {
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

const FONTS = {
  head: 'Bebas Neue, sans-serif',
  mono: 'Space Mono, monospace',
  body: 'IBM Plex Sans, sans-serif',
}

// ─── Status / priority colour maps ────────────────────────────────────────────
const STATUS_COLOR = {
  PENDING:     '#6b7280',
  ACTIVE:      T.accent,
  ESCALATED:   T.danger,
  DEESCALATED: T.purple,
  SUSPENDED:   T.warning,
  COMPLETED:   T.success,
  CANCELLED:   '#4b5563',
}

const PRIORITY_COLOR = {
  LOW:      T.success,
  MEDIUM:   T.warning,
  HIGH:     '#f97316',
  CRITICAL: T.danger,
}

const ACTION_STATUS_COLOR = {
  PENDING:     '#6b7280',
  IN_PROGRESS: T.accent,
  COMPLETED:   T.success,
  BLOCKED:     T.danger,
  CANCELLED:   '#4b5563',
}

const REPORT_TYPE_COLOR = {
  SITUATION:   T.accent,
  PROGRESS:    T.success,
  AFTER_ACTION:T.purple,
  DAILY:       T.warning,
}

const TRIGGER_TYPE_COLOR = {
  CASE_COUNT:   T.danger,
  RISK_SCORE:   T.warning,
  TIME_ELAPSED: T.accent,
  CAPACITY:     T.purple,
  MORTALITY:    '#f97316',
}

const PAGE_SIZE = 20

// ─── Tiny helpers ─────────────────────────────────────────────────────────────
const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.28, ease: 'easeOut', delay },
})

function fmtDate(v) {
  if (!v) return '—'
  return new Date(v).toLocaleString('en-NA', { dateStyle: 'short', timeStyle: 'short' })
}
function fmtDateOnly(v) {
  if (!v) return '—'
  return new Date(v).toLocaleDateString('en-NA', { day: '2-digit', month: 'short', year: 'numeric' })
}

// ─── Micro UI ─────────────────────────────────────────────────────────────────
const Badge = ({ label, color }) => (
  <span style={{
    fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.12em',
    textTransform: 'uppercase', color,
    background: color + '18', border: `1px solid ${color}30`,
    borderRadius: 2, padding: '2px 8px', whiteSpace: 'nowrap',
  }}>{label}</span>
)

const shimmerStyle = {
  background: `linear-gradient(90deg,${T.surface} 25%,${T.surfaceHigh} 50%,${T.surface} 75%)`,
  backgroundSize: '200% 100%',
  animation: 'resp-shimmer 1.5s infinite',
  borderRadius: 4,
}
const Shimmer = ({ w = '100%', h = 14 }) => (
  <div style={{ width: w, height: h, ...shimmerStyle }} />
)

function StatCard({ label, value, color = T.accent, icon, loading }) {
  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.border}`,
      borderRadius: 6, padding: '16px 20px', flex: 1, minWidth: 130,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10 }}>
        {icon && (
          <svg width={13} height={13} viewBox="0 0 24 24" fill="none"
            stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <path d={icon} />
          </svg>
        )}
        <span style={{ fontFamily: FONTS.mono, fontSize: 8, letterSpacing: '0.14em',
          textTransform: 'uppercase', color: T.textMuted }}>{label}</span>
      </div>
      {loading
        ? <Shimmer h={28} w={56} />
        : <div style={{ fontFamily: FONTS.head, fontSize: 32, color, lineHeight: 1 }}>
            {value ?? '—'}
          </div>
      }
    </div>
  )
}

function FilterPill({ label, active, onClick, color }) {
  return (
    <button onClick={onClick} style={{
      fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.1em',
      textTransform: 'uppercase', padding: '4px 12px', borderRadius: 20,
      border: `1px solid ${active ? (color || T.accent) + '60' : T.border}`,
      background: active ? (color || T.accent) + '1a' : 'transparent',
      color: active ? (color || T.accent) : T.textSub,
      cursor: 'pointer', transition: 'all 0.14s', whiteSpace: 'nowrap',
    }}>{label}</button>
  )
}

const ProbBar = ({ value }) => {
  const pct = Math.round((value ?? 0) * 100)
  const color = pct >= 80 ? T.danger : pct >= 50 ? T.warning : T.success
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, minWidth: 40, height: 4, background: T.border, borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2 }} />
      </div>
      <span style={{ fontFamily: FONTS.mono, fontSize: 9, color: T.textMuted, minWidth: 26 }}>{pct}%</span>
    </div>
  )
}

const ProgressRing = ({ pct, size = 44 }) => {
  const r = (size - 6) / 2
  const circ = 2 * Math.PI * r
  const dash = ((pct ?? 0) / 100) * circ
  const color = pct >= 75 ? T.success : pct >= 40 ? T.warning : T.accent
  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={size/2} cy={size/2} r={r} stroke={T.border} strokeWidth={3} fill="none" />
      <circle cx={size/2} cy={size/2} r={r} stroke={color} strokeWidth={3} fill="none"
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
        style={{ transition: 'stroke-dasharray 0.6s ease' }} />
    </svg>
  )
}

function ActionBtn({ onClick, children, icon, variant = 'ghost', disabled, small }) {
  const styles = {
    ghost:   { background: 'transparent', border: `1px solid ${T.border}`, color: T.textSub },
    accent:  { background: T.accent + '18', border: `1px solid ${T.accent}40`, color: T.accent },
    success: { background: T.success + '18', border: `1px solid ${T.success}40`, color: T.success },
    danger:  { background: T.danger + '18', border: `1px solid ${T.danger}40`, color: T.danger },
    warning: { background: T.warning + '18', border: `1px solid ${T.warning}40`, color: T.warning },
    solid:   { background: T.accent, border: `1px solid ${T.accent}`, color: '#fff' },
  }
  return (
    <button onClick={disabled ? undefined : onClick} style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      borderRadius: 4, padding: small ? '4px 10px' : '6px 14px',
      fontFamily: FONTS.body, fontSize: small ? 11 : 12,
      cursor: disabled ? 'not-allowed' : 'pointer',
      transition: 'all 0.14s', opacity: disabled ? 0.45 : 1,
      whiteSpace: 'nowrap',
      ...styles[variant],
    }}>{icon}<span>{children}</span></button>
  )
}

// ─── Table chrome ─────────────────────────────────────────────────────────────
const Th = ({ children }) => (
  <th style={{
    padding: '9px 14px', textAlign: 'left',
    fontFamily: FONTS.mono, fontSize: 8, letterSpacing: '0.12em',
    textTransform: 'uppercase', color: T.textMuted, fontWeight: 400,
    borderBottom: `1px solid ${T.border}`,
    background: T.surfaceHigh, whiteSpace: 'nowrap',
  }}>{children}</th>
)

const Td = ({ children, style }) => (
  <td style={{ padding: '10px 14px', borderBottom: `1px solid ${T.border}`, ...style }}>
    {children}
  </td>
)

function TableCard({ toolbar, children, footer }) {
  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden' }}>
      {toolbar && <div style={{ padding: '14px 18px', borderBottom: `1px solid ${T.border}` }}>{toolbar}</div>}
      <div style={{ overflowX: 'auto' }}>{children}</div>
      {footer}
    </div>
  )
}

function Pagination({ page, totalPages, totalCount, onPrev, onNext }) {
  if (totalPages <= 1) return null
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '11px 16px', borderTop: `1px solid ${T.border}`, flexWrap: 'wrap', gap: 8 }}>
      <span style={{ fontFamily: FONTS.mono, fontSize: 9, color: T.textMuted }}>
        Page {page} / {totalPages} · {totalCount} total
      </span>
      <div style={{ display: 'flex', gap: 6 }}>
        <button disabled={page === 1} onClick={onPrev} style={{
          background: 'transparent', border: `1px solid ${T.border}`, borderRadius: 4,
          padding: '4px 10px', fontFamily: FONTS.body, fontSize: 11,
          color: page === 1 ? T.border : T.textSub, cursor: page === 1 ? 'not-allowed' : 'pointer',
        }}>← Prev</button>
        <button disabled={page === totalPages} onClick={onNext} style={{
          background: 'transparent', border: `1px solid ${T.border}`, borderRadius: 4,
          padding: '4px 10px', fontFamily: FONTS.body, fontSize: 11,
          color: page === totalPages ? T.border : T.textSub, cursor: page === totalPages ? 'not-allowed' : 'pointer',
        }}>Next →</button>
      </div>
    </div>
  )
}

function EmptyRow({ cols, msg }) {
  return (
    <tr><td colSpan={cols} style={{ padding: '36px 14px', textAlign: 'center',
      color: T.textSub, fontFamily: FONTS.mono, fontSize: 10 }}>{msg}</td></tr>
  )
}

function ShimmerRows({ cols, n = 5 }) {
  return Array.from({ length: n }).map((_, i) => (
    <tr key={i}><td colSpan={cols} style={{ padding: '10px 14px' }}><Shimmer /></td></tr>
  ))
}

// ─── Level badge ──────────────────────────────────────────────────────────────
const LEVEL_COLORS = {1:'#10b981',2:'#3b82f6',3:'#f59e0b',4:'#f97316',5:'#ef4444'}
function LevelBadge({ level }) {
  const c = LEVEL_COLORS[level] || T.textMuted
  return <Badge label={`L${level}`} color={c} />
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB: ACTIVATIONS
// ═══════════════════════════════════════════════════════════════════════════════
function ActivationsTab({ navigate, wsMessages }) {
  const { error: toastErr, success: toastOk } = useToast()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [totalCount, setTotal] = useState(0)
  const [statusFilter, setStatus] = useState('ALL')
  const [hovered, setHovered] = useState(null)
  const [acting, setActing] = useState(null)
  const [levels, setLevels] = useState([])

  const [formOpen, setFormOpen] = useState(false)
  const [form, setForm]         = useState({ response_level:'', disease_name:'', disease_code:'', notes:'' })
  const [saving, setSaving]     = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE }
      if (statusFilter !== 'ALL') params.status = statusFilter
      const res = await responseApi.listActivations(params)
      setRows(res.data.results ?? res.data)
      setTotal(res.data.count ?? 0)
    } catch (e) { toastErr(extractError(e)) }
    finally { setLoading(false) }
  }, [page, statusFilter])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [statusFilter])
  useEffect(() => {
    responseApi.listLevels({ page_size: 20 }).then(r => setLevels(r.data.results ?? r.data)).catch(() => {})
  }, [])

  // WS upsert
  useEffect(() => {
    const ev = wsMessages[wsMessages.length - 1]
    if (ev?.activation_code) load()
  }, [wsMessages])

  const openNew = () => {
    setForm({ response_level:'', disease_name:'', disease_code:'', notes:'' })
    setFormOpen(true)
  }
  const handleCreate = async () => {
    if (!form.response_level) { toastErr('Response level is required'); return }
    setSaving(true)
    try {
      await responseApi.createActivation({
        response_level: Number(form.response_level),
        disease_name: form.disease_name, disease_code: form.disease_code, notes: form.notes,
      })
      toastOk('Activation created')
      setFormOpen(false)
      load()
    } catch (e) { toastErr(extractError(e)) }
    finally { setSaving(false) }
  }

  const handleSuspend = async (id, code) => {
    const reason = prompt(`Reason for suspending ${code}:`)
    if (!reason?.trim()) return
    setActing(id)
    try {
      await responseApi.suspend(id, { reason })
      toastOk(`${code} suspended`)
      load()
    } catch (e) { toastErr(extractError(e)) }
    finally { setActing(null) }
  }

  const [pendingComplete, setPendingComplete] = useState(null)

  const handleComplete = async (id, code) => {
    if (pendingComplete !== id) { setPendingComplete(id); return }
    setPendingComplete(null)
    setActing(id)
    try {
      await responseApi.complete(id, {})
      toastOk(`${code} completed`)
      load()
    } catch (e) { toastErr(extractError(e)) }
    finally { setActing(null) }
  }

  const STATUS_FILTERS = ['ALL','ACTIVE','ESCALATED','PENDING','SUSPENDED','DEESCALATED','COMPLETED','CANCELLED']
  const totalPages = Math.ceil(totalCount / PAGE_SIZE)
  const setF = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const inpStyle = { background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, padding: '8px 10px', color: T.text, fontFamily: FONTS.body, fontSize: 13, outline: 'none', width: '100%', boxSizing: 'border-box' }
  const lblStyle = { fontFamily: FONTS.mono, fontSize: 9, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 }

  const toolbar = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ fontFamily: FONTS.head, fontSize: 17, color: T.text, letterSpacing: '0.05em' }}>
          ACTIVATIONS <span style={{ fontFamily: FONTS.mono, fontSize: 10, color: T.textMuted, marginLeft: 8 }}>{totalCount}</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <ActionBtn onClick={openNew} variant="solid">+ New Activation</ActionBtn>
          <ActionBtn onClick={load} icon={<RefreshIco />}>Refresh</ActionBtn>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
        {STATUS_FILTERS.map(s => (
          <FilterPill key={s} label={s === 'ALL' ? 'All' : s} active={statusFilter === s}
            onClick={() => setStatus(s)} color={s !== 'ALL' ? STATUS_COLOR[s] : undefined} />
        ))}
      </div>
    </div>
  )

  return (
    <>
      {formOpen && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.65)', zIndex:1000, display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}>
          <div style={{ background:T.surface, border:`1px solid ${T.border}`, borderRadius:8, width:'100%', maxWidth:480, padding:28 }}>
            <div style={{ fontFamily:FONTS.head, fontSize:22, color:T.text, marginBottom:22, letterSpacing:'0.05em' }}>NEW ACTIVATION</div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14, marginBottom:14 }}>
              <div style={{ gridColumn:'1/-1' }}>
                <label style={lblStyle}>Response Level *</label>
                <select style={inpStyle} value={form.response_level} onChange={e => setF('response_level', e.target.value)}>
                  <option value="">— Select level —</option>
                  {levels.map(l => <option key={l.id} value={l.id}>Level {l.level}: {l.name}</option>)}
                </select>
              </div>
              <div>
                <label style={lblStyle}>Disease Name</label>
                <input style={inpStyle} value={form.disease_name} onChange={e => setF('disease_name', e.target.value)} placeholder="e.g. Cholera" />
              </div>
              <div>
                <label style={lblStyle}>Disease Code</label>
                <input style={inpStyle} value={form.disease_code} onChange={e => setF('disease_code', e.target.value.toUpperCase())} placeholder="e.g. CHOLERA" />
              </div>
              <div style={{ gridColumn:'1/-1' }}>
                <label style={lblStyle}>Notes</label>
                <textarea style={{ ...inpStyle, minHeight:80, resize:'vertical' }} value={form.notes} onChange={e => setF('notes', e.target.value)} placeholder="Initial notes…" />
              </div>
            </div>
            <div style={{ display:'flex', gap:10, justifyContent:'flex-end' }}>
              <ActionBtn variant="ghost" onClick={() => setFormOpen(false)}>Cancel</ActionBtn>
              <ActionBtn variant="solid" onClick={handleCreate} disabled={saving}>
                {saving ? 'Creating…' : 'Create Activation'}
              </ActionBtn>
            </div>
          </div>
        </div>
      )}
      <TableCard toolbar={toolbar} footer={
      <Pagination page={page} totalPages={totalPages} totalCount={totalCount}
        onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)} />
    }>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr>
          {['Code','Level','Status','Disease','Location','Started','Esc. Prob','Progress',''].map(h => <Th key={h}>{h}</Th>)}
        </tr></thead>
        <tbody>
          {loading
            ? <ShimmerRows cols={9} />
            : rows.length === 0
              ? <EmptyRow cols={9} msg="No activations found" />
              : rows.map(row => (
                <tr key={row.id}
                  onMouseEnter={() => setHovered(row.id)}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => navigate(`/dashboard/response/${row.id}`)}
                  style={{ background: hovered === row.id ? 'rgba(255,255,255,0.02)' : 'transparent',
                    cursor: 'pointer', transition: 'background 0.1s' }}
                >
                  <Td>
                    <div style={{ fontFamily: FONTS.mono, fontSize: 10, color: T.accent }}>{row.activation_code}</div>
                  </Td>
                  <Td><LevelBadge level={row.response_level_number ?? row.response_level} /></Td>
                  <Td><Badge label={row.status} color={STATUS_COLOR[row.status] ?? T.textSub} /></Td>
                  <Td>
                    <div style={{ fontFamily: FONTS.body, fontSize: 12, color: T.text }}>{row.disease_name || '—'}</div>
                    {row.disease_code && <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: T.textMuted }}>{row.disease_code}</div>}
                  </Td>
                  <Td style={{ fontSize: 12, color: T.textSub }}>{row.location_name || '—'}</Td>
                  <Td style={{ fontFamily: FONTS.mono, fontSize: 9, color: T.textMuted, whiteSpace: 'nowrap' }}>
                    {fmtDate(row.activated_at)}
                  </Td>
                  <Td style={{ minWidth: 100 }}><ProbBar value={row.escalation_probability} /></Td>
                  <Td style={{ minWidth: 70 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <ProgressRing pct={row.completion_percentage ?? 0} size={36} />
                      <span style={{ fontFamily: FONTS.mono, fontSize: 9, color: T.textMuted }}>
                        {row.completion_percentage ?? 0}%
                      </span>
                    </div>
                  </Td>
                  <Td>
                    <div style={{ display: 'flex', gap: 5 }} onClick={e => e.stopPropagation()}>
                      <ActionBtn small onClick={() => navigate(`/dashboard/response/${row.id}`)}>View</ActionBtn>
                      {(row.status === 'ACTIVE' || row.status === 'ESCALATED') && (
                        <ActionBtn small variant="warning" onClick={() => handleSuspend(row.id, row.activation_code)}
                          disabled={acting === row.id}>Suspend</ActionBtn>
                      )}
                      {row.status === 'ACTIVE' && (
                        pendingComplete === row.id ? (
                          <>
                            <ActionBtn small variant="success" onClick={() => handleComplete(row.id, row.activation_code)} disabled={acting === row.id}>Confirm</ActionBtn>
                            <ActionBtn small variant="ghost" onClick={() => setPendingComplete(null)}>Cancel</ActionBtn>
                          </>
                        ) : (
                          <ActionBtn small variant="success" onClick={() => handleComplete(row.id, row.activation_code)} disabled={acting === row.id}>Complete</ActionBtn>
                        )
                      )}
                    </div>
                  </Td>
                </tr>
              ))
          }
        </tbody>
      </table>
    </TableCard>
    </>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB: ACTION ITEMS
// ═══════════════════════════════════════════════════════════════════════════════
function ActionItemsTab() {
  const { error: toastErr, success: toastOk } = useToast()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [filter, setFilter] = useState('ALL')
  const [priorityFilter, setPriority] = useState('ALL')
  const [acting, setActing] = useState(null)
  const [hovered, setHovered] = useState(null)

  const [formOpen, setFormOpen] = useState(false)
  const [form, setForm]         = useState({ title:'', priority:'MEDIUM', description:'', due_date:'' })
  const [saving, setSaving]     = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      let res
      if (filter === 'OVERDUE') res = await responseApi.overdueActions({ page, page_size: PAGE_SIZE })
      else if (filter === 'CRITICAL') res = await responseApi.criticalPendingActions({ page, page_size: PAGE_SIZE })
      else if (filter === 'MINE') res = await responseApi.myActions({ page, page_size: PAGE_SIZE })
      else {
        const params = { page, page_size: PAGE_SIZE }
        if (filter !== 'ALL') params.status = filter
        if (priorityFilter !== 'ALL') params.priority = priorityFilter
        res = await responseApi.listActionItems(params)
      }
      setItems(res.data.results ?? res.data)
      setTotal(res.data.count ?? 0)
    } catch (e) { toastErr(extractError(e)) }
    finally { setLoading(false) }
  }, [page, filter, priorityFilter])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [filter, priorityFilter])

  const handleStart = async (id) => {
    setActing(id)
    try { await responseApi.startActionItem(id); toastOk('Action started'); load() }
    catch (e) { toastErr(extractError(e)) }
    finally { setActing(null) }
  }

  const handleComplete = async (id) => {
    const notes = prompt('Completion notes (optional):') ?? ''
    setActing(id)
    try { await responseApi.completeActionItem(id, { completion_notes: notes }); toastOk('Action completed'); load() }
    catch (e) { toastErr(extractError(e)) }
    finally { setActing(null) }
  }

  const handleBlock = async (id) => {
    const reason = prompt('Blocker description:')
    if (!reason?.trim()) return
    setActing(id)
    try { await responseApi.blockActionItem(id, { blocker: reason }); toastOk('Action blocked'); load() }
    catch (e) { toastErr(extractError(e)) }
    finally { setActing(null) }
  }

  const openNew = () => {
    setForm({ title:'', priority:'MEDIUM', description:'', due_date:'' })
    setFormOpen(true)
  }
  const handleCreate = async () => {
    if (!form.title.trim()) { toastErr('Title is required'); return }
    setSaving(true)
    try {
      await responseApi.createActionItem({
        title: form.title.trim(), priority: form.priority,
        description: form.description, due_date: form.due_date || null,
      })
      toastOk('Action item created')
      setFormOpen(false)
      load()
    } catch (e) { toastErr(extractError(e)) }
    finally { setSaving(false) }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const setF = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const inpStyle = { background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, padding: '8px 10px', color: T.text, fontFamily: FONTS.body, fontSize: 13, outline: 'none', width: '100%', boxSizing: 'border-box' }
  const lblStyle = { fontFamily: FONTS.mono, fontSize: 9, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 }

  const toolbar = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ fontFamily: FONTS.head, fontSize: 17, color: T.text, letterSpacing: '0.05em' }}>
          ACTION ITEMS <span style={{ fontFamily: FONTS.mono, fontSize: 10, color: T.textMuted, marginLeft: 8 }}>{total}</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <ActionBtn onClick={openNew} variant="solid">+ New Action Item</ActionBtn>
          <ActionBtn onClick={load} icon={<RefreshIco />}>Refresh</ActionBtn>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontFamily: FONTS.mono, fontSize: 8, color: T.textMuted, textTransform: 'uppercase' }}>View:</span>
        {[['ALL','All'],['OVERDUE','Overdue'],['CRITICAL','Critical'],['MINE','Mine'],
          ['PENDING','Pending'],['IN_PROGRESS','In Progress'],['COMPLETED','Completed'],['BLOCKED','Blocked']].map(([k,l]) => (
          <FilterPill key={k} label={l} active={filter === k} onClick={() => setFilter(k)}
            color={k === 'OVERDUE' ? T.danger : k === 'CRITICAL' ? T.danger : undefined} />
        ))}
        <div style={{ width: 1, height: 14, background: T.border }} />
        {['ALL','LOW','MEDIUM','HIGH','CRITICAL'].map(p => (
          <FilterPill key={p} label={p} active={priorityFilter === p} onClick={() => setPriority(p)}
            color={p !== 'ALL' ? PRIORITY_COLOR[p] : undefined} />
        ))}
      </div>
    </div>
  )

  return (
    <>
      {formOpen && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.65)', zIndex:1000, display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}>
          <div style={{ background:T.surface, border:`1px solid ${T.border}`, borderRadius:8, width:'100%', maxWidth:480, padding:28 }}>
            <div style={{ fontFamily:FONTS.head, fontSize:22, color:T.text, marginBottom:22, letterSpacing:'0.05em' }}>NEW ACTION ITEM</div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14, marginBottom:14 }}>
              <div style={{ gridColumn:'1/-1' }}>
                <label style={lblStyle}>Title *</label>
                <input style={inpStyle} value={form.title} onChange={e => setF('title', e.target.value)} placeholder="Action item title" />
              </div>
              <div>
                <label style={lblStyle}>Priority</label>
                <select style={inpStyle} value={form.priority} onChange={e => setF('priority', e.target.value)}>
                  {['LOW','MEDIUM','HIGH','CRITICAL'].map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label style={lblStyle}>Due Date</label>
                <input style={inpStyle} type="date" value={form.due_date} onChange={e => setF('due_date', e.target.value)} />
              </div>
              <div style={{ gridColumn:'1/-1' }}>
                <label style={lblStyle}>Description</label>
                <textarea style={{ ...inpStyle, minHeight:80, resize:'vertical' }} value={form.description} onChange={e => setF('description', e.target.value)} placeholder="Describe the action required…" />
              </div>
            </div>
            <div style={{ display:'flex', gap:10, justifyContent:'flex-end' }}>
              <ActionBtn variant="ghost" onClick={() => setFormOpen(false)}>Cancel</ActionBtn>
              <ActionBtn variant="solid" onClick={handleCreate} disabled={saving}>
                {saving ? 'Creating…' : 'Create Action Item'}
              </ActionBtn>
            </div>
          </div>
        </div>
      )}
      <TableCard toolbar={toolbar} footer={
        <Pagination page={page} totalPages={totalPages} totalCount={total}
          onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)} />
      }>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>
            {['Title','Priority','Status','Assigned To','Response','Due','Overdue',''].map(h => <Th key={h}>{h}</Th>)}
          </tr></thead>
        <tbody>
          {loading
            ? <ShimmerRows cols={8} />
            : items.length === 0
              ? <EmptyRow cols={8} msg="No action items found" />
              : items.map(item => {
                const overdue = item.is_overdue || (item.due_date && new Date(item.due_date) < new Date()
                  && ['PENDING','IN_PROGRESS'].includes(item.status))
                return (
                  <tr key={item.id}
                    onMouseEnter={() => setHovered(item.id)}
                    onMouseLeave={() => setHovered(null)}
                    style={{ background: hovered === item.id ? 'rgba(255,255,255,0.02)' : 'transparent',
                      transition: 'background 0.1s' }}
                  >
                    <Td>
                      <div style={{ fontFamily: FONTS.body, fontSize: 12, color: T.text, fontWeight: 500, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {item.title}
                      </div>
                      {item.blockers && (
                        <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: T.danger, marginTop: 2 }}>⚠ {item.blockers.slice(0, 50)}</div>
                      )}
                    </Td>
                    <Td><Badge label={item.priority} color={PRIORITY_COLOR[item.priority] ?? T.textSub} /></Td>
                    <Td><Badge label={item.status} color={ACTION_STATUS_COLOR[item.status] ?? T.textSub} /></Td>
                    <Td style={{ fontSize: 12, color: T.textSub }}>{item.assigned_to_name ?? '—'}</Td>
                    <Td style={{ fontFamily: FONTS.mono, fontSize: 9, color: T.textMuted }}>{item.activation_code ?? '—'}</Td>
                    <Td style={{ fontFamily: FONTS.mono, fontSize: 9, color: overdue ? T.danger : T.textMuted, whiteSpace: 'nowrap' }}>
                      {fmtDateOnly(item.due_date)}
                    </Td>
                    <Td>
                      {overdue && <Badge label="Overdue" color={T.danger} />}
                    </Td>
                    <Td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {item.status === 'PENDING' && (
                          <ActionBtn small variant="accent" onClick={() => handleStart(item.id)} disabled={acting === item.id}>Start</ActionBtn>
                        )}
                        {['PENDING','IN_PROGRESS'].includes(item.status) && (
                          <ActionBtn small variant="success" onClick={() => handleComplete(item.id)} disabled={acting === item.id}>Done</ActionBtn>
                        )}
                        {item.status === 'IN_PROGRESS' && (
                          <ActionBtn small variant="danger" onClick={() => handleBlock(item.id)} disabled={acting === item.id}>Block</ActionBtn>
                        )}
                      </div>
                    </Td>
                  </tr>
                )
              })
          }
        </tbody>
      </table>
    </TableCard>
    </>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB: REPORTS
// ═══════════════════════════════════════════════════════════════════════════════
function ReportsTab() {
  const { error: toastErr, success: toastOk } = useToast()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [typeFilter, setType] = useState('ALL')
  const [pubFilter, setPub] = useState('ALL')
  const [acting, setActing] = useState(null)
  const [hovered, setHovered] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE }
      if (typeFilter !== 'ALL') params.report_type = typeFilter
      if (pubFilter === 'PUBLISHED') params.is_published = true
      if (pubFilter === 'DRAFT') params.is_published = false
      const res = await responseApi.listResponseReports(params)
      setRows(res.data.results ?? res.data)
      setTotal(res.data.count ?? 0)
    } catch (e) { toastErr(extractError(e)) }
    finally { setLoading(false) }
  }, [page, typeFilter, pubFilter])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [typeFilter, pubFilter])

  const [pendingPublish, setPendingPublish] = useState(null)

  const handlePublish = async (id) => {
    if (pendingPublish !== id) { setPendingPublish(id); return }
    setPendingPublish(null)
    setActing(id)
    try { await responseApi.publishReport(id); toastOk('Report published'); load() }
    catch (e) { toastErr(extractError(e)) }
    finally { setActing(null) }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const REPORT_TYPES = ['SITUATION','PROGRESS','AFTER_ACTION','DAILY']

  const toolbar = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ fontFamily: FONTS.head, fontSize: 17, color: T.text, letterSpacing: '0.05em' }}>
          RESPONSE REPORTS <span style={{ fontFamily: FONTS.mono, fontSize: 10, color: T.textMuted, marginLeft: 8 }}>{total}</span>
        </div>
        <ActionBtn onClick={load} icon={<RefreshIco />}>Refresh</ActionBtn>
      </div>
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', alignItems: 'center' }}>
        <FilterPill label="All Types" active={typeFilter === 'ALL'} onClick={() => setType('ALL')} />
        {REPORT_TYPES.map(t => (
          <FilterPill key={t} label={t.replace('_', ' ')} active={typeFilter === t}
            onClick={() => setType(t)} color={REPORT_TYPE_COLOR[t]} />
        ))}
        <div style={{ width: 1, height: 14, background: T.border }} />
        {[['ALL','All'],['PUBLISHED','Published'],['DRAFT','Draft']].map(([k,l]) => (
          <FilterPill key={k} label={l} active={pubFilter === k} onClick={() => setPub(k)}
            color={k === 'PUBLISHED' ? T.success : undefined} />
        ))}
      </div>
    </div>
  )

  return (
    <TableCard toolbar={toolbar} footer={
      <Pagination page={page} totalPages={totalPages} totalCount={total}
        onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)} />
    }>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr>
          {['Title','Type','Activation','Date','Period','Cases','Status',''].map(h => <Th key={h}>{h}</Th>)}
        </tr></thead>
        <tbody>
          {loading
            ? <ShimmerRows cols={8} />
            : rows.length === 0
              ? <EmptyRow cols={8} msg="No reports found" />
              : rows.map(r => (
                <tr key={r.id}
                  onMouseEnter={() => setHovered(r.id)}
                  onMouseLeave={() => setHovered(null)}
                  style={{ background: hovered === r.id ? 'rgba(255,255,255,0.02)' : 'transparent',
                    transition: 'background 0.1s' }}
                >
                  <Td>
                    <div style={{ fontFamily: FONTS.body, fontSize: 12, color: T.text, fontWeight: 500, maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {r.title}
                    </div>
                  </Td>
                  <Td><Badge label={r.report_type?.replace('_',' ')} color={REPORT_TYPE_COLOR[r.report_type] ?? T.accent} /></Td>
                  <Td style={{ fontFamily: FONTS.mono, fontSize: 9, color: T.textMuted }}>{r.activation_code ?? '—'}</Td>
                  <Td style={{ fontFamily: FONTS.mono, fontSize: 9, color: T.textMuted, whiteSpace: 'nowrap' }}>
                    {fmtDateOnly(r.report_date)}
                  </Td>
                  <Td style={{ fontFamily: FONTS.mono, fontSize: 9, color: T.textMuted, whiteSpace: 'nowrap' }}>
                    {r.period_start ? `${fmtDateOnly(r.period_start)} → ${fmtDateOnly(r.period_end)}` : '—'}
                  </Td>
                  <Td style={{ fontFamily: FONTS.mono, fontSize: 11, color: T.text }}>
                    {r.cases_managed ?? '—'}
                  </Td>
                  <Td>
                    <Badge label={r.is_published ? 'Published' : 'Draft'} color={r.is_published ? T.success : T.textMuted} />
                  </Td>
                  <Td>
                    {!r.is_published && (
                      pendingPublish === r.id ? (
                        <>
                          <ActionBtn small variant="success" onClick={() => handlePublish(r.id)} disabled={acting === r.id}>Confirm</ActionBtn>
                          <ActionBtn small variant="ghost" onClick={() => setPendingPublish(null)}>Cancel</ActionBtn>
                        </>
                      ) : (
                        <ActionBtn small variant="success" onClick={() => handlePublish(r.id)} disabled={acting === r.id}>Publish</ActionBtn>
                      )
                    )}
                  </Td>
                </tr>
              ))
          }
        </tbody>
      </table>
    </TableCard>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB: PROTOCOLS
// ═══════════════════════════════════════════════════════════════════════════════
function ProtocolsTab() {
  const { error: toastErr, success: toastOk } = useToast()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [typeFilter, setType] = useState('ALL')
  const [hovered, setHovered] = useState(null)

  const [formOpen, setFormOpen]     = useState(false)
  const [editTarget, setEditTarget] = useState(null)
  const [form, setForm]             = useState({ name:'', code:'', protocol_type:'GENERAL', version:'1.0', response_time_hours:24, disease_codes_raw:'', description:'' })
  const [saving, setSaving]         = useState(false)
  const [deleting, setDeleting]     = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE }
      if (typeFilter !== 'ALL') params.protocol_type = typeFilter
      const res = await responseApi.listProtocols(params)
      setRows(res.data.results ?? res.data)
      setTotal(res.data.count ?? 0)
    } catch (e) { toastErr(extractError(e)) }
    finally { setLoading(false) }
  }, [page, typeFilter])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [typeFilter])

  const openNew = () => {
    setEditTarget(null)
    setForm({ name:'', code:'', protocol_type:'GENERAL', version:'1.0', response_time_hours:24, disease_codes_raw:'', description:'' })
    setFormOpen(true)
  }
  const openEdit = (p) => {
    setEditTarget(p)
    setForm({
      name: p.name, code: p.code, protocol_type: p.protocol_type,
      version: p.version || '1.0', response_time_hours: p.response_time_hours || 24,
      disease_codes_raw: (p.disease_codes ?? []).join(', '),
      description: p.description ?? '',
    })
    setFormOpen(true)
  }
  const handleSave = async () => {
    if (!form.name.trim() || !form.code.trim()) { toastErr('Name and Code are required'); return }
    setSaving(true)
    try {
      const payload = {
        name: form.name.trim(), code: form.code.trim().toUpperCase(),
        protocol_type: form.protocol_type, version: form.version,
        response_time_hours: Number(form.response_time_hours) || 24,
        disease_codes: form.disease_codes_raw ? form.disease_codes_raw.split(',').map(s => s.trim()).filter(Boolean) : [],
        description: form.description,
      }
      if (editTarget) {
        await responseApi.updateProtocol(editTarget.id, payload)
        toastOk('Protocol updated')
      } else {
        await responseApi.createProtocol(payload)
        toastOk('Protocol created')
      }
      setFormOpen(false)
      load()
    } catch (e) { toastErr(extractError(e)) }
    finally { setSaving(false) }
  }
  const handleDelete = async (p) => {
    if (deleting !== p.id) { setDeleting(p.id); return }
    try {
      await responseApi.deleteProtocol(p.id)
      toastOk('Protocol deleted')
      setDeleting(null)
      load()
    } catch (e) { toastErr(extractError(e)); setDeleting(null) }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const PROTO_TYPES = ['DISEASE','SCENARIO','GENERAL']
  const PROTO_TYPE_COLOR = { DISEASE: T.danger, SCENARIO: T.warning, GENERAL: T.accent }
  const setF = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const inpStyle = { background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, padding: '8px 10px', color: T.text, fontFamily: FONTS.body, fontSize: 13, outline: 'none', width: '100%', boxSizing: 'border-box' }
  const lblStyle = { fontFamily: FONTS.mono, fontSize: 9, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 }

  const toolbar = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ fontFamily: FONTS.head, fontSize: 17, color: T.text, letterSpacing: '0.05em' }}>
          RESPONSE PROTOCOLS <span style={{ fontFamily: FONTS.mono, fontSize: 10, color: T.textMuted, marginLeft: 8 }}>{total}</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <ActionBtn onClick={openNew} variant="solid">+ New Protocol</ActionBtn>
          <ActionBtn onClick={load} icon={<RefreshIco />}>Refresh</ActionBtn>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
        <FilterPill label="All" active={typeFilter === 'ALL'} onClick={() => setType('ALL')} />
        {PROTO_TYPES.map(t => (
          <FilterPill key={t} label={t} active={typeFilter === t} onClick={() => setType(t)} color={PROTO_TYPE_COLOR[t]} />
        ))}
      </div>
    </div>
  )

  return (
    <>
      {formOpen && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.65)', zIndex:1000, display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}>
          <div style={{ background:T.surface, border:`1px solid ${T.border}`, borderRadius:8, width:'100%', maxWidth:560, padding:28, maxHeight:'90vh', overflowY:'auto' }}>
            <div style={{ fontFamily:FONTS.head, fontSize:22, color:T.text, marginBottom:22, letterSpacing:'0.05em' }}>
              {editTarget ? 'EDIT PROTOCOL' : 'NEW PROTOCOL'}
            </div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14, marginBottom:14 }}>
              <div style={{ gridColumn:'1/-1' }}>
                <label style={lblStyle}>Name *</label>
                <input style={inpStyle} value={form.name} onChange={e => setF('name', e.target.value)} placeholder="Protocol name" />
              </div>
              <div>
                <label style={lblStyle}>Code *</label>
                <input style={inpStyle} value={form.code} onChange={e => setF('code', e.target.value.toUpperCase())} placeholder="PROT-001" />
              </div>
              <div>
                <label style={lblStyle}>Type</label>
                <select style={inpStyle} value={form.protocol_type} onChange={e => setF('protocol_type', e.target.value)}>
                  {PROTO_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label style={lblStyle}>Version</label>
                <input style={inpStyle} value={form.version} onChange={e => setF('version', e.target.value)} placeholder="1.0" />
              </div>
              <div>
                <label style={lblStyle}>Response Time (hours)</label>
                <input style={inpStyle} type="number" min="1" value={form.response_time_hours} onChange={e => setF('response_time_hours', e.target.value)} placeholder="24" />
              </div>
              <div style={{ gridColumn:'1/-1' }}>
                <label style={lblStyle}>Disease Codes (comma-separated)</label>
                <input style={inpStyle} value={form.disease_codes_raw} onChange={e => setF('disease_codes_raw', e.target.value)} placeholder="COVID-19, CHOLERA, EBOLA" />
              </div>
              <div style={{ gridColumn:'1/-1' }}>
                <label style={lblStyle}>Description</label>
                <textarea style={{ ...inpStyle, minHeight:80, resize:'vertical' }} value={form.description} onChange={e => setF('description', e.target.value)} placeholder="Protocol description…" />
              </div>
            </div>
            <div style={{ display:'flex', gap:10, justifyContent:'flex-end' }}>
              <ActionBtn variant="ghost" onClick={() => setFormOpen(false)}>Cancel</ActionBtn>
              <ActionBtn variant="solid" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving…' : editTarget ? 'Save Changes' : 'Create Protocol'}
              </ActionBtn>
            </div>
          </div>
        </div>
      )}
      <TableCard toolbar={toolbar} footer={
        <Pagination page={page} totalPages={totalPages} totalCount={total}
          onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)} />
      }>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>
            {['Code','Name','Type','Version','Response Time','Last Reviewed','Disease Codes','Status','Actions'].map(h => <Th key={h}>{h}</Th>)}
          </tr></thead>
          <tbody>
            {loading
              ? <ShimmerRows cols={9} />
              : rows.length === 0
                ? <EmptyRow cols={9} msg="No protocols found" />
                : rows.map(p => (
                  <tr key={p.id}
                    onMouseEnter={() => setHovered(p.id)}
                    onMouseLeave={() => setHovered(null)}
                    style={{ background: hovered === p.id ? 'rgba(255,255,255,0.02)' : 'transparent', transition: 'background 0.1s' }}
                  >
                    <Td><Badge label={p.code} color={T.accent} /></Td>
                    <Td><div style={{ fontFamily: FONTS.body, fontSize: 12, color: T.text, fontWeight: 500 }}>{p.name}</div></Td>
                    <Td><Badge label={p.protocol_type} color={PROTO_TYPE_COLOR[p.protocol_type] ?? T.textSub} /></Td>
                    <Td style={{ fontFamily: FONTS.mono, fontSize: 10, color: T.textSub }}>v{p.version}</Td>
                    <Td style={{ fontFamily: FONTS.mono, fontSize: 10, color: T.textSub }}>{p.response_time_hours}h</Td>
                    <Td style={{ fontFamily: FONTS.mono, fontSize: 9, color: T.textMuted }}>{fmtDateOnly(p.last_reviewed)}</Td>
                    <Td>
                      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {(p.disease_codes ?? []).slice(0, 3).map(c => <Badge key={c} label={c} color={T.textMuted} />)}
                        {(p.disease_codes ?? []).length > 3 && (
                          <span style={{ fontFamily: FONTS.mono, fontSize: 9, color: T.textMuted }}>+{p.disease_codes.length - 3}</span>
                        )}
                      </div>
                    </Td>
                    <Td><Badge label={p.is_active ? 'Active' : 'Inactive'} color={p.is_active ? T.success : T.textMuted} /></Td>
                    <Td>
                      <div style={{ display:'flex', gap:5 }}>
                        <ActionBtn small onClick={() => openEdit(p)}>Edit</ActionBtn>
                        {deleting === p.id ? (
                          <>
                            <ActionBtn small variant="danger" onClick={() => handleDelete(p)}>Confirm</ActionBtn>
                            <ActionBtn small onClick={() => setDeleting(null)}>Cancel</ActionBtn>
                          </>
                        ) : (
                          <ActionBtn small variant="danger" onClick={() => handleDelete(p)}>Delete</ActionBtn>
                        )}
                      </div>
                    </Td>
                  </tr>
                ))
            }
          </tbody>
        </table>
      </TableCard>
    </>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB: ESCALATION TRIGGERS
// ═══════════════════════════════════════════════════════════════════════════════
function TriggersTab() {
  const { error: toastErr, success: toastOk } = useToast()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [typeFilter, setType] = useState('ALL')
  const [hovered, setHovered] = useState(null)
  const [levels, setLevels] = useState([])

  const [formOpen, setFormOpen]     = useState(false)
  const [editTarget, setEditTarget] = useState(null)
  const [form, setForm]             = useState({ name:'', trigger_type:'CASE_COUNT', from_level:'', to_level:'', threshold_value:'', evaluation_period_days:7, auto_escalate:false, description:'' })
  const [saving, setSaving]         = useState(false)
  const [deleting, setDeleting]     = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE }
      if (typeFilter !== 'ALL') params.trigger_type = typeFilter
      const res = await responseApi.listEscalationTriggers(params)
      setRows(res.data.results ?? res.data)
      setTotal(res.data.count ?? 0)
    } catch (e) { toastErr(extractError(e)) }
    finally { setLoading(false) }
  }, [page, typeFilter])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [typeFilter])
  useEffect(() => {
    responseApi.listLevels({ page_size: 20 }).then(r => setLevels(r.data.results ?? r.data)).catch(() => {})
  }, [])

  const openNew = () => {
    setEditTarget(null)
    setForm({ name:'', trigger_type:'CASE_COUNT', from_level:'', to_level:'', threshold_value:'', evaluation_period_days:7, auto_escalate:false, description:'' })
    setFormOpen(true)
  }
  const openEdit = (t) => {
    setEditTarget(t)
    setForm({
      name: t.name, trigger_type: t.trigger_type,
      from_level: t.from_level ?? '', to_level: t.to_level ?? '',
      threshold_value: t.threshold_value ?? '', evaluation_period_days: t.evaluation_period_days ?? 7,
      auto_escalate: t.auto_escalate ?? false, description: t.description ?? '',
    })
    setFormOpen(true)
  }
  const handleSave = async () => {
    if (!form.name.trim()) { toastErr('Name is required'); return }
    setSaving(true)
    try {
      const payload = {
        name: form.name.trim(), trigger_type: form.trigger_type,
        from_level: form.from_level || null, to_level: form.to_level || null,
        threshold_value: form.threshold_value !== '' ? Number(form.threshold_value) : null,
        evaluation_period_days: Number(form.evaluation_period_days) || 7,
        auto_escalate: form.auto_escalate, description: form.description,
      }
      if (editTarget) {
        await responseApi.updateEscalationTrigger(editTarget.id, payload)
        toastOk('Trigger updated')
      } else {
        await responseApi.createEscalationTrigger(payload)
        toastOk('Trigger created')
      }
      setFormOpen(false)
      load()
    } catch (e) { toastErr(extractError(e)) }
    finally { setSaving(false) }
  }
  const handleDelete = async (t) => {
    if (deleting !== t.id) { setDeleting(t.id); return }
    try {
      await responseApi.deleteEscalationTrigger(t.id)
      toastOk('Trigger deleted')
      setDeleting(null)
      load()
    } catch (e) { toastErr(extractError(e)); setDeleting(null) }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const TRIGGER_TYPES = ['CASE_COUNT','RISK_SCORE','TIME_ELAPSED','CAPACITY','MORTALITY']
  const setF = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const inpStyle = { background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, padding: '8px 10px', color: T.text, fontFamily: FONTS.body, fontSize: 13, outline: 'none', width: '100%', boxSizing: 'border-box' }
  const lblStyle = { fontFamily: FONTS.mono, fontSize: 9, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 }

  const toolbar = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ fontFamily: FONTS.head, fontSize: 17, color: T.text, letterSpacing: '0.05em' }}>
          ESCALATION TRIGGERS <span style={{ fontFamily: FONTS.mono, fontSize: 10, color: T.textMuted, marginLeft: 8 }}>{total}</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <ActionBtn onClick={openNew} variant="solid">+ New Trigger</ActionBtn>
          <ActionBtn onClick={load} icon={<RefreshIco />}>Refresh</ActionBtn>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
        <FilterPill label="All" active={typeFilter === 'ALL'} onClick={() => setType('ALL')} />
        {TRIGGER_TYPES.map(t => (
          <FilterPill key={t} label={t.replace('_',' ')} active={typeFilter === t}
            onClick={() => setType(t)} color={TRIGGER_TYPE_COLOR[t]} />
        ))}
      </div>
    </div>
  )

  return (
    <>
      {formOpen && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.65)', zIndex:1000, display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}>
          <div style={{ background:T.surface, border:`1px solid ${T.border}`, borderRadius:8, width:'100%', maxWidth:560, padding:28, maxHeight:'90vh', overflowY:'auto' }}>
            <div style={{ fontFamily:FONTS.head, fontSize:22, color:T.text, marginBottom:22, letterSpacing:'0.05em' }}>
              {editTarget ? 'EDIT TRIGGER' : 'NEW ESCALATION TRIGGER'}
            </div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14, marginBottom:14 }}>
              <div style={{ gridColumn:'1/-1' }}>
                <label style={lblStyle}>Name *</label>
                <input style={inpStyle} value={form.name} onChange={e => setF('name', e.target.value)} placeholder="Trigger name" />
              </div>
              <div>
                <label style={lblStyle}>Trigger Type</label>
                <select style={inpStyle} value={form.trigger_type} onChange={e => setF('trigger_type', e.target.value)}>
                  {TRIGGER_TYPES.map(t => <option key={t} value={t}>{t.replace('_',' ')}</option>)}
                </select>
              </div>
              <div>
                <label style={lblStyle}>Threshold Value</label>
                <input style={inpStyle} type="number" value={form.threshold_value} onChange={e => setF('threshold_value', e.target.value)} placeholder="e.g. 50" />
              </div>
              <div>
                <label style={lblStyle}>From Level</label>
                <select style={inpStyle} value={form.from_level} onChange={e => setF('from_level', e.target.value)}>
                  <option value="">— Any —</option>
                  {levels.map(l => <option key={l.id} value={l.id}>Level {l.level}: {l.name}</option>)}
                </select>
              </div>
              <div>
                <label style={lblStyle}>To Level</label>
                <select style={inpStyle} value={form.to_level} onChange={e => setF('to_level', e.target.value)}>
                  <option value="">— Any —</option>
                  {levels.map(l => <option key={l.id} value={l.id}>Level {l.level}: {l.name}</option>)}
                </select>
              </div>
              <div>
                <label style={lblStyle}>Evaluation Period (days)</label>
                <input style={inpStyle} type="number" min="1" value={form.evaluation_period_days} onChange={e => setF('evaluation_period_days', e.target.value)} placeholder="7" />
              </div>
              <div style={{ display:'flex', alignItems:'center', gap:10, paddingTop:20 }}>
                <input type="checkbox" id="auto_esc" checked={form.auto_escalate} onChange={e => setF('auto_escalate', e.target.checked)} style={{ width:16, height:16, cursor:'pointer' }} />
                <label htmlFor="auto_esc" style={{ ...lblStyle, marginBottom:0, cursor:'pointer' }}>Auto-Escalate</label>
              </div>
              <div style={{ gridColumn:'1/-1' }}>
                <label style={lblStyle}>Description</label>
                <textarea style={{ ...inpStyle, minHeight:70, resize:'vertical' }} value={form.description} onChange={e => setF('description', e.target.value)} placeholder="Trigger description…" />
              </div>
            </div>
            <div style={{ display:'flex', gap:10, justifyContent:'flex-end' }}>
              <ActionBtn variant="ghost" onClick={() => setFormOpen(false)}>Cancel</ActionBtn>
              <ActionBtn variant="solid" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving…' : editTarget ? 'Save Changes' : 'Create Trigger'}
              </ActionBtn>
            </div>
          </div>
        </div>
      )}
      <TableCard toolbar={toolbar} footer={
        <Pagination page={page} totalPages={totalPages} totalCount={total}
          onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)} />
      }>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>
            {['Name','Type','From Level','To Level','Threshold','Eval. Period','Auto-Escalate','Status','Actions'].map(h => <Th key={h}>{h}</Th>)}
          </tr></thead>
          <tbody>
            {loading
              ? <ShimmerRows cols={9} />
              : rows.length === 0
                ? <EmptyRow cols={9} msg="No escalation triggers found" />
                : rows.map(t => (
                  <tr key={t.id}
                    onMouseEnter={() => setHovered(t.id)}
                    onMouseLeave={() => setHovered(null)}
                    style={{ background: hovered === t.id ? 'rgba(255,255,255,0.02)' : 'transparent', transition: 'background 0.1s' }}
                  >
                    <Td>
                      <div style={{ fontFamily: FONTS.body, fontSize: 12, color: T.text, fontWeight: 500 }}>{t.name}</div>
                      {t.description && <div style={{ fontFamily: FONTS.body, fontSize: 11, color: T.textMuted, marginTop: 2 }}>{t.description.slice(0,60)}</div>}
                    </Td>
                    <Td><Badge label={t.trigger_type?.replace('_',' ')} color={TRIGGER_TYPE_COLOR[t.trigger_type] ?? T.accent} /></Td>
                    <Td><LevelBadge level={t.from_level_name?.match(/\d+/)?.[0] ?? t.from_level} /></Td>
                    <Td><LevelBadge level={t.to_level_name?.match(/\d+/)?.[0] ?? t.to_level} /></Td>
                    <Td style={{ fontFamily: FONTS.mono, fontSize: 11, color: T.text }}>{t.threshold_value}</Td>
                    <Td style={{ fontFamily: FONTS.mono, fontSize: 10, color: T.textSub }}>{t.evaluation_period_days}d</Td>
                    <Td><Badge label={t.auto_escalate ? 'Auto' : 'Manual'} color={t.auto_escalate ? T.warning : T.textMuted} /></Td>
                    <Td><Badge label={t.is_active ? 'Active' : 'Off'} color={t.is_active ? T.success : T.textMuted} /></Td>
                    <Td>
                      <div style={{ display:'flex', gap:5 }}>
                        <ActionBtn small onClick={() => openEdit(t)}>Edit</ActionBtn>
                        {deleting === t.id ? (
                          <>
                            <ActionBtn small variant="danger" onClick={() => handleDelete(t)}>Confirm</ActionBtn>
                            <ActionBtn small onClick={() => setDeleting(null)}>Cancel</ActionBtn>
                          </>
                        ) : (
                          <ActionBtn small variant="danger" onClick={() => handleDelete(t)}>Delete</ActionBtn>
                        )}
                      </div>
                    </Td>
                  </tr>
                ))
            }
          </tbody>
        </table>
      </TableCard>
    </>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// SIDEBAR: Critical + Overdue
// ═══════════════════════════════════════════════════════════════════════════════
function CriticalSidebar({ stats, statsLoading }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* Responses by level */}
      <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '14px 16px' }}>
        <div style={{ fontFamily: FONTS.head, fontSize: 13, color: T.text, letterSpacing: '0.05em', marginBottom: 12 }}>BY LEVEL</div>
        {statsLoading
          ? Array.from({length: 5}).map((_,i) => <div key={i} style={{ ...shimmerStyle, height: 12, marginBottom: 8 }} />)
          : Object.entries(stats?.responses_by_level ?? {}).map(([lvl, cnt]) => (
            <div key={lvl} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <LevelBadge level={Number(lvl)} />
              <span style={{ fontFamily: FONTS.head, fontSize: 22, color: LEVEL_COLORS[lvl] || T.text }}>{cnt}</span>
            </div>
          ))
        }
      </div>

      {/* Recent critical actions */}
      <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '14px 16px' }}>
        <div style={{ fontFamily: FONTS.head, fontSize: 13, color: T.danger, letterSpacing: '0.05em', marginBottom: 12 }}>CRITICAL ACTIONS</div>
        {statsLoading
          ? Array.from({length: 3}).map((_,i) => <div key={i} style={{ ...shimmerStyle, height: 40, marginBottom: 8 }} />)
          : (stats?.critical_actions ?? []).length === 0
            ? <div style={{ fontFamily: FONTS.mono, fontSize: 10, color: T.textMuted }}>None pending</div>
            : (stats?.critical_actions ?? []).map((a,i) => (
              <div key={i} style={{ borderLeft: `3px solid ${T.danger}`, paddingLeft: 10, marginBottom: 12 }}>
                <div style={{ fontFamily: FONTS.body, fontSize: 11, color: T.text, marginBottom: 3, lineHeight: 1.4 }}>{a.title}</div>
                <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: T.textMuted }}>
                  {a['assigned_to__username'] ?? 'Unassigned'} · Due: {fmtDateOnly(a.due_date)}
                </div>
                <div style={{ marginTop: 4 }}>
                  <Badge label={a.status} color={ACTION_STATUS_COLOR[a.status] ?? T.textSub} />
                </div>
              </div>
            ))
        }
      </div>

      {/* Recent activations */}
      <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '14px 16px' }}>
        <div style={{ fontFamily: FONTS.head, fontSize: 13, color: T.text, letterSpacing: '0.05em', marginBottom: 12 }}>RECENT ACTIVATIONS</div>
        {statsLoading
          ? Array.from({length: 3}).map((_,i) => <div key={i} style={{ ...shimmerStyle, height: 36, marginBottom: 8 }} />)
          : (stats?.recent_activations ?? []).map((a,i) => (
            <div key={i} style={{ paddingBottom: 10, marginBottom: 10, borderBottom: i < (stats?.recent_activations?.length ?? 0) - 1 ? `1px solid ${T.border}` : 'none' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 3 }}>
                <span style={{ fontFamily: FONTS.mono, fontSize: 9, color: T.accent }}>{a.activation_code}</span>
                <LevelBadge level={a['response_level__level']} />
              </div>
              <div style={{ fontFamily: FONTS.body, fontSize: 11, color: T.textSub }}>{a.disease_name || '—'}</div>
              <div style={{ fontFamily: FONTS.mono, fontSize: 8, color: T.textMuted }}>📍 {a['location__name']}</div>
            </div>
          ))
        }
      </div>
    </div>
  )
}

// ─── Tab definitions ──────────────────────────────────────────────────────────
const TABS = [
  { key: 'activations', label: 'Activations' },
  { key: 'actions',     label: 'Action Items' },
  { key: 'reports',     label: 'Reports' },
  { key: 'protocols',   label: 'Protocols' },
  { key: 'triggers',    label: 'Triggers' },
]

// ─── Inline icon ─────────────────────────────────────────────────────────────
const RefreshIco = () => (
  <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10"/>
    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
  </svg>
)

const shimmerStyleObj = {
  background: `linear-gradient(90deg,${T.surface} 25%,${T.surfaceHigh} 50%,${T.surface} 75%)`,
  backgroundSize: '200% 100%',
  animation: 'resp-shimmer 1.5s infinite',
  borderRadius: 4,
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN EXPORT
// ═══════════════════════════════════════════════════════════════════════════════
export default function Response() {
  const navigate = useNavigate()
  const { error: toastErr } = useToast()
  const { data: wsMessages } = useResponseStream()

  const [stats, setStats] = useState(null)
  const [statsLoading, setStatsLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('activations')

  const loadStats = useCallback(async () => {
    setStatsLoading(true)
    try {
      const res = await responseApi.getDashboard()
      setStats(res.data)
    } catch (e) { toastErr(extractError(e)) }
    finally { setStatsLoading(false) }
  }, [])

  useEffect(() => { loadStats() }, [loadStats])

  const STAT_CARDS = [
    { label: 'Active', value: stats?.active_responses, color: T.accent, icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
    { label: 'Level 5', value: stats?.level_5_responses, color: T.danger, icon: 'M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z' },
    { label: 'Pending Actions', value: stats?.pending_actions, color: T.warning, icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2' },
    { label: 'Overdue Actions', value: stats?.overdue_actions, color: T.danger, icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
  ]

  return (
    <div style={{ minHeight: '100%', fontFamily: FONTS.body, background: T.bg }}>
      <style>{`
        @keyframes resp-shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: #111827; }
        ::-webkit-scrollbar-thumb { background: #1f2937; border-radius: 3px; }
        @media (max-width: 1023px) { .resp-sidebar { display: none !important; } }
      `}</style>

      <div style={{ padding: 'clamp(16px, 2.5vw, 28px)' }}>

        {/* ── Header ── */}
        <motion.div {...fadeUp(0)} style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.18em',
                textTransform: 'uppercase', color: T.textSub, marginBottom: 5 }}>
                Operations / Response Management
              </div>
              <h1 style={{ fontFamily: FONTS.head, fontSize: 'clamp(26px, 4.5vw, 40px)',
                color: T.text, letterSpacing: '0.04em', margin: 0, lineHeight: 1 }}>
                RESPONSE MANAGEMENT
              </h1>
              <div style={{ fontFamily: FONTS.body, fontSize: 13, color: T.textSub, marginTop: 5 }}>
                Activations · Action items · Protocols · Triggers · Reports
              </div>
            </div>
            <ActionBtn onClick={loadStats} icon={<RefreshIco />} variant="ghost">Refresh Stats</ActionBtn>
          </div>
        </motion.div>

        {/* ── Stat cards ── */}
        <motion.div {...fadeUp(0.05)} style={{ display: 'flex', gap: 10, marginBottom: 24, flexWrap: 'wrap' }}>
          {STAT_CARDS.map(c => (
            <StatCard key={c.label} label={c.label} value={c.value} color={c.color} icon={c.icon} loading={statsLoading} />
          ))}
        </motion.div>

        {/* ── Body: tabs + sidebar ── */}
        <div style={{ display: 'flex', gap: 18, alignItems: 'flex-start' }}>

          {/* Main column */}
          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Tab bar */}
            <motion.div {...fadeUp(0.1)}>
              <div style={{
                display: 'flex', gap: 0, marginBottom: 18,
                borderBottom: `1px solid ${T.border}`,
                overflowX: 'auto', msOverflowStyle: 'none', scrollbarWidth: 'none',
              }}>
                {TABS.map(t => (
                  <button key={t.key} onClick={() => setActiveTab(t.key)} style={{
                    background: 'transparent', border: 'none',
                    borderBottom: activeTab === t.key ? `2px solid ${T.accent}` : '2px solid transparent',
                    padding: '10px 16px',
                    fontFamily: FONTS.body, fontSize: 13,
                    color: activeTab === t.key ? T.text : T.textSub,
                    cursor: 'pointer', fontWeight: activeTab === t.key ? 500 : 400,
                    transition: 'all 0.14s', marginBottom: -1,
                    whiteSpace: 'nowrap', flexShrink: 0,
                  }}>{t.label}</button>
                ))}
              </div>
            </motion.div>

            {/* Tab content */}
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.18 }}
              >
                {activeTab === 'activations' && <ActivationsTab navigate={navigate} wsMessages={wsMessages ?? []} />}
                {activeTab === 'actions'     && <ActionItemsTab />}
                {activeTab === 'reports'     && <ReportsTab />}
                {activeTab === 'protocols'   && <ProtocolsTab />}
                {activeTab === 'triggers'    && <TriggersTab />}
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Right sidebar — hidden below 1024 px */}
          <motion.div {...fadeUp(0.12)} className="resp-sidebar" style={{ width: 260, flexShrink: 0 }}>
            <CriticalSidebar stats={stats} statsLoading={statsLoading} />
          </motion.div>
        </div>
      </div>
    </div>
  )
}