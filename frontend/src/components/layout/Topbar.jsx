/**
 * Topbar — OryxShield
 * ============================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Live notification counter — polls /notifications/unread_count/ every 60 s.
 * UIContext.notifCount is kept in sync so Sidebar badge also stays current.
 * isTablet is read from UIContext (no local duplicate hook).
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useUI } from '../../context/UIContext'
import { coreApi } from '../../services/api'
import { useToast } from '../../context/ToastContext'

const C = {
  bg:      '#070b17',
  border:  '#1f2937',
  accent:  '#3b82f6',
  text:    '#f9fafb',
  textSub: '#6b7280',
  danger:  '#ef4444',
}

const TITLES = {
  '/dashboard':                        'Dashboard',
  '/dashboard/alerts':                 'Alerts',
  '/dashboard/surveillance':           'Surveillance',
  '/dashboard/risk':                   'Risk Assessment',
  '/dashboard/risk/alerts':            'Risk Alerts',
  '/dashboard/response':               'Response',
  '/dashboard/coordination':           'Coordination',
  '/dashboard/resources':              'Resources',
  '/dashboard/resources/requests':     'Resource Requests',
  '/dashboard/communications':         'Communications',
  '/dashboard/communications/compose': 'Compose Message',
  '/dashboard/analytics':              'Analytics',
  '/dashboard/analytics/reports':      'Reports',
  '/dashboard/operations':             'Operations',
  '/dashboard/integrations':           'Integrations',
  '/dashboard/admin/users':            'User Management',
  '/dashboard/admin/settings':         'System Settings',
  '/dashboard/profile':                'Profile',
}

function getTitle(pathname) {
  if (TITLES[pathname]) return TITLES[pathname]
  const clean = pathname.replace(/\/$/, '')
  if (TITLES[clean]) return TITLES[clean]
  const parent = clean.split('/').slice(0, -1).join('/')
  return TITLES[parent] || 'OryxShield'
}

export default function Topbar() {
  const { user }     = useAuth()
  const { toggleSidebar, sidebarCollapsed, notifCount, setNotifCount, isMobile, isTablet, wsStatus } = useUI()
  const { error: toastError } = useToast()
  const location     = useLocation()
  const navigate     = useNavigate()
  const [notifOpen,  setNotifOpen]  = useState(false)
  const [notifs,     setNotifs]     = useState([])
  const [nLoading,   setNLoading]   = useState(false)
  const [nError,     setNError]     = useState(false)
  const pollRef      = useRef(null)
  // Cache: don't re-fetch on every open; invalidate when a notif is marked read
  const notifsFetched = useRef(false)

  const title       = getTitle(location.pathname)
  const sidebarW    = isMobile ? 0 : (sidebarCollapsed ? 64 : 240)
  const displayName = user?.first_name || user?.username || user?.email?.split('@')[0] || '—'
  const shortName   = displayName.split(' ')[0]

  // ── Poll unread count ──────────────────────────────────────────────────────
  const fetchCount = useCallback(() => {
    coreApi.unreadCount()
      .then(r => {
        const cnt = r.data?.count ?? r.data?.unread_count ?? r.data ?? 0
        if (typeof setNotifCount === 'function') setNotifCount(typeof cnt === 'number' ? cnt : 0)
      })
      .catch(e => { if (import.meta.env.DEV) console.warn('[Topbar] Notification count unavailable:', e) })
  }, [setNotifCount])

  useEffect(() => {
    fetchCount()
    pollRef.current = setInterval(fetchCount, 60_000)
    return () => clearInterval(pollRef.current)
  }, [fetchCount])

  // ── Open notification panel ────────────────────────────────────────────────
  const openNotifications = () => {
    const nowOpen = !notifOpen
    setNotifOpen(nowOpen)
    // Only fetch if opening and results aren't already cached
    if (nowOpen && !notifsFetched.current) {
      setNLoading(true)
      setNError(false)
      coreApi.unreadNotifications()
        .then(r => {
          setNotifs(r.data.results || r.data || [])
          notifsFetched.current = true
        })
        .catch(() => setNError(true))
        .finally(() => setNLoading(false))
    }
  }

  const markRead = (id) => {
    coreApi.markNotifRead(id)
      .then(() => {
        setNotifs(prev => prev.filter(n => n.id !== id))
        notifsFetched.current = false  // invalidate cache so next open re-fetches
        if (typeof setNotifCount === 'function') setNotifCount(c => Math.max(0, c - 1))
      })
      .catch(() => toastError('Failed to mark notification as read'))
  }

  const markAllRead = () => {
    coreApi.markAllNotifsRead()
      .then(() => {
        setNotifs([])
        notifsFetched.current = false
        if (typeof setNotifCount === 'function') setNotifCount(0)
      })
      .catch(() => toastError('Failed to mark all notifications as read'))
  }

  return (
    <>
      <header
        style={{
          position:     'fixed',
          top:          0,
          left:         sidebarW,
          right:        0,
          height:       56,
          background:   C.bg,
          borderBottom: `1px solid ${C.border}`,
          display:      'flex',
          alignItems:   'center',
          padding:      isMobile ? '0 14px' : '0 24px',
          gap:          isMobile ? 10 : 16,
          zIndex:       99,
          transition:   'left 0.22s ease',
        }}
      >
        {/* ── Hamburger ── */}
        <button
          onClick={toggleSidebar}
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px 6px', display: 'flex', flexDirection: 'column', gap: 4, flexShrink: 0 }}
        >
          {[0, 1, 2].map((i) => (
            <span key={i} style={{ display: 'block', height: 1.5, background: C.textSub, borderRadius: 1, width: i === 1 ? 14 : 18, transition: 'width 0.2s' }} />
          ))}
        </button>

        {/* ── Page title ── */}
        <div style={{ flex: isMobile ? 1 : '0 0 auto', minWidth: 0 }}>
          <span style={{
            fontFamily: 'Bebas Neue, sans-serif', fontSize: isMobile ? 16 : 18,
            letterSpacing: '0.1em', color: C.text,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block',
          }}>{title}</span>
        </div>

        {!isMobile && <div style={{ flex: 1 }} />}

        {/* ── WS status dot ── */}
        {!isMobile && <WsDot status={wsStatus} />}

        {/* ── Ctrl+K hint ── */}
        {!isMobile && !isTablet && (
          <button
            onClick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true }))}
            title="Open command palette (Ctrl+K)"
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              background: 'none', border: `1px solid ${C.border}`,
              borderRadius: 4, padding: '3px 8px', cursor: 'pointer', flexShrink: 0,
            }}
          >
            <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: C.textSub, letterSpacing: '0.06em' }}>Ctrl</span>
            <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: C.textSub }}>K</span>
          </button>
        )}

        {/* ── Notification bell + dropdown ── */}
        <div style={{ position: 'relative', flexShrink: 0 }}>
          <button
            aria-label={`Notifications${notifCount > 0 ? ` — ${notifCount} unread` : ''}`}
            onClick={openNotifications}
            style={{
              position: 'relative', background: 'none', border: 'none', cursor: 'pointer',
              padding: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <svg width={17} height={17} viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M8 1.5A4.5 4.5 0 003.5 6v3.5L2 11h12l-1.5-1.5V6A4.5 4.5 0 008 1.5z"
                stroke={notifOpen ? C.accent : C.textSub} strokeWidth="1.3" strokeLinejoin="round"/>
              <path d="M6.5 11.5a1.5 1.5 0 003 0" stroke={notifOpen ? C.accent : C.textSub} strokeWidth="1.3"/>
            </svg>
            {notifCount > 0 && (
              <span style={{
                position: 'absolute', top: 2, right: 2,
                background: C.danger, borderRadius: '50%',
                minWidth: 15, height: 15,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'Space Mono, monospace', fontSize: 8, fontWeight: 700, color: '#fff',
                padding: '0 2px', lineHeight: 1,
              }} aria-hidden="true">
                {notifCount > 99 ? '99+' : notifCount}
              </span>
            )}
          </button>

          {/* ── Dropdown ── */}
          {notifOpen && (
            <>
              {/* Click-away backdrop */}
              <div
                style={{ position: 'fixed', inset: 0, zIndex: 149 }}
                onClick={() => setNotifOpen(false)}
                aria-hidden="true"
              />
              <div role="dialog" aria-label="Notifications" style={{
                position: 'absolute', top: 'calc(100% + 8px)', right: 0,
                width: 320, maxHeight: 420,
                background: '#0f1729',
                border: `1px solid ${C.border}`,
                borderRadius: 6, zIndex: 150,
                display: 'flex', flexDirection: 'column',
                boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                overflow: 'hidden',
              }}>
                {/* Header */}
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '12px 16px', borderBottom: `1px solid ${C.border}`, flexShrink: 0,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: C.text }}>
                      Notifications
                    </span>
                    {notifCount > 0 && (
                      <span style={{
                        background: C.danger, borderRadius: 2, padding: '1px 6px',
                        fontFamily: 'Space Mono, monospace', fontSize: 8, fontWeight: 700, color: '#fff',
                      }}>{notifCount}</span>
                    )}
                  </div>
                  {notifCount > 0 && (
                    <button
                      onClick={markAllRead}
                      style={{
                        fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, color: C.accent,
                        background: 'none', border: 'none', cursor: 'pointer', padding: 0,
                      }}
                    >Mark all read</button>
                  )}
                </div>

                {/* List */}
                <div style={{ overflowY: 'auto', flex: 1 }}>
                  {nLoading ? (
                    <div style={{ padding: '20px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                      {[1, 2, 3].map(i => (
                        <div key={i} style={{ height: 14, borderRadius: 3, background: `linear-gradient(90deg, #111827 25%, #151e2e 50%, #111827 75%)`, backgroundSize: '200% 100%', animation: 'tb-shimmer 1.5s infinite' }} />
                      ))}
                    </div>
                  ) : nError ? (
                    <div style={{ padding: '32px 16px', textAlign: 'center' }}>
                      <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.14em', textTransform: 'uppercase', color: C.danger, marginBottom: 6 }}>
                        Failed to load
                      </div>
                      <button
                        onClick={() => { notifsFetched.current = false; setNError(false); openNotifications() }}
                        style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: C.accent, background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                      >
                        Retry
                      </button>
                    </div>
                  ) : notifs.length === 0 ? (
                    <div style={{ padding: '32px 16px', textAlign: 'center' }}>
                      <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.14em', textTransform: 'uppercase', color: C.textSub }}>All caught up</div>
                      <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: C.textSub, marginTop: 6 }}>No unread notifications</div>
                    </div>
                  ) : (
                    notifs.map(n => (
                      <button
                        key={n.id}
                        onClick={() => {
                          markRead(n.id)
                          navigate(n.action_url || '/dashboard/notifications')
                          setNotifOpen(false)
                        }}
                        style={{
                          width: '100%',
                          padding: '12px 16px', borderBottom: `1px solid ${C.border}`,
                          display: 'flex', gap: 12, alignItems: 'flex-start',
                          cursor: 'pointer', background: 'transparent', border: 'none',
                          borderBottom: `1px solid ${C.border}`,
                          textAlign: 'left',
                          transition: 'background 0.12s',
                        }}
                        onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                      >
                        {/* Unread dot */}
                        <div style={{ width: 6, height: 6, borderRadius: '50%', background: C.accent, flexShrink: 0, marginTop: 5 }} aria-hidden="true" />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: C.text, lineHeight: 1.4 }}>{n.title || n.message || 'Notification'}</div>
                          {n.message && n.title && (
                            <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, color: C.textSub, marginTop: 2, lineHeight: 1.4 }}>{n.message}</div>
                          )}
                          {n.created_at && (
                            <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: C.textSub, marginTop: 4, letterSpacing: '0.08em' }}>
                              {new Date(n.created_at).toLocaleString('en-NA', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                            </div>
                          )}
                        </div>
                        <span
                          onClick={e => { e.stopPropagation(); markRead(n.id) }}
                          onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); markRead(n.id) } }}
                          role="button"
                          tabIndex={0}
                          aria-label="Mark as read"
                          style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.textSub, fontSize: 14, padding: '0 2px', flexShrink: 0, lineHeight: 1 }}
                        >×</span>
                      </button>
                    ))
                  )}
                </div>

                {/* Footer */}
                <div style={{ padding: '10px 16px', borderTop: `1px solid ${C.border}`, flexShrink: 0 }}>
                  <button
                    onClick={() => { navigate('/dashboard/notifications'); setNotifOpen(false) }}
                    style={{
                      width: '100%', fontFamily: 'Space Mono, monospace', fontSize: 9,
                      letterSpacing: '0.1em', textTransform: 'uppercase',
                      color: C.accent, background: 'none', border: 'none',
                      cursor: 'pointer', padding: 0, textAlign: 'center',
                    }}
                  >View all alerts →</button>
                </div>
              </div>
            </>
          )}
        </div>

        {/* ── Role badge + username ── */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0,
          paddingLeft: isMobile ? 0 : 8,
          borderLeft: isMobile ? 'none' : `1px solid ${C.border}`,
        }}>
          {!isMobile && <RoleBadge role={user?.role} compact={isTablet} />}
          <span style={{
            fontFamily: 'IBM Plex Sans, sans-serif', fontSize: isMobile ? 11 : 12, fontWeight: 500,
            color: C.text, whiteSpace: 'nowrap',
            maxWidth: isMobile ? 72 : 120, overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {isMobile ? shortName : displayName}
          </span>
        </div>
      </header>

      <style>{`
        @keyframes tb-shimmer {
          0%   { background-position: -200% 0; }
          100% { background-position:  200% 0; }
        }
        @keyframes ws-pulse {
          0%   { transform: scale(1);   opacity: 0.4; }
          70%  { transform: scale(2.4); opacity: 0; }
          100% { transform: scale(2.4); opacity: 0; }
        }
      `}</style>
    </>
  )
}

