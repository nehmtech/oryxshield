import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { operationsApi, extractError } from '../../services/api'
import { useToast } from '../../context/ToastContext'

// ─── Animation helpers ────────────────────────────────────────────────────────
const fadeUp = (delay = 0) => ({
  style: { animation: `ops-fadeUp 0.3s ease-out ${delay}s both` },
})

// ─── Shared atoms ─────────────────────────────────────────────────────────────
const Badge = ({ color, children }) => (
  <span style={{
    display: 'inline-block', padding: '2px 8px', borderRadius: 2,
    fontSize: 9, fontFamily: 'Space Mono, monospace', letterSpacing: '0.12em',
    textTransform: 'uppercase', color, background: color + '18',
    border: `1px solid ${color}30`, fontWeight: 700,
  }}>{children}</span>
)

const Shimmer = ({ w = '60%', h = 14 }) => (
  <div style={{
    background: 'linear-gradient(90deg,#111827 0%,#151e2e 50%,#111827 100%)',
    backgroundSize: '200% 100%', animation: 'ops-shimmer 1.5s infinite',
    borderRadius: 4, height: h, width: w, marginBottom: 6,
  }} />
)

// ─── Color maps ───────────────────────────────────────────────────────────────
const CLASSIFICATION_COLORS = {
  SUSPECT: '#f59e0b', PROBABLE: '#f97316', CONFIRMED: '#ef4444', NOT_A_CASE: '#6b7280',
}
const STATUS_COLORS = {
  ACTIVE: '#ef4444', RECOVERED: '#10b981', DECEASED: '#6b7280', LOST_TO_FOLLOWUP: '#9ca3af',
}
const CONTACT_STATUS_COLORS = {
  IDENTIFIED: '#6b7280', UNDER_MONITORING: '#3b82f6', QUARANTINED: '#f59e0b',
  SYMPTOMATIC: '#ef4444', TESTED_NEGATIVE: '#10b981', BECAME_CASE: '#9b1c1c', CLEARED: '#4ade80',
}

// ─── Table styles ─────────────────────────────────────────────────────────────
const thStyle = {
  padding: '10px 14px', fontFamily: 'Space Mono, monospace', fontSize: 9,
  letterSpacing: '0.12em', textTransform: 'uppercase', color: '#6b7280',
  textAlign: 'left', borderBottom: '1px solid #1f2937', fontWeight: 400,
  whiteSpace: 'nowrap',
}
const tdStyle = {
  padding: '11px 14px', fontSize: 13, color: '#f9fafb',
  fontFamily: 'IBM Plex Sans, sans-serif', borderBottom: '1px solid #1f2937',
}

// ─── Stat card definition: maps to OperationsDashboardSerializer fields ───────
const STAT_CARDS = [
  { label: 'Active Cases',            key: 'active_cases',               color: '#ef4444' },
  { label: 'Confirmed Cases',         key: 'confirmed_cases',            color: '#f97316' },
  { label: 'Under Monitoring',        key: 'contacts_under_monitoring',  color: '#3b82f6' },
  { label: 'Symptomatic Contacts',    key: 'symptomatic_contacts',       color: '#f59e0b' },
  { label: 'Quarantined',             key: 'quarantined_individuals',    color: '#8b5cf6' },
  { label: 'Tests Today',             key: 'tests_today',                color: '#06b6d4' },
  { label: 'Positive Tests Today',    key: 'positive_tests_today',       color: '#ef4444' },
  { label: 'Vaccinations Today',      key: 'vaccinations_today',         color: '#10b981' },
  { label: 'Completions Today',       key: 'quarantine_completions_today', color: '#4ade80' },
  { label: 'Facilities at Capacity',  key: 'facilities_at_capacity',    color: '#9b1c1c' },
]

// ─── Section toggle button ────────────────────────────────────────────────────
const SectionTab = ({ label, active, onClick }) => (
  <button
    onClick={onClick}
    style={{
      background: active ? '#3b82f6' : 'transparent',
      color: active ? '#fff' : '#6b7280',
      border: `1px solid ${active ? '#3b82f6' : '#1f2937'}`,
      borderRadius: 4, padding: '6px 16px', fontSize: 11,
      fontFamily: 'Space Mono, monospace', letterSpacing: '0.08em',
      cursor: 'pointer', fontWeight: active ? 700 : 400, transition: 'all 0.15s',
    }}
  >{label}</button>
)

