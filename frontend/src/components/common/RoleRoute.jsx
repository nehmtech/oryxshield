/**
 * RoleRoute — OryxShield
 * ================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * FIX: Added loading guard. Without it, on a hard refresh the auth context
 * resolves asynchronously — user is null for a brief moment, so RoleRoute
 * would redirect to /login even for authenticated users.
 *
 * Now: if loading → show nothing (PrivateRoute above already shows its own
 * loader, so this is just a safety net). If no user → redirect. If user but
 * wrong role → show 403 Forbidden inline.
 */
import { Navigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

const C = {
  bg:      '#0a0f1e',
  danger:  '#ef4444',
  text:    '#f9fafb',
  textSub: '#9ca3af',
}

function Forbidden({ requiredRoles, userRole }) {
  return (
    <div style={{
      display:        'flex',
      alignItems:     'center',
      justifyContent: 'center',
      minHeight:      '60vh',
      flexDirection:  'column',
      gap:            12,
      padding:        32,
    }}>
      <span style={{
        fontFamily: 'Bebas Neue, sans-serif',
        fontSize:   72,
        color:      C.danger,
        lineHeight: 1,
      }}>
        403
      </span>
      <p style={{
        fontFamily:    'Space Mono, monospace',
        fontSize:      11,
        letterSpacing: '0.15em',
        color:         C.textSub,
        textTransform: 'uppercase',
        margin:        0,
      }}>
        Access Denied
      </p>
      <p style={{
        fontFamily: 'IBM Plex Sans, sans-serif',
        fontSize:   13,
        color:      C.textSub,
        textAlign:  'center',
        maxWidth:   340,
        lineHeight: 1.6,
        margin:     0,
      }}>
        Your role{' '}
        <span style={{ color: C.text, fontFamily: 'Space Mono, monospace', fontSize: 11 }}>
          ({userRole || 'unknown'})
        </span>
        {' '}does not have access to this section. Required:{' '}
        <span style={{ color: C.text }}>{requiredRoles.join(', ')}</span>.
      </p>
      <button
        onClick={() => window.history.back()}
        style={{
          marginTop:     16,
          fontFamily:    'Space Mono, monospace',
          fontSize:      9,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          padding:       '8px 20px',
          background:    'transparent',
          border:        '1px solid #1f2937',
          borderRadius:  3,
          color:         C.textSub,
          cursor:        'pointer',
        }}
      >
        ← Go Back
      </button>
    </div>
  )
}

// RoleRoute wraps children (not Outlet).
// Usage in App.jsx:
//   <RoleRoute roles={['admin', 'analyst']}><Dashboard /></RoleRoute>
export default function RoleRoute({ roles = [], children }) {
  const { user, loading, hasRole } = useAuth()

  // While auth is resolving, render nothing — PrivateRoute above us
  // is already showing its AuthLoader spinner. Rendering children here
  // before user is known would cause a flash of either content or redirect.
  if (loading) return null

  // Should not normally reach here (PrivateRoute handles this above),
  // but kept as a safety net.
  if (!user) return <Navigate to="/login" replace />

  // Role check — user.role is set by AuthContext.deriveRole() which maps
  // is_staff/is_superuser → 'admin', so this always has a real value.
  if (roles.length > 0 && !hasRole(roles)) {
    return <Forbidden requiredRoles={roles} userRole={user.role} />
  }

  return children
}