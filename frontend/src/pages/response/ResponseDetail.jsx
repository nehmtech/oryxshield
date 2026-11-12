/**
 * ResponseDetail.jsx — OryxShield
 * ==========================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Detail view for a single ResponseActivation.
 * Backend fields used: activation_code, response_level (level/name), protocol,
 *   location, disease_code, disease_name, status, activated_at, completed_at,
 *   expected_completion, incident_commander, activated_by, justification,
 *   objectives, personnel_deployed, resources_allocated, completion_percentage,
 *   escalation_history, metadata, days_active, escalation_probability.
 *
 * Tabs:
 *   Overview | Action Items | Escalation Timeline | Decision Log | Reports | Resources
 *
 * Actions: Escalate, De-escalate, Suspend, Complete, get Effectiveness,
 *   get Escalation Recommendation, get Resource Suggestions
 *
 * Responsiveness:
 *   - Padding: clamp()
 *   - Right sidebar: hidden below 900 px
 *   - All tables: horizontal scroll
 *   - Header meta-row: wraps
 */

import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { responseApi, extractError } from '../../services/api'
import { useResponseStream } from '../../hooks/ws/useResponseStream'
import { useToast } from '../../context/ToastContext'
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
  purple:      '#a78bfa',
  text:        '#f9fafb',
  textSub:     '#9ca3af',
  textMuted:   '#6b7280',
}
const FONTS = {
  head: 'Bebas Neue, sans-serif',
  mono: 'Space Mono, monospace',
  body: 'IBM Plex Sans, sans-serif',
}

const STATUS_COLOR = {
  PENDING:'#6b7280', ACTIVE:T.accent, ESCALATED:T.danger,
  DEESCALATED:T.purple, SUSPENDED:T.warning,
  COMPLETED:T.success, CANCELLED:'#4b5563',
}
const PRIORITY_COLOR = {
  LOW:T.success, MEDIUM:T.warning, HIGH:'#f97316', CRITICAL:T.danger,
}
const ACTION_STATUS_COLOR = {
  PENDING:'#6b7280', IN_PROGRESS:T.accent, COMPLETED:T.success,
  BLOCKED:T.danger, CANCELLED:'#4b5563',
}
const LEVEL_COLORS = {1:'#10b981',2:'#3b82f6',3:'#f59e0b',4:'#f97316',5:'#ef4444'}

const fadeUp = (d = 0) => ({
  initial:{opacity:0,y:14}, animate:{opacity:1,y:0},
  transition:{duration:0.28,ease:'easeOut',delay:d},
})

function fmtDate(v) {
  if (!v) return '—'
  return new Date(v).toLocaleString('en-NA',{dateStyle:'short',timeStyle:'short'})
}
function fmtDateOnly(v) {
  if (!v) return '—'
  return new Date(v).toLocaleDateString('en-NA',{day:'2-digit',month:'short',year:'numeric'})
}

// ─── Micro UI ─────────────────────────────────────────────────────────────────
const Badge = ({label,color}) => (
  <span style={{fontFamily:FONTS.mono,fontSize:9,letterSpacing:'0.12em',
    textTransform:'uppercase',color,background:color+'18',
    border:`1px solid ${color}30`,borderRadius:2,padding:'2px 8px',whiteSpace:'nowrap'}}>{label}</span>
)

const shimmerStyle = {
  background:`linear-gradient(90deg,${T.surface} 25%,${T.surfaceHigh} 50%,${T.surface} 75%)`,
  backgroundSize:'200% 100%', animation:'rds-shimmer 1.5s infinite', borderRadius:4,
}
const Shimmer = ({w='100%',h=14}) => <div style={{width:w,height:h,...shimmerStyle}} />

function LevelBadge({level}) {
  const c = LEVEL_COLORS[level] || T.textMuted
  return <Badge label={`Level ${level}`} color={c} />
}

function InfoRow({label, value, mono, accent}) {
  return (
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',
      padding:'8px 0',borderBottom:`1px solid ${T.border}`,gap:16}}>
      <span style={{fontFamily:FONTS.mono,fontSize:9,color:T.textMuted,letterSpacing:'0.1em',
        textTransform:'uppercase',paddingTop:2,flexShrink:0}}>{label}</span>
      <span style={{fontFamily:mono?FONTS.mono:FONTS.body,fontSize:mono?10:13,
        color:accent||T.text,textAlign:'right',maxWidth:'65%',wordBreak:'break-word'}}>
        {value ?? '—'}
      </span>
    </div>
  )
}

function ActionBtn({onClick,children,icon,variant='ghost',disabled,small}) {
  const S = {
    ghost:  {background:'transparent',border:`1px solid ${T.border}`,color:T.textSub},
    accent: {background:T.accent+'18',border:`1px solid ${T.accent}40`,color:T.accent},
    success:{background:T.success+'18',border:`1px solid ${T.success}40`,color:T.success},
    danger: {background:T.danger+'18',border:`1px solid ${T.danger}40`,color:T.danger},
    warning:{background:T.warning+'18',border:`1px solid ${T.warning}40`,color:T.warning},
    solid:  {background:T.accent,border:`1px solid ${T.accent}`,color:'#fff'},
  }
  return (
    <button onClick={disabled?undefined:onClick} style={{
      display:'inline-flex',alignItems:'center',gap:5,borderRadius:4,
      padding:small?'4px 10px':'7px 14px',fontFamily:FONTS.body,fontSize:small?11:12,
      cursor:disabled?'not-allowed':'pointer',transition:'all 0.14s',
      opacity:disabled?0.45:1,whiteSpace:'nowrap',...S[variant],
    }}>{icon}<span>{children}</span></button>
  )
}

function SectionTitle({children}) {
  return (
    <div style={{fontFamily:FONTS.head,fontSize:15,color:T.text,
      letterSpacing:'0.05em',marginBottom:14}}>{children}</div>
  )
}

