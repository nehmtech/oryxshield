import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

// Shows a minimal full-screen loader while auth state is being resolved
function AuthLoader() {
  return (
    <div style={{
      height: '100vh',
      background: '#0a0f1e',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexDirection: 'column',
      gap: 16,
    }}>
      <div style={{
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: '#3b82f6',
        animation: 'pulse 1.4s ease-in-out infinite',
      }} />
      <style>{`@keyframes pulse { 0%,100%{opacity:.3;transform:scale(1)} 50%{opacity:1;transform:scale(1.6)} }`}</style>
      <span style={{
        fontFamily: 'Space Mono, monospace',
        fontSize: 9,
        letterSpacing: '0.2em',
        color: 'rgba(249,250,251,0.3)',
        textTransform: 'uppercase',
      }}>
        Authenticating…
      </span>
    </div>
  )
}

export default function PrivateRoute() {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <AuthLoader />
  if (!user)   return <Navigate to="/login" state={{ from: location }} replace />

  return <Outlet />
}