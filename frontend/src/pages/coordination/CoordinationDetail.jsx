/**
 * CoordinationDetail.jsx — OryxShield
 * =============================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Route: /dashboard/coordination/:id
 * Displays a single CoordinationTeam with 5 tabs:
 *   Overview  — team metadata + memberships (GET /coordination/teams/:id/members/)
 *   Tasks     — tasks assigned to this team (GET /coordination/tasks/?coordination_team=:id)
 *   Meetings  — meetings for this team (GET /coordination/meetings/?coordination_team=:id)
 *   Channels  — communication channels (GET /coordination/channels/?coordination_team=:id)
 *   Products  — information products (GET /coordination/information-products/?coordination_team=:id)
 *
 * Actions available in-page:
 *   Activate / Deactivate team (POST /coordination/teams/:id/activate|deactivate/)
 *   Accept / Start / Complete tasks (via coordinationApi)
 *   Commence / Close meetings (via coordinationApi)
 *
 * API fields from:
 *   CoordinationTeamSerializer, TeamMembershipSerializer, TaskListSerializer,
 *   MeetingListSerializer, CommunicationChannelSerializer, InformationProductListSerializer
 */

import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { coordinationApi, extractError } from '../../services/api'
import Breadcrumb from '../../components/ui/Breadcrumb'

// ─── @keyframes ───────────────────────────────────────────────────────────────
const STYLE_TAG = `
@keyframes copd-shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position:  200% 0; }
}
@keyframes copd-fadeUp {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0);    }
}
`

// ─── Design tokens ────────────────────────────────────────────────────────────
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

// ─── Color maps ───────────────────────────────────────────────────────────────
const PRIORITY_COLOR = {
  LOW: '#10b981', MEDIUM: '#f59e0b', HIGH: '#f97316',
  URGENT: '#f97316', CRITICAL: '#ef4444',
}
const TASK_STATUS_COLOR = {
  PENDING: '#6b7280', ASSIGNED: '#3b82f6', ACCEPTED: '#8b5cf6',
  IN_PROGRESS: '#3b82f6', COMPLETED: '#10b981', CANCELLED: '#6b7280',
}
const MEETING_STATUS_COLOR = {
  SCHEDULED: '#3b82f6', IN_PROGRESS: '#f59e0b',
  COMPLETED: '#10b981', CANCELLED: '#6b7280',
}
const CHANNEL_TYPE_COLOR = {
  EMAIL: '#3b82f6', CHAT: '#10b981', FORUM: '#8b5cf6',
  PHONE: '#f59e0b', RADIO: '#f97316', VIDEO: '#ec4899', PORTAL: '#6b7280',
}
const PRODUCT_TYPE_COLOR = {
  SITREP: '#3b82f6', BRIEFING: '#8b5cf6', ANALYSIS: '#f59e0b',
  MAP: '#10b981', GUIDELINE: '#6b7280', PLAN: '#ec4899',
  DATA: '#f97316', BULLETIN: '#ef4444',
}
const MEMBER_ROLE_COLOR = {
  LEAD: '#ef4444', CO_LEAD: '#f97316', MEMBER: '#3b82f6',
  OBSERVER: '#6b7280', ADVISOR: '#8b5cf6', SUPPORT: '#10b981',
}
const TEAM_TYPE_COLOR = {
  INCIDENT: '#ef4444', TASK_FORCE: '#f97316', WORKING_GROUP: '#3b82f6',
  TECHNICAL: '#8b5cf6', EOC: '#ec4899', LIAISON: '#10b981',
}

// ─── Utility ──────────────────────────────────────────────────────────────────
function fmt(dt) {
  if (!dt) return '—'
  try { return new Date(dt).toLocaleDateString('en-NA', { day: '2-digit', month: 'short', year: 'numeric' }) }
  catch { return '—' }
}
function fmtDt(dt) {
  if (!dt) return '—'
  try { return new Date(dt).toLocaleString('en-NA', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) }
  catch { return '—' }
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
      animation: 'copd-shimmer 1.5s infinite',
      marginBottom: mb,
    }} />
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
const IcoBack = (s = 14) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
    <path d="M19 12H5M12 5l-7 7 7 7" strokeLinecap="round" strokeLinejoin="round"/>
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
const IcoChannel = (s = 14) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)
const IcoDoc = (s = 14) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)
const IcoLink = (s = 14) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)
const IcoDownload = (s = 14) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

