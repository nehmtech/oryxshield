/**
 * AuthContext — OryxShield
 * ==================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * ROOT FIX: Django's UserDetailSerializer has no `role` field. It returns
 * `is_staff` and `is_superuser`. This context derives a synthetic `role`
 * string from those flags so every component that reads `user.role` works
 * correctly.
 *
 * Role derivation priority:
 *   is_superuser → 'admin'
 *   is_staff     → 'admin'
 *   profile.role if present → use as-is
 *   fallback     → 'public'
 *
 * The derived role is merged back onto the user object, so consumers only
 * ever need to read `user.role` — no special cases anywhere else.
 */

import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import { authApi, tokenStorage, extractError } from '../services/api'

const AuthContext = createContext(null)

// ---------------------------------------------------------------------------
// Role derivation — maps Django user fields → frontend role string
// ---------------------------------------------------------------------------
function deriveRole(userData) {
  if (!userData) return 'public'

  // Superuser or staff → admin
  if (userData.is_superuser || userData.is_staff) return 'admin'

  // If backend ever adds a role field directly, use it
  if (userData.role && userData.role !== 'public') return userData.role

  // Profile-level role (nested under `profile.role` if backend adds it)
  if (userData.profile?.role && userData.profile.role !== 'public') {
    return userData.profile.role
  }

  // Group membership heuristics (if backend adds groups array)
  if (Array.isArray(userData.groups)) {
    const groupNames = userData.groups.map((g) =>
      typeof g === 'string' ? g.toLowerCase() : (g.name || '').toLowerCase()
    )
    if (groupNames.includes('admin'))         return 'admin'
    if (groupNames.includes('analyst'))       return 'analyst'
    if (groupNames.includes('coordinator'))   return 'coordinator'
    if (groupNames.includes('field_officer')) return 'field_officer'
    if (groupNames.includes('field officer')) return 'field_officer'
  }

  return 'public'
}

// Normalise the raw API response, attaching a `role` property
function normaliseUser(raw) {
  if (!raw) return null
  const role = deriveRole(raw)
  return { ...raw, role }
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------
export function AuthProvider({ children }) {
  const [user,    setUser]    = useState(null)
  const [loading, setLoading] = useState(true)
  const fetchingRef = useRef(false)   // prevent concurrent fetchMe calls

  // ── Fetch current user ─────────────────────────────────────────────────────
  const fetchMe = useCallback(async () => {
    if (fetchingRef.current) return
    fetchingRef.current = true
    try {
      const res = await authApi.me()
      const normalised = normaliseUser(res.data)
      setUser(normalised)
      return normalised
    } catch (err) {
      // 401 = token expired/invalid; clear everything
      setUser(null)
      tokenStorage.clear()
      return null
    } finally {
      fetchingRef.current = false
    }
  }, [])

  // On mount: if we have a stored token, validate it by fetching /users/me/
  useEffect(() => {
    if (tokenStorage.getAccess()) {
      fetchMe().finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [fetchMe])

  // ── Login ──────────────────────────────────────────────────────────────────
  // Returns { success, requires2fa, sessionToken?, method? } or throws
  const login = async (email, password) => {
    // authApi.login already remaps { email } → { username } (fixed in api.js)
    const res  = await authApi.login({ email, password })
    const data = res.data

    // Immediate token response (2FA disabled)
    if (data.access && data.refresh) {
      tokenStorage.setTokens(data.access, data.refresh)
      const me = await fetchMe()
      return { success: true, requires2fa: false, user: me }
    }

    // 2FA challenge — backend returns { session_token, method }
    if (data.session_token) {
      return {
        success:      false,
        requires2fa:  true,
        sessionToken: data.session_token,
        method:       data.method || 'totp',   // 'totp' | 'sms' | 'email'
      }
    }

    // Unexpected response shape — treat as error
    throw new Error(data.error?.message || 'Login failed. Please try again.')
  }

  // ── Verify 2FA ─────────────────────────────────────────────────────────────
  const verify2fa = async (code, sessionToken) => {
    const res  = await authApi.verify2fa({ code, session_token: sessionToken })
    const data = res.data
    tokenStorage.setTokens(data.access, data.refresh)
    const me = await fetchMe()
    return { success: true, user: me }
  }

  // ── Resend 2FA code ────────────────────────────────────────────────────────
  const resend2fa = async (sessionToken) => {
    await authApi.resend2fa({ session_token: sessionToken })
  }

  // ── Logout ─────────────────────────────────────────────────────────────────
  const logout = async () => {
    try {
      const refresh = tokenStorage.getRefresh()
      if (refresh) await authApi.logout({ refresh })
    } catch {
      // Logout failure is non-fatal — always clear local state
    } finally {
      tokenStorage.clear()
      setUser(null)
    }
  }

  // ── Role helpers ───────────────────────────────────────────────────────────
  // hasRole accepts a string or array of strings
  const hasRole = useCallback((roles) => {
    if (!user) return false
    const userRole = user.role || 'public'
    if (Array.isArray(roles)) return roles.includes(userRole)
    return userRole === roles
  }, [user])

  // Convenience booleans — all elevated roles implicitly include admin
  const isAdmin        = useCallback(() => hasRole('admin'),                             [hasRole])
  const isAnalyst      = useCallback(() => hasRole(['admin', 'analyst']),                [hasRole])
  const isCoordinator  = useCallback(() => hasRole(['admin', 'coordinator']),            [hasRole])
  const isFieldOfficer = useCallback(() => hasRole(['admin', 'field_officer']),          [hasRole])
  const isAuthenticated = useCallback(() => !!user && !!tokenStorage.getAccess(),       [user])

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      login,
      logout,
      verify2fa,
      resend2fa,
      fetchMe,
      hasRole,
      isAdmin,
      isAnalyst,
      isCoordinator,
      isFieldOfficer,
      isAuthenticated,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}