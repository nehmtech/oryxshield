/**
 * Locations — OryxShield
 * =================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Admin view for Location reference data (countries, regions, districts, facilities).
 *
 * API (coreApi — verified against core URLs):
 *   GET    /locations/          listLocations(params)
 *   POST   /locations/          createLocation(data)
 *   PATCH  /locations/{id}/     updateLocation(id, data)
 *   DELETE /locations/{id}/     deleteLocation(id)
 *   GET    /locations/tree/     locationTree()
 *   GET    /locations/{id}/children/    locationChildren(id)
 */

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { coreApi, extractError } from '../../services/api'
import { useToast } from '../../context/ToastContext'

const C = {
  bg:          '#0a0f1e',
  surface:     '#111827',
  surfaceHigh: '#151e2e',
  border:      '#1f2937',
  accent:      '#3b82f6',
  accentBg:    'rgba(59,130,246,0.08)',
  danger:      '#ef4444',
  warning:     '#f59e0b',
  success:     '#10b981',
  text:        '#f9fafb',
  textSub:     '#9ca3af',
  textMuted:   '#6b7280',
}

const PAGE_SIZE = 40

const LOCATION_TYPES = ['COUNTRY','REGION','PROVINCE','DISTRICT','MUNICIPALITY','FACILITY','ZONE','OTHER']

const TYPE_COLOR = {
  COUNTRY:      '#a78bfa',
  REGION:       C.accent,
  PROVINCE:     '#22d3ee',
  DISTRICT:     C.success,
  MUNICIPALITY: C.warning,
  FACILITY:     '#f97316',
  ZONE:         C.textSub,
  OTHER:        C.textMuted,
}

function LocationRow({ loc, onEdit, onDelete }) {
  const [hovered, setHovered] = useState(false)
  const [confirmDel, setConfirmDel] = useState(false)
  const color = TYPE_COLOR[loc.location_type] || C.textMuted

  return (
    <tr
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background:   hovered ? C.surfaceHigh : 'transparent',
        borderBottom: `1px solid ${C.border}`,
        transition:   'background 0.12s',
      }}
    >
      <td style={{ padding: '10px 14px', fontSize: 13, color: C.text }}>{loc.name}</td>
      <td style={{ padding: '10px 14px' }}>
        <span style={{
          padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 700,
          background: `${color}18`, color, border: `1px solid ${color}40`,
        }}>{loc.location_type}</span>
      </td>
      <td style={{ padding: '10px 14px', fontSize: 12, color: C.textSub }}>{loc.parent_name || loc.parent || '—'}</td>
      <td style={{ padding: '10px 14px', fontSize: 12, color: C.textMuted }}>{loc.code || '—'}</td>
      <td style={{ padding: '10px 14px', fontSize: 12, color: C.textMuted }}>{loc.population ? Number(loc.population).toLocaleString() : '—'}</td>
      <td style={{ padding: '10px 14px', textAlign: 'center' }}>
        <span style={{ color: loc.is_active !== false ? C.success : C.danger, fontSize: 12 }}>
          {loc.is_active !== false ? '●' : '○'}
        </span>
      </td>
      <td style={{ padding: '10px 14px' }}>
        <div style={{ display: 'flex', gap: 6, opacity: hovered ? 1 : 0, transition: 'opacity 0.15s' }}>
          <button
            onClick={() => onEdit(loc)}
            style={{ padding: '3px 10px', borderRadius: 6, border: `1px solid ${C.accent}`, background: C.accentBg, color: C.accent, fontSize: 11, cursor: 'pointer' }}
          >Edit</button>
          {confirmDel ? (
            <>
              <button onClick={() => { onDelete(loc); setConfirmDel(false) }}
                style={{ padding: '3px 10px', borderRadius: 6, border: '1px solid rgba(239,68,68,0.5)', background: 'rgba(239,68,68,0.18)', color: C.danger, fontSize: 11, cursor: 'pointer', fontWeight: 600 }}>
                Confirm
              </button>
              <button onClick={() => setConfirmDel(false)}
                style={{ padding: '3px 10px', borderRadius: 6, border: `1px solid ${C.border}`, background: 'transparent', color: C.textMuted, fontSize: 11, cursor: 'pointer' }}>
                Cancel
              </button>
            </>
          ) : (
            <button
              onClick={() => setConfirmDel(true)}
              style={{ padding: '3px 10px', borderRadius: 6, border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.08)', color: C.danger, fontSize: 11, cursor: 'pointer' }}
            >Delete</button>
          )}
        </div>
      </td>
    </tr>
  )
}

