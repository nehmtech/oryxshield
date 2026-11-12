import { Component } from 'react'

const C = {
  bg:      '#070b17',
  surface: '#111827',
  border:  '#1f2937',
  text:    '#f9fafb',
  muted:   '#6b7280',
  accent:  '#3b82f6',
  danger:  '#ef4444',
}

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    if (import.meta.env.DEV) console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (!this.state.hasError) return this.props.children

    const isDev = import.meta.env.DEV

    return (
      <div style={{
        minHeight:      '60vh',
        display:        'flex',
        flexDirection:  'column',
        alignItems:     'center',
        justifyContent: 'center',
        padding:        '40px 24px',
        background:     C.bg,
      }}>
        <div style={{
          background:   C.surface,
          border:       `1px solid ${C.danger}30`,
          borderRadius: 8,
          padding:      '32px 40px',
          maxWidth:     540,
          width:        '100%',
          textAlign:    'center',
        }}>
          <div style={{
            width:        40,
            height:       40,
            borderRadius: '50%',
            background:   `${C.danger}18`,
            border:       `1px solid ${C.danger}40`,
            display:      'flex',
            alignItems:   'center',
            justifyContent: 'center',
            margin:       '0 auto 20px',
            fontSize:     20,
          }}>
            ⚠
          </div>

          <h2 style={{
            fontFamily:    'Bebas Neue, sans-serif',
            fontSize:      26,
            letterSpacing: '0.06em',
            color:         C.text,
            margin:        '0 0 10px',
          }}>
            Something went wrong
          </h2>

          <p style={{
            fontFamily: 'IBM Plex Sans, sans-serif',
            fontSize:   13,
            color:      C.muted,
            margin:     '0 0 24px',
            lineHeight: 1.6,
          }}>
            This section encountered an unexpected error. Refreshing the page usually resolves this.
          </p>

          {isDev && this.state.error && (
            <pre style={{
              fontFamily:  'Space Mono, monospace',
              fontSize:    10,
              color:       C.danger,
              background:  `${C.danger}08`,
              border:      `1px solid ${C.danger}20`,
              borderRadius: 4,
              padding:     '12px 14px',
              textAlign:   'left',
              overflowX:   'auto',
              whiteSpace:  'pre-wrap',
              wordBreak:   'break-word',
              marginBottom: 24,
            }}>
              {this.state.error.toString()}
            </pre>
          )}

          <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={{
                background:   C.accent,
                border:       'none',
                borderRadius: 4,
                color:        C.text,
                fontFamily:   'Space Mono, monospace',
                fontSize:     10,
                letterSpacing:'0.1em',
                textTransform:'uppercase',
                padding:      '10px 20px',
                cursor:       'pointer',
              }}
            >
              Reload page
            </button>
            <button
              type="button"
              onClick={() => this.setState({ hasError: false, error: null })}
              style={{
                background:   'transparent',
                border:       `1px solid ${C.border}`,
                borderRadius: 4,
                color:        C.muted,
                fontFamily:   'Space Mono, monospace',
                fontSize:     10,
                letterSpacing:'0.1em',
                textTransform:'uppercase',
                padding:      '10px 20px',
                cursor:       'pointer',
              }}
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    )
  }
}
