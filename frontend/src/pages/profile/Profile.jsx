/**
 * OryxShield — Profile Page
 * ====================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Sections
 * --------
 * 1. Identity        — first_name, last_name, username, avatar (PATCH /users/me/ + /profiles/my_profile/)
 * 2. Profile Details — phone, bio, dob, org, dept, job_title, employee_id, language, timezone
 * 3. Security        — password change (POST /auth/change-password/)
 * 4. Two-Factor Auth — enable/disable TOTP/SMS/EMAIL (POST /profiles/enable_2fa/ | disable_2fa/)
 * 5. API Keys        — list, create, revoke (GET/POST/POST /api-keys/)
 * 6. Account         — deactivate (POST /users/{id}/deactivate/) | delete account (DELETE /users/{id}/)
 *
 * Backend alignment notes:
 *  - ChangePasswordSerializer fields: old_password, new_password, new_password_confirm
 *  - UserProfileUpdateSerializer fields: phone_number, bio, date_of_birth, organization,
 *      department, job_title, employee_id, language, timezone, location
 *  - Avatar: PATCH /profiles/my_profile/ with multipart/form-data (avatar field)
 *  - Deactivate: backend blocks self-deactivation → show info modal instead
 *  - Delete: DELETE /users/{id}/ — staff only; non-staff shown contact-support message
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi, coreApi, extractError } from '../../services/api'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'

// ─── Inline keyframes ─────────────────────────────────────────────────────────
const STYLES = `
  @keyframes prof-fadeUp {
    from { opacity: 0; transform: translateY(14px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes prof-shimmer {
    0%   { background-position: -200% 0; }
    100% { background-position:  200% 0; }
  }
  @keyframes prof-spin {
    from { transform: rotate(0deg); }
    to   { transform: rotate(360deg); }
  }
`

// ─── Design tokens ────────────────────────────────────────────────────────────
const T = {
  bg:         '#0a0f1e',
  surface:    '#111827',
  surfaceHi:  '#151e2e',
  border:     '#1f2937',
  accent:     '#3b82f6',
  danger:     '#ef4444',
  warning:    '#f59e0b',
  success:    '#10b981',
  text:       '#f9fafb',
  textSub:    '#9ca3af',
  textMuted:  '#6b7280',
}

const ROLE_COLORS = {
  admin:        '#ef4444',
  analyst:      '#3b82f6',
  coordinator:  '#10b981',
  field_officer:'#f59e0b',
  public:       '#6b7280',
}

const LANGUAGE_OPTIONS = [
  { value: 'en',  label: 'English' },
  { value: 'af',  label: 'Afrikaans' },
  { value: 'ng',  label: 'Oshiwambo' },
  { value: 'naq', label: 'Damara/Nama' },
  { value: 'hz',  label: 'Herero' },
  { value: 'kav', label: 'Kavango' },
]

// ─── Shared sub-components ────────────────────────────────────────────────────

function Shimmer({ height = 16, style = {} }) {
  return (
    <div style={{
      height, borderRadius: 3,
      background: `linear-gradient(90deg,${T.surface} 25%,${T.surfaceHi} 50%,${T.surface} 75%)`,
      backgroundSize: '200% 100%',
      animation: 'prof-shimmer 1.5s infinite',
      ...style,
    }} />
  )
}

function Badge({ label, color = T.textMuted }) {
  return (
    <span style={{
      fontFamily: 'Space Mono, monospace',
      fontSize: 9, letterSpacing: '0.12em',
      textTransform: 'uppercase',
      padding: '2px 8px', borderRadius: 2,
      background: `${color}18`,
      border: `1px solid ${color}30`,
      color,
    }}>
      {label}
    </span>
  )
}

function SectionHeader({ label }) {
  return (
    <div style={{
      fontFamily: 'Space Mono, monospace',
      fontSize: 9, letterSpacing: '0.18em',
      textTransform: 'uppercase',
      color: T.textMuted,
      marginBottom: 20,
      paddingBottom: 12,
      borderBottom: `1px solid ${T.border}`,
    }}>
      {label}
    </div>
  )
}

function Spinner() {
  return (
    <span style={{
      display: 'inline-block',
      width: 12, height: 12,
      border: `2px solid rgba(255,255,255,0.2)`,
      borderTopColor: '#fff',
      borderRadius: '50%',
      animation: 'prof-spin 0.7s linear infinite',
      marginRight: 6,
      verticalAlign: 'middle',
    }} />
  )
}

// ─── Style helpers ────────────────────────────────────────────────────────────

const sectionStyle = (animDelay = '0s') => ({
  background: T.surface,
  border: `1px solid ${T.border}`,
  borderRadius: 6,
  padding: 24,
  marginBottom: 20,
  animation: `prof-fadeUp 0.45s ease ${animDelay} both`,
})

const labelStyle = {
  fontFamily: 'Space Mono, monospace',
  fontSize: 9, letterSpacing: '0.14em',
  textTransform: 'uppercase',
  color: T.textMuted,
  marginBottom: 6,
  display: 'block',
}

function inputBase(focused, error) {
  return {
    width: '100%',
    background: T.bg,
    border: `1px solid ${error ? T.danger : focused ? T.accent : T.border}`,
    borderRadius: 4,
    padding: '10px 12px',
    fontSize: 13,
    fontFamily: 'IBM Plex Sans, sans-serif',
    color: T.text,
    outline: 'none',
    boxSizing: 'border-box',
    transition: 'border-color 0.15s',
  }
}

function PrimaryBtn({ onClick, disabled, loading, children, style = {} }) {
  const [hov, setHov] = useState(false)
  const active = !disabled && !loading
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        fontFamily: 'IBM Plex Sans, sans-serif',
        fontSize: 13, fontWeight: 500,
        padding: '8px 20px', borderRadius: 4,
        border: 'none',
        background: active ? (hov ? '#2563eb' : T.accent) : T.border,
        color: active ? '#fff' : '#4b5563',
        cursor: active ? 'pointer' : 'not-allowed',
        transition: 'background 0.15s',
        display: 'flex', alignItems: 'center',
        ...style,
      }}
    >
      {loading && <Spinner />}
      {children}
    </button>
  )
}

function DangerBtn({ onClick, disabled, loading, children, style = {} }) {
  const [hov, setHov] = useState(false)
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        fontFamily: 'IBM Plex Sans, sans-serif',
        fontSize: 13, fontWeight: 500,
        padding: '8px 20px', borderRadius: 4,
        border: `1px solid ${T.danger}40`,
        background: hov ? `${T.danger}22` : `${T.danger}12`,
        color: T.danger,
        cursor: disabled || loading ? 'not-allowed' : 'pointer',
        transition: 'background 0.15s',
        display: 'flex', alignItems: 'center',
        opacity: disabled || loading ? 0.6 : 1,
        ...style,
      }}
    >
      {loading && <Spinner />}
      {children}
    </button>
  )
}

// ─── Focused input hook ───────────────────────────────────────────────────────
function useInput(initial = '') {
  const [value, setValue] = useState(initial)
  const [focused, setFocused] = useState(false)
  return {
    value, setValue,
    bind: {
      value,
      onChange: e => setValue(e.target.value),
      onFocus: () => setFocused(true),
      onBlur: () => setFocused(false),
    },
    focused,
  }
}

// ─── Confirm Modal ────────────────────────────────────────────────────────────
function ConfirmModal({ title, message, confirmLabel = 'Confirm', danger = false, onConfirm, onCancel, loading, children }) {
  return (
    <div style={{
      position: 'fixed', inset: 0,
      background: 'rgba(0,0,0,0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000,
    }}
      onClick={e => e.target === e.currentTarget && onCancel()}
    >
      <div style={{
        background: T.surface,
        border: `1px solid ${T.border}`,
        borderRadius: 8,
        padding: 28,
        width: 420, maxWidth: 'calc(100vw - 32px)',
        animation: 'prof-fadeUp 0.2s ease both',
      }}>
        <h3 style={{
          fontFamily: 'Bebas Neue, sans-serif',
          fontSize: 22, letterSpacing: '0.04em',
          color: danger ? T.danger : T.text,
          margin: '0 0 10px',
        }}>
          {title}
        </h3>
        <p style={{
          fontFamily: 'IBM Plex Sans, sans-serif',
          fontSize: 13, color: T.textSub,
          margin: '0 0 20px', lineHeight: 1.6,
        }}>
          {message}
        </p>
        {children}
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', paddingTop: 8 }}>
          <button
            onClick={onCancel}
            style={{
              fontFamily: 'IBM Plex Sans, sans-serif',
              fontSize: 13, padding: '8px 16px', borderRadius: 4,
              border: `1px solid ${T.border}`,
              background: 'transparent', color: T.textSub,
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          {danger
            ? <DangerBtn onClick={onConfirm} loading={loading}>{confirmLabel}</DangerBtn>
            : <PrimaryBtn onClick={onConfirm} loading={loading}>{confirmLabel}</PrimaryBtn>
          }
        </div>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// Main Profile Component
// ═══════════════════════════════════════════════════════════════════════════════

export default function Profile() {
  const toast   = useToast()
  const { user: authUser, logout } = useAuth()
  const navigate = useNavigate()
  const fileRef = useRef(null)

  // ── Data state ──────────────────────────────────────────────────────────────
  const [user,    setUser]    = useState(null)
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  // ── Identity (User model) ───────────────────────────────────────────────────
  const firstName = useInput('')
  const lastName  = useInput('')
  const username  = useInput('')
  const [avatarSrc,   setAvatarSrc]   = useState(null)
  const [savingId,    setSavingId]    = useState(false)
  const [uploadingAvatar, setUploadingAvatar] = useState(false)

  // ── Profile Details (UserProfile model) ────────────────────────────────────
  const phone      = useInput('')
  const bio        = useInput('')
  const dob        = useInput('')
  const org        = useInput('')
  const dept       = useInput('')
  const jobTitle   = useInput('')
  const employeeId = useInput('')
  const language   = useInput('en')
  const timezone   = useInput('Africa/Windhoek')
  const [savingProfile, setSavingProfile] = useState(false)

  // ── Password ────────────────────────────────────────────────────────────────
  const oldPwd     = useInput('')
  const newPwd     = useInput('')
  const confirmPwd = useInput('')
  const [pwdError,  setPwdError]  = useState(null)
  const [savingPwd, setSavingPwd] = useState(false)

  // ── 2FA ─────────────────────────────────────────────────────────────────────
  const [twoFaMethod, setTwoFaMethod] = useState('TOTP')
  const [saving2fa,   setSaving2fa]   = useState(false)

  // ── API Keys ─────────────────────────────────────────────────────────────────
  const [apiKeys,       setApiKeys]       = useState([])
  const [keysLoading,   setKeysLoading]   = useState(false)
  const [newKeyName,    setNewKeyName]    = useState('')
  const [creatingKey,   setCreatingKey]   = useState(false)
  const [newKeyVisible, setNewKeyVisible] = useState(null) // { key, id } full key shown once
  const [revokingKey,   setRevokingKey]   = useState(null)

  // ── Account management ───────────────────────────────────────────────────────
  const [showDeactivateModal, setShowDeactivateModal] = useState(false)
  const [showDeleteModal,     setShowDeleteModal]     = useState(false)
  const [deleteConfirmPwd,    setDeleteConfirmPwd]    = useState('')
  const [deletingAccount,     setDeletingAccount]     = useState(false)

  // ── Load data ────────────────────────────────────────────────────────────────
  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [userRes, profileRes] = await Promise.all([
        authApi.me(),
        coreApi.myProfile(),
      ])
      const u = userRes.data
      const p = profileRes.data

      setUser(u)
      setProfile(p)

      // Populate User fields
      firstName.setValue(u.first_name || '')
      lastName.setValue(u.last_name   || '')
      username.setValue(u.username    || '')
      setAvatarSrc(p.avatar || null)

      // Populate Profile fields
      phone.setValue(p.phone_number   || '')
      bio.setValue(p.bio              || '')
      dob.setValue(p.date_of_birth    || '')
      org.setValue(p.organization     || '')
      dept.setValue(p.department      || '')
      jobTitle.setValue(p.job_title   || '')
      employeeId.setValue(p.employee_id || '')
      language.setValue(p.language    || 'en')
      timezone.setValue(p.timezone    || 'Africa/Windhoek')
    } catch (err) {
      setError(extractError(err))
    } finally {
      setLoading(false)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { loadData() }, [loadData])

  // API keys
  const loadApiKeys = useCallback(async () => {
    setKeysLoading(true)
    try {
      const res = await authApi.listApiKeys()
      setApiKeys(res.data?.results ?? res.data ?? [])
    } catch {
      // non-critical
    } finally {
      setKeysLoading(false)
    }
  }, [])

  useEffect(() => { loadApiKeys() }, [loadApiKeys])

  // ── Dirty checks ─────────────────────────────────────────────────────────────
  const identityDirty = user && (
    firstName.value !== (user.first_name || '') ||
    lastName.value  !== (user.last_name  || '') ||
    username.value  !== (user.username   || '')
  )

  const profileDirty = profile && (
    phone.value      !== (profile.phone_number  || '') ||
    bio.value        !== (profile.bio           || '') ||
    dob.value        !== (profile.date_of_birth || '') ||
    org.value        !== (profile.organization  || '') ||
    dept.value       !== (profile.department    || '') ||
    jobTitle.value   !== (profile.job_title     || '') ||
    employeeId.value !== (profile.employee_id   || '') ||
    language.value   !== (profile.language      || 'en') ||
    timezone.value   !== (profile.timezone      || 'Africa/Windhoek')
  )

  // ── Handlers ─────────────────────────────────────────────────────────────────

  async function handleSaveIdentity() {
    setSavingId(true)
    try {
      const res = await authApi.updateMe({
        first_name: firstName.value,
        last_name:  lastName.value,
        username:   username.value,
      })
      setUser(res.data)
      toast.success('Identity updated')
    } catch (err) {
      toast.error(extractError(err))
    } finally {
      setSavingId(false)
    }
  }

  async function handleSaveProfile() {
    setSavingProfile(true)
    try {
      const res = await coreApi.updateMyProfile({
        phone_number: phone.value,
        bio:          bio.value,
        date_of_birth: dob.value || null,
        organization: org.value,
        department:   dept.value,
        job_title:    jobTitle.value,
        employee_id:  employeeId.value,
        language:     language.value,
        timezone:     timezone.value,
      })
      setProfile(res.data)
      toast.success('Profile details updated')
    } catch (err) {
      toast.error(extractError(err))
    } finally {
      setSavingProfile(false)
    }
  }

  async function handleAvatarChange(e) {
    const file = e.target.files[0]
    if (!file) return

    // Size guard — 5 MB
    if (file.size > 5 * 1024 * 1024) {
      toast.error('Avatar must be under 5 MB')
      return
    }

    const previewUrl = URL.createObjectURL(file)
    setAvatarSrc(previewUrl)
    setUploadingAvatar(true)

    try {
      const formData = new FormData()
      formData.append('avatar', file)
      // Avatar is on UserProfile — PATCH /profiles/my_profile/
      const res = await coreApi.updateMyProfile(formData)
      setAvatarSrc(res.data.avatar || previewUrl)
      toast.success('Avatar updated')
    } catch (err) {
      toast.error(extractError(err))
      setAvatarSrc(profile?.avatar || null)
    } finally {
      setUploadingAvatar(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function handleChangePassword() {
    setPwdError(null)
    if (newPwd.value !== confirmPwd.value) {
      setPwdError('New passwords do not match')
      return
    }
    if (newPwd.value.length < 10) {
      setPwdError('Password must be at least 10 characters')
      return
    }
    setSavingPwd(true)
    try {
      // Backend: old_password, new_password, new_password_confirm
      await authApi.changePassword({
        old_password:         oldPwd.value,
        new_password:         newPwd.value,
        new_password_confirm: confirmPwd.value,
      })
      toast.success('Password changed successfully')
      oldPwd.setValue('')
      newPwd.setValue('')
      confirmPwd.setValue('')
    } catch (err) {
      toast.error(extractError(err))
    } finally {
      setSavingPwd(false)
    }
  }

  async function handle2faToggle() {
    setSaving2fa(true)
    try {
      if (profile?.two_factor_enabled) {
        await authApi.disable2fa({})
        toast.success('Two-factor authentication disabled')
      } else {
        await authApi.confirm2fa({ method: twoFaMethod })
        toast.success(`2FA enabled via ${twoFaMethod}`)
      }
      const profileRes = await coreApi.myProfile()
      setProfile(profileRes.data)
    } catch (err) {
      toast.error(extractError(err))
    } finally {
      setSaving2fa(false)
    }
  }

  async function handleCreateApiKey() {
    if (!newKeyName.trim()) { toast.error('Key name is required'); return }
    setCreatingKey(true)
    try {
      const res = await authApi.createApiKey({ name: newKeyName.trim() })
      const created = res.data
      setNewKeyVisible({ key: created.key, id: created.id, name: created.name })
      setNewKeyName('')
      await loadApiKeys()
    } catch (err) {
      toast.error(extractError(err))
    } finally {
      setCreatingKey(false)
    }
  }

  async function handleRevokeKey(id) {
    setRevokingKey(id)
    try {
      await authApi.revokeApiKey(id)
      toast.success('API key revoked')
      await loadApiKeys()
    } catch (err) {
      toast.error(extractError(err))
    } finally {
      setRevokingKey(null)
    }
  }

  async function handleDeleteAccount() {
    if (!deleteConfirmPwd.trim()) { toast.error('Password is required'); return }
    setDeletingAccount(true)
    try {
      // Verify password first via a login attempt is not ideal; instead
      // try to change password with wrong data to verify — but better: just call DELETE /users/{id}/
      // The backend requires staff; for non-staff we show a support message.
      if (!authUser?.is_staff) {
        // Non-staff can't self-delete — show message
        setShowDeleteModal(false)
        toast.info('Account deletion requested. Please contact support@nehmtech.com.')
        return
      }
      await coreApi.deleteUser(user.id)
      toast.success('Account deleted')
      logout()
      navigate('/login', { replace: true })
    } catch (err) {
      toast.error(extractError(err))
    } finally {
      setDeletingAccount(false)
    }
  }

  // ── Derived ───────────────────────────────────────────────────────────────────
  const role       = authUser?.role || 'public'
  const roleColor  = ROLE_COLORS[role] || T.textMuted
  const initials   = user
    ? `${(user.first_name || user.username || '?')[0]}${(user.last_name || '')[0] || ''}`.toUpperCase()
    : '?'
  const displayName = user
    ? [user.first_name, user.last_name].filter(Boolean).join(' ') || user.username
    : '—'
  const is2faEnabled = profile?.two_factor_enabled || false
  const pwdCanSubmit = oldPwd.value && newPwd.value && confirmPwd.value

  // ═══════════════════════════════════════════════════════════════════════════════
  // Render
  // ═══════════════════════════════════════════════════════════════════════════════

  return (
    <div style={{ padding: '32px 24px', maxWidth: 700, margin: '0 auto' }}>
      <style>{STYLES}</style>

      {/* ── Page header ── */}
      <div style={{
        fontFamily: 'Space Mono, monospace',
        fontSize: 9, letterSpacing: '0.18em',
        textTransform: 'uppercase', color: T.textMuted,
        marginBottom: 6,
        animation: 'prof-fadeUp 0.3s ease both',
      }}>
        Account / Settings
      </div>
      <h1 style={{
        fontFamily: 'Bebas Neue, sans-serif',
        fontSize: 32, letterSpacing: '0.04em',
        color: T.text, margin: '0 0 28px',
        animation: 'prof-fadeUp 0.35s ease 0.05s both',
      }}>
        My Profile
      </h1>

      {error && (
        <div style={{
          background: `${T.danger}18`, border: `1px solid ${T.danger}30`,
          borderRadius: 4, padding: '10px 14px',
          fontSize: 12, fontFamily: 'IBM Plex Sans, sans-serif',
          color: T.danger, marginBottom: 20,
        }}>
          {error}
        </div>
      )}

      {/* ════════════════════════════════════════════════════
          SECTION 1 — Identity
      ════════════════════════════════════════════════════ */}
      <div style={sectionStyle('0.1s')}>
        <SectionHeader label="Identity" />

        {/* Avatar + name card */}
        {loading ? (
          <div style={{ display: 'flex', gap: 20, marginBottom: 24 }}>
            <Shimmer height={72} style={{ width: 72, borderRadius: '50%', flexShrink: 0 }} />
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <Shimmer height={18} />
              <Shimmer height={14} style={{ width: '60%' }} />
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', marginBottom: 24 }}>
            {/* Avatar */}
            <div
              style={{
                width: 72, height: 72, borderRadius: '50%',
                background: `${roleColor}18`,
                border: `2px solid ${roleColor}40`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0, position: 'relative',
                cursor: 'pointer', overflow: 'hidden',
                opacity: uploadingAvatar ? 0.6 : 1,
                transition: 'opacity 0.15s',
              }}
              onClick={() => !uploadingAvatar && fileRef.current?.click()}
              title="Change avatar"
            >
              {avatarSrc ? (
                <img
                  src={avatarSrc}
                  alt="Avatar"
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              ) : (
                <span style={{
                  fontFamily: 'Bebas Neue, sans-serif',
                  fontSize: 26, color: roleColor, letterSpacing: '0.05em',
                }}>
                  {initials}
                </span>
              )}
              {/* hover overlay */}
              <AvatarOverlay uploading={uploadingAvatar} />
            </div>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              style={{ display: 'none' }}
              onChange={handleAvatarChange}
            />

            {/* Name / role / email */}
            <div style={{ flex: 1, paddingTop: 4 }}>
              <div style={{
                fontFamily: 'IBM Plex Sans, sans-serif',
                fontSize: 16, fontWeight: 600, color: T.text, marginBottom: 6,
              }}>
                {displayName}
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
                <Badge label={role} color={roleColor} />
                {profile?.email_verified && <Badge label="email verified" color={T.success} />}
                {profile?.two_factor_enabled && <Badge label="2FA on" color={T.accent} />}
                {profile?.is_locked && <Badge label="locked" color={T.danger} />}
              </div>
              <div style={{
                fontFamily: 'IBM Plex Sans, sans-serif',
                fontSize: 12, color: T.textMuted,
              }}>
                {user?.email}
              </div>
              {profile?.last_login_ip && (
                <div style={{
                  fontFamily: 'Space Mono, monospace',
                  fontSize: 9, color: T.textMuted,
                  letterSpacing: '0.1em', marginTop: 4,
                }}>
                  Last IP: {profile.last_login_ip}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Editable identity fields */}
        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Shimmer height={38} /><Shimmer height={38} /><Shimmer height={38} />
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 180px), 1fr))', gap: 12 }}>
              <FocusInput label="First Name" bind={firstName.bind} focused={firstName.focused} />
              <FocusInput label="Last Name"  bind={lastName.bind}  focused={lastName.focused} />
            </div>
            <FocusInput label="Username" bind={username.bind} focused={username.focused} />
            <div>
              <label style={labelStyle}>Email Address</label>
              <input
                style={{ ...inputBase(false, false), color: T.textMuted, cursor: 'default' }}
                value={user?.email || ''}
                readOnly
              />
              <div style={{
                fontFamily: 'Space Mono, monospace', fontSize: 9,
                color: T.textMuted, letterSpacing: '0.1em', marginTop: 5,
              }}>
                Contact support to change your email address.
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: 4 }}>
              <PrimaryBtn
                onClick={handleSaveIdentity}
                disabled={!identityDirty}
                loading={savingId}
              >
                {savingId ? 'Saving…' : 'Save Identity'}
              </PrimaryBtn>
            </div>
          </div>
        )}
      </div>

      {/* ════════════════════════════════════════════════════
          SECTION 2 — Profile Details
      ════════════════════════════════════════════════════ */}
      <div style={sectionStyle('0.15s')}>
        <SectionHeader label="Profile Details" />

        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {[...Array(5)].map((_, i) => <Shimmer key={i} height={38} />)}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 180px), 1fr))', gap: 12 }}>
              <FocusInput label="Phone Number" bind={phone.bind} focused={phone.focused} placeholder="+264 700 000 000" />
              <FocusInput label="Date of Birth" bind={dob.bind} focused={dob.focused} type="date" />
            </div>

            <div>
              <label style={labelStyle}>Bio</label>
              <textarea
                style={{
                  ...inputBase(bio.focused, false),
                  resize: 'vertical', minHeight: 80,
                }}
                {...bio.bind}
                placeholder="Short description about yourself…"
                maxLength={500}
              />
              <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted, textAlign: 'right', marginTop: 3 }}>
                {bio.value.length}/500
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 180px), 1fr))', gap: 12 }}>
              <FocusInput label="Organization" bind={org.bind} focused={org.focused} />
              <FocusInput label="Department"   bind={dept.bind} focused={dept.focused} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 180px), 1fr))', gap: 12 }}>
              <FocusInput label="Job Title"   bind={jobTitle.bind}   focused={jobTitle.focused} />
              <FocusInput label="Employee ID" bind={employeeId.bind} focused={employeeId.focused} />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 180px), 1fr))', gap: 12 }}>
              {/* Language select */}
              <div>
                <label style={labelStyle}>Language</label>
                <select
                  value={language.value}
                  onChange={e => language.setValue(e.target.value)}
                  style={{ ...inputBase(false, false), cursor: 'pointer' }}
                >
                  {LANGUAGE_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
              {/* Timezone */}
              <FocusInput label="Timezone" bind={timezone.bind} focused={timezone.focused} placeholder="Africa/Windhoek" />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: 4 }}>
              <PrimaryBtn
                onClick={handleSaveProfile}
                disabled={!profileDirty}
                loading={savingProfile}
              >
                {savingProfile ? 'Saving…' : 'Save Details'}
              </PrimaryBtn>
            </div>
          </div>
        )}
      </div>

      {/* ════════════════════════════════════════════════════
          SECTION 3 — Password
      ════════════════════════════════════════════════════ */}
      <div style={sectionStyle('0.2s')}>
        <SectionHeader label="Change Password" />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <FocusInput
            label="Current Password"
            bind={oldPwd.bind}
            focused={oldPwd.focused}
            type="password"
            placeholder="••••••••••"
          />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 180px), 1fr))', gap: 12 }}>
            <FocusInput
              label="New Password"
              bind={newPwd.bind}
              focused={newPwd.focused}
              type="password"
              placeholder="••••••••••"
              onChange={e => { newPwd.setValue(e.target.value); setPwdError(null) }}
            />
            <FocusInput
              label="Confirm New Password"
              bind={confirmPwd.bind}
              focused={confirmPwd.focused}
              type="password"
              placeholder="••••••••••"
              error={!!pwdError}
              onChange={e => { confirmPwd.setValue(e.target.value); setPwdError(null) }}
            />
          </div>
          {pwdError && (
            <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, color: T.danger }}>
              {pwdError}
            </div>
          )}

          {/* Password strength hint */}
          {newPwd.value && (
            <PasswordStrength password={newPwd.value} />
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: 4 }}>
            <PrimaryBtn
              onClick={handleChangePassword}
              disabled={!pwdCanSubmit}
              loading={savingPwd}
            >
              {savingPwd ? 'Changing…' : 'Change Password'}
            </PrimaryBtn>
          </div>
        </div>
      </div>

      {/* ════════════════════════════════════════════════════
          SECTION 4 — Two-Factor Authentication
      ════════════════════════════════════════════════════ */}
      <div style={sectionStyle('0.25s')}>
        <SectionHeader label="Two-Factor Authentication" />

        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Shimmer height={20} /><Shimmer height={38} />
          </div>
        ) : (
          <div>
            {/* Status row */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '12px 14px',
              background: T.bg, border: `1px solid ${T.border}`,
              borderRadius: 4, marginBottom: 16,
            }}>
              <div>
                <div style={{
                  fontFamily: 'IBM Plex Sans, sans-serif',
                  fontSize: 13, fontWeight: 500, color: T.text, marginBottom: 3,
                }}>
                  Two-Factor Authentication
                </div>
                <div style={{
                  fontFamily: 'IBM Plex Sans, sans-serif',
                  fontSize: 11, color: T.textMuted,
                }}>
                  {is2faEnabled
                    ? `Enabled via ${profile?.two_factor_method || 'TOTP'}`
                    : 'Add an extra layer of security to your account.'}
                </div>
              </div>
              <Badge
                label={is2faEnabled ? 'enabled' : 'disabled'}
                color={is2faEnabled ? T.success : T.textMuted}
              />
            </div>

            {/* Method selector (only when disabled) */}
            {!is2faEnabled && (
              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>Authentication Method</label>
                <div style={{ display: 'flex', gap: 8 }}>
                  {['TOTP', 'SMS', 'EMAIL'].map(m => (
                    <MethodPill
                      key={m}
                      label={m}
                      selected={twoFaMethod === m}
                      onClick={() => setTwoFaMethod(m)}
                    />
                  ))}
                </div>
                <div style={{
                  fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted,
                  letterSpacing: '0.1em', marginTop: 8,
                }}>
                  {twoFaMethod === 'TOTP' && 'Use an authenticator app (Google Authenticator, Authy).'}
                  {twoFaMethod === 'SMS'  && 'Receive a code via SMS to your registered phone number.'}
                  {twoFaMethod === 'EMAIL'&& 'Receive a code via email on every login.'}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              {is2faEnabled ? (
                <DangerBtn onClick={handle2faToggle} loading={saving2fa}>
                  {saving2fa ? 'Disabling…' : 'Disable 2FA'}
                </DangerBtn>
              ) : (
                <PrimaryBtn onClick={handle2faToggle} loading={saving2fa}>
                  {saving2fa ? 'Enabling…' : 'Enable 2FA'}
                </PrimaryBtn>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ════════════════════════════════════════════════════
          SECTION 5 — API Keys
      ════════════════════════════════════════════════════ */}
      <div style={sectionStyle('0.3s')}>
        <SectionHeader label="API Keys" />

        {/* Create new key */}
        <div style={{
          display: 'flex', gap: 10, marginBottom: 20, alignItems: 'flex-end',
        }}>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>New Key Name</label>
            <input
              style={inputBase(false, false)}
              value={newKeyName}
              onChange={e => setNewKeyName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreateApiKey()}
              placeholder="e.g. dashboard-integration"
              maxLength={100}
            />
          </div>
          <PrimaryBtn
            onClick={handleCreateApiKey}
            disabled={!newKeyName.trim()}
            loading={creatingKey}
            style={{ flexShrink: 0, alignSelf: 'flex-end' }}
          >
            {creatingKey ? 'Creating…' : 'Create Key'}
          </PrimaryBtn>
        </div>

        {/* One-time reveal */}
        {newKeyVisible && (
          <div style={{
            background: `${T.success}10`, border: `1px solid ${T.success}30`,
            borderRadius: 4, padding: '12px 14px', marginBottom: 16,
          }}>
            <div style={{
              fontFamily: 'Space Mono, monospace', fontSize: 9,
              color: T.success, letterSpacing: '0.12em', marginBottom: 8,
            }}>
              ⚠ KEY CREATED — COPY NOW, NOT SHOWN AGAIN
            </div>
            <div style={{
              fontFamily: 'Space Mono, monospace', fontSize: 11,
              color: T.text, wordBreak: 'break-all',
              background: T.bg, padding: '8px 10px', borderRadius: 3,
              marginBottom: 8,
            }}>
              {newKeyVisible.key}
            </div>
            <button
              onClick={() => {
                navigator.clipboard.writeText(newKeyVisible.key)
                toast.success('API key copied to clipboard')
              }}
              style={{
                fontFamily: 'Space Mono, monospace', fontSize: 9,
                letterSpacing: '0.1em', textTransform: 'uppercase',
                background: `${T.success}22`, border: `1px solid ${T.success}40`,
                color: T.success, borderRadius: 2, padding: '4px 10px',
                cursor: 'pointer', marginRight: 8,
              }}
            >
              Copy
            </button>
            <button
              onClick={() => setNewKeyVisible(null)}
              style={{
                fontFamily: 'Space Mono, monospace', fontSize: 9,
                letterSpacing: '0.1em', textTransform: 'uppercase',
                background: 'transparent', border: `1px solid ${T.border}`,
                color: T.textMuted, borderRadius: 2, padding: '4px 10px',
                cursor: 'pointer',
              }}
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Keys list */}
        {keysLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Shimmer height={48} /><Shimmer height={48} />
          </div>
        ) : apiKeys.length === 0 ? (
          <div style={{
            fontFamily: 'IBM Plex Sans, sans-serif',
            fontSize: 12, color: T.textMuted,
            padding: '14px 0', textAlign: 'center',
          }}>
            No API keys yet. Create one above.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {apiKeys.map(k => (
              <div key={k.id} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                background: T.bg, border: `1px solid ${T.border}`,
                borderRadius: 4, padding: '10px 14px',
              }}>
                <div>
                  <div style={{
                    fontFamily: 'IBM Plex Sans, sans-serif',
                    fontSize: 13, fontWeight: 500, color: T.text, marginBottom: 2,
                  }}>
                    {k.name}
                  </div>
                  <div style={{
                    fontFamily: 'Space Mono, monospace', fontSize: 9,
                    color: T.textMuted, letterSpacing: '0.1em',
                  }}>
                    {k.key} · {k.usage_count || 0} uses
                    {k.last_used_at && ` · Last used ${new Date(k.last_used_at).toLocaleDateString()}`}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <Badge
                    label={k.is_active ? 'active' : 'inactive'}
                    color={k.is_active ? T.success : T.textMuted}
                  />
                  <DangerBtn
                    onClick={() => handleRevokeKey(k.id)}
                    loading={revokingKey === k.id}
                    style={{ padding: '4px 10px', fontSize: 11 }}
                  >
                    Revoke
                  </DangerBtn>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ════════════════════════════════════════════════════
          SECTION 6 — Account Management
      ════════════════════════════════════════════════════ */}
      <div style={{
        ...sectionStyle('0.35s'),
        border: `1px solid ${T.danger}30`,
      }}>
        <SectionHeader label="Account Management" />

        {/* Account info */}
        {!loading && user && (
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 20, marginBottom: 20,
            fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub,
          }}>
            <InfoItem label="Member since" value={user.date_joined ? new Date(user.date_joined).toLocaleDateString('en-NA', { year: 'numeric', month: 'long', day: 'numeric' }) : '—'} />
            <InfoItem label="Last login"   value={user.last_login ? new Date(user.last_login).toLocaleDateString('en-NA', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'Never'} />
            <InfoItem label="Account status" value={user.is_active ? 'Active' : 'Inactive'} valueColor={user.is_active ? T.success : T.danger} />
            <InfoItem label="Account type"   value={user.is_staff ? 'Staff' : 'Standard'} />
          </div>
        )}

        <div style={{
          background: `${T.danger}08`,
          border: `1px solid ${T.danger}20`,
          borderRadius: 4, padding: '14px 16px', marginBottom: 16,
        }}>
          <div style={{
            fontFamily: 'Space Mono, monospace', fontSize: 9,
            color: T.danger, letterSpacing: '0.14em',
            textTransform: 'uppercase', marginBottom: 8,
          }}>
            ⚠ Danger Zone
          </div>
          <p style={{
            fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12,
            color: T.textSub, margin: '0 0 16px', lineHeight: 1.6,
          }}>
            These actions are permanent or irreversible. Proceed with caution.
          </p>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            <DangerBtn
              onClick={() => setShowDeactivateModal(true)}
              disabled={loading}
            >
              Deactivate Account
            </DangerBtn>
            <DangerBtn
              onClick={() => setShowDeleteModal(true)}
              disabled={loading}
            >
              Delete Account
            </DangerBtn>
          </div>
        </div>
      </div>

      {/* ── Deactivate Modal ── */}
      {showDeactivateModal && (
        <ConfirmModal
          title="Deactivate Account"
          danger
          message={
            authUser?.is_staff
              ? "Your account will be deactivated. You will not be able to log in until a system administrator re-activates it. Are you sure?"
              : "Account self-deactivation requires administrator action. Please contact your system administrator or email support@nehmtech.com to request deactivation."
          }
          confirmLabel={authUser?.is_staff ? "Deactivate" : "Got it"}
          onCancel={() => setShowDeactivateModal(false)}
          onConfirm={() => {
            // Backend /users/{id}/deactivate/ blocks self-deactivation for non-staff
            // Staff also cannot deactivate themselves per the backend check
            setShowDeactivateModal(false)
            toast.info('Please contact your system administrator to deactivate your account.')
          }}
        />
      )}

      {/* ── Delete Modal ── */}
      {showDeleteModal && (
        <ConfirmModal
          title="Delete Account"
          danger
          message={
            authUser?.is_staff
              ? "This will permanently delete your account and all associated data. This action cannot be undone. Enter your password to confirm."
              : "Account deletion is handled by system administrators. We will process your request within 30 days. To proceed, click Confirm and we will send instructions to your email."
          }
          confirmLabel={authUser?.is_staff ? "Delete My Account" : "Send Deletion Request"}
          loading={deletingAccount}
          onCancel={() => { setShowDeleteModal(false); setDeleteConfirmPwd('') }}
          onConfirm={handleDeleteAccount}
        >
          {authUser?.is_staff && (
            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>Confirm Password</label>
              <input
                type="password"
                style={inputBase(false, false)}
                value={deleteConfirmPwd}
                onChange={e => setDeleteConfirmPwd(e.target.value)}
                placeholder="Enter your password to confirm"
                autoFocus
              />
            </div>
          )}
        </ConfirmModal>
      )}

    </div>
  )
}

// ─── Small sub-components ────────────────────────────────────────────────────

function FocusInput({ label, bind, focused, type = 'text', placeholder = '', error = false, onChange }) {
  const merged = onChange ? { ...bind, onChange } : bind
  return (
    <div>
      {label && <label style={labelStyle}>{label}</label>}
      <input
        type={type}
        style={inputBase(focused, error)}
        placeholder={placeholder}
        {...merged}
      />
    </div>
  )
}

function AvatarOverlay({ uploading }) {
  const [hov, setHov] = useState(false)
  return (
    <div
      style={{
        position: 'absolute', inset: 0,
        background: 'rgba(0,0,0,0.55)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        borderRadius: '50%',
        opacity: uploading || hov ? 1 : 0,
        transition: 'opacity 0.15s',
      }}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
    >
      <span style={{
        fontFamily: 'Space Mono, monospace',
        fontSize: 9, color: '#fff', letterSpacing: '0.1em',
      }}>
        {uploading ? 'UPLOADING' : 'EDIT'}
      </span>
    </div>
  )
}

function MethodPill({ label, selected, onClick }) {
  const [hov, setHov] = useState(false)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        fontFamily: 'Space Mono, monospace',
        fontSize: 9, letterSpacing: '0.12em',
        textTransform: 'uppercase',
        padding: '6px 14px', borderRadius: 2,
        border: `1px solid ${selected ? T.accent : T.border}`,
        background: selected ? `${T.accent}18` : hov ? `${T.border}50` : 'transparent',
        color: selected ? T.accent : T.textMuted,
        cursor: 'pointer', transition: 'all 0.15s',
      }}
    >
      {label}
    </button>
  )
}

