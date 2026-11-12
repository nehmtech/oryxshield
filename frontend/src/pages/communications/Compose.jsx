/**
 * Compose — OryxShield
 * ==============================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Compose a message or create a broadcast.
 * Modes: Single Message · Broadcast
 *
 * API:
 *   POST /communications/messages/send/  — single message
 *   POST /communications/broadcasts/     — broadcast
 *   GET  /communications/templates/      — template list for quick-fill
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { communicationsApi, extractError } from '../../services/api'
import { useToast } from '../../context/ToastContext'

// ─── Design tokens ────────────────────────────────────────────────────────────
const C = {
  bg:      '#0a0f1e',
  surface: '#111827',
  border:  '#1f2937',
  accent:  '#3b82f6',
  danger:  '#ef4444',
  warning: '#f59e0b',
  success: '#10b981',
  text:    '#f9fafb',
  textSub: '#9ca3af',
  textMut: '#6b7280',
}

const CHANNELS = [
  { id: 'SMS',   label: 'SMS',   color: C.success },
  { id: 'EMAIL', label: 'Email', color: C.accent  },
  { id: 'PUSH',  label: 'Push',  color: C.warning },
]

const PRIORITIES = ['NORMAL', 'HIGH', 'CRITICAL']

const labelStyle = {
  fontFamily: 'Space Mono, monospace', fontSize: 9,
  letterSpacing: '0.14em', textTransform: 'uppercase',
  color: C.textMut, marginBottom: 6, display: 'block',
}

const inputStyle = (focused) => ({
  width: '100%',
  background: C.bg,
  border: `1px solid ${focused ? C.accent : C.border}`,
  borderRadius: 4,
  padding: '10px 12px',
  fontSize: 13,
  fontFamily: 'IBM Plex Sans, sans-serif',
  color: C.text,
  outline: 'none',
  boxSizing: 'border-box',
  transition: 'border-color 0.15s',
})

function Field({ label, children }) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      {children}
    </div>
  )
}

function FocusInput({ as: As = 'input', ...props }) {
  const [focused, setFocused] = useState(false)
  return (
    <As
      {...props}
      style={{ ...inputStyle(focused), ...(props.style || {}) }}
      onFocus={e => { setFocused(true); props.onFocus?.(e) }}
      onBlur={e => { setFocused(false); props.onBlur?.(e) }}
    />
  )
}

// ─── Component ────────────────────────────────────────────────────────────────
export default function Compose() {
  const navigate = useNavigate()
  const toast    = useToast()

  // Mode: 'message' | 'broadcast'
  const [mode,       setMode]       = useState('message')

  // Shared fields
  const [channel,    setChannel]    = useState('EMAIL')
  const [subject,    setSubject]    = useState('')
  const [body,       setBody]       = useState('')
  const [priority,   setPriority]   = useState('NORMAL')

  // Single message
  const [recipient,  setRecipient]  = useState('')

  // Broadcast
  const [bTitle,     setBTitle]     = useState('')
  const [bChannels,  setBChannels]  = useState(['EMAIL'])

  // Template
  const [templates,  setTemplates]  = useState([])
  const [tLoading,   setTLoading]   = useState(false)
  const [tSelected,  setTSelected]  = useState('')

  // Send state
  const [sending,    setSending]    = useState(false)
  const [error,      setError]      = useState(null)

  useEffect(() => {
    setTLoading(true)
    communicationsApi.listTemplates({ page_size: 50, is_active: true })
      .then(r => setTemplates(r.data.results || []))
      .catch(e => { if (import.meta.env.DEV) console.warn('[Compose] Templates failed to load:', e); toast.warning?.('Message templates unavailable — you can still compose manually') })
      .finally(() => setTLoading(false))
  }, [])

  // Fill body from template
  const handleTemplateChange = (templateId) => {
    setTSelected(templateId)
    if (!templateId) return
    const t = templates.find(t => String(t.id) === templateId)
    if (!t) return
    if (t.subject) setSubject(t.subject)
    if (t.body)    setBody(t.body)
    if (t.template_type) {
      const ch = t.template_type === 'SMS' ? 'SMS' : t.template_type === 'EMAIL' ? 'EMAIL' : channel
      setChannel(ch)
    }
  }

  const toggleBChannel = (ch) => {
    setBChannels(prev =>
      prev.includes(ch) ? prev.filter(c => c !== ch) : [...prev, ch]
    )
  }

  const canSend = mode === 'message'
    ? (recipient.trim() && body.trim() && !sending)
    : (bTitle.trim() && body.trim() && bChannels.length > 0 && !sending)

  const handleSend = async () => {
    if (!canSend) return
    setSending(true); setError(null)
    try {
      if (mode === 'message') {
        await communicationsApi.sendMessage({
          channel,
          recipient,
          subject,
          body,
          priority,
        })
        toast.success('Message queued for delivery')
      } else {
        await communicationsApi.createBroadcast({
          title: bTitle,
          channels: bChannels,
          subject,
          body_text: body,
          priority,
        })
        toast.success('Broadcast created — pending approval')
      }
      navigate('/dashboard/communications')
    } catch (err) {
      const msg = extractError(err)
      setError(msg)
      toast.error(msg)
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      <style>{`
        @keyframes cm-fadeUp {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div style={{ padding: '32px 28px', maxWidth: 720, margin: '0 auto', animation: 'cm-fadeUp 0.35s ease both' }}>

        {/* ── Eyebrow ── */}
        <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.18em', textTransform: 'uppercase', color: C.textMut, marginBottom: 6 }}>
          Communications / Compose
        </div>

        <h1 style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 32, letterSpacing: '0.04em', color: C.text, margin: '0 0 24px' }}>
          New Message
        </h1>

        {/* ── Mode toggle ── */}
        <div style={{ display: 'flex', gap: 0, marginBottom: 24, background: C.surface, border: `1px solid ${C.border}`, borderRadius: 4, overflow: 'hidden', width: 'fit-content' }}>
          {[
            { id: 'message',   label: 'Single Message' },
            { id: 'broadcast', label: 'Broadcast'      },
          ].map(m => (
            <button
              key={m.id}
              onClick={() => setMode(m.id)}
              style={{
                fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase',
                padding: '8px 20px',
                background: mode === m.id ? C.accent : 'transparent',
                color: mode === m.id ? '#fff' : C.textMut,
                border: 'none', cursor: 'pointer', transition: 'all 0.15s',
              }}
            >{m.label}</button>
          ))}
        </div>

        {/* ── Card ── */}
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 6, padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* Template picker */}
          <Field label="Quick-fill from Template">
            <select
              value={tSelected}
              onChange={e => handleTemplateChange(e.target.value)}
              disabled={tLoading}
              style={{
                ...inputStyle(false), padding: '9px 12px', cursor: 'pointer', appearance: 'auto',
                background: C.bg, color: tSelected ? C.text : C.textMut,
              }}
            >
              <option value="">{tLoading ? 'Loading templates…' : '— No template —'}</option>
              {templates.map(t => (
                <option key={t.id} value={String(t.id)}>{t.name} ({t.template_type})</option>
              ))}
            </select>
          </Field>

          {/* Mode-specific fields */}
          {mode === 'broadcast' ? (
            <>
              <Field label="Broadcast Title *">
                <FocusInput
                  value={bTitle}
                  onChange={e => setBTitle(e.target.value)}
                  placeholder="e.g. Windhoek COVID-19 Alert — March 2026"
                />
              </Field>
              <Field label="Channels *">
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {CHANNELS.map(ch => {
                    const active = bChannels.includes(ch.id)
                    return (
                      <button
                        key={ch.id}
                        onClick={() => toggleBChannel(ch.id)}
                        style={{
                          fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase',
                          padding: '6px 14px', borderRadius: 2,
                          border: `1px solid ${active ? ch.color : C.border}`,
                          background: active ? `${ch.color}18` : 'transparent',
                          color: active ? ch.color : C.textMut,
                          cursor: 'pointer', transition: 'all 0.15s',
                        }}
                      >{ch.label} {active ? '✓' : ''}</button>
                    )
                  })}
                </div>
              </Field>
            </>
          ) : (
            <>
              <Field label="Channel *">
                <div style={{ display: 'flex', gap: 8 }}>
                  {CHANNELS.map(ch => {
                    const active = channel === ch.id
                    return (
                      <button
                        key={ch.id}
                        onClick={() => setChannel(ch.id)}
                        style={{
                          fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase',
                          padding: '6px 14px', borderRadius: 2,
                          border: `1px solid ${active ? ch.color : C.border}`,
                          background: active ? `${ch.color}18` : 'transparent',
                          color: active ? ch.color : C.textMut,
                          cursor: 'pointer', transition: 'all 0.15s',
                        }}
                      >{ch.label}</button>
                    )
                  })}
                </div>
              </Field>

              <Field label="Recipient *">
                <FocusInput
                  value={recipient}
                  onChange={e => setRecipient(e.target.value)}
                  placeholder={
                    channel === 'SMS'   ? '+264 7XX XXX XXX' :
                    channel === 'EMAIL' ? 'email@example.com' :
                    'Device token or user ID'
                  }
                />
              </Field>
            </>
          )}

          {/* Subject — email only */}
          {(channel === 'EMAIL' || (mode === 'broadcast' && bChannels.includes('EMAIL'))) && (
            <Field label="Subject">
              <FocusInput
                value={subject}
                onChange={e => setSubject(e.target.value)}
                placeholder="Message subject"
              />
            </Field>
          )}

          {/* Priority */}
          <Field label="Priority">
            <div style={{ display: 'flex', gap: 8 }}>
              {PRIORITIES.map(p => {
                const active = priority === p
                const col = p === 'CRITICAL' ? C.danger : p === 'HIGH' ? C.warning : C.textMut
                return (
                  <button
                    key={p}
                    onClick={() => setPriority(p)}
                    style={{
                      fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase',
                      padding: '5px 12px', borderRadius: 2,
                      border: `1px solid ${active ? col : C.border}`,
                      background: active ? `${col}18` : 'transparent',
                      color: active ? col : C.textMut,
                      cursor: 'pointer', transition: 'all 0.15s',
                    }}
                  >{p}</button>
                )
              })}
            </div>
          </Field>

          {/* Body */}
          <Field label="Message *">
            <FocusInput
              as="textarea"
              value={body}
              onChange={e => setBody(e.target.value)}
              placeholder="Write your message here…"
              style={{ resize: 'vertical', minHeight: 140, lineHeight: 1.6 }}
            />
            <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: C.textMut, textAlign: 'right', marginTop: 4, letterSpacing: '0.1em' }}>
              {body.length} chars{channel === 'SMS' && body.length > 160 ? ` · ${Math.ceil(body.length / 160)} SMS parts` : ''}
            </div>
          </Field>

          {/* Error */}
          {error && (
            <div style={{
              background: 'rgba(239,68,68,0.08)', border: `1px solid rgba(239,68,68,0.25)`,
              borderRadius: 4, padding: '10px 14px',
              fontSize: 13, fontFamily: 'IBM Plex Sans, sans-serif', color: C.danger,
            }}>{error}</div>
          )}

          {/* Actions */}
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', paddingTop: 4 }}>
            <button
              onClick={() => navigate('/dashboard/communications')}
              style={{
                fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, fontWeight: 500,
                padding: '8px 16px', borderRadius: 4,
                border: `1px solid ${C.border}`, background: 'transparent', color: C.textSub,
                cursor: 'pointer',
              }}
            >Cancel</button>
            <button
              onClick={handleSend}
              disabled={!canSend}
              style={{
                fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, fontWeight: 500,
                padding: '8px 22px', borderRadius: 4, border: 'none',
                background: canSend ? C.accent : C.border,
                color: canSend ? '#fff' : '#4b5563',
                cursor: canSend ? 'pointer' : 'not-allowed',
                transition: 'background 0.15s', minWidth: 110,
              }}
              onMouseEnter={e => { if (canSend) e.target.style.background = '#2563eb' }}
              onMouseLeave={e => { if (canSend) e.target.style.background = C.accent }}
            >
              {sending ? 'Sending…' : mode === 'broadcast' ? 'Create Broadcast' : 'Send Message'}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}