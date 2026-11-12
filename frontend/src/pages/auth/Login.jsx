/**
 * Login — OryxShield
 * ============================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * BUGS FIXED
 * ----------
 * 1. OTPInput: `Array.from({ length: 6 }, () => useRef(null))` calls useRef
 *    inside a callback — a hook inside a loop. React tracks hooks by call
 *    order; a dynamic loop makes that count non-deterministic.
 *    FIX: declare all 6 refs individually at the top of the component, then
 *    collect them into a static array — refs always called unconditionally.
 *
 * 2. Login component: early `return <Navigate />` at line ~220 placed BEFORE
 *    two `useEffect` calls. On the render where user is already authenticated
 *    React exits at the Navigate return and never reaches the effects → hook
 *    count mismatch → crash.
 *    FIX: move ALL hooks (useState, useEffect, useCallback…) to the very top
 *    of the component, before any conditional returns.
 *
 * Both violations break the Rules of Hooks:
 *   "Don't call Hooks inside loops, conditions, or nested functions."
 *   "Don't call Hooks after an early return."
 */

import { useState, useRef, useEffect } from 'react'
import { useNavigate, useLocation, Navigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { extractError } from '../../services/api'

const C = {
  bg:          '#0a0f1e',
  surface:     '#111827',
  surfaceHigh: '#151e2e',
  border:      '#1f2937',
  accent:      '#3b82f6',
  accentHover: '#2563eb',
  danger:      '#ef4444',
  success:     '#10b981',
  text:        '#f9fafb',
  textSub:     '#9ca3af',
  textMuted:   '#6b7280',
}

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  exit:    { opacity: 0, y: -8 },
}

const METHOD_META = {
  totp:  { label: 'Authenticator App', desc: 'Enter the 6-digit code from your authenticator app.' },
  sms:   { label: 'SMS Code',          desc: 'A verification code has been sent to your registered phone number.' },
  email: { label: 'Email Code',        desc: 'A verification code has been sent to your email address.' },
}

// ─── GridBg ───────────────────────────────────────────────────────────────────
function GridBg() {
  return (
    <div style={{
      position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0,
      backgroundImage: `
        linear-gradient(rgba(59,130,246,0.018) 1px, transparent 1px),
        linear-gradient(90deg, rgba(59,130,246,0.018) 1px, transparent 1px)
      `,
      backgroundSize: '48px 48px',
    }} />
  )
}

// ─── Spinner ──────────────────────────────────────────────────────────────────
function Spinner({ size = 18, color = C.accent }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      style={{ animation: 'ls-spin 0.8s linear infinite', flexShrink: 0 }}>
      <style>{`@keyframes ls-spin { to { transform: rotate(360deg) } }`}</style>
      <circle cx="12" cy="12" r="9" stroke={color} strokeWidth="2" strokeOpacity="0.25"/>
      <path d="M12 3a9 9 0 019 9" stroke={color} strokeWidth="2" strokeLinecap="round"/>
    </svg>
  )
}

// ─── Eye icons ────────────────────────────────────────────────────────────────
function EyeIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" fill="none">
      <path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z" stroke="#6b7280" strokeWidth="1.2" strokeLinejoin="round"/>
      <circle cx="8" cy="8" r="2" stroke="#6b7280" strokeWidth="1.2"/>
    </svg>
  )
}
function EyeOffIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" fill="none">
      <path d="M1 1l14 14M6.53 6.54A2 2 0 0010.46 9.46M4.15 4.16C2.5 5.26 1 8 1 8s2.5 5 7 5a7.2 7.2 0 003.85-1.15M7 3.07A7 7 0 0115 8s-.73 1.46-2 2.73" stroke="#6b7280" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  )
}

// ─── Input ────────────────────────────────────────────────────────────────────
function Input({ label, type = 'text', value, onChange, placeholder, autoComplete, autoFocus, disabled, error, hint, ...rest }) {
  // ✅ Hooks at top, unconditional — no early returns above these
  const [focused, setFocused] = useState(false)
  const [show,    setShow]    = useState(false)
  const isPassword = type === 'password'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      {label && (
        <label style={{
          fontFamily: 'Space Mono, monospace',
          fontSize: 9, letterSpacing: '0.18em', textTransform: 'uppercase',
          color: error ? C.danger : focused ? C.accent : C.textMuted,
          transition: 'color 0.15s',
        }}>
          {label}
        </label>
      )}
      <div style={{ position: 'relative' }}>
        <input
          type={isPassword && show ? 'text' : type}
          value={value} onChange={onChange} placeholder={placeholder}
          autoComplete={autoComplete} autoFocus={autoFocus} disabled={disabled}
          onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
          style={{
            width: '100%',
            background:   focused ? C.surfaceHigh : C.surface,
            border:       `1px solid ${error ? C.danger : focused ? C.accent : C.border}`,
            borderRadius: 4,
            padding:      isPassword ? '11px 40px 11px 14px' : '11px 14px',
            color:        disabled ? C.textMuted : C.text,
            fontFamily:   'IBM Plex Sans, sans-serif', fontSize: 14,
            outline:      'none',
            transition:   'border-color 0.15s, background 0.15s',
            opacity:      disabled ? 0.6 : 1,
            cursor:       disabled ? 'not-allowed' : 'text',
            boxSizing:    'border-box',
          }}
          {...rest}
        />
        {isPassword && (
          <button
            type="button" tabIndex={-1} onClick={() => setShow((s) => !s)}
            style={{
              position: 'absolute', right: 12, top: '50%',
              transform: 'translateY(-50%)',
              background: 'none', border: 'none', cursor: 'pointer',
              padding: 2, display: 'flex', alignItems: 'center',
            }}
          >
            {show ? <EyeOffIcon /> : <EyeIcon />}
          </button>
        )}
      </div>
      {(error || hint) && (
        <p style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, color: error ? C.danger : C.textMuted, lineHeight: 1.4, margin: 0 }}>
          {error || hint}
        </p>
      )}
    </div>
  )
}

// ─── OTPInput ─────────────────────────────────────────────────────────────────
// FIX: refs declared individually at top-level — NEVER inside Array.from or
// any loop/callback. React requires hooks to be called in the same order and
// count on every render. Dynamic arrays break that guarantee.
function OTPInput({ value, onChange, disabled, error }) {
  // ✅ 6 individual refs — always called, always in the same order
  const ref0 = useRef(null)
  const ref1 = useRef(null)
  const ref2 = useRef(null)
  const ref3 = useRef(null)
  const ref4 = useRef(null)
  const ref5 = useRef(null)

  // Collect into a static array AFTER all hook calls
  const inputRefs = [ref0, ref1, ref2, ref3, ref4, ref5]

  const digits = value.split('').concat(Array(6).fill('')).slice(0, 6)

  const handleChange = (i, e) => {
    const ch   = e.target.value.replace(/\D/g, '').slice(-1)
    const next = [...digits]; next[i] = ch
    onChange(next.join(''))
    if (ch && i < 5) inputRefs[i + 1].current?.focus()
  }

  const handleKeyDown = (i, e) => {
    if (e.key === 'Backspace' && !digits[i] && i > 0) {
      const next = [...digits]; next[i - 1] = ''
      onChange(next.join('')); inputRefs[i - 1].current?.focus()
    }
    if (e.key === 'ArrowLeft'  && i > 0) inputRefs[i - 1].current?.focus()
    if (e.key === 'ArrowRight' && i < 5) inputRefs[i + 1].current?.focus()
  }

  const handlePaste = (e) => {
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    onChange(pasted.padEnd(6, '').slice(0, 6))
    inputRefs[Math.min(pasted.length, 5)].current?.focus()
    e.preventDefault()
  }

  return (
    <div style={{ display: 'flex', gap: 6 }}>
      {digits.map((d, i) => (
        <input
          key={i}
          ref={inputRefs[i]}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={d}
          onChange={(e) => handleChange(i, e)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={i === 0 ? handlePaste : undefined}
          disabled={disabled}
          style={{
            flex: '1 1 0', minWidth: 28, height: 'clamp(38px, 8vw, 52px)',
            textAlign: 'center',
            background: d ? C.surfaceHigh : C.surface,
            border: `1px solid ${error ? C.danger : d ? C.accent : C.border}`,
            borderRadius: 4, color: C.text,
            fontFamily: 'Space Mono, monospace',
            fontSize: 'clamp(14px, 4vw, 20px)', fontWeight: 700,
            outline: 'none',
            transition: 'border-color 0.15s, background 0.15s',
            opacity: disabled ? 0.5 : 1,
            cursor: disabled ? 'not-allowed' : 'text',
          }}
          onFocus={(e) => { e.target.style.borderColor = C.accent }}
          onBlur={(e)  => { e.target.style.borderColor = d ? C.accent : C.border }}
        />
      ))}
    </div>
  )
}

// ─── PrimaryBtn ───────────────────────────────────────────────────────────────
function PrimaryBtn({ children, loading, disabled, onClick, type = 'button' }) {
  const [hovered, setHovered] = useState(false)
  return (
    <button
      type={type} onClick={onClick}
      disabled={disabled || loading}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        width: '100%',
        background:   disabled || loading ? 'rgba(59,130,246,0.4)' : hovered ? C.accentHover : C.accent,
        border: 'none', borderRadius: 4, padding: '13px 24px', color: '#fff',
        fontFamily: 'Space Mono, monospace', fontSize: 10, fontWeight: 700,
        letterSpacing: '0.15em', textTransform: 'uppercase',
        cursor: disabled || loading ? 'not-allowed' : 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        transition: 'background 0.15s',
      }}
    >
      {loading && <Spinner size={14} color="#fff" />}
      {children}
    </button>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Login Page
// ─────────────────────────────────────────────────────────────────────────────
export default function Login() {
  const { user, loading, login, verify2fa, resend2fa } = useAuth()
  const { error: toastError, success: toastSuccess, info: toastInfo } = useToast()
  const navigate = useNavigate()
  const location = useLocation()

  const from = location.state?.from?.pathname || '/dashboard'

  // ── All useState calls ─────────────────────────────────────────────────────
  const [step,           setStep]           = useState('credentials')
  const [email,          setEmail]          = useState('')
  const [password,       setPassword]       = useState('')
  const [credErr,        setCredErr]        = useState({})
  const [credLoading,    setCredLoading]    = useState(false)
  const [otpCode,        setOtpCode]        = useState('')
  const [sessionToken,   setSessionToken]   = useState('')
  const [twoFaMethod,    setTwoFaMethod]    = useState('totp')
  const [twoFaLoading,   setTwoFaLoading]   = useState(false)
  const [twoFaErr,       setTwoFaErr]       = useState('')
  const [resendLoading,  setResendLoading]  = useState(false)
  const [resendCooldown, setResendCooldown] = useState(0)

  // ── All useEffect calls — MUST come before any conditional return ──────────
  // FIX: these were previously placed AFTER the `if (!loading && user) return`
  // guard at line ~220. That early return caused React to see fewer hooks on
  // authenticated renders, crashing with "Rendered fewer hooks than expected".

  // Resend OTP countdown
  useEffect(() => {
    if (resendCooldown <= 0) return
    const t = setInterval(() => setResendCooldown((c) => c - 1), 1000)
    return () => clearInterval(t)
  }, [resendCooldown])

  // Auto-submit when all 6 OTP digits are entered
  useEffect(() => {
    if (otpCode.replace(/\D/g, '').length === 6 && step === '2fa' && !twoFaLoading) {
      handle2fa()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [otpCode])

  // ── NOW it is safe to conditionally return ────────────────────────────────
  // All hooks have already been called unconditionally above this point.

  // Show loader while auth state is being resolved (token being verified)
  if (loading) {
    return (
      <div style={{
        minHeight: '100vh', background: C.bg,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexDirection: 'column', gap: 16,
      }}>
        <Spinner size={24} />
        <span style={{
          fontFamily: 'Space Mono, monospace', fontSize: 9,
          letterSpacing: '0.2em', color: C.textMuted, textTransform: 'uppercase',
        }}>
          Loading…
        </span>
      </div>
    )
  }

  // Already authenticated — redirect to intended destination
  if (user) {
    return <Navigate to={from !== '/login' ? from : '/dashboard'} replace />
  }

  // ── Handlers ─────────────────────────────────────────────────────────────────

  const validateCreds = () => {
    const e = {}
    if (!email.trim())                     e.email    = 'Email is required.'
    else if (!/\S+@\S+\.\S+/.test(email))  e.email    = 'Enter a valid email address.'
    if (!password)                         e.password = 'Password is required.'
    else if (password.length < 6)          e.password = 'Minimum 6 characters.'
    setCredErr(e)
    return !Object.keys(e).length
  }

  const handleCredentials = async (ev) => {
    ev?.preventDefault()
    if (!validateCreds()) return
    setCredLoading(true)
    try {
      const result = await login(email, password)
      if (result.requires2fa) {
        setSessionToken(result.sessionToken)
        setTwoFaMethod(result.method || 'totp')
        setStep('2fa')
        if (result.method !== 'totp') toastInfo(`Code sent via ${result.method.toUpperCase()}.`)
      } else {
        navigate(from !== '/login' ? from : '/dashboard', { replace: true })
      }
    } catch (err) {
      setCredErr({ general: extractError(err) })
    } finally {
      setCredLoading(false)
    }
  }

  const handle2fa = async (ev) => {
    ev?.preventDefault()
    const clean = otpCode.replace(/\D/g, '')
    if (clean.length < 6) { setTwoFaErr('Enter the full 6-digit code.'); return }
    setTwoFaErr(''); setTwoFaLoading(true)
    try {
      await verify2fa(clean, sessionToken)
      navigate(from !== '/login' ? from : '/dashboard', { replace: true })
    } catch (err) {
      setTwoFaErr(extractError(err)); setOtpCode('')
    } finally {
      setTwoFaLoading(false)
    }
  }

  const handleResend = async () => {
    if (resendCooldown > 0) return
    setResendLoading(true)
    try {
      await resend2fa(sessionToken)
      toastSuccess('Code resent.')
      setResendCooldown(60)
    } catch (err) {
      toastError(extractError(err))
    } finally {
      setResendLoading(false)
    }
  }

  const methodMeta = METHOD_META[twoFaMethod] || METHOD_META.totp

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div style={{
      minHeight: '100vh', background: C.bg,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '24px 16px', position: 'relative',
    }}>
      <GridBg />
      <motion.div
        initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        style={{ position: 'relative', zIndex: 1, width: '100%', maxWidth: 420 }}
      >
        {/* ── Logo ── */}
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, marginBottom: 8 }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%', background: C.success,
              boxShadow: `0 0 10px ${C.success}`, animation: 'ls-pulse 2.2s ease-in-out infinite',
            }} />
            <style>{`@keyframes ls-pulse { 0%,100%{box-shadow:0 0 6px ${C.success}} 50%{box-shadow:0 0 18px ${C.success}} }`}</style>
            <span style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 22, letterSpacing: '0.16em', color: C.text }}>
              ORYXSHIELD
            </span>
          </div>
          <p style={{
            fontFamily: 'Space Mono, monospace', fontSize: 9,
            letterSpacing: '0.2em', color: C.textMuted,
            textTransform: 'uppercase', margin: 0,
          }}>
            OryxShield Operations Platform
          </p>
        </div>

        {/* ── Card ── */}
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, overflow: 'hidden' }}>

          {/* Progress bar */}
          <div style={{ height: 3, background: C.border, position: 'relative' }}>
            <motion.div
              animate={{ width: step === 'credentials' ? '50%' : '100%' }}
              transition={{ duration: 0.4, ease: 'easeInOut' }}
              style={{
                position: 'absolute', left: 0, top: 0, height: '100%',
                background: `linear-gradient(to right, ${C.accent}, #60a5fa)`,
              }}
            />
          </div>

          <div style={{ padding: '32px 32px 36px' }}>
            <AnimatePresence mode="wait">

              {/* ── Step 1: Credentials ── */}
              {step === 'credentials' && (
                <motion.div key="creds" {...fadeUp} transition={{ duration: 0.28, ease: 'easeOut' }}>
                  <div style={{ marginBottom: 24 }}>
                    <h1 style={{
                      fontFamily: 'Bebas Neue, sans-serif', fontSize: 32,
                      letterSpacing: '0.06em', color: C.text,
                      lineHeight: 1, margin: '0 0 6px',
                    }}>
                      SIGN IN
                    </h1>
                    <p style={{
                      fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
                      color: C.textSub, lineHeight: 1.5, fontWeight: 300, margin: 0,
                    }}>
                      Access the operations platform. Authorised personnel only.
                    </p>
                  </div>

                  <AnimatePresence>
                    {credErr.general && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        style={{
                          background: 'rgba(239,68,68,0.08)',
                          border: '1px solid rgba(239,68,68,0.3)',
                          borderRadius: 4, padding: '10px 14px',
                          marginBottom: 18, display: 'flex', gap: 10,
                        }}
                      >
                        <span style={{ color: C.danger, fontSize: 12, fontFamily: 'Space Mono, monospace', fontWeight: 700, flexShrink: 0 }}>!</span>
                        <p style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: C.danger, margin: 0 }}>
                          {credErr.general}
                        </p>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <form onSubmit={handleCredentials} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                    <Input
                      label="Email Address" type="email" value={email}
                      onChange={(e) => { setEmail(e.target.value); setCredErr((p) => ({ ...p, email: '', general: '' })) }}
                      placeholder="operator@oryxshield.gov.na"
                      autoComplete="email" autoFocus
                      disabled={credLoading} error={credErr.email}
                    />
                    <Input
                      label="Password" type="password" value={password}
                      onChange={(e) => { setPassword(e.target.value); setCredErr((p) => ({ ...p, password: '', general: '' })) }}
                      placeholder="••••••••••"
                      autoComplete="current-password"
                      disabled={credLoading} error={credErr.password}
                    />
                    <div style={{ marginTop: 4 }}>
                      <PrimaryBtn type="submit" loading={credLoading}>
                        {credLoading ? 'Authenticating…' : 'Sign In →'}
                      </PrimaryBtn>
                    </div>
                  </form>

                  <p style={{
                    fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11,
                    color: C.textMuted, lineHeight: 1.6, fontWeight: 300,
                    textAlign: 'center', marginTop: 16, marginBottom: 0,
                  }}>
                    Forgot your password?{' '}
                    <a href="/reset-password" style={{ color: C.accent, textDecoration: 'none' }}>Reset it here</a>
                  </p>
                  <p style={{
                    fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11,
                    color: C.textMuted, lineHeight: 1.6, fontWeight: 300,
                    textAlign: 'center', marginTop: 8, marginBottom: 0,
                  }}>
                    All access is monitored, logged, and audited. Unauthorised access is prohibited.
                  </p>
                </motion.div>
              )}

              {/* ── Step 2: 2FA ── */}
              {step === '2fa' && (
                <motion.div key="2fa" {...fadeUp} transition={{ duration: 0.28, ease: 'easeOut' }}>
                  <button
                    onClick={() => { setStep('credentials'); setOtpCode(''); setTwoFaErr('') }}
                    style={{
                      background: 'none', border: 'none', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: 6,
                      marginBottom: 20, padding: 0,
                      color: C.textMuted, fontFamily: 'Space Mono, monospace',
                      fontSize: 9, letterSpacing: '0.15em', textTransform: 'uppercase',
                    }}
                  >
                    ← Back
                  </button>

                  <div style={{ marginBottom: 24 }}>
                    <div style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)',
                      borderRadius: 2, padding: '3px 10px', marginBottom: 14,
                    }}>
                      <div style={{ width: 5, height: 5, borderRadius: '50%', background: C.accent }} />
                      <span style={{
                        fontFamily: 'Space Mono, monospace', fontSize: 8,
                        letterSpacing: '0.18em', color: C.accent, textTransform: 'uppercase',
                      }}>
                        {methodMeta.label}
                      </span>
                    </div>
                    <h1 style={{
                      fontFamily: 'Bebas Neue, sans-serif', fontSize: 28,
                      letterSpacing: '0.06em', color: C.text,
                      lineHeight: 1, margin: '0 0 8px',
                    }}>
                      TWO-FACTOR<br />VERIFICATION
                    </h1>
                    <p style={{
                      fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
                      color: C.textSub, lineHeight: 1.55, fontWeight: 300, margin: 0,
                    }}>
                      {methodMeta.desc}
                    </p>
                  </div>

                  <form onSubmit={handle2fa} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                    <div>
                      <div style={{
                        fontFamily: 'Space Mono, monospace', fontSize: 9,
                        letterSpacing: '0.18em', textTransform: 'uppercase',
                        color: twoFaErr ? C.danger : C.textMuted, marginBottom: 8,
                      }}>
                        Verification Code
                      </div>
                      <OTPInput
                        value={otpCode}
                        onChange={setOtpCode}
                        disabled={twoFaLoading}
                        error={!!twoFaErr}
                      />
                      <AnimatePresence>
                        {twoFaErr && (
                          <motion.p
                            initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                            style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, color: C.danger, marginTop: 6, marginBottom: 0 }}
                          >
                            {twoFaErr}
                          </motion.p>
                        )}
                      </AnimatePresence>
                    </div>
                    <PrimaryBtn
                      type="submit"
                      loading={twoFaLoading}
                      disabled={otpCode.replace(/\D/g, '').length < 6}
                    >
                      {twoFaLoading ? 'Verifying…' : 'Verify & Continue →'}
                    </PrimaryBtn>
                  </form>

                  {twoFaMethod !== 'totp' && (
                    <div style={{ marginTop: 20, textAlign: 'center' }}>
                      <button
                        onClick={handleResend}
                        disabled={resendCooldown > 0 || resendLoading}
                        style={{
                          background: 'none', border: 'none',
                          cursor: resendCooldown > 0 || resendLoading ? 'not-allowed' : 'pointer',
                          fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12,
                          color: resendCooldown > 0 ? C.textMuted : C.accent,
                          display: 'inline-flex', alignItems: 'center', gap: 6,
                          opacity: resendCooldown > 0 ? 0.6 : 1,
                        }}
                      >
                        {resendLoading && <Spinner size={12} />}
                        {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend code'}
                      </button>
                    </div>
                  )}

                  {twoFaMethod === 'totp' && (
                    <p style={{
                      fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11,
                      color: C.textMuted, textAlign: 'center',
                      marginTop: 20, lineHeight: 1.6, fontWeight: 300, marginBottom: 0,
                    }}>
                      Lost access to your authenticator? Contact your system administrator.
                    </p>
                  )}
                </motion.div>
              )}

            </AnimatePresence>
          </div>
        </div>

        <p style={{
          fontFamily: 'Space Mono, monospace', fontSize: 8,
          letterSpacing: '0.14em', color: C.textMuted,
          textTransform: 'uppercase', textAlign: 'center', marginTop: 20,
        }}>
          © 2026 OryxShield · IHR 2005 Aligned · All access monitored
        </p>
      </motion.div>
    </div>
  )
}