/**
 * Sidebar — OryxShield
 * ==============================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Three responsive states:
 *
 *   Mobile  < 768 px  → sidebar is hidden entirely; MobileNav takes over
 *   Tablet  768–1023  → sidebar renders as a slide-over overlay (toggled by
 *                        the hamburger in Topbar). When open it covers content;
 *                        a translucent backdrop closes it on tap.
 *                        Default: closed (collapsed).  Width when open: 240 px.
 *   Desktop ≥ 1024    → fixed sidebar, always visible.
 *                        Collapsed = 64 px icon-only rail.
 *                        Expanded  = 240 px with labels.
 *
 * UIContext must expose:
 *   isMobile         — true when window < 768
 *   isTablet         — true when 768 ≤ window < 1024   ← NEW (add to UIContext)
 *   sidebarCollapsed — toggled by Topbar hamburger
 *   toggleSidebar    — toggle function
 *   notifCount       — unread notification count (kept in sync by Topbar)
 *
 * If UIContext does not yet provide isTablet, a local fallback hook is used.
 *
 * FIX (original): activePortal was initialised with useState at render time
 * while user was still null → role defaulted to 'public'.
 * Solution: useMemo recomputes whenever user changes; useEffect resets portal
 * if role changes make it inaccessible.
 *
 * ADDED: Notification badges on Alerts, Risk Alerts, and Communications items.
 *   badge: 'alert' | 'comms' on a portal item → pulls UIContext.notifCount.
 *   Collapsed state: small red dot.  Expanded state: numbered chip (99+ cap).
 */

import { useState, useMemo, useEffect, useCallback } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useUI } from '../../context/UIContext'
import { useToast } from '../../context/ToastContext'

// ─── Design tokens ────────────────────────────────────────────────────────────
const C = {
  bg:        '#070b17',
  bgHover:   'rgba(255,255,255,0.03)',
  border:    '#1f2937',
  accent:    '#3b82f6',
  accentBg:  'rgba(59,130,246,0.08)',
  danger:    '#ef4444',
  success:   '#10b981',
  warning:   '#f59e0b',
  text:      '#f9fafb',
  textSub:   '#9ca3af',
  textMuted: '#6b7280',
  overlay:   'rgba(0,0,0,0.55)',
}


// ─── Portal definitions ───────────────────────────────────────────────────────
// badge: 'alert' → shows notifCount on Alerts / Risk Alerts
// badge: 'comms' → shows notifCount on Communications
const PORTALS = [
  {
    id:    'operations',
    label: 'Operations',
    short: 'OPS',
    icon:  ShieldIcon,
    roles: ['admin', 'coordinator', 'field_officer'],
    groups: [
      {
        label: 'COMMAND',
        items: [
          { to: '/dashboard',                label: 'Dashboard',     icon: DashIcon },
          { to: '/dashboard/alerts',         label: 'Alerts',        icon: AlertIcon,  badge: 'alert' },
          { to: '/dashboard/notifications',  label: 'Notifications', icon: BellIcon,   badge: 'notif' },
        ],
      },
      {
        label: 'RESPONSE',
        items: [
          { to: '/dashboard/response',     label: 'Response',     icon: ResponseIcon,  roles: ['admin', 'coordinator'] },
          { to: '/dashboard/coordination', label: 'Coordination', icon: CoordIcon,     roles: ['admin', 'coordinator'] },
          { to: '/dashboard/resources',    label: 'Resources',    icon: ResourcesIcon, roles: ['admin', 'coordinator', 'field_officer'] },
          { to: '/dashboard/operations',   label: 'Operations',   icon: OpsIcon,       roles: ['admin', 'coordinator', 'field_officer'] },
        ],
      },
      {
        label: 'COMMS',
        items: [
          { to: '/dashboard/communications', label: 'Communications', icon: CommsIcon, roles: ['admin', 'coordinator'], badge: 'comms' },
        ],
      },
    ],
  },
  {
    id:    'intelligence',
    label: 'Intelligence',
    short: 'INTEL',
    icon:  RadarIcon,
    roles: ['admin', 'analyst'],
    groups: [
      {
        label: 'SURVEILLANCE',
        items: [
          { to: '/dashboard/surveillance',    label: 'Surveillance', icon: SurvIcon },
          { to: '/dashboard/risk',            label: 'Risk',         icon: RiskIcon },
          { to: '/dashboard/risk/alerts',     label: 'Risk Alerts',  icon: RiskAlertIcon, badge: 'alert' },
        ],
      },
      {
        label: 'ANALYTICS',
        items: [
          { to: '/dashboard/analytics',         label: 'Analytics', icon: AnalyticsIcon },
          { to: '/dashboard/analytics/reports', label: 'Reports',   icon: ReportsIcon },
        ],
      },
    ],
  },
  {
    id:    'admin',
    label: 'Admin',
    short: 'ADM',
    icon:  AdminIcon,
    roles: ['admin'],
    groups: [
      {
        label: 'SYSTEM',
        items: [
          { to: '/dashboard/admin/users',      label: 'Users',      icon: UsersIcon },
          { to: '/dashboard/admin/settings',   label: 'Settings',   icon: SettingsIcon },
          { to: '/dashboard/admin/locations',  label: 'Locations',  icon: MapPinIcon },
          { to: '/dashboard/admin/audit-logs', label: 'Audit Logs', icon: AuditIcon },
        ],
      },
      {
        label: 'INTEGRATIONS',
        items: [
          { to: '/dashboard/integrations', label: 'Integrations', icon: IntegIcon },
        ],
      },
    ],
  },
]

