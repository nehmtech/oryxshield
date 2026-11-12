import { useState } from 'react'
import { Link } from 'react-router-dom'
import { communicationsApi, extractError } from '../../services/api'

const T = {
  bg: '#0a0f1e', surface: '#111827', surfaceHigh: '#151e2e',
  border: '#1f2937', accent: '#3b82f6', success: '#10b981',
  warning: '#f59e0b', danger: '#ef4444', text: '#f9fafb', textSub: '#9ca3af',
}
const FONTS = {
  heading: "'Bebas Neue', sans-serif",
  mono:    "'Space Mono', monospace",
  body:    "'IBM Plex Sans', sans-serif",
}

// Matches backend FeedbackResponse.FEEDBACK_TYPES choices
const FEEDBACK_TYPES = [
  { value: 'INQUIRY',      label: 'General Inquiry'         },
  { value: 'REQUEST',      label: 'Request for Information' },
  { value: 'COMPLAINT',    label: 'Complaint'               },
  { value: 'SUGGESTION',   label: 'Suggestion'              },
  { value: 'REPORT',       label: 'Incident Report'         },
  { value: 'APPRECIATION', label: 'Appreciation'            },
]

const CONTACTS = [
  { label: 'General Enquiries', value: 'info@oryxshield.gov.na',       icon: '✉' },
  { label: 'Technical Support', value: 'support@oryxshield.gov.na',    icon: '⊙' },
  { label: 'Emergency Line',    value: '+264 61 203 2720',                    icon: '⚡' },
  { label: 'Location',          value: 'Ministry of Health, Harvey Street, Windhoek', icon: '◉' },
]

const EMPTY_FORM = {
  feedback_type:  'INQUIRY',
  sender_name:    '',
  sender_contact: '',   // backend field — accepts email or phone
  organisation:   '',   // optional, sent in metadata
  subject:        '',
  message:        '',
}

// Per-field validation
function validate(form) {
  const errors = {}
  if (!form.sender_name.trim())    errors.sender_name    = 'Your name is required.'
  if (!form.sender_contact.trim()) errors.sender_contact = 'Email or phone is required.'
  else if (
    !form.sender_contact.includes('@') &&
    !/^\+?[\d\s\-]{7,}$/.test(form.sender_contact)
  ) errors.sender_contact = 'Enter a valid email or phone number.'
  if (!form.subject.trim())        errors.subject        = 'A subject is required.'
  if (!form.message.trim())        errors.message        = 'Message cannot be empty.'
  else if (form.message.trim().length < 10) errors.message = 'Please provide more detail (min 10 chars).'
  return errors
}

function Field({ label, error, required, children }) {
  return (
    <div style={{ marginBottom: error ? 12 : 18 }}>
      <label style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: error ? T.danger : T.textSub, display: 'block', marginBottom: 6 }}>
        {label}{required && <span style={{ color: T.danger }}> *</span>}
      </label>
      {children}
      {error && (
        <div style={{ fontFamily: FONTS.body, fontSize: 11, color: T.danger, marginTop: 4 }}>{error}</div>
      )}
    </div>
  )
}

const inputBase = (hasError) => ({
  width: '100%', background: T.surfaceHigh,
  border: `1px solid ${hasError ? T.danger : T.border}`, borderRadius: 3,
  padding: '10px 14px', color: T.text,
  fontFamily: FONTS.body, fontSize: 13, outline: 'none',
  boxSizing: 'border-box', transition: 'border-color 0.15s',
})

