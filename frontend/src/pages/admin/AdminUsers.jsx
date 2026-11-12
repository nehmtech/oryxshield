/**
 * AdminUsers — OryxShield
 * ==================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * API alignment
 * -------------
 * GET  /users/?page=&page_size=&search= → coreApi.listUsers(params)
 * GET  /users/{id}/                     → coreApi.getUser(id)
 * POST /users/                          → coreApi.createUser(data)
 * PATCH /users/{id}/                    → coreApi.updateUser(id, data)
 * DELETE /users/{id}/                   → coreApi.deleteUser(id)
 * POST /users/{id}/activate/            → coreApi.activateUser(id)
 * POST /users/{id}/deactivate/          → coreApi.deactivateUser(id)
 * GET  /users/statistics/               → coreApi.userStatistics()
 *
 * Backend notes
 * -------------
 * - UserDetailSerializer returns: id, username, email, first_name, last_name,
 *   full_name, is_active, is_staff, date_joined, last_login, profile{}
 * - NO "role" field on User model — role is DERIVED:
 *     is_superuser || is_staff → "admin"; else "public" (no role in DB)
 * - Role promotion = toggling is_staff via PATCH /users/{id}/
 * - Activate/deactivate use dedicated action endpoints, not PATCH is_active
 * - UserViewSet: non-staff queryset only returns own record; staff sees all
 * - deactivate endpoint blocks self-deactivation (returns 400)
 * - UserCreateSerializer fields: username, email, password, password_confirm,
 *   first_name, last_name
 * - CustomPagination response: { count, total_pages, current_page, page_size, next, previous, results }
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { coreApi, extractError } from '../../services/api'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'

// ─── Keyframes ────────────────────────────────────────────────────────────────
const STYLES = `
  @keyframes au-fadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes au-shimmer {
    0%   { background-position: -200% 0; }
    100% { background-position: 200% 0; }
  }
  @keyframes au-spin {
    from { transform: rotate(0deg); }
    to   { transform: rotate(360deg); }
  }
  .au-row:hover td { background: rgba(255,255,255,0.018) !important; }
`

// ─── Design tokens ─────────────────────────────────────────────────────────────
const T = {
  bg:        '#0a0f1e',
  surface:   '#111827',
  surfaceHi: '#151e2e',
  border:    '#1f2937',
  accent:    '#3b82f6',
  danger:    '#ef4444',
  warning:   '#f59e0b',
  success:   '#10b981',
  text:      '#f9fafb',
  textSub:   '#9ca3af',
  textMuted: '#6b7280',
}

// Role derivation: is_superuser/is_staff → admin; groups array → specific role; fallback → public
function deriveRole(user) {
  if (!user) return 'public'
  if (user.is_superuser || user.is_staff) return 'admin'
  const groups = Array.isArray(user.groups) ? user.groups.map(g =>
    typeof g === 'string' ? g.toLowerCase() : (g.name || '').toLowerCase()
  ) : []
  if (groups.includes('analyst'))       return 'analyst'
  if (groups.includes('coordinator'))   return 'coordinator'
  if (groups.includes('field_officer')) return 'field_officer'
  if (groups.includes('field officer')) return 'field_officer'
  return 'public'
}

const ALL_ROLES = ['admin', 'analyst', 'coordinator', 'field_officer', 'public']

const ROLE_CONFIG = {
  admin:         { bg: 'rgba(239,68,68,0.15)',    border: 'rgba(239,68,68,0.3)',    text: '#f87171' },
  analyst:       { bg: 'rgba(59,130,246,0.15)',   border: 'rgba(59,130,246,0.3)',   text: '#60a5fa' },
  coordinator:   { bg: 'rgba(139,92,246,0.15)',   border: 'rgba(139,92,246,0.3)',   text: '#a78bfa' },
  field_officer: { bg: 'rgba(245,158,11,0.15)',   border: 'rgba(245,158,11,0.3)',   text: '#fbbf24' },
  public:        { bg: 'rgba(107,114,128,0.15)',  border: 'rgba(107,114,128,0.3)',  text: '#9ca3af' },
}

const STATUS_CONFIG = {
  active:   { bg: 'rgba(16,185,129,0.15)',  border: 'rgba(16,185,129,0.3)',  text: '#34d399' },
  inactive: { bg: 'rgba(107,114,128,0.15)', border: 'rgba(107,114,128,0.3)', text: '#9ca3af' },
}

const PAGE_SIZE = 20

// ─── Shared helpers ───────────────────────────────────────────────────────────

function Badge({ label, config }) {
  return (
    <span style={{
      fontFamily: 'Space Mono, monospace',
      fontSize: 9, letterSpacing: '0.12em',
      textTransform: 'uppercase', padding: '2px 8px',
      borderRadius: 2,
      background: config.bg,
      border: `1px solid ${config.border}`,
      color: config.text,
      whiteSpace: 'nowrap',
    }}>
      {label}
    </span>
  )
}

function Spinner({ size = 12, color = T.textMuted }) {
  return (
    <span style={{
      display: 'inline-block', width: size, height: size,
      border: `2px solid rgba(255,255,255,0.1)`,
      borderTopColor: color,
      borderRadius: '50%',
      animation: 'au-spin 0.7s linear infinite',
      flexShrink: 0,
    }} />
  )
}

function Shimmer({ height = 14, style = {} }) {
  return (
    <div style={{
      height, borderRadius: 2,
      background: `linear-gradient(90deg,${T.surface} 25%,${T.surfaceHi} 50%,${T.surface} 75%)`,
      backgroundSize: '200% 100%',
      animation: 'au-shimmer 1.5s infinite',
      ...style,
    }} />
  )
}

// ─── Table shimmer rows ───────────────────────────────────────────────────────

function ShimmerRows() {
  return Array.from({ length: 8 }).map((_, i) => (
    <tr key={i}>
      {[60, 80, 45, 40, 50, 50].map((w, j) => (
        <td key={j} style={{ padding: '13px 16px', borderBottom: `1px solid ${T.border}` }}>
          <Shimmer height={13} style={{ width: `${w}%` }} />
        </td>
      ))}
    </tr>
  ))
}

// ─── User Detail Drawer (slide-over) ─────────────────────────────────────────

function UserDrawer({ userId, onClose, onUpdated }) {
  const toast = useToast()
  const { user: authUser } = useAuth()
  const [user,       setUser]       = useState(null)
  const [loading,    setLoading]    = useState(true)
  const [toggling,   setToggling]   = useState(false)
  const [assigning,  setAssigning]  = useState(false)
  const [deleting,   setDeleting]   = useState(false)
  const [confirmDel, setConfirmDel] = useState(false)
  const [editMode,   setEditMode]   = useState(false)
  const [editForm,   setEditForm]   = useState({ first_name: '', last_name: '', email: '' })
  const [editSaving, setEditSaving] = useState(false)

  useEffect(() => {
    coreApi.getUser(userId)
      .then(r => {
        setUser(r.data)
        setEditForm({ first_name: r.data.first_name || '', last_name: r.data.last_name || '', email: r.data.email || '' })
      })
      .catch(err => toast.error(extractError(err)))
      .finally(() => setLoading(false))
  }, [userId]) // eslint-disable-line react-hooks/exhaustive-deps

  const isSelf = authUser?.id === userId

  const handleToggleActive = async () => {
    if (!user) return
    setToggling(true)
    try {
      if (user.is_active) {
        if (isSelf) {
          toast.error('You cannot deactivate your own account')
          return
        }
        await coreApi.deactivateUser(userId)
        setUser(u => ({ ...u, is_active: false }))
        toast.success(`${user.username} deactivated`)
      } else {
        await coreApi.activateUser(userId)
        setUser(u => ({ ...u, is_active: true }))
        toast.success(`${user.username} activated`)
      }
      onUpdated()
    } catch (err) {
      toast.error(extractError(err))
    } finally {
      setToggling(false)
    }
  }

  const handleAssignRole = async (newRole) => {
    if (!user || !newRole) return
    if (isSelf) { toast.error('Cannot change your own role'); return }
    setAssigning(true)
    try {
      const res = await coreApi.assignRole(userId, newRole)
      setUser(res.data.user)
      toast.success(`${user.username} assigned role "${newRole}"`)
      onUpdated()
    } catch (err) {
      toast.error(extractError(err))
    } finally {
      setAssigning(false)
    }
  }

  const handleDelete = async () => {
    if (!user) return
    setDeleting(true)
    try {
      await coreApi.deleteUser(userId)
      toast.success(`${user.username} deleted`)
      onUpdated()
      onClose()
    } catch (err) {
      toast.error(extractError(err))
      setDeleting(false)
      setConfirmDel(false)
    }
  }

  const handleUpdate = async () => {
    if (!user) return
    setEditSaving(true)
    try {
      const res = await coreApi.updateUser(userId, editForm)
      setUser(prev => ({ ...prev, ...res.data }))
      toast.success('User updated')
      setEditMode(false)
      onUpdated()
    } catch (err) {
      toast.error(extractError(err))
    } finally {
      setEditSaving(false)
    }
  }

  const role = user ? deriveRole(user) : 'public'
  const roleConfig   = ROLE_CONFIG[role]   || ROLE_CONFIG.public
  const statusConfig = user?.is_active ? STATUS_CONFIG.active : STATUS_CONFIG.inactive

  return (
    <>
      {/* Backdrop */}
      <div
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.55)',
          zIndex: 900,
        }}
        onClick={onClose}
      />
      {/* Drawer */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0,
        width: 360, maxWidth: '90vw',
        background: T.surface,
        borderLeft: `1px solid ${T.border}`,
        zIndex: 901,
        display: 'flex', flexDirection: 'column',
        animation: 'au-fadeUp 0.25s ease both',
        overflowY: 'auto',
      }}>
        {/* Drawer header */}
        <div style={{
          padding: '14px 20px',
          borderBottom: `1px solid ${T.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
        }}>
          <span style={{
            fontFamily: 'Space Mono, monospace', fontSize: 9,
            letterSpacing: '0.14em', textTransform: 'uppercase', color: T.textMuted,
          }}>
            {editMode ? 'Edit User' : 'User Details'}
          </span>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            {!loading && user && !editMode && (
              <button
                onClick={() => setEditMode(true)}
                style={{
                  background: `${T.accent}10`, border: `1px solid ${T.accent}30`,
                  color: T.accent, borderRadius: 3, padding: '4px 10px',
                  fontSize: 11, fontFamily: 'IBM Plex Sans, sans-serif',
                  cursor: 'pointer', fontWeight: 500,
                }}
              >
                Edit
              </button>
            )}
            {editMode && (
              <>
                <button
                  onClick={handleUpdate}
                  disabled={editSaving}
                  style={{
                    background: `${T.success}12`, border: `1px solid ${T.success}30`,
                    color: T.success, borderRadius: 3, padding: '4px 10px',
                    fontSize: 11, fontFamily: 'IBM Plex Sans, sans-serif',
                    cursor: editSaving ? 'wait' : 'pointer', fontWeight: 500,
                    display: 'flex', alignItems: 'center', gap: 4,
                  }}
                >
                  {editSaving && <Spinner size={9} color={T.success} />}
                  Save
                </button>
                <button
                  onClick={() => { setEditMode(false); setEditForm({ first_name: user.first_name || '', last_name: user.last_name || '', email: user.email || '' }) }}
                  style={{
                    background: 'transparent', border: `1px solid ${T.border}`,
                    color: T.textMuted, borderRadius: 3, padding: '4px 10px',
                    fontSize: 11, fontFamily: 'IBM Plex Sans, sans-serif', cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
              </>
            )}
            <button
              onClick={onClose}
              style={{
                background: 'transparent', border: `1px solid ${T.border}`,
                color: T.textMuted, borderRadius: 3,
                width: 28, height: 28, cursor: 'pointer',
                fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              ×
            </button>
          </div>
        </div>

        {loading ? (
          <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 14 }}>
            {[...Array(6)].map((_, i) => <Shimmer key={i} height={i === 0 ? 28 : 14} />)}
          </div>
        ) : user ? (
          <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Avatar + name */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div style={{
                width: 52, height: 52, borderRadius: '50%',
                background: `${roleConfig.text}18`,
                border: `2px solid ${roleConfig.border}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
              }}>
                {user.profile?.avatar ? (
                  <img
                    src={user.profile.avatar}
                    alt=""
                    style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }}
                  />
                ) : (
                  <span style={{
                    fontFamily: 'Bebas Neue, sans-serif', fontSize: 22,
                    color: roleConfig.text, letterSpacing: '0.05em',
                  }}>
                    {(user.first_name || user.username || '?')[0].toUpperCase()}
                    {(user.last_name || '')[0]?.toUpperCase() || ''}
                  </span>
                )}
              </div>
              <div>
                <div style={{
                  fontFamily: 'IBM Plex Sans, sans-serif',
                  fontSize: 15, fontWeight: 600, color: T.text, marginBottom: 6,
                }}>
                  {user.full_name || user.username}
                </div>
                <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                  <Badge label={role}                      config={roleConfig} />
                  <Badge label={user.is_active ? 'active' : 'inactive'} config={statusConfig} />
                  {isSelf && <Badge label="you" config={{ bg: `${T.accent}18`, border: `${T.accent}30`, text: T.accent }} />}
                </div>
              </div>
            </div>

            {/* Info grid / Edit form */}
            <div style={{
              background: T.bg, border: `1px solid ${editMode ? T.accent + '40' : T.border}`,
              borderRadius: 4, padding: '14px 16px',
              display: 'flex', flexDirection: 'column', gap: 10,
              transition: 'border-color 0.15s',
            }}>
              {editMode ? (
                <>
                  {[
                    { key: 'first_name', label: 'First Name' },
                    { key: 'last_name',  label: 'Last Name'  },
                    { key: 'email',      label: 'Email'       },
                  ].map(({ key, label }) => (
                    <div key={key}>
                      <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textMuted, marginBottom: 4 }}>
                        {label}
                      </div>
                      <input
                        type={key === 'email' ? 'email' : 'text'}
                        value={editForm[key]}
                        onChange={e => setEditForm(f => ({ ...f, [key]: e.target.value }))}
                        style={{
                          width: '100%', boxSizing: 'border-box',
                          background: T.surface, border: `1px solid ${T.border}`,
                          borderRadius: 3, color: T.text,
                          fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
                          padding: '7px 10px', outline: 'none',
                        }}
                        onFocus={e => { e.target.style.borderColor = T.accent }}
                        onBlur={e => { e.target.style.borderColor = T.border }}
                      />
                    </div>
                  ))}
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, paddingTop: 4 }}>
                    <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textMuted, flexShrink: 0 }}>Username</span>
                    <span style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textMuted }}>{user.username}</span>
                  </div>
                </>
              ) : (
                [
                  { label: 'Username',   value: user.username },
                  { label: 'Email',      value: user.email },
                  { label: 'Name',       value: user.full_name || `${user.first_name || ''} ${user.last_name || ''}`.trim() || '—' },
                  { label: 'Joined',     value: user.date_joined ? new Date(user.date_joined).toLocaleDateString('en-NA', { year: 'numeric', month: 'short', day: 'numeric' }) : '—' },
                  { label: 'Last login', value: user.last_login  ? new Date(user.last_login).toLocaleString('en-NA',  { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'Never' },
                  { label: 'Job title',  value: user.profile?.job_title  || '—' },
                  { label: 'Org',        value: user.profile?.organization || '—' },
                  { label: '2FA',        value: user.profile?.two_factor_enabled ? `Enabled (${user.profile.two_factor_method})` : 'Disabled' },
                ].map(({ label, value }) => (
                  <div key={label} style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textMuted, flexShrink: 0 }}>
                      {label}
                    </span>
                    <span style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub, textAlign: 'right', wordBreak: 'break-all' }}>
                      {value}
                    </span>
                  </div>
                ))
              )}
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {/* Activate / Deactivate */}
              <button
                onClick={handleToggleActive}
                disabled={toggling || isSelf}
                title={isSelf ? 'Cannot deactivate your own account' : undefined}
                style={{
                  background: user.is_active ? `${T.danger}12` : `${T.success}12`,
                  border: `1px solid ${user.is_active ? `${T.danger}30` : `${T.success}30`}`,
                  color: user.is_active ? T.danger : T.success,
                  borderRadius: 4, padding: '9px 14px',
                  fontSize: 13, fontFamily: 'IBM Plex Sans, sans-serif', fontWeight: 500,
                  cursor: (toggling || isSelf) ? 'not-allowed' : 'pointer',
                  opacity: isSelf ? 0.5 : 1,
                  display: 'flex', alignItems: 'center', gap: 6,
                  transition: 'opacity 0.15s',
                }}
              >
                {toggling && <Spinner size={11} color={user.is_active ? T.danger : T.success} />}
                {user.is_active ? 'Deactivate Account' : 'Activate Account'}
              </button>

              {/* Role assignment */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                <span style={{
                  fontFamily: 'Space Mono, monospace', fontSize: 9,
                  letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textMuted,
                }}>
                  Assign Role
                </span>
                <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                  {ALL_ROLES.map(r => {
                    const currentRole = deriveRole(user)
                    const isActive = currentRole === r
                    const cfg = ROLE_CONFIG[r] || ROLE_CONFIG.public
                    const disabled = assigning || isSelf || user.is_superuser
                    return (
                      <button
                        key={r}
                        onClick={() => !isActive && handleAssignRole(r)}
                        disabled={disabled || isActive}
                        title={
                          user.is_superuser ? 'Superuser role cannot be changed here'
                          : isSelf ? 'Cannot change your own role'
                          : isActive ? 'Current role'
                          : undefined
                        }
                        style={{
                          background: isActive ? cfg.bg : 'transparent',
                          border: `1px solid ${isActive ? cfg.border : T.border}`,
                          color: isActive ? cfg.text : T.textMuted,
                          borderRadius: 3, padding: '4px 10px',
                          fontSize: 10, fontFamily: 'Space Mono, monospace',
                          letterSpacing: '0.1em', textTransform: 'uppercase',
                          cursor: (disabled || isActive) ? 'not-allowed' : 'pointer',
                          opacity: disabled ? 0.5 : 1,
                          transition: 'all 0.15s',
                          display: 'flex', alignItems: 'center', gap: 4,
                        }}
                      >
                        {assigning && isActive && <Spinner size={8} color={cfg.text} />}
                        {r.replace('_', ' ')}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Delete */}
              {!isSelf && (
                confirmDel ? (
                  <div style={{
                    background: `${T.danger}08`, border: `1px solid ${T.danger}30`,
                    borderRadius: 4, padding: '12px 14px',
                    display: 'flex', flexDirection: 'column', gap: 8,
                  }}>
                    <span style={{
                      fontFamily: 'Space Mono, monospace', fontSize: 9,
                      color: T.danger, letterSpacing: '0.12em', textTransform: 'uppercase',
                    }}>
                      This is permanent. Are you sure?
                    </span>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button
                        onClick={handleDelete}
                        disabled={deleting}
                        style={{
                          background: `${T.danger}18`, border: `1px solid ${T.danger}40`,
                          color: T.danger, borderRadius: 3, padding: '7px 14px',
                          fontSize: 12, fontFamily: 'IBM Plex Sans, sans-serif',
                          cursor: deleting ? 'wait' : 'pointer',
                          display: 'flex', alignItems: 'center', gap: 5,
                          flex: 1, justifyContent: 'center',
                        }}
                      >
                        {deleting && <Spinner size={10} color={T.danger} />}
                        {deleting ? 'Deleting…' : 'Yes, delete'}
                      </button>
                      <button
                        onClick={() => setConfirmDel(false)}
                        style={{
                          background: 'transparent', border: `1px solid ${T.border}`,
                          color: T.textMuted, borderRadius: 3, padding: '7px 14px',
                          fontSize: 12, fontFamily: 'IBM Plex Sans, sans-serif', cursor: 'pointer',
                          flex: 1,
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmDel(true)}
                    style={{
                      background: 'transparent', border: `1px solid ${T.border}`,
                      color: T.textMuted, borderRadius: 4, padding: '9px 14px',
                      fontSize: 13, fontFamily: 'IBM Plex Sans, sans-serif',
                      cursor: 'pointer', transition: 'all 0.15s',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = `${T.danger}50`; e.currentTarget.style.color = T.danger }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.color = T.textMuted }}
                  >
                    Delete Account
                  </button>
                )
              )}
            </div>
          </div>
        ) : (
          <div style={{ padding: 24, color: T.textMuted, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13 }}>
            User not found.
          </div>
        )}
      </div>
    </>
  )
}