const DEFAULT_PORTAL_FOR_ROLE = {
  admin:         'operations',
  coordinator:   'operations',
  field_officer: 'operations',
  analyst:       'intelligence',
  public:        'operations',
}

const ROLE_LABELS = {
  admin:         'Admin',
  analyst:       'Analyst',
  coordinator:   'Coordinator',
  field_officer: 'Field Officer',
  public:        'Public',
}

const ROLE_COLORS = {
  admin:         '#ef4444',
  analyst:       '#3b82f6',
  coordinator:   '#f59e0b',
  field_officer: '#10b981',
  public:        '#6b7280',
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────
export default function Sidebar() {
  const { user, logout } = useAuth()
  const { sidebarCollapsed, toggleSidebar, notifCount, isMobile, isTablet } = useUI()
  const { error: toastError } = useToast()
  const navigate = useNavigate()

  const userRole = user?.role || 'public'

  const myPortals = useMemo(
    () => PORTALS.filter((p) => p.roles.includes(userRole)),
    [userRole]
  )

  const defaultPortalId = DEFAULT_PORTAL_FOR_ROLE[userRole] || myPortals[0]?.id || 'operations'
  const [activePortalId, setActivePortalId] = useState(defaultPortalId)

  useEffect(() => {
    const accessible = myPortals.some((p) => p.id === activePortalId)
    if (!accessible) setActivePortalId(defaultPortalId)
  }, [userRole, myPortals, activePortalId, defaultPortalId])

  // On tablet, close sidebar after a nav click
  const handleNavClick = useCallback(() => {
    if (isTablet && !sidebarCollapsed) toggleSidebar()
  }, [isTablet, sidebarCollapsed, toggleSidebar])

  const handleLogout = async () => {
    try { await logout() } catch { toastError('Logout failed. Please try again.') }
    navigate('/login', { replace: true })
  }

  // ── Responsive rendering ──────────────────────────────────────────────────

  // Mobile: completely absent — MobileNav handles navigation
  if (isMobile) return null

  // On tablet the sidebar is an overlay: collapsed = hidden, open = 240 px slide-in
  const isTabletOpen = isTablet && !sidebarCollapsed

  // Desktop widths
  const W = sidebarCollapsed ? 64 : 240

  const portal = myPortals.find((p) => p.id === activePortalId) || myPortals[0]

  // ── Tablet: backdrop ──────────────────────────────────────────────────────
  const Backdrop = isTabletOpen
    ? <div
        onClick={toggleSidebar}
        style={{
          position:   'fixed',
          inset:      0,
          background: C.overlay,
          zIndex:     99,
          backdropFilter: 'blur(2px)',
        }}
      />
    : null

  // ── Sidebar style: tablet slides in from left; desktop is always visible ──
  const sidebarStyle = isTablet
    ? {
        position:    'fixed',
        top:         0,
        left:        0,
        bottom:      0,
        width:       240,
        background:  C.bg,
        borderRight: `1px solid ${C.border}`,
        display:     'flex',
        flexDirection:'column',
        zIndex:      100,
        overflowX:   'hidden',
        overflowY:   'auto',
        // Slide in/out
        transform:   isTabletOpen ? 'translateX(0)' : 'translateX(-100%)',
        transition:  'transform 0.22s ease',
        // Shadow when open
        boxShadow:   isTabletOpen ? '4px 0 24px rgba(0,0,0,0.5)' : 'none',
      }
    : {
        // Desktop: fixed, always visible
        position:    'fixed',
        top:         0,
        left:        0,
        bottom:      0,
        width:       W,
        background:  C.bg,
        borderRight: `1px solid ${C.border}`,
        display:     'flex',
        flexDirection:'column',
        transition:  'width 0.22s ease',
        zIndex:      100,
        overflowX:   'hidden',
        overflowY:   'auto',
      }

  // On tablet the sidebar is never "collapsed" in icon mode — it's either
  // fully open (240 px) or hidden (translated off screen). So treat
  // collapsed = false for rendering purposes when tablet is open.
  const collapsed = isTablet ? false : sidebarCollapsed

  return (
    <>
      {Backdrop}

      <nav style={sidebarStyle}>

        {/* ── Logo ──────────────────────────────────────────────────────────── */}
        <div style={{
          height:       56,
          display:      'flex',
          alignItems:   'center',
          padding:      '0 20px',
          borderBottom: `1px solid ${C.border}`,
          flexShrink:   0,
          gap:          10,
        }}>
          {/* Status dot */}
          <div style={{
            width:        8,
            height:       8,
            borderRadius: '50%',
            background:   C.success,
            flexShrink:   0,
            boxShadow:    `0 0 8px ${C.success}`,
            animation:    'ls-glow 2.5s ease-in-out infinite',
          }} />
          <style>{`
            @keyframes ls-glow {
              0%,100% { box-shadow: 0 0 6px ${C.success}; }
              50%      { box-shadow: 0 0 16px ${C.success}; }
            }
          `}</style>

          {!collapsed && (
            <div>
              <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 14, letterSpacing: '0.14em', color: C.text, lineHeight: 1 }}>
                ORYXSHIELD
              </div>
              <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 7, letterSpacing: '0.14em', color: C.textMuted, textTransform: 'uppercase', lineHeight: 1.4 }}>
                Protocol
              </div>
            </div>
          )}
        </div>

        {/* ── Portal Switcher ───────────────────────────────────────────────── */}
        {myPortals.length > 1 && (
          <div style={{
            display:      'flex',
            flexDirection: collapsed ? 'column' : 'row',
            gap:          collapsed ? 4 : 0,
            padding:      collapsed ? '8px 12px' : '8px 10px',
            borderBottom: `1px solid ${C.border}`,
            flexShrink:   0,
          }}>
            {myPortals.map((p) => {
              const isActive = portal?.id === p.id
              return (
                <button
                  key={p.id}
                  onClick={() => setActivePortalId(p.id)}
                  title={p.label}
                  style={{
                    flex:           collapsed ? undefined : 1,
                    minWidth:       0,
                    display:        'flex',
                    alignItems:     'center',
                    justifyContent: 'center',
                    gap:            4,
                    padding:        collapsed ? '7px 0' : '6px 4px',
                    background:     isActive ? C.accentBg : 'transparent',
                    border:         `1px solid ${isActive ? C.accent : 'transparent'}`,
                    borderRadius:   4,
                    cursor:         'pointer',
                    transition:     'all 0.15s',
                    overflow:       'hidden',
                  }}
                >
                  <p.icon size={13} color={isActive ? C.accent : C.textMuted} style={{ flexShrink: 0 }} />
                  {!collapsed && (
                    <span style={{
                      fontFamily:    'Space Mono, monospace',
                      fontSize:      8,
                      letterSpacing: '0.1em',
                      textTransform: 'uppercase',
                      color:         isActive ? C.accent : C.textMuted,
                      fontWeight:    isActive ? 700 : 400,
                      overflow:      'hidden',
                      textOverflow:  'ellipsis',
                      whiteSpace:    'nowrap',
                    }}>
                      {p.short || p.label}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        )}

        {/* ── Nav Groups ────────────────────────────────────────────────────── */}
        <div style={{ flex: 1, paddingTop: 8, paddingBottom: 8 }}>
          {portal?.groups.map((group) => {
            const visibleItems = group.items.filter(
              (item) => !item.roles || item.roles.includes(userRole)
            )
            if (!visibleItems.length) return null

            return (
              <div key={group.label} style={{ marginBottom: 4 }}>
                {!collapsed && (
                  <div style={{
                    fontFamily:    'Space Mono, monospace',
                    fontSize:      8,
                    letterSpacing: '0.2em',
                    color:         C.textMuted,
                    textTransform: 'uppercase',
                    padding:       '10px 20px 4px',
                  }}>
                    {group.label}
                  </div>
                )}
                {collapsed && <div style={{ height: 8 }} />}
                {visibleItems.map((item) => (
                  <SidebarItem
                    key={item.to}
                    item={item}
                    collapsed={collapsed}
                    onClick={handleNavClick}
                    notifCount={notifCount}
                  />
                ))}
              </div>
            )
          })}
        </div>

        {/* ── Profile + Logout ──────────────────────────────────────────────── */}
        <div style={{ borderTop: `1px solid ${C.border}`, flexShrink: 0 }}>
          <NavLink
            to="/dashboard/profile"
            onClick={handleNavClick}
            style={({ isActive }) => ({
              display:        'flex',
              alignItems:     'center',
              gap:            10,
              padding:        collapsed ? '10px 18px' : '10px 20px',
              textDecoration: 'none',
              background:     isActive ? C.accentBg : 'transparent',
              borderLeft:     `2px solid ${isActive ? C.accent : 'transparent'}`,
              transition:     'all 0.15s',
            })}
          >
            <Avatar user={user} />
            {!collapsed && (
              <div style={{ overflow: 'hidden', flex: 1 }}>
                <p style={{
                  fontFamily:   'IBM Plex Sans, sans-serif',
                  fontSize:     12,
                  fontWeight:   500,
                  color:        C.text,
                  whiteSpace:   'nowrap',
                  overflow:     'hidden',
                  textOverflow: 'ellipsis',
                  margin:       0,
                }}>
                  {user?.first_name || user?.email?.split('@')[0] || 'User'}
                </p>
                <p style={{
                  fontFamily:    'Space Mono, monospace',
                  fontSize:      8,
                  color:         ROLE_COLORS[userRole] || C.textMuted,
                  textTransform: 'uppercase',
                  letterSpacing: '0.1em',
                  margin:        0,
                }}>
                  {ROLE_LABELS[userRole] || userRole}
                </p>
              </div>
            )}
            {!collapsed && <RoleDot role={userRole} />}
          </NavLink>

          <button
            onClick={handleLogout}
            title="Logout"
            style={{
              display:    'flex',
              alignItems: 'center',
              gap:        10,
              padding:    collapsed ? '10px 18px' : '10px 20px',
              background: 'transparent',
              border:     'none',
              borderLeft: '2px solid transparent',
              cursor:     'pointer',
              width:      '100%',
              transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(239,68,68,0.07)' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
          >
            <LogoutIcon size={15} color="rgba(239,68,68,0.6)" />
            {!collapsed && (
              <span style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: 'rgba(239,68,68,0.6)' }}>
                Logout
              </span>
            )}
          </button>
        </div>
      </nav>
    </>
  )
}

// ─── Nav Item ─────────────────────────────────────────────────────────────────
function SidebarItem({ item, collapsed, onClick, notifCount }) {
  // Resolve badge count — alert / comms / notif all use the global notifCount
  const badgeCount = (item.badge === 'alert' || item.badge === 'comms' || item.badge === 'notif') ? (notifCount || 0) : 0

  return (
    <NavLink
      to={item.to}
      end={item.to === '/dashboard' || item.to === '/dashboard/alerts'}
      title={collapsed ? item.label : undefined}
      onClick={onClick}
      style={({ isActive }) => ({
        display:        'flex',
        alignItems:     'center',
        gap:            10,
        padding:        collapsed ? '9px 22px' : '9px 20px',
        textDecoration: 'none',
        background:     isActive ? C.accentBg : 'transparent',
        borderLeft:     `2px solid ${isActive ? C.accent : 'transparent'}`,
        transition:     'background 0.15s, border-color 0.15s',
      })}
      onMouseEnter={(e) => {
        if (!e.currentTarget.style.background.includes('59,130')) {
          e.currentTarget.style.background = C.bgHover
        }
      }}
      onMouseLeave={(e) => {
        if (!e.currentTarget.style.background.includes('59,130')) {
          e.currentTarget.style.background = 'transparent'
        }
      }}
    >
      {({ isActive }) => (
        <>
          {/* Icon — wrapped in relative div so collapsed dot badge can be absolute-positioned */}
          <div style={{ position: 'relative', flexShrink: 0 }}>
            <item.icon size={14} color={isActive ? C.accent : C.textMuted} />
            {/* Collapsed state: small red dot indicator (no room for a number) */}
            {collapsed && badgeCount > 0 && (
              <div style={{
                position:     'absolute',
                top:          -3,
                right:        -3,
                width:        6,
                height:       6,
                borderRadius: '50%',
                background:   C.danger,
              }} />
            )}
          </div>

          {!collapsed && (
            <>
              <span style={{
                fontFamily: 'IBM Plex Sans, sans-serif',
                fontSize:   13,
                fontWeight: isActive ? 500 : 400,
                color:      isActive ? C.text : C.textSub,
                transition: 'color 0.15s',
                whiteSpace: 'nowrap',
                flex:       1,
              }}>
                {item.label}
              </span>

              {/* Expanded state: red count chip */}
              {badgeCount > 0 && (
                <span style={{
                  fontFamily:    'Space Mono, monospace',
                  fontSize:      8,
                  fontWeight:    700,
                  letterSpacing: '0.05em',
                  background:    C.danger,
                  color:         '#fff',
                  borderRadius:  2,
                  padding:       '1px 5px',
                  lineHeight:    1.4,
                  flexShrink:    0,
                }}>
                  {badgeCount > 99 ? '99+' : badgeCount}
                </span>
              )}
            </>
          )}
        </>
      )}
    </NavLink>
  )
}

// ─── Avatar ───────────────────────────────────────────────────────────────────
function Avatar({ user }) {
  const initial = (
    user?.first_name?.[0]?.toUpperCase() ||
    user?.username?.[0]?.toUpperCase()   ||
    user?.email?.[0]?.toUpperCase()      ||
    '?'
  )
  return (
    <div style={{
      width:          26,
      height:         26,
      borderRadius:   '50%',
      background:     'rgba(59,130,246,0.15)',
      border:         '1px solid rgba(59,130,246,0.25)',
      display:        'flex',
      alignItems:     'center',
      justifyContent: 'center',
      flexShrink:     0,
      fontFamily:     'Space Mono, monospace',
      fontSize:       10,
      fontWeight:     700,
      color:          C.accent,
    }}>
      {initial}
    </div>
  )
}

// ─── Role dot ─────────────────────────────────────────────────────────────────
function RoleDot({ role }) {
  const color = ROLE_COLORS[role] || '#6b7280'
  return (
    <div style={{
      width:        6,
      height:       6,
      borderRadius: '50%',
      background:   color,
      flexShrink:   0,
    }} />
  )
}

// ─── Icons ────────────────────────────────────────────────────────────────────
function Ico({ size = 16, children }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ flexShrink: 0 }}
    >
      {children}
    </svg>
  )
}

function ShieldIcon({ size, color })    { return <Ico size={size}><path d="M8 1L13 3v5c0 3.5-2.5 5.5-5 6.5C5.5 13.5 3 11.5 3 8V3L8 1z" stroke={color} strokeWidth="1.2" strokeLinejoin="round"/></Ico> }
function RadarIcon({ size, color })     { return <Ico size={size}><circle cx="8" cy="8" r="6" stroke={color} strokeWidth="1.2"/><circle cx="8" cy="8" r="3" stroke={color} strokeWidth="1.2"/><path d="M8 2V4M8 12V14M2 8H4M12 8H14" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function AdminIcon({ size, color })     { return <Ico size={size}><circle cx="8" cy="5" r="2.5" stroke={color} strokeWidth="1.2"/><path d="M3 13c0-2.76 2.24-4 5-4h0" stroke={color} strokeWidth="1.2" strokeLinecap="round"/><circle cx="11.5" cy="11.5" r="2" stroke={color} strokeWidth="1.2"/><path d="M11.5 10v1.5l1 1" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function DashIcon({ size, color })      { return <Ico size={size}><rect x="1" y="1" width="6" height="6" rx="1" stroke={color} strokeWidth="1.2"/><rect x="9" y="1" width="6" height="6" rx="1" stroke={color} strokeWidth="1.2"/><rect x="1" y="9" width="6" height="6" rx="1" stroke={color} strokeWidth="1.2"/><rect x="9" y="9" width="6" height="6" rx="1" stroke={color} strokeWidth="1.2"/></Ico> }
function AlertIcon({ size, color })     { return <Ico size={size}><path d="M8 2L14 13H2L8 2Z" stroke={color} strokeWidth="1.2" strokeLinejoin="round"/><path d="M8 6V9" stroke={color} strokeWidth="1.2" strokeLinecap="round"/><circle cx="8" cy="11" r=".6" fill={color}/></Ico> }
function ResponseIcon({ size, color })  { return <Ico size={size}><circle cx="8" cy="8" r="6" stroke={color} strokeWidth="1.2"/><path d="M8 5V8L10 10" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function CoordIcon({ size, color })     { return <Ico size={size}><circle cx="4" cy="4" r="2" stroke={color} strokeWidth="1.2"/><circle cx="12" cy="4" r="2" stroke={color} strokeWidth="1.2"/><circle cx="8" cy="12" r="2" stroke={color} strokeWidth="1.2"/><path d="M4 6L8 10M12 6L8 10" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function ResourcesIcon({ size, color }) { return <Ico size={size}><rect x="2" y="4" width="12" height="9" rx="1" stroke={color} strokeWidth="1.2"/><path d="M5 4V3a1 1 0 011-1h4a1 1 0 011 1v1" stroke={color} strokeWidth="1.2"/><path d="M5 8.5H11" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function OpsIcon({ size, color })       { return <Ico size={size}><path d="M8 1L10.5 6H14L11 9.5L12.5 14L8 11.5L3.5 14L5 9.5L2 6H5.5L8 1Z" stroke={color} strokeWidth="1.2" strokeLinejoin="round"/></Ico> }
function CommsIcon({ size, color })     { return <Ico size={size}><path d="M2 3h12a1 1 0 011 1v7a1 1 0 01-1 1H5L2 14V4a1 1 0 011-1z" stroke={color} strokeWidth="1.2" strokeLinejoin="round"/></Ico> }
function SurvIcon({ size, color })      { return <Ico size={size}><circle cx="8" cy="8" r="6" stroke={color} strokeWidth="1.2"/><circle cx="8" cy="8" r="2" stroke={color} strokeWidth="1.2"/><path d="M8 2V4M8 12V14M2 8H4M12 8H14" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function RiskIcon({ size, color })      { return <Ico size={size}><path d="M2 12L5 8L8 10L11 5L14 7" stroke={color} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></Ico> }
function RiskAlertIcon({ size, color }) { return <Ico size={size}><path d="M8 2L14 13H2L8 2Z" stroke={color} strokeWidth="1.2" strokeLinejoin="round"/><path d="M8 6v3" stroke={color} strokeWidth="1.2" strokeLinecap="round"/><circle cx="8" cy="11" r=".6" fill={color}/><path d="M4 13H2M14 13H12" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function AnalyticsIcon({ size, color }) { return <Ico size={size}><path d="M2 12L5 8L8 10L11 5L14 7" stroke={color} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/><path d="M2 14H14" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function ReportsIcon({ size, color })   { return <Ico size={size}><rect x="3" y="1" width="10" height="14" rx="1" stroke={color} strokeWidth="1.2"/><path d="M6 5H10M6 8H10M6 11H8" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function UsersIcon({ size, color })     { return <Ico size={size}><circle cx="6" cy="5" r="2.5" stroke={color} strokeWidth="1.2"/><path d="M1 13c0-2.76 2.24-4 5-4s5 1.24 5 4" stroke={color} strokeWidth="1.2" strokeLinecap="round"/><path d="M11 3.5a2 2 0 010 4M15 13c0-2-1.5-3.5-4-3.5" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function SettingsIcon({ size, color })  { return <Ico size={size}><circle cx="8" cy="8" r="2.5" stroke={color} strokeWidth="1.2"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.22 3.22l1.41 1.41M11.37 11.37l1.41 1.41M3.22 12.78l1.41-1.41M11.37 4.63l1.41-1.41" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function IntegIcon({ size, color })     { return <Ico size={size}><circle cx="4" cy="8" r="2" stroke={color} strokeWidth="1.2"/><circle cx="12" cy="4" r="2" stroke={color} strokeWidth="1.2"/><circle cx="12" cy="12" r="2" stroke={color} strokeWidth="1.2"/><path d="M6 8H9M10 5.5L6.5 7.5M10 10.5L6.5 8.5" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function LogoutIcon({ size, color })    { return <Ico size={size}><path d="M6 2H3a1 1 0 00-1 1v10a1 1 0 001 1h3" stroke={color} strokeWidth="1.2" strokeLinecap="round"/><path d="M11 11l3-3-3-3" stroke={color} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/><path d="M14 8H6" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function BellIcon({ size, color })     { return <Ico size={size}><path d="M8 1a5 5 0 015 5v3l1 2H2L3 9V6a5 5 0 015-5z" stroke={color} strokeWidth="1.2" strokeLinejoin="round"/><path d="M6 13a2 2 0 004 0" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function MapPinIcon({ size, color })   { return <Ico size={size}><path d="M8 1C5.24 1 3 3.24 3 6c0 4 5 9 5 9s5-5 5-9c0-2.76-2.24-5-5-5z" stroke={color} strokeWidth="1.2" strokeLinejoin="round"/><circle cx="8" cy="6" r="1.5" stroke={color} strokeWidth="1.2"/></Ico> }
function AuditIcon({ size, color })    { return <Ico size={size}><rect x="2" y="1" width="12" height="14" rx="1" stroke={color} strokeWidth="1.2"/><path d="M5 5H11M5 8H11M5 11H8" stroke={color} strokeWidth="1.2" strokeLinecap="round"/><path d="M10 10l1.5 1.5L14 9" stroke={color} strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></Ico> }