const TABS = [
  { id: 'OVERVIEW',  label: 'Overview',  icon: IcoTeam    },
  { id: 'TASKS',     label: 'Tasks',     icon: IcoTask    },
  { id: 'MEETINGS',  label: 'Meetings',  icon: IcoMeeting },
  { id: 'CHANNELS',  label: 'Channels',  icon: IcoChannel },
  { id: 'PRODUCTS',  label: 'Products',  icon: IcoDoc     },
]

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────
export default function CoordinationDetail() {
  const { id } = useParams()
  const navigate = useNavigate()

  // ── State ──────────────────────────────────────────────────────────────────
  const [team, setTeam]           = useState(null)
  const [teamLoad, setTmLoad]     = useState(true)
  const [teamErr, setTmErr]       = useState(null)

  const [members, setMembers]     = useState([])
  const [membersLoad, setMbLoad]  = useState(false)
  const [membersErr, setMbErr]    = useState(null)

  const [tasks, setTasks]         = useState([])
  const [tasksLoad, setTkLoad]    = useState(false)
  const [tasksErr, setTkErr]      = useState(null)

  const [meetings, setMeetings]   = useState([])
  const [meetLoad, setMtLoad]     = useState(false)
  const [meetErr, setMtErr]       = useState(null)

  const [channels, setChannels]   = useState([])
  const [chanLoad, setChLoad]     = useState(false)
  const [chanErr, setChErr]       = useState(null)

  const [products, setProducts]   = useState([])
  const [prodLoad, setPrLoad]     = useState(false)
  const [prodErr, setPrErr]       = useState(null)

  const [activeTab, setActiveTab] = useState('OVERVIEW')
  const [actionMsg, setActionMsg] = useState(null)   // { type: 'success'|'error', text }
  const [actionLoading, setActLd] = useState(null)   // key of loading action

  const [hoverRow, setHoverRow]   = useState(null)
  const [hoverCard, setHoverCard] = useState(null)
  const [hoverBtn, setHoverBtn]   = useState(null)

  // ── Fetchers ───────────────────────────────────────────────────────────────
  const fetchTeam = useCallback(async () => {
    setTmLoad(true); setTmErr(null)
    try {
      const res = await coordinationApi.getTeam(id)
      setTeam(res.data)
    } catch (e) { setTmErr(extractError(e)) }
    finally { setTmLoad(false) }
  }, [id])

  const fetchMembers = useCallback(async () => {
    setMbLoad(true); setMbErr(null)
    try {
      const res = await coordinationApi.teamMembers(id)
      setMembers(res.data?.results ?? res.data ?? [])
    } catch (e) { setMbErr(extractError(e)) }
    finally { setMbLoad(false) }
  }, [id])

  const fetchTasks = useCallback(async () => {
    setTkLoad(true); setTkErr(null)
    try {
      const res = await coordinationApi.listTasks({ coordination_team: id, page_size: 50, ordering: 'due_date' })
      setTasks(res.data?.results ?? res.data ?? [])
    } catch (e) { setTkErr(extractError(e)) }
    finally { setTkLoad(false) }
  }, [id])

  const fetchMeetings = useCallback(async () => {
    setMtLoad(true); setMtErr(null)
    try {
      const res = await coordinationApi.listMeetings({ coordination_team: id, page_size: 50, ordering: 'scheduled_start' })
      setMeetings(res.data?.results ?? res.data ?? [])
    } catch (e) { setMtErr(extractError(e)) }
    finally { setMtLoad(false) }
  }, [id])

  const fetchChannels = useCallback(async () => {
    setChLoad(true); setChErr(null)
    try {
      const res = await coordinationApi.listChannels({ coordination_team: id, page_size: 50 })
      setChannels(res.data?.results ?? res.data ?? [])
    } catch (e) { setChErr(extractError(e)) }
    finally { setChLoad(false) }
  }, [id])

  const fetchProducts = useCallback(async () => {
    setPrLoad(true); setPrErr(null)
    try {
      const res = await coordinationApi.listInfoProducts({ coordination_team: id, page_size: 50, ordering: '-effective_date' })
      setProducts(res.data?.results ?? res.data ?? [])
    } catch (e) { setPrErr(extractError(e)) }
    finally { setPrLoad(false) }
  }, [id])

  // ── Initial loads ──────────────────────────────────────────────────────────
  useEffect(() => { fetchTeam() }, [fetchTeam])
  useEffect(() => { fetchMembers() }, [fetchMembers])

  // Lazy-load tab data on first activation
  useEffect(() => {
    if (activeTab === 'TASKS'    && tasks.length    === 0 && !tasksLoad) fetchTasks()
    if (activeTab === 'MEETINGS' && meetings.length === 0 && !meetLoad)  fetchMeetings()
    if (activeTab === 'CHANNELS' && channels.length === 0 && !chanLoad)  fetchChannels()
    if (activeTab === 'PRODUCTS' && products.length === 0 && !prodLoad)  fetchProducts()
    // eslint-disable-next-line
  }, [activeTab])

  // ── Actions ────────────────────────────────────────────────────────────────
  const showMsg = (type, text) => {
    setActionMsg({ type, text })
    setTimeout(() => setActionMsg(null), 3500)
  }

  async function handleActivate() {
    setActLd('activate')
    try {
      await coordinationApi.activateTeam(id)
      showMsg('success', 'Team activated successfully.')
      fetchTeam()
    } catch (e) { showMsg('error', extractError(e)) }
    finally { setActLd(null) }
  }

  async function handleDeactivate() {
    setActLd('deactivate')
    try {
      await coordinationApi.deactivateTeam(id)
      showMsg('success', 'Team deactivated.')
      fetchTeam()
    } catch (e) { showMsg('error', extractError(e)) }
    finally { setActLd(null) }
  }

  async function handleTaskAction(taskId, action) {
    const key = `task-${taskId}-${action}`
    setActLd(key)
    try {
      if (action === 'accept')   await coordinationApi.acceptTask(taskId)
      if (action === 'start')    await coordinationApi.startTask(taskId)
      if (action === 'complete') await coordinationApi.completeTask(taskId, {})
      if (action === 'cancel')   await coordinationApi.cancelTask(taskId, {})
      showMsg('success', `Task ${action}ed.`)
      fetchTasks()
    } catch (e) { showMsg('error', extractError(e)) }
    finally { setActLd(null) }
  }

  async function handleMeetingAction(meetingId, action) {
    const key = `mtg-${meetingId}-${action}`
    setActLd(key)
    try {
      if (action === 'commence') await coordinationApi.commenceMeeting(meetingId)
      if (action === 'close')    await coordinationApi.closeMeeting(meetingId, {})
      if (action === 'cancel')   await coordinationApi.cancelMeeting(meetingId, {})
      showMsg('success', `Meeting ${action}d.`)
      fetchMeetings()
    } catch (e) { showMsg('error', extractError(e)) }
    finally { setActLd(null) }
  }

  async function handleDownloadProduct(productId) {
    setActLd('dl-' + productId)
    try {
      const res = await coordinationApi.getInfoProduct(productId)
      // The /download/ action increments count and returns file_url
      // We call getInfoProduct then open file_url if present
      if (res.data?.file_url) window.open(res.data.file_url, '_blank')
      else showMsg('error', 'No file attached to this product.')
    } catch (e) { showMsg('error', extractError(e)) }
    finally { setActLd(null) }
  }

  // ── Style helpers ──────────────────────────────────────────────────────────
  const thStyle = {
    padding: '8px 14px',
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
    padding: '10px 14px',
    fontSize: 12,
    color: T.text,
    borderBottom: `1px solid ${T.border}`,
    verticalAlign: 'middle',
  }
  const actionBtn = (id, color = T.accent) => ({
    padding: '3px 9px',
    borderRadius: 3,
    border: `1px solid ${hoverBtn === id ? color + '80' : color + '40'}`,
    background: hoverBtn === id ? color + '20' : color + '0a',
    color,
    fontSize: 10,
    fontFamily: 'Space Mono, monospace',
    cursor: actionLoading === id ? 'not-allowed' : 'pointer',
    letterSpacing: '0.06em',
    transition: 'all 0.15s',
    opacity: actionLoading === id ? 0.5 : 1,
    whiteSpace: 'nowrap',
  })

  // ─────────────────────────────────────────────────────────────────────────
  // Loading / Error state for team header
  if (teamLoad) {
    return (
      <div style={{ minHeight: '100vh', background: T.bg, padding: '32px', fontFamily: 'IBM Plex Sans, sans-serif' }}>
        <style>{STYLE_TAG}</style>
        {[...Array(8)].map((_, i) => <ShimmerBox key={i} h={i === 0 ? 36 : 44} mb={8} />)}
      </div>
    )
  }
  if (teamErr) {
    return (
      <div style={{ minHeight: '100vh', background: T.bg, padding: '32px', fontFamily: 'IBM Plex Sans, sans-serif', color: T.text }}>
        <style>{STYLE_TAG}</style>
        <button onClick={() => navigate(-1)} style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', color: T.textSub, cursor: 'pointer', fontSize: 13, marginBottom: 24 }}>
          <span style={{ color: T.accent }}>{IcoBack(14)}</span> Back
        </button>
        <div style={{ padding: '16px 20px', background: T.danger + '14', border: `1px solid ${T.danger}30`, borderRadius: 4, color: T.danger, fontSize: 13 }}>
          {teamErr}
        </div>
      </div>
    )
  }

  const t = team ?? {}
  const typeColor = TEAM_TYPE_COLOR[t.team_type] ?? T.accent

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div style={{ minHeight: '100vh', background: T.bg, fontFamily: 'IBM Plex Sans, sans-serif', color: T.text }}>
      <style>{STYLE_TAG}</style>

      {/* ── Action Message Toast ── */}
      {actionMsg && (
        <div style={{
          position: 'fixed', top: 20, right: 24, zIndex: 9999,
          padding: '10px 18px', borderRadius: 4,
          background: actionMsg.type === 'success' ? T.success + '20' : T.danger + '20',
          border: `1px solid ${actionMsg.type === 'success' ? T.success + '50' : T.danger + '50'}`,
          color: actionMsg.type === 'success' ? T.success : T.danger,
          fontSize: 13, fontFamily: 'IBM Plex Sans, sans-serif',
          animation: 'copd-fadeUp 0.2s ease both',
          maxWidth: 320,
        }}>
          {actionMsg.text}
        </div>
      )}

      {/* ── Page Header ── */}
      <div style={{ padding: '28px 32px 0', animation: 'copd-fadeUp 0.25s ease both' }}>
        <Breadcrumb items={[
          { label: 'Coordination', to: '/dashboard/coordination' },
          { label: team?.name || `Team #${id}` },
        ]} />

        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap', marginBottom: 20 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 6 }}>
              <h1 style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 30, color: T.text, letterSpacing: '0.06em', margin: 0, lineHeight: 1 }}>
                {t.name || 'TEAM DETAIL'}
              </h1>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 11, color: T.textMuted, letterSpacing: '0.08em' }}>
                [{t.code}]
              </span>
              <Badge color={t.is_active ? T.success : T.textMuted}>
                {t.is_active ? 'ACTIVE' : 'INACTIVE'}
              </Badge>
              {t.team_type && <Badge color={typeColor}>{t.team_type}</Badge>}
            </div>
            {t.mandate && (
              <p style={{ fontSize: 12, color: T.textSub, margin: 0, lineHeight: 1.5, maxWidth: 600 }}>
                {t.mandate}
              </p>
            )}
          </div>

          {/* Activate / Deactivate */}
          <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
            {!t.is_active ? (
              <button
                onClick={handleActivate}
                disabled={actionLoading === 'activate'}
                onMouseEnter={() => setHoverBtn('activate')}
                onMouseLeave={() => setHoverBtn(null)}
                style={{
                  padding: '7px 16px', borderRadius: 4,
                  border: `1px solid ${T.success}50`,
                  background: hoverBtn === 'activate' ? T.success + '20' : T.success + '0e',
                  color: T.success, fontSize: 12, fontFamily: 'Space Mono, monospace',
                  cursor: actionLoading === 'activate' ? 'not-allowed' : 'pointer',
                  opacity: actionLoading === 'activate' ? 0.5 : 1,
                  letterSpacing: '0.06em', transition: 'all 0.15s',
                }}
              >
                {actionLoading === 'activate' ? '…' : 'Activate'}
              </button>
            ) : (
              <button
                onClick={handleDeactivate}
                disabled={actionLoading === 'deactivate'}
                onMouseEnter={() => setHoverBtn('deactivate')}
                onMouseLeave={() => setHoverBtn(null)}
                style={{
                  padding: '7px 16px', borderRadius: 4,
                  border: `1px solid ${T.danger}50`,
                  background: hoverBtn === 'deactivate' ? T.danger + '20' : T.danger + '0e',
                  color: T.danger, fontSize: 12, fontFamily: 'Space Mono, monospace',
                  cursor: actionLoading === 'deactivate' ? 'not-allowed' : 'pointer',
                  opacity: actionLoading === 'deactivate' ? 0.5 : 1,
                  letterSpacing: '0.06em', transition: 'all 0.15s',
                }}
              >
                {actionLoading === 'deactivate' ? '…' : 'Deactivate'}
              </button>
            )}
          </div>
        </div>

        {/* Meta row */}
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginBottom: 0 }}>
          {[
            { label: 'Lead Agency', value: t.lead_agency_name ?? '—' },
            { label: 'Team Leader', value: t.team_leader_name ?? '—' },
            { label: 'Meeting Frequency', value: t.meeting_frequency || '—' },
            { label: 'Activated', value: t.activated_at ? fmt(t.activated_at) : '—' },
            { label: 'Members', value: (t.memberships?.filter(m => m.is_active)?.length ?? members.length) + ' active' },
          ].map(meta => (
            <div key={meta.label} style={{ minWidth: 120 }}>
              <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textMuted, marginBottom: 3 }}>
                {meta.label}
              </div>
              <div style={{ fontSize: 13, color: T.text, fontWeight: 500 }}>
                {meta.value}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Tab bar ── */}
      <div style={{ padding: '20px 32px 0', display: 'flex', gap: 0, borderBottom: `1px solid ${T.border}`, overflowX: 'auto' }}>
        {TABS.map(tab => {
          const active = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              onMouseEnter={() => setHoverBtn('tab-' + tab.id)}
              onMouseLeave={() => setHoverBtn(null)}
              style={{
                display: 'flex', alignItems: 'center', gap: 7,
                padding: '10px 18px',
                background: 'none',
                border: 'none',
                borderBottom: active ? `2px solid ${T.accent}` : '2px solid transparent',
                color: active ? T.accent : hoverBtn === 'tab-' + tab.id ? T.textSub : T.textMuted,
                cursor: 'pointer',
                fontSize: 11,
                fontFamily: 'Space Mono, monospace',
                letterSpacing: '0.06em',
                transition: 'all 0.15s',
                whiteSpace: 'nowrap',
                marginBottom: -1,
              }}
            >
              <span style={{ opacity: active ? 1 : 0.6 }}>{tab.icon(12)}</span>
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* ── Tab Content ── */}
      <div style={{ padding: '20px 32px 40px', animation: 'copd-fadeUp 0.2s ease both' }}>

        {/* ════ OVERVIEW TAB ════════════════════════════════════════════════ */}
        {activeTab === 'OVERVIEW' && (
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start' }}>

            {/* Objectives */}
            {Array.isArray(t.objectives) && t.objectives.length > 0 && (
              <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '16px 20px', minWidth: 260, flex: 1 }}>
                <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textMuted, marginBottom: 12 }}>
                  Objectives
                </div>
                {t.objectives.map((obj, i) => (
                  <div key={i} style={{ display: 'flex', gap: 10, marginBottom: 8 }}>
                    <span style={{ color: typeColor, fontFamily: 'Space Mono, monospace', fontSize: 10, flexShrink: 0, marginTop: 1 }}>{i + 1}.</span>
                    <span style={{ fontSize: 13, color: T.textSub, lineHeight: 1.5 }}>{typeof obj === 'string' ? obj : JSON.stringify(obj)}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Members */}
            <div style={{ flex: 2, minWidth: 300, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden' }}>
              <div style={{ padding: '12px 20px', borderBottom: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: T.accent }}>{IcoTeam(13)}</span>
                <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textSub, fontWeight: 700 }}>
                  Member Agencies
                </span>
                <span style={{ marginLeft: 'auto', fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textMuted }}>
                  {members.length}
                </span>
              </div>

              {membersLoad ? (
                <div style={{ padding: 16 }}>{[...Array(4)].map((_, i) => <ShimmerBox key={i} />)}</div>
              ) : membersErr ? (
                <div style={{ padding: '12px 20px', color: T.danger, fontSize: 13 }}>{membersErr}</div>
              ) : members.length === 0 ? (
                <div style={{ padding: '12px 20px', color: T.textMuted, fontSize: 13 }}>No members found</div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr>
                        {['Agency', 'Acronym', 'Role', 'Representative', 'Joined', 'Status'].map(h => (
                          <th key={h} style={thStyle}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {members.map((m, i) => (
                        <tr
                          key={m.id}
                          onMouseEnter={() => setHoverRow('mb-' + i)}
                          onMouseLeave={() => setHoverRow(null)}
                          style={{ background: hoverRow === 'mb-' + i ? 'rgba(255,255,255,0.02)' : 'transparent' }}
                        >
                          <td style={{ ...tdStyle, fontWeight: 500, maxWidth: 180 }}>
                            <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {m.agency_name || '—'}
                            </span>
                          </td>
                          <td style={{ ...tdStyle, fontFamily: 'Space Mono, monospace', fontSize: 11, color: T.textSub }}>
                            {m.agency_acronym || '—'}
                          </td>
                          <td style={tdStyle}>
                            <Badge color={MEMBER_ROLE_COLOR[m.role] ?? T.textMuted}>{m.role ?? '—'}</Badge>
                          </td>
                          <td style={{ ...tdStyle, color: T.textSub, maxWidth: 160 }}>
                            <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {m.primary_representative_name || '—'}
                            </span>
                          </td>
                          <td style={{ ...tdStyle, fontFamily: 'Space Mono, monospace', fontSize: 11, color: T.textMuted }}>
                            {fmt(m.joined_at)}
                          </td>
                          <td style={tdStyle}>
                            <Badge color={m.is_active ? T.success : T.textMuted}>
                              {m.is_active ? 'ACTIVE' : 'INACTIVE'}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ════ TASKS TAB ═══════════════════════════════════════════════════ */}
        {activeTab === 'TASKS' && (
          <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden' }}>
            <div style={{ padding: '12px 20px', borderBottom: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ color: T.warning }}>{IcoTask(13)}</span>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textSub, fontWeight: 700 }}>Tasks</span>
              <span style={{ marginLeft: 'auto', fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textMuted }}>{tasks.length}</span>
            </div>

            {tasksLoad ? (
              <div style={{ padding: 16 }}>{[...Array(5)].map((_, i) => <ShimmerBox key={i} />)}</div>
            ) : tasksErr ? (
              <div style={{ padding: '12px 20px', color: T.danger, fontSize: 13 }}>{tasksErr}</div>
            ) : tasks.length === 0 ? (
              <div style={{ padding: '12px 20px', color: T.textMuted, fontSize: 13 }}>No tasks for this team</div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      {['Title', 'Agency', 'Priority', 'Status', 'Due Date', 'Progress', 'Actions'].map(h => (
                        <th key={h} style={thStyle}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tasks.map((task, i) => {
                      const isOverdue = task.is_overdue
                      const canAccept   = task.status === 'ASSIGNED'
                      const canStart    = task.status === 'ACCEPTED'
                      const canComplete = ['ASSIGNED','ACCEPTED','IN_PROGRESS'].includes(task.status)
                      const canCancel   = ['ASSIGNED','ACCEPTED','IN_PROGRESS'].includes(task.status)
                      return (
                        <tr
                          key={task.id}
                          onMouseEnter={() => setHoverRow('tk-' + i)}
                          onMouseLeave={() => setHoverRow(null)}
                          style={{ background: hoverRow === 'tk-' + i ? 'rgba(255,255,255,0.02)' : 'transparent' }}
                        >
                          <td style={{ ...tdStyle, maxWidth: 220 }}>
                            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 500 }}>
                              {task.title || '—'}
                            </div>
                            {isOverdue && (
                              <Badge color={T.danger}>OVERDUE</Badge>
                            )}
                          </td>
                          <td style={{ ...tdStyle, color: T.textSub, maxWidth: 140 }}>
                            <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {task.agency_name || '—'}
                            </span>
                          </td>
                          <td style={tdStyle}>
                            <Badge color={PRIORITY_COLOR[task.priority] ?? T.textMuted}>{task.priority ?? 'N/A'}</Badge>
                          </td>
                          <td style={tdStyle}>
                            <Badge color={TASK_STATUS_COLOR[task.status] ?? T.textMuted}>{task.status ?? 'N/A'}</Badge>
                          </td>
                          <td style={{ ...tdStyle, fontFamily: 'Space Mono, monospace', fontSize: 11, color: isOverdue ? T.danger : T.textMuted, whiteSpace: 'nowrap' }}>
                            {fmt(task.due_date)}
                          </td>
                          <td style={{ ...tdStyle, minWidth: 130 }}>
                            <ProgressBar value={task.progress_percentage ?? 0} />
                          </td>
                          <td style={{ ...tdStyle, minWidth: 160 }}>
                            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                              {canAccept && (
                                <button
                                  onMouseEnter={() => setHoverBtn(`ta-accept-${task.id}`)}
                                  onMouseLeave={() => setHoverBtn(null)}
                                  onClick={() => handleTaskAction(task.id, 'accept')}
                                  disabled={!!actionLoading}
                                  style={actionBtn(`ta-accept-${task.id}`, T.accent)}
                                >Accept</button>
                              )}
                              {canStart && (
                                <button
                                  onMouseEnter={() => setHoverBtn(`ta-start-${task.id}`)}
                                  onMouseLeave={() => setHoverBtn(null)}
                                  onClick={() => handleTaskAction(task.id, 'start')}
                                  disabled={!!actionLoading}
                                  style={actionBtn(`ta-start-${task.id}`, T.warning)}
                                >Start</button>
                              )}
                              {canComplete && (
                                <button
                                  onMouseEnter={() => setHoverBtn(`ta-done-${task.id}`)}
                                  onMouseLeave={() => setHoverBtn(null)}
                                  onClick={() => handleTaskAction(task.id, 'complete')}
                                  disabled={!!actionLoading}
                                  style={actionBtn(`ta-done-${task.id}`, T.success)}
                                >Complete</button>
                              )}
                              {canCancel && (
                                <button
                                  onMouseEnter={() => setHoverBtn(`ta-cancel-${task.id}`)}
                                  onMouseLeave={() => setHoverBtn(null)}
                                  onClick={() => handleTaskAction(task.id, 'cancel')}
                                  disabled={!!actionLoading}
                                  style={actionBtn(`ta-cancel-${task.id}`, T.danger)}
                                >Cancel</button>
                              )}
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ════ MEETINGS TAB ════════════════════════════════════════════════ */}
        {activeTab === 'MEETINGS' && (
          <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden' }}>
            <div style={{ padding: '12px 20px', borderBottom: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ color: T.accent }}>{IcoMeeting(13)}</span>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textSub, fontWeight: 700 }}>Meetings</span>
              <span style={{ marginLeft: 'auto', fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textMuted }}>{meetings.length}</span>
            </div>

            {meetLoad ? (
              <div style={{ padding: 16 }}>{[...Array(4)].map((_, i) => <ShimmerBox key={i} />)}</div>
            ) : meetErr ? (
              <div style={{ padding: '12px 20px', color: T.danger, fontSize: 13 }}>{meetErr}</div>
            ) : meetings.length === 0 ? (
              <div style={{ padding: '12px 20px', color: T.textMuted, fontSize: 13 }}>No meetings scheduled</div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      {['Title', 'Type', 'Scheduled Start', 'Scheduled End', 'Mode', 'Status', 'Actions'].map(h => (
                        <th key={h} style={thStyle}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {meetings.map((m, i) => {
                      const canCommence = m.status === 'SCHEDULED'
                      const canClose    = m.status === 'IN_PROGRESS'
                      const canCancel   = ['SCHEDULED','IN_PROGRESS'].includes(m.status)
                      return (
                        <tr
                          key={m.id}
                          onMouseEnter={() => setHoverRow('mt-' + i)}
                          onMouseLeave={() => setHoverRow(null)}
                          style={{ background: hoverRow === 'mt-' + i ? 'rgba(255,255,255,0.02)' : 'transparent' }}
                        >
                          <td style={{ ...tdStyle, fontWeight: 500, maxWidth: 200 }}>
                            <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {m.title || '—'}
                            </span>
                            {m.is_virtual && m.meeting_link && (
                              <a href={m.meeting_link} target="_blank" rel="noopener noreferrer"
                                style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: T.accent, fontSize: 10, textDecoration: 'none', marginTop: 2 }}>
                                {IcoLink(10)} Join Link
                              </a>
                            )}
                          </td>
                          <td style={tdStyle}>
                            <Badge color={T.accent}>{m.meeting_type ?? '—'}</Badge>
                          </td>
                          <td style={{ ...tdStyle, fontFamily: 'Space Mono, monospace', fontSize: 11, color: T.textSub, whiteSpace: 'nowrap' }}>
                            {fmtDt(m.scheduled_start)}
                          </td>
                          <td style={{ ...tdStyle, fontFamily: 'Space Mono, monospace', fontSize: 11, color: T.textSub, whiteSpace: 'nowrap' }}>
                            {fmtDt(m.scheduled_end)}
                          </td>
                          <td style={tdStyle}>
                            <Badge color={m.is_virtual ? '#8b5cf6' : T.textMuted}>
                              {m.is_virtual ? 'VIRTUAL' : 'IN-PERSON'}
                            </Badge>
                          </td>
                          <td style={tdStyle}>
                            <Badge color={MEETING_STATUS_COLOR[m.status] ?? T.textMuted}>{m.status ?? '—'}</Badge>
                          </td>
                          <td style={{ ...tdStyle, minWidth: 160 }}>
                            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                              {canCommence && (
                                <button
                                  onMouseEnter={() => setHoverBtn(`ma-commence-${m.id}`)}
                                  onMouseLeave={() => setHoverBtn(null)}
                                  onClick={() => handleMeetingAction(m.id, 'commence')}
                                  disabled={!!actionLoading}
                                  style={actionBtn(`ma-commence-${m.id}`, T.accent)}
                                >Commence</button>
                              )}
                              {canClose && (
                                <button
                                  onMouseEnter={() => setHoverBtn(`ma-close-${m.id}`)}
                                  onMouseLeave={() => setHoverBtn(null)}
                                  onClick={() => handleMeetingAction(m.id, 'close')}
                                  disabled={!!actionLoading}
                                  style={actionBtn(`ma-close-${m.id}`, T.success)}
                                >Close</button>
                              )}
                              {canCancel && (
                                <button
                                  onMouseEnter={() => setHoverBtn(`ma-cancel-${m.id}`)}
                                  onMouseLeave={() => setHoverBtn(null)}
                                  onClick={() => handleMeetingAction(m.id, 'cancel')}
                                  disabled={!!actionLoading}
                                  style={actionBtn(`ma-cancel-${m.id}`, T.danger)}
                                >Cancel</button>
                              )}
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ════ CHANNELS TAB ════════════════════════════════════════════════ */}
        {activeTab === 'CHANNELS' && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
              <span style={{ color: T.success }}>{IcoChannel(13)}</span>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textSub, fontWeight: 700 }}>
                Communication Channels
              </span>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textMuted }}>{channels.length}</span>
            </div>

            {chanLoad ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 12 }}>
                {[...Array(6)].map((_, i) => <ShimmerBox key={i} h={110} mb={0} />)}
              </div>
            ) : chanErr ? (
              <div style={{ color: T.danger, fontSize: 13 }}>{chanErr}</div>
            ) : channels.length === 0 ? (
              <div style={{ color: T.textMuted, fontSize: 13 }}>No communication channels for this team</div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 12 }}>
                {channels.map((ch, i) => {
                  const typeColor = CHANNEL_TYPE_COLOR[ch.channel_type] ?? T.textMuted
                  return (
                    <div
                      key={ch.id}
                      onMouseEnter={() => setHoverCard('ch-' + i)}
                      onMouseLeave={() => setHoverCard(null)}
                      style={{
                        background: hoverCard === 'ch-' + i ? T.surfaceHi : T.surface,
                        border: `1px solid ${hoverCard === 'ch-' + i ? typeColor + '50' : T.border}`,
                        borderRadius: 5,
                        padding: '14px 16px',
                        transition: 'all 0.15s',
                        borderLeft: `3px solid ${ch.is_active ? typeColor : T.textMuted}`,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                        <span style={{ fontSize: 13, fontWeight: 600, color: T.text, flex: 1, marginRight: 8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {ch.name || '—'}
                        </span>
                        <Badge color={typeColor}>{ch.channel_type ?? 'OTHER'}</Badge>
                      </div>
                      {ch.description && (
                        <p style={{
                          fontSize: 12, color: T.textSub, margin: '0 0 10px', lineHeight: 1.4,
                          overflow: 'hidden', display: '-webkit-box',
                          WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                        }}>
                          {ch.description}
                        </p>
                      )}
                      {ch.contact_address && (
                        <div style={{ fontSize: 11, color: T.accent, marginBottom: 8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {ch.contact_address}
                        </div>
                      )}
                      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span style={{ color: T.textMuted }}>{IcoTeam(11)}</span>
                          <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textMuted }}>
                            {ch.member_count ?? 0} members
                          </span>
                        </div>
                        <Badge color={ch.is_active ? T.success : T.textMuted}>
                          {ch.is_active ? 'ACTIVE' : 'INACTIVE'}
                        </Badge>
                        {ch.is_primary && <Badge color={T.accent}>PRIMARY</Badge>}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* ════ PRODUCTS TAB ════════════════════════════════════════════════ */}
        {activeTab === 'PRODUCTS' && (
          <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden' }}>
            <div style={{ padding: '12px 20px', borderBottom: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ color: '#8b5cf6' }}>{IcoDoc(13)}</span>
              <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textSub, fontWeight: 700 }}>Information Products</span>
              <span style={{ marginLeft: 'auto', fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textMuted }}>{products.length}</span>
            </div>

            {prodLoad ? (
              <div style={{ padding: 16 }}>{[...Array(4)].map((_, i) => <ShimmerBox key={i} />)}</div>
            ) : prodErr ? (
              <div style={{ padding: '12px 20px', color: T.danger, fontSize: 13 }}>{prodErr}</div>
            ) : products.length === 0 ? (
              <div style={{ padding: '12px 20px', color: T.textMuted, fontSize: 13 }}>No information products</div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      {['Title', 'Type', 'Produced By', 'Version', 'Effective', 'Visibility', 'Status', 'Actions'].map(h => (
                        <th key={h} style={thStyle}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {products.map((p, i) => (
                      <tr
                        key={p.id}
                        onMouseEnter={() => setHoverRow('pr-' + i)}
                        onMouseLeave={() => setHoverRow(null)}
                        style={{ background: hoverRow === 'pr-' + i ? 'rgba(255,255,255,0.02)' : 'transparent' }}
                      >
                        <td style={{ ...tdStyle, fontWeight: 500, maxWidth: 200 }}>
                          <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {p.title || '—'}
                          </span>
                        </td>
                        <td style={tdStyle}>
                          <Badge color={PRODUCT_TYPE_COLOR[p.product_type] ?? T.textMuted}>{p.product_type ?? '—'}</Badge>
                        </td>
                        <td style={{ ...tdStyle, color: T.textSub, maxWidth: 160 }}>
                          <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {p.agency_name || '—'}
                          </span>
                        </td>
                        <td style={{ ...tdStyle, fontFamily: 'Space Mono, monospace', fontSize: 11, color: T.textSub }}>
                          v{p.version}
                        </td>
                        <td style={{ ...tdStyle, fontFamily: 'Space Mono, monospace', fontSize: 11, color: T.textMuted, whiteSpace: 'nowrap' }}>
                          {fmt(p.effective_date)}
                        </td>
                        <td style={tdStyle}>
                          <Badge color={p.is_public ? T.success : T.textMuted}>
                            {p.is_public ? 'PUBLIC' : 'RESTRICTED'}
                          </Badge>
                        </td>
                        <td style={tdStyle}>
                          <Badge color={p.is_current ? T.accent : T.textMuted}>
                            {p.is_current ? 'CURRENT' : 'SUPERSEDED'}
                          </Badge>
                        </td>
                        <td style={tdStyle}>
                          {p.file_url ? (
                            <button
                              onMouseEnter={() => setHoverBtn('dl-' + p.id)}
                              onMouseLeave={() => setHoverBtn(null)}
                              onClick={() => handleDownloadProduct(p.id)}
                              disabled={actionLoading === 'dl-' + p.id}
                              style={{
                                display: 'inline-flex', alignItems: 'center', gap: 4,
                                padding: '3px 9px', borderRadius: 3,
                                border: `1px solid ${hoverBtn === 'dl-' + p.id ? '#8b5cf6' + '80' : '#8b5cf6' + '40'}`,
                                background: hoverBtn === 'dl-' + p.id ? '#8b5cf6' + '20' : '#8b5cf6' + '0a',
                                color: '#8b5cf6', fontSize: 10,
                                fontFamily: 'Space Mono, monospace',
                                cursor: actionLoading === 'dl-' + p.id ? 'not-allowed' : 'pointer',
                                opacity: actionLoading === 'dl-' + p.id ? 0.5 : 1,
                                letterSpacing: '0.06em', transition: 'all 0.15s',
                              }}
                            >
                              {IcoDownload(10)} View
                            </button>
                          ) : (
                            <span style={{ color: T.textMuted, fontSize: 11 }}>—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  )
}