const Th = ({children}) => (
  <th style={{padding:'9px 14px',textAlign:'left',fontFamily:FONTS.mono,fontSize:8,
    letterSpacing:'0.12em',textTransform:'uppercase',color:T.textMuted,fontWeight:400,
    borderBottom:`1px solid ${T.border}`,background:T.surfaceHigh,whiteSpace:'nowrap'}}>{children}</th>
)
const Td = ({children,style}) => (
  <td style={{padding:'10px 14px',borderBottom:`1px solid ${T.border}`,...style}}>{children}</td>
)

function ChartTooltip({active,payload,label}) {
  if (!active||!payload?.length) return null
  return (
    <div style={{background:T.surfaceHigh,border:`1px solid ${T.border}`,borderRadius:4,padding:'10px 14px'}}>
      <div style={{fontFamily:FONTS.mono,fontSize:9,color:T.textMuted,marginBottom:6}}>{label}</div>
      {payload.map((p,i)=>(
        <div key={i} style={{fontFamily:FONTS.body,fontSize:12,color:p.color||T.text}}>
          {p.name}: <strong>{p.value}</strong>
        </div>
      ))}
    </div>
  )
}

const RefreshIco = () => (
  <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10"/>
    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
  </svg>
)

// ─── Tab list ─────────────────────────────────────────────────────────────────
const TABS = [
  {key:'overview',  label:'Overview'},
  {key:'actions',   label:'Action Items'},
  {key:'timeline',  label:'Timeline'},
  {key:'decisions', label:'Decision Log'},
  {key:'reports',   label:'Reports'},
  {key:'resources', label:'Resources'},
]

// ═══════════════════════════════════════════════════════════════════════════════
// TAB — OVERVIEW
// ═══════════════════════════════════════════════════════════════════════════════
function OverviewTab({activation}) {
  if (!activation) return null
  const a = activation
  return (
    <div style={{display:'flex',flexDirection:'column',gap:14}}>
      <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,padding:'18px 22px'}}>
        <SectionTitle>ACTIVATION DETAILS</SectionTitle>
        <InfoRow label="Activation Code"   value={a.activation_code} mono />
        <InfoRow label="Response Level"    value={`Level ${a.response_level_number} — ${a.response_level_name}`} />
        <InfoRow label="Protocol"          value={a.protocol_name} />
        <InfoRow label="Location"          value={a.location_name} />
        <InfoRow label="Disease"           value={`${a.disease_name}${a.disease_code?' ('+a.disease_code+')':''}`} />
        <InfoRow label="Status"            value={<Badge label={a.status} color={STATUS_COLOR[a.status]??T.textSub} />} />
        <InfoRow label="Activated At"      value={fmtDate(a.activated_at)} mono />
        <InfoRow label="Expected Completion" value={fmtDate(a.expected_completion)} mono />
        {a.completed_at && <InfoRow label="Completed At" value={fmtDate(a.completed_at)} mono />}
        <InfoRow label="Days Active"       value={a.days_active} mono />
        <InfoRow label="Progress"          value={`${a.completion_percentage ?? 0}%`} mono accent={T.accent} />
      </div>

      <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,padding:'18px 22px'}}>
        <SectionTitle>PERSONNEL</SectionTitle>
        <InfoRow label="Incident Commander" value={a.incident_commander_name} />
        <InfoRow label="Activated By"      value={a.activated_by_name} />
        <InfoRow label="Personnel Deployed" value={a.personnel_deployed} mono />
      </div>

      <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,padding:'18px 22px'}}>
        <SectionTitle>JUSTIFICATION & OBJECTIVES</SectionTitle>
        <div style={{fontFamily:FONTS.body,fontSize:13,color:T.text,lineHeight:1.7,marginBottom:16}}>
          {a.justification || '—'}
        </div>
        {(a.objectives??[]).length > 0 && (
          <>
            <div style={{fontFamily:FONTS.mono,fontSize:9,color:T.textMuted,textTransform:'uppercase',
              letterSpacing:'0.1em',marginBottom:8}}>Objectives</div>
            <ul style={{margin:0,padding:'0 0 0 18px'}}>
              {a.objectives.map((obj,i)=>(
                <li key={i} style={{fontFamily:FONTS.body,fontSize:13,color:T.text,marginBottom:6,lineHeight:1.6}}>{obj}</li>
              ))}
            </ul>
          </>
        )}
      </div>

      {/* Trigger linkage */}
      {(a.triggered_by_alert || a.triggered_by_risk_score) && (
        <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,padding:'18px 22px'}}>
          <SectionTitle>TRIGGER LINKAGE</SectionTitle>
          {a.triggered_by_alert && <InfoRow label="Alert" value={String(a.triggered_by_alert)} mono />}
          {a.triggered_by_risk_score && <InfoRow label="Risk Score" value={String(a.triggered_by_risk_score)} mono />}
        </div>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB — ACTION ITEMS
