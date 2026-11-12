/**
 * Layout.jsx — OryxShield
 * ==================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Responsive shell for all protected pages.
 *
 * Breakpoints (mirrors UIContext):
 *   Mobile  < 768 px  → sidebar hidden, bottom MobileNav shown
 *   Tablet  768–1024  → sidebar auto-collapses to icon-only (64 px)
 *   Desktop > 1024    → full sidebar (240 px) or collapsed (64 px)
 *
 * Main content padding scales with clamp() so pages never feel cramped
 * on small screens or excessively padded on large ones.
 */
import { Suspense } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useUI } from '../../context/UIContext'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import MobileNav from './MobileNav'
import CommandPalette from './CommandPalette'
import ErrorBoundary from '../common/ErrorBoundary'

const PageLoader = () => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
    <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: '#6b7280', letterSpacing: '0.18em', textTransform: 'uppercase' }}>
      LOADING...
    </div>
  </div>
)

export default function Layout() {
  const { sidebarCollapsed, isMobile } = useUI()
  const { key: routeKey } = useLocation()
  const sidebarW = isMobile ? 0 : (sidebarCollapsed ? 64 : 240)

  return (
    <div style={{ minHeight: '100vh', background: '#0a0f1e' }}>
      {/* Sidebar — desktop / tablet only */}
      <Sidebar />

      {/* Fixed topbar — offset by sidebar width */}
      <Topbar />

      {/* ── Main content area ── */}
      <main
        style={{
          marginLeft:     sidebarW,
          marginTop:      56,            // topbar height
          minHeight:      'calc(100vh - 56px)',
          // clamp keeps padding comfortable at every width:
          //   mobile → 16px,  tablet → ~20px,  desktop → 28px
          padding:        'clamp(16px, 2.5vw, 28px)',
          paddingBottom:  isMobile ? 76 : 'clamp(16px, 2.5vw, 28px)',
          transition:     'margin-left 0.22s ease',
          // Prevent horizontal scroll if a page overflows slightly
          overflowX:      'hidden',
        }}
      >
        <ErrorBoundary key={routeKey}>
          <Suspense fallback={<PageLoader />}>
            <Outlet />
          </Suspense>
        </ErrorBoundary>
      </main>

      {/* Mobile bottom nav */}
      {isMobile && <MobileNav />}

      {/* Global command palette — Ctrl+K */}
      <CommandPalette />
    </div>
  )
}