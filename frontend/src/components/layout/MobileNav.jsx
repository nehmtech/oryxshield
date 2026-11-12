/**
 * MobileNav — OryxShield
 * ================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Bottom navigation bar — mobile only (< 768 px).
 *
 * Improvements over original:
 *  - env(safe-area-inset-bottom) padding for iOS home bar / notched devices
 *  - Height accounts for safe area so content isn't clipped on iPhone
 *  - Active indicator uses a top border stripe rather than just colour
 *  - Touch target minimum 44 px per WCAG (achieved via flex stretch)
 *  - Labels hidden on very small screens (< 360 px) to prevent wrapping
 */
import { NavLink } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

const C = {
  bg:     '#070b17',
  border: '#1f2937',
  accent: '#3b82f6',
  sub:    '#6b7280',
  text:   '#f9fafb',
}

// Base nav items — visible to everyone
const BASE_TABS = [
  { to: '/dashboard',              label: 'Home',     icon: HomeIcon,     end: true  },
  { to: '/dashboard/alerts',       label: 'Alerts',   icon: AlertIcon,    end: true  },
  { to: '/dashboard/surveillance', label: 'Monitor',  icon: RadarIcon,    end: false },
  { to: '/dashboard/response',     label: 'Response', icon: ResponseIcon, end: false },
  { to: '/dashboard/profile',      label: 'Profile',  icon: ProfileIcon,  end: true  },
]

// Extra tab shown only to admin
const ADMIN_TAB = {
  to: '/dashboard/admin/users', label: 'Admin', icon: AdminIcon, end: false,
}

export default function MobileNav() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  // Admins get an extra tab; keep total ≤ 5 to avoid overcrowding
  // by swapping Profile to the last position
  const tabs = isAdmin
    ? [...BASE_TABS.slice(0, 4), ADMIN_TAB]
    : BASE_TABS

  return (
    <>
      {/* Compensate for fixed bar height (60 + safe area) in layout */}
      <style>{`
        @supports (padding-bottom: env(safe-area-inset-bottom)) {
          .ls-mobile-nav {
            padding-bottom: env(safe-area-inset-bottom) !important;
            height: calc(60px + env(safe-area-inset-bottom)) !important;
          }
        }
        /* Hide label text on very narrow phones */
        @media (max-width: 359px) {
          .ls-mobile-nav .ls-nav-label { display: none !important; }
        }
      `}</style>

      <nav
        className="ls-mobile-nav"
        style={{
          position:   'fixed',
          bottom:     0,
          left:       0,
          right:      0,
          height:     60,
          background: C.bg,
          borderTop:  `1px solid ${C.border}`,
          display:    'flex',
          alignItems: 'stretch',
          zIndex:     100,
        }}
      >
        {tabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            style={({ isActive }) => ({
              flex:           1,
              display:        'flex',
              flexDirection:  'column',
              alignItems:     'center',
              justifyContent: 'center',
              gap:            3,
              textDecoration: 'none',
              color:          isActive ? C.accent : C.sub,
              // Top border stripe for active state
              borderTop:      isActive ? `2px solid ${C.accent}` : `2px solid transparent`,
              // Touch-friendly: full height is the touch target
              transition:     'color 0.15s, border-color 0.15s',
              paddingBottom:  2,
              WebkitTapHighlightColor: 'transparent',
            })}
          >
            {({ isActive }) => (
              <>
                <tab.icon size={19} color={isActive ? C.accent : C.sub} />
                <span
                  className="ls-nav-label"
                  style={{
                    fontFamily:    'Space Mono, monospace',
                    fontSize:      7,
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                    lineHeight:    1,
                  }}
                >
                  {tab.label}
                </span>
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </>
  )
}

// ─── Icons ────────────────────────────────────────────────────────────────────
function Ico({ size, children }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      style={{ flexShrink: 0 }}
    >
      {children}
    </svg>
  )
}

function HomeIcon({ size, color }) {
  return (
    <Ico size={size}>
      <rect x="1" y="7" width="14" height="8" rx="1" stroke={color} strokeWidth="1.2"/>
      <path d="M1 7L8 2L15 7" stroke={color} strokeWidth="1.2" strokeLinejoin="round"/>
    </Ico>
  )
}
function AlertIcon({ size, color }) {
  return (
    <Ico size={size}>
      <path d="M8 2L14 13H2L8 2Z" stroke={color} strokeWidth="1.2" strokeLinejoin="round"/>
      <path d="M8 6V9" stroke={color} strokeWidth="1.2" strokeLinecap="round"/>
      <circle cx="8" cy="11" r=".6" fill={color}/>
    </Ico>
  )
}
function RadarIcon({ size, color }) {
  return (
    <Ico size={size}>
      <circle cx="8" cy="8" r="6" stroke={color} strokeWidth="1.2"/>
      <circle cx="8" cy="8" r="2" stroke={color} strokeWidth="1.2"/>
      <path d="M8 2V4M8 12V14M2 8H4M12 8H14" stroke={color} strokeWidth="1.2" strokeLinecap="round"/>
    </Ico>
  )
}
function ResponseIcon({ size, color }) {
  return (
    <Ico size={size}>
      <circle cx="8" cy="8" r="6" stroke={color} strokeWidth="1.2"/>
      <path d="M8 5V8L10 10" stroke={color} strokeWidth="1.2" strokeLinecap="round"/>
    </Ico>
  )
}
function ProfileIcon({ size, color }) {
  return (
    <Ico size={size}>
      <circle cx="8" cy="5" r="3" stroke={color} strokeWidth="1.2"/>
      <path d="M2 14c0-3.31 2.69-5 6-5s6 1.69 6 5" stroke={color} strokeWidth="1.2" strokeLinecap="round"/>
    </Ico>
  )
}
function AdminIcon({ size, color }) {
  return (
    <Ico size={size}>
      <circle cx="8" cy="5" r="2.5" stroke={color} strokeWidth="1.2"/>
      <path d="M3 13c0-2.76 2.24-4 5-4h0" stroke={color} strokeWidth="1.2" strokeLinecap="round"/>
      <circle cx="11.5" cy="11.5" r="2" stroke={color} strokeWidth="1.2"/>
      <path d="M11.5 10v1.5l1 1" stroke={color} strokeWidth="1.2" strokeLinecap="round"/>
    </Ico>
  )
}