// ─── Create User Modal ────────────────────────────────────────────────────────

function CreateUserModal({ onClose, onCreate }) {
  const toast = useToast()
  const [form,   setForm]   = useState({
    username: '', email: '', first_name: '', last_name: '',
    password: '', password_confirm: '', role: 'public',
  })
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)

  const set = (k, v) => { setForm(f => ({ ...f, [k]: v })); setErrors(e => ({ ...e, [k]: null })) }

  const validate = () => {
    const e = {}
    if (!form.username.trim())        e.username         = 'Required'
    if (!form.email.trim())           e.email            = 'Required'
    if (!form.password)               e.password         = 'Required'
    if (form.password.length < 10)    e.password         = 'Minimum 10 characters'
    if (form.password !== form.password_confirm) e.password_confirm = 'Passwords do not match'
    return e
  }

  const handleCreate = async () => {
    const e = validate()
    if (Object.keys(e).length) { setErrors(e); return }
    setSaving(true)
    try {
      // eslint-disable-next-line no-unused-vars
      const { role, ...userPayload } = form
      const res = await onCreate(userPayload)
      // Assign role after creation if not public
      if (role && role !== 'public' && res?.data?.id) {
        try {
          await coreApi.assignRole(res.data.id, role)
        } catch {
          toast.warning(`User created but role "${role}" could not be assigned`)
        }
      }
      onClose()
    } catch (err) {
      toast.error(extractError(err))
    } finally {
      setSaving(false)
    }
  }

  const inputSt = (err) => ({
    background: T.bg,
    border: `1px solid ${err ? `${T.danger}60` : T.border}`,
    borderRadius: 4, color: T.text,
    fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
    padding: '9px 12px', outline: 'none',
    width: '100%', boxSizing: 'border-box',
  })
  const labelSt = {
    fontFamily: 'Space Mono, monospace', fontSize: 9,
    letterSpacing: '0.14em', textTransform: 'uppercase',
    color: T.textMuted, display: 'block', marginBottom: 5,
  }
  const errSt = { fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, color: T.danger, marginTop: 4 }

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div style={{
        background: T.surface, border: `1px solid ${T.border}`,
        borderRadius: 8, padding: 28,
        width: 480, maxWidth: 'calc(100vw - 32px)',
        animation: 'au-fadeUp 0.2s ease both',
        display: 'flex', flexDirection: 'column', gap: 14,
        maxHeight: '90vh', overflowY: 'auto',
      }}>
        <h3 style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 22, letterSpacing: '0.04em', color: T.text, margin: 0 }}>
          Create User
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div>
            <label style={labelSt}>First Name</label>
            <input style={inputSt(false)} value={form.first_name} onChange={e => set('first_name', e.target.value)} />
          </div>
          <div>
            <label style={labelSt}>Last Name</label>
            <input style={inputSt(false)} value={form.last_name} onChange={e => set('last_name', e.target.value)} />
          </div>
        </div>

        <div>
          <label style={labelSt}>Username *</label>
          <input style={inputSt(errors.username)} value={form.username} onChange={e => set('username', e.target.value)} autoFocus />
          {errors.username && <div style={errSt}>{errors.username}</div>}
        </div>

        <div>
          <label style={labelSt}>Email *</label>
          <input type="email" style={inputSt(errors.email)} value={form.email} onChange={e => set('email', e.target.value)} />
          {errors.email && <div style={errSt}>{errors.email}</div>}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div>
            <label style={labelSt}>Password *</label>
            <input type="password" style={inputSt(errors.password)} value={form.password} onChange={e => set('password', e.target.value)} placeholder="Min 10 chars" />
            {errors.password && <div style={errSt}>{errors.password}</div>}
          </div>
          <div>
            <label style={labelSt}>Confirm Password *</label>
            <input type="password" style={inputSt(errors.password_confirm)} value={form.password_confirm} onChange={e => set('password_confirm', e.target.value)} />
            {errors.password_confirm && <div style={errSt}>{errors.password_confirm}</div>}
          </div>
        </div>

        {/* Role selector */}
        <div>
          <label style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.14em', textTransform: 'uppercase', color: T.textMuted, display: 'block', marginBottom: 7 }}>
            Role
          </label>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {ALL_ROLES.map(r => {
              const isActive = form.role === r
              const cfg = ROLE_CONFIG[r] || ROLE_CONFIG.public
              return (
                <button
                  key={r} type="button"
                  onClick={() => set('role', r)}
                  style={{
                    background: isActive ? cfg.bg : 'transparent',
                    border: `1px solid ${isActive ? cfg.border : T.border}`,
                    color: isActive ? cfg.text : T.textMuted,
                    borderRadius: 3, padding: '5px 12px',
                    fontSize: 10, fontFamily: 'Space Mono, monospace',
                    letterSpacing: '0.1em', textTransform: 'uppercase',
                    cursor: 'pointer', transition: 'all 0.15s',
                  }}
                >
                  {r.replace('_', ' ')}
                </button>
              )
            })}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', paddingTop: 6 }}>
          <button onClick={onClose} style={{ background: 'transparent', border: `1px solid ${T.border}`, color: T.textSub, borderRadius: 4, padding: '8px 16px', fontSize: 13, fontFamily: 'IBM Plex Sans, sans-serif', cursor: 'pointer' }}>
            Cancel
          </button>
          <button onClick={handleCreate} disabled={saving} style={{ background: T.accent, border: 'none', color: '#fff', borderRadius: 4, padding: '8px 20px', fontSize: 13, fontFamily: 'IBM Plex Sans, sans-serif', fontWeight: 500, cursor: saving ? 'wait' : 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
            {saving ? <Spinner size={11} color="#fff" /> : null}
            {saving ? 'Creating…' : 'Create User'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function AdminUsers() {
  const toast = useToast()
  const { user: authUser } = useAuth()

  const [users,       setUsers]       = useState([])
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState(null)
  const [page,        setPage]        = useState(1)
  const [totalPages,  setTotalPages]  = useState(1)
  const [totalCount,  setTotalCount]  = useState(0)
  const [search,      setSearch]      = useState('')
  const [filterActive, setFilterActive] = useState('all') // 'all' | 'active' | 'inactive'
  const [stats,       setStats]       = useState(null)
  const [selectedId,  setSelectedId]  = useState(null)
  const [showCreate,  setShowCreate]  = useState(false)

  // ── Fetch users ──────────────────────────────────────────────────────────────
  const fetchUsers = useCallback(async (p = 1, q = '') => {
    setLoading(true)
    setError(null)
    try {
      const params = { page: p, page_size: PAGE_SIZE }
      if (q.trim()) params.search = q.trim()
      // is_active filter — backend UserViewSet supports query params
      if (filterActive === 'active')   params.is_active = 'true'
      if (filterActive === 'inactive') params.is_active = 'false'

      const res = await coreApi.listUsers(params)
      // CustomPagination shape: { count, total_pages, current_page, page_size, results }
      const data = res.data
      setUsers(data.results ?? data)
      setTotalCount(data.count ?? data.length ?? 0)
      setTotalPages(data.total_pages ?? Math.max(1, Math.ceil((data.count ?? 0) / PAGE_SIZE)))
    } catch (err) {
      setError(extractError(err))
    } finally {
      setLoading(false)
    }
  }, [filterActive])

  // Debounced search
  useEffect(() => {
    const t = setTimeout(() => { setPage(1); fetchUsers(1, search) }, search ? 350 : 0)
    return () => clearTimeout(t)
  }, [search, fetchUsers]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetchUsers(page, search) }, [page]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { setPage(1); fetchUsers(1, search) }, [filterActive]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Stats ────────────────────────────────────────────────────────────────────
  useEffect(() => {
    coreApi.userStatistics()
      .then(r => setStats(r.data))
      .catch(e => { if (import.meta.env.DEV) console.warn('[AdminUsers] Stats unavailable:', e); toast.warning?.('User statistics unavailable') })
  }, [])

  // ── Row-level toggle active (inline, without opening drawer) ─────────────────
  const [rowToggling, setRowToggling] = useState({})

  const handleRowToggleActive = async (user) => {
    if (authUser?.id === user.id) { toast.error('Cannot deactivate your own account'); return }
    const key = user.id
    setRowToggling(s => ({ ...s, [key]: true }))
    const wasActive = user.is_active
    // Optimistic update
    setUsers(us => us.map(u => u.id === user.id ? { ...u, is_active: !wasActive } : u))
    try {
      if (wasActive) {
        await coreApi.deactivateUser(user.id)
      } else {
        await coreApi.activateUser(user.id)
      }
      toast.success(`${user.username} ${wasActive ? 'deactivated' : 'activated'}`)
    } catch (err) {
      // Rollback
      setUsers(us => us.map(u => u.id === user.id ? { ...u, is_active: wasActive } : u))
      toast.error(extractError(err))
    } finally {
      setRowToggling(s => { const n = { ...s }; delete n[key]; return n })
    }
  }

  const handleCreate = async (data) => {
    const res = await coreApi.createUser(data)
    toast.success(`User "${res.data.username}" created`)
    fetchUsers(page, search)
    return res  // returned so CreateUserModal can assign role post-creation
  }

  const handleDrawerUpdated = () => fetchUsers(page, search)

  // ── Table styles ──────────────────────────────────────────────────────────────
  const thSt = {
    padding: '10px 16px',
    fontFamily: 'Space Mono, monospace', fontSize: 9,
    letterSpacing: '0.12em', textTransform: 'uppercase',
    color: T.textMuted, textAlign: 'left',
    borderBottom: `1px solid ${T.border}`,
    whiteSpace: 'nowrap',
    background: T.surfaceHi,
  }
  const tdSt = {
    padding: '12px 16px',
    fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
    color: T.text,
    borderBottom: `1px solid ${T.border}`,
    verticalAlign: 'middle',
  }

  return (
    <div style={{ padding: '32px 40px', minHeight: '100vh', background: T.bg }}>
      <style>{STYLES}</style>

      {/* ── Header ── */}
      <div style={{ animation: 'au-fadeUp 0.4s ease both', marginBottom: 28 }}>
        <span style={{
          fontFamily: 'Space Mono, monospace', fontSize: 9,
          letterSpacing: '0.12em', textTransform: 'uppercase',
          color: T.accent, display: 'block', marginBottom: 6,
        }}>
          Admin / Users
        </span>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
          <h1 style={{
            fontFamily: 'Bebas Neue, sans-serif', fontSize: 36,
            letterSpacing: '0.04em', color: T.text, margin: 0,
          }}>
            User Management
          </h1>
          <button
            onClick={() => setShowCreate(true)}
            style={{
              background: T.accent, border: 'none', color: '#fff',
              borderRadius: 4, padding: '9px 18px',
              fontSize: 13, fontFamily: 'IBM Plex Sans, sans-serif', fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            + Create User
          </button>
        </div>
      </div>

      {/* ── Stats bar ── */}
      {stats && (
        <div style={{
          display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 24,
          animation: 'au-fadeUp 0.4s ease 0.05s both',
        }}>
          {[
            { label: 'Total',       value: stats.total,         color: T.accent },
            { label: 'Active',      value: stats.active,        color: T.success },
            { label: 'Staff',       value: stats.staff,         color: T.warning },
            { label: 'New / week',  value: stats.new_this_week, color: '#8b5cf6' },
          ].map(s => (
            <div key={s.label} style={{
              background: T.surface, border: `1px solid ${T.border}`,
              borderRadius: 4, padding: '10px 18px',
              display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <span style={{
                fontFamily: 'Bebas Neue, sans-serif',
                fontSize: 22, letterSpacing: '0.04em', color: s.color,
              }}>
                {s.value ?? '—'}
              </span>
              <span style={{
                fontFamily: 'Space Mono, monospace', fontSize: 9,
                letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textMuted,
              }}>
                {s.label}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Search + filter bar ── */}
      <div style={{
        display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20,
        animation: 'au-fadeUp 0.4s ease 0.08s both',
      }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search username, email, name…"
          style={{
            background: T.surface, border: `1px solid ${T.border}`,
            borderRadius: 4, color: T.text,
            fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
            padding: '9px 14px', outline: 'none', flex: '1 1 260px', minWidth: 0,
          }}
          onFocus={e => e.target.style.borderColor = T.accent}
          onBlur={e => e.target.style.borderColor = T.border}
        />

        {/* Status filter pills */}
        {['all', 'active', 'inactive'].map(f => {
          const active = filterActive === f
          const color = f === 'active' ? T.success : f === 'inactive' ? T.textMuted : T.accent
          return (
            <button
              key={f}
              onClick={() => setFilterActive(f)}
              style={{
                fontFamily: 'Space Mono, monospace', fontSize: 9,
                letterSpacing: '0.12em', textTransform: 'uppercase',
                padding: '6px 12px', borderRadius: 2,
                border: `1px solid ${active ? color : T.border}`,
                background: active ? `${color}18` : 'transparent',
                color: active ? color : T.textMuted,
                cursor: 'pointer', transition: 'all 0.15s',
              }}
            >
              {f}
            </button>
          )
        })}
      </div>

      {/* ── Error ── */}
      {error && (
        <div style={{
          background: `${T.danger}12`, border: `1px solid ${T.danger}30`,
          color: '#f87171', borderRadius: 4, padding: '12px 16px',
          fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, marginBottom: 20,
        }}>
          {error}
        </div>
      )}

      {/* ── Table ── */}
      <div style={{
        background: T.surface, border: `1px solid ${T.border}`,
        borderRadius: 6, overflow: 'hidden',
        animation: 'au-fadeUp 0.4s ease 0.1s both',
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['User', 'Email', 'Role', 'Status', 'Joined', 'Last Login', 'Actions'].map(h => (
                <th key={h} style={thSt}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading
              ? <ShimmerRows />
              : users.map(user => {
                  const role = deriveRole(user)
                  const roleConf   = ROLE_CONFIG[role]   || ROLE_CONFIG.public
                  const statusConf = user.is_active ? STATUS_CONFIG.active : STATUS_CONFIG.inactive
                  const isRowToggling = rowToggling[user.id]
                  const isSelf = authUser?.id === user.id

                  return (
                    <tr
                      key={user.id}
                      className="au-row"
                      style={{ cursor: 'default' }}
                    >
                      {/* User */}
                      <td style={tdSt}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          {/* Mini avatar */}
                          <div style={{
                            width: 30, height: 30, borderRadius: '50%',
                            background: `${roleConf.text}18`,
                            border: `1px solid ${roleConf.border}`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            flexShrink: 0,
                          }}>
                            <span style={{
                              fontFamily: 'Bebas Neue, sans-serif',
                              fontSize: 14, color: roleConf.text, letterSpacing: '0.05em',
                            }}>
                              {(user.first_name || user.username || '?')[0].toUpperCase()}
                            </span>
                          </div>
                          <div>
                            <div style={{ fontWeight: 500, color: T.text, marginBottom: 2 }}>
                              {user.username}
                              {isSelf && (
                                <span style={{
                                  fontFamily: 'Space Mono, monospace', fontSize: 8,
                                  color: T.accent, letterSpacing: '0.1em', marginLeft: 6,
                                }}>
                                  (you)
                                </span>
                              )}
                            </div>
                            {(user.first_name || user.last_name) && (
                              <div style={{ fontSize: 11, color: T.textMuted }}>
                                {[user.first_name, user.last_name].filter(Boolean).join(' ')}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Email */}
                      <td style={{ ...tdSt, color: T.textSub }}>{user.email || '—'}</td>

                      {/* Role */}
                      <td style={tdSt}>
                        <Badge label={role} config={roleConf} />
                      </td>

                      {/* Status */}
                      <td style={tdSt}>
                        <Badge label={user.is_active ? 'active' : 'inactive'} config={statusConf} />
                      </td>

                      {/* Joined */}
                      <td style={{ ...tdSt, color: T.textMuted, fontSize: 12 }}>
                        {user.date_joined
                          ? new Date(user.date_joined).toLocaleDateString('en-NA', { day: '2-digit', month: 'short', year: 'numeric' })
                          : '—'}
                      </td>

                      {/* Last Login */}
                      <td style={{ ...tdSt, color: T.textMuted, fontSize: 12 }}>
                        {user.last_login
                          ? new Date(user.last_login).toLocaleDateString('en-NA', { day: '2-digit', month: 'short', year: 'numeric' })
                          : 'Never'}
                      </td>

                      {/* Actions */}
                      <td style={tdSt}>
                        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                          {/* Inline activate / deactivate */}
                          <button
                            onClick={() => handleRowToggleActive(user)}
                            disabled={isRowToggling || isSelf}
                            title={isSelf ? 'Cannot deactivate your own account' : undefined}
                            style={{
                              background: user.is_active ? `${T.danger}10` : `${T.success}10`,
                              border: `1px solid ${user.is_active ? `${T.danger}30` : `${T.success}30`}`,
                              color: user.is_active ? T.danger : T.success,
                              borderRadius: 3, padding: '4px 10px',
                              fontSize: 11, fontFamily: 'IBM Plex Sans, sans-serif', fontWeight: 500,
                              cursor: (isRowToggling || isSelf) ? 'not-allowed' : 'pointer',
                              opacity: isSelf ? 0.4 : 1,
                              display: 'flex', alignItems: 'center', gap: 4,
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {isRowToggling
                              ? <Spinner size={9} color={user.is_active ? T.danger : T.success} />
                              : null}
                            {user.is_active ? 'Deactivate' : 'Activate'}
                          </button>

                          {/* View details */}
                          <button
                            onClick={() => setSelectedId(user.id)}
                            style={{
                              background: `${T.accent}10`, border: `1px solid ${T.accent}30`,
                              color: T.accent, borderRadius: 3, padding: '4px 10px',
                              fontSize: 11, fontFamily: 'IBM Plex Sans, sans-serif',
                              cursor: 'pointer', whiteSpace: 'nowrap',
                            }}
                          >
                            Details
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })
            }
          </tbody>
        </table>

        {!loading && users.length === 0 && (
          <div style={{
            textAlign: 'center', padding: '48px 24px',
            color: T.textMuted,
            fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 14,
          }}>
            {search
              ? `No users matching "${search}"`
              : 'No users found.'}
          </div>
        )}
      </div>

      {/* ── Pagination ── */}
      {totalPages > 1 && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginTop: 20, flexWrap: 'wrap', gap: 12,
          animation: 'au-fadeUp 0.4s ease 0.2s both',
        }}>
          <span style={{
            fontFamily: 'Space Mono, monospace', fontSize: 9,
            color: T.textMuted, letterSpacing: '0.1em',
          }}>
            {totalCount} USERS · PAGE {page} OF {totalPages}
          </span>
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              disabled={page <= 1}
              onClick={() => setPage(p => p - 1)}
              style={{
                background: T.surface, border: `1px solid ${T.border}`,
                color: page <= 1 ? T.border : T.textSub,
                borderRadius: 4, padding: '6px 14px',
                fontSize: 13, fontFamily: 'IBM Plex Sans, sans-serif',
                cursor: page <= 1 ? 'not-allowed' : 'pointer',
              }}
            >
              ← Prev
            </button>

            {/* Page numbers (up to 5 visible) */}
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const start = Math.max(1, Math.min(page - 2, totalPages - 4))
              const p = start + i
              return (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  style={{
                    background: p === page ? T.accent : T.surface,
                    border: `1px solid ${p === page ? T.accent : T.border}`,
                    color: p === page ? '#fff' : T.textSub,
                    borderRadius: 4, padding: '6px 12px',
                    fontSize: 13, fontFamily: 'IBM Plex Sans, sans-serif',
                    cursor: 'pointer', minWidth: 36, textAlign: 'center',
                  }}
                >
                  {p}
                </button>
              )
            })}

            <button
              disabled={page >= totalPages}
              onClick={() => setPage(p => p + 1)}
              style={{
                background: T.surface, border: `1px solid ${T.border}`,
                color: page >= totalPages ? T.border : T.textSub,
                borderRadius: 4, padding: '6px 14px',
                fontSize: 13, fontFamily: 'IBM Plex Sans, sans-serif',
                cursor: page >= totalPages ? 'not-allowed' : 'pointer',
              }}
            >
              Next →
            </button>
          </div>
        </div>
      )}

      {/* ── User detail drawer ── */}
      {selectedId && (
        <UserDrawer
          userId={selectedId}
          onClose={() => setSelectedId(null)}
          onUpdated={handleDrawerUpdated}
        />
      )}

      {/* ── Create user modal ── */}
      {showCreate && (
        <CreateUserModal
          onClose={() => setShowCreate(false)}
          onCreate={handleCreate}
        />
      )}
    </div>
  )
}