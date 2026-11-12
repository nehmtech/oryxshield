/**
 * PublicLayout — OryxShield
 * ====================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Responsive public shell (header + footer + Outlet).
 *
 * Breakpoints handled via CSS @media in a <style> tag (no Tailwind):
 *   < 640 px  — mobile: hamburger menu, stacked footer, compact padding
 *   640–1024  — tablet: condensed nav, slightly smaller padding
 *   > 1024    — desktop: full nav + footer columns
 *
 * FIX (original): Header checks auth state and shows "Go to Dashboard"
 * when the user is already logged in, instead of always showing "Sign In".
 */

import { useState, useEffect, Suspense } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

const PageLoader = () => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '40vh' }}>
    <div style={{ fontFamily: "'Space Mono', monospace", fontSize: 10, color: '#6b7280', letterSpacing: '0.18em', textTransform: 'uppercase' }}>
      LOADING...
    </div>
  </div>
)

const T = {
  bg:      '#0a0f1e',
  surface: '#111827',
  border:  '#1f2937',
  accent:  '#3b82f6',
  text:    '#f9fafb',
  textSub: '#9ca3af',
  success: '#10b981',
}

const FONTS = {
  heading: "'Bebas Neue', sans-serif",
  mono:    "'Space Mono', monospace",
  body:    "'IBM Plex Sans', sans-serif",
}

const NAV_LINKS = [
  { to: '/',        label: 'Home'    },
  { to: '/about',   label: 'About'   },
  { to: '/contact', label: 'Contact' },
]

// ─── Logo ─────────────────────────────────────────────────────────────────────
function LogoMark({ size = 26 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" style={{ flexShrink: 0 }}>
      <rect x="2" y="2" width="24" height="24" rx="3" stroke={T.accent} strokeWidth="1.5"/>
      <path d="M8 20 L14 8 L20 20" stroke={T.accent} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M10 16 L18 16" stroke={T.accent} strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  )
}

// ─── Header ───────────────────────────────────────────────────────────────────
function PublicHeader() {
  const navigate = useNavigate()
  const { user, logout, loading } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)

  // Close menu on resize to desktop
  useEffect(() => {
    const fn = () => { if (window.innerWidth >= 640) setMenuOpen(false) }
    window.addEventListener('resize', fn, { passive: true })
    return () => window.removeEventListener('resize', fn)
  }, [])

  const handleLogout = async () => {
    setMenuOpen(false)
    await logout()
    navigate('/', { replace: true })
  }

  // Auth-aware CTA button
  const ctaButton = loading ? null : user ? (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <Link
        to="/dashboard"
        onClick={() => setMenuOpen(false)}
        style={{
          fontFamily:    FONTS.mono,
          fontSize:      9,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          padding:       '7px 16px',
          borderRadius:  3,
          background:    T.accent,
          color:         '#fff',
          textDecoration:'none',
          border:        `1px solid ${T.accent}`,
          whiteSpace:    'nowrap',
        }}
      >
        Dashboard →
      </Link>
      <button
        onClick={handleLogout}
        style={{
          fontFamily:    FONTS.mono,
          fontSize:      9,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          padding:       '7px 12px',
          borderRadius:  3,
          background:    'transparent',
          color:         T.textSub,
          border:        `1px solid ${T.border}`,
          cursor:        'pointer',
          whiteSpace:    'nowrap',
        }}
      >
        Logout
      </button>
    </div>
  ) : (
    <Link
      to="/login"
      onClick={() => setMenuOpen(false)}
      style={{
        fontFamily:    FONTS.mono,
        fontSize:      9,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        padding:       '7px 16px',
        borderRadius:  3,
        background:    T.accent,
        color:         '#fff',
        textDecoration:'none',
        border:        `1px solid ${T.accent}`,
        whiteSpace:    'nowrap',
      }}
    >
      Sign In
    </Link>
  )

  return (
    <>
      <style>{`
        /* ── Public header responsive ── */
        .pub-nav-links { display: flex; align-items: center; gap: 4px; }
        .pub-hamburger { display: none; }
        .pub-mobile-menu { display: none; }

        @media (max-width: 639px) {
          .pub-nav-links  { display: none !important; }
          .pub-cta-desktop{ display: none !important; }
          .pub-hamburger  { display: flex !important; }
          .pub-user-badge { display: none !important; }
        }
        .pub-mobile-menu.open {
          display: flex !important;
          flex-direction: column;
          position: fixed;
          top: 60px;
          left: 0; right: 0;
          background: rgba(7,11,23,0.97);
          border-bottom: 1px solid ${T.border};
          padding: 12px 20px 20px;
          gap: 4px;
          z-index: 499;
          backdrop-filter: blur(12px);
        }
      `}</style>

      <header
        style={{
          position:     'sticky',
          top:          0,
          zIndex:       500,
          background:   'rgba(10,15,30,0.92)',
          backdropFilter:'blur(12px)',
          borderBottom: `1px solid ${T.border}`,
        }}
      >
        <div
          style={{
            maxWidth:       1160,
            margin:         '0 auto',
            padding:        '0 clamp(16px, 4vw, 32px)',
            height:         60,
            display:        'flex',
            alignItems:     'center',
            justifyContent: 'space-between',
            gap:            12,
          }}
        >
          {/* Logo */}
          <Link
            to="/"
            style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none', flexShrink: 0 }}
          >
            <LogoMark size={24} />
            <div>
              <div style={{ fontFamily: FONTS.heading, fontSize: 17, color: T.text, letterSpacing: '0.08em', lineHeight: 1 }}>
                ORYXSHIELD
              </div>
              <div style={{ fontFamily: FONTS.mono, fontSize: 7, letterSpacing: '0.16em', color: T.textSub, textTransform: 'uppercase' }}>
                Protocol
              </div>
            </div>
          </Link>

          {/* Desktop nav */}
          <nav className="pub-nav-links">
            {NAV_LINKS.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                style={({ isActive }) => ({
                  fontFamily:    FONTS.mono,
                  fontSize:      9,
                  letterSpacing: '0.12em',
                  textTransform: 'uppercase',
                  padding:       '6px 14px',
                  borderRadius:  3,
                  color:         isActive ? T.text : T.textSub,
                  background:    isActive ? 'rgba(59,130,246,0.1)' : 'transparent',
                  border:        `1px solid ${isActive ? 'rgba(59,130,246,0.3)' : 'transparent'}`,
                  textDecoration:'none',
                  transition:    'all 0.15s',
                })}
              >
                {label}
              </NavLink>
            ))}

            <div style={{ marginLeft: 8 }} className="pub-cta-desktop">
              {ctaButton}
            </div>

            {/* Authenticated user indicator */}
            {!loading && user && (
              <div
                className="pub-user-badge"
                style={{
                  marginLeft:  8,
                  paddingLeft: 12,
                  borderLeft:  `1px solid ${T.border}`,
                  display:     'flex',
                  alignItems:  'center',
                  gap:         6,
                }}
              >
                <div style={{ width: 7, height: 7, borderRadius: '50%', background: T.success, boxShadow: `0 0 8px ${T.success}` }} />
                <span style={{ fontFamily: FONTS.mono, fontSize: 8, letterSpacing: '0.12em', color: T.textSub, textTransform: 'uppercase', whiteSpace: 'nowrap' }}>
                  {user.first_name || user.username || user.email?.split('@')[0]}
                </span>
              </div>
            )}
          </nav>

          {/* Hamburger (mobile) */}
          <button
            className="pub-hamburger"
            onClick={() => setMenuOpen((o) => !o)}
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            style={{
              display:       'none',  // overridden by CSS above
              background:    'none',
              border:        'none',
              cursor:        'pointer',
              padding:       '6px',
              flexDirection: 'column',
              gap:           5,
              flexShrink:    0,
            }}
          >
            {menuOpen
              ? /* X icon */
                <svg width={20} height={20} viewBox="0 0 20 20" fill="none">
                  <path d="M4 4l12 12M16 4L4 16" stroke={T.textSub} strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              : /* Hamburger lines */
                [0, 1, 2].map((i) => (
                  <span key={i} style={{ display: 'block', width: 20, height: 1.5, background: T.textSub, borderRadius: 1 }} />
                ))
            }
          </button>
        </div>

        {/* ── Mobile dropdown menu ── */}
        <div className={`pub-mobile-menu${menuOpen ? ' open' : ''}`}>
          {NAV_LINKS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setMenuOpen(false)}
              style={({ isActive }) => ({
                fontFamily:    FONTS.mono,
                fontSize:      10,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                padding:       '12px 14px',
                borderRadius:  3,
                color:         isActive ? T.text : T.textSub,
                background:    isActive ? 'rgba(59,130,246,0.1)' : 'transparent',
                border:        `1px solid ${isActive ? 'rgba(59,130,246,0.3)' : 'transparent'}`,
                textDecoration:'none',
              })}
            >
              {label}
            </NavLink>
          ))}
          <div style={{ marginTop: 8, paddingTop: 12, borderTop: `1px solid ${T.border}` }}>
            {ctaButton}
          </div>
        </div>
      </header>
    </>
  )
}

// ─── Footer ───────────────────────────────────────────────────────────────────
function PublicFooter() {
  const year = new Date().getFullYear()
  const { user, loading } = useAuth()

  const platformLinks = [
    { to: '/',        label: 'Home'    },
    { to: '/about',   label: 'About'   },
    { to: '/contact', label: 'Contact' },
    ...(!loading
      ? user
        ? [{ to: '/dashboard', label: 'Dashboard' }]
        : [{ to: '/login',     label: 'Sign In'   }]
      : []
    ),
  ]

  return (
    <>
      <style>{`
        .pub-footer-inner {
          display: flex;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 32px;
          margin-bottom: 36px;
        }
        .pub-footer-links-row {
          display: flex;
          gap: 48px;
          flex-wrap: wrap;
        }
        .pub-footer-bottom {
          display: flex;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 12px;
          align-items: center;
        }
        @media (max-width: 639px) {
          .pub-footer-inner { flex-direction: column; gap: 24px; }
          .pub-footer-links-row { gap: 24px; }
          .pub-footer-bottom { flex-direction: column; align-items: flex-start; gap: 8px; }
        }
      `}</style>

      <footer
        style={{
          borderTop:  `1px solid ${T.border}`,
          background: T.surface,
          padding:    'clamp(24px, 4vw, 40px) clamp(16px, 4vw, 32px) clamp(20px, 3vw, 32px)',
        }}
      >
        <div style={{ maxWidth: 1160, margin: '0 auto' }}>
          <div className="pub-footer-inner">
            {/* Brand */}
            <div style={{ maxWidth: 280 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <LogoMark size={20} />
                <span style={{ fontFamily: FONTS.heading, fontSize: 15, color: T.text, letterSpacing: '0.08em' }}>
                  ORYXSHIELD
                </span>
              </div>
              <p style={{ fontFamily: FONTS.body, fontSize: 12, color: T.textSub, lineHeight: 1.7, margin: 0 }}>
                Pandemic surveillance and response infrastructure for public health authorities across Africa.
              </p>
            </div>

            {/* Link groups */}
            <div className="pub-footer-links-row">
              <FooterGroup title="Platform" links={platformLinks} />
              <FooterGroup title="Legal" links={[
                { to: '/privacy', label: 'Privacy Policy'   },
                { to: '/terms',   label: 'Terms of Service' },
              ]} />
            </div>
          </div>

          {/* Bottom bar */}
          <div
            style={{ borderTop: `1px solid ${T.border}`, paddingTop: 20 }}
            className="pub-footer-bottom"
          >
            <span style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.12em', color: T.textSub, textTransform: 'uppercase' }}>
              © {year} OryxShield. All rights reserved.
            </span>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: T.success }} />
              <span style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.1em', color: T.textSub, textTransform: 'uppercase' }}>
                Systems Operational
              </span>
            </div>
          </div>
        </div>
      </footer>
    </>
  )
}

function FooterGroup({ title, links }) {
  return (
    <div>
      <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.14em', textTransform: 'uppercase', color: T.textSub, marginBottom: 14 }}>
        {title}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {links.map(({ to, label }) => (
          <Link
            key={to}
            to={to}
            style={{ fontFamily: FONTS.body, fontSize: 13, color: T.textSub, textDecoration: 'none' }}
          >
            {label}
          </Link>
        ))}
      </div>
    </div>
  )
}

// ─── Layout ───────────────────────────────────────────────────────────────────
export default function PublicLayout() {
  return (
    <div style={{ minHeight: '100vh', background: T.bg, display: 'flex', flexDirection: 'column' }}>
      <PublicHeader />
      <main style={{ flex: 1 }}>
        <Suspense fallback={<PageLoader />}>
          <Outlet />
        </Suspense>
      </main>
      <PublicFooter />
    </div>
  )
}