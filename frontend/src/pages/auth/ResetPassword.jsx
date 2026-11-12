/**
 * ResetPassword — OryxShield
 * =====================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Two-step password reset flow:
 *   Step 1: /reset-password           → user enters email → POST /auth/password/reset/
 *   Step 2: /reset-password/confirm   → user enters token + new password → POST /auth/password/reset/confirm/
 *
 * The confirm page reads ?token=xxx from the URL query string (emailed link).
 */

import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { authApi, extractError } from '../../services/api'
import { useToast } from '../../context/ToastContext'

const C = {
  bg:         '#0a0f1e',
  surface:    '#111827',
  border:     '#1f2937',
  accent:     '#3b82f6',
  accentBg:   'rgba(59,130,246,0.08)',
  danger:     '#ef4444',
  success:    '#10b981',
  text:       '#f9fafb',
  textSub:    '#9ca3af',
  textMuted:  '#6b7280',
}

const inputStyle = {
  width: '100%',
  padding: '11px 14px',
  background: '#0d1526',
  border: `1px solid ${C.border}`,
  borderRadius: 8,
  color: C.text,
  fontSize: 14,
  outline: 'none',
  boxSizing: 'border-box',
}

// ─── Request form ─────────────────────────────────────────────────────────────
function RequestReset() {
  const { success: toastSuccess } = useToast()
  const [email, setEmail]   = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent]     = useState(false)
  const [error, setError]   = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!email.trim()) { setError('Please enter your email address.'); return }
    setError('')
    setLoading(true)
    try {
      await authApi.resetPasswordRequest({ email })
      setSent(true)
      toastSuccess('Password reset link sent. Check your email.')
    } catch (err) {
      setError(extractError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
      {sent ? (
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📧</div>
          <h2 style={{ color: C.text, margin: '0 0 8px', fontSize: 20 }}>Check your email</h2>
          <p style={{ color: C.textSub, margin: '0 0 24px', fontSize: 14, lineHeight: 1.6 }}>
            We've sent a password reset link to <strong style={{ color: C.text }}>{email}</strong>.
            Follow the link in the email to set a new password.
          </p>
          <p style={{ fontSize: 13, color: C.textMuted }}>
            Didn't receive it?{' '}
            <button onClick={() => setSent(false)} style={{ background: 'none', border: 'none', color: C.accent, cursor: 'pointer', fontSize: 13 }}>
              Try again
            </button>
          </p>
        </div>
      ) : (
        <form onSubmit={handleSubmit}>
          <h2 style={{ color: C.text, margin: '0 0 6px', fontSize: 20, fontWeight: 700 }}>Reset your password</h2>
          <p style={{ color: C.textSub, margin: '0 0 24px', fontSize: 13 }}>
            Enter your registered email and we'll send you a reset link.
          </p>

          {error && (
            <div style={{ padding: '10px 14px', background: 'rgba(239,68,68,0.1)', border: `1px solid rgba(239,68,68,0.3)`, borderRadius: 8, color: C.danger, fontSize: 13, marginBottom: 16 }}>
              {error}
            </div>
          )}

          <label style={{ display: 'block', fontSize: 12, color: C.textMuted, marginBottom: 6 }}>Email address</label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
            style={{ ...inputStyle, marginBottom: 20 }}
          />

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%', padding: '11px', borderRadius: 8,
              background: loading ? '#1d4ed8' : C.accent,
              border: 'none', color: '#fff', fontSize: 14, fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1, transition: 'opacity 0.15s',
            }}
          >
            {loading ? 'Sending…' : 'Send Reset Link'}
          </button>

          <p style={{ textAlign: 'center', marginTop: 20, fontSize: 13, color: C.textMuted }}>
            Remember your password?{' '}
            <Link to="/login" style={{ color: C.accent, textDecoration: 'none' }}>Sign in</Link>
          </p>
        </form>
      )}
    </motion.div>
  )
}

