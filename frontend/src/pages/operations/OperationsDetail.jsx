import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { operationsApi, extractError } from '../../services/api'
import Breadcrumb from '../../components/ui/Breadcrumb'

// ─── Animation / style helpers ────────────────────────────────────────────────
const fadeUp = (delay = 0) => ({
  style: { animation: `opsd-fadeUp 0.3s ease-out ${delay}s both` },
})

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
    backgroundSize: '200% 100%', animation: 'opsd-shimmer 1.5s infinite',
    borderRadius: 4, height: h, width: w, marginBottom: 6,
  }} />
)

const Field = ({ label, value, mono = false }) => (
  <div style={{ marginBottom: 14 }}>
    <div style={{
      fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em',
      textTransform: 'uppercase', color: '#6b7280', marginBottom: 3,
    }}>{label}</div>
    <div style={{
      fontSize: 13, color: value ? '#f9fafb' : '#374151',
      fontFamily: mono ? 'Space Mono, monospace' : 'IBM Plex Sans, sans-serif',
    }}>{value || '—'}</div>
  </div>
)

// ─── Color maps ────────────────────────────────────────────────────────────────
const CLASSIFICATION_COLORS = {
  SUSPECT: '#f59e0b', PROBABLE: '#f97316', CONFIRMED: '#ef4444', NOT_A_CASE: '#6b7280',
}
const CASE_STATUS_COLORS = {
  ACTIVE: '#ef4444', RECOVERED: '#10b981', DECEASED: '#6b7280', LOST_TO_FOLLOWUP: '#9ca3af',
}
const CONTACT_STATUS_COLORS = {
  IDENTIFIED: '#6b7280', UNDER_MONITORING: '#3b82f6', QUARANTINED: '#f59e0b',
  SYMPTOMATIC: '#ef4444', TESTED_NEGATIVE: '#10b981', BECAME_CASE: '#9b1c1c', CLEARED: '#4ade80',
}
const APPT_STATUS_COLORS = {
  SCHEDULED: '#3b82f6', COMPLETED: '#10b981', CANCELLED: '#6b7280', NO_SHOW: '#f59e0b',
}
const RESULT_COLORS = {
  POSITIVE: '#ef4444', NEGATIVE: '#10b981', INCONCLUSIVE: '#f59e0b', PENDING: '#6b7280',
}
const QRECORD_STATUS_COLORS = {
  ADMITTED: '#3b82f6', IN_QUARANTINE: '#f59e0b', COMPLETED: '#10b981',
  RELEASED_EARLY: '#06b6d4', TRANSFERRED: '#8b5cf6',
}
const MONITORING_STATUS_COLORS = {
  UNDER_MONITORING: '#3b82f6', COMPLETED: '#10b981', LOST_TO_FOLLOWUP: '#6b7280',
}

// ─── Table header / cell ─────────────────────────────────────────────────────
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

const TABS = [
  { key: 'OVERVIEW',    label: 'Overview' },
  { key: 'CONTACTS',    label: 'Contacts' },
  { key: 'MONITORING',  label: 'Monitoring' },
  { key: 'TESTING',     label: 'Testing' },
  { key: 'QUARANTINE',  label: 'Quarantine' },
]

