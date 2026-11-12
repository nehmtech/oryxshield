/**
 * Integrations — shared design tokens & colour maps
 * Extracted to a plain JS file so shared.jsx and tabs can both import
 * without creating circular dependencies.
 */

export const C = {
  bg:        '#070b17',
  bgCard:    '#0d1425',
  bgHover:   'rgba(255,255,255,0.03)',
  border:    '#1a2235',
  borderSub: 'rgba(255,255,255,0.06)',
  accent:    '#3b82f6',
  accentBg:  'rgba(59,130,246,0.10)',
  accentGlow:'rgba(59,130,246,0.18)',
  danger:    '#ef4444',
  success:   '#10b981',
  warning:   '#f59e0b',
  info:      '#06b6d4',
  purple:    '#8b5cf6',
  text:      '#f9fafb',
  textSub:   '#9ca3af',
  textMuted: '#6b7280',
  mono:      'Space Mono, monospace',
  sans:      'IBM Plex Sans, sans-serif',
  display:   'Bebas Neue, sans-serif',
}

export const HEALTH_COLOR = {
  HEALTHY:   C.success,
  DEGRADED:  C.warning,
  UNHEALTHY: C.danger,
  UNKNOWN:   C.textMuted,
}

export const STATUS_COLOR = {
  PENDING:      C.textMuted,
  QUEUED:       C.info,
  RUNNING:      C.accent,
  PAUSED:       C.warning,
  COMPLETED:    C.success,
  FAILED:       C.danger,
  CANCELLED:    C.textMuted,
  RETRYING:     C.warning,
  TRANSFERRING: C.accent,
  VERIFYING:    C.info,
  PARTIAL:      C.warning,
  ROLLED_BACK:  C.danger,
}

export const LOG_COLOR = {
  DEBUG:    C.textMuted,
  INFO:     C.accent,
  WARNING:  C.warning,
  ERROR:    C.danger,
  CRITICAL: '#ff2d55',
}