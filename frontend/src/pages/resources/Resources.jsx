/**
 * Resources.jsx — Phase 7
 * Dashboard overview: stat cards, facility table, low-stock sidebar,
 * recent stock movements. Uses correct resourcesApi endpoints.
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { resourcesApi, extractError } from '../../services/api'
import { useToast } from '../../context/ToastContext'

// ─── Design tokens ────────────────────────────────────────────────────────────
const T = {
  bg:         '#0a0f1e',
  surface:    '#111827',
  surfaceHigh:'#151e2e',
  border:     '#1f2937',
  accent:     '#3b82f6',
  danger:     '#ef4444',
  warning:    '#f59e0b',
  success:    '#10b981',
  text:       '#f9fafb',
  textSub:    '#9ca3af',
  muted:      '#6b7280',
  orange:     '#f97316',
}

// ─── Status maps ──────────────────────────────────────────────────────────────
const INV_STATUS = {
  AVAILABLE:    { label: 'Available',    color: T.success },
  LOW_STOCK:    { label: 'Low Stock',    color: T.warning },
  OUT_OF_STOCK: { label: 'Out of Stock', color: T.danger  },
  EXPIRED:      { label: 'Expired',      color: T.muted   },
  RESERVED:     { label: 'Reserved',     color: T.orange  },
}

const MOVE_TYPE = {
  RECEIPT:    { label: 'Receipt',    color: T.success },
  ISSUE:      { label: 'Issue',      color: T.warning },
  TRANSFER:   { label: 'Transfer',   color: T.accent  },
  ADJUSTMENT: { label: 'Adjustment', color: T.muted   },
  DISPOSAL:   { label: 'Disposal',   color: T.danger  },
}

// ─── Shared atoms ─────────────────────────────────────────────────────────────
function Badge({ label, color }) {
  return (
    <span style={{
      fontFamily:      'Space Mono, monospace',
      fontSize:        9,
      letterSpacing:   '0.12em',
      textTransform:   'uppercase',
      color,
      background:      color + '18',
      border:          `1px solid ${color}30`,
      borderRadius:    2,
      padding:         '2px 8px',
      whiteSpace:      'nowrap',
    }}>{label}</span>
  )
}

function Shimmer({ height = 16 }) {
  return (
    <>
      <style>{`
        @keyframes res-shimmer {
          0%   { background-position: -200% 0 }
          100% { background-position:  200% 0 }
        }
      `}</style>
      <div style={{
        height,
        borderRadius:    3,
        background:      `linear-gradient(90deg,${T.surface} 0%,${T.surfaceHigh} 50%,${T.surface} 100%)`,
        backgroundSize:  '200% 100%',
        animation:       'res-shimmer 1.5s infinite',
      }} />
    </>
  )
}

function StatCard({ label, value, sub, color, loading, onClick }) {
  const [hov, setHov] = useState(false)
  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background:    T.surface,
        border:        `1px solid ${hov && onClick ? T.accent + '60' : T.border}`,
        borderRadius:  6,
        padding:       '20px 24px',
        flex:          1,
        minWidth:      140,
        cursor:        onClick ? 'pointer' : 'default',
        transition:    'border-color 0.15s',
      }}
    >
      <div style={{
        fontFamily:    'Space Mono, monospace',
        fontSize:      9,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        color:         T.textSub,
        marginBottom:  12,
      }}>{label}</div>
      {loading
        ? <Shimmer height={32} />
        : <div style={{
            fontFamily: 'Bebas Neue, sans-serif',
            fontSize:   36,
            color:      color || T.text,
            lineHeight: 1,
          }}>{value ?? '—'}</div>
      }
      {sub && !loading && (
        <div style={{
          fontFamily:  'IBM Plex Sans, sans-serif',
          fontSize:    12,
          color:       T.textSub,
          marginTop:   6,
        }}>{sub}</div>
      )}
    </div>
  )
}

function OccupancyBar({ pct }) {
  const p   = Math.min(100, Math.max(0, pct || 0))
  const col = p >= 90 ? T.danger : p >= 70 ? T.warning : T.success
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width: 72, height: 5, background: T.border, borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${p}%`, height: '100%', background: col, borderRadius: 3 }} />
      </div>
      <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textSub }}>{p}%</span>
    </div>
  )
}

const thStyle = {
  fontFamily:    'Space Mono, monospace',
  fontSize:      9,
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  color:         T.muted,
  padding:       '10px 14px',
  textAlign:     'left',
  borderBottom:  `1px solid ${T.border}`,
  whiteSpace:    'nowrap',
}
const tdStyle = {
  fontFamily:   'IBM Plex Sans, sans-serif',
  fontSize:     13,
  color:        T.text,
  padding:      '11px 14px',
  borderBottom: `1px solid ${T.border}`,
}

const PAGE_SIZE = 20

// ─── Filter bar component ─────────────────────────────────────────────────────
function FacilityFilters({ search, onSearch, typeFilter, onType, opFilter, onOp }) {
  const inputStyle = {
    background:    T.surfaceHigh,
    border:        `1px solid ${T.border}`,
    borderRadius:  4,
    color:         T.text,
    fontFamily:    'IBM Plex Sans, sans-serif',
    fontSize:      13,
    padding:       '6px 12px',
    outline:       'none',
  }
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', padding: '12px 16px', borderBottom: `1px solid ${T.border}` }}>
      <input
        value={search}
        onChange={e => onSearch(e.target.value)}
        placeholder="Search facilities…"
        style={{ ...inputStyle, minWidth: 180 }}
      />
      <select value={typeFilter} onChange={e => onType(e.target.value)} style={inputStyle}>
        <option value="">All Types</option>
        <option value="HOSPITAL">Hospital</option>
        <option value="CLINIC">Clinic</option>
        <option value="HEALTH_CENTER">Health Centre</option>
        <option value="DISPENSARY">Dispensary</option>
        <option value="WAREHOUSE">Warehouse</option>
        <option value="ISOLATION_CENTRE">Isolation Centre</option>
        <option value="QUARANTINE_FACILITY">Quarantine Facility</option>
        <option value="FIELD_HOSPITAL">Field Hospital</option>
      </select>
      <select value={opFilter} onChange={e => onOp(e.target.value)} style={inputStyle}>
        <option value="">All Status</option>
        <option value="true">Operational</option>
        <option value="false">Non-Operational</option>
      </select>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function Resources() {
  const navigate = useNavigate()
  const toast    = useToast()

  // Dashboard stats
  const [dashboard,    setDashboard]    = useState(null)
  const [dashLoading,  setDashLoading]  = useState(true)

  // Facilities table
  const [facilities,   setFacilities]   = useState([])
  const [facLoading,   setFacLoading]   = useState(true)
  const [facError,     setFacError]     = useState(null)
  const [facPage,      setFacPage]      = useState(1)
  const [facTotal,     setFacTotal]     = useState(0)
  const [search,       setSearch]       = useState('')
  const [typeFilter,   setTypeFilter]   = useState('')
  const [opFilter,     setOpFilter]     = useState('')
  const [hovRow,       setHovRow]       = useState(null)

  // Low-stock sidebar
  const [lowStock,     setLowStock]     = useState([])
  const [lsLoading,    setLsLoading]    = useState(true)

  // Recent movements
  const [movements,    setMovements]    = useState([])
  const [movLoading,   setMovLoading]   = useState(true)

  // ── Dashboard ──────────────────────────────────────────────────────────────
  useEffect(() => {
    resourcesApi.resourcesDashboard()
      .then(r => setDashboard(r.data))
      .catch(e => { if (import.meta.env.DEV) console.warn('[Resources] Dashboard stats unavailable:', e); toast.warning?.('Resources dashboard stats unavailable') })
      .finally(() => setDashLoading(false))
  }, [])

  // ── Facilities (search debounce) ───────────────────────────────────────────
  const loadFacilities = useCallback(() => {
    setFacLoading(true)
    setFacError(null)
    const params = { page: facPage, page_size: PAGE_SIZE }
    if (search)     params.search           = search
    if (typeFilter) params.facility_type    = typeFilter
    if (opFilter)   params.is_operational   = opFilter
    resourcesApi.listFacilities(params)
      .then(r => {
        setFacilities(r.data.results ?? [])
        setFacTotal(r.data.count ?? 0)
      })
      .catch(e => setFacError(extractError(e)))
      .finally(() => setFacLoading(false))
  }, [facPage, search, typeFilter, opFilter])

  useEffect(() => {
    const t = setTimeout(loadFacilities, search ? 350 : 0)
    return () => clearTimeout(t)
  }, [loadFacilities, search])

  // Reset to page 1 on filter changes
  useEffect(() => { setFacPage(1) }, [search, typeFilter, opFilter])

  // ── Low-stock critical items ───────────────────────────────────────────────
  useEffect(() => {
    // inventoryLowStock = GET /resources/inventory/low_stock/
    resourcesApi.inventoryLowStock({ page_size: 15 })
      .then(r => setLowStock(r.data.results ?? []))
      .catch(e => { if (import.meta.env.DEV) console.warn('[Resources] Low-stock data unavailable:', e); toast.warning?.('Low-stock data unavailable') })
      .finally(() => setLsLoading(false))
  }, [])

  // ── Recent movements ──────────────────────────────────────────────────────
  useEffect(() => {
    // recentStockMovements = GET /resources/movements/recent/  (returns last 50, no pagination)
    resourcesApi.recentStockMovements()
      .then(r => setMovements((r.data ?? []).slice(0, 8)))
      .catch(e => { if (import.meta.env.DEV) console.warn('[Resources] Recent movements unavailable:', e); toast.warning?.('Recent stock movements unavailable') })
      .finally(() => setMovLoading(false))
  }, [])

  const totalPages = Math.ceil(facTotal / PAGE_SIZE)

  // ── Stat cards ─────────────────────────────────────────────────────────────
  const stats = [
    {
      label: 'Total Facilities',
      value: dashboard?.total_facilities,
      sub:   dashboard ? `${dashboard.operational_facilities} operational` : null,
    },
    {
      label: 'Critical Low Stock',
      value: dashboard?.critical_items_low_stock,
      color: dashboard?.critical_items_low_stock > 0 ? T.danger : T.success,
      sub:   'Critical items below reorder point',
    },
    {
      label: 'Avg Occupancy',
      value: dashboard?.average_occupancy_rate != null
        ? `${dashboard.average_occupancy_rate}%`
        : null,
      color: dashboard?.average_occupancy_rate >= 80 ? T.warning : T.success,
      sub:   dashboard ? `${dashboard.facilities_above_80_percent} above 80%` : null,
    },
    {
      label: 'Pending Procurement',
      value: dashboard?.pending_procurement_requests,
      color: dashboard?.pending_procurement_requests > 0 ? T.warning : T.text,
      sub:   'Awaiting review / approval',
    },
    {
      label: 'Expiring <30d',
      value: dashboard?.expiring_within_30_days,
      color: dashboard?.expiring_within_30_days > 0 ? T.orange : T.text,
      sub:   'Inventory items expiring soon',
    },
    {
      label: "Today's Movements",
      value: dashboard?.total_stock_movements_today,
      sub:   'Stock movements recorded today',
    },
  ]

  return (
    <div style={{
      minHeight:   '100vh',
      background:  T.bg,
      padding:     '32px 32px 64px',
      fontFamily:  'IBM Plex Sans, sans-serif',
    }}>
      {/* Page header */}
      <div style={{
        fontFamily:    'Space Mono, monospace',
        fontSize:      9,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        color:         T.textSub,
        marginBottom:  6,
      }}>Operations / Resources</div>

      <h1 style={{
        fontFamily:    'Bebas Neue, sans-serif',
        fontSize:      48,
        color:         T.text,
        margin:        '0 0 28px',
        letterSpacing: '0.03em',
        lineHeight:    1,
      }}>Resource Management</h1>

      {/* Stat cards */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 28 }}>
        {stats.map((s, i) => (
          <StatCard key={i} loading={dashLoading} {...s} />
        ))}
      </div>

      {/* Main content row */}
      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', flexWrap: 'wrap' }}>

        {/* Facilities table */}
        <div style={{ flex: 1, minWidth: 0, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden' }}>
          <div style={{
            padding:        '16px 20px',
            borderBottom:   `1px solid ${T.border}`,
            display:        'flex',
            alignItems:     'center',
            justifyContent: 'space-between',
          }}>
            <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.text }}>
              Facilities
            </span>
            <span style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub }}>
              {facTotal} total
            </span>
          </div>

          <FacilityFilters
            search={search} onSearch={setSearch}
            typeFilter={typeFilter} onType={setTypeFilter}
            opFilter={opFilter} onOp={setOpFilter}
          />

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Name', 'Code', 'Type', 'Location', 'Beds', 'Occupancy', 'Status', ''].map(h => (
                    <th key={h} style={thStyle}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {facLoading
                  ? Array(6).fill(0).map((_, i) => (
                      <tr key={i}>
                        {Array(8).fill(0).map((_, j) => <td key={j} style={tdStyle}><Shimmer /></td>)}
                      </tr>
                    ))
                  : facError
                    ? (
                      <tr>
                        <td colSpan={8} style={{ ...tdStyle, color: T.danger, textAlign: 'center', padding: 32 }}>
                          {facError}
                          <button
                            onClick={loadFacilities}
                            style={{ marginLeft: 12, background: 'transparent', border: `1px solid ${T.danger}`, borderRadius: 4, color: T.danger, padding: '4px 10px', fontSize: 12, cursor: 'pointer' }}
                          >Retry</button>
                        </td>
                      </tr>
                    )
                    : facilities.length === 0
                      ? (
                        <tr>
                          <td colSpan={8} style={{ ...tdStyle, textAlign: 'center', color: T.textSub, padding: 40 }}>
                            No facilities found
                          </td>
                        </tr>
                      )
                      : facilities.map(f => {
                          // is_operational is a boolean from FacilityListSerializer
                          const opColor = f.is_operational ? T.success : T.danger
                          const opLabel = f.is_operational ? 'Operational' : 'Non-Operational'
                          return (
                            <tr
                              key={f.id}
                              onClick={() => navigate(`/dashboard/resources/${f.id}`)}
                              onMouseEnter={() => setHovRow(f.id)}
                              onMouseLeave={() => setHovRow(null)}
                              style={{
                                cursor:     'pointer',
                                background: hovRow === f.id ? 'rgba(255,255,255,0.02)' : 'transparent',
                                transition: 'background 0.15s',
                              }}
                            >
                              <td style={{ ...tdStyle, fontWeight: 500 }}>{f.name}</td>
                              <td style={{ ...tdStyle, fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textSub }}>{f.code}</td>
                              <td style={{ ...tdStyle, color: T.textSub }}>{f.facility_type || '—'}</td>
                              <td style={{ ...tdStyle, color: T.textSub }}>{f.location_name || '—'}</td>
                              <td style={{ ...tdStyle, color: T.textSub }}>{f.total_beds ?? '—'}</td>
                              <td style={tdStyle}>
                                {/* Occupancy % from capacity; fall back to beds if not available */}
                                <OccupancyBar pct={f.occupancy_rate ?? 0} />
                              </td>
                              <td style={tdStyle}>
                                <Badge label={opLabel} color={opColor} />
                              </td>
                              <td style={{ ...tdStyle, textAlign: 'right' }}>
                                <button
                                  onClick={e => { e.stopPropagation(); navigate(`/dashboard/resources/${f.id}`) }}
                                  style={{
                                    background:  T.accent,
                                    color:       '#fff',
                                    border:      'none',
                                    borderRadius:4,
                                    padding:     '5px 12px',
                                    fontSize:    12,
                                    fontWeight:  500,
                                    cursor:      'pointer',
                                    fontFamily:  'IBM Plex Sans, sans-serif',
                                  }}
                                >View</button>
                              </td>
                            </tr>
                          )
                        })
                }
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{
              padding:        '12px 16px',
              borderTop:      `1px solid ${T.border}`,
              display:        'flex',
              alignItems:     'center',
              justifyContent: 'space-between',
            }}>
              <span style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub }}>
                Page {facPage} of {totalPages} — {facTotal} facilities
              </span>
              <div style={{ display: 'flex', gap: 8 }}>
                {[
                  { label: '← Prev', disabled: facPage === 1,         fn: () => setFacPage(p => p - 1) },
                  { label: 'Next →', disabled: facPage === totalPages, fn: () => setFacPage(p => p + 1) },
                ].map(({ label, disabled, fn }) => (
                  <button
                    key={label}
                    disabled={disabled}
                    onClick={fn}
                    style={{
                      background:  T.surfaceHigh,
                      color:       disabled ? T.muted : T.text,
                      border:      `1px solid ${T.border}`,
                      borderRadius:4,
                      padding:     '5px 14px',
                      fontSize:    12,
                      cursor:      disabled ? 'default' : 'pointer',
                      fontFamily:  'IBM Plex Sans, sans-serif',
                    }}
                  >{label}</button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, width: 260, flexShrink: 0 }}>

          {/* Low-stock alerts */}
          <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden' }}>
            <div style={{ padding: '12px 16px', borderBottom: `1px solid ${T.border}` }}>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.warning }}>
                ⚠ Low Stock Alerts
              </span>
            </div>
            <div style={{ maxHeight: 340, overflowY: 'auto' }}>
              {lsLoading
                ? Array(5).fill(0).map((_, i) => (
                    <div key={i} style={{ padding: '10px 16px', borderBottom: `1px solid ${T.border}` }}>
                      <Shimmer />
                    </div>
                  ))
                : lowStock.length === 0
                  ? (
                    <div style={{ padding: '24px 16px', textAlign: 'center', fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub }}>
                      All stock levels normal
                    </div>
                  )
                  : lowStock.map(item => {
                      // InventoryListSerializer fields: resource_name, facility_name, quantity_available, status, is_critical
                      const ss = INV_STATUS[item.status] ?? { label: item.status, color: T.muted }
                      return (
                        <div key={item.id} style={{ padding: '10px 16px', borderBottom: `1px solid ${T.border}` }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
                            <span style={{
                              fontFamily: 'IBM Plex Sans, sans-serif',
                              fontSize:   13,
                              color:      T.text,
                              fontWeight: 500,
                              lineHeight: 1.3,
                              maxWidth:   140,
                            }}>{item.resource_name}</span>
                            <Badge label={ss.label} color={ss.color} />
                          </div>
                          <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, color: T.textSub, marginBottom: 2 }}>
                            {item.facility_name || '—'}
                          </div>
                          <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textSub }}>
                            Qty: {item.quantity_available ?? '—'}
                            {item.is_critical && <span style={{ marginLeft: 6, color: T.danger }}>● critical</span>}
                          </div>
                        </div>
                      )
                    })
              }
            </div>
            {lowStock.length > 0 && (
              <div style={{ padding: '10px 16px', borderTop: `1px solid ${T.border}` }}>
                <button
                  onClick={() => navigate('/dashboard/resources?tab=inventory')}
                  style={{
                    background:  'transparent',
                    color:       T.accent,
                    border:      'none',
                    fontFamily:  'IBM Plex Sans, sans-serif',
                    fontSize:    12,
                    cursor:      'pointer',
                    padding:     0,
                  }}
                >View all inventory →</button>
              </div>
            )}
          </div>

          {/* Recent movements */}
          <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden' }}>
            <div style={{ padding: '12px 16px', borderBottom: `1px solid ${T.border}` }}>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.text }}>
                Recent Movements
              </span>
            </div>
            <div>
              {movLoading
                ? Array(4).fill(0).map((_, i) => (
                    <div key={i} style={{ padding: '10px 16px', borderBottom: `1px solid ${T.border}` }}>
                      <Shimmer />
                    </div>
                  ))
                : movements.length === 0
                  ? (
                    <div style={{ padding: '24px 16px', textAlign: 'center', fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub }}>
                      No movements today
                    </div>
                  )
                  : movements.map(mv => {
                      // StockMovementSerializer: movement_type, resource_name, quantity, reference_number, movement_date
                      const mt = MOVE_TYPE[mv.movement_type] ?? { label: mv.movement_type, color: T.muted }
                      const dt = mv.movement_date ? new Date(mv.movement_date).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'
                      return (
                        <div key={mv.id} style={{ padding: '10px 16px', borderBottom: `1px solid ${T.border}` }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
                            <Badge label={mt.label} color={mt.color} />
                            <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textSub }}>{mv.quantity}</span>
                          </div>
                          <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.text, marginBottom: 2 }}>
                            {mv.resource_name}
                          </div>
                          <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.muted }}>
                            {mv.reference_number} · {dt}
                          </div>
                        </div>
                      )
                    })
              }
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}