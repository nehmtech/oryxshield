/**
 * ResourceDetail.jsx — Phase 7
 * Facility detail with 5 tabs: Inventory, Capacity, Procurement, Stock Movements, Info
 * All fields map to actual serializer output from views.py / serializers.py
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { resourcesApi, extractError } from '../../services/api'
import Breadcrumb from '../../components/ui/Breadcrumb'

// ─── Design tokens ────────────────────────────────────────────────────────────
const T = {
  bg:          '#0a0f1e',
  surface:     '#111827',
  surfaceHigh: '#151e2e',
  border:      '#1f2937',
  accent:      '#3b82f6',
  danger:      '#ef4444',
  warning:     '#f59e0b',
  success:     '#10b981',
  text:        '#f9fafb',
  textSub:     '#9ca3af',
  muted:       '#6b7280',
  orange:      '#f97316',
}

// ─── Status / type maps ───────────────────────────────────────────────────────
const INV_STATUS = {
  AVAILABLE:    { label: 'Available',    color: T.success },
  LOW_STOCK:    { label: 'Low Stock',    color: T.warning },
  OUT_OF_STOCK: { label: 'Out of Stock', color: T.danger  },
  EXPIRED:      { label: 'Expired',      color: T.muted   },
  RESERVED:     { label: 'Reserved',     color: T.orange  },
}

const PROC_STATUS = {
  DRAFT:        { label: 'Draft',        color: T.muted   },
  SUBMITTED:    { label: 'Submitted',    color: T.accent  },
  UNDER_REVIEW: { label: 'Under Review', color: T.orange  },
  APPROVED:     { label: 'Approved',     color: T.success },
  ORDERED:      { label: 'Ordered',      color: T.accent  },
  DELIVERED:    { label: 'Delivered',    color: T.success },
  REJECTED:     { label: 'Rejected',     color: T.danger  },
  CANCELLED:    { label: 'Cancelled',    color: T.muted   },
}

const PRIORITY = {
  LOW:      { label: 'Low',      color: T.success },
  MEDIUM:   { label: 'Medium',   color: T.warning },
  HIGH:     { label: 'High',     color: T.orange  },
  CRITICAL: { label: 'Critical', color: T.danger  },
}

const MOVE_TYPE = {
  RECEIPT:    { label: 'Receipt',    color: T.success },
  ISSUE:      { label: 'Issue',      color: T.warning },
  TRANSFER:   { label: 'Transfer',   color: T.accent  },
  ADJUSTMENT: { label: 'Adjustment', color: T.muted   },
  DISPOSAL:   { label: 'Disposal',   color: T.danger  },
}

const TABS = ['INVENTORY', 'CAPACITY', 'PROCUREMENT', 'MOVEMENTS', 'INFO']

// ─── Shared atoms ─────────────────────────────────────────────────────────────
function Badge({ label, color }) {
  return (
    <span style={{
      fontFamily:    'Space Mono, monospace',
      fontSize:      9,
      letterSpacing: '0.12em',
      textTransform: 'uppercase',
      color,
      background:    color + '18',
      border:        `1px solid ${color}30`,
      borderRadius:  2,
      padding:       '2px 8px',
      whiteSpace:    'nowrap',
    }}>{label}</span>
  )
}

function Shimmer({ height = 16 }) {
  return (
    <>
      <style>{`
        @keyframes rd-shimmer {
          0%   { background-position: -200% 0 }
          100% { background-position:  200% 0 }
        }
      `}</style>
      <div style={{
        height,
        borderRadius:   3,
        background:     `linear-gradient(90deg,${T.surface} 0%,${T.surfaceHigh} 50%,${T.surface} 100%)`,
        backgroundSize: '200% 100%',
        animation:      'rd-shimmer 1.5s infinite',
      }} />
    </>
  )
}

function FillBar({ pct, color }) {
  const p = Math.min(100, Math.max(0, pct || 0))
  const c = color || (p >= 90 ? T.danger : p >= 70 ? T.warning : T.success)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, height: 5, background: T.border, borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${p}%`, height: '100%', background: c, borderRadius: 3 }} />
      </div>
      <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textSub, minWidth: 30 }}>{p}%</span>
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
  padding:      '10px 14px',
  borderBottom: `1px solid ${T.border}`,
}

function TableLoader({ cols = 6, rows = 5 }) {
  return Array(rows).fill(0).map((_, i) => (
    <tr key={i}>
      {Array(cols).fill(0).map((_, j) => <td key={j} style={tdStyle}><Shimmer /></td>)}
    </tr>
  ))
}

function EmptyRow({ cols, msg = 'No records found' }) {
  return (
    <tr>
      <td colSpan={cols} style={{ ...tdStyle, textAlign: 'center', color: T.textSub, padding: 40 }}>
        {msg}
      </td>
    </tr>
  )
}

// ─── Pagination control ───────────────────────────────────────────────────────
function Pager({ page, totalPages, total, onPrev, onNext }) {
  if (totalPages <= 1) return null
  return (
    <div style={{ padding: '12px 16px', borderTop: `1px solid ${T.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub }}>
        Page {page} of {totalPages} · {total} records
      </span>
      <div style={{ display: 'flex', gap: 8 }}>
        {[['← Prev', page === 1, onPrev], ['Next →', page === totalPages, onNext]].map(([lbl, dis, fn]) => (
          <button key={lbl} disabled={dis} onClick={fn} style={{
            background:  T.surfaceHigh, color: dis ? T.muted : T.text,
            border:      `1px solid ${T.border}`, borderRadius: 4,
            padding:     '5px 14px', fontSize: 12,
            cursor:      dis ? 'default' : 'pointer',
            fontFamily:  'IBM Plex Sans, sans-serif',
          }}>{lbl}</button>
        ))}
      </div>
    </div>
  )
}

// ─── Tab: Inventory ───────────────────────────────────────────────────────────
function InventoryTab({ facilityId, valid = true }) {
  const [items,   setItems]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)
  const [page,    setPage]    = useState(1)
  const [total,   setTotal]   = useState(0)
  const [status,  setStatus]  = useState('')
  const PAGE = 20

  const load = useCallback(() => {
    if (!valid) return
    setLoading(true)
    const params = { page, page_size: PAGE }
    if (status) params.status = status
    resourcesApi.facilityInventory(facilityId, params)
      .then(r => {
        setItems(r.data.results ?? r.data ?? [])
        setTotal(r.data.count ?? 0)
      })
      .catch(e => setError(extractError(e)))
      .finally(() => setLoading(false))
  }, [facilityId, page, status])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [status])

  const totalPages = Math.ceil(total / PAGE)

  return (
    <div>
      {/* Filter bar */}
      <div style={{ padding: '10px 14px', borderBottom: `1px solid ${T.border}`, display: 'flex', gap: 8 }}>
        <select
          value={status}
          onChange={e => setStatus(e.target.value)}
          style={{ background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, color: T.text, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, padding: '5px 10px' }}
        >
          <option value="">All Statuses</option>
          {Object.entries(INV_STATUS).map(([v, { label }]) => <option key={v} value={v}>{label}</option>)}
        </select>
      </div>

      {error && <div style={{ padding: '16px 14px', color: T.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13 }}>{error}</div>}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Item', 'Code', 'Batch', 'Qty Available', 'Expiry Date', 'Status', 'Critical'].map(h => (
                <th key={h} style={thStyle}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading
              ? <TableLoader cols={7} />
              : items.length === 0
                ? <EmptyRow cols={7} msg="No inventory at this facility" />
                : items.map(item => {
                    // InventoryListSerializer: resource_name, resource_item, facility_name, quantity_available, status, expiry_date, batch_number, is_critical
                    const ss      = INV_STATUS[item.status] ?? { label: item.status, color: T.muted }
                    const expiry  = item.expiry_date ? new Date(item.expiry_date).toLocaleDateString() : '—'
                    const expired = item.expiry_date && new Date(item.expiry_date) < new Date()
                    return (
                      <tr key={item.id}>
                        <td style={{ ...tdStyle, fontWeight: 500 }}>{item.resource_name}</td>
                        <td style={{ ...tdStyle, fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textSub }}>{item.resource_code ?? '—'}</td>
                        <td style={{ ...tdStyle, color: T.textSub }}>{item.batch_number || '—'}</td>
                        <td style={{ ...tdStyle, fontWeight: 500, color: item.quantity_available === 0 ? T.danger : T.text }}>
                          {item.quantity_available ?? '—'}
                        </td>
                        <td style={{ ...tdStyle, color: expired ? T.danger : T.textSub }}>{expiry}</td>
                        <td style={tdStyle}><Badge label={ss.label} color={ss.color} /></td>
                        <td style={tdStyle}>
                          {item.is_critical
                            ? <Badge label="Critical" color={T.danger} />
                            : <span style={{ color: T.muted, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12 }}>—</span>
                          }
                        </td>
                      </tr>
                    )
                  })
            }
          </tbody>
        </table>
      </div>
      <Pager page={page} totalPages={totalPages} total={total} onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)} />
    </div>
  )
}