// ─── Confirm form ─────────────────────────────────────────────────────────────
function ConfirmReset() {
  const { success: toastSuccess } = useToast()
  const [searchParams] = useSearchParams()
  const [token, setToken]           = useState(searchParams.get('token') || '')
  const [uid, setUid]               = useState(searchParams.get('uid') || '')
  const [password, setPassword]     = useState('')
  const [confirm, setConfirm]       = useState('')
  const [loading, setLoading]       = useState(false)
  const [done, setDone]             = useState(false)
  const [error, setError]           = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (password !== confirm) { setError('Passwords do not match.'); return }
    if (password.length < 8)  { setError('Password must be at least 8 characters.'); return }
    setError('')
    setLoading(true)
    try {
      await authApi.resetPasswordConfirm({ token, uid, new_password: password })
      setDone(true)
      toastSuccess('Password changed successfully.')
    } catch (err) {
      setError(extractError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
      {done ? (
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>✅</div>
          <h2 style={{ color: C.text, margin: '0 0 8px', fontSize: 20 }}>Password updated</h2>
          <p style={{ color: C.textSub, margin: '0 0 24px', fontSize: 14 }}>
            Your password has been changed. You can now sign in with your new password.
          </p>
          <Link to="/login" style={{
            display: 'inline-block', padding: '10px 28px', borderRadius: 8,
            background: C.accent, color: '#fff', textDecoration: 'none',
            fontWeight: 600, fontSize: 14,
          }}>Go to Sign In</Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit}>
          <h2 style={{ color: C.text, margin: '0 0 6px', fontSize: 20, fontWeight: 700 }}>Set new password</h2>
          <p style={{ color: C.textSub, margin: '0 0 24px', fontSize: 13 }}>
            Enter your new password below.
          </p>

          {error && (
            <div style={{ padding: '10px 14px', background: 'rgba(239,68,68,0.1)', border: `1px solid rgba(239,68,68,0.3)`, borderRadius: 8, color: C.danger, fontSize: 13, marginBottom: 16 }}>
              {error}
            </div>
          )}

          {!searchParams.get('token') && (
            <>
              <label style={{ display: 'block', fontSize: 12, color: C.textMuted, marginBottom: 6 }}>Reset token</label>
              <input value={token} onChange={e => setToken(e.target.value)} placeholder="Paste reset token from email" style={{ ...inputStyle, marginBottom: 14 }} />
              <label style={{ display: 'block', fontSize: 12, color: C.textMuted, marginBottom: 6 }}>UID</label>
              <input value={uid} onChange={e => setUid(e.target.value)} placeholder="UID from email link" style={{ ...inputStyle, marginBottom: 14 }} />
            </>
          )}

          <label style={{ display: 'block', fontSize: 12, color: C.textMuted, marginBottom: 6 }}>New password</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Min. 8 characters" required style={{ ...inputStyle, marginBottom: 14 }} />

          <label style={{ display: 'block', fontSize: 12, color: C.textMuted, marginBottom: 6 }}>Confirm password</label>
          <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="Repeat new password" required style={{ ...inputStyle, marginBottom: 20 }} />

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%', padding: '11px', borderRadius: 8,
              background: loading ? '#1d4ed8' : C.accent,
              border: 'none', color: '#fff', fontSize: 14, fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? 'Saving…' : 'Set New Password'}
          </button>
        </form>
      )}
    </motion.div>
  )
}

// ─── Page wrapper ─────────────────────────────────────────────────────────────
export default function ResetPassword({ confirm = false }) {
  return (
    <div style={{
      minHeight: '100vh',
      background: C.bg,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 20,
    }}>
      <div style={{
        width: '100%',
        maxWidth: 420,
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderRadius: 14,
        padding: '36px 32px',
      }}>
        <div style={{ marginBottom: 28, textAlign: 'center' }}>
          <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 20, letterSpacing: '0.16em', color: C.text }}>ORYXSHIELD</div>
          <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, letterSpacing: '0.14em', color: C.textMuted }}>PROTOCOL</div>
        </div>

        {confirm ? <ConfirmReset /> : <RequestReset />}
      </div>
    </div>
  )
}
