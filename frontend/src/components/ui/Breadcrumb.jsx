/**
 * Breadcrumb — OryxShield
 * Company : NEHMTECH INNOVATIONS LIMITED
 */
import { useNavigate } from 'react-router-dom'

const C = {
  accent:    '#3b82f6',
  textSub:   '#9ca3af',
  textMuted: '#6b7280',
}

/**
 * @param {{ items: Array<{ label: string, to?: string }> }} props
 * items: ordered list of crumbs; last one is current page (no link needed)
 */
export default function Breadcrumb({ items = [] }) {
  const navigate = useNavigate()
  return (
    <nav aria-label="Breadcrumb" style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: 20, flexWrap: 'wrap' }}>
      {items.map((crumb, i) => {
        const isLast = i === items.length - 1
        return (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
            {crumb.to && !isLast ? (
              <button
                onClick={() => navigate(crumb.to)}
                style={{
                  background:  'none',
                  border:      'none',
                  cursor:      'pointer',
                  padding:     0,
                  fontFamily:  'IBM Plex Sans, sans-serif',
                  fontSize:    12,
                  color:       C.accent,
                  letterSpacing: '0.01em',
                }}
                onMouseEnter={e => e.currentTarget.style.textDecoration = 'underline'}
                onMouseLeave={e => e.currentTarget.style.textDecoration = 'none'}
              >
                {crumb.label}
              </button>
            ) : (
              <span style={{
                fontFamily:  'IBM Plex Sans, sans-serif',
                fontSize:    12,
                color:       isLast ? C.textSub : C.accent,
                letterSpacing: '0.01em',
              }}>
                {crumb.label}
              </span>
            )}
            {!isLast && (
              <span style={{
                margin:     '0 6px',
                color:      C.textMuted,
                fontSize:   10,
                userSelect: 'none',
              }} aria-hidden="true">
                /
              </span>
            )}
          </span>
        )
      })}
    </nav>
  )
}