function LocationForm({ initial, onSave, onCancel }) {
  const [form, setForm] = useState({
    name:          initial?.name          || '',
    location_type: initial?.location_type || 'DISTRICT',
    code:          initial?.code          || '',
    parent:        initial?.parent        || '',
    population:    initial?.population    || '',
    latitude:      initial?.latitude      || '',
    longitude:     initial?.longitude     || '',
    is_active:     initial?.is_active !== false,
  })

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const labelStyle = { display: 'block', fontSize: 12, color: C.textMuted, marginBottom: 4 }
  const inputStyle = {
    width: '100%', padding: '8px 10px',
    background: C.surface, border: `1px solid ${C.border}`,
    borderRadius: 6, color: C.text, fontSize: 13, outline: 'none', boxSizing: 'border-box',
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      style={{
        background: C.surfaceHigh, border: `1px solid ${C.border}`,
        borderRadius: 10, padding: 20, marginBottom: 20,
      }}
    >
      <h3 style={{ margin: '0 0 16px', color: C.text, fontSize: 15 }}>
        {initial ? 'Edit Location' : 'New Location'}
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
        <div>
          <label style={labelStyle}>Name *</label>
          <input style={inputStyle} value={form.name} onChange={e => set('name', e.target.value)} placeholder="Location name" />
        </div>
        <div>
          <label style={labelStyle}>Type *</label>
          <select style={inputStyle} value={form.location_type} onChange={e => set('location_type', e.target.value)}>
            {LOCATION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Code</label>
          <input style={inputStyle} value={form.code} onChange={e => set('code', e.target.value)} placeholder="e.g. NAM-KH-001" />
        </div>
        <div>
          <label style={labelStyle}>Parent ID</label>
          <input style={inputStyle} value={form.parent} onChange={e => set('parent', e.target.value)} placeholder="Parent location UUID" />
        </div>
        <div>
          <label style={labelStyle}>Population</label>
          <input style={inputStyle} type="number" value={form.population} onChange={e => set('population', e.target.value)} placeholder="0" />
        </div>
        <div>
          <label style={labelStyle}>Latitude</label>
          <input style={inputStyle} type="number" step="any" value={form.latitude} onChange={e => set('latitude', e.target.value)} placeholder="-22.5" />
        </div>
        <div>
          <label style={labelStyle}>Longitude</label>
          <input style={inputStyle} type="number" step="any" value={form.longitude} onChange={e => set('longitude', e.target.value)} placeholder="17.0" />
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: 2 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, color: C.textSub }}>
            <input type="checkbox" checked={form.is_active} onChange={e => set('is_active', e.target.checked)} />
            Active
          </label>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
        <button
          onClick={() => onSave(form)}
          style={{ padding: '8px 20px', borderRadius: 8, border: `1px solid ${C.accent}`, background: C.accentBg, color: C.accent, fontSize: 13, cursor: 'pointer' }}
        >{initial ? 'Save Changes' : 'Create'}</button>
        <button
          onClick={onCancel}
          style={{ padding: '8px 20px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: C.textSub, fontSize: 13, cursor: 'pointer' }}
        >Cancel</button>
      </div>
    </motion.div>
  )
}

export default function Locations() {
  const { success: toastSuccess, error: toastError } = useToast()

  const [locations, setLocations] = useState([])
  const [loading, setLoading]     = useState(true)
  const [page, setPage]           = useState(1)
  const [total, setTotal]         = useState(0)
  const [search, setSearch]       = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [showForm, setShowForm]   = useState(false)
  const [editing, setEditing]     = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE }
      if (search)     params.search = search
      if (typeFilter) params.location_type = typeFilter
      const res = await coreApi.listLocations(params)
      const data = res.data
      setLocations(data.results || (Array.isArray(data) ? data : []))
      setTotal(data.count || (Array.isArray(data) ? data.length : 0))
    } catch (e) {
      toastError(extractError(e))
    } finally {
      setLoading(false)
    }
  }, [page, search, typeFilter, toastError])

  useEffect(() => { load() }, [load])

  const handleSave = async (form) => {
    try {
      const clean = {}
      Object.entries(form).forEach(([k, v]) => { if (v !== '' && v !== null) clean[k] = v })
      if (editing) {
        await coreApi.updateLocation(editing.id, clean)
        toastSuccess('Location updated.')
      } else {
        await coreApi.createLocation(clean)
        toastSuccess('Location created.')
      }
      setShowForm(false)
      setEditing(null)
      load()
    } catch (e) {
      toastError(extractError(e))
    }
  }

  const [pendingDelete, setPendingDelete] = useState(null)

  const handleDelete = async (loc) => {
    if (pendingDelete?.id !== loc.id) { setPendingDelete(loc); return }
    setPendingDelete(null)
    try {
      await coreApi.deleteLocation(loc.id)
      toastSuccess('Location deleted.')
      load()
    } catch (e) {
      toastError(extractError(e))
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div style={{ minHeight: '100vh', background: C.bg, padding: '24px 20px' }}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>

        {/* ── Header ────────────────────────────────────────────────────────── */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: C.text }}>Locations</h1>
            <p style={{ margin: '4px 0 0', fontSize: 13, color: C.textSub }}>
              Reference geography · {total.toLocaleString()} entries
            </p>
          </div>
          <button
            onClick={() => { setShowForm(true); setEditing(null) }}
            style={{ padding: '8px 18px', borderRadius: 8, border: `1px solid ${C.accent}`, background: C.accentBg, color: C.accent, fontSize: 13, cursor: 'pointer' }}
          >+ Add Location</button>
        </div>

        {/* ── Form ──────────────────────────────────────────────────────────── */}
        <AnimatePresence>
          {(showForm || editing) && (
            <LocationForm
              initial={editing}
              onSave={handleSave}
              onCancel={() => { setShowForm(false); setEditing(null) }}
            />
          )}
        </AnimatePresence>

        {/* ── Filters ───────────────────────────────────────────────────────── */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
          <input
            placeholder="Search name or code…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            style={{
              flex: '1 1 200px', padding: '8px 12px',
              background: C.surface, border: `1px solid ${C.border}`,
              borderRadius: 8, color: C.text, fontSize: 13, outline: 'none',
            }}
          />
          <select
            value={typeFilter}
            onChange={e => { setTypeFilter(e.target.value); setPage(1) }}
            style={{
              padding: '8px 12px', background: C.surface,
              border: `1px solid ${C.border}`, borderRadius: 8,
              color: typeFilter ? C.text : C.textMuted, fontSize: 13,
            }}
          >
            <option value="">All Types</option>
            {LOCATION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>

        {/* ── Table ─────────────────────────────────────────────────────────── */}
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: C.surfaceHigh }}>
                  {['Name','Type','Parent','Code','Population','Active','Actions'].map(h => (
                    <th key={h} style={{
                      padding: '10px 14px', textAlign: 'left',
                      fontSize: 11, fontWeight: 700, color: C.textMuted,
                      letterSpacing: '0.06em', textTransform: 'uppercase',
                      borderBottom: `1px solid ${C.border}`,
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={7} style={{ textAlign: 'center', padding: 40, color: C.textMuted, fontSize: 14 }}>Loading…</td></tr>
                ) : locations.length === 0 ? (
                  <tr><td colSpan={7} style={{ textAlign: 'center', padding: 40, color: C.textMuted, fontSize: 14 }}>No locations found.</td></tr>
                ) : (
                  locations.map(loc => (
                    <LocationRow
                      key={loc.id}
                      loc={loc}
                      onEdit={(l) => { setEditing(l); setShowForm(false) }}
                      onDelete={handleDelete}
                    />
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── Pagination ────────────────────────────────────────────────────── */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', justifyContent: 'center', gap: 10, marginTop: 20 }}>
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
              style={{ padding: '6px 16px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: page <= 1 ? C.textMuted : C.text, cursor: page <= 1 ? 'default' : 'pointer', fontSize: 13 }}>Prev</button>
            <span style={{ padding: '6px 12px', color: C.textSub, fontSize: 13 }}>{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
              style={{ padding: '6px 16px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: page >= totalPages ? C.textMuted : C.text, cursor: page >= totalPages ? 'default' : 'pointer', fontSize: 13 }}>Next</button>
          </div>
        )}
      </div>
    </div>
  )
}