// ─── Main component ───────────────────────────────────────────────────────────
export default function Operations() {
  const navigate = useNavigate()
  const toast    = useToast()

  // ── Dashboard ────────────────────────────────────────────────────────────
  const [dashboard, setDashboard] = useState(null)
  const [dashLoading, setDashLoading] = useState(true)
  const [dashError, setDashError]     = useState(null)

  // ── Cases (paginated) ────────────────────────────────────────────────────
  const [cases, setCases]           = useState([])
  const [casesLoading, setCasesLoading] = useState(true)
  const [casesError, setCasesError]   = useState(null)
  const [casePage, setCasePage]       = useState(1)
  const [totalCases, setTotalCases]   = useState(0)
  const [caseSearch, setCaseSearch]   = useState('')
  const [caseSearchDebounced, setCaseSearchDebounced] = useState('')
  const [caseStatusFilter, setCaseStatusFilter] = useState('')
  const [caseClassFilter, setCaseClassFilter]   = useState('')
  const caseSearchTimer = useRef(null)

  // ── Testing Centers sidebar ───────────────────────────────────────────────
  const [centers, setCenters]         = useState([])
  const [centersLoading, setCentersLoading] = useState(true)

  // ── Contacts quick panel ──────────────────────────────────────────────────
  const [activeSection, setActiveSection] = useState('CASES')
  const [contacts, setContacts]           = useState([])
  const [contactsLoading, setContactsLoading] = useState(false)
  const [contactsError, setContactsError]   = useState(null)
  const [contactPage, setContactPage]       = useState(1)
  const [totalContacts, setTotalContacts]   = useState(0)
  const [contactStatusFilter, setContactStatusFilter] = useState('')

  // ── Vaccination campaigns quick panel ────────────────────────────────────
  const [campaigns, setCampaigns]     = useState([])
  const [campaignsLoading, setCampaignsLoading] = useState(false)
  const [campaignsError, setCampaignsError] = useState(null)

  // ─────────────────────────────────────────────────────────────────────────
  // Initial: dashboard + testing centers
  // ─────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    const ctrl = new AbortController()
    operationsApi.getDashboard({ signal: ctrl.signal })
      .then(r => setDashboard(r.data))
      .catch(e => { if (e?.name !== 'CanceledError') setDashError(extractError(e)) })
      .finally(() => setDashLoading(false))

    operationsApi.listTestingCenters({ page_size: 10, is_operational: true }, { signal: ctrl.signal })
      .then(r => setCenters(r.data.results ?? r.data))
      .catch(e => { if (e?.name !== 'CanceledError') { if (import.meta.env.DEV) console.warn('[Operations] Failed to load testing centers:', e); toast.warning?.('Testing centres data unavailable') } })
      .finally(() => setCentersLoading(false))

    return () => ctrl.abort()
  }, [])

  // ─────────────────────────────────────────────────────────────────────────
  // Cases
  // ─────────────────────────────────────────────────────────────────────────
  // Debounce: 350ms after typing stops, commit search to trigger API
  useEffect(() => {
    clearTimeout(caseSearchTimer.current)
    caseSearchTimer.current = setTimeout(() => {
      setCaseSearchDebounced(caseSearch)
      setCasePage(1)
    }, 350)
    return () => clearTimeout(caseSearchTimer.current)
  }, [caseSearch])

  const loadCases = useCallback((signal) => {
    setCasesLoading(true)
    setCasesError(null)
    const params = {
      page: casePage,
      page_size: 20,
      ...(caseSearchDebounced && { search: caseSearchDebounced }),
      ...(caseStatusFilter    && { status: caseStatusFilter }),
      ...(caseClassFilter     && { classification: caseClassFilter }),
    }
    operationsApi.listCases(params, { signal })
      .then(r => {
        setCases(r.data.results ?? r.data)
        setTotalCases(r.data.count ?? 0)
      })
      .catch(e => { if (e?.name !== 'CanceledError') setCasesError(extractError(e)) })
      .finally(() => setCasesLoading(false))
  }, [casePage, caseSearchDebounced, caseStatusFilter, caseClassFilter])

  useEffect(() => {
    const ctrl = new AbortController()
    loadCases(ctrl.signal)
    return () => ctrl.abort()
  }, [loadCases])

  // ─────────────────────────────────────────────────────────────────────────
  // Contacts
  // ─────────────────────────────────────────────────────────────────────────
  const loadContacts = useCallback((signal) => {
    if (activeSection !== 'CONTACTS') return
    setContactsLoading(true)
    setContactsError(null)
    const params = {
      page: contactPage,
      page_size: 20,
      ...(contactStatusFilter && { status: contactStatusFilter }),
    }
    operationsApi.listContacts(params, { signal })
      .then(r => {
        setContacts(r.data.results ?? r.data)
        setTotalContacts(r.data.count ?? 0)
      })
      .catch(e => { if (e?.name !== 'CanceledError') setContactsError(extractError(e)) })
      .finally(() => setContactsLoading(false))
  }, [activeSection, contactPage, contactStatusFilter])

  useEffect(() => {
    const ctrl = new AbortController()
    loadContacts(ctrl.signal)
    return () => ctrl.abort()
  }, [loadContacts])

  // ─────────────────────────────────────────────────────────────────────────
  // Vaccination campaigns
  // ─────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (activeSection !== 'CAMPAIGNS') return
    const ctrl = new AbortController()
    setCampaignsLoading(true)
    setCampaignsError(null)
    operationsApi.listVaccinationCampaigns({ page_size: 20 }, { signal: ctrl.signal })
      .then(r => setCampaigns(r.data.results ?? r.data))
      .catch(e => { if (e?.name !== 'CanceledError') setCampaignsError(extractError(e)) })
      .finally(() => setCampaignsLoading(false))
    return () => ctrl.abort()
  }, [activeSection])

  const caseTotalPages    = Math.ceil(totalCases    / 20)
  const contactTotalPages = Math.ceil(totalContacts / 20)

  const CAMPAIGN_STATUS_COLORS = {
    PLANNED: '#6b7280', ACTIVE: '#10b981', PAUSED: '#f59e0b', COMPLETED: '#3b82f6', CANCELLED: '#ef4444',
  }

  return (
    <div style={{
      padding: '32px 28px', fontFamily: 'IBM Plex Sans, sans-serif',
      color: '#f9fafb', minHeight: '100vh', maxWidth: 1400,
    }}>
      <style>{`
        @keyframes ops-fadeUp {
          from { opacity:0; transform:translateY(16px); }
          to   { opacity:1; transform:translateY(0); }
        }
        @keyframes ops-shimmer {
          0%   { background-position:200% 0; }
          100% { background-position:-200% 0; }
        }
        .ops-row:hover { background: rgba(255,255,255,0.025) !important; cursor:pointer; }
        .ops-input:focus { outline:none; border-color:#3b82f6 !important; }
        .ops-select:focus { outline:none; border-color:#3b82f6 !important; }
      `}</style>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div {...fadeUp(0)} style={{ marginBottom: 4 }}>
        <span style={{
          fontFamily: 'Space Mono, monospace', fontSize: 9,
          letterSpacing: '0.12em', textTransform: 'uppercase', color: '#6b7280',
        }}>Operations / Overview</span>
      </div>
      <h1 {...fadeUp(0.04)} style={{
        fontFamily: 'Bebas Neue, sans-serif', fontSize: 32,
        letterSpacing: '0.04em', color: '#f9fafb', margin: '0 0 28px',
      }}>Operations Command</h1>

      {/* ── Dashboard stat cards (10 metrics from OperationsDashboardSerializer) ── */}
      <div {...fadeUp(0.08)} style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 140px), 1fr))',
        gap: 12, marginBottom: 28,
      }}>
        {STAT_CARDS.map(({ label, key, color }) => (
          <div key={key} style={{
            background: '#111827', border: '1px solid #1f2937',
            borderRadius: 6, padding: '16px 18px',
          }}>
            <div style={{
              fontFamily: 'Space Mono, monospace', fontSize: 9,
              letterSpacing: '0.12em', textTransform: 'uppercase',
              color: '#6b7280', marginBottom: 8,
            }}>{label}</div>
            {dashLoading
              ? <Shimmer w="50%" h={22} />
              : dashError
                ? <span style={{ color: '#ef4444', fontSize: 11 }}>—</span>
                : <div style={{
                    fontFamily: 'Bebas Neue, sans-serif', fontSize: 26,
                    color, letterSpacing: '0.04em',
                  }}>
                    {(dashboard?.[key] ?? '—').toLocaleString?.() ?? dashboard?.[key] ?? '—'}
                  </div>
            }
          </div>
        ))}
      </div>

      {/* ── Section tabs ─────────────────────────────────────────────────────── */}
      <div {...fadeUp(0.1)} style={{ display: 'flex', gap: 6, marginBottom: 20 }}>
        {['CASES', 'CONTACTS', 'CAMPAIGNS'].map(s => (
          <SectionTab
            key={s} label={s} active={activeSection === s}
            onClick={() => setActiveSection(s)}
          />
        ))}
      </div>

      {/* ── Main two-column layout ───────────────────────────────────────────── */}
      <div {...fadeUp(0.12)} style={{ display: 'flex', gap: 20, alignItems: 'flex-start', flexWrap: 'wrap' }}>

        {/* ── Left: primary data table ──────────────────────────────────────── */}
        <div style={{ flex: 1, minWidth: 0 }}>

          {/* ═══ CASES TABLE ══════════════════════════════════════════════════ */}
          {activeSection === 'CASES' && (
            <div style={{
              background: '#111827', border: '1px solid #1f2937',
              borderRadius: 6, overflow: 'hidden',
            }}>
              {/* Table header + filters */}
              <div style={{
                padding: '16px 20px', borderBottom: '1px solid #1f2937',
                display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
              }}>
                <span style={{
                  fontFamily: 'Bebas Neue, sans-serif', fontSize: 18,
                  letterSpacing: '0.04em', marginRight: 8,
                }}>Cases</span>
                <span style={{
                  fontFamily: 'Space Mono, monospace', fontSize: 9,
                  color: '#6b7280', letterSpacing: '0.12em', marginRight: 12,
                }}>{totalCases} TOTAL</span>

                {/* Search */}
                <input
                  className="ops-input"
                  value={caseSearch}
                  onChange={e => setCaseSearch(e.target.value)}
                  placeholder="Search case ID, patient, disease…"
                  style={{
                    background: '#0a0f1e', color: '#f9fafb', border: '1px solid #1f2937',
                    borderRadius: 4, padding: '6px 10px', fontSize: 12,
                    fontFamily: 'IBM Plex Sans, sans-serif', width: 200,
                  }}
                />
                {/* Status filter */}
                <select
                  className="ops-select"
                  value={caseStatusFilter}
                  onChange={e => { setCaseStatusFilter(e.target.value); setCasePage(1) }}
                  style={{
                    background: '#0a0f1e', color: caseStatusFilter ? '#f9fafb' : '#6b7280',
                    border: '1px solid #1f2937', borderRadius: 4,
                    padding: '6px 10px', fontSize: 12,
                    fontFamily: 'IBM Plex Sans, sans-serif',
                  }}
                >
                  <option value="">All Statuses</option>
                  <option value="ACTIVE">Active</option>
                  <option value="RECOVERED">Recovered</option>
                  <option value="DECEASED">Deceased</option>
                  <option value="LOST_TO_FOLLOWUP">Lost to Follow-up</option>
                </select>
                {/* Classification filter */}
                <select
                  className="ops-select"
                  value={caseClassFilter}
                  onChange={e => { setCaseClassFilter(e.target.value); setCasePage(1) }}
                  style={{
                    background: '#0a0f1e', color: caseClassFilter ? '#f9fafb' : '#6b7280',
                    border: '1px solid #1f2937', borderRadius: 4,
                    padding: '6px 10px', fontSize: 12,
                    fontFamily: 'IBM Plex Sans, sans-serif',
                  }}
                >
                  <option value="">All Classifications</option>
                  <option value="SUSPECT">Suspect</option>
                  <option value="PROBABLE">Probable</option>
                  <option value="CONFIRMED">Confirmed</option>
                  <option value="NOT_A_CASE">Not a Case</option>
                </select>
              </div>

              {casesError && (
                <div style={{
                  padding: '12px 20px', color: '#ef4444', fontSize: 12,
                  background: '#1a0a0a', borderBottom: '1px solid #1f2937',
                }}>{casesError}</div>
              )}

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      {['Case ID', 'Patient', 'Disease', 'Classification', 'Status',
                        'Location', 'Assigned To', 'Reported', ''].map(h => (
                        <th key={h} style={thStyle}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {casesLoading
                      ? Array.from({ length: 8 }).map((_, i) => (
                          <tr key={i}>
                            {Array.from({ length: 9 }).map((_, j) => (
                              <td key={j} style={tdStyle}><Shimmer /></td>
                            ))}
                          </tr>
                        ))
                      : cases.length === 0
                        ? <tr><td colSpan={9} style={{ ...tdStyle, color: '#6b7280', textAlign: 'center', padding: 40 }}>
                            No cases found
                          </td></tr>
                        : cases.map(c => (
                            <tr
                              key={c.id}
                              className="ops-row"
                              onClick={() => navigate(`/dashboard/operations/${c.id}`)}
                              style={{ background: 'transparent' }}
                            >
                              <td style={tdStyle}>
                                <span style={{
                                  fontFamily: 'Space Mono, monospace',
                                  fontSize: 11, color: '#9ca3af',
                                }}>{c.case_id}</span>
                              </td>
                              <td style={tdStyle}>
                                <div style={{ fontSize: 13, fontWeight: 500 }}>{c.patient_name}</div>
                                {c.patient_age && (
                                  <div style={{ fontSize: 11, color: '#6b7280' }}>
                                    Age {c.patient_age}{c.patient_gender ? ` · ${c.patient_gender}` : ''}
                                  </div>
                                )}
                              </td>
                              <td style={{ ...tdStyle, color: '#9ca3af' }}>
                                <div style={{ fontSize: 12 }}>{c.disease_name || '—'}</div>
                                {c.disease_code && (
                                  <div style={{ fontSize: 10, color: '#6b7280', fontFamily: 'Space Mono, monospace' }}>
                                    {c.disease_code}
                                  </div>
                                )}
                              </td>
                              <td style={tdStyle}>
                                <Badge color={CLASSIFICATION_COLORS[c.classification] || '#6b7280'}>
                                  {c.classification}
                                </Badge>
                              </td>
                              <td style={tdStyle}>
                                <Badge color={STATUS_COLORS[c.status] || '#6b7280'}>
                                  {c.status?.replace('_', ' ')}
                                </Badge>
                              </td>
                              <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 12 }}>
                                {c.location_name || '—'}
                              </td>
                              <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 12 }}>
                                {c.assigned_to_name || <span style={{ color: '#374151' }}>Unassigned</span>}
                              </td>
                              <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 11, whiteSpace: 'nowrap' }}>
                                {c.created_at
                                  ? new Date(c.created_at).toLocaleDateString('en-NA', {
                                      day: '2-digit', month: 'short', year: 'numeric',
                                    })
                                  : '—'}
                              </td>
                              <td style={tdStyle}>
                                <button
                                  onClick={e => {
                                    e.stopPropagation()
                                    navigate(`/dashboard/operations/${c.id}`)
                                  }}
                                  style={{
                                    background: '#3b82f6', color: '#fff', border: 'none',
                                    borderRadius: 4, padding: '5px 12px', fontSize: 12,
                                    fontWeight: 500, cursor: 'pointer',
                                    fontFamily: 'IBM Plex Sans, sans-serif',
                                  }}
                                >View</button>
                              </td>
                            </tr>
                          ))
                    }
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {caseTotalPages > 1 && (
                <div style={{
                  padding: '12px 20px', display: 'flex', gap: 8,
                  alignItems: 'center', borderTop: '1px solid #1f2937',
                }}>
                  <button
                    disabled={casePage === 1}
                    onClick={() => setCasePage(p => p - 1)}
                    style={{
                      background: 'transparent',
                      color: casePage === 1 ? '#374151' : '#f9fafb',
                      border: '1px solid #1f2937', borderRadius: 4,
                      padding: '5px 12px', fontSize: 12,
                      cursor: casePage === 1 ? 'not-allowed' : 'pointer',
                    }}
                  >← Prev</button>
                  <span style={{
                    fontFamily: 'Space Mono, monospace', fontSize: 10, color: '#6b7280',
                  }}>
                    {casePage} / {caseTotalPages}
                  </span>
                  <button
                    disabled={casePage === caseTotalPages}
                    onClick={() => setCasePage(p => p + 1)}
                    style={{
                      background: 'transparent',
                      color: casePage === caseTotalPages ? '#374151' : '#f9fafb',
                      border: '1px solid #1f2937', borderRadius: 4,
                      padding: '5px 12px', fontSize: 12,
                      cursor: casePage === caseTotalPages ? 'not-allowed' : 'pointer',
                    }}
                  >Next →</button>
                </div>
              )}
            </div>
          )}

          {/* ═══ CONTACTS TABLE ═══════════════════════════════════════════════ */}
          {activeSection === 'CONTACTS' && (
            <div style={{
              background: '#111827', border: '1px solid #1f2937',
              borderRadius: 6, overflow: 'hidden',
            }}>
              <div style={{
                padding: '16px 20px', borderBottom: '1px solid #1f2937',
                display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
              }}>
                <span style={{
                  fontFamily: 'Bebas Neue, sans-serif', fontSize: 18,
                  letterSpacing: '0.04em', marginRight: 8,
                }}>Contacts</span>
                <span style={{
                  fontFamily: 'Space Mono, monospace', fontSize: 9,
                  color: '#6b7280', letterSpacing: '0.12em', marginRight: 12,
                }}>{totalContacts} TOTAL</span>
                <select
                  className="ops-select"
                  value={contactStatusFilter}
                  onChange={e => { setContactStatusFilter(e.target.value); setContactPage(1) }}
                  style={{
                    background: '#0a0f1e', color: contactStatusFilter ? '#f9fafb' : '#6b7280',
                    border: '1px solid #1f2937', borderRadius: 4,
                    padding: '6px 10px', fontSize: 12,
                    fontFamily: 'IBM Plex Sans, sans-serif',
                  }}
                >
                  <option value="">All Statuses</option>
                  <option value="IDENTIFIED">Identified</option>
                  <option value="UNDER_MONITORING">Under Monitoring</option>
                  <option value="QUARANTINED">Quarantined</option>
                  <option value="SYMPTOMATIC">Symptomatic</option>
                  <option value="TESTED_NEGATIVE">Tested Negative</option>
                  <option value="BECAME_CASE">Became Case</option>
                  <option value="CLEARED">Cleared</option>
                </select>
              </div>

              {contactsError && (
                <div style={{
                  padding: '12px 20px', color: '#ef4444', fontSize: 12,
                  background: '#1a0a0a', borderBottom: '1px solid #1f2937',
                }}>{contactsError}</div>
              )}

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      {['Contact ID', 'Name', 'Source Case', 'Type', 'Status',
                        'Exposure Date', 'Monitoring Ends', 'Quarantined'].map(h => (
                        <th key={h} style={thStyle}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {contactsLoading
                      ? Array.from({ length: 8 }).map((_, i) => (
                          <tr key={i}>
                            {Array.from({ length: 8 }).map((_, j) => (
                              <td key={j} style={tdStyle}><Shimmer /></td>
                            ))}
                          </tr>
                        ))
                      : contacts.length === 0
                        ? <tr><td colSpan={8} style={{ ...tdStyle, color: '#6b7280', textAlign: 'center', padding: 40 }}>
                            No contacts found
                          </td></tr>
                        : contacts.map(ct => (
                            <tr key={ct.id} style={{ background: 'transparent' }}>
                              <td style={tdStyle}>
                                <span style={{
                                  fontFamily: 'Space Mono, monospace',
                                  fontSize: 11, color: '#9ca3af',
                                }}>{ct.contact_id}</span>
                              </td>
                              <td style={tdStyle}>{ct.contact_name}</td>
                              <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 12 }}>
                                {ct.source_case_id || '—'}
                              </td>
                              <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 12 }}>
                                {ct.contact_type?.replace('_', ' ') || '—'}
                              </td>
                              <td style={tdStyle}>
                                <Badge color={CONTACT_STATUS_COLORS[ct.status] || '#6b7280'}>
                                  {ct.status?.replace(/_/g, ' ')}
                                </Badge>
                              </td>
                              <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 12 }}>
                                {ct.exposure_date
                                  ? new Date(ct.exposure_date).toLocaleDateString('en-NA')
                                  : '—'}
                              </td>
                              <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 12 }}>
                                {ct.monitoring_end_date
                                  ? new Date(ct.monitoring_end_date).toLocaleDateString('en-NA')
                                  : '—'}
                              </td>
                              <td style={tdStyle}>
                                <Badge color={ct.is_quarantined ? '#f59e0b' : '#374151'}>
                                  {ct.is_quarantined ? 'YES' : 'NO'}
                                </Badge>
                              </td>
                            </tr>
                          ))
                    }
                  </tbody>
                </table>
              </div>

              {contactTotalPages > 1 && (
                <div style={{
                  padding: '12px 20px', display: 'flex', gap: 8,
                  alignItems: 'center', borderTop: '1px solid #1f2937',
                }}>
                  <button
                    disabled={contactPage === 1}
                    onClick={() => setContactPage(p => p - 1)}
                    style={{
                      background: 'transparent',
                      color: contactPage === 1 ? '#374151' : '#f9fafb',
                      border: '1px solid #1f2937', borderRadius: 4,
                      padding: '5px 12px', fontSize: 12,
                      cursor: contactPage === 1 ? 'not-allowed' : 'pointer',
                    }}
                  >← Prev</button>
                  <span style={{
                    fontFamily: 'Space Mono, monospace', fontSize: 10, color: '#6b7280',
                  }}>{contactPage} / {contactTotalPages}</span>
                  <button
                    disabled={contactPage === contactTotalPages}
                    onClick={() => setContactPage(p => p + 1)}
                    style={{
                      background: 'transparent',
                      color: contactPage === contactTotalPages ? '#374151' : '#f9fafb',
                      border: '1px solid #1f2937', borderRadius: 4,
                      padding: '5px 12px', fontSize: 12,
                      cursor: contactPage === contactTotalPages ? 'not-allowed' : 'pointer',
                    }}
                  >Next →</button>
                </div>
              )}
            </div>
          )}

          {/* ═══ VACCINATION CAMPAIGNS TABLE ══════════════════════════════════ */}
          {activeSection === 'CAMPAIGNS' && (
            <div style={{
              background: '#111827', border: '1px solid #1f2937',
              borderRadius: 6, overflow: 'hidden',
            }}>
              <div style={{
                padding: '16px 20px', borderBottom: '1px solid #1f2937',
                display: 'flex', gap: 10, alignItems: 'center',
              }}>
                <span style={{
                  fontFamily: 'Bebas Neue, sans-serif', fontSize: 18, letterSpacing: '0.04em',
                }}>Vaccination Campaigns</span>
              </div>

              {campaignsError && (
                <div style={{
                  padding: '12px 20px', color: '#ef4444', fontSize: 12,
                  background: '#1a0a0a', borderBottom: '1px solid #1f2937',
                }}>{campaignsError}</div>
              )}

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      {['Code', 'Campaign', 'Vaccine', 'Status', 'Dates',
                        'Target Pop.', 'Vaccinated', 'Coverage', 'Doses Given'].map(h => (
                        <th key={h} style={thStyle}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {campaignsLoading
                      ? Array.from({ length: 6 }).map((_, i) => (
                          <tr key={i}>
                            {Array.from({ length: 9 }).map((_, j) => (
                              <td key={j} style={tdStyle}><Shimmer /></td>
                            ))}
                          </tr>
                        ))
                      : campaigns.length === 0
                        ? <tr><td colSpan={9} style={{ ...tdStyle, color: '#6b7280', textAlign: 'center', padding: 40 }}>
                            No campaigns found
                          </td></tr>
                        : campaigns.map(cp => (
                            <tr key={cp.id} style={{ background: 'transparent' }}>
                              <td style={tdStyle}>
                                <span style={{
                                  fontFamily: 'Space Mono, monospace', fontSize: 11, color: '#9ca3af',
                                }}>{cp.campaign_code}</span>
                              </td>
                              <td style={tdStyle}>
                                <div style={{ fontWeight: 500 }}>{cp.name}</div>
                                {cp.manager_name && (
                                  <div style={{ fontSize: 11, color: '#6b7280' }}>mgr: {cp.manager_name}</div>
                                )}
                              </td>
                              <td style={{ ...tdStyle, color: '#9ca3af' }}>{cp.vaccine_name}</td>
                              <td style={tdStyle}>
                                <Badge color={CAMPAIGN_STATUS_COLORS[cp.status] || '#6b7280'}>
                                  {cp.status}
                                </Badge>
                              </td>
                              <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 11, whiteSpace: 'nowrap' }}>
                                {cp.start_date ? new Date(cp.start_date).toLocaleDateString('en-NA') : '—'}
                                {' → '}
                                {cp.end_date   ? new Date(cp.end_date).toLocaleDateString('en-NA')   : '—'}
                              </td>
                              <td style={{ ...tdStyle, color: '#9ca3af' }}>
                                {cp.target_population?.toLocaleString() ?? '—'}
                              </td>
                              <td style={{ ...tdStyle, color: '#10b981' }}>
                                {cp.people_vaccinated?.toLocaleString() ?? '—'}
                              </td>
                              <td style={tdStyle}>
                                {cp.coverage_rate != null
                                  ? <span style={{ color: cp.coverage_rate >= 70 ? '#10b981' : '#f59e0b' }}>
                                      {cp.coverage_rate.toFixed(1)}%
                                    </span>
                                  : '—'}
                              </td>
                              <td style={{ ...tdStyle, color: '#9ca3af' }}>
                                {cp.doses_administered?.toLocaleString() ?? '—'}
                              </td>
                            </tr>
                          ))
                    }
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* ── Right: Testing Centers sidebar ──────────────────────────────────── */}
        <div style={{
          width: 280, background: '#111827', border: '1px solid #1f2937',
          borderRadius: 6, flexShrink: 0,
        }}>
          <div style={{ padding: '16px 18px', borderBottom: '1px solid #1f2937' }}>
            <span style={{
              fontFamily: 'Bebas Neue, sans-serif', fontSize: 18, letterSpacing: '0.04em',
            }}>Testing Centers</span>
          </div>
          <div style={{ maxHeight: 520, overflowY: 'auto' }}>
            {centersLoading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} style={{ padding: '14px 18px', borderBottom: '1px solid #1f2937' }}>
                    <Shimmer w="70%" h={13} /><Shimmer w="50%" h={11} /><Shimmer w="40%" h={10} />
                  </div>
                ))
              : centers.length === 0
                ? <div style={{ padding: '18px 18px', color: '#6b7280', fontSize: 13 }}>
                    No testing centers
                  </div>
                : centers.map(ct => {
                    const load = ct.current_load ?? 0
                    const cap  = ct.daily_capacity ?? 1
                    const pct  = Math.round((load / cap) * 100)
                    const barColor = pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#10b981'
                    return (
                      <div key={ct.id} style={{
                        padding: '14px 18px', borderBottom: '1px solid #1f2937',
                      }}>
                        <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 2 }}>
                          {ct.name}
                        </div>
                        <div style={{
                          fontFamily: 'Space Mono, monospace', fontSize: 9,
                          color: '#6b7280', letterSpacing: '0.08em', marginBottom: 6,
                        }}>{ct.code}</div>
                        <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 8 }}>
                          {ct.location_name || '—'}
                        </div>
                        {/* Capacity bar */}
                        <div style={{ marginBottom: 6 }}>
                          <div style={{
                            background: '#1f2937', borderRadius: 2,
                            height: 4, overflow: 'hidden',
                          }}>
                            <div style={{
                              background: barColor, height: '100%',
                              width: `${Math.min(pct, 100)}%`,
                              transition: 'width 0.4s ease',
                            }} />
                          </div>
                          <div style={{
                            display: 'flex', justifyContent: 'space-between',
                            marginTop: 3,
                          }}>
                            <span style={{
                              fontFamily: 'Space Mono, monospace', fontSize: 9, color: barColor,
                            }}>{pct}% load</span>
                            <span style={{
                              fontFamily: 'Space Mono, monospace', fontSize: 9, color: '#6b7280',
                            }}>{load}/{cap}</span>
                          </div>
                        </div>
                        <Badge color={ct.is_operational ? '#10b981' : '#6b7280'}>
                          {ct.is_operational ? 'OPERATIONAL' : 'INACTIVE'}
                        </Badge>
                      </div>
                    )
                  })
            }
          </div>
        </div>

      </div>
    </div>
  )
}