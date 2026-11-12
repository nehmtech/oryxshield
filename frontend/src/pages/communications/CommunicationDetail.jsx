/**
 * CommunicationDetail — OryxShield
 * =========================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Smart detail view — resolves which resource the :id belongs to by trying
 * the appropriate endpoint based on query-param ?type= or attempting messages first.
 *
 * Routes:
 *   /dashboard/communications/:id?type=message      → communicationsApi.getMessage
 *   /dashboard/communications/:id?type=broadcast    → communicationsApi.getBroadcast
 *   /dashboard/communications/:id?type=campaign     → communicationsApi.getCampaign
 *   /dashboard/communications/:id?type=feedback     → communicationsApi.getFeedback
 *   /dashboard/communications/:id?type=announcement → communicationsApi.getAnnouncement
 *   (no ?type)                                       → tries getMessage first
 *
 * Actions supported:
 *   Broadcast: approve, cancel
 *   Campaign:  launch, pause, complete
 *   Feedback:  respond, resolve, assign
 *   Message:   retry (failed messages)
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { format } from 'date-fns'
import { communicationsApi, extractError } from '../../services/api'
import { useToast } from '../../context/ToastContext'
import Breadcrumb from '../../components/ui/Breadcrumb'

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

const CHANNEL_PAL = {
  sms:    { color: C.success, bg: 'rgba(16,185,129,0.12)',  border: 'rgba(16,185,129,0.25)' },
  email:  { color: C.accent,  bg: 'rgba(59,130,246,0.12)', border: 'rgba(59,130,246,0.25)' },
  push:   { color: C.warning, bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.25)' },
  social: { color: C.purple,  bg: 'rgba(167,139,250,0.12)',border: 'rgba(167,139,250,0.25)' },
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

const Badge = ({ label, palette }) => {
  if (!label) return <span style={{ color: C.textMut, fontSize: 12, fontFamily: 'IBM Plex Sans, sans-serif' }}>—</span>
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

const Shimmer = ({ w = '100%', h = 14, radius = 3 }) => (
  <div style={{
    width: w, height: h, borderRadius: radius,
    background: `linear-gradient(90deg, ${C.surface} 25%, ${C.surfH} 50%, ${C.surface} 75%)`,
    backgroundSize: '200% 100%',
    animation: 'cd-shimmer 1.5s infinite',
  }} />
)

const Field = ({ label, children, span }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 5, gridColumn: span ? `span ${span}` : undefined }}>
    <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: C.textMut }}>
      {label}
    </span>
    <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: C.text }}>{children}</div>
  </div>
)

const Divider = () => <div style={{ borderTop: `1px solid ${C.border}`, margin: '4px 0' }} />

const ActionBtn = ({ label, color, onClick, loading, disabled }) => (
  <button
    onClick={onClick}
    disabled={loading || disabled}
    style={{
      fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, fontWeight: 500,
      color: '#fff', background: loading || disabled ? '#374151' : color,
      border: 'none', borderRadius: 4, padding: '8px 16px',
      cursor: loading || disabled ? 'not-allowed' : 'pointer',
      transition: 'background 0.15s',
    }}
  >{loading ? '…' : label}</button>
)

// ─── Delivery Timeline ────────────────────────────────────────────────────────
const DeliveryTimeline = ({ timeline }) => {
  if (!Array.isArray(timeline) || !timeline.length) return null
  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: C.textMut, marginBottom: 12 }}>
        Delivery Timeline
      </div>
      {timeline.map((evt, i) => {
        const key = evt.status?.toLowerCase()
        const dotColor = (STATUS_PAL[key] || {}).color || C.textMut
        const isLast = i === timeline.length - 1
        return (
          <div key={i} style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 16, flexShrink: 0 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: dotColor, flexShrink: 0, boxShadow: `0 0 6px ${dotColor}55`, marginTop: 3 }} />
              {!isLast && <div style={{ width: 1, flexGrow: 1, background: C.border, minHeight: 20, marginTop: 2 }} />}
            </div>
            <div style={{ paddingBottom: isLast ? 0 : 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <Badge label={evt.status} />
                {evt.timestamp && (
                  <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMut, letterSpacing: '0.08em' }}>
                    {format(new Date(evt.timestamp), 'dd MMM yyyy, HH:mm:ss')}
                  </span>
                )}
              </div>
              {evt.message && <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: C.textSub, marginTop: 4 }}>{evt.message}</div>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ─── Feedback response form ───────────────────────────────────────────────────
function FeedbackResponseForm({ id, onDone }) {
  const toast = useToast()
  const [text, setText]   = useState('')
  const [busy, setBusy]   = useState(false)
  const [err,  setErr]    = useState(null)
  const [focused, setFocused] = useState(false)

  const submit = async () => {
    if (!text.trim()) return
    setBusy(true); setErr(null)
    try {
      await communicationsApi.respondFeedback(id, { response: text })
      toast.success('Response sent')
      onDone()
    } catch (e) {
      setErr(extractError(e)); toast.error(extractError(e))
    } finally { setBusy(false) }
  }

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: C.textMut, marginBottom: 10 }}>
        Send Response
      </div>
      <textarea
        value={text}
        onChange={e => setText(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder="Type your response…"
        rows={4}
        style={{
          width: '100%', boxSizing: 'border-box',
          background: C.bg, border: `1px solid ${focused ? C.accent : C.border}`,
          borderRadius: 4, padding: '10px 12px',
          fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: C.text,
          resize: 'vertical', outline: 'none', transition: 'border-color 0.15s',
        }}
      />
      {err && <div style={{ color: C.danger, fontSize: 12, fontFamily: 'IBM Plex Sans, sans-serif', marginTop: 6 }}>{err}</div>}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}>
        <ActionBtn label="Send Response" color={C.accent} onClick={submit} loading={busy} disabled={!text.trim()} />
      </div>
    </div>
  )
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────
const LoadingSkeleton = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
    {[['60%', 10], ['40%', 14], ['100%', 18], ['80%', 14], ['100%', 80]].map(([w, h], i) => (
      <Shimmer key={i} w={w} h={h} />
    ))}
  </div>
)

// ─── Main component ───────────────────────────────────────────────────────────
export default function CommunicationDetail() {
  const { id }               = useParams()
  const [searchParams]       = useSearchParams()
  const navigate             = useNavigate()
  const toast                = useToast()
  const hintType             = searchParams.get('type')

  const [data,     setData]     = useState(null)
  const [type,     setType]     = useState(hintType || 'message')
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState(null)
  const [acting,   setActing]   = useState(null)
  const [backHover,setBackHover]= useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      let res
      if (hintType === 'broadcast')    res = await communicationsApi.getBroadcast(id)
      else if (hintType === 'campaign')res = await communicationsApi.getCampaign(id)
      else if (hintType === 'feedback')res = await communicationsApi.getFeedback(id)
      else if (hintType === 'announcement') res = await communicationsApi.getAnnouncement(id)
      else {
        // Try message first, fall back to others
        try { res = await communicationsApi.getMessage(id); setType('message') }
        catch {
          try { res = await communicationsApi.getBroadcast(id); setType('broadcast') }
          catch {
            try { res = await communicationsApi.getCampaign(id); setType('campaign') }
            catch { res = await communicationsApi.getFeedback(id); setType('feedback') }
          }
        }
      }
      setData(res.data)
    } catch (e) {
      setError(extractError(e))
    } finally {
      setLoading(false)
    }
  }, [id, hintType])

  useEffect(() => { load() }, [load])

  const doAction = async (label, fn) => {
    setActing(label)
    try {
      await fn()
      toast.success(`${label} successful`)
      load()
    } catch (e) {
      toast.error(extractError(e))
    } finally { setActing(null) }
  }

  // ── Title derivation ──
  const getTitle = () => {
    if (!data) return 'Loading…'
    return data.title || data.subject || data.name || 'Detail'
  }

  // ── Type label ──
  const typeLabel = {
    message:      'Message',
    broadcast:    'Broadcast',
    campaign:     'Campaign',
    feedback:     'Feedback',
    announcement: 'Announcement',
  }[type] || 'Record'

  return (
    <>
      <style>{`
        @keyframes cd-shimmer {
          0%   { background-position: -200% 0; }
          100% { background-position:  200% 0; }
        }
        @keyframes cd-fadeUp {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div style={{ padding: '28px 32px', minHeight: '100vh', background: C.bg, maxWidth: 860, animation: 'cd-fadeUp 0.35s ease both' }}>

        {/* Breadcrumb */}
        <Breadcrumb items={[
          { label: 'Communications', to: '/dashboard/communications' },
          { label: loading ? '…' : (getTitle() || `#${id}`) },
        ]} />

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24, gap: 16, flexWrap: 'wrap' }}>
          <h1 style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 34, color: C.text, letterSpacing: '0.04em', margin: 0 }}>
            {loading ? 'Loading…' : getTitle()}
          </h1>
          <button
            onClick={() => navigate('/dashboard/communications')}
            onMouseEnter={() => setBackHover(true)}
            onMouseLeave={() => setBackHover(false)}
            style={{
              fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, fontWeight: 500,
              color: backHover ? C.text : C.textSub,
              background: backHover ? C.border : 'transparent',
              border: `1px solid ${C.border}`, borderRadius: 4,
              padding: '8px 16px', cursor: 'pointer', transition: 'all 0.15s', flexShrink: 0,
            }}
          >← Back</button>
        </div>

        {/* Error */}
        {error && (
          <div style={{
            background: 'rgba(239,68,68,0.08)', border: `1px solid rgba(239,68,68,0.25)`,
            borderRadius: 6, padding: '12px 16px', marginBottom: 20,
            fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: C.danger,
          }}>{error}</div>
        )}

        {/* Card */}
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 6, padding: '24px 28px' }}>
          {loading ? <LoadingSkeleton /> : !data ? (
            <div style={{ textAlign: 'center', padding: '40px 0', fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: C.textMut }}>
              Record not found.
            </div>
          ) : (
            <>
              {/* ── MESSAGE ── */}
              {type === 'message' && (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
                    <Badge label={data.channel} palette={CHANNEL_PAL} />
                    <Badge label={data.status} />
                    <Badge label={data.priority} />
                    {data.sent_at && (
                      <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMut, letterSpacing: '0.08em' }}>
                        {format(new Date(data.sent_at), 'dd MMM yyyy, HH:mm')}
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '18px 32px', marginBottom: 20 }}>
                    <Field label="Recipient">{data.recipient_identifier || data.recipient || '—'}</Field>
                    <Field label="Subject">{data.subject || '—'}</Field>
                    {data.campaign_name && <Field label="Campaign">{data.campaign_name}</Field>}
                    {data.sender && <Field label="Sender">{data.sender}</Field>}
                    <Field label="Created">{data.created_at ? format(new Date(data.created_at), 'dd MMM yyyy, HH:mm') : '—'}</Field>
                    {data.delivered_at && <Field label="Delivered">{format(new Date(data.delivered_at), 'dd MMM yyyy, HH:mm')}</Field>}
                  </div>
                  <Divider />
                  <div style={{ marginTop: 16 }}>
                    <Field label="Body">
                      <pre style={{
                        margin: '6px 0 0', padding: '14px 16px',
                        background: C.bg, border: `1px solid ${C.border}`,
                        borderRadius: 4, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                        fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: '#d1d5db', lineHeight: 1.7,
                      }}>{data.body || data.content || data.message || '(no body)'}</pre>
                    </Field>
                  </div>
                  {data.status === 'FAILED' && (
                    <>
                      <Divider />
                      <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
                        <ActionBtn label="Retry" color={C.warning}
                          onClick={() => doAction('Retry', () => communicationsApi.getMessage(id))}
                          loading={acting === 'Retry'} />
                      </div>
                    </>
                  )}
                  {data.delivery_timeline && (
                    <>
                      <Divider />
                      <DeliveryTimeline timeline={data.delivery_timeline} />
                    </>
                  )}
                </>
              )}

              {/* ── BROADCAST ── */}
              {type === 'broadcast' && (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
                    <Badge label={data.status} />
                    {Array.isArray(data.channels) && data.channels.map(ch => (
                      <Badge key={ch} label={ch} palette={CHANNEL_PAL} />
                    ))}
                    {data.created_at && (
                      <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMut }}>
                        {format(new Date(data.created_at), 'dd MMM yyyy, HH:mm')}
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '18px 32px', marginBottom: 20 }}>
                    <Field label="Created By">{data.created_by_name || '—'}</Field>
                    <Field label="Approved By">{data.approved_by_name || '—'}</Field>
                    <Field label="Scheduled For">{data.scheduled_for ? format(new Date(data.scheduled_for), 'dd MMM yyyy, HH:mm') : '—'}</Field>
                    <Field label="Sent At">{data.sent_at ? format(new Date(data.sent_at), 'dd MMM yyyy, HH:mm') : '—'}</Field>
                    <Field label="Recipients">{data.total_recipients ?? '—'}</Field>
                    <Field label="Delivered">{data.messages_delivered ?? '—'} / {data.messages_sent ?? '—'}</Field>
                    <Field label="Delivery Rate">{data.delivery_rate != null ? `${data.delivery_rate.toFixed(1)}%` : '—'}</Field>
                    <Field label="Failed">{data.messages_failed ?? '—'}</Field>
                  </div>
                  {data.message_body && (
                    <>
                      <Divider />
                      <div style={{ marginTop: 16 }}>
                        <Field label="Message Body">
                          <pre style={{
                            margin: '6px 0 0', padding: '14px 16px',
                            background: C.bg, border: `1px solid ${C.border}`,
                            borderRadius: 4, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                            fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: '#d1d5db', lineHeight: 1.7,
                          }}>{data.message_body}</pre>
                        </Field>
                      </div>
                    </>
                  )}
                  {(data.status === 'PENDING' || data.status === 'DRAFT') && (
                    <>
                      <Divider />
                      <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
                        <ActionBtn label="Approve" color={C.success}
                          onClick={() => doAction('Approve', () => communicationsApi.approveBroadcast(id))}
                          loading={acting === 'Approve'} />
                        <ActionBtn label="Cancel" color={C.danger}
                          onClick={() => doAction('Cancel', () => communicationsApi.cancelBroadcast(id, { reason: 'Cancelled by operator' }))}
                          loading={acting === 'Cancel'} />
                      </div>
                    </>
                  )}
                </>
              )}

              {/* ── CAMPAIGN ── */}
              {type === 'campaign' && (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
                    <Badge label={data.status} />
                    <Badge label={data.campaign_type} />
                    {data.is_running && (
                      <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.success, letterSpacing: '0.1em', fontWeight: 700 }}>● RUNNING</span>
                    )}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '18px 32px', marginBottom: 20 }}>
                    <Field label="Manager">{data.manager_name || '—'}</Field>
                    <Field label="Reach">{data.actual_reach ?? '—'} / {data.target_reach ?? '?'}</Field>
                    <Field label="Start">{data.start_date ? format(new Date(data.start_date), 'dd MMM yyyy, HH:mm') : '—'}</Field>
                    <Field label="End">{data.end_date ? format(new Date(data.end_date), 'dd MMM yyyy, HH:mm') : '—'}</Field>
                    <Field label="Channels" span={2}>{Array.isArray(data.channels) ? data.channels.join(', ') : (data.channels || '—')}</Field>
                  </div>
                  {data.description && (
                    <>
                      <Divider />
                      <div style={{ marginTop: 16 }}>
                        <Field label="Description">
                          <p style={{ margin: 0, lineHeight: 1.6, color: C.textSub }}>{data.description}</p>
                        </Field>
                      </div>
                    </>
                  )}
                  <Divider />
                  <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
                    {data.status === 'DRAFT' && (
                      <ActionBtn label="Launch" color={C.success}
                        onClick={() => doAction('Launch', () => communicationsApi.launchCampaign(id))}
                        loading={acting === 'Launch'} />
                    )}
                    {data.status === 'ACTIVE' && (
                      <ActionBtn label="Pause" color={C.warning}
                        onClick={() => doAction('Pause', () => communicationsApi.pauseCampaign(id))}
                        loading={acting === 'Pause'} />
                    )}
                    {data.status === 'PAUSED' && (
                      <ActionBtn label="Resume" color={C.accent}
                        onClick={() => doAction('Resume', () => communicationsApi.launchCampaign(id))}
                        loading={acting === 'Resume'} />
                    )}
                    {(data.status === 'ACTIVE' || data.status === 'PAUSED') && (
                      <ActionBtn label="Complete" color={C.success}
                        onClick={() => doAction('Complete', () => communicationsApi.completeCampaign(id))}
                        loading={acting === 'Complete'} />
                    )}
                  </div>
                </>
              )}

              {/* ── FEEDBACK ── */}
              {type === 'feedback' && (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
                    <Badge label={data.feedback_type} />
                    <Badge label={data.status} />
                    {data.is_urgent && (
                      <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.danger, fontWeight: 700, letterSpacing: '0.12em' }}>⚠ URGENT</span>
                    )}
                    {data.created_at && (
                      <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMut }}>
                        {format(new Date(data.created_at), 'dd MMM yyyy, HH:mm')}
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '18px 32px', marginBottom: 20 }}>
                    <Field label="From">{data.sender_name || '—'}</Field>
                    <Field label="Contact">{data.sender_email || data.sender_phone || '—'}</Field>
                    <Field label="Subject" span={2}>{data.subject || '—'}</Field>
                    <Field label="Assigned To">{data.assigned_to_name || '—'}</Field>
                    <Field label="Response Time">{data.response_time_hours != null ? `${data.response_time_hours.toFixed(1)}h` : '—'}</Field>
                    {data.responded_at && <Field label="Responded At">{format(new Date(data.responded_at), 'dd MMM yyyy, HH:mm')}</Field>}
                    {data.resolved_at && <Field label="Resolved At">{format(new Date(data.resolved_at), 'dd MMM yyyy, HH:mm')}</Field>}
                  </div>
                  <Divider />
                  <div style={{ marginTop: 16 }}>
                    <Field label="Message">
                      <pre style={{
                        margin: '6px 0 0', padding: '14px 16px',
                        background: C.bg, border: `1px solid ${C.border}`,
                        borderRadius: 4, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                        fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: '#d1d5db', lineHeight: 1.7,
                      }}>{data.message || data.body || '(no message)'}</pre>
                    </Field>
                  </div>
                  {data.response && (
                    <>
                      <Divider />
                      <div style={{ marginTop: 16 }}>
                        <Field label="Response Sent">
                          <pre style={{
                            margin: '6px 0 0', padding: '14px 16px',
                            background: 'rgba(16,185,129,0.04)', border: `1px solid rgba(16,185,129,0.2)`,
                            borderRadius: 4, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                            fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: '#d1d5db', lineHeight: 1.7,
                          }}>{data.response}</pre>
                        </Field>
                      </div>
                    </>
                  )}
                  {data.status !== 'RESOLVED' && data.status !== 'CLOSED' && (
                    <>
                      <Divider />
                      <FeedbackResponseForm id={id} onDone={load} />
                      <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
                        {data.status === 'OPEN' && (
                          <ActionBtn label="Resolve" color={C.success}
                            onClick={() => doAction('Resolve', () => communicationsApi.resolveFeedback(id))}
                            loading={acting === 'Resolve'} />
                        )}
                        <ActionBtn label="Escalate" color={C.warning}
                          onClick={() => doAction('Escalate', () => communicationsApi.escalateFeedback(id, { reason: 'Requires senior review' }))}
                          loading={acting === 'Escalate'} />
                      </div>
                    </>
                  )}
                </>
              )}

              {/* ── ANNOUNCEMENT ── */}
              {type === 'announcement' && (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
                    <Badge label={data.announcement_type} />
                    <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: data.is_published ? C.success : C.textMut, letterSpacing: '0.1em', fontWeight: 700 }}>
                      {data.is_published ? 'PUBLISHED' : 'DRAFT'}
                    </span>
                    {data.is_featured && (
                      <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.warning, letterSpacing: '0.1em', fontWeight: 700 }}>★ FEATURED</span>
                    )}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '18px 32px', marginBottom: 20 }}>
                    <Field label="Author">{data.author_name || '—'}</Field>
                    <Field label="Views">{data.view_count ?? 0}</Field>
                    <Field label="Publish Date">{data.publish_date ? format(new Date(data.publish_date), 'dd MMM yyyy') : '—'}</Field>
                    <Field label="Expiry Date">{data.expiry_date ? format(new Date(data.expiry_date), 'dd MMM yyyy') : '—'}</Field>
                    <Field label="Slug" span={2}><code style={{ fontFamily: 'Space Mono, monospace', fontSize: 11, color: C.textSub }}>{data.slug || '—'}</code></Field>
                  </div>
                  {data.summary && (
                    <>
                      <Divider />
                      <div style={{ marginTop: 16 }}>
                        <Field label="Summary">
                          <p style={{ margin: '6px 0 0', lineHeight: 1.6, color: C.textSub, fontSize: 13, fontFamily: 'IBM Plex Sans, sans-serif' }}>{data.summary}</p>
                        </Field>
                      </div>
                    </>
                  )}
                  {data.content && (
                    <>
                      <Divider />
                      <div style={{ marginTop: 16 }}>
                        <Field label="Content">
                          <div style={{
                            margin: '6px 0 0', padding: '14px 16px',
                            background: C.bg, border: `1px solid ${C.border}`,
                            borderRadius: 4,
                            fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: '#d1d5db', lineHeight: 1.7,
                          }}>{data.content}</div>
                        </Field>
                      </div>
                    </>
                  )}
                </>
              )}
            </>
          )}
        </div>
      </div>
    </>
  )
}