// ─── Tab: Capacity ────────────────────────────────────────────────────────────
function CapacityTab({ facilityId, valid = true }) {
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)
  const [page,    setPage]    = useState(1)
  const [total,   setTotal]   = useState(0)
  const PAGE = 10

  useEffect(() => {
    if (!valid) return
    setLoading(true)
    resourcesApi.listCapacity({ facility: facilityId, page, page_size: PAGE, ordering: '-recorded_at' })
      .then(r => {
        setRecords(r.data.results ?? [])
        setTotal(r.data.count ?? 0)
      })
      .catch(e => setError(extractError(e)))
      .finally(() => setLoading(false))
  }, [facilityId, page])

  const totalPages = Math.ceil(total / PAGE)

  if (error) return <div style={{ padding: 24, color: T.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13 }}>{error}</div>

  // Latest record summary card
  const latest = records[0]

  return (
    <div>
      {/* Latest snapshot summary */}
      {latest && !loading && (
        <div style={{ display: 'flex', gap: 16, padding: 16, borderBottom: `1px solid ${T.border}`, flexWrap: 'wrap' }}>
          {[
            { label: 'Beds Occupied', value: latest.beds_occupied, color: latest.occupancy_rate >= 90 ? T.danger : T.text },
            { label: 'Beds Available', value: latest.beds_available },
            { label: 'ICU Occupied', value: latest.icu_occupied ?? '—' },
            { label: 'Ventilators Used', value: latest.ventilators_in_use ?? '—' },
          ].map(c => (
            <div key={c.label} style={{ background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, padding: '12px 20px', flex: 1, minWidth: 100 }}>
              <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textSub, marginBottom: 6 }}>{c.label}</div>
              <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 30, color: c.color || T.text, lineHeight: 1 }}>{c.value ?? '—'}</div>
            </div>
          ))}
          <div style={{ background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, padding: '12px 20px', flex: 2, minWidth: 200 }}>
            <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textSub, marginBottom: 10 }}>Bed Occupancy</div>
            <FillBar pct={latest.occupancy_rate ?? 0} />
            <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, color: T.textSub, marginTop: 6 }}>
              Recorded: {latest.recorded_at ? new Date(latest.recorded_at).toLocaleString() : '—'}
            </div>
          </div>
        </div>
      )}

      {/* History table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Recorded At', 'Beds Occupied', 'Beds Available', 'Occupancy %', 'ICU Occupied', 'Ventilators', 'Recorded By'].map(h => (
                <th key={h} style={thStyle}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading
              ? <TableLoader cols={7} />
              : records.length === 0
                ? <EmptyRow cols={7} msg="No capacity records for this facility" />
                : records.map(r => {
                    // FacilityCapacitySerializer: facility_name, beds_occupied, beds_available, occupancy_rate, recorded_at, icu_occupied, ventilators_in_use, recorded_by_name
                    const occ = r.occupancy_rate ?? 0
                    const col = occ >= 90 ? T.danger : occ >= 70 ? T.warning : T.success
                    return (
                      <tr key={r.id}>
                        <td style={{ ...tdStyle, fontFamily: 'Space Mono, monospace', fontSize: 11, color: T.textSub }}>
                          {r.recorded_at ? new Date(r.recorded_at).toLocaleString() : '—'}
                        </td>
                        <td style={{ ...tdStyle, fontWeight: 500 }}>{r.beds_occupied ?? '—'}</td>
                        <td style={tdStyle}>{r.beds_available ?? '—'}</td>
                        <td style={{ ...tdStyle, color: col, fontWeight: 500 }}>
                          {occ != null ? `${occ}%` : '—'}
                        </td>
                        <td style={{ ...tdStyle, color: T.textSub }}>{r.icu_occupied ?? '—'}</td>
                        <td style={{ ...tdStyle, color: T.textSub }}>{r.ventilators_in_use ?? '—'}</td>
                        <td style={{ ...tdStyle, color: T.textSub }}>{r.recorded_by_name || '—'}</td>
                      </tr>
                    )
                  })
            }
          </tbody>
        </table>
      </div>
      <Pager page={page} totalPages={totalPages} total={total} onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)} />
    </div>
  )
}

// ─── Tab: Procurement ─────────────────────────────────────────────────────────
function ProcurementTab({ facilityId, valid = true }) {
  const [items,   setItems]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)
  const [page,    setPage]    = useState(1)
  const [total,   setTotal]   = useState(0)
  const [status,  setStatus]  = useState('')
  const PAGE = 20

  const load = useCallback(() => {
    if (!valid) return
    setLoading(true)
    const params = { requesting_facility: facilityId, page, page_size: PAGE }
    if (status) params.status = status
    resourcesApi.listProcurement(params)
      .then(r => {
        setItems(r.data.results ?? [])
        setTotal(r.data.count ?? 0)
      })
      .catch(e => setError(extractError(e)))
      .finally(() => setLoading(false))
  }, [facilityId, page, status])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [status])

  const totalPages = Math.ceil(total / PAGE)

  const [actionLoading, setActionLoading] = useState(null)
  const [toast, setToast] = useState(null)

  const showToast = (msg, isErr = false) => {
    setToast({ msg, isErr })
    setTimeout(() => setToast(null), 3500)
  }

  const doAction = async (id, action, payload = {}) => {
    setActionLoading(id + action)
    try {
      if (action === 'submit')   await resourcesApi.submitProcurement(id)
      if (action === 'approve')  await resourcesApi.approveProcurement(id, payload)
      if (action === 'reject')   await resourcesApi.rejectProcurement(id, payload)
      if (action === 'cancel')   await resourcesApi.cancelProcurement(id, payload)
      if (action === 'deliver')  await resourcesApi.markProcurementDelivered(id, payload)
      showToast(`Request ${action}d successfully`)
      load()
    } catch(e) {
      showToast(extractError(e), true)
    } finally {
      setActionLoading(null)
    }
  }

  return (
    <div>
      {toast && (
        <div style={{ padding: '10px 16px', background: toast.isErr ? T.danger + '22' : T.success + '22', borderBottom: `1px solid ${toast.isErr ? T.danger : T.success}30`, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: toast.isErr ? T.danger : T.success }}>
          {toast.msg}
        </div>
      )}

      <div style={{ padding: '10px 14px', borderBottom: `1px solid ${T.border}`, display: 'flex', gap: 8 }}>
        <select
          value={status}
          onChange={e => setStatus(e.target.value)}
          style={{ background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, color: T.text, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, padding: '5px 10px' }}
        >
          <option value="">All Statuses</option>
          {Object.entries(PROC_STATUS).map(([v, { label }]) => <option key={v} value={v}>{label}</option>)}
        </select>
      </div>

      {error && <div style={{ padding: '16px 14px', color: T.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13 }}>{error}</div>}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Ref #', 'Items', 'Est. Cost', 'Priority', 'Status', 'Required By', 'Requested By', 'Actions'].map(h => (
                <th key={h} style={thStyle}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading
              ? <TableLoader cols={8} />
              : items.length === 0
                ? <EmptyRow cols={8} msg="No procurement requests for this facility" />
                : items.map(pr => {
                    // ProcurementRequestListSerializer fields: request_number, requesting_facility, facility_name,
                    // priority, status, requested_date, required_by_date, estimated_cost, item_count
                    const pri  = PRIORITY[pr.priority]    ?? { label: pr.priority,    color: T.muted }
                    const pst  = PROC_STATUS[pr.status]   ?? { label: pr.status,      color: T.muted }
                    const cost = pr.estimated_cost != null ? `KES ${Number(pr.estimated_cost).toLocaleString()}` : '—'
                    const reqBy = pr.required_by_date ? new Date(pr.required_by_date).toLocaleDateString() : '—'
                    const busy  = actionLoading?.startsWith(pr.id)
                    return (
                      <tr key={pr.id}>
                        <td style={{ ...tdStyle, fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.accent }}>
                          {pr.request_number}
                        </td>
                        <td style={{ ...tdStyle, color: T.textSub }}>{pr.item_count ?? '—'}</td>
                        <td style={tdStyle}>{cost}</td>
                        <td style={tdStyle}><Badge label={pri.label} color={pri.color} /></td>
                        <td style={tdStyle}><Badge label={pst.label} color={pst.color} /></td>
                        <td style={{ ...tdStyle, color: T.textSub }}>{reqBy}</td>
                        <td style={{ ...tdStyle, color: T.textSub }}>{pr.requested_by_name || '—'}</td>
                        <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                          <div style={{ display: 'flex', gap: 6 }}>
                            {pr.status === 'DRAFT' && (
                              <ActionBtn label="Submit" color={T.accent} disabled={busy} onClick={() => doAction(pr.id, 'submit')} />
                            )}
                            {['SUBMITTED', 'UNDER_REVIEW'].includes(pr.status) && (
                              <>
                                <ActionBtn label="Approve" color={T.success} disabled={busy} onClick={() => doAction(pr.id, 'approve')} />
                                <ActionBtn label="Reject"  color={T.danger}  disabled={busy} onClick={() => {
                                  const reason = window.prompt('Rejection reason (min 10 chars):')
                                  if (reason && reason.length >= 10) doAction(pr.id, 'reject', { reason })
                                }} />
                              </>
                            )}
                            {pr.status === 'ORDERED' && (
                              <ActionBtn label="Delivered" color={T.success} disabled={busy} onClick={() => doAction(pr.id, 'deliver')} />
                            )}
                            {!['DELIVERED', 'CANCELLED'].includes(pr.status) && (
                              <ActionBtn label="Cancel" color={T.muted} disabled={busy} onClick={() => doAction(pr.id, 'cancel')} />
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })
            }
          </tbody>
        </table>
      </div>
      <Pager page={page} totalPages={totalPages} total={total} onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)} />
    </div>
  )
}

function ActionBtn({ label, color, disabled, onClick }) {
  const [hov, setHov] = useState(false)
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background:  hov ? color + '28' : 'transparent',
        color,
        border:      `1px solid ${color}60`,
        borderRadius:3,
        padding:     '3px 8px',
        fontSize:    11,
        cursor:      disabled ? 'default' : 'pointer',
        fontFamily:  'IBM Plex Sans, sans-serif',
        opacity:     disabled ? 0.5 : 1,
        transition:  'background 0.12s',
      }}
    >{label}</button>
  )
}

// ─── Tab: Stock Movements ─────────────────────────────────────────────────────
function MovementsTab({ facilityId, valid = true }) {
  const [items,   setItems]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)
  const [page,    setPage]    = useState(1)
  const [total,   setTotal]   = useState(0)
  const [type,    setType]    = useState('')
  const PAGE = 20

  const load = useCallback(() => {
    setLoading(true)
    // Filter by from_facility OR to_facility (backend supports both filters)
    const params = { page, page_size: PAGE, ordering: '-movement_date' }
    if (type) params.movement_type = type
    params.from_facility = facilityId
    resourcesApi.listStockMovements(params)
      .then(r => {
        setItems(r.data.results ?? [])
        setTotal(r.data.count ?? 0)
      })
      .catch(e => setError(extractError(e)))
      .finally(() => setLoading(false))
  }, [facilityId, page, type])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [type])

  const totalPages = Math.ceil(total / PAGE)

  return (
    <div>
      <div style={{ padding: '10px 14px', borderBottom: `1px solid ${T.border}`, display: 'flex', gap: 8 }}>
        <select
          value={type}
          onChange={e => setType(e.target.value)}
          style={{ background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, color: T.text, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, padding: '5px 10px' }}
        >
          <option value="">All Types</option>
          {Object.entries(MOVE_TYPE).map(([v, { label }]) => <option key={v} value={v}>{label}</option>)}
        </select>
      </div>

      {error && <div style={{ padding: '16px 14px', color: T.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13 }}>{error}</div>}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['Reference', 'Type', 'Item', 'Quantity', 'From', 'To', 'Recorded By', 'Date'].map(h => (
                <th key={h} style={thStyle}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading
              ? <TableLoader cols={8} />
              : items.length === 0
                ? <EmptyRow cols={8} msg="No stock movements found" />
                : items.map(mv => {
                    // StockMovementSerializer: movement_type, resource_name, quantity, reference_number,
                    // from_facility_name, to_facility_name, recorded_by_name, movement_date
                    const mt = MOVE_TYPE[mv.movement_type] ?? { label: mv.movement_type, color: T.muted }
                    const dt = mv.movement_date ? new Date(mv.movement_date).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'
                    return (
                      <tr key={mv.id}>
                        <td style={{ ...tdStyle, fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.accent }}>{mv.reference_number}</td>
                        <td style={tdStyle}><Badge label={mt.label} color={mt.color} /></td>
                        <td style={{ ...tdStyle, fontWeight: 500 }}>{mv.resource_name}</td>
                        <td style={{ ...tdStyle, fontFamily: 'Space Mono, monospace', fontSize: 11 }}>{mv.quantity}</td>
                        <td style={{ ...tdStyle, color: T.textSub }}>{mv.from_facility_name || '—'}</td>
                        <td style={{ ...tdStyle, color: T.textSub }}>{mv.to_facility_name || '—'}</td>
                        <td style={{ ...tdStyle, color: T.textSub }}>{mv.recorded_by_name || '—'}</td>
                        <td style={{ ...tdStyle, color: T.textSub, fontSize: 12 }}>{dt}</td>
                      </tr>
                    )
                  })
            }
          </tbody>
        </table>
      </div>
      <Pager page={page} totalPages={totalPages} total={total} onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)} />
    </div>
  )
}

// ─── Tab: Facility Info ───────────────────────────────────────────────────────
function InfoTab({ facility }) {
  if (!facility) return null

  const rows = [
    ['Code',             facility.code],
    ['Facility Type',    facility.facility_type],
    ['Location',         facility.location_name],
    ['Address',          facility.address],
    ['Contact Phone',    facility.contact_phone],
    ['Contact Email',    facility.contact_email],
    ['Total Beds',       facility.total_beds],
    ['ICU Beds',         facility.icu_beds],
    ['Isolation Beds',   facility.isolation_beds],
    ['Operating Hours',  facility.operating_hours],
    ['Operational',      facility.is_operational ? 'Yes' : 'No'],
    ['Managing Agency',  facility.managing_agency_name],
  ]

  return (
    <div style={{ padding: 20 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 1, border: `1px solid ${T.border}`, borderRadius: 4, overflow: 'hidden' }}>
        {rows.map(([label, value]) => (
          <div key={label} style={{ display: 'flex', borderBottom: `1px solid ${T.border}`, borderRight: `1px solid ${T.border}` }}>
            <div style={{
              fontFamily:    'Space Mono, monospace',
              fontSize:      9,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color:         T.textSub,
              padding:       '10px 14px',
              width:         140,
              flexShrink:    0,
              borderRight:   `1px solid ${T.border}`,
            }}>{label}</div>
            <div style={{
              fontFamily: 'IBM Plex Sans, sans-serif',
              fontSize:   13,
              color:      value ? T.text : T.muted,
              padding:    '10px 14px',
            }}>{value || '—'}</div>
          </div>
        ))}
      </div>

      {facility.notes && (
        <div style={{ marginTop: 16, background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, padding: 16 }}>
          <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textSub, marginBottom: 8 }}>Notes</div>
          <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.text, lineHeight: 1.6 }}>{facility.notes}</div>
        </div>
      )}
    </div>
  )
}

// ─── UUID guard ───────────────────────────────────────────────────────────────
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

// ─── Main component ───────────────────────────────────────────────────────────
export default function ResourceDetail() {
  const { id }   = useParams()
  const navigate = useNavigate()

  const validId = UUID_RE.test(id ?? '')

  const [facility,  setFacility]  = useState(null)
  const [loading,   setLoading]   = useState(validId)
  const [error,     setError]     = useState(validId ? null : `"${id}" is not a valid facility ID.`)
  const [activeTab, setActiveTab] = useState('INVENTORY')

  const [decommLoading, setDecommLoading] = useState(false)
  const [toast, setToast] = useState(null)

  const showToast = (msg, isErr = false) => {
    setToast({ msg, isErr })
    setTimeout(() => setToast(null), 3500)
  }

  useEffect(() => {
    if (!validId) return
    setLoading(true)
    resourcesApi.getFacility(id)
      .then(r => setFacility(r.data))
      .catch(e => setError(extractError(e)))
      .finally(() => setLoading(false))
  }, [id, validId])

  const [pendingDecomm, setPendingDecomm] = useState(false)

  const handleDecommission = async () => {
    if (!pendingDecomm) { setPendingDecomm(true); return }
    setPendingDecomm(false)
    setDecommLoading(true)
    try {
      await resourcesApi.decommissionFacility(id)
      setFacility(f => ({ ...f, is_operational: false }))
      showToast('Facility marked as non-operational')
    } catch(e) {
      showToast(extractError(e), true)
    } finally {
      setDecommLoading(false)
    }
  }

  const opColor = facility?.is_operational ? T.success : T.danger
  const opLabel = facility?.is_operational ? 'Operational' : 'Non-Operational'

  return (
    <div style={{
      minHeight:  '100vh',
      background: T.bg,
      padding:    '32px 32px 64px',
      fontFamily: 'IBM Plex Sans, sans-serif',
    }}>

      {/* Toast */}
      {toast && (
        <div style={{
          position:   'fixed',
          top:        20,
          right:      24,
          zIndex:     9999,
          background: toast.isErr ? T.danger : T.success,
          color:      '#fff',
          padding:    '10px 18px',
          borderRadius: 4,
          fontFamily: 'IBM Plex Sans, sans-serif',
          fontSize:   13,
          fontWeight: 500,
          boxShadow:  '0 4px 16px rgba(0,0,0,0.4)',
        }}>{toast.msg}</div>
      )}

      {/* Back */}
      <button
        onClick={() => navigate('/dashboard/resources')}
        style={{
          display:    'flex',
          alignItems: 'center',
          gap:        6,
          background: 'transparent',
          border:     'none',
          color:      T.textSub,
          cursor:     'pointer',
          fontFamily: 'IBM Plex Sans, sans-serif',
          fontSize:   13,
          padding:    0,
          marginBottom: 20,
        }}
      >
        <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
        All Resources
      </button>

      {/* Breadcrumb */}
      <Breadcrumb items={[
        { label: 'Resources', to: '/dashboard/resources' },
        { label: facility?.name || `Facility #${id}` },
      ]} />

      {/* Header */}
      {loading
        ? (
          <div style={{ marginBottom: 28 }}>
            <div style={{ width: 320, marginBottom: 12 }}><Shimmer height={40} /></div>
            <div style={{ width: 200 }}><Shimmer /></div>
          </div>
        )
        : error
          ? (
            <div style={{
              background:  T.danger + '12',
              border:      `1px solid ${T.danger}40`,
              borderRadius:6,
              padding:     '32px 28px',
              textAlign:   'center',
              marginBottom:24,
            }}>
              <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 28, color: T.danger, marginBottom: 10 }}>
                Facility Not Found
              </div>
              <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.textSub, marginBottom: 20 }}>
                {error}
              </div>
              <button
                onClick={() => navigate('/dashboard/resources')}
                style={{ background: T.accent, color: '#fff', border: 'none', borderRadius: 4, padding: '8px 20px', fontSize: 13, cursor: 'pointer', fontFamily: 'IBM Plex Sans, sans-serif' }}
              >← Back to Resources</button>
            </div>
          )
          : facility && (
            <div style={{ marginBottom: 28 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 10, flexWrap: 'wrap' }}>
                <h1 style={{
                  fontFamily:    'Bebas Neue, sans-serif',
                  fontSize:      42,
                  color:         T.text,
                  margin:        0,
                  letterSpacing: '0.03em',
                  lineHeight:    1,
                }}>{facility.name}</h1>
                <Badge label={opLabel} color={opColor} />
                {facility.is_operational && (
                  pendingDecomm ? (
                    <div style={{ display:'flex', gap:6, marginLeft:'auto', alignItems:'center' }}>
                      <span style={{ fontFamily:'IBM Plex Sans, sans-serif', fontSize:12, color:T.danger }}>
                        Mark as non-operational?
                      </span>
                      <button onClick={handleDecommission} disabled={decommLoading}
                        style={{ background:'rgba(239,68,68,0.18)', border:`1px solid ${T.danger}60`, borderRadius:4, color:T.danger, padding:'5px 12px', fontSize:12, cursor:'pointer', fontFamily:'IBM Plex Sans, sans-serif', fontWeight:600 }}>
                        {decommLoading ? 'Processing…' : 'Confirm'}
                      </button>
                      <button onClick={() => setPendingDecomm(false)}
                        style={{ background:'transparent', border:'1px solid rgba(255,255,255,0.1)', borderRadius:4, color:'#9ca3af', padding:'5px 12px', fontSize:12, cursor:'pointer', fontFamily:'IBM Plex Sans, sans-serif' }}>
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button onClick={handleDecommission} disabled={decommLoading}
                      style={{ background:'transparent', border:`1px solid ${T.danger}60`, borderRadius:4, color:T.danger, padding:'5px 12px', fontSize:12, cursor:'pointer', fontFamily:'IBM Plex Sans, sans-serif', marginLeft:'auto' }}>
                      {decommLoading ? 'Processing…' : 'Decommission'}
                    </button>
                  )
                )}
              </div>
              <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
                {facility.facility_type && (
                  <span style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.textSub }}>
                    {facility.facility_type}
                  </span>
                )}
                {facility.location_name && (
                  <>
                    <span style={{ color: T.border }}>·</span>
                    <span style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.textSub }}>{facility.location_name}</span>
                  </>
                )}
                {facility.total_beds != null && (
                  <>
                    <span style={{ color: T.border }}>·</span>
                    <span style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.textSub }}>{facility.total_beds} beds</span>
                  </>
                )}
                {facility.contact_phone && (
                  <>
                    <span style={{ color: T.border }}>·</span>
                    <span style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.textSub }}>{facility.contact_phone}</span>
                  </>
                )}
              </div>
            </div>
          )
      }

      {/* Tabs — only show when we have a valid facility */}
      {!error && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
        {TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              fontFamily:    'Space Mono, monospace',
              fontSize:      10,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              padding:       '6px 16px',
              borderRadius:  4,
              border:        `1px solid ${activeTab === tab ? T.accent : T.border}`,
              background:    activeTab === tab ? T.accent + '18' : 'transparent',
              color:         activeTab === tab ? T.accent : T.textSub,
              cursor:        'pointer',
              transition:    'all 0.15s',
            }}
          >{tab}</button>
          ))}
        </div>
      )}

      {/* Tab panel — only render when no error */}
      {!error && (
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden' }}>
          {activeTab === 'INVENTORY'   && <InventoryTab   facilityId={id} valid={validId} />}
          {activeTab === 'CAPACITY'    && <CapacityTab    facilityId={id} valid={validId} />}
          {activeTab === 'PROCUREMENT' && <ProcurementTab facilityId={id} valid={validId} />}
          {activeTab === 'MOVEMENTS'   && <MovementsTab   facilityId={id} valid={validId} />}
          {activeTab === 'INFO'        && <InfoTab        facility={facility} />}
        </div>
      )}
    </div>
  )
}