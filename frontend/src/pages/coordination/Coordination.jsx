/**
 * Coordination.jsx — OryxShield
 * ========================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Displays:
 *   • Dashboard overview (GET /coordination/dashboard/overview/)
 *   • Agencies list with pagination (GET /coordination/agencies/)
 *   • Coordination teams grid (GET /coordination/teams/)
 *   • Recent tasks sidebar (GET /coordination/tasks/)
 *   • Meetings section (GET /coordination/meetings/)
 *
 * API fields sourced from:
 *   CoordinationDashboardDataSerializer, AgencyListSerializer,
 *   CoordinationTeamListSerializer, TaskListSerializer, MeetingListSerializer
 *
 * Design tokens: bg #0a0f1e, surface #111827, surfaceHigh #151e2e,
 * border #1f2937, accent #3b82f6, fonts: Bebas Neue / Space Mono / IBM Plex Sans
 * Inline styles only. No Tailwind, no CSS modules.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { coordinationApi, extractError } from '../../services/api'

// ─── @keyframes (prefixed to avoid collisions) ────────────────────────────────
const STYLE_TAG = `
@keyframes coord-shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position:  200% 0; }
}
@keyframes coord-fadeUp {
  from { opacity: 0; transform: translateY(14px); }
  to   { opacity: 1; transform: translateY(0);    }
}
`

// ─── Design tokens ────────────────────────────────────────────────────────────
const T = {
  bg:         '#0a0f1e',
  surface:    '#111827',
  surfaceHi:  '#151e2e',
  border:     '#1f2937',
  accent:     '#3b82f6',
  danger:     '#ef4444',
  warning:    '#f59e0b',
  success:    '#10b981',
  text:       '#f9fafb',
  textSub:    '#9ca3af',
  textMuted:  '#6b7280',
}

// ─── Color maps (from backend choices) ───────────────────────────────────────
const PRIORITY_COLOR = {
  LOW: '#10b981', MEDIUM: '#f59e0b', HIGH: '#f97316',
  URGENT: '#f97316', CRITICAL: '#ef4444',
}
const TASK_STATUS_COLOR = {
  PENDING: '#6b7280', ASSIGNED: '#3b82f6', ACCEPTED: '#8b5cf6',
  IN_PROGRESS: '#3b82f6', COMPLETED: '#10b981', CANCELLED: '#6b7280',
}
const TEAM_TYPE_COLOR = {
  INCIDENT: '#ef4444', TASK_FORCE: '#f97316', WORKING_GROUP: '#3b82f6',
  TECHNICAL: '#8b5cf6', EOC: '#ec4899', LIAISON: '#10b981',
}
const MEETING_STATUS_COLOR = {
  SCHEDULED: '#3b82f6', IN_PROGRESS: '#f59e0b',
  COMPLETED: '#10b981', CANCELLED: '#6b7280',
}
const CHANNEL_TYPE_COLOR = {
  EMAIL: '#3b82f6', CHAT: '#10b981', FORUM: '#8b5cf6',
  PHONE: '#f59e0b', RADIO: '#f97316', VIDEO: '#ec4899', PORTAL: '#6b7280',
}
const AGENCY_TYPE_COLOR = {
  HEALTH: '#10b981', EMERGENCY: '#ef4444', MILITARY: '#6b7280',
  INTERNATIONAL: '#3b82f6', NGO: '#8b5cf6', PRIVATE: '#f59e0b',
  COMMUNITY: '#f97316', GOVERNMENT: '#ec4899', OTHER: '#6b7280',
}

// ─── Utility ──────────────────────────────────────────────────────────────────
function fmt(dt) {
  if (!dt) return '—'
  try {
    return new Date(dt).toLocaleDateString('en-NA', { day: '2-digit', month: 'short', year: 'numeric' })
  } catch { return '—' }
}
function fmtDatetime(dt) {
  if (!dt) return '—'
  try {
    return new Date(dt).toLocaleString('en-NA', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
    })
  } catch { return '—' }
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function Badge({ color, children }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 2,
      fontSize: 9,
      fontFamily: 'Space Mono, monospace',
      fontWeight: 700,
      letterSpacing: '0.12em',
      textTransform: 'uppercase',
      color,
      background: color + '18',
      border: `1px solid ${color}30`,
      whiteSpace: 'nowrap',
    }}>
      {children}
    </span>
  )
}

function ShimmerBox({ h = 44, mb = 4 }) {
  return (
    <div style={{
      height: h,
      borderRadius: 4,
      background: `linear-gradient(90deg, ${T.surface} 0%, ${T.surfaceHi} 50%, ${T.surface} 100%)`,
      backgroundSize: '200% 100%',
      animation: 'coord-shimmer 1.5s infinite',
      marginBottom: mb,
    }} />
  )
}

function SectionHeader({ icon, label, count, color = T.accent }) {
  return (
    <div style={{
      padding: '12px 20px',
      borderBottom: `1px solid ${T.border}`,
      display: 'flex',
      alignItems: 'center',
      gap: 8,
    }}>
      <span style={{ color }}>{icon}</span>
      <span style={{
        fontFamily: 'Space Mono, monospace',
        fontSize: 9,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        color: T.textSub,
        fontWeight: 700,
      }}>{label}</span>
      {count !== undefined && (
        <span style={{
          marginLeft: 'auto',
          fontFamily: 'Space Mono, monospace',
          fontSize: 10,
          color: T.textMuted,
        }}>{count}</span>
      )}
    </div>
  )
}

function ProgressBar({ value = 0 }) {
  const pct = Math.min(100, Math.max(0, value))
  const color = pct >= 100 ? T.success : pct >= 60 ? T.accent : pct >= 30 ? T.warning : T.textMuted
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, height: 3, background: T.border, borderRadius: 2 }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.4s' }} />
      </div>
      <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textMuted, minWidth: 26 }}>
        {pct}%
      </span>
    </div>
  )
}

// ─── SVG Icons ────────────────────────────────────────────────────────────────
const IcoAgency = (s = 14) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v3M12 14v3M16 14v3" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)
const IcoTeam = (s = 14) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)
const IcoTask = (s = 14) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)
const IcoMeeting = (s = 14) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
    <line x1="16" y1="2" x2="16" y2="6"/>
    <line x1="8" y1="2" x2="8" y2="6"/>
    <line x1="3" y1="10" x2="21" y2="10"/>
  </svg>
)
const IcoChevDown = (s = 14) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
    <path d="M19 9l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)
const IcoRefresh = (s = 14) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)
const IcoAlert = (s = 14) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)
const IcoDoc = (s = 14) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

// ─── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({ label, value, icon, color, loading }) {
  const [hover, setHover] = useState(false)
  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: hover ? T.surfaceHi : T.surface,
        border: `1px solid ${hover ? color + '40' : T.border}`,
        borderRadius: 6,
        padding: '18px 20px',
        transition: 'all 0.15s',
        cursor: 'default',
        animation: 'coord-fadeUp 0.3s ease both',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textMuted }}>
          {label}
        </span>
        <span style={{ color, opacity: 0.7 }}>{icon}</span>
      </div>
      {loading ? (
        <div style={{ height: 28, borderRadius: 3, background: `linear-gradient(90deg, ${T.surface} 0%, ${T.surfaceHi} 50%, ${T.surface} 100%)`, backgroundSize: '200% 100%', animation: 'coord-shimmer 1.5s infinite' }} />
      ) : (
        <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 28, color: T.text, letterSpacing: '0.02em' }}>
          {value ?? '—'}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────
export default function Coordination() {
  const navigate = useNavigate()

  // ── State ──────────────────────────────────────────────────────────────────
  const [overview, setOverview]           = useState(null)
  const [overviewLoading, setOvLoad]      = useState(true)
  const [overviewError, setOvErr]         = useState(null)

  const [agencies, setAgencies]           = useState([])
  const [agenciesLoad, setAgLoad]         = useState(true)
  const [agenciesErr, setAgErr]           = useState(null)
  const [agPage, setAgPage]               = useState(1)
  const [agTotal, setAgTotal]             = useState(0)
  const [agSearch, setAgSearch]           = useState('')
  const [agType, setAgType]               = useState('')

  const [teams, setTeams]                 = useState([])
  const [teamsLoad, setTmLoad]            = useState(true)
  const [teamsErr, setTmErr]              = useState(null)
  const [teamsOpen, setTeamsOpen]         = useState(true)
  const [teamsFilter, setTeamsFilter]     = useState('')   // '' = all, 'active' = active only

  const [tasks, setTasks]                 = useState([])
  const [tasksLoad, setTkLoad]            = useState(true)
  const [tasksErr, setTkErr]              = useState(null)
  const [tasksFilter, setTasksFilter]     = useState('')   // priority filter

  const [meetings, setMeetings]           = useState([])
  const [meetLoad, setMtLoad]             = useState(true)
  const [meetErr, setMtErr]               = useState(null)
  const [meetingsOpen, setMeetingsOpen]   = useState(false)

  const [hoverCard, setHoverCard]         = useState(null)
  const [hoverRow, setHoverRow]           = useState(null)
  const [hoverBtn, setHoverBtn]           = useState(null)

  const PAGE_SIZE = 12

  // ── Fetch overview ─────────────────────────────────────────────────────────
  const fetchOverview = useCallback(async () => {
    setOvLoad(true); setOvErr(null)
    try {
      const res = await coordinationApi.coordinationDashboard()
      setOverview(res.data)
    } catch (e) { setOvErr(extractError(e)) }
    finally { setOvLoad(false) }
  }, [])

  // ── Fetch agencies ─────────────────────────────────────────────────────────
  const fetchAgencies = useCallback(async (page, search, type) => {
    setAgLoad(true); setAgErr(null)
    try {
      const params = { page, page_size: PAGE_SIZE }
      if (search) params.search = search
      if (type)   params.agency_type = type
      const res = await coordinationApi.listAgencies(params)
      setAgencies(res.data.results ?? res.data)
      setAgTotal(res.data.count ?? 0)
    } catch (e) { setAgErr(extractError(e)) }
    finally { setAgLoad(false) }
  }, [])

  // ── Fetch teams ────────────────────────────────────────────────────────────
  const fetchTeams = useCallback(async (filter) => {
    setTmLoad(true); setTmErr(null)
    try {
      const params = { page_size: 50 }
      if (filter === 'active') params.is_active = true
      const res = await coordinationApi.listTeams(params)
      setTeams(res.data.results ?? res.data)
    } catch (e) { setTmErr(extractError(e)) }
    finally { setTmLoad(false) }
  }, [])

  // ── Fetch tasks ────────────────────────────────────────────────────────────
  const fetchTasks = useCallback(async (priority) => {
    setTkLoad(true); setTkErr(null)
    try {
      const params = { page_size: 12, ordering: 'due_date' }
      if (priority) params.priority = priority
      const res = await coordinationApi.listTasks(params)
      setTasks(res.data.results ?? res.data)
    } catch (e) { setTkErr(extractError(e)) }
    finally { setTkLoad(false) }
  }, [])

  // ── Fetch meetings ─────────────────────────────────────────────────────────
  const fetchMeetings = useCallback(async () => {
    setMtLoad(true); setMtErr(null)
    try {
      const res = await coordinationApi.listMeetings({ page_size: 20, ordering: 'scheduled_start' })
      setMeetings(res.data.results ?? res.data)
    } catch (e) { setMtErr(extractError(e)) }
    finally { setMtLoad(false) }
  }, [])

  // ── Effects ────────────────────────────────────────────────────────────────
  useEffect(() => { fetchOverview() }, [fetchOverview])
  useEffect(() => { fetchAgencies(agPage, agSearch, agType) }, [fetchAgencies, agPage, agSearch, agType])
  useEffect(() => { fetchTeams(teamsFilter) }, [fetchTeams, teamsFilter])
  useEffect(() => { fetchTasks(tasksFilter) }, [fetchTasks, tasksFilter])
  useEffect(() => { fetchMeetings() }, [fetchMeetings])

  // ── Derived ────────────────────────────────────────────────────────────────
  const totalPages = Math.ceil(agTotal / PAGE_SIZE)
  const ov = overview ?? {}

  // ── Stat cards config ──────────────────────────────────────────────────────
  const statCards = [
    { label: 'Active Teams',      value: ov.active_teams,      icon: IcoTeam(16),    color: T.success },
    { label: 'Active Tasks',      value: ov.active_tasks,      icon: IcoTask(16),    color: T.warning },
    { label: 'Overdue Tasks',     value: ov.overdue_tasks,     icon: IcoAlert(16),   color: T.danger  },
    { label: 'Upcoming Meetings', value: ov.upcoming_meetings, icon: IcoMeeting(16), color: T.accent  },
  ]

  const btnStyle = (id) => ({
    padding: '5px 12px',
    borderRadius: 3,
    border: `1px solid ${hoverBtn === id ? T.border : 'transparent'}`,
    background: hoverBtn === id ? T.surfaceHi : 'transparent',
    color: T.textSub,
    fontSize: 11,
    fontFamily: 'Space Mono, monospace',
    cursor: 'pointer',
    transition: 'all 0.15s',
    letterSpacing: '0.06em',
  })

  const filterBtnStyle = (id, active) => ({
    padding: '4px 10px',
    borderRadius: 3,
    border: `1px solid ${active ? T.accent + '60' : T.border}`,
    background: active ? T.accent + '14' : 'transparent',
    color: active ? T.accent : T.textMuted,
    fontSize: 10,
    fontFamily: 'Space Mono, monospace',
    cursor: 'pointer',
    transition: 'all 0.15s',
    letterSpacing: '0.06em',
  })

  const thStyle = {
    padding: '8px 12px',
    fontFamily: 'Space Mono, monospace',
    fontSize: 9,
    letterSpacing: '0.12em',
    textTransform: 'uppercase',
    color: T.textMuted,
    background: T.surface,
    borderBottom: `1px solid ${T.border}`,
    fontWeight: 400,
    textAlign: 'left',
    whiteSpace: 'nowrap',
  }

  const tdStyle = {
    padding: '10px 12px',
    fontSize: 12,
    color: T.text,
    borderBottom: `1px solid ${T.border}`,
    verticalAlign: 'middle',
  }

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div style={{ minHeight: '100vh', background: T.bg, fontFamily: 'IBM Plex Sans, sans-serif', color: T.text }}>
      <style>{STYLE_TAG}</style>

      {/* ── Page Header ── */}
      <div style={{ padding: '28px 32px 0', animation: 'coord-fadeUp 0.25s ease both' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 4 }}>
          <div>
            <h1 style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 32, color: T.text, letterSpacing: '0.06em', margin: 0, lineHeight: 1 }}>
              COORDINATION
            </h1>
            <p style={{ fontSize: 12, color: T.textMuted, margin: '6px 0 0', fontFamily: 'IBM Plex Sans, sans-serif' }}>
              Multi-agency coordination platform — teams, tasks, meetings &amp; information products
            </p>
          </div>
          <button
            onMouseEnter={() => setHoverBtn('refresh')}
            onMouseLeave={() => setHoverBtn(null)}
            onClick={() => { fetchOverview(); fetchAgencies(agPage, agSearch, agType); fetchTeams(teamsFilter); fetchTasks(tasksFilter); fetchMeetings() }}
            style={{ ...btnStyle('refresh'), display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}
          >
            <span style={{ color: T.accent }}>{IcoRefresh(12)}</span>
            Refresh
          </button>
        </div>

        {overviewError && (
          <div style={{ marginTop: 12, padding: '10px 16px', background: T.danger + '14', border: `1px solid ${T.danger}30`, borderRadius: 4, color: T.danger, fontSize: 12 }}>
            {overviewError}
          </div>
        )}
      </div>

      {/* ── Stat Cards ── */}
      <div style={{ padding: '20px 32px 0', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
        {statCards.map((s) => (
          <StatCard key={s.label} label={s.label} value={s.value} icon={s.icon} color={s.color} loading={overviewLoading} />
        ))}
      </div>

      {/* ── Body: main + sidebar ── */}
      <div style={{ padding: '20px 32px 40px', display: 'flex', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>

        {/* ═══ MAIN COLUMN ════════════════════════════════════════════════════ */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* ── Agencies Section ── */}
          <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden', animation: 'coord-fadeUp 0.3s ease both' }}>
            <div style={{ padding: '12px 20px', borderBottom: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <span style={{ color: T.accent }}>{IcoAgency(14)}</span>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textSub, fontWeight: 700 }}>
                Partner Agencies
              </span>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textMuted }}>
                {agTotal > 0 ? `${agTotal} total` : ''}
              </span>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                {/* Search */}
                <input
                  value={agSearch}
                  onChange={e => { setAgSearch(e.target.value); setAgPage(1) }}
                  placeholder="Search agencies…"
                  style={{
                    background: T.bg,
                    border: `1px solid ${T.border}`,
                    borderRadius: 3,
                    padding: '4px 10px',
                    color: T.text,
                    fontSize: 11,
                    fontFamily: 'IBM Plex Sans, sans-serif',
                    outline: 'none',
                    width: 160,
                  }}
                />
                {/* Type filter */}
                <select
                  value={agType}
                  onChange={e => { setAgType(e.target.value); setAgPage(1) }}
                  style={{
                    background: T.bg,
                    border: `1px solid ${T.border}`,
                    borderRadius: 3,
                    padding: '4px 8px',
                    color: agType ? T.text : T.textMuted,
                    fontSize: 11,
                    fontFamily: 'IBM Plex Sans, sans-serif',
                    outline: 'none',
                    cursor: 'pointer',
                  }}
                >
                  <option value="">All Types</option>
                  {['HEALTH','EMERGENCY','MILITARY','INTERNATIONAL','NGO','PRIVATE','COMMUNITY','GOVERNMENT','OTHER'].map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Agency table */}
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    {['Agency', 'Acronym', 'Type', 'Contact', 'Email', 'Status'].map(h => (
                      <th key={h} style={thStyle}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {agenciesLoad ? (
                    <tr><td colSpan={6} style={{ padding: 16 }}>
                      {[...Array(5)].map((_, i) => <ShimmerBox key={i} />)}
                    </td></tr>
                  ) : agenciesErr ? (
                    <tr><td colSpan={6} style={{ ...tdStyle, color: T.danger, textAlign: 'center' }}>{agenciesErr}</td></tr>
                  ) : agencies.length === 0 ? (
                    <tr><td colSpan={6} style={{ ...tdStyle, color: T.textMuted, textAlign: 'center' }}>No agencies found</td></tr>
                  ) : agencies.map((a, i) => (
                    <tr
                      key={a.id}
                      onMouseEnter={() => setHoverRow('ag-' + i)}
                      onMouseLeave={() => setHoverRow(null)}
                      style={{ background: hoverRow === 'ag-' + i ? 'rgba(255,255,255,0.02)' : 'transparent', cursor: 'default' }}
                    >
                      <td style={{ ...tdStyle, fontWeight: 500, maxWidth: 200 }}>
                        <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {a.name || '—'}
                        </span>
                      </td>
                      <td style={{ ...tdStyle, fontFamily: 'Space Mono, monospace', fontSize: 11, color: T.textSub }}>
                        {a.acronym || '—'}
                      </td>
                      <td style={tdStyle}>
                        <Badge color={AGENCY_TYPE_COLOR[a.agency_type] ?? T.textMuted}>
                          {a.agency_type ?? 'OTHER'}
                        </Badge>
                      </td>
                      <td style={{ ...tdStyle, color: T.textSub, maxWidth: 160 }}>
                        <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {/* AgencyListSerializer doesn't include primary_contact; shown from full serializer if present */}
                          —
                        </span>
                      </td>
                      <td style={{ ...tdStyle, color: T.accent, fontSize: 11 }}>
                        {a.contact_email
                          ? <a href={`mailto:${a.contact_email}`} style={{ color: T.accent, textDecoration: 'none' }}>{a.contact_email}</a>
                          : '—'}
                      </td>
                      <td style={tdStyle}>
                        <Badge color={a.is_active ? T.success : T.textMuted}>
                          {a.is_active ? 'ACTIVE' : 'INACTIVE'}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div style={{ padding: '10px 20px', borderTop: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <button
                  onClick={() => setAgPage(p => Math.max(1, p - 1))}
                  disabled={agPage === 1}
                  onMouseEnter={() => setHoverBtn('pg-prev')}
                  onMouseLeave={() => setHoverBtn(null)}
                  style={{ ...btnStyle('pg-prev'), opacity: agPage === 1 ? 0.4 : 1, cursor: agPage === 1 ? 'not-allowed' : 'pointer' }}
                >← Prev</button>
                <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textMuted }}>
                  {agPage} / {totalPages}
                </span>
                <button
                  onClick={() => setAgPage(p => Math.min(totalPages, p + 1))}
                  disabled={agPage === totalPages}
                  onMouseEnter={() => setHoverBtn('pg-next')}
                  onMouseLeave={() => setHoverBtn(null)}
                  style={{ ...btnStyle('pg-next'), opacity: agPage === totalPages ? 0.4 : 1, cursor: agPage === totalPages ? 'not-allowed' : 'pointer' }}
                >Next →</button>
              </div>
            )}
          </div>

          {/* ── Teams Section ── */}
          <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden', animation: 'coord-fadeUp 0.35s ease both' }}>
            <button
              onClick={() => setTeamsOpen(o => !o)}
              onMouseEnter={() => setHoverBtn('teams-toggle')}
              onMouseLeave={() => setHoverBtn(null)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '12px 20px',
                background: hoverBtn === 'teams-toggle' ? 'rgba(255,255,255,0.02)' : 'transparent',
                border: 'none',
                borderBottom: teamsOpen ? `1px solid ${T.border}` : 'none',
                cursor: 'pointer',
                transition: 'background 0.15s',
              }}
            >
              <span style={{ color: T.success }}>{IcoTeam(14)}</span>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textSub, fontWeight: 700 }}>
                Coordination Teams
              </span>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textMuted }}>
                {teams.length > 0 ? `${teams.length} teams` : ''}
              </span>
              <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
                {teamsOpen && (
                  <div style={{ display: 'flex', gap: 4 }} onClick={e => e.stopPropagation()}>
                    {[{ v: '', l: 'All' }, { v: 'active', l: 'Active' }].map(f => (
                      <button
                        key={f.v}
                        onClick={() => setTeamsFilter(f.v)}
                        style={filterBtnStyle(f.v, teamsFilter === f.v)}
                      >{f.l}</button>
                    ))}
                  </div>
                )}
                <span style={{ color: T.textMuted, transform: teamsOpen ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.2s' }}>
                  {IcoChevDown(13)}
                </span>
              </div>
            </button>

            {teamsOpen && (
              <div style={{ padding: 16 }}>
                {teamsLoad ? (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 180px), 1fr))', gap: 10 }}>
                    {[...Array(6)].map((_, i) => <ShimmerBox key={i} h={100} mb={0} />)}
                  </div>
                ) : teamsErr ? (
                  <div style={{ color: T.danger, fontSize: 13, padding: '8px 4px' }}>{teamsErr}</div>
                ) : teams.length === 0 ? (
                  <div style={{ color: T.textMuted, fontSize: 13, padding: '8px 4px' }}>No teams found</div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 180px), 1fr))', gap: 10 }}>
                    {teams.map((t, i) => {
                      const typeColor = TEAM_TYPE_COLOR[t.team_type] ?? T.accent
                      return (
                        <div
                          key={t.id}
                          onClick={() => navigate('/dashboard/coordination/' + t.id)}
                          onMouseEnter={() => setHoverCard('tm-' + i)}
                          onMouseLeave={() => setHoverCard(null)}
                          style={{
                            background: hoverCard === 'tm-' + i ? T.surfaceHi : T.bg,
                            border: `1px solid ${hoverCard === 'tm-' + i ? typeColor + '50' : T.border}`,
                            borderRadius: 5,
                            padding: '14px 16px',
                            cursor: 'pointer',
                            transition: 'all 0.15s',
                            borderLeft: `3px solid ${t.is_active ? typeColor : T.textMuted}`,
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                            <span style={{ fontSize: 13, fontWeight: 600, color: T.text, lineHeight: 1.3, flex: 1, marginRight: 8 }}>
                              {t.name || '—'}
                            </span>
                            <Badge color={t.is_active ? T.success : T.textMuted}>
                              {t.is_active ? 'ACTIVE' : 'INACTIVE'}
                            </Badge>
                          </div>
                          <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
                            <Badge color={typeColor}>{t.team_type ?? 'TEAM'}</Badge>
                            <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted, letterSpacing: '0.08em' }}>
                              [{t.code}]
                            </span>
                          </div>
                          <div style={{ fontSize: 11, color: T.textSub, marginBottom: 8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            Lead: {t.lead_agency_name ?? '—'}
                          </div>
                          <div style={{ display: 'flex', gap: 14 }}>
                            <span style={{ fontSize: 11, fontFamily: 'Space Mono, monospace', color: T.textMuted }}>
                              <span style={{ color: T.text }}>{t.member_count ?? 0}</span> members
                            </span>
                            {t.activated_at && (
                              <span style={{ fontSize: 10, fontFamily: 'Space Mono, monospace', color: T.textMuted }}>
                                {fmt(t.activated_at)}
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ── Meetings Section (collapsible) ── */}
          <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden', animation: 'coord-fadeUp 0.4s ease both' }}>
            <button
              onClick={() => setMeetingsOpen(o => !o)}
              onMouseEnter={() => setHoverBtn('mtg-toggle')}
              onMouseLeave={() => setHoverBtn(null)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '12px 20px',
                background: hoverBtn === 'mtg-toggle' ? 'rgba(255,255,255,0.02)' : 'transparent',
                border: 'none',
                borderBottom: meetingsOpen ? `1px solid ${T.border}` : 'none',
                cursor: 'pointer',
                transition: 'background 0.15s',
              }}
            >
              <span style={{ color: T.accent }}>{IcoMeeting(14)}</span>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textSub, fontWeight: 700 }}>
                Scheduled Meetings
              </span>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textMuted }}>
                {meetings.length > 0 ? `${meetings.length} meetings` : ''}
              </span>
              <span style={{ marginLeft: 'auto', color: T.textMuted, transform: meetingsOpen ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.2s' }}>
                {IcoChevDown(13)}
              </span>
            </button>

            {meetingsOpen && (
              <div style={{ overflowX: 'auto' }}>
                {meetLoad ? (
                  <div style={{ padding: 16 }}>{[...Array(4)].map((_, i) => <ShimmerBox key={i} />)}</div>
                ) : meetErr ? (
                  <div style={{ padding: '12px 20px', color: T.danger, fontSize: 13 }}>{meetErr}</div>
                ) : meetings.length === 0 ? (
                  <div style={{ padding: '12px 20px', color: T.textMuted, fontSize: 13 }}>No meetings found</div>
                ) : (
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr>
                        {['Title', 'Team', 'Type', 'Scheduled', 'Mode', 'Status'].map(h => (
                          <th key={h} style={thStyle}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {meetings.map((m, i) => (
                        <tr
                          key={m.id}
                          onMouseEnter={() => setHoverRow('mt-' + i)}
                          onMouseLeave={() => setHoverRow(null)}
                          style={{ background: hoverRow === 'mt-' + i ? 'rgba(255,255,255,0.02)' : 'transparent' }}
                        >
                          <td style={{ ...tdStyle, fontWeight: 500, maxWidth: 220 }}>
                            <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {m.title || '—'}
                            </span>
                          </td>
                          <td style={{ ...tdStyle, color: T.textSub, maxWidth: 160 }}>
                            <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {m.team_name || '—'}
                            </span>
                          </td>
                          <td style={tdStyle}>
                            <Badge color={T.accent}>{m.meeting_type ?? '—'}</Badge>
                          </td>
                          <td style={{ ...tdStyle, fontFamily: 'Space Mono, monospace', fontSize: 11, color: T.textSub, whiteSpace: 'nowrap' }}>
                            {fmtDatetime(m.scheduled_start)}
                          </td>
                          <td style={tdStyle}>
                            <Badge color={m.is_virtual ? '#8b5cf6' : T.textMuted}>
                              {m.is_virtual ? 'VIRTUAL' : 'IN-PERSON'}
                            </Badge>
                          </td>
                          <td style={tdStyle}>
                            <Badge color={MEETING_STATUS_COLOR[m.status] ?? T.textMuted}>
                              {m.status || 'UNKNOWN'}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>

          {/* ── Dashboard: Critical Tasks + Tasks by Priority ── */}
          {!overviewLoading && overview && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16, animation: 'coord-fadeUp 0.45s ease both' }}>

              {/* Critical Tasks */}
              {overview.critical_tasks?.length > 0 && (
                <div style={{ background: T.surface, border: `1px solid ${T.danger}30`, borderRadius: 6, overflow: 'hidden' }}>
                  <SectionHeader icon={IcoAlert(14)} label="Critical Tasks" color={T.danger} count={overview.critical_tasks.length} />
                  <div style={{ padding: '8px 0' }}>
                    {overview.critical_tasks.map((ct, i) => (
                      <div
                        key={ct.id}
                        onMouseEnter={() => setHoverRow('ct-' + i)}
                        onMouseLeave={() => setHoverRow(null)}
                        style={{
                          padding: '10px 16px',
                          borderBottom: i < overview.critical_tasks.length - 1 ? `1px solid ${T.border}` : 'none',
                          background: hoverRow === 'ct-' + i ? 'rgba(255,255,255,0.02)' : 'transparent',
                          transition: 'background 0.12s',
                        }}
                      >
                        <div style={{ fontSize: 12, fontWeight: 500, color: T.text, marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {ct.title || '—'}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'space-between' }}>
                          <span style={{ fontSize: 11, color: T.textMuted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 120 }}>
                            {ct.assigned_to_agency__name || 'Unassigned'}
                          </span>
                          <ProgressBar value={ct.progress_percentage ?? 0} />
                        </div>
                        <div style={{ marginTop: 4, fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.danger }}>
                          Due {fmt(ct.due_date)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tasks by Priority */}
              {overview.tasks_by_priority && Object.keys(overview.tasks_by_priority).length > 0 && (
                <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden' }}>
                  <SectionHeader icon={IcoTask(14)} label="Tasks by Priority" count="" />
                  <div style={{ padding: 16 }}>
                    {Object.entries(overview.tasks_by_priority).map(([priority, count]) => {
                      const color = PRIORITY_COLOR[priority] ?? T.textMuted
                      const total = Object.values(overview.tasks_by_priority).reduce((a, b) => a + b, 0)
                      const pct = total > 0 ? Math.round((count / total) * 100) : 0
                      return (
                        <div key={priority} style={{ marginBottom: 10 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                            <Badge color={color}>{priority}</Badge>
                            <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 11, color: T.textSub }}>
                              {count}
                            </span>
                          </div>
                          <div style={{ height: 3, background: T.border, borderRadius: 2 }}>
                            <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2 }} />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Recent Information Products */}
              {overview.recent_products?.length > 0 && (
                <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden' }}>
                  <SectionHeader icon={IcoDoc(14)} label="Recent Products" color="#8b5cf6" />
                  <div style={{ padding: '8px 0' }}>
                    {overview.recent_products.map((p, i) => (
                      <div
                        key={p.id}
                        onMouseEnter={() => setHoverRow('rp-' + i)}
                        onMouseLeave={() => setHoverRow(null)}
                        style={{
                          padding: '10px 16px',
                          borderBottom: i < overview.recent_products.length - 1 ? `1px solid ${T.border}` : 'none',
                          background: hoverRow === 'rp-' + i ? 'rgba(255,255,255,0.02)' : 'transparent',
                          transition: 'background 0.12s',
                        }}
                      >
                        <div style={{ fontSize: 12, fontWeight: 500, color: T.text, marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {p.title || '—'}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <Badge color="#8b5cf6">{p.product_type}</Badge>
                          <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textMuted }}>
                            {fmt(p.effective_date)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            </div>
          )}

        </div>

        {/* ═══ TASKS SIDEBAR ══════════════════════════════════════════════════ */}
        <div style={{ width: 270, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 12, animation: 'coord-fadeUp 0.3s ease both' }}>

          {/* Tasks Panel */}
          <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden' }}>
            <div style={{ padding: '12px 16px', borderBottom: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ color: T.warning }}>{IcoTask(14)}</span>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textSub, fontWeight: 700 }}>
                Active Tasks
              </span>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: 3 }}>
                {[{ v: '', l: 'All' }, { v: 'CRITICAL', l: 'CRIT' }, { v: 'HIGH', l: 'HIGH' }].map(f => (
                  <button
                    key={f.v}
                    onClick={() => setTasksFilter(f.v)}
                    style={filterBtnStyle(f.v, tasksFilter === f.v)}
                  >{f.l}</button>
                ))}
              </div>
            </div>

            <div style={{ maxHeight: 460, overflowY: 'auto' }}>
              {tasksLoad ? (
                <div style={{ padding: '8px 12px' }}>
                  {[...Array(5)].map((_, i) => <ShimmerBox key={i} h={62} />)}
                </div>
              ) : tasksErr ? (
                <div style={{ padding: '12px 16px', color: T.danger, fontSize: 12 }}>{tasksErr}</div>
              ) : tasks.length === 0 ? (
                <div style={{ padding: '12px 16px', color: T.textMuted, fontSize: 12 }}>No tasks found</div>
              ) : tasks.map((task, i) => {
                const prColor = PRIORITY_COLOR[task.priority] ?? T.textMuted
                const stColor = TASK_STATUS_COLOR[task.status] ?? T.textMuted
                const isOverdue = task.is_overdue
                return (
                  <div
                    key={task.id}
                    onMouseEnter={() => setHoverCard('tk-' + i)}
                    onMouseLeave={() => setHoverCard(null)}
                    style={{
                      padding: '10px 14px',
                      borderBottom: i < tasks.length - 1 ? `1px solid ${T.border}` : 'none',
                      background: hoverCard === 'tk-' + i ? 'rgba(255,255,255,0.02)' : 'transparent',
                      transition: 'background 0.12s',
                      borderLeft: `2px solid ${isOverdue ? T.danger : prColor}`,
                    }}
                  >
                    <div style={{ fontSize: 12, fontWeight: 500, color: T.text, marginBottom: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {task.title || '—'}
                    </div>
                    <div style={{ fontSize: 11, color: T.textMuted, marginBottom: 6, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {task.agency_name || 'Unassigned'}
                    </div>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: task.progress_percentage !== undefined ? 6 : 0 }}>
                      <Badge color={prColor}>{task.priority ?? 'N/A'}</Badge>
                      <Badge color={stColor}>{task.status ?? 'N/A'}</Badge>
                      {isOverdue && <Badge color={T.danger}>OVERDUE</Badge>}
                    </div>
                    {task.progress_percentage !== undefined && (
                      <ProgressBar value={task.progress_percentage} />
                    )}
                    {task.due_date && (
                      <div style={{ marginTop: 5, fontFamily: 'Space Mono, monospace', fontSize: 10, color: isOverdue ? T.danger : T.textMuted }}>
                        Due {fmt(task.due_date)}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* Tasks by Agency (from overview) */}
          {!overviewLoading && overview?.tasks_by_agency?.length > 0 && (
            <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden' }}>
              <SectionHeader icon={IcoAgency(13)} label="Tasks by Agency" color={T.textSub} />
              <div style={{ padding: '8px 0' }}>
                {overview.tasks_by_agency.map((item, i) => (
                  <div key={i} style={{ padding: '7px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 12, color: T.textSub, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 160 }}>
                      {item.assigned_to_agency__name || 'Unknown'}
                    </span>
                    <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 11, color: T.accent, flexShrink: 0 }}>
                      {item.count}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>

      </div>
    </div>
  )
}