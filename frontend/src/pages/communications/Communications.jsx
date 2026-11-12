/**
 * Communications — OryxShield
 * =====================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Multi-tab communications hub:
 *   Messages · Broadcasts · Campaigns · Feedback · Announcements
 *
 * API endpoints used (all from communicationsApi):
 *   GET /communications/messages/         — paginated message list
 *   GET /communications/broadcasts/       — broadcast list
 *   GET /communications/campaigns/        — campaign list
 *   GET /communications/feedback/         — feedback list
 *   GET /communications/announcements/    — announcement list
 *   GET /communications/dashboard/        — dashboard stats (1 call)
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { format } from 'date-fns'
import { communicationsApi, extractError } from '../../services/api'
import { useToast } from '../../context/ToastContext'

// ─── Design tokens ────────────────────────────────────────────────────────────
const C = {
  bg:      '#0a0f1e',
  surface: '#111827',
  surfH:   '#151e2e',
  border:  '#1f2937',
  accent:  '#3b82f6',
  danger:  '#ef4444',
  warning: '#f59e0b',
  success: '#10b981',
  purple:  '#a78bfa',
  text:    '#f9fafb',
  textSub: '#9ca3af',
  textMut: '#6b7280',
}

// ─── Palettes ─────────────────────────────────────────────────────────────────
const CHANNEL_PAL = {
  sms:    { color: C.success, bg: 'rgba(16,185,129,0.12)',  border: 'rgba(16,185,129,0.25)' },
  email:  { color: C.accent,  bg: 'rgba(59,130,246,0.12)', border: 'rgba(59,130,246,0.25)' },
  push:   { color: C.warning, bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.25)' },
  social: { color: C.purple,  bg: 'rgba(167,139,250,0.12)',border: 'rgba(167,139,250,0.25)' },
  sms_email_push: { color: C.accent, bg: 'rgba(59,130,246,0.08)', border: 'rgba(59,130,246,0.2)' },
}
const STATUS_PAL = {
  sent:      { color: C.success, bg: 'rgba(16,185,129,0.12)',  border: 'rgba(16,185,129,0.25)' },
  delivered: { color: C.accent,  bg: 'rgba(59,130,246,0.12)', border: 'rgba(59,130,246,0.25)' },
  failed:    { color: C.danger,  bg: 'rgba(239,68,68,0.12)',   border: 'rgba(239,68,68,0.25)' },
  pending:   { color: C.warning, bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.25)' },
  queued:    { color: C.warning, bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.25)' },
  draft:     { color: C.textMut, bg: 'rgba(156,163,175,0.12)',border: 'rgba(156,163,175,0.25)' },
  active:    { color: C.success, bg: 'rgba(16,185,129,0.12)',  border: 'rgba(16,185,129,0.25)' },
  approved:  { color: C.success, bg: 'rgba(16,185,129,0.12)',  border: 'rgba(16,185,129,0.25)' },
  cancelled: { color: C.danger,  bg: 'rgba(239,68,68,0.12)',   border: 'rgba(239,68,68,0.25)' },
  paused:    { color: C.warning, bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.25)' },
  completed: { color: C.textSub, bg: 'rgba(156,163,175,0.1)', border: 'rgba(156,163,175,0.2)' },
  open:      { color: C.warning, bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.25)' },
  resolved:  { color: C.success, bg: 'rgba(16,185,129,0.12)',  border: 'rgba(16,185,129,0.25)' },
  escalated: { color: C.danger,  bg: 'rgba(239,68,68,0.12)',   border: 'rgba(239,68,68,0.25)' },
}
const FEEDBACK_PAL = {
  inquiry:     { color: C.accent,  bg: 'rgba(59,130,246,0.1)',  border: 'rgba(59,130,246,0.2)'  },
  complaint:   { color: C.danger,  bg: 'rgba(239,68,68,0.1)',   border: 'rgba(239,68,68,0.2)'   },
  suggestion:  { color: C.success, bg: 'rgba(16,185,129,0.1)',  border: 'rgba(16,185,129,0.2)'  },
  report:      { color: C.warning, bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.2)'  },
  request:     { color: C.purple,  bg: 'rgba(167,139,250,0.1)', border: 'rgba(167,139,250,0.2)' },
  appreciation:{ color: C.success, bg: 'rgba(16,185,129,0.1)',  border: 'rgba(16,185,129,0.2)'  },
}

// ─── Shared micro-components ──────────────────────────────────────────────────
const Badge = ({ label, palette }) => {
  if (!label) return <span style={{ color: C.textMut, fontFamily: 'Space Mono, monospace', fontSize: 9 }}>—</span>
  const key = label.toString().toLowerCase()
  const p = (palette || STATUS_PAL)[key] || { color: C.textMut, bg: 'rgba(156,163,175,0.1)', border: 'rgba(156,163,175,0.2)' }
  return (
    <span style={{
      fontFamily: 'Space Mono, monospace', fontSize: 9, fontWeight: 700,
      letterSpacing: '0.12em', textTransform: 'uppercase',
      color: p.color, background: p.bg, border: `1px solid ${p.border}`,
      borderRadius: 2, padding: '2px 8px', whiteSpace: 'nowrap',
    }}>{label}</span>
  )
}

const thStyle = {
  fontFamily: 'Space Mono, monospace', fontSize: 9, fontWeight: 700,
  letterSpacing: '0.14em', textTransform: 'uppercase', color: C.textMut,
  padding: '10px 14px', textAlign: 'left', borderBottom: `1px solid ${C.border}`,
  background: C.bg, whiteSpace: 'nowrap',
}
const tdStyle = {
  padding: '12px 14px', borderBottom: `1px solid ${C.border}`,
  fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: C.text,
  verticalAlign: 'middle',
}

// ─── Shimmer ──────────────────────────────────────────────────────────────────
const Shimmer = ({ w = '100%', h = 14, radius = 3 }) => (
  <div style={{
    width: w, height: h, borderRadius: radius,
    background: `linear-gradient(90deg, ${C.surface} 25%, ${C.surfH} 50%, ${C.surface} 75%)`,
    backgroundSize: '200% 100%',
    animation: 'cm-shimmer 1.5s infinite',
  }} />
)

const ShimmerRow = ({ cols = 5 }) => (
  <tr>
    {Array.from({ length: cols }).map((_, i) => (
      <td key={i} style={tdStyle}><Shimmer w={80 + i * 20} /></td>
    ))}
  </tr>
)

// ─── Pagination strip ─────────────────────────────────────────────────────────
const Pager = ({ page, total, onChange }) => {
  if (total <= 1) return null
  const btnBase = {
    fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12,
    color: C.text, background: C.surface,
    border: `1px solid ${C.border}`, borderRadius: 4,
    padding: '6px 14px', cursor: 'pointer', transition: 'background 0.15s',
  }
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'flex-end',
      gap: 8, marginTop: 14,
    }}>
      <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMut, letterSpacing: '0.1em' }}>
        PAGE {page} / {total}
      </span>
      <button
        disabled={page <= 1} onClick={() => onChange(page - 1)}
        style={{ ...btnBase, opacity: page <= 1 ? 0.35 : 1, cursor: page <= 1 ? 'not-allowed' : 'pointer' }}
        onMouseEnter={e => { if (page > 1) e.target.style.background = '#374151' }}
        onMouseLeave={e => { e.target.style.background = C.surface }}
      >← Prev</button>
      <button
        disabled={page >= total} onClick={() => onChange(page + 1)}
        style={{ ...btnBase, opacity: page >= total ? 0.35 : 1, cursor: page >= total ? 'not-allowed' : 'pointer' }}
        onMouseEnter={e => { if (page < total) e.target.style.background = '#374151' }}
        onMouseLeave={e => { e.target.style.background = C.surface }}
      >Next →</button>
    </div>
  )
}

// ─── Empty state ──────────────────────────────────────────────────────────────
const Empty = ({ label = 'No Records', cols }) => (
  <tr>
    <td colSpan={cols} style={{ ...tdStyle, textAlign: 'center', padding: '48px 0', color: C.textMut }}>
      <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 22, letterSpacing: '0.04em', marginBottom: 6 }}>{label}</div>
      <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase' }}>Nothing to display</div>
    </td>
  </tr>
)

// ─── Error banner ─────────────────────────────────────────────────────────────
const ErrBanner = ({ msg }) => msg ? (
  <div style={{
    background: 'rgba(239,68,68,0.08)', border: `1px solid rgba(239,68,68,0.25)`,
    borderRadius: 6, padding: '12px 16px', marginBottom: 16,
    fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: C.danger,
  }}>{msg}</div>
) : null

// ─── Stat card ────────────────────────────────────────────────────────────────
const StatCard = ({ label, value, color, loading }) => (
  <div style={{
    background: C.surface, border: `1px solid ${C.border}`, borderRadius: 6,
    padding: '14px 18px', flex: 1, minWidth: 110,
  }}>
    {loading
      ? <Shimmer w="60%" h={24} />
      : <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 28, color: color || C.text, letterSpacing: '0.04em', lineHeight: 1 }}>{value ?? '—'}</div>
    }
    <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, letterSpacing: '0.14em', textTransform: 'uppercase', color: C.textMut, marginTop: 4 }}>{label}</div>
  </div>
)

// ─── TABS ─────────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'messages',      label: 'Messages' },
  { id: 'broadcasts',    label: 'Broadcasts' },
  { id: 'campaigns',     label: 'Campaigns' },
  { id: 'feedback',      label: 'Feedback' },
  { id: 'announcements', label: 'Announcements' },
]

// ─── Messages Tab ─────────────────────────────────────────────────────────────
function MessagesTab({ navigate }) {
  const [rows,   setRows]   = useState([])
  const [loading,setLoading]= useState(true)
  const [error,  setError]  = useState(null)
  const [page,   setPage]   = useState(1)
  const [total,  setTotal]  = useState(1)
  const [channel,setChannel]= useState('')
  const [status, setStatus] = useState('')
  const PAGE = 20

  const load = useCallback(() => {
    setLoading(true); setError(null)
    const params = { page, page_size: PAGE }
    if (channel) params.channel = channel.toUpperCase()
    if (status)  params.status  = status.toUpperCase()
    communicationsApi.listMessages(params)
      .then(r => { setRows(r.data.results || []); setTotal(Math.ceil((r.data.count || 0) / PAGE)) })
      .catch(e => setError(extractError(e)))
      .finally(() => setLoading(false))
  }, [page, channel, status])

  useEffect(() => { load() }, [load])

  const filters = (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
      {[
        { val: channel, set: v => { setChannel(v); setPage(1) }, opts: ['','SMS','Email','Push','Social'], label: 'Channel' },
        { val: status,  set: v => { setStatus(v);  setPage(1) }, opts: ['','Sent','Delivered','Failed','Pending','Draft'], label: 'Status' },
      ].map(f => (
        <select key={f.label} value={f.val} onChange={e => f.set(e.target.value)} style={{
          background: C.surface, border: `1px solid ${C.border}`, borderRadius: 4,
          color: C.textSub, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12,
          padding: '6px 10px', cursor: 'pointer', outline: 'none',
        }}>
          {f.opts.map(o => <option key={o} value={o}>{o || `All ${f.label}s`}</option>)}
        </select>
      ))}
    </div>
  )

  return (
    <>
      {filters}
      <ErrBanner msg={error} />
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 6, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>{['Channel','Recipient','Subject','Status','Priority','Sent At'].map(h => <th key={h} style={thStyle}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 8 }).map((_,i) => <ShimmerRow key={i} cols={6} />)
              : rows.length === 0
                ? <Empty label="No Messages" cols={6} />
                : rows.map(m => (
                  <tr key={m.id} className="cm-row" onClick={() => navigate(`/dashboard/communications/${m.id}`)}>
                    <td style={tdStyle}><Badge label={m.channel} palette={CHANNEL_PAL} /></td>
                    <td style={{ ...tdStyle, color: C.textSub, maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {m.recipient_identifier || m.recipient || '—'}
                    </td>
                    <td style={{ ...tdStyle, maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {m.subject || '(no subject)'}
                    </td>
                    <td style={tdStyle}><Badge label={m.status} /></td>
                    <td style={tdStyle}><Badge label={m.priority} /></td>
                    <td style={{ ...tdStyle, color: C.textSub, whiteSpace: 'nowrap' }}>
                      {m.sent_at ? format(new Date(m.sent_at), 'dd MMM yy, HH:mm') : '—'}
                    </td>
                  </tr>
                ))
            }
          </tbody>
        </table>
      </div>
      <Pager page={page} total={total} onChange={setPage} />
    </>
  )
}

// ─── Broadcasts Tab ───────────────────────────────────────────────────────────
function BroadcastsTab({ navigate }) {
  const [rows,   setRows]   = useState([])
  const [loading,setLoading]= useState(true)
  const [error,  setError]  = useState(null)
  const [page,   setPage]   = useState(1)
  const [total,  setTotal]  = useState(1)
  const [approving, setApproving] = useState(null)
  const PAGE = 20

  const load = useCallback(() => {
    setLoading(true); setError(null)
    communicationsApi.listBroadcasts({ page, page_size: PAGE })
      .then(r => { setRows(r.data.results || []); setTotal(Math.ceil((r.data.count || 0) / PAGE)) })
      .catch(e => setError(extractError(e)))
      .finally(() => setLoading(false))
  }, [page])

  useEffect(() => { load() }, [load])

  const handleApprove = async (e, id) => {
    e.stopPropagation()
    setApproving(id)
    try {
      await communicationsApi.approveBroadcast(id)
      load()
    } catch (err) {
      setError(extractError(err))
    } finally {
      setApproving(null)
    }
  }

  return (
    <>
      <ErrBanner msg={error} />
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 6, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>{['Title','Channels','Recipients','Sent','Delivered','Rate','Status','Scheduled','Action'].map(h => <th key={h} style={thStyle}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 6 }).map((_,i) => <ShimmerRow key={i} cols={9} />)
              : rows.length === 0
                ? <Empty label="No Broadcasts" cols={9} />
                : rows.map(b => {
                  const rate = b.delivery_rate != null ? `${b.delivery_rate.toFixed(1)}%` : '—'
                  const channels = Array.isArray(b.channels) ? b.channels.join(', ') : (b.channels || '—')
                  return (
                    <tr key={b.id} className="cm-row" onClick={() => navigate(`/dashboard/communications/${b.id}`)}>
                      <td style={{ ...tdStyle, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 500 }}>{b.title || '—'}</td>
                      <td style={{ ...tdStyle, color: C.textSub, fontSize: 11 }}>{channels}</td>
                      <td style={{ ...tdStyle, color: C.textSub }}>{b.total_recipients ?? '—'}</td>
                      <td style={{ ...tdStyle, color: C.textSub }}>{b.messages_sent ?? '—'}</td>
                      <td style={{ ...tdStyle, color: C.textSub }}>{b.messages_delivered ?? '—'}</td>
                      <td style={{ ...tdStyle, color: C.success }}>{rate}</td>
                      <td style={tdStyle}><Badge label={b.status} /></td>
                      <td style={{ ...tdStyle, color: C.textSub, whiteSpace: 'nowrap', fontSize: 11 }}>
                        {b.scheduled_for ? format(new Date(b.scheduled_for), 'dd MMM yy, HH:mm') : '—'}
                      </td>
                      <td style={tdStyle} onClick={e => e.stopPropagation()}>
                        {b.status === 'PENDING' && (
                          <button
                            disabled={approving === b.id}
                            onClick={e => handleApprove(e, b.id)}
                            style={{
                              fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, fontWeight: 500,
                              color: '#fff', background: approving === b.id ? '#374151' : C.success,
                              border: 'none', borderRadius: 3, padding: '4px 10px',
                              cursor: approving === b.id ? 'not-allowed' : 'pointer',
                            }}
                          >{approving === b.id ? '…' : 'Approve'}</button>
                        )}
                      </td>
                    </tr>
                  )
                })
            }
          </tbody>
        </table>
      </div>
      <Pager page={page} total={total} onChange={setPage} />
    </>
  )
}

// ─── Campaigns Tab ────────────────────────────────────────────────────────────
function CampaignsTab({ navigate }) {
  const [rows,   setRows]   = useState([])
  const [loading,setLoading]= useState(true)
  const [error,  setError]  = useState(null)
  const [page,   setPage]   = useState(1)
  const [total,  setTotal]  = useState(1)
  const [acting, setActing] = useState(null)
  const PAGE = 20

  const load = useCallback(() => {
    setLoading(true); setError(null)
    communicationsApi.listCampaigns({ page, page_size: PAGE })
      .then(r => { setRows(r.data.results || []); setTotal(Math.ceil((r.data.count || 0) / PAGE)) })
      .catch(e => setError(extractError(e)))
      .finally(() => setLoading(false))
  }, [page])

  useEffect(() => { load() }, [load])

  const doAction = async (e, fn, id) => {
    e.stopPropagation(); setActing(id)
    try { await fn(id); load() }
    catch (err) { setError(extractError(err)) }
    finally { setActing(null) }
  }

  return (
    <>
      <ErrBanner msg={error} />
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 6, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>{['Name','Type','Status','Reach','Start','End','Actions'].map(h => <th key={h} style={thStyle}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 6 }).map((_,i) => <ShimmerRow key={i} cols={7} />)
              : rows.length === 0
                ? <Empty label="No Campaigns" cols={7} />
                : rows.map(c => (
                  <tr key={c.id} className="cm-row" onClick={() => navigate(`/dashboard/communications/${c.id}`)}>
                    <td style={{ ...tdStyle, fontWeight: 500, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.name}</td>
                    <td style={{ ...tdStyle, color: C.textSub, fontSize: 11 }}>{c.campaign_type || '—'}</td>
                    <td style={tdStyle}><Badge label={c.status} /></td>
                    <td style={{ ...tdStyle, color: C.textSub }}>
                      {c.actual_reach != null ? `${c.actual_reach} / ${c.target_reach ?? '?'}` : '—'}
                    </td>
                    <td style={{ ...tdStyle, color: C.textSub, fontSize: 11, whiteSpace: 'nowrap' }}>
                      {c.start_date ? format(new Date(c.start_date), 'dd MMM yy') : '—'}
                    </td>
                    <td style={{ ...tdStyle, color: C.textSub, fontSize: 11, whiteSpace: 'nowrap' }}>
                      {c.end_date ? format(new Date(c.end_date), 'dd MMM yy') : '—'}
                    </td>
                    <td style={tdStyle} onClick={e => e.stopPropagation()}>
                      <div style={{ display: 'flex', gap: 6 }}>
                        {c.status === 'DRAFT' && (
                          <CampaignBtn label="Launch" color={C.success} disabled={acting === c.id}
                            onClick={e => doAction(e, communicationsApi.launchCampaign, c.id)} />
                        )}
                        {c.status === 'ACTIVE' && (
                          <CampaignBtn label="Pause" color={C.warning} disabled={acting === c.id}
                            onClick={e => doAction(e, communicationsApi.pauseCampaign, c.id)} />
                        )}
                        {c.status === 'PAUSED' && (
                          <CampaignBtn label="Resume" color={C.accent} disabled={acting === c.id}
                            onClick={e => doAction(e, communicationsApi.launchCampaign, c.id)} />
                        )}
                      </div>
                    </td>
                  </tr>
                ))
            }
          </tbody>
        </table>
      </div>
      <Pager page={page} total={total} onChange={setPage} />
    </>
  )
}

function CampaignBtn({ label, color, onClick, disabled }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      style={{
        fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, fontWeight: 500,
        color: '#fff', background: disabled ? '#374151' : color,
        border: 'none', borderRadius: 3, padding: '4px 10px',
        cursor: disabled ? 'not-allowed' : 'pointer',
      }}
    >{disabled ? '…' : label}</button>
  )
}

// ─── Feedback Tab ─────────────────────────────────────────────────────────────
function FeedbackTab({ navigate }) {
  const [rows,   setRows]   = useState([])
  const [loading,setLoading]= useState(true)
  const [error,  setError]  = useState(null)
  const [page,   setPage]   = useState(1)
  const [total,  setTotal]  = useState(1)
  const PAGE = 20

  const load = useCallback(() => {
    setLoading(true); setError(null)
    communicationsApi.listFeedback({ page, page_size: PAGE })
      .then(r => { setRows(r.data.results || []); setTotal(Math.ceil((r.data.count || 0) / PAGE)) })
      .catch(e => setError(extractError(e)))
      .finally(() => setLoading(false))
  }, [page])

  useEffect(() => { load() }, [load])

  return (
    <>
      <ErrBanner msg={error} />
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 6, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>{['Type','Subject','From','Status','Urgent','Assigned To','Received'].map(h => <th key={h} style={thStyle}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 6 }).map((_,i) => <ShimmerRow key={i} cols={7} />)
              : rows.length === 0
                ? <Empty label="No Feedback" cols={7} />
                : rows.map(f => (
                  <tr key={f.id} className="cm-row" onClick={() => navigate(`/dashboard/communications/${f.id}`)}>
                    <td style={tdStyle}><Badge label={f.feedback_type} palette={FEEDBACK_PAL} /></td>
                    <td style={{ ...tdStyle, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 500 }}>{f.subject || '—'}</td>
                    <td style={{ ...tdStyle, color: C.textSub }}>{f.sender_name || '—'}</td>
                    <td style={tdStyle}><Badge label={f.status} /></td>
                    <td style={tdStyle}>
                      {f.is_urgent
                        ? <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.danger, fontWeight: 700, letterSpacing: '0.1em' }}>URGENT</span>
                        : <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMut }}>—</span>
                      }
                    </td>
                    <td style={{ ...tdStyle, color: C.textSub }}>{f.assigned_to_name || f.assigned_to || '—'}</td>
                    <td style={{ ...tdStyle, color: C.textSub, whiteSpace: 'nowrap', fontSize: 11 }}>
                      {f.created_at ? format(new Date(f.created_at), 'dd MMM yy, HH:mm') : '—'}
                    </td>
                  </tr>
                ))
            }
          </tbody>
        </table>
      </div>
      <Pager page={page} total={total} onChange={setPage} />
    </>
  )
}

// ─── Announcements Tab ────────────────────────────────────────────────────────
function AnnouncementsTab({ navigate }) {
  const [rows,   setRows]   = useState([])
  const [loading,setLoading]= useState(true)
  const [error,  setError]  = useState(null)
  const [page,   setPage]   = useState(1)
  const [total,  setTotal]  = useState(1)
  const PAGE = 20

  const load = useCallback(() => {
    setLoading(true); setError(null)
    communicationsApi.listAnnouncements({ page, page_size: PAGE })
      .then(r => { setRows(r.data.results || []); setTotal(Math.ceil((r.data.count || 0) / PAGE)) })
      .catch(e => setError(extractError(e)))
      .finally(() => setLoading(false))
  }, [page])

  useEffect(() => { load() }, [load])

  return (
    <>
      <ErrBanner msg={error} />
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 6, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>{['Title','Type','Published','Featured','Views','Publish Date'].map(h => <th key={h} style={thStyle}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 6 }).map((_,i) => <ShimmerRow key={i} cols={6} />)
              : rows.length === 0
                ? <Empty label="No Announcements" cols={6} />
                : rows.map(a => (
                  <tr key={a.id} className="cm-row" onClick={() => navigate(`/dashboard/communications/${a.id}`)}>
                    <td style={{ ...tdStyle, fontWeight: 500, maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.title}</td>
                    <td style={{ ...tdStyle, color: C.textSub, fontSize: 11 }}>{a.announcement_type || '—'}</td>
                    <td style={tdStyle}>
                      <span style={{
                        fontFamily: 'Space Mono, monospace', fontSize: 9,
                        color: a.is_published ? C.success : C.textMut, letterSpacing: '0.1em',
                      }}>{a.is_published ? 'LIVE' : 'DRAFT'}</span>
                    </td>
                    <td style={tdStyle}>
                      {a.is_featured
                        ? <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.warning, letterSpacing: '0.1em', fontWeight: 700 }}>★ YES</span>
                        : <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMut }}>—</span>
                      }
                    </td>
                    <td style={{ ...tdStyle, color: C.textSub }}>{a.view_count ?? 0}</td>
                    <td style={{ ...tdStyle, color: C.textSub, fontSize: 11, whiteSpace: 'nowrap' }}>
                      {a.publish_date ? format(new Date(a.publish_date), 'dd MMM yy') : '—'}
                    </td>
                  </tr>
                ))
            }
          </tbody>
        </table>
      </div>
      <Pager page={page} total={total} onChange={setPage} />
    </>
  )
}

// ─── Root Component ───────────────────────────────────────────────────────────
export default function Communications() {
  const navigate    = useNavigate()
  const toast       = useToast()
  const [tab,  setTab]  = useState('messages')
  const [stats,setStats]= useState(null)
  const [sLoading, setSLoading] = useState(true)
  const [btnHover, setBtnHover] = useState(false)

  // Dashboard stats
  useEffect(() => {
    setSLoading(true)
    communicationsApi.getDashboard()
      .then(r => { if (r.data) setStats(r.data) })
      .catch(e => { if (import.meta.env.DEV) console.warn('[Communications] Dashboard stats unavailable:', e); toast.warning?.('Communications dashboard stats unavailable') })
      .finally(() => setSLoading(false))
  }, [])

  return (
    <>
      <style>{`
        @keyframes cm-shimmer {
          0%   { background-position: -200% 0; }
          100% { background-position:  200% 0; }
        }
        @keyframes cm-fadeUp {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .cm-row:hover td { background: rgba(255,255,255,0.02); cursor: pointer; }
      `}</style>

      <div style={{ padding: '28px 32px', minHeight: '100vh', background: C.bg, animation: 'cm-fadeUp 0.35s ease both' }}>

        {/* ── Eyebrow ── */}
        <div style={{ marginBottom: 4 }}>
          <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: C.accent }}>Communications</span>
          <span style={{ color: C.border, margin: '0 6px', fontFamily: 'Space Mono, monospace', fontSize: 9 }}>/</span>
          <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: C.textMut }}>Hub</span>
        </div>

        {/* ── Header ── */}
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
          <h1 style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 36, color: C.text, letterSpacing: '0.04em', margin: 0 }}>
            Communications
          </h1>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={() => navigate('/dashboard/communications/compose')}
              onMouseEnter={() => setBtnHover(true)}
              onMouseLeave={() => setBtnHover(false)}
              style={{
                fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, fontWeight: 500,
                color: '#fff', background: btnHover ? '#2563eb' : C.accent,
                border: 'none', borderRadius: 4, padding: '8px 16px',
                cursor: 'pointer', transition: 'background 0.15s',
              }}
            >+ Compose</button>
          </div>
        </div>

        {/* ── Stat Strip ── */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
          <StatCard label="Active Campaigns"   value={stats?.active_campaigns}     color={C.accent}   loading={sLoading} />
          <StatCard label="Sent Today"         value={stats?.messages_sent_today}  color={C.success}  loading={sLoading} />
          <StatCard label="Pending"            value={stats?.messages_pending}     color={C.warning}  loading={sLoading} />
          <StatCard label="7d Delivery Rate"   value={stats?.delivery_rate_7d != null ? `${stats.delivery_rate_7d.toFixed(1)}%` : null} color={C.success} loading={sLoading} />
          <StatCard label="Feedback Pending"   value={stats?.feedback_pending}     color={C.danger}   loading={sLoading} />
          <StatCard label="Live Announcements" value={stats?.announcements_live}   color={C.purple}   loading={sLoading} />
        </div>

        {/* ── Tab Bar ── */}
        <div style={{ display: 'flex', gap: 0, borderBottom: `1px solid ${C.border}`, marginBottom: 20 }}>
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                fontFamily: 'Space Mono, monospace', fontSize: 9, fontWeight: 700,
                letterSpacing: '0.12em', textTransform: 'uppercase',
                color: tab === t.id ? C.accent : C.textMut,
                background: 'none', border: 'none',
                borderBottom: `2px solid ${tab === t.id ? C.accent : 'transparent'}`,
                padding: '10px 18px', cursor: 'pointer',
                transition: 'color 0.15s, border-color 0.15s',
              }}
            >{t.label}</button>
          ))}
        </div>

        {/* ── Tab Panels ── */}
        {tab === 'messages'      && <MessagesTab      navigate={navigate} />}
        {tab === 'broadcasts'    && <BroadcastsTab    navigate={navigate} />}
        {tab === 'campaigns'     && <CampaignsTab     navigate={navigate} />}
        {tab === 'feedback'      && <FeedbackTab      navigate={navigate} />}
        {tab === 'announcements' && <AnnouncementsTab navigate={navigate} />}
      </div>
    </>
  )
}