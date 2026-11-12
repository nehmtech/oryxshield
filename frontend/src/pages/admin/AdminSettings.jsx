/**
 * AdminSettings — OryxShield
 * =====================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * API alignment
 * -------------
 * GET  /configurations/by_category/         → coreApi.configByCategory()
 * GET  /configurations/?category=&search=   → coreApi.listConfigurations(params)
 * POST /configurations/                     → coreApi.createConfiguration(data)
 * PATCH /configurations/{id}/              → coreApi.updateConfiguration(id, data)
 * DELETE /configurations/{id}/             → coreApi.deleteConfiguration(id)
 * POST /configurations/{id}/toggle_active/ → coreApi.toggleConfigActive(id)
 *
 * Backend notes
 * -------------
 * - SystemConfiguration.value is a JSONField (any JSON type: string, number, bool, object)
 * - SystemConfigurationSerializer masks is_sensitive values as "***SENSITIVE***"
 * - SystemConfigurationWriteSerializer validates key must be UPPER_CASE
 * - Permission: read = any authenticated; write = is_staff only
 * - Categories from model: general, security, notifications, integrations,
 *   surveillance, response, ml, performance, features, compliance
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { coreApi, extractError } from '../../services/api'
import { useToast } from '../../context/ToastContext'

// ─── Keyframes ────────────────────────────────────────────────────────────────
const STYLES = `
  @keyframes as-fadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes as-shimmer {
    0%   { background-position: -200% 0; }
    100% { background-position:  200% 0; }
  }
  @keyframes as-spin {
    from { transform: rotate(0deg); }
    to   { transform: rotate(360deg); }
  }
`

// ─── Design tokens ─────────────────────────────────────────────────────────────
const T = {
  bg:        '#0a0f1e',
  surface:   '#111827',
  surfaceHi: '#151e2e',
  border:    '#1f2937',
  accent:    '#3b82f6',
  danger:    '#ef4444',
  warning:   '#f59e0b',
  success:   '#10b981',
  text:      '#f9fafb',
  textSub:   '#9ca3af',
  textMuted: '#6b7280',
}

const CATEGORY_COLORS = {
  general:       '#9ca3af',
  security:      '#ef4444',
  notifications: '#f59e0b',
  integrations:  '#8b5cf6',
  surveillance:  '#06b6d4',
  response:      '#f97316',
  ml:            '#ec4899',
  performance:   '#10b981',
  features:      '#3b82f6',
  compliance:    '#a78bfa',
}

const ALL_CATEGORIES = [
  'general', 'security', 'notifications', 'integrations',
  'surveillance', 'response', 'ml', 'performance', 'features', 'compliance',
]

// ─── Helpers ──────────────────────────────────────────────────────────────────

function Shimmer({ height = 14, style = {} }) {
  return (
    <div style={{
      height, borderRadius: 2,
      background: `linear-gradient(90deg,${T.surface} 25%,${T.surfaceHi} 50%,${T.surface} 75%)`,
      backgroundSize: '200% 100%',
      animation: 'as-shimmer 1.5s infinite',
      ...style,
    }} />
  )
}

function Spinner({ size = 12, color = '#fff' }) {
  return (
    <span style={{
      display: 'inline-block', width: size, height: size,
      border: `2px solid rgba(255,255,255,0.15)`,
      borderTopColor: color,
      borderRadius: '50%',
      animation: 'as-spin 0.7s linear infinite',
      flexShrink: 0,
    }} />
  )
}

function Badge({ label, color = T.textMuted }) {
  return (
    <span style={{
      fontFamily: 'Space Mono, monospace',
      fontSize: 9, letterSpacing: '0.12em',
      textTransform: 'uppercase',
      padding: '2px 8px', borderRadius: 2,
      background: `${color}18`,
      border: `1px solid ${color}30`,
      color,
    }}>
      {label}
    </span>
  )
}

// Parse value from string input back to JSON-compatible type
function parseValue(raw) {
  const s = raw.trim()
  if (s === 'true')  return true
  if (s === 'false') return false
  if (s === 'null')  return null
  const n = Number(s)
  if (s !== '' && !isNaN(n)) return n
  try { return JSON.parse(s) } catch { return s }
}

// Display value for editing — stringify objects/arrays, keep primitives as string
function displayValue(v) {
  if (v === null || v === undefined) return ''
  if (typeof v === 'object') return JSON.stringify(v, null, 2)
  return String(v)
}

function valueType(v) {
  if (v === null) return 'null'
  if (Array.isArray(v)) return 'array'
  return typeof v
}

// ─── ConfigCard ───────────────────────────────────────────────────────────────

function ConfigCard({ config, onSave, onDelete, onToggleActive }) {
  const toast = useToast()
  const [rawValue,  setRawValue]  = useState(displayValue(config.value))
  const [saving,    setSaving]    = useState(false)
  const [toggling,  setToggling]  = useState(false)
  const [deleting,  setDeleting]  = useState(false)
  const [saved,     setSaved]     = useState(false)
  const [cardErr,   setCardErr]   = useState(null)
  const [showDel,   setShowDel]   = useState(false)

  // Track original so dirty check works after external updates
  const originalRef = useRef(displayValue(config.value))
  useEffect(() => {
    const d = displayValue(config.value)
    originalRef.current = d
    setRawValue(d)
    setSaved(false)
    setCardErr(null)
  }, [config.value])

  const dirty = rawValue !== originalRef.current
  const isSensitive = config.is_sensitive
  const isActive = config.is_active

  // Multi-line for objects/arrays, single line for primitives
  const isMultiLine = rawValue.includes('\n') || rawValue.startsWith('{') || rawValue.startsWith('[')

  const handleSave = async () => {
    setSaving(true)
    setSaved(false)
    setCardErr(null)
    try {
      const parsed = parseValue(rawValue)
      await onSave(config.id, parsed)
      originalRef.current = displayValue(parsed)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (err) {
      const msg = extractError(err)
      setCardErr(msg)
      toast.error(msg)
    } finally {
      setSaving(false)
    }
  }

  const handleToggle = async () => {
    setToggling(true)
    try {
      await onToggleActive(config.id)
    } catch (err) {
      toast.error(extractError(err))
    } finally {
      setToggling(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await onDelete(config.id)
      toast.success(`Configuration "${config.key}" deleted`)
    } catch (err) {
      toast.error(extractError(err))
      setDeleting(false)
      setShowDel(false)
    }
  }

  const borderColor = saved
    ? `${T.success}50`
    : cardErr
    ? `${T.danger}40`
    : !isActive
    ? `${T.border}80`
    : T.border

  return (
    <div style={{
      background: isActive ? T.surface : `${T.surface}88`,
      border: `1px solid ${borderColor}`,
      borderRadius: 6,
      padding: '18px 20px',
      transition: 'border-color 0.25s, opacity 0.2s',
      opacity: isActive ? 1 : 0.7,
      display: 'flex', flexDirection: 'column', gap: 10,
    }}>
      {/* Key + badges row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ minWidth: 0 }}>
          <span style={{
            fontFamily: 'Space Mono, monospace',
            fontSize: 10, letterSpacing: '0.12em',
            textTransform: 'uppercase',
            color: T.accent, display: 'block', marginBottom: 3,
            wordBreak: 'break-all',
          }}>
            {config.key}
          </span>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            <Badge
              label={valueType(config.value)}
              color={T.textMuted}
            />
            {isSensitive && <Badge label="sensitive" color={T.warning} />}
            {!isActive   && <Badge label="inactive"  color={T.textMuted} />}
          </div>
        </div>
        {/* Toggle active */}
        <button
          onClick={handleToggle}
          disabled={toggling}
          title={isActive ? 'Deactivate' : 'Activate'}
          style={{
            background: isActive ? `${T.success}12` : `${T.border}50`,
            border: `1px solid ${isActive ? `${T.success}30` : T.border}`,
            color: isActive ? T.success : T.textMuted,
            borderRadius: 3,
            padding: '3px 8px',
            fontSize: 10,
            fontFamily: 'Space Mono, monospace',
            letterSpacing: '0.1em',
            cursor: toggling ? 'wait' : 'pointer',
            display: 'flex', alignItems: 'center', gap: 4,
            flexShrink: 0,
            transition: 'all 0.15s',
          }}
        >
          {toggling ? <Spinner size={9} color={T.textMuted} /> : null}
          {isActive ? 'ON' : 'OFF'}
        </button>
      </div>

      {/* Value input — sensitive masked, otherwise editable */}
      {isSensitive ? (
        <div style={{
          background: `${T.warning}08`,
          border: `1px solid ${T.warning}20`,
          borderRadius: 3, padding: '8px 12px',
          fontFamily: 'Space Mono, monospace',
          fontSize: 11, color: T.warning, letterSpacing: '0.1em',
        }}>
          ***SENSITIVE*** — edit via Django admin
        </div>
      ) : isMultiLine ? (
        <textarea
          value={rawValue}
          onChange={e => { setRawValue(e.target.value); setCardErr(null); setSaved(false) }}
          rows={4}
          style={{
            background: T.bg,
            border: `1px solid ${cardErr ? `${T.danger}60` : T.border}`,
            borderRadius: 4, color: T.text,
            fontFamily: 'Space Mono, monospace', fontSize: 11,
            padding: '8px 12px', outline: 'none', resize: 'vertical',
            width: '100%', boxSizing: 'border-box',
            transition: 'border-color 0.15s', lineHeight: 1.5,
          }}
          onFocus={e => { if (!cardErr) e.target.style.borderColor = T.accent }}
          onBlur={e => { if (!cardErr) e.target.style.borderColor = T.border }}
        />
      ) : (
        <input
          value={rawValue}
          onChange={e => { setRawValue(e.target.value); setCardErr(null); setSaved(false) }}
          style={{
            background: T.bg,
            border: `1px solid ${cardErr ? `${T.danger}60` : T.border}`,
            borderRadius: 4, color: T.text,
            fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
            padding: '8px 12px', outline: 'none',
            width: '100%', boxSizing: 'border-box',
            transition: 'border-color 0.15s',
          }}
          onFocus={e => { if (!cardErr) e.target.style.borderColor = T.accent }}
          onBlur={e => { if (!cardErr) e.target.style.borderColor = T.border }}
        />
      )}

      {/* Description */}
      {config.description && (
        <p style={{
          margin: 0, fontFamily: 'IBM Plex Sans, sans-serif',
          fontSize: 11, color: T.textMuted, lineHeight: 1.5,
        }}>
          {config.description}
        </p>
      )}

      {/* Default value hint */}
      {config.default_value !== null && config.default_value !== undefined && (
        <div style={{
          fontFamily: 'Space Mono, monospace', fontSize: 9,
          color: T.textMuted, letterSpacing: '0.1em',
        }}>
          Default: {displayValue(config.default_value)}
        </div>
      )}

      {/* Footer */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ fontSize: 11, fontFamily: 'IBM Plex Sans, sans-serif' }}>
          {cardErr && <span style={{ color: T.danger }}>{cardErr}</span>}
          {saved   && <span style={{ color: T.success }}>✓ Saved</span>}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {/* Delete with inline confirm */}
          {!isSensitive && (
            showDel ? (
              <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                <span style={{
                  fontFamily: 'Space Mono, monospace', fontSize: 9,
                  color: T.danger, letterSpacing: '0.1em',
                }}>
                  Sure?
                </span>
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  style={{
                    background: `${T.danger}18`, border: `1px solid ${T.danger}40`,
                    color: T.danger, borderRadius: 3, padding: '4px 8px',
                    fontSize: 11, fontFamily: 'IBM Plex Sans, sans-serif',
                    cursor: deleting ? 'wait' : 'pointer',
                    display: 'flex', alignItems: 'center', gap: 4,
                  }}
                >
                  {deleting ? <Spinner size={9} color={T.danger} /> : null}
                  Delete
                </button>
                <button
                  onClick={() => setShowDel(false)}
                  style={{
                    background: 'transparent', border: `1px solid ${T.border}`,
                    color: T.textMuted, borderRadius: 3, padding: '4px 8px',
                    fontSize: 11, fontFamily: 'IBM Plex Sans, sans-serif',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowDel(true)}
                style={{
                  background: 'transparent', border: `1px solid ${T.border}`,
                  color: T.textMuted, borderRadius: 3, padding: '5px 10px',
                  fontSize: 11, fontFamily: 'IBM Plex Sans, sans-serif',
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = `${T.danger}50`; e.currentTarget.style.color = T.danger }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.color = T.textMuted }}
              >
                Delete
              </button>
            )
          )}

          {/* Save */}
          {!isSensitive && (
            <button
              onClick={handleSave}
              disabled={saving || !dirty}
              style={{
                background: saving ? `${T.accent}20` : dirty ? T.accent : `${T.border}80`,
                border: `1px solid ${dirty ? T.accent : T.border}`,
                color: dirty ? '#fff' : T.textMuted,
                borderRadius: 4, padding: '5px 14px',
                fontSize: 12, fontFamily: 'IBM Plex Sans, sans-serif', fontWeight: 500,
                cursor: saving || !dirty ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s',
                display: 'flex', alignItems: 'center', gap: 5,
              }}
            >
              {saving ? <Spinner size={10} /> : null}
              {saving ? 'Saving…' : 'Save'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Create Config Modal ───────────────────────────────────────────────────────

function CreateModal({ onClose, onCreate }) {
  const toast = useToast()
  const [key,         setKey]         = useState('')
  const [value,       setValue]       = useState('')
  const [description, setDescription] = useState('')
  const [category,    setCategory]    = useState('general')
  const [isSensitive, setIsSensitive] = useState(false)
  const [saving,      setSaving]      = useState(false)
  const [errors,      setErrors]      = useState({})

  const validate = () => {
    const e = {}
    if (!key.trim())    e.key = 'Key is required'
    if (!/^[A-Z0-9_]+$/.test(key.trim())) e.key = 'Key must be UPPER_CASE (letters, digits, underscores only)'
    if (value.trim() === '') e.value = 'Value is required'
    return e
  }

  const handleCreate = async () => {
    const e = validate()
    if (Object.keys(e).length) { setErrors(e); return }
    setSaving(true)
    try {
      await onCreate({
        key: key.trim(),
        value: parseValue(value),
        description: description.trim(),
        category,
        is_sensitive: isSensitive,
        is_active: true,
      })
      toast.success(`Configuration "${key.trim()}" created`)
      onClose()
    } catch (err) {
      toast.error(extractError(err))
    } finally {
      setSaving(false)
    }
  }

  const inputStyle = (err) => ({
    background: T.bg,
    border: `1px solid ${err ? `${T.danger}60` : T.border}`,
    borderRadius: 4, color: T.text,
    fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
    padding: '9px 12px', outline: 'none',
    width: '100%', boxSizing: 'border-box',
  })
  const labelStyle = {
    fontFamily: 'Space Mono, monospace', fontSize: 9,
    letterSpacing: '0.14em', textTransform: 'uppercase',
    color: T.textMuted, display: 'block', marginBottom: 5,
  }
  const errStyle = {
    fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11,
    color: T.danger, marginTop: 4,
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0,0,0,0.75)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div style={{
        background: T.surface,
        border: `1px solid ${T.border}`,
        borderRadius: 8, padding: 28,
        width: 480, maxWidth: 'calc(100vw - 32px)',
        animation: 'as-fadeUp 0.2s ease both',
        display: 'flex', flexDirection: 'column', gap: 16,
      }}>
        <h3 style={{
          fontFamily: 'Bebas Neue, sans-serif',
          fontSize: 22, letterSpacing: '0.04em', color: T.text, margin: 0,
        }}>
          New Configuration
        </h3>

        {/* Key */}
        <div>
          <label style={labelStyle}>Key (UPPER_CASE)</label>
          <input
            style={inputStyle(errors.key)}
            value={key}
            onChange={e => { setKey(e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, '')); setErrors(v => ({ ...v, key: null })) }}
            placeholder="MAX_ALERTS_PER_HOUR"
            autoFocus
          />
          {errors.key && <div style={errStyle}>{errors.key}</div>}
        </div>

        {/* Value */}
        <div>
          <label style={labelStyle}>Value (JSON — string, number, boolean, array, object)</label>
          <textarea
            style={{ ...inputStyle(errors.value), resize: 'vertical', minHeight: 64, fontFamily: 'Space Mono, monospace', fontSize: 11 }}
            value={value}
            onChange={e => { setValue(e.target.value); setErrors(v => ({ ...v, value: null })) }}
            placeholder={`"active"\n42\ntrue\n{"threshold": 10}`}
            rows={3}
          />
          {errors.value && <div style={errStyle}>{errors.value}</div>}
        </div>

        {/* Description */}
        <div>
          <label style={labelStyle}>Description (optional)</label>
          <input
            style={inputStyle(false)}
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="Human-readable explanation of this setting"
          />
        </div>

        {/* Category + Sensitive row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12, alignItems: 'flex-end' }}>
          <div>
            <label style={labelStyle}>Category</label>
            <select
              value={category}
              onChange={e => setCategory(e.target.value)}
              style={{ ...inputStyle(false), cursor: 'pointer' }}
            >
              {ALL_CATEGORIES.map(c => (
                <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
              ))}
            </select>
          </div>
          <label style={{
            display: 'flex', alignItems: 'center', gap: 6,
            cursor: 'pointer', paddingBottom: 10,
          }}>
            <input
              type="checkbox"
              checked={isSensitive}
              onChange={e => setIsSensitive(e.target.checked)}
              style={{ accentColor: T.accent }}
            />
            <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.1em', color: T.textMuted }}>
              SENSITIVE
            </span>
          </label>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', paddingTop: 4 }}>
          <button
            onClick={onClose}
            style={{
              background: 'transparent', border: `1px solid ${T.border}`,
              color: T.textSub, borderRadius: 4, padding: '8px 16px',
              fontSize: 13, fontFamily: 'IBM Plex Sans, sans-serif', cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={saving}
            style={{
              background: T.accent, border: 'none', color: '#fff',
              borderRadius: 4, padding: '8px 20px',
              fontSize: 13, fontFamily: 'IBM Plex Sans, sans-serif', fontWeight: 500,
              cursor: saving ? 'wait' : 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            {saving ? <Spinner size={11} /> : null}
            {saving ? 'Creating…' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── ShimmerGrid ──────────────────────────────────────────────────────────────

function ShimmerGrid() {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
      gap: 16,
    }}>
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} style={{
          background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: 6, padding: '18px 20px',
          display: 'flex', flexDirection: 'column', gap: 12,
        }}>
          <Shimmer height={10} style={{ width: '45%' }} />
          <Shimmer height={36} />
          <Shimmer height={10} style={{ width: '70%' }} />
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Shimmer height={28} style={{ width: 60 }} />
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function AdminSettings() {
  const toast = useToast()

  const [configs,         setConfigs]         = useState([])
  const [loading,         setLoading]         = useState(true)
  const [error,           setError]           = useState(null)
  const [searchQuery,     setSearchQuery]     = useState('')
  const [activeCategory,  setActiveCategory]  = useState('all')
  const [showCreate,      setShowCreate]      = useState(false)
  const [viewMode,        setViewMode]        = useState('category') // 'category' | 'flat'

  // ── Fetch via by_category for grouped display, or filtered list ─────────────
  const fetchConfigs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      // Always fetch full list — we handle grouping client-side for live search
      // Backend supports ?category=&search= params
      const params = {}
      if (activeCategory !== 'all') params.category = activeCategory
      if (searchQuery.trim()) params.search = searchQuery.trim()
      const res = await coreApi.listConfigurations(params)
      setConfigs(res.data.results ?? res.data)
    } catch (err) {
      setError(extractError(err))
    } finally {
      setLoading(false)
    }
  }, [activeCategory, searchQuery])

  useEffect(() => {
    const t = setTimeout(fetchConfigs, searchQuery ? 350 : 0)
    return () => clearTimeout(t)
  }, [fetchConfigs, searchQuery])

  // ── Handlers ─────────────────────────────────────────────────────────────────

  const handleSave = async (id, value) => {
    // Backend: SystemConfigurationWriteSerializer expects { value }
    const res = await coreApi.updateConfiguration(id, { value })
    setConfigs(cs => cs.map(c => c.id === id ? { ...c, value } : c))
    return res
  }

  const handleToggleActive = async (id) => {
    // POST /configurations/{id}/toggle_active/ returns { is_active }
    const res = await coreApi.toggleConfigActive(id)
    const next = res.data.is_active
    setConfigs(cs => cs.map(c => c.id === id ? { ...c, is_active: next } : c))
    toast.success(`Configuration ${next ? 'activated' : 'deactivated'}`)
  }

  const handleDelete = async (id) => {
    await coreApi.deleteConfiguration(id)
    setConfigs(cs => cs.filter(c => c.id !== id))
  }

  const handleCreate = async (data) => {
    const res = await coreApi.createConfiguration(data)
    setConfigs(cs => [...cs, res.data])
  }

  // ── Group by category ─────────────────────────────────────────────────────
  const grouped = configs.reduce((acc, cfg) => {
    const cat = cfg.category || 'general'
    if (!acc[cat]) acc[cat] = []
    acc[cat].push(cfg)
    return acc
  }, {})

  const categories = Object.keys(grouped).sort()

  // Stats
  const total    = configs.length
  const active   = configs.filter(c => c.is_active).length
  const inactive = total - active

  return (
    <div style={{ padding: '32px 40px', minHeight: '100vh', background: T.bg }}>
      <style>{STYLES}</style>

      {/* ── Header ── */}
      <div style={{ animation: 'as-fadeUp 0.4s ease both', marginBottom: 28 }}>
        <span style={{
          fontFamily: 'Space Mono, monospace', fontSize: 9,
          letterSpacing: '0.12em', textTransform: 'uppercase',
          color: T.accent, display: 'block', marginBottom: 6,
        }}>
          Admin / Settings
        </span>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
          <h1 style={{
            fontFamily: 'Bebas Neue, sans-serif', fontSize: 36,
            letterSpacing: '0.04em', color: T.text, margin: 0,
          }}>
            System Configuration
          </h1>
          <button
            onClick={() => setShowCreate(true)}
            style={{
              background: T.accent, border: 'none', color: '#fff',
              borderRadius: 4, padding: '9px 18px',
              fontSize: 13, fontFamily: 'IBM Plex Sans, sans-serif', fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            + New Configuration
          </button>
        </div>
      </div>

      {/* ── Stats bar ── */}
      {!loading && configs.length > 0 && (
        <div style={{
          display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 24,
          animation: 'as-fadeUp 0.4s ease 0.05s both',
        }}>
          {[
            { label: 'Total',    value: total,    color: T.accent },
            { label: 'Active',   value: active,   color: T.success },
            { label: 'Inactive', value: inactive, color: T.textMuted },
          ].map(s => (
            <div key={s.label} style={{
              background: T.surface, border: `1px solid ${T.border}`,
              borderRadius: 4, padding: '10px 18px',
              display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <span style={{
                fontFamily: 'Bebas Neue, sans-serif',
                fontSize: 22, letterSpacing: '0.04em', color: s.color,
              }}>
                {s.value}
              </span>
              <span style={{
                fontFamily: 'Space Mono, monospace', fontSize: 9,
                letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textMuted,
              }}>
                {s.label}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Search + Filter bar ── */}
      <div style={{
        display: 'flex', gap: 10, flexWrap: 'wrap',
        marginBottom: 24,
        animation: 'as-fadeUp 0.4s ease 0.08s both',
      }}>
        {/* Search */}
        <input
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          placeholder="Search by key or description…"
          style={{
            background: T.surface, border: `1px solid ${T.border}`,
            borderRadius: 4, color: T.text,
            fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
            padding: '9px 14px', outline: 'none', flex: '1 1 260px',
            minWidth: 0,
          }}
          onFocus={e => e.target.style.borderColor = T.accent}
          onBlur={e => e.target.style.borderColor = T.border}
        />

        {/* Category pills */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          {['all', ...ALL_CATEGORIES].map(cat => {
            const active = activeCategory === cat
            const color = cat === 'all' ? T.accent : CATEGORY_COLORS[cat] || T.textMuted
            return (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                style={{
                  fontFamily: 'Space Mono, monospace', fontSize: 9,
                  letterSpacing: '0.12em', textTransform: 'uppercase',
                  padding: '5px 10px', borderRadius: 2,
                  border: `1px solid ${active ? color : T.border}`,
                  background: active ? `${color}18` : 'transparent',
                  color: active ? color : T.textMuted,
                  cursor: 'pointer', transition: 'all 0.15s',
                  whiteSpace: 'nowrap',
                }}
              >
                {cat}
              </button>
            )
          })}
        </div>
      </div>

      {/* ── Error ── */}
      {error && (
        <div style={{
          background: `${T.danger}12`, border: `1px solid ${T.danger}30`,
          color: '#f87171', borderRadius: 4, padding: '12px 16px',
          fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
          marginBottom: 24,
        }}>
          {error}
        </div>
      )}

      {/* ── Content ── */}
      {loading ? (
        <ShimmerGrid />
      ) : configs.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: '64px 24px',
          color: T.textMuted, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 14,
        }}>
          {searchQuery
            ? `No configurations matching "${searchQuery}"`
            : activeCategory !== 'all'
            ? `No configurations in category "${activeCategory}"`
            : 'No configuration entries found. Create one to get started.'}
        </div>
      ) : (
        <div style={{ animation: 'as-fadeUp 0.4s ease 0.1s both' }}>
          {categories.map((cat, ci) => (
            <div key={cat} style={{ marginBottom: 40 }}>
              {/* Category header */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16,
              }}>
                <span style={{
                  fontFamily: 'Space Mono, monospace', fontSize: 9,
                  letterSpacing: '0.14em', textTransform: 'uppercase',
                  color: CATEGORY_COLORS[cat] || T.textMuted,
                }}>
                  {cat}
                </span>
                <div style={{ flex: 1, height: 1, background: T.border }} />
                <span style={{
                  fontFamily: 'Space Mono, monospace', fontSize: 9,
                  color: T.textMuted, letterSpacing: '0.1em',
                }}>
                  {grouped[cat].length}
                </span>
              </div>

              {/* Cards */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 280px), 1fr))',
                gap: 16,
              }}>
                {grouped[cat].map(cfg => (
                  <ConfigCard
                    key={cfg.id}
                    config={cfg}
                    onSave={handleSave}
                    onDelete={handleDelete}
                    onToggleActive={handleToggleActive}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Create Modal ── */}
      {showCreate && (
        <CreateModal
          onClose={() => setShowCreate(false)}
          onCreate={handleCreate}
        />
      )}
    </div>
  )
}