// ═══════════════════════════════════════════════════════════════════════════════
function ActionItemsTab({activationId}) {
  const {error:toastErr,success:toastOk} = useToast()
  const [items,setItems] = useState([])
  const [loading,setLoading] = useState(true)
  const [acting,setActing] = useState(null)
  const [priorityFilter,setPriority] = useState('ALL')
  const [statusFilter,setStatus] = useState('ALL')
  const [hovered,setHovered] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = {response_activation: activationId, page_size:50}
      if (priorityFilter !== 'ALL') params.priority = priorityFilter
      if (statusFilter !== 'ALL') params.status = statusFilter
      const res = await responseApi.listActionItems(params)
      setItems(res.data.results ?? res.data)
    } catch(e){toastErr(extractError(e))}
    finally{setLoading(false)}
  },[activationId,priorityFilter,statusFilter])

  useEffect(()=>{load()},[load])

  const handleStart = async (id) => {
    setActing(id)
    try{await responseApi.startActionItem(id);toastOk('Started');load()}
    catch(e){toastErr(extractError(e))}finally{setActing(null)}
  }
  const handleComplete = async (id) => {
    const notes = prompt('Completion notes:') ?? ''
    setActing(id)
    try{await responseApi.completeActionItem(id,{completion_notes:notes});toastOk('Completed');load()}
    catch(e){toastErr(extractError(e))}finally{setActing(null)}
  }
  const handleBlock = async (id) => {
    const r = prompt('Blocker description:')
    if (!r?.trim()) return
    setActing(id)
    try{await responseApi.blockActionItem(id,{blocker:r});toastOk('Blocked');load()}
    catch(e){toastErr(extractError(e))}finally{setActing(null)}
  }

  return (
    <div>
      <div style={{display:'flex',gap:6,marginBottom:12,flexWrap:'wrap',alignItems:'center'}}>
        <span style={{fontFamily:FONTS.mono,fontSize:8,color:T.textMuted,textTransform:'uppercase'}}>Priority:</span>
        {['ALL','LOW','MEDIUM','HIGH','CRITICAL'].map(p=>(
          <button key={p} onClick={()=>setPriority(p)} style={{
            fontFamily:FONTS.mono,fontSize:9,letterSpacing:'0.1em',textTransform:'uppercase',
            padding:'3px 10px',borderRadius:20,cursor:'pointer',transition:'all 0.13s',
            border:`1px solid ${priorityFilter===p?(PRIORITY_COLOR[p]||T.accent)+'60':T.border}`,
            background:priorityFilter===p?(PRIORITY_COLOR[p]||T.accent)+'1a':'transparent',
            color:priorityFilter===p?(PRIORITY_COLOR[p]||T.accent):T.textSub,
          }}>{p}</button>
        ))}
        <div style={{width:1,height:14,background:T.border}} />
        <span style={{fontFamily:FONTS.mono,fontSize:8,color:T.textMuted,textTransform:'uppercase'}}>Status:</span>
        {['ALL','PENDING','IN_PROGRESS','COMPLETED','BLOCKED'].map(s=>(
          <button key={s} onClick={()=>setStatus(s)} style={{
            fontFamily:FONTS.mono,fontSize:9,letterSpacing:'0.1em',textTransform:'uppercase',
            padding:'3px 10px',borderRadius:20,cursor:'pointer',transition:'all 0.13s',
            border:`1px solid ${statusFilter===s?(ACTION_STATUS_COLOR[s]||T.accent)+'60':T.border}`,
            background:statusFilter===s?(ACTION_STATUS_COLOR[s]||T.accent)+'1a':'transparent',
            color:statusFilter===s?(ACTION_STATUS_COLOR[s]||T.accent):T.textSub,
          }}>{s.replace('_',' ')}</button>
        ))}
      </div>

      <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,overflow:'hidden'}}>
        <div style={{overflowX:'auto'}}>
          <table style={{width:'100%',borderCollapse:'collapse'}}>
            <thead><tr>
              {['Title','Priority','Status','Assigned','Due','Overdue','Blockers',''].map(h=><Th key={h}>{h}</Th>)}
            </tr></thead>
            <tbody>
              {loading
                ? Array.from({length:5}).map((_,i)=>(
                  <tr key={i}><td colSpan={8} style={{padding:'10px 14px'}}><Shimmer /></td></tr>
                ))
                : items.length===0
                  ? <tr><td colSpan={8} style={{padding:'36px',textAlign:'center',
                    color:T.textSub,fontFamily:FONTS.mono,fontSize:10}}>NO ACTION ITEMS</td></tr>
                  : items.map(item=>{
                    const overdue = item.is_overdue || (item.due_date && new Date(item.due_date)<new Date()
                      && ['PENDING','IN_PROGRESS'].includes(item.status))
                    return (
                      <tr key={item.id}
                        onMouseEnter={()=>setHovered(item.id)}
                        onMouseLeave={()=>setHovered(null)}
                        style={{background:hovered===item.id?'rgba(255,255,255,0.02)':'transparent',transition:'background 0.1s'}}>
                        <Td>
                          <div style={{fontFamily:FONTS.body,fontSize:12,color:T.text,fontWeight:500,maxWidth:200,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{item.title}</div>
                          {item.description && <div style={{fontFamily:FONTS.body,fontSize:11,color:T.textMuted,marginTop:2}}>{item.description.slice(0,60)}</div>}
                        </Td>
                        <Td><Badge label={item.priority} color={PRIORITY_COLOR[item.priority]??T.textSub} /></Td>
                        <Td><Badge label={item.status} color={ACTION_STATUS_COLOR[item.status]??T.textSub} /></Td>
                        <Td style={{fontSize:12,color:T.textSub}}>{item.assigned_to_name??'—'}</Td>
                        <Td style={{fontFamily:FONTS.mono,fontSize:9,color:overdue?T.danger:T.textMuted,whiteSpace:'nowrap'}}>{fmtDateOnly(item.due_date)}</Td>
                        <Td>{overdue&&<Badge label="Overdue" color={T.danger}/>}</Td>
                        <Td style={{fontSize:11,color:T.danger,maxWidth:140,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{item.blockers||'—'}</Td>
                        <Td>
                          <div style={{display:'flex',gap:4}}>
                            {item.status==='PENDING'&&<ActionBtn small variant="accent" onClick={()=>handleStart(item.id)} disabled={acting===item.id}>Start</ActionBtn>}
                            {['PENDING','IN_PROGRESS'].includes(item.status)&&<ActionBtn small variant="success" onClick={()=>handleComplete(item.id)} disabled={acting===item.id}>Done</ActionBtn>}
                            {item.status==='IN_PROGRESS'&&<ActionBtn small variant="danger" onClick={()=>handleBlock(item.id)} disabled={acting===item.id}>Block</ActionBtn>}
                          </div>
                        </Td>
                      </tr>
                    )
                  })
              }
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB — ESCALATION TIMELINE (from activationTimeline endpoint)
// ═══════════════════════════════════════════════════════════════════════════════
function TimelineTab({activationId,activation}) {
  const {error:toastErr} = useToast()
  const [events,setEvents] = useState([])
  const [loading,setLoading] = useState(true)

  useEffect(()=>{
    ;(async()=>{
      setLoading(true)
      try{
        const res = await responseApi.activationTimeline(activationId)
        setEvents(res.data ?? [])
      } catch {
        // Fallback to embedded escalation_history
        setEvents(activation?.escalation_history ?? [])
      }
      finally{setLoading(false)}
    })()
  },[activationId])

  const EVENT_COLORS = {
    'Response Activated':T.success,
    'Response Escalated':T.danger,
    'Response De-escalated':T.purple,
    'Action Completed':T.accent,
    'Decision Logged':T.warning,
    'Response Completed':T.success,
  }

  return (
    <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,padding:'20px 22px'}}>
      <SectionTitle>RESPONSE TIMELINE</SectionTitle>
      {loading
        ? Array.from({length:5}).map((_,i)=>(
          <div key={i} style={{display:'flex',gap:14,marginBottom:20}}>
            <div style={{width:3,background:T.border,borderRadius:2,alignSelf:'stretch',minHeight:50}} />
            <div style={{flex:1}}><Shimmer h={12} w="40%" /><div style={{height:6}}/><Shimmer h={10} w="60%" /></div>
          </div>
        ))
        : events.length===0
          ? <div style={{fontFamily:FONTS.mono,fontSize:10,color:T.textMuted}}>No timeline events found.</div>
          : events.map((ev,idx)=>{
            const color = EVENT_COLORS[ev.event] || T.accent
            const isEsc = ev.event?.includes('Escalat')
            return (
              <motion.div key={idx} {...fadeUp(idx*0.04)}
                style={{display:'flex',gap:0,marginBottom:0,position:'relative'}}>
                {idx < events.length-1 && (
                  <div style={{position:'absolute',left:11,top:24,bottom:-20,width:1,background:T.border}} />
                )}
                <div style={{width:24,height:24,borderRadius:'50%',border:`2px solid ${color}`,
                  background:color+'20',flexShrink:0,marginTop:2,zIndex:1}} />
                <div style={{marginLeft:14,marginBottom:24,borderLeft:`3px solid ${color}`,
                  paddingLeft:14,flex:1}}>
                  <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:5,flexWrap:'wrap'}}>
                    <span style={{fontFamily:FONTS.head,fontSize:15,color,letterSpacing:'0.04em'}}>
                      {ev.event}
                    </span>
                    <span style={{fontFamily:FONTS.mono,fontSize:9,color:T.textMuted}}>
                      {fmtDate(ev.timestamp)}
                    </span>
                    {ev.actor && (
                      <span style={{fontFamily:FONTS.mono,fontSize:8,color:T.textMuted}}>by {ev.actor}</span>
                    )}
                  </div>
                  {ev.details && (
                    <div style={{fontFamily:FONTS.body,fontSize:12,color:T.text,lineHeight:1.6}}>{ev.details}</div>
                  )}
                </div>
              </motion.div>
            )
          })
      }
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB — DECISION LOG
// ═══════════════════════════════════════════════════════════════════════════════
function DecisionLogTab({activationId}) {
  const {error:toastErr,success:toastOk} = useToast()
  const [logs,setLogs] = useState([])
  const [loading,setLoading] = useState(true)
  const [expanded,setExpanded] = useState(new Set())
  const [acting,setActing] = useState(null)
  const [hovered,setHovered] = useState(null)

  useEffect(()=>{
    ;(async()=>{
      setLoading(true)
      try{
        const res = await responseApi.listDecisionLogs({response_activation:activationId,page_size:50})
        setLogs(res.data.results??res.data)
      } catch(e){toastErr(extractError(e))}
      finally{setLoading(false)}
    })()
  },[activationId])

  const toggle = (id) => setExpanded(p=>{const n=new Set(p);n.has(id)?n.delete(id):n.add(id);return n})

  const handleReview = async (id) => {
    const notes = prompt('Review notes (optional):') ?? ''
    setActing(id)
    try{
      await responseApi.markDecisionReviewed(id,{review_notes:notes})
      toastOk('Decision marked reviewed')
      const res = await responseApi.listDecisionLogs({response_activation:activationId,page_size:50})
      setLogs(res.data.results??res.data)
    } catch(e){toastErr(extractError(e))}
    finally{setActing(null)}
  }

  return (
    <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,overflow:'hidden'}}>
      <div style={{overflowX:'auto'}}>
        <table style={{width:'100%',borderCollapse:'collapse'}}>
          <thead><tr>
            {['Decision','Description','Made By','Options Considered','Decision Made','Date','Reviewed',''].map(h=><Th key={h}>{h}</Th>)}
          </tr></thead>
          <tbody>
            {loading
              ? Array.from({length:4}).map((_,i)=>(
                <tr key={i}><td colSpan={8} style={{padding:'10px 14px'}}><Shimmer /></td></tr>
              ))
              : logs.length===0
                ? <tr><td colSpan={8} style={{padding:'36px',textAlign:'center',color:T.textSub,fontFamily:FONTS.mono,fontSize:10}}>NO DECISION LOG ENTRIES</td></tr>
                : logs.map(log=>{
                  const isExp = expanded.has(log.id)
                  const dm = log.decision_made || ''
                  const truncDm = dm.length > 80
                  return (
                    <tr key={log.id}
                      onMouseEnter={()=>setHovered(log.id)}
                      onMouseLeave={()=>setHovered(null)}
                      style={{background:hovered===log.id?'rgba(255,255,255,0.02)':'transparent',transition:'background 0.1s'}}>
                      <Td>
                        <div style={{fontFamily:FONTS.body,fontSize:12,color:T.text,fontWeight:500,maxWidth:180,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{log.decision_title}</div>
                      </Td>
                      <Td style={{maxWidth:220,fontSize:12,color:T.text}}>
                        <div style={{overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{log.decision_description?.slice(0,80) || '—'}</div>
                      </Td>
                      <Td style={{fontSize:12,color:T.textSub,whiteSpace:'nowrap'}}>{log.decided_by_name??'—'}</Td>
                      <Td style={{fontFamily:FONTS.mono,fontSize:9,color:T.textMuted}}>
                        {(log.options_considered??[]).length} options
                      </Td>
                      <Td style={{maxWidth:200,fontSize:12,color:T.text}}>
                        {truncDm&&!isExp
                          ? <>{dm.slice(0,80)}…{' '}
                            <button onClick={()=>toggle(log.id)} style={{background:'none',border:'none',color:T.accent,fontSize:11,cursor:'pointer',padding:0}}>more</button></>
                          : <>{dm||'—'}{truncDm&&<>{' '}<button onClick={()=>toggle(log.id)} style={{background:'none',border:'none',color:T.accent,fontSize:11,cursor:'pointer',padding:0}}>less</button></>}</>
                        }
                      </Td>
                      <Td style={{fontFamily:FONTS.mono,fontSize:9,color:T.textMuted,whiteSpace:'nowrap'}}>
                        {fmtDate(log.decision_date)}
                      </Td>
                      <Td>
                        {log.reviewed
                          ? <Badge label="Reviewed" color={T.success} />
                          : <Badge label="Pending" color={T.textMuted} />
                        }
                      </Td>
                      <Td>
                        {!log.reviewed && (
                          <ActionBtn small variant="accent" onClick={()=>handleReview(log.id)} disabled={acting===log.id}>Review</ActionBtn>
                        )}
                      </Td>
                    </tr>
                  )
                })
            }
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB — REPORTS
// ═══════════════════════════════════════════════════════════════════════════════
function ReportsTab({activationId}) {
  const {error:toastErr,success:toastOk} = useToast()
  const [rows,setRows] = useState([])
  const [loading,setLoading] = useState(true)
  const [acting,setActing] = useState(null)
  const [hovered,setHovered] = useState(null)

  const REPORT_TYPE_COLOR = {SITUATION:T.accent,PROGRESS:T.success,AFTER_ACTION:T.purple,DAILY:T.warning}

  useEffect(()=>{
    ;(async()=>{
      setLoading(true)
      try{
        const res = await responseApi.listResponseReports({response_activation:activationId,page_size:50})
        setRows(res.data.results??res.data)
      } catch(e){toastErr(extractError(e))}
      finally{setLoading(false)}
    })()
  },[activationId])

  const [pendingPublish, setPendingPublish] = useState(null)

  const handlePublish = async (id) => {
    if (pendingPublish !== id) { setPendingPublish(id); return }
    setPendingPublish(null)
    setActing(id)
    try{await responseApi.publishReport(id);toastOk('Published');
      const res=await responseApi.listResponseReports({response_activation:activationId,page_size:50})
      setRows(res.data.results??res.data)
    } catch(e){toastErr(extractError(e))}
    finally{setActing(null)}
  }

  return (
    <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,overflow:'hidden'}}>
      <div style={{overflowX:'auto'}}>
        <table style={{width:'100%',borderCollapse:'collapse'}}>
          <thead><tr>
            {['Title','Type','Date','Period','Cases','Personnel','Status',''].map(h=><Th key={h}>{h}</Th>)}
          </tr></thead>
          <tbody>
            {loading
              ? Array.from({length:4}).map((_,i)=>(
                <tr key={i}><td colSpan={8} style={{padding:'10px 14px'}}><Shimmer /></td></tr>
              ))
              : rows.length===0
                ? <tr><td colSpan={8} style={{padding:'36px',textAlign:'center',color:T.textSub,fontFamily:FONTS.mono,fontSize:10}}>NO REPORTS</td></tr>
                : rows.map(r=>(
                  <tr key={r.id}
                    onMouseEnter={()=>setHovered(r.id)}
                    onMouseLeave={()=>setHovered(null)}
                    style={{background:hovered===r.id?'rgba(255,255,255,0.02)':'transparent',transition:'background 0.1s'}}>
                    <Td>
                      <div style={{fontFamily:FONTS.body,fontSize:12,color:T.text,fontWeight:500,maxWidth:220,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{r.title}</div>
                    </Td>
                    <Td><Badge label={r.report_type?.replace('_',' ')} color={REPORT_TYPE_COLOR[r.report_type]??T.accent} /></Td>
                    <Td style={{fontFamily:FONTS.mono,fontSize:9,color:T.textMuted,whiteSpace:'nowrap'}}>{fmtDateOnly(r.report_date)}</Td>
                    <Td style={{fontFamily:FONTS.mono,fontSize:9,color:T.textMuted,whiteSpace:'nowrap'}}>
                      {r.period_start?`${fmtDateOnly(r.period_start)} → ${fmtDateOnly(r.period_end)}`:'—'}
                    </Td>
                    <Td style={{fontFamily:FONTS.mono,fontSize:11,color:T.text}}>{r.cases_managed??'—'}</Td>
                    <Td style={{fontFamily:FONTS.mono,fontSize:11,color:T.text}}>{r.personnel_deployed??'—'}</Td>
                    <Td><Badge label={r.is_published?'Published':'Draft'} color={r.is_published?T.success:T.textMuted} /></Td>
                    <Td>
                      {!r.is_published && (
                        pendingPublish === r.id ? (
                          <>
                            <ActionBtn small variant="success" onClick={()=>handlePublish(r.id)} disabled={acting===r.id}>Confirm</ActionBtn>
                            <ActionBtn small variant="ghost" onClick={()=>setPendingPublish(null)}>Cancel</ActionBtn>
                          </>
                        ) : (
                          <ActionBtn small variant="success" onClick={()=>handlePublish(r.id)} disabled={acting===r.id}>Publish</ActionBtn>
                        )
                      )}
                    </Td>
                  </tr>
                ))
            }
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAB — RESOURCES (suggestions + allocated)
// ═══════════════════════════════════════════════════════════════════════════════
function ResourcesTab({activationId,activation}) {
  const {error:toastErr} = useToast()
  const [suggestions,setSuggestions] = useState(null)
  const [effectiveness,setEffectiveness] = useState(null)
  const [loading,setLoading] = useState(true)

  useEffect(()=>{
    ;(async()=>{
      setLoading(true)
      try{
        const [sugRes,effRes] = await Promise.allSettled([
          responseApi.resourceSuggestions(activationId),
          responseApi.activationEffectiveness(activationId),
        ])
        if(sugRes.status==='fulfilled') setSuggestions(sugRes.value.data)
        if(effRes.status==='fulfilled') setEffectiveness(effRes.value.data)
      } catch(e){toastErr(extractError(e))}
      finally{setLoading(false)}
    })()
  },[activationId])

  if (loading) return <div style={{display:'flex',flexDirection:'column',gap:8}}>
    {Array.from({length:4}).map((_,i)=><Shimmer key={i} h={80} />)}
  </div>

  const allocated = activation?.resources_allocated ?? {}
  const effScore = effectiveness?.effectiveness_score

  const effColor = effScore >= 75 ? T.success : effScore >= 50 ? T.warning : T.danger

  return (
    <div style={{display:'flex',flexDirection:'column',gap:14}}>
      {/* Effectiveness */}
      {effectiveness && (
        <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,padding:'18px 22px'}}>
          <SectionTitle>RESPONSE EFFECTIVENESS</SectionTitle>
          <div style={{display:'flex',alignItems:'center',gap:24,flexWrap:'wrap'}}>
            <div style={{textAlign:'center'}}>
              <div style={{fontFamily:FONTS.head,fontSize:56,color:effColor,lineHeight:1}}>{effScore?.toFixed(1) ?? '—'}</div>
              <div style={{fontFamily:FONTS.mono,fontSize:9,color:T.textMuted,textTransform:'uppercase',letterSpacing:'0.1em'}}>/ 100</div>
            </div>
            <div style={{flex:1,minWidth:200}}>
              <div style={{height:8,background:T.border,borderRadius:4,overflow:'hidden',marginBottom:8}}>
                <div style={{width:`${effScore??0}%`,height:'100%',background:effColor,borderRadius:4}} />
              </div>
              <InfoRow label="Completion" value={`${activation?.completion_percentage??0}%`} mono />
            </div>
          </div>
        </div>
      )}

      {/* Suggested resources */}
      {suggestions && (
        <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,padding:'18px 22px'}}>
          <SectionTitle>SUGGESTED RESOURCE ALLOCATION</SectionTitle>
          <div style={{fontFamily:FONTS.mono,fontSize:9,color:T.textMuted,marginBottom:12}}>
            Based on: Level {suggestions.basis?.response_level} · Population {suggestions.basis?.population?.toLocaleString()} · {suggestions.basis?.location}
          </div>
          <div style={{display:'flex',gap:14,flexWrap:'wrap'}}>
            {/* Personnel */}
            <div style={{flex:1,minWidth:160,background:T.surfaceHigh,border:`1px solid ${T.border}`,borderRadius:4,padding:'14px 16px'}}>
              <div style={{fontFamily:FONTS.mono,fontSize:9,color:T.textMuted,textTransform:'uppercase',letterSpacing:'0.1em',marginBottom:10}}>Personnel</div>
              {Object.entries(suggestions.personnel??{}).map(([k,v])=>(
                <div key={k} style={{display:'flex',justifyContent:'space-between',marginBottom:6}}>
                  <span style={{fontFamily:FONTS.body,fontSize:12,color:T.textSub,textTransform:'capitalize'}}>{k.replace('_',' ')}</span>
                  <span style={{fontFamily:FONTS.head,fontSize:18,color:T.accent}}>{v}</span>
                </div>
              ))}
            </div>
            {/* Equipment */}
            <div style={{flex:1,minWidth:160,background:T.surfaceHigh,border:`1px solid ${T.border}`,borderRadius:4,padding:'14px 16px'}}>
              <div style={{fontFamily:FONTS.mono,fontSize:9,color:T.textMuted,textTransform:'uppercase',letterSpacing:'0.1em',marginBottom:10}}>Equipment</div>
              {Object.entries(suggestions.equipment??{}).map(([k,v])=>(
                <div key={k} style={{display:'flex',justifyContent:'space-between',marginBottom:6}}>
                  <span style={{fontFamily:FONTS.body,fontSize:12,color:T.textSub,textTransform:'capitalize'}}>{k.replace(/_/g,' ')}</span>
                  <span style={{fontFamily:FONTS.head,fontSize:18,color:T.warning}}>{v?.toLocaleString()}</span>
                </div>
              ))}
            </div>
            {/* Supplies */}
            <div style={{flex:1,minWidth:160,background:T.surfaceHigh,border:`1px solid ${T.border}`,borderRadius:4,padding:'14px 16px'}}>
              <div style={{fontFamily:FONTS.mono,fontSize:9,color:T.textMuted,textTransform:'uppercase',letterSpacing:'0.1em',marginBottom:10}}>Supplies</div>
              {Object.entries(suggestions.supplies??{}).map(([k,v])=>(
                <div key={k} style={{display:'flex',justifyContent:'space-between',marginBottom:6}}>
                  <span style={{fontFamily:FONTS.body,fontSize:12,color:T.textSub,textTransform:'capitalize'}}>{k.replace(/_/g,' ')}</span>
                  <span style={{fontFamily:FONTS.head,fontSize:18,color:T.success}}>{v?.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Allocated resources */}
      {Object.keys(allocated).length > 0 && (
        <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,padding:'18px 22px'}}>
          <SectionTitle>ALLOCATED RESOURCES</SectionTitle>
          {Object.entries(allocated).map(([k,v])=>(
            <InfoRow key={k} label={k.replace(/_/g,' ')} value={typeof v === 'object' ? JSON.stringify(v) : String(v)} />
          ))}
        </div>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// RIGHT SIDEBAR
// ═══════════════════════════════════════════════════════════════════════════════
function DetailSidebar({activation,setTab,activeTab,onReload}) {
  const {error:toastErr,success:toastOk} = useToast()
  const [rec,setRec] = useState(null)
  const [recLoading,setRecLoading] = useState(false)
  const [levels,setLevels] = useState([])
  const [acting,setActing] = useState(false)

  useEffect(()=>{
    if (!activation) return
    ;(async()=>{
      setRecLoading(true)
      try{
        const [recRes,lvlRes] = await Promise.allSettled([
          responseApi.escalationRecommendation(activation.id),
          responseApi.activeLevels(),
        ])
        if(recRes.status==='fulfilled') setRec(recRes.value.data)
        if(lvlRes.status==='fulfilled') setLevels(lvlRes.value.data.results??lvlRes.value.data)
      } catch{} finally{setRecLoading(false)}
    })()
  },[activation?.id])

  const handleEscalate = async () => {
    if (!rec?.recommended_level) return
    const lvl = levels.find(l=>l.level===rec.recommended_level)
    if (!lvl) { toastErr('Level not found'); return }
    const reason = prompt(`Escalate to Level ${lvl.level} — ${lvl.name}?\nReason:`)
    if (!reason?.trim()) return
    setActing(true)
    try{await responseApi.escalate(activation.id,{new_level_id:lvl.id,reason});toastOk('Escalated');onReload()}
    catch(e){toastErr(extractError(e))}finally{setActing(false)}
  }

  const handleSuspend = async () => {
    const reason = prompt('Reason for suspending:')
    if (!reason?.trim()) return
    setActing(true)
    try{await responseApi.suspend(activation.id,{reason});toastOk('Suspended');onReload()}
    catch(e){toastErr(extractError(e))}finally{setActing(false)}
  }

  const [pendingComplete, setPendingComplete] = useState(false)

  const handleComplete = async () => {
    if (!pendingComplete) { setPendingComplete(true); return }
    setPendingComplete(false)
    setActing(true)
    try{await responseApi.complete(activation.id,{});toastOk('Completed');onReload()}
    catch(e){toastErr(extractError(e))}finally{setActing(false)}
  }

  if (!activation) return null
  const a = activation
  const canAct = ['ACTIVE','ESCALATED'].includes(a.status)
  const probPct = Math.round((a.escalation_probability??0)*100)
  const probColor = probPct>=80?T.danger:probPct>=50?T.warning:T.success

  return (
    <div style={{display:'flex',flexDirection:'column',gap:14}}>
      {/* Progress */}
      <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,padding:'16px 18px'}}>
        <div style={{fontFamily:FONTS.head,fontSize:13,color:T.text,letterSpacing:'0.05em',marginBottom:12}}>PROGRESS</div>
        <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:10}}>
          <svg width={52} height={52} style={{transform:'rotate(-90deg)',flexShrink:0}}>
            {(()=>{const r=23,circ=2*Math.PI*r,d=(a.completion_percentage??0)/100*circ;
              const c=a.completion_percentage>=75?T.success:a.completion_percentage>=40?T.warning:T.accent;
              return(<><circle cx={26}cy={26}r={r}stroke={T.border}strokeWidth={3}fill="none"/>
              <circle cx={26}cy={26}r={r}stroke={c}strokeWidth={3}fill="none"
                strokeDasharray={`${d} ${circ}`}strokeLinecap="round"/></>)
            })()}
          </svg>
          <div>
            <div style={{fontFamily:FONTS.head,fontSize:36,color:T.accent,lineHeight:1}}>
              {a.completion_percentage??0}%
            </div>
            <div style={{fontFamily:FONTS.mono,fontSize:8,color:T.textMuted}}>COMPLETE</div>
          </div>
        </div>
        <InfoRow label="Days Active" value={a.days_active} mono />
        <InfoRow label="Personnel" value={a.personnel_deployed} mono />
      </div>

      {/* Escalation probability */}
      <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,padding:'16px 18px'}}>
        <div style={{fontFamily:FONTS.head,fontSize:13,color:probColor,letterSpacing:'0.05em',marginBottom:10}}>ESCALATION RISK</div>
        <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:12}}>
          <div style={{flex:1,height:6,background:T.border,borderRadius:3,overflow:'hidden'}}>
            <div style={{width:`${probPct}%`,height:'100%',background:probColor,borderRadius:3,transition:'width 0.4s'}} />
          </div>
          <span style={{fontFamily:FONTS.head,fontSize:24,color:probColor}}>{probPct}%</span>
        </div>
        {recLoading
          ? <Shimmer h={40} />
          : rec?.should_escalate && (
            <div style={{background:T.danger+'10',border:`1px solid ${T.danger}30`,borderRadius:4,padding:'10px 12px'}}>
              <div style={{fontFamily:FONTS.mono,fontSize:8,color:T.danger,textTransform:'uppercase',letterSpacing:'0.1em',marginBottom:6}}>
                {rec.urgency} — Escalate to Level {rec.recommended_level}
              </div>
              {rec.triggered_conditions?.map((tc,i)=>(
                <div key={i} style={{fontFamily:FONTS.body,fontSize:11,color:T.text,marginBottom:3}}>
                  ▸ {tc.trigger_name} ({tc.trigger_type?.replace('_',' ')})
                </div>
              ))}
            </div>
          )
        }
      </div>

      {/* Actions */}
      {canAct && (
        <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,padding:'16px 18px'}}>
          <div style={{fontFamily:FONTS.head,fontSize:13,color:T.text,letterSpacing:'0.05em',marginBottom:12}}>ACTIONS</div>
          <div style={{display:'flex',flexDirection:'column',gap:8}}>
            {rec?.should_escalate && (
              <ActionBtn variant="danger" onClick={handleEscalate} disabled={acting}>
                ↑ Escalate to L{rec.recommended_level}
              </ActionBtn>
            )}
            <ActionBtn variant="warning" onClick={handleSuspend} disabled={acting}>Suspend</ActionBtn>
            {a.status === 'ACTIVE' && (
              pendingComplete ? (
                <>
                  <ActionBtn variant="success" onClick={handleComplete} disabled={acting}>Confirm Complete</ActionBtn>
                  <ActionBtn variant="ghost" onClick={() => setPendingComplete(false)}>Cancel</ActionBtn>
                </>
              ) : (
                <ActionBtn variant="success" onClick={handleComplete} disabled={acting}>Complete</ActionBtn>
              )
            )}
          </div>
        </div>
      )}

      {/* Quick nav */}
      <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,padding:'16px 18px'}}>
        <div style={{fontFamily:FONTS.head,fontSize:13,color:T.text,letterSpacing:'0.05em',marginBottom:10}}>EXPLORE</div>
        {TABS.map(t=>(
          <button key={t.key} onClick={()=>setTab(t.key)} style={{
            display:'block',width:'100%',background:activeTab===t.key?T.accent+'18':'transparent',
            border:`1px solid ${activeTab===t.key?T.accent+'40':T.border}`,
            borderRadius:4,padding:'7px 12px',fontFamily:FONTS.body,fontSize:12,
            color:activeTab===t.key?T.accent:T.textSub,cursor:'pointer',textAlign:'left',marginBottom:5,
          }}>{t.label}</button>
        ))}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN EXPORT
// ═══════════════════════════════════════════════════════════════════════════════
export default function ResponseDetail() {
  const {id} = useParams()
  const navigate = useNavigate()
  const {error:toastErr} = useToast()
  const {data:wsActivations} = useResponseStream()

  const [activation,setActivation] = useState(null)
  const [loading,setLoading] = useState(true)
  const [activeTab,setActiveTab] = useState('overview')

  const load = useCallback(async()=>{
    setLoading(true)
    try{const res=await responseApi.getActivation(id);setActivation(res.data)}
    catch(e){toastErr(extractError(e))}finally{setLoading(false)}
  },[id])

  useEffect(()=>{load()},[load])

  // WS refresh on matching update
  useEffect(()=>{
    const ev = wsActivations?.[wsActivations.length-1]
    if (ev?.activation_code === activation?.activation_code) load()
  },[wsActivations])

  const sev = activation ? STATUS_COLOR[activation.status] ?? T.textSub : T.textSub

  return (
    <div style={{minHeight:'100vh',background:T.bg}}>
      <style>{`
        @keyframes rds-shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
        *{box-sizing:border-box}
        ::-webkit-scrollbar{width:5px;height:5px}
        ::-webkit-scrollbar-track{background:#111827}
        ::-webkit-scrollbar-thumb{background:#1f2937;border-radius:3px}
        @media(max-width:899px){.rdd-sidebar{display:none!important}}
      `}</style>

      <div style={{padding:'clamp(16px,2.5vw,28px)'}}>

        {/* Breadcrumb */}
        <Breadcrumb items={[
          { label: 'Response', to: '/dashboard/response' },
          { label: activation?.activation_code || `Activation #${id}` },
        ]} />

        {/* Header */}
        <motion.div {...fadeUp(0.05)} style={{marginBottom:24}}>
          {loading
            ? <><Shimmer h={18} w={180}/><div style={{height:8}}/><Shimmer h={40} w={300}/><div style={{height:8}}/><Shimmer h={14} w={240}/></>
            : activation && (
              <>
                <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:10,flexWrap:'wrap'}}>
                  <Badge label={activation.status} color={sev} />
                  <LevelBadge level={activation.response_level_number} />
                  {activation.escalation_probability >= 0.7 && (
                    <Badge label="High Escalation Risk" color={T.danger} />
                  )}
                </div>
                <h1 style={{fontFamily:FONTS.head,fontSize:'clamp(24px,4vw,38px)',color:T.text,
                  letterSpacing:'0.04em',margin:0,lineHeight:1}}>
                  {activation.activation_code}
                </h1>
                <div style={{fontFamily:FONTS.body,fontSize:13,color:T.textSub,marginTop:6}}>
                  <span style={{fontFamily:FONTS.mono,fontSize:9,color:sev}}>{activation.response_level_name}</span>
                  {' · '}{activation.disease_name}{activation.disease_code?` (${activation.disease_code})`:''}
                  {' · '}{activation.location_name}
                </div>

                {/* Meta row */}
                <div style={{display:'flex',gap:20,flexWrap:'wrap',marginTop:16}}>
                  {[
                    {label:'Activated', value:fmtDate(activation.activated_at)},
                    {label:'Expected Completion', value:fmtDate(activation.expected_completion)},
                    {label:'Days Active', value:activation.days_active??'—'},
                    {label:'Commander', value:activation.incident_commander_name},
                  ].map(({label,value})=>(
                    <div key={label}>
                      <div style={{fontFamily:FONTS.mono,fontSize:8,color:T.textMuted,
                        textTransform:'uppercase',letterSpacing:'0.1em',marginBottom:2}}>{label}</div>
                      <div style={{fontFamily:FONTS.body,fontSize:12,color:T.text}}>{value??'—'}</div>
                    </div>
                  ))}
                </div>
              </>
            )
          }
        </motion.div>

        {/* Tabs */}
        <motion.div {...fadeUp(0.08)} style={{marginBottom:18}}>
          <div style={{display:'flex',gap:0,borderBottom:`1px solid ${T.border}`,
            overflowX:'auto',msOverflowStyle:'none',scrollbarWidth:'none'}}>
            {TABS.map(t=>(
              <button key={t.key} onClick={()=>setActiveTab(t.key)} style={{
                background:'transparent',border:'none',
                borderBottom:activeTab===t.key?`2px solid ${T.accent}`:'2px solid transparent',
                padding:'10px 16px',fontFamily:FONTS.body,fontSize:13,
                color:activeTab===t.key?T.text:T.textSub,cursor:'pointer',
                fontWeight:activeTab===t.key?500:400,transition:'all 0.14s',
                marginBottom:-1,whiteSpace:'nowrap',flexShrink:0,
              }}>{t.label}</button>
            ))}
          </div>
        </motion.div>

        {/* Body */}
        <div style={{display:'flex',gap:18,alignItems:'flex-start'}}>
          <motion.div {...fadeUp(0.12)} style={{flex:1,minWidth:0}}>
            <AnimatePresence mode="wait">
              <motion.div key={activeTab}
                initial={{opacity:0,y:8}} animate={{opacity:1,y:0}}
                exit={{opacity:0,y:-6}} transition={{duration:0.18}}>
                {activeTab==='overview'  && <OverviewTab activation={activation} />}
                {activeTab==='actions'   && <ActionItemsTab activationId={id} />}
                {activeTab==='timeline'  && <TimelineTab activationId={id} activation={activation} />}
                {activeTab==='decisions' && <DecisionLogTab activationId={id} />}
                {activeTab==='reports'   && <ReportsTab activationId={id} />}
                {activeTab==='resources' && <ResourcesTab activationId={id} activation={activation} />}
              </motion.div>
            </AnimatePresence>
          </motion.div>

          {/* Right sidebar — hidden < 900 px */}
          <motion.div {...fadeUp(0.14)} className="rdd-sidebar" style={{width:260,flexShrink:0}}>
            <DetailSidebar activation={activation} setTab={setActiveTab}
              activeTab={activeTab} onReload={load} />
          </motion.div>
        </div>
      </div>
    </div>
  )
}