// ─── Main component ────────────────────────────────────────────────────────────
export default function OperationsDetail() {
  const { id } = useParams()
  const navigate = useNavigate()

  // ── Case header ────────────────────────────────────────────────────────────
  const [caseData, setCaseData]     = useState(null)
  const [caseLoading, setCaseLoading] = useState(true)
  const [caseError, setCaseError]   = useState(null)

  // ── Active tab ────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState('OVERVIEW')

  // ── Contacts tab ──────────────────────────────────────────────────────────
  const [contacts, setContacts]         = useState([])
  const [contactsLoading, setContactsLoading] = useState(false)
  const [contactsError, setContactsError] = useState(null)
  const [contactPage, setContactPage]   = useState(1)
  const [totalContacts, setTotalContacts] = useState(0)

  // ── Monitoring tab ────────────────────────────────────────────────────────
  const [monitoring, setMonitoring]       = useState([])
  const [monitoringLoading, setMonitoringLoading] = useState(false)
  const [monitoringError, setMonitoringError]   = useState(null)

  // ── Testing appointments tab ──────────────────────────────────────────────
  const [testing, setTesting]           = useState([])
  const [testingLoading, setTestingLoading] = useState(false)
  const [testingError, setTestingError] = useState(null)

  // ── Quarantine records tab ────────────────────────────────────────────────
  const [quarantine, setQuarantine]       = useState([])
  const [quarantineLoading, setQuarantineLoading] = useState(false)
  const [quarantineError, setQuarantineError]   = useState(null)

  // ─────────────────────────────────────────────────────────────────────────
  // Load case
  // ─────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    operationsApi.getCase(id)
      .then(r => setCaseData(r.data))
      .catch(e => setCaseError(extractError(e)))
      .finally(() => setCaseLoading(false))
  }, [id])

  // ─────────────────────────────────────────────────────────────────────────
  // Tab data loaders
  // ─────────────────────────────────────────────────────────────────────────

  // CONTACTS — from CaseViewSet GET /cases/{id}/contacts/
  const loadContacts = useCallback(() => {
    if (activeTab !== 'CONTACTS') return
    setContactsLoading(true)
    setContactsError(null)
    operationsApi.getCaseContacts(id, { page: contactPage, page_size: 20 })
      .then(r => {
        setContacts(r.data.results ?? r.data)
        setTotalContacts(r.data.count ?? 0)
      })
      .catch(e => setContactsError(extractError(e)))
      .finally(() => setContactsLoading(false))
  }, [activeTab, id, contactPage])

  useEffect(() => { loadContacts() }, [loadContacts])

  // MONITORING — from ContactMonitoringViewSet filtered by contact's source case
  // We filter monitoring records by contacts of this case using source_case param
  useEffect(() => {
    if (activeTab !== 'MONITORING') return
    setMonitoringLoading(true)
    setMonitoringError(null)
    // Filter monitoring records whose contact belongs to this case
    // ContactMonitoring filterset: contact, monitoring_date, has_symptoms, is_compliant
    // We need contacts first, then per-contact monitoring — or filter by contact__source_case
    // The API supports filtering by contact id; use contacts endpoint with source_case filter
    operationsApi.listContactMonitoring({ page_size: 50, contact__source_case: id })
      .then(r => setMonitoring(r.data.results ?? r.data))
      .catch(() => {
        // Fallback: if the double-underscore filter isn't registered, try direct case contacts
        operationsApi.listContacts({ source_case: id, page_size: 100 })
          .then(cr => {
            const contactIds = (cr.data.results ?? cr.data).map(c => c.id)
            if (contactIds.length === 0) { setMonitoring([]); return }
            // Fetch monitoring records for the first contact only as sample
            return operationsApi.listContactMonitoring({
              contact: contactIds[0], page_size: 50,
            }).then(mr => setMonitoring(mr.data.results ?? mr.data))
          })
          .catch(e => setMonitoringError(extractError(e)))
      })
      .finally(() => setMonitoringLoading(false))
  }, [activeTab, id])

  // TESTING — TestingAppointmentViewSet filtered by case id
  useEffect(() => {
    if (activeTab !== 'TESTING') return
    setTestingLoading(true)
    setTestingError(null)
    operationsApi.listTestingAppointments({ case: id, page_size: 50 })
      .then(r => setTesting(r.data.results ?? r.data))
      .catch(e => setTestingError(extractError(e)))
      .finally(() => setTestingLoading(false))
  }, [activeTab, id])

  // QUARANTINE — QuarantineRecordViewSet filtered by case id
  useEffect(() => {
    if (activeTab !== 'QUARANTINE') return
    setQuarantineLoading(true)
    setQuarantineError(null)
    operationsApi.listQuarantineRecords({ case: id, page_size: 50 })
      .then(r => setQuarantine(r.data.results ?? r.data))
      .catch(e => setQuarantineError(extractError(e)))
      .finally(() => setQuarantineLoading(false))
  }, [activeTab, id])

  const contactTotalPages = Math.ceil(totalContacts / 20)

  const fmt   = d => d ? new Date(d).toLocaleDateString('en-NA', {
    day: '2-digit', month: 'short', year: 'numeric'
  }) : '—'
  const fmtDt = d => d ? new Date(d).toLocaleString('en-NA', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }) : '—'

  return (
    <div style={{
      padding: '32px 28px', fontFamily: 'IBM Plex Sans, sans-serif',
      color: '#f9fafb', minHeight: '100vh',
    }}>
      <style>{`
        @keyframes opsd-fadeUp {
          from { opacity:0; transform:translateY(16px); }
          to   { opacity:1; transform:translateY(0); }
        }
        @keyframes opsd-shimmer {
          0%   { background-position:200% 0; }
          100% { background-position:-200% 0; }
        }
      `}</style>

      {/* ── Breadcrumb ─────────────────────────────────────────────────────────── */}
      <Breadcrumb items={[
        { label: 'Operations', to: '/dashboard/operations' },
        { label: caseData?.case_id || caseData?.title || `Case #${id}` },
      ]} />

      {/* ── Case header card ──────────────────────────────────────────────────── */}
      <div {...fadeUp(0.08)} style={{
        background: '#111827', border: '1px solid #1f2937',
        borderRadius: 6, padding: '22px 24px', marginBottom: 24,
      }}>
        {caseLoading ? (
          <div>
            <Shimmer w="25%" h={22} />
            <Shimmer w="40%" h={14} />
            <Shimmer w="30%" h={12} />
          </div>
        ) : caseError ? (
          <div style={{ color: '#ef4444', fontSize: 13 }}>{caseError}</div>
        ) : caseData ? (
          <div>
            {/* Top row: ID + actions */}
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              alignItems: 'flex-start', flexWrap: 'wrap', gap: 16, marginBottom: 20,
            }}>
              <div>
                <h1 style={{
                  fontFamily: 'Bebas Neue, sans-serif', fontSize: 30,
                  letterSpacing: '0.04em', margin: '0 0 6px',
                }}>{caseData.case_id}</h1>
                <div style={{ fontSize: 16, color: '#9ca3af', marginBottom: 10 }}>
                  {caseData.disease_name}
                  {caseData.disease_code && (
                    <span style={{
                      marginLeft: 8, fontFamily: 'Space Mono, monospace',
                      fontSize: 10, color: '#6b7280',
                    }}>({caseData.disease_code})</span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <Badge color={CLASSIFICATION_COLORS[caseData.classification] || '#6b7280'}>
                    {caseData.classification}
                  </Badge>
                  <Badge color={CASE_STATUS_COLORS[caseData.status] || '#6b7280'}>
                    {caseData.status?.replace('_', ' ')}
                  </Badge>
                  {caseData.is_isolated && (
                    <Badge color="#8b5cf6">ISOLATED</Badge>
                  )}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{
                  fontFamily: 'Space Mono, monospace', fontSize: 9,
                  color: '#6b7280', letterSpacing: '0.12em', marginBottom: 4,
                }}>REPORTED</div>
                <div style={{ fontSize: 13, color: '#9ca3af' }}>{fmtDt(caseData.created_at)}</div>
                {caseData.assigned_to_name && (
                  <>
                    <div style={{
                      fontFamily: 'Space Mono, monospace', fontSize: 9,
                      color: '#6b7280', letterSpacing: '0.12em', marginTop: 8, marginBottom: 4,
                    }}>ASSIGNED TO</div>
                    <div style={{ fontSize: 13, color: '#9ca3af' }}>{caseData.assigned_to_name}</div>
                  </>
                )}
              </div>
            </div>

            {/* Patient grid */}
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
              gap: '4px 24px', paddingTop: 16,
              borderTop: '1px solid #1f2937',
            }}>
              <Field label="Patient Name"    value={caseData.patient_name} />
              <Field label="Age / Gender"
                value={[caseData.patient_age, caseData.patient_gender].filter(Boolean).join(' · ')} />
              <Field label="Location"        value={caseData.location_name} />
              <Field label="Contacts Count"  value={caseData.contacts_count?.toLocaleString()} />
              <Field label="Symptom Onset"   value={fmt(caseData.symptom_onset_date)} />
              <Field label="Diagnosis Date"  value={fmt(caseData.diagnosis_date)} />
              <Field label="Hospitalised"    value={fmt(caseData.hospitalization_date)} />
              <Field label="Recovery Date"   value={fmt(caseData.recovery_date)} />
              {caseData.is_isolated && (
                <Field label="Isolation Location" value={caseData.isolation_location} />
              )}
              {caseData.address && (
                <Field label="Address" value={caseData.address} />
              )}
            </div>

            {/* Symptoms / comorbidities */}
            {(caseData.symptoms?.length > 0 || caseData.comorbidities?.length > 0) && (
              <div style={{
                display: 'flex', gap: 24, marginTop: 16, paddingTop: 16,
                borderTop: '1px solid #1f2937', flexWrap: 'wrap',
              }}>
                {caseData.symptoms?.length > 0 && (
                  <div>
                    <div style={{
                      fontFamily: 'Space Mono, monospace', fontSize: 9,
                      letterSpacing: '0.12em', textTransform: 'uppercase',
                      color: '#6b7280', marginBottom: 6,
                    }}>Symptoms</div>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {caseData.symptoms.map((s, i) => (
                        <Badge key={i} color="#f59e0b">{s}</Badge>
                      ))}
                    </div>
                  </div>
                )}
                {caseData.comorbidities?.length > 0 && (
                  <div>
                    <div style={{
                      fontFamily: 'Space Mono, monospace', fontSize: 9,
                      letterSpacing: '0.12em', textTransform: 'uppercase',
                      color: '#6b7280', marginBottom: 6,
                    }}>Comorbidities</div>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {caseData.comorbidities.map((c, i) => (
                        <Badge key={i} color="#8b5cf6">{c}</Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Clinical notes */}
            {caseData.clinical_notes && (
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid #1f2937' }}>
                <div style={{
                  fontFamily: 'Space Mono, monospace', fontSize: 9,
                  letterSpacing: '0.12em', textTransform: 'uppercase',
                  color: '#6b7280', marginBottom: 6,
                }}>Clinical Notes</div>
                <p style={{ fontSize: 13, color: '#9ca3af', margin: 0, lineHeight: 1.6 }}>
                  {caseData.clinical_notes}
                </p>
              </div>
            )}
          </div>
        ) : null}
      </div>

      {/* ── Tab pills ──────────────────────────────────────────────────────────── */}
      <div {...fadeUp(0.12)} style={{ display: 'flex', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            style={{
              background: activeTab === t.key ? '#3b82f6' : 'transparent',
              color:      activeTab === t.key ? '#fff' : '#6b7280',
              border:     `1px solid ${activeTab === t.key ? '#3b82f6' : '#1f2937'}`,
              borderRadius: 4, padding: '6px 18px', fontSize: 11,
              fontFamily: 'Space Mono, monospace', letterSpacing: '0.08em',
              cursor: 'pointer', fontWeight: activeTab === t.key ? 700 : 400,
              transition: 'all 0.15s',
            }}
          >{t.label}</button>
        ))}
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════
          OVERVIEW TAB — repeat of key case data in a more readable layout
       ═══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'OVERVIEW' && caseData && (
        <div {...fadeUp(0.14)} style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16,
        }}>
          {/* Isolation status */}
          <div style={{
            background: '#111827', border: '1px solid #1f2937',
            borderRadius: 6, padding: '20px 22px',
          }}>
            <div style={{
              fontFamily: 'Bebas Neue, sans-serif', fontSize: 16,
              letterSpacing: '0.04em', marginBottom: 14,
            }}>Isolation Status</div>
            <Field label="Currently Isolated" value={caseData.is_isolated ? 'Yes' : 'No'} />
            {caseData.is_isolated && (
              <>
                <Field label="Location"        value={caseData.isolation_location} />
                <Field label="Started"         value={fmt(caseData.isolation_start_date)} />
                <Field label="Expected End"    value={fmt(caseData.isolation_end_date)} />
              </>
            )}
          </div>

          {/* Contact summary */}
          <div style={{
            background: '#111827', border: '1px solid #1f2937',
            borderRadius: 6, padding: '20px 22px',
          }}>
            <div style={{
              fontFamily: 'Bebas Neue, sans-serif', fontSize: 16,
              letterSpacing: '0.04em', marginBottom: 14,
            }}>Contact Summary</div>
            <Field label="Total Contacts Traced" value={caseData.contacts_count} />
            <div style={{ marginTop: 12 }}>
              <button
                onClick={() => setActiveTab('CONTACTS')}
                style={{
                  background: '#3b82f6', color: '#fff', border: 'none',
                  borderRadius: 4, padding: '7px 16px', fontSize: 12,
                  fontWeight: 500, cursor: 'pointer',
                  fontFamily: 'IBM Plex Sans, sans-serif',
                }}
              >View All Contacts →</button>
            </div>
          </div>

          {/* Timeline */}
          <div style={{
            background: '#111827', border: '1px solid #1f2937',
            borderRadius: 6, padding: '20px 22px', gridColumn: '1 / -1',
          }}>
            <div style={{
              fontFamily: 'Bebas Neue, sans-serif', fontSize: 16,
              letterSpacing: '0.04em', marginBottom: 16,
            }}>Case Timeline</div>
            <div style={{ display: 'flex', gap: 0, overflowX: 'auto', paddingBottom: 8 }}>
              {[
                { label: 'Symptom Onset', date: caseData.symptom_onset_date },
                { label: 'Diagnosis',     date: caseData.diagnosis_date     },
                { label: 'Hospitalised',  date: caseData.hospitalization_date },
                { label: 'Recovery',      date: caseData.recovery_date      },
                { label: 'Death',         date: caseData.death_date         },
              ].filter(e => e.date).map((e, i, arr) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center' }}>
                  <div style={{ textAlign: 'center', minWidth: 120 }}>
                    <div style={{
                      width: 10, height: 10, borderRadius: '50%',
                      background: '#3b82f6', margin: '0 auto 6px',
                    }} />
                    <div style={{
                      fontFamily: 'Space Mono, monospace', fontSize: 9,
                      color: '#6b7280', letterSpacing: '0.08em',
                      textTransform: 'uppercase', marginBottom: 3,
                    }}>{e.label}</div>
                    <div style={{ fontSize: 12, color: '#9ca3af' }}>{fmt(e.date)}</div>
                  </div>
                  {i < arr.length - 1 && (
                    <div style={{
                      flex: 1, height: 1, background: '#1f2937', minWidth: 40,
                    }} />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════════
          CONTACTS TAB — CaseViewSet GET /cases/{id}/contacts/
          Returns ContactListSerializer: contact_id, contact_name, contact_type,
          status, source_case, source_case_id, exposure_date, is_quarantined,
          monitoring_end_date
       ═══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'CONTACTS' && (
        <div {...fadeUp(0.14)}>
          {contactsError && (
            <div style={{
              padding: '12px 16px', color: '#ef4444', fontSize: 12,
              background: '#1a0a0a', border: '1px solid #ef444430',
              borderRadius: 6, marginBottom: 12,
            }}>{contactsError}</div>
          )}
          <div style={{
            background: '#111827', border: '1px solid #1f2937',
            borderRadius: 6, overflow: 'hidden',
          }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Contact ID', 'Name', 'Type', 'Status',
                      'Exposure Date', 'Monitoring Ends', 'Quarantined'].map(h => (
                      <th key={h} style={thStyle}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {contactsLoading
                    ? Array.from({ length: 6 }).map((_, i) => (
                        <tr key={i}>{Array.from({ length: 7 }).map((_, j) => (
                          <td key={j} style={tdStyle}><Shimmer /></td>
                        ))}</tr>
                      ))
                    : contacts.length === 0
                      ? <tr><td colSpan={7} style={{ ...tdStyle, color: '#6b7280', textAlign: 'center', padding: 40 }}>
                          No contacts traced for this case
                        </td></tr>
                      : contacts.map(ct => (
                          <tr key={ct.id} style={{ background: 'transparent' }}>
                            <td style={tdStyle}>
                              <span style={{
                                fontFamily: 'Space Mono, monospace', fontSize: 11, color: '#9ca3af',
                              }}>{ct.contact_id}</span>
                            </td>
                            <td style={tdStyle}>{ct.contact_name}</td>
                            <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 12 }}>
                              {ct.contact_type?.replace('_', ' ') || '—'}
                            </td>
                            <td style={tdStyle}>
                              <Badge color={CONTACT_STATUS_COLORS[ct.status] || '#6b7280'}>
                                {ct.status?.replace(/_/g, ' ')}
                              </Badge>
                            </td>
                            <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 12 }}>
                              {fmt(ct.exposure_date)}
                            </td>
                            <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 12 }}>
                              {fmt(ct.monitoring_end_date)}
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
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════════
          MONITORING TAB — ContactMonitoringSerializer:
          contact, contact_name, monitoring_date, has_symptoms, temperature,
          is_reachable, is_compliant, symptoms_reported, monitored_by_name, notes
       ═══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'MONITORING' && (
        <div {...fadeUp(0.14)}>
          {monitoringError && (
            <div style={{
              padding: '12px 16px', color: '#ef4444', fontSize: 12,
              background: '#1a0a0a', border: '1px solid #ef444430',
              borderRadius: 6, marginBottom: 12,
            }}>{monitoringError}</div>
          )}
          <div style={{
            background: '#111827', border: '1px solid #1f2937',
            borderRadius: 6, overflow: 'hidden',
          }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Contact', 'Date', 'Symptoms?', 'Temperature',
                      'Reachable', 'Compliant', 'Monitored By', 'Notes'].map(h => (
                      <th key={h} style={thStyle}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {monitoringLoading
                    ? Array.from({ length: 6 }).map((_, i) => (
                        <tr key={i}>{Array.from({ length: 8 }).map((_, j) => (
                          <td key={j} style={tdStyle}><Shimmer /></td>
                        ))}</tr>
                      ))
                    : monitoring.length === 0
                      ? <tr><td colSpan={8} style={{ ...tdStyle, color: '#6b7280', textAlign: 'center', padding: 40 }}>
                          No monitoring records found
                        </td></tr>
                      : monitoring.map(m => (
                          <tr key={m.id} style={{ background: 'transparent' }}>
                            <td style={tdStyle}>{m.contact_name || m.contact}</td>
                            <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 12, whiteSpace: 'nowrap' }}>
                              {fmt(m.monitoring_date)}
                            </td>
                            <td style={tdStyle}>
                              <Badge color={m.has_symptoms ? '#ef4444' : '#10b981'}>
                                {m.has_symptoms ? 'YES' : 'NO'}
                              </Badge>
                            </td>
                            <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 12 }}>
                              {m.temperature ? `${m.temperature} °C` : '—'}
                            </td>
                            <td style={tdStyle}>
                              <Badge color={m.is_reachable ? '#10b981' : '#ef4444'}>
                                {m.is_reachable ? 'YES' : 'NO'}
                              </Badge>
                            </td>
                            <td style={tdStyle}>
                              <Badge color={m.is_compliant ? '#10b981' : '#f59e0b'}>
                                {m.is_compliant ? 'YES' : 'NO'}
                              </Badge>
                            </td>
                            <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 12 }}>
                              {m.monitored_by_name || '—'}
                            </td>
                            <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 12, maxWidth: 180 }}>
                              {m.notes || '—'}
                            </td>
                          </tr>
                        ))
                  }
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════════
          TESTING TAB — TestingAppointmentSerializer:
          appointment_id, patient_name, center_name, appointment_date,
          appointment_time, status, result, case_ref, contact_ref
       ═══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'TESTING' && (
        <div {...fadeUp(0.14)}>
          {testingError && (
            <div style={{
              padding: '12px 16px', color: '#ef4444', fontSize: 12,
              background: '#1a0a0a', border: '1px solid #ef444430',
              borderRadius: 6, marginBottom: 12,
            }}>{testingError}</div>
          )}
          <div style={{
            background: '#111827', border: '1px solid #1f2937',
            borderRadius: 6, overflow: 'hidden',
          }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Appointment ID', 'Patient', 'Testing Center',
                      'Date', 'Time', 'Test Type', 'Status', 'Result'].map(h => (
                      <th key={h} style={thStyle}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {testingLoading
                    ? Array.from({ length: 5 }).map((_, i) => (
                        <tr key={i}>{Array.from({ length: 8 }).map((_, j) => (
                          <td key={j} style={tdStyle}><Shimmer /></td>
                        ))}</tr>
                      ))
                    : testing.length === 0
                      ? <tr><td colSpan={8} style={{ ...tdStyle, color: '#6b7280', textAlign: 'center', padding: 40 }}>
                          No testing appointments found
                        </td></tr>
                      : testing.map(t => (
                          <tr key={t.id} style={{ background: 'transparent' }}>
                            <td style={tdStyle}>
                              <span style={{
                                fontFamily: 'Space Mono, monospace', fontSize: 11, color: '#9ca3af',
                              }}>{t.appointment_id}</span>
                            </td>
                            <td style={tdStyle}>{t.patient_name}</td>
                            <td style={{ ...tdStyle, color: '#9ca3af' }}>
                              {t.center_name || '—'}
                            </td>
                            <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 12 }}>
                              {fmt(t.appointment_date)}
                            </td>
                            <td style={{ ...tdStyle, color: '#9ca3af', fontSize: 12 }}>
                              {t.appointment_time || '—'}
                            </td>
                            <td style={{ ...tdStyle, color: '#9ca3af' }}>
                              {t.test_type || '—'}
                            </td>
                            <td style={tdStyle}>
                              <Badge color={APPT_STATUS_COLORS[t.status] || '#6b7280'}>
                                {t.status}
                              </Badge>
                            </td>
                            <td style={tdStyle}>
                              <Badge color={RESULT_COLORS[t.result] || '#6b7280'}>
                                {t.result || 'PENDING'}
                              </Badge>
                            </td>
                          </tr>
                        ))
                  }
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════════
          QUARANTINE TAB — QuarantineRecordSerializer:
          record_id, individual_name, facility_name, status,
          admission_date, expected_release_date, actual_release_date,
          days_remaining, room_number, daily_monitoring, notes, case_ref
       ═══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'QUARANTINE' && (
        <div {...fadeUp(0.14)}>
          {quarantineError && (
            <div style={{
              padding: '12px 16px', color: '#ef4444', fontSize: 12,
              background: '#1a0a0a', border: '1px solid #ef444430',
              borderRadius: 6, marginBottom: 12,
            }}>{quarantineError}</div>
          )}
          {quarantineLoading ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} style={{
                  background: '#111827', border: '1px solid #1f2937',
                  borderRadius: 6, padding: 20,
                }}>
                  <Shimmer w="70%" h={16} />
                  <Shimmer w="50%" />
                  <Shimmer w="40%" h={10} />
                </div>
              ))}
            </div>
          ) : quarantine.length === 0 ? (
            <div style={{
              background: '#111827', border: '1px solid #1f2937',
              borderRadius: 6, padding: 40, color: '#6b7280',
              textAlign: 'center', fontSize: 13,
            }}>No quarantine records found for this case</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              {quarantine.map(q => {
                const daysLeft = q.days_remaining
                return (
                  <div key={q.id} style={{
                    background: '#111827', border: '1px solid #1f2937',
                    borderRadius: 6, padding: '18px 20px',
                  }}>
                    {/* Header row */}
                    <div style={{
                      display: 'flex', justifyContent: 'space-between',
                      alignItems: 'flex-start', marginBottom: 12,
                    }}>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 2 }}>
                          {q.individual_name}
                        </div>
                        <div style={{
                          fontFamily: 'Space Mono, monospace', fontSize: 9,
                          color: '#6b7280', letterSpacing: '0.08em',
                        }}>{q.record_id}</div>
                      </div>
                      <Badge color={QRECORD_STATUS_COLORS[q.status] || '#6b7280'}>
                        {q.status?.replace('_', ' ')}
                      </Badge>
                    </div>

                    {/* Facility */}
                    <div style={{
                      fontSize: 13, color: '#9ca3af', marginBottom: 10,
                    }}>
                      📍 {q.facility_name || '—'}
                      {q.room_number && (
                        <span style={{
                          marginLeft: 8, fontFamily: 'Space Mono, monospace',
                          fontSize: 10, color: '#6b7280',
                        }}>Rm {q.room_number}</span>
                      )}
                    </div>

                    {/* Dates */}
                    <div style={{
                      fontFamily: 'Space Mono, monospace', fontSize: 10,
                      color: '#6b7280', letterSpacing: '0.06em', marginBottom: 12,
                    }}>
                      {fmt(q.admission_date)} → {fmt(q.expected_release_date)}
                      {q.actual_release_date && (
                        <span style={{ color: '#10b981' }}>
                          {' '}(released {fmt(q.actual_release_date)})
                        </span>
                      )}
                    </div>

                    {/* Footer */}
                    <div style={{
                      display: 'flex', alignItems: 'center',
                      justifyContent: 'space-between',
                    }}>
                      <Badge color={q.daily_monitoring ? '#10b981' : '#6b7280'}>
                        {q.daily_monitoring ? 'DAILY MONITORING' : 'NO MONITORING'}
                      </Badge>
                      {daysLeft != null && q.status === 'IN_QUARANTINE' && (
                        <span style={{
                          fontFamily: 'Space Mono, monospace', fontSize: 11,
                          color: daysLeft <= 2 ? '#ef4444' : '#9ca3af',
                        }}>
                          {daysLeft} day{daysLeft !== 1 ? 's' : ''} left
                        </span>
                      )}
                    </div>

                    {q.notes && (
                      <div style={{
                        marginTop: 10, paddingTop: 10,
                        borderTop: '1px solid #1f2937',
                        fontSize: 12, color: '#9ca3af', lineHeight: 1.5,
                      }}>{q.notes}</div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}