export default function Contact() {
  const [form,      setForm]      = useState(EMPTY_FORM)
  const [errors,    setErrors]    = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [submitted,  setSubmitted]  = useState(false)
  const [apiError,   setApiError]   = useState(null)
  const [submitHov,  setSubmitHov]  = useState(false)

  const set = (k, v) => {
    setForm(f => ({ ...f, [k]: v }))
    // Clear field error on change
    if (errors[k]) setErrors(e => { const n = { ...e }; delete n[k]; return n })
  }

  const handleSubmit = async () => {
    const errs = validate(form)
    if (Object.keys(errs).length) { setErrors(errs); return }

    setSubmitting(true)
    setApiError(null)
    try {
      // Build payload exactly matching FeedbackResponse model fields
      const payload = {
        feedback_type:  form.feedback_type,
        sender_name:    form.sender_name.trim(),
        sender_contact: form.sender_contact.trim(),
        subject:        form.subject.trim(),
        message:        form.message.trim(),
        // Pass organisation in metadata if provided
        ...(form.organisation.trim() ? {
          metadata: { organisation: form.organisation.trim() },
        } : {}),
      }
      await communicationsApi.submitFeedback(payload)
      setSubmitted(true)
    } catch (err) {
      setApiError(extractError(err))
    } finally {
      setSubmitting(false)
    }
  }

  const handleReset = () => {
    setForm(EMPTY_FORM)
    setErrors({})
    setApiError(null)
    setSubmitted(false)
  }

  return (
    <>
      <style>{`
        @keyframes ct-fadeUp { from{opacity:0;transform:translateY(16px)} to{opacity:1;transform:translateY(0)} }
        .ct-input:focus { border-color: #3b82f6 !important; }
        @media (max-width: 800px) {
          .ct-grid { grid-template-columns: 1fr !important; }
          .ct-form-row { grid-template-columns: 1fr !important; }
        }
      `}</style>

      <div style={{ maxWidth: 1160, margin: '0 auto', padding: '80px 24px 96px', animation: 'ct-fadeUp 0.4s ease' }}>
        {/* Header */}
        <div style={{ marginBottom: 56 }}>
          <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.18em', textTransform: 'uppercase', color: T.textSub, marginBottom: 10 }}>
            Get In Touch
          </div>
          <h1 style={{ fontFamily: FONTS.heading, fontSize: 'clamp(44px, 6vw, 72px)', color: T.text, margin: 0, letterSpacing: '0.03em', lineHeight: 1 }}>
            CONTACT US
          </h1>
        </div>

        <div className="ct-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1.7fr', gap: 56, alignItems: 'start' }}>

          {/* ── Left: contact info ── */}
          <div>
            <p style={{ fontFamily: FONTS.body, fontSize: 14, color: T.textSub, lineHeight: 1.8, margin: '0 0 36px' }}>
              For platform access, technical support, or inter-agency coordination enquiries, reach us through any of the channels below or submit the form.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {CONTACTS.map((c, i) => (
                <div key={i} style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: 3, flexShrink: 0,
                    background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: T.accent, fontSize: 14,
                  }}>{c.icon}</div>
                  <div>
                    <div style={{ fontFamily: FONTS.mono, fontSize: 8, letterSpacing: '0.14em', textTransform: 'uppercase', color: T.textSub, marginBottom: 3 }}>{c.label}</div>
                    <div style={{ fontFamily: FONTS.body, fontSize: 13, color: T.text }}>{c.value}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Response time note */}
            <div style={{
              marginTop: 32, background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)',
              borderRadius: 4, padding: '12px 16px',
            }}>
              <div style={{ fontFamily: FONTS.mono, fontSize: 8, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.success, marginBottom: 4 }}>Response Time</div>
              <p style={{ fontFamily: FONTS.body, fontSize: 12, color: T.textSub, margin: 0, lineHeight: 1.65 }}>
                We aim to respond to all enquiries within one business day. Emergency reports are escalated immediately.
              </p>
            </div>
          </div>

          {/* ── Right: form ── */}
          <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '32px 28px' }}>
            {submitted ? (
              // Success state
              <div style={{ textAlign: 'center', padding: '48px 0' }}>
                <div style={{
                  width: 56, height: 56, borderRadius: '50%', margin: '0 auto 20px',
                  background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 24, color: T.success,
                }}>✓</div>
                <div style={{ fontFamily: FONTS.heading, fontSize: 28, color: T.text, letterSpacing: '0.04em', marginBottom: 12 }}>MESSAGE SENT</div>
                <p style={{ fontFamily: FONTS.body, fontSize: 13, color: T.textSub, lineHeight: 1.7, marginBottom: 28 }}>
                  Thank you. Your {form.feedback_type.toLowerCase()} has been received with status <strong style={{ color: T.text }}>RECEIVED</strong> and will be reviewed by our team within one business day.
                </p>
                <button onClick={handleReset} style={{
                  fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase',
                  padding: '9px 20px', borderRadius: 3, background: 'transparent',
                  border: `1px solid ${T.border}`, color: T.textSub, cursor: 'pointer',
                }}>Send Another</button>
              </div>
            ) : (
              <>
                <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.16em', textTransform: 'uppercase', color: T.textSub, marginBottom: 24, paddingBottom: 16, borderBottom: `1px solid ${T.border}` }}>
                  Submit Feedback / Enquiry
                </div>

                {/* API-level error */}
                {apiError && (
                  <div style={{
                    background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.28)',
                    borderRadius: 3, padding: '10px 14px', color: '#f87171',
                    fontFamily: FONTS.body, fontSize: 12, marginBottom: 20, lineHeight: 1.5,
                  }}>{apiError}</div>
                )}

                {/* Feedback type */}
                <Field label="Type" required>
                  <select
                    value={form.feedback_type}
                    onChange={e => set('feedback_type', e.target.value)}
                    className="ct-input"
                    style={{ ...inputBase(false), appearance: 'none', cursor: 'pointer' }}
                  >
                    {FEEDBACK_TYPES.map(ft => (
                      <option key={ft.value} value={ft.value}>{ft.label}</option>
                    ))}
                  </select>
                </Field>

                {/* Name + Contact */}
                <div className="ct-form-row" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                  <Field label="Full Name" required error={errors.sender_name}>
                    <input
                      className="ct-input"
                      value={form.sender_name}
                      onChange={e => set('sender_name', e.target.value)}
                      placeholder="Jane Mwangi"
                      style={inputBase(!!errors.sender_name)}
                    />
                  </Field>
                  <Field label="Email or Phone" required error={errors.sender_contact}>
                    <input
                      className="ct-input"
                      value={form.sender_contact}
                      onChange={e => set('sender_contact', e.target.value)}
                      placeholder="jane@health.gov.na or +264..."
                      style={inputBase(!!errors.sender_contact)}
                    />
                  </Field>
                </div>

                {/* Organisation + Subject */}
                <div className="ct-form-row" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                  <Field label="Organisation (optional)">
                    <input
                      className="ct-input"
                      value={form.organisation}
                      onChange={e => set('organisation', e.target.value)}
                      placeholder="Regional Health Dept."
                      style={inputBase(false)}
                    />
                  </Field>
                  <Field label="Subject" required error={errors.subject}>
                    <input
                      className="ct-input"
                      value={form.subject}
                      onChange={e => set('subject', e.target.value)}
                      placeholder="Platform access request"
                      style={inputBase(!!errors.subject)}
                    />
                  </Field>
                </div>

                {/* Message */}
                <Field label="Message" required error={errors.message}>
                  <textarea
                    className="ct-input"
                    value={form.message}
                    onChange={e => set('message', e.target.value)}
                    rows={5}
                    placeholder="Describe your enquiry in detail…"
                    style={{ ...inputBase(!!errors.message), resize: 'vertical', lineHeight: 1.6 }}
                  />
                </Field>

                {/* Urgent flag for REPORT and COMPLAINT */}
                {(form.feedback_type === 'REPORT' || form.feedback_type === 'COMPLAINT') && (
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    marginBottom: 20, padding: '10px 14px',
                    background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 3,
                  }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: T.warning }} />
                    <span style={{ fontFamily: FONTS.body, fontSize: 12, color: T.textSub, lineHeight: 1.5 }}>
                      {form.feedback_type === 'REPORT'
                        ? 'Incident reports are escalated to the surveillance team within 1 hour.'
                        : 'Complaints are reviewed by the supervisor within one business day.'}
                    </span>
                  </div>
                )}

                <button
                  onClick={handleSubmit}
                  disabled={submitting}
                  onMouseEnter={() => setSubmitHov(true)}
                  onMouseLeave={() => setSubmitHov(false)}
                  style={{
                    width: '100%', fontFamily: FONTS.mono, fontSize: 10, letterSpacing: '0.12em',
                    textTransform: 'uppercase', padding: '12px 0', borderRadius: 3,
                    background: submitting ? T.border : (submitHov ? '#2563eb' : T.accent),
                    border: 'none', color: '#fff', cursor: submitting ? 'not-allowed' : 'pointer',
                    fontWeight: 600, transition: 'background 0.15s',
                  }}
                >
                  {submitting ? 'Submitting…' : 'Submit'}
                </button>

                <p style={{ fontFamily: FONTS.body, fontSize: 11, color: T.textSub, textAlign: 'center', marginTop: 12, lineHeight: 1.6 }}>
                  By submitting you agree to our{' '}
                  <Link to="/privacy" style={{ color: T.accent, textDecoration: 'none' }}>Privacy Policy</Link>.
                  Your contact details are only used to respond to your enquiry.
                </p>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  )
}