function WsDot({ status }) {
  const cfg = {
    open:       { color: '#10b981', label: 'Live — real-time feed connected' },
    connecting: { color: '#f59e0b', label: 'Connecting to live feed…' },
    error:      { color: '#ef4444', label: 'Live feed error — retrying' },
    closed:     { color: '#6b7280', label: 'Live feed disconnected — retrying' },
  }
  const { color, label } = cfg[status] || cfg.connecting
  const pulse = status === 'open'
  return (
    <div title={label} aria-label={label} style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
      <div style={{ position: 'relative', width: 8, height: 8 }}>
        {pulse && (
          <span style={{
            position: 'absolute', inset: 0,
            borderRadius: '50%', background: color, opacity: 0.4,
            animation: 'ws-pulse 1.8s ease-out infinite',
          }} aria-hidden="true" />
        )}
        <span style={{
          position: 'absolute', inset: 0,
          borderRadius: '50%', background: color,
        }} />
      </div>
      <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, letterSpacing: '0.12em', color: '#6b7280', textTransform: 'uppercase' }}>
        {status === 'open' ? 'Live' : status === 'connecting' ? 'Sync' : 'Off'}
      </span>
    </div>
  )
}

function RoleBadge({ role, compact }) {
  const map = {
    admin:         { color: '#ef4444', label: 'ADMIN',    short: 'ADM' },
    analyst:       { color: '#3b82f6', label: 'ANALYST',  short: 'ANL' },
    coordinator:   { color: '#f59e0b', label: 'COORD',    short: 'CRD' },
    field_officer: { color: '#10b981', label: 'FIELD',    short: 'FLD' },
    public:        { color: '#6b7280', label: 'PUBLIC',   short: 'PUB' },
  }
  const v = map[role] || { color: '#6b7280', label: role?.toUpperCase() || '—', short: '—' }
  return (
    <span style={{
      fontFamily: 'Space Mono, monospace', fontSize: 8, letterSpacing: '0.15em',
      color: v.color, background: `${v.color}18`,
      border: `1px solid ${v.color}30`, borderRadius: 2, padding: '2px 6px', whiteSpace: 'nowrap',
    }}>
      {compact ? v.short : v.label}
    </span>
  )
}