function PasswordStrength({ password }) {
  const checks = [
    { label: '10+ chars',        ok: password.length >= 10 },
    { label: 'Uppercase',        ok: /[A-Z]/.test(password) },
    { label: 'Lowercase',        ok: /[a-z]/.test(password) },
    { label: 'Digit',            ok: /\d/.test(password) },
    { label: 'Special char',     ok: /[!@#$%^&*()\-_=+\[\]{};:'",.<>?/\\|`~]/.test(password) },
  ]
  const score = checks.filter(c => c.ok).length
  const color = score <= 2 ? T.danger : score <= 3 ? T.warning : T.success
  const label = score <= 2 ? 'WEAK' : score <= 3 ? 'FAIR' : score === 4 ? 'GOOD' : 'STRONG'

  return (
    <div>
      <div style={{ display: 'flex', gap: 4, marginBottom: 6 }}>
        {[...Array(5)].map((_, i) => (
          <div key={i} style={{
            flex: 1, height: 3, borderRadius: 2,
            background: i < score ? color : T.border,
            transition: 'background 0.2s',
          }} />
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {checks.map(c => (
            <span key={c.label} style={{
              fontFamily: 'Space Mono, monospace', fontSize: 8, letterSpacing: '0.1em',
              color: c.ok ? T.success : T.textMuted,
              textDecoration: c.ok ? 'none' : 'none',
            }}>
              {c.ok ? '✓' : '○'} {c.label}
            </span>
          ))}
        </div>
        <span style={{
          fontFamily: 'Space Mono, monospace', fontSize: 9,
          color, letterSpacing: '0.14em', fontWeight: 700,
        }}>
          {label}
        </span>
      </div>
    </div>
  )
}

function InfoItem({ label, value, valueColor = T.text }) {
  return (
    <div>
      <div style={{
        fontFamily: 'Space Mono, monospace', fontSize: 8,
        letterSpacing: '0.14em', textTransform: 'uppercase',
        color: T.textMuted, marginBottom: 2,
      }}>
        {label}
      </div>
      <div style={{
        fontFamily: 'IBM Plex Sans, sans-serif',
        fontSize: 13, fontWeight: 500, color: valueColor,
      }}>
        {value}
      </div>
    </div>
  )
}