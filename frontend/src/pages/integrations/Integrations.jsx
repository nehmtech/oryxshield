/**
 * Integrations — OryxShield
 * ====================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Tab-based integrations hub (admin-only).
 * Design tokens live in ./constants.js to avoid circular imports.
 */
import { useState, useEffect, useCallback } from 'react'
import { integrationsApi, extractError } from '../../services/api'
import { useToast } from '../../context/ToastContext'
import { C } from './constants'
import SystemsTab   from './tabs/SystemsTab'
import JobsTab      from './tabs/JobsTab'
import MappingsTab  from './tabs/MappingsTab'
import WebhooksTab  from './tabs/WebhooksTab'
import ApiKeysTab   from './tabs/ApiKeysTab'
import LogsTab      from './tabs/LogsTab'
import TransfersTab from './tabs/TransfersTab'

const TABS = [
  { id:'systems',   label:'Systems',  Icon:SystemsIcon   },
  { id:'jobs',      label:'Jobs',     Icon:JobsIcon      },
  { id:'mappings',  label:'Mappings', Icon:MappingsIcon  },
  { id:'webhooks',  label:'Webhooks', Icon:WebhooksIcon  },
  { id:'keys',      label:'API Keys', Icon:KeyIcon       },
  { id:'logs',      label:'Logs',     Icon:LogsIcon      },
  { id:'transfers', label:'Transfers',Icon:TransfersIcon },
]

export default function Integrations() {
  const [activeTab, setActiveTab] = useState('systems')
  const [summary,   setSummary]   = useState(null)
  const { error: toastErr } = useToast()

  const fetchSummary = useCallback(async () => {
    try {
      const [sRes, jRes, wRes] = await Promise.all([
        integrationsApi.listSystems({ page_size:1 }),
        integrationsApi.listJobs({ status:'RUNNING', page_size:1 }),
        integrationsApi.listWebhooks({ page_size:1 }),
      ])
      setSummary({
        systems:  sRes.data.count  ?? 0,
        running:  jRes.data.count  ?? 0,
        webhooks: wRes.data.count  ?? 0,
      })
    } catch { /* non-blocking */ }
  }, [])

  useEffect(() => { fetchSummary() }, [fetchSummary])

  return (
    <div style={{ minHeight:'100vh', background:C.bg, color:C.text, padding:'32px 28px' }}>

      {/* Header */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:28, flexWrap:'wrap', gap:20 }}>
        <div>
          <p style={{ fontFamily:C.mono, fontSize:9, color:C.accent, letterSpacing:'0.2em', margin:'0 0 6px', textTransform:'uppercase' }}>
            SYSTEM INTEGRATIONS
          </p>
          <h1 style={{ fontFamily:C.display, fontSize:32, color:C.text, margin:'0 0 6px', letterSpacing:'0.04em' }}>
            External Systems
          </h1>
          <p style={{ fontFamily:C.sans, fontSize:13, color:C.textSub, margin:0 }}>
            Manage DHIS2, SORMAS, WHO EIOS, Africa CDC and all connected health information systems.
          </p>
        </div>
        {summary && (
          <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
            <StatPill label="Connected" value={summary.systems} color={C.success} />
            <StatPill label="Running"   value={summary.running}  color={C.accent}  />
            <StatPill label="Webhooks"  value={summary.webhooks} color={C.purple}  />
          </div>
        )}
      </div>

      {/* Tab bar */}
      <div style={{ display:'flex', gap:2, borderBottom:`1px solid ${C.border}`, marginBottom:24, overflowX:'auto' }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              display:'flex', alignItems:'center', gap:6, padding:'10px 14px',
              background:'transparent', border:'none',
              borderBottom: activeTab===tab.id ? `2px solid ${C.accent}` : '2px solid transparent',
              cursor:'pointer', whiteSpace:'nowrap', position:'relative', zIndex:1,
            }}
          >
            <tab.Icon size={13} color={activeTab===tab.id ? C.accent : C.textMuted} />
            <span style={{
              fontFamily:C.sans, fontSize:12,
              fontWeight: activeTab===tab.id ? 600 : 400,
              color: activeTab===tab.id ? C.text : C.textSub,
            }}>
              {tab.label}
            </span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ minHeight:400 }}>
        {activeTab==='systems'   && <SystemsTab   onRefreshSummary={fetchSummary} />}
        {activeTab==='jobs'      && <JobsTab      />}
        {activeTab==='mappings'  && <MappingsTab  />}
        {activeTab==='webhooks'  && <WebhooksTab  />}
        {activeTab==='keys'      && <ApiKeysTab   />}
        {activeTab==='logs'      && <LogsTab      />}
        {activeTab==='transfers' && <TransfersTab />}
      </div>
    </div>
  )
}

function StatPill({ label, value, color }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', alignItems:'center', padding:'8px 18px', borderRadius:6, border:`1px solid ${color}22`, background:`${color}0d`, minWidth:70 }}>
      <span style={{ fontFamily:C.display, fontSize:22, color, lineHeight:1 }}>{value}</span>
      <span style={{ fontFamily:C.mono, fontSize:9, color:C.textMuted, marginTop:3, letterSpacing:'0.1em' }}>{label.toUpperCase()}</span>
    </div>
  )
}

// Icons
function Ico({ size=16, children }) { return <svg width={size} height={size} viewBox="0 0 16 16" fill="none" style={{flexShrink:0}}>{children}</svg> }
function SystemsIcon({ size, color })   { return <Ico size={size}><circle cx="4" cy="8" r="2" stroke={color} strokeWidth="1.2"/><circle cx="12" cy="4" r="2" stroke={color} strokeWidth="1.2"/><circle cx="12" cy="12" r="2" stroke={color} strokeWidth="1.2"/><path d="M6 8H9M10 5.5L6.5 7.5M10 10.5L6.5 8.5" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function JobsIcon({ size, color })      { return <Ico size={size}><rect x="2" y="2" width="12" height="12" rx="2" stroke={color} strokeWidth="1.2"/><path d="M5 8l2 2 4-4" stroke={color} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></Ico> }
function MappingsIcon({ size, color })  { return <Ico size={size}><path d="M2 4h4M10 4h4M2 12h4M10 12h4M6 4l4 8M6 12l4-8" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function WebhooksIcon({ size, color })  { return <Ico size={size}><path d="M2 3h12a1 1 0 011 1v7a1 1 0 01-1 1H5L2 14V4a1 1 0 011-1z" stroke={color} strokeWidth="1.2" strokeLinejoin="round"/></Ico> }
function KeyIcon({ size, color })       { return <Ico size={size}><circle cx="5.5" cy="9.5" r="3" stroke={color} strokeWidth="1.2"/><path d="M8 8l5.5-5.5M11 2.5L13.5 5M10 5.5l1.5 1.5" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function LogsIcon({ size, color })      { return <Ico size={size}><rect x="2" y="2" width="12" height="12" rx="1" stroke={color} strokeWidth="1.2"/><path d="M5 5h6M5 8h6M5 11h3" stroke={color} strokeWidth="1.2" strokeLinecap="round"/></Ico> }
function TransfersIcon({ size, color }) { return <Ico size={size}><path d="M2 6l4-4 4 4M6 2v10M14 10l-4 4-4-4M10 14V4" stroke={color} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></Ico> }