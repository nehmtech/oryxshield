/**
 * CommandPalette — OryxShield
 * =====================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Triggered by Ctrl+K (or Cmd+K on Mac).
 * Role-aware navigation list with fuzzy text filter.
 * Keyboard navigation: ↑↓ to move, Enter to navigate, Esc to close.
 */
import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

const C = {
  overlay:     'rgba(7,11,23,0.82)',
  surface:     '#0f1729',
  surfaceHigh: '#151e2e',
  border:      '#1f2937',
  accent:      '#3b82f6',
  text:        '#f9fafb',
  textSub:     '#9ca3af',
  textMuted:   '#6b7280',
}

// Full navigation map (mirrors Sidebar PORTALS)
const ALL_ITEMS = [
  { to: '/dashboard',                        label: 'Dashboard',           group: 'Command',       roles: ['admin','coordinator','field_officer','analyst','public'] },
  { to: '/dashboard/alerts',                 label: 'Alerts',              group: 'Command',       roles: ['admin','coordinator','field_officer','analyst'] },
  { to: '/dashboard/surveillance',           label: 'Surveillance',        group: 'Intelligence',  roles: ['admin','analyst'] },
  { to: '/dashboard/risk',                   label: 'Risk Assessment',     group: 'Intelligence',  roles: ['admin','analyst'] },
  { to: '/dashboard/risk/alerts',            label: 'Risk Alerts',         group: 'Intelligence',  roles: ['admin','analyst'] },
  { to: '/dashboard/response',               label: 'Response',            group: 'Response',      roles: ['admin','coordinator'] },
  { to: '/dashboard/coordination',           label: 'Coordination',        group: 'Response',      roles: ['admin','coordinator'] },
  { to: '/dashboard/resources',              label: 'Resources',           group: 'Response',      roles: ['admin','coordinator','field_officer'] },
  { to: '/dashboard/resources/requests',     label: 'Resource Requests',   group: 'Response',      roles: ['admin','coordinator','field_officer'] },
  { to: '/dashboard/operations',             label: 'Operations',          group: 'Response',      roles: ['admin','coordinator','field_officer'] },
  { to: '/dashboard/communications',         label: 'Communications',      group: 'Comms',         roles: ['admin','coordinator'] },
  { to: '/dashboard/communications/compose', label: 'Compose Message',     group: 'Comms',         roles: ['admin','coordinator'] },
  { to: '/dashboard/analytics',             label: 'Analytics',           group: 'Analytics',     roles: ['admin','analyst'] },
  { to: '/dashboard/analytics/reports',     label: 'Reports',             group: 'Analytics',     roles: ['admin','analyst'] },
  { to: '/dashboard/integrations',          label: 'Integrations',        group: 'System',        roles: ['admin'] },
  { to: '/dashboard/admin/users',           label: 'User Management',     group: 'System',        roles: ['admin'] },
  { to: '/dashboard/admin/settings',        label: 'System Settings',     group: 'System',        roles: ['admin'] },
  { to: '/dashboard/profile',               label: 'My Profile',          group: 'Account',       roles: ['admin','coordinator','field_officer','analyst','public'] },
]

function fuzzy(label, query) {
  if (!query) return true
  const q = query.toLowerCase()
  const l = label.toLowerCase()
  // Simple: all query chars appear in order
  let qi = 0
  for (let i = 0; i < l.length && qi < q.length; i++) {
    if (l[i] === q[qi]) qi++
  }
  return qi === q.length
}

function highlight(label, query) {
  if (!query) return <span>{label}</span>
  const q = query.toLowerCase()
  const l = label.toLowerCase()
  const chars = []
  let qi = 0
  for (let i = 0; i < label.length; i++) {
    if (qi < q.length && l[i] === q[qi]) {
      chars.push(<mark key={i} style={{ background: 'transparent', color: C.accent, fontWeight: 700 }}>{label[i]}</mark>)
      qi++
    } else {
      chars.push(label[i])
    }
  }
  return <span>{chars}</span>
}

export default function CommandPalette() {
  const [open, setOpen]     = useState(false)
  const [query, setQuery]   = useState('')
  const [cursor, setCursor] = useState(0)
  const inputRef            = useRef(null)
  const listRef             = useRef(null)
  const navigate            = useNavigate()
  const { user }            = useAuth()
  const role                = user?.role || 'public'

  const items = useMemo(() => {
    const accessible = ALL_ITEMS.filter(it => it.roles.includes(role))
    return accessible.filter(it => fuzzy(it.label, query))
  }, [role, query])

  const openPalette = useCallback(() => {
    setQuery('')
    setCursor(0)
    setOpen(true)
  }, [])

  const closePalette = useCallback(() => {
    setOpen(false)
    setQuery('')
    setCursor(0)
  }, [])

  const go = useCallback((item) => {
    navigate(item.to)
    closePalette()
  }, [navigate, closePalette])

  // Global Ctrl+K / Cmd+K listener
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(prev => {
          if (prev) { closePalette(); return false }
          openPalette(); return true
        })
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [openPalette, closePalette])

  // Focus input when opened
  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [open])

  // Clamp cursor when list shrinks
  useEffect(() => {
    setCursor(c => Math.min(c, Math.max(0, items.length - 1)))
  }, [items.length])

  // Scroll active item into view
  useEffect(() => {
    if (!listRef.current) return
    const el = listRef.current.children[cursor]
    el?.scrollIntoView({ block: 'nearest' })
  }, [cursor])

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown')  { e.preventDefault(); setCursor(c => Math.min(c + 1, items.length - 1)) }
    if (e.key === 'ArrowUp')    { e.preventDefault(); setCursor(c => Math.max(c - 1, 0)) }
    if (e.key === 'Enter')      { if (items[cursor]) go(items[cursor]) }
    if (e.key === 'Escape')     { closePalette() }
  }

  if (!open) return null

  // Group consecutive items
  const grouped = []
  let lastGroup = null
  for (const item of items) {
    if (item.group !== lastGroup) {
      grouped.push({ type: 'header', label: item.group })
      lastGroup = item.group
    }
    grouped.push({ type: 'item', item })
  }

  // Build flat item index for cursor mapping
  const flatItems = grouped.filter(g => g.type === 'item').map(g => g.item)

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={closePalette}
        style={{
          position: 'fixed', inset: 0,
          background: C.overlay,
          zIndex: 900,
          backdropFilter: 'blur(2px)',
        }}
        aria-hidden="true"
      />

      {/* Palette modal */}
      <div
        role="dialog"
        aria-label="Command palette"
        aria-modal="true"
        style={{
          position:     'fixed',
          top:          '18vh',
          left:         '50%',
          transform:    'translateX(-50%)',
          width:        'min(560px, calc(100vw - 32px))',
          background:   C.surface,
          border:       `1px solid ${C.border}`,
          borderRadius: 8,
          boxShadow:    '0 24px 80px rgba(0,0,0,0.7)',
          zIndex:       901,
          overflow:     'hidden',
          display:      'flex',
          flexDirection:'column',
          maxHeight:    '60vh',
        }}
      >
        {/* Search input row */}
        <div style={{
          display:      'flex',
          alignItems:   'center',
          gap:          10,
          padding:      '12px 16px',
          borderBottom: `1px solid ${C.border}`,
          flexShrink:   0,
        }}>
          {/* Search icon */}
          <svg width={14} height={14} viewBox="0 0 16 16" fill="none" aria-hidden="true" style={{ flexShrink: 0, opacity: 0.5 }}>
            <circle cx="6.5" cy="6.5" r="4.5" stroke={C.text} strokeWidth="1.4"/>
            <path d="M10 10l3.5 3.5" stroke={C.text} strokeWidth="1.4" strokeLinecap="round"/>
          </svg>
          <input
            ref={inputRef}
            value={query}
            onChange={e => { setQuery(e.target.value); setCursor(0) }}
            onKeyDown={onKeyDown}
            placeholder="Go to page…"
            aria-label="Search pages"
            style={{
              flex:        1,
              background:  'none',
              border:      'none',
              outline:     'none',
              fontFamily:  'IBM Plex Sans, sans-serif',
              fontSize:    14,
              color:       C.text,
              caretColor:  C.accent,
            }}
          />
          <kbd style={{
            fontFamily:  'Space Mono, monospace',
            fontSize:     8,
            color:        C.textMuted,
            border:       `1px solid ${C.border}`,
            borderRadius: 3,
            padding:      '2px 5px',
            letterSpacing:'0.08em',
          }}>ESC</kbd>
        </div>

        {/* Results list */}
        <div
          ref={listRef}
          role="listbox"
          aria-label="Navigation options"
          style={{ overflowY: 'auto', flex: 1 }}
        >
          {items.length === 0 ? (
            <div style={{ padding: '28px 16px', textAlign: 'center' }}>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.14em', textTransform: 'uppercase', color: C.textMuted }}>
                No results
              </span>
            </div>
          ) : (
            grouped.map((entry, gi) => {
              if (entry.type === 'header') {
                return (
                  <div key={`h-${entry.label}`} style={{
                    padding:     '8px 16px 4px',
                    fontFamily:  'Space Mono, monospace',
                    fontSize:    8,
                    letterSpacing:'0.15em',
                    textTransform:'uppercase',
                    color:       C.textMuted,
                  }}>
                    {entry.label}
                  </div>
                )
              }
              const itemIdx = flatItems.indexOf(entry.item)
              const active  = itemIdx === cursor
              return (
                <button
                  key={entry.item.to}
                  role="option"
                  aria-selected={active}
                  onClick={() => go(entry.item)}
                  onMouseEnter={() => setCursor(itemIdx)}
                  style={{
                    width:       '100%',
                    display:     'flex',
                    alignItems:  'center',
                    justifyContent: 'space-between',
                    gap:         12,
                    padding:     '9px 16px',
                    background:  active ? C.surfaceHigh : 'transparent',
                    border:      'none',
                    borderLeft:  active ? `2px solid ${C.accent}` : '2px solid transparent',
                    cursor:      'pointer',
                    textAlign:   'left',
                    transition:  'background 0.1s',
                  }}
                >
                  <span style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: C.text }}>
                    {highlight(entry.item.label, query)}
                  </span>
                  {active && (
                    <kbd style={{
                      fontFamily:  'Space Mono, monospace',
                      fontSize:    8,
                      color:       C.textMuted,
                      border:      `1px solid ${C.border}`,
                      borderRadius: 3,
                      padding:     '1px 5px',
                      letterSpacing:'0.08em',
                      flexShrink:  0,
                    }}>↵</kbd>
                  )}
                </button>
              )
            })
          )}
        </div>

        {/* Footer hint */}
        <div style={{
          padding:     '8px 16px',
          borderTop:   `1px solid ${C.border}`,
          display:     'flex',
          gap:         16,
          flexShrink:  0,
        }}>
          {[['↑↓', 'navigate'], ['↵', 'go'], ['esc', 'close']].map(([key, desc]) => (
            <span key={key} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <kbd style={{ fontFamily: 'Space Mono, monospace', fontSize: 7, color: C.textMuted, border: `1px solid ${C.border}`, borderRadius: 2, padding: '1px 4px' }}>{key}</kbd>
              <span style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 10, color: C.textMuted }}>{desc}</span>
            </span>
          ))}
        </div>
      </div>
    </>
  )
}
