/**
 * SystemsTab — External Systems Management
 */
import { useState, useEffect, useCallback } from 'react'
import { integrationsApi, extractError } from '../../../services/api'
import { useToast } from '../../../context/ToastContext'
import { C, HEALTH_COLOR } from '../constants'
import { Card, Btn, IconBtn, HealthBadge, Table, THead, Th, Td, TRow, Empty, Skeleton, Modal, Field, Input, Select, Pagination, reltime } from '../shared'

const SYSTEM_TYPES = ['DHIS2','SORMAS','WHO_EIOS','AFRICA_CDC','LIS','EMR','HMIS','CUSTOM']
const AUTH_TYPES   = ['API_KEY','OAUTH2','BASIC','TOKEN']
const TYPE_LABEL   = { DHIS2:'DHIS2', SORMAS:'SORMAS', WHO_EIOS:'WHO EIOS', AFRICA_CDC:'Africa CDC', LIS:'Lab Info System', EMR:'Electronic Med Record', HMIS:'Health MGMT Info', CUSTOM:'Custom' }
const TYPE_ICON    = { DHIS2:'🌐', SORMAS:'🔬', WHO_EIOS:'🏥', AFRICA_CDC:'🌍', LIS:'🧪', EMR:'📋', HMIS:'📊', CUSTOM:'⚙️' }

const EMPTY_FORM = { name:'', system_code:'', system_type:'DHIS2', description:'', base_url:'', api_version:'', timeout_seconds:30, auth_type:'API_KEY', credentials:{}, sync_interval_minutes:60, batch_size:100, sync_enabled:true, is_active:true }

export default function SystemsTab({ onRefreshSummary }) {
  const [systems,  setSystems]  = useState([])
  const [loading,  setLoading]  = useState(true)
  const [page,     setPage]     = useState(1)
  const [total,    setTotal]    = useState(0)
  const [filter,   setFilter]   = useState({ system_type:'', health_status:'', search:'' })
  const [modal,    setModal]    = useState(null)
  const [selected, setSelected] = useState(null)
  const [form,     setForm]     = useState(EMPTY_FORM)
  const [saving,   setSaving]   = useState(false)
  const [testing,  setTesting]  = useState({})
  const [syncing,  setSyncing]  = useState({})
  const [stats,    setStats]    = useState(null)
  const { success, error:toastErr } = useToast()
  const PS = 10

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size:PS }
      if (filter.system_type)   params.system_type   = filter.system_type
      if (filter.health_status) params.health_status = filter.health_status
      if (filter.search)        params.search        = filter.search
      const res = await integrationsApi.listSystems(params)
      setSystems(res.data.results || res.data)
      setTotal(res.data.count || 0)
    } catch(e) { toastErr(extractError(e)) }
    finally { setLoading(false) }
  }, [page, filter])

  useEffect(() => { load() }, [load])

  const openAdd  = () => { setForm({...EMPTY_FORM}); setSelected(null); setModal('form') }
  const openEdit = (s) => {
    setForm({ name:s.name, system_code:s.system_code, system_type:s.system_type, description:s.description||'', base_url:s.base_url, api_version:s.api_version||'', timeout_seconds:s.timeout_seconds, auth_type:s.auth_type, credentials:{}, sync_interval_minutes:s.sync_interval_minutes, batch_size:s.batch_size, sync_enabled:s.sync_enabled, is_active:s.is_active })
    setSelected(s); setModal('form')
  }
  const openStats = async (s) => {
    setSelected(s); setStats(null); setModal('stats')
    try { const r = await integrationsApi.systemStats(s.id); setStats(r.data) }
    catch { setStats({ error:true }) }
  }

  const save = async () => {
    setSaving(true)
    try {
      if (!selected) { await integrationsApi.createSystem(form); success('System added.') }
      else           { await integrationsApi.updateSystem(selected.id, form); success('System updated.') }
      setModal(null); load(); onRefreshSummary?.()
    } catch(e) { toastErr(extractError(e)) }
    finally { setSaving(false) }
  }

  const [pendingDelete, setPendingDelete] = useState(null)

  const del = async (s) => {
    if (pendingDelete?.id !== s.id) { setPendingDelete(s); return }
    setPendingDelete(null)
    try { await integrationsApi.deleteSystem(s.id); success('Deleted.'); load(); onRefreshSummary?.() }
    catch(e) { toastErr(extractError(e)) }
  }

  const testConn = async (s) => {
    setTesting(p=>({...p,[s.id]:true}))
    try {
      const r = await integrationsApi.testSystemConnection(s.id)
      const ok = r.data?.healthy ?? r.data?.success
      ok ? success(`${s.name}: connection OK`) : toastErr(`${s.name}: ${r.data?.error||'failed'}`)
      load()
    } catch(e) { toastErr(extractError(e)) }
    finally { setTesting(p=>({...p,[s.id]:false})) }
  }

  const triggerSync = async (s) => {
    setSyncing(p=>({...p,[s.id]:true}))
    try { await integrationsApi.triggerSystemSync(s.id, {}); success(`Sync queued for ${s.name}.`) }
    catch(e) { toastErr(extractError(e)) }
    finally { setSyncing(p=>({...p,[s.id]:false})) }
  }

  const set = (k,v) => setForm(p=>({...p,[k]:v}))
  const totalPages = Math.ceil(total/PS)

  return (
    <div>
      <div style={{ display:'flex', gap:8, marginBottom:16, flexWrap:'wrap', alignItems:'center' }}>
        <input value={filter.search} onChange={e=>{setFilter(p=>({...p,search:e.target.value}));setPage(1)}} placeholder="Search systems…" style={IS} />
        <Select value={filter.system_type} onChange={e=>{setFilter(p=>({...p,system_type:e.target.value}));setPage(1)}} style={{minWidth:140}}>
          <option value="">All types</option>
          {SYSTEM_TYPES.map(t=><option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
        </Select>
        <Select value={filter.health_status} onChange={e=>{setFilter(p=>({...p,health_status:e.target.value}));setPage(1)}} style={{minWidth:130}}>
          <option value="">All health</option>
          {['HEALTHY','DEGRADED','UNHEALTHY','UNKNOWN'].map(h=><option key={h} value={h}>{h}</option>)}
        </Select>
        <div style={{flex:1}}/>
        <Btn onClick={openAdd}>+ Add System</Btn>
      </div>

      {!loading && systems.length>0 && (
        <div style={{ display:'flex', gap:10, marginBottom:16, flexWrap:'wrap' }}>
          {['HEALTHY','DEGRADED','UNHEALTHY','UNKNOWN'].map(h=>{
            const cnt = systems.filter(s=>s.health_status===h).length
            if (!cnt) return null
            const col = HEALTH_COLOR[h]
            return <div key={h} style={{ background:`${col}0d`, border:`1px solid ${col}22`, borderRadius:6, padding:'6px 12px', display:'flex', gap:8, alignItems:'center' }}>
              <span style={{ fontFamily:C.display, fontSize:16, color:col }}>{cnt}</span>
              <span style={{ fontFamily:C.mono, fontSize:9, color:C.textMuted, letterSpacing:'0.1em' }}>{h}</span>
            </div>
          })}
        </div>
      )}

      <Card>
        {loading ? <div style={{padding:16}}><Skeleton /></div> : (
          <>
            <Table>
              <THead>
                <Th>System</Th><Th>Type</Th><Th>Health</Th><Th>Last Sync</Th><Th>OK / Fail</Th><Th>Actions</Th>
              </THead>
              <tbody>
                {systems.length===0 ? <tr><td colSpan={6}><Empty message="No external systems configured" /></td></tr>
                : systems.map(s=>(
                  <TRow key={s.id}>
                    <Td style={{color:C.text}}>
                      <div style={{display:'flex',alignItems:'center',gap:8}}>
                        <span style={{fontSize:16}}>{TYPE_ICON[s.system_type]||'⚙️'}</span>
                        <div>
                          <div style={{fontWeight:500,color:C.text}}>{s.name}</div>
                          <div style={{fontFamily:C.mono,fontSize:9,color:C.textMuted}}>{s.system_code}</div>
                        </div>
                      </div>
                    </Td>
                    <Td><span style={{fontFamily:C.mono,fontSize:9,color:C.accent,background:C.accentBg,padding:'2px 7px',borderRadius:4}}>{TYPE_LABEL[s.system_type]||s.system_type}</span></Td>
                    <Td><HealthBadge status={s.health_status} /></Td>
                    <Td style={{fontFamily:C.mono,fontSize:10}}>{reltime(s.last_sync)}</Td>
                    <Td style={{fontFamily:C.mono,fontSize:10}}>
                      <span style={{color:C.success}}>{s.successful_sync_count}</span>{' / '}
                      <span style={{color:s.failed_sync_count>0?C.danger:C.textMuted}}>{s.failed_sync_count}</span>
                    </Td>
                    <Td>
                      <div style={{display:'flex',gap:4}}>
                        <IconBtn onClick={()=>testConn(s)} title="Test connection" variant="accent" disabled={testing[s.id]}>{testing[s.id]?<Spin/>:<PingIco/>}</IconBtn>
                        <IconBtn onClick={()=>triggerSync(s)} title="Trigger sync" variant="success" disabled={syncing[s.id]}>{syncing[s.id]?<Spin/>:<SyncIco/>}</IconBtn>
                        <IconBtn onClick={()=>openStats(s)} title="Stats" variant="ghost"><StatsIco/></IconBtn>
                        <IconBtn onClick={()=>openEdit(s)} title="Edit" variant="ghost"><EditIco/></IconBtn>
                        {pendingDelete?.id === s.id ? (
                          <>
                            <Btn size="sm" variant="danger" onClick={()=>del(s)}>Confirm</Btn>
                            <Btn size="sm" variant="ghost" onClick={()=>setPendingDelete(null)}>Cancel</Btn>
                          </>
                        ) : (
                          <IconBtn onClick={()=>del(s)} title="Delete" variant="danger"><TrashIco/></IconBtn>
                        )}
                      </div>
                    </Td>
                  </TRow>
                ))}
              </tbody>
            </Table>
            <div style={{padding:'10px 12px'}}><Pagination page={page} totalPages={totalPages} total={total} pageSize={PS} onPage={setPage} /></div>
          </>
        )}
      </Card>

      <Modal open={modal==='form'} onClose={()=>setModal(null)} title={selected?'Edit System':'Add External System'} width={580}>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'0 16px'}}>
          <Field label="System Name" required><Input value={form.name} onChange={e=>set('name',e.target.value)} placeholder="e.g. Namibia DHIS2" /></Field>
          <Field label="System Code" required><Input value={form.system_code} onChange={e=>set('system_code',e.target.value)} placeholder="e.g. ke-dhis2" /></Field>
          <Field label="System Type" required><Select value={form.system_type} onChange={e=>set('system_type',e.target.value)} style={{width:'100%'}}>{SYSTEM_TYPES.map(t=><option key={t} value={t}>{TYPE_LABEL[t]}</option>)}</Select></Field>
          <Field label="Auth Type" required><Select value={form.auth_type} onChange={e=>set('auth_type',e.target.value)} style={{width:'100%'}}>{AUTH_TYPES.map(a=><option key={a} value={a}>{a}</option>)}</Select></Field>
          <Field label="Base URL" required style={{gridColumn:'span 2'}}><Input value={form.base_url} onChange={e=>set('base_url',e.target.value)} placeholder="https://dhis2.example.org" /></Field>
          <Field label="API Version"><Input value={form.api_version} onChange={e=>set('api_version',e.target.value)} placeholder="2.37" /></Field>
          <Field label="Timeout (s)"><Input type="number" value={form.timeout_seconds} onChange={e=>set('timeout_seconds',+e.target.value)} /></Field>
          {form.auth_type==='API_KEY' && <Field label="API Key" style={{gridColumn:'span 2'}}><Input type="password" value={form.credentials?.api_key||''} onChange={e=>set('credentials',{...form.credentials,api_key:e.target.value})} placeholder="Stored encrypted" /></Field>}
          {form.auth_type==='TOKEN'   && <Field label="Token"   style={{gridColumn:'span 2'}}><Input type="password" value={form.credentials?.token||''} onChange={e=>set('credentials',{...form.credentials,token:e.target.value})} placeholder="Bearer token" /></Field>}
          {form.auth_type==='BASIC'   && <>
            <Field label="Username"><Input value={form.credentials?.username||''} onChange={e=>set('credentials',{...form.credentials,username:e.target.value})} /></Field>
            <Field label="Password"><Input type="password" value={form.credentials?.password||''} onChange={e=>set('credentials',{...form.credentials,password:e.target.value})} /></Field>
          </>}
          <Field label="Sync Interval (min)"><Input type="number" value={form.sync_interval_minutes} onChange={e=>set('sync_interval_minutes',+e.target.value)} /></Field>
          <Field label="Batch Size"><Input type="number" value={form.batch_size} onChange={e=>set('batch_size',+e.target.value)} /></Field>
          <Field label="Description" style={{gridColumn:'span 2'}}>
            <textarea value={form.description} onChange={e=>set('description',e.target.value)} rows={2} style={{fontFamily:C.sans,fontSize:12,color:C.text,background:'rgba(255,255,255,0.04)',border:`1px solid ${C.border}`,borderRadius:5,padding:'7px 10px',outline:'none',width:'100%',resize:'vertical',boxSizing:'border-box'}} placeholder="Optional description" />
          </Field>
          <div style={{gridColumn:'span 2',display:'flex',gap:16}}>
            <label style={{display:'flex',alignItems:'center',gap:6,cursor:'pointer',fontFamily:C.sans,fontSize:12,color:C.textSub}}><input type="checkbox" checked={form.sync_enabled} onChange={e=>set('sync_enabled',e.target.checked)}/> Sync enabled</label>
            <label style={{display:'flex',alignItems:'center',gap:6,cursor:'pointer',fontFamily:C.sans,fontSize:12,color:C.textSub}}><input type="checkbox" checked={form.is_active} onChange={e=>set('is_active',e.target.checked)}/> Active</label>
          </div>
        </div>
        <div style={{display:'flex',gap:8,justifyContent:'flex-end',marginTop:20}}>
          <Btn variant="ghost" onClick={()=>setModal(null)}>Cancel</Btn>
          <Btn onClick={save} disabled={saving}>{saving?'Saving…':selected?'Save Changes':'Add System'}</Btn>
        </div>
      </Modal>

      <Modal open={modal==='stats'} onClose={()=>setModal(null)} title={`${selected?.name} — Stats`} width={460}>
        {!stats ? <div style={{textAlign:'center',padding:32,fontFamily:C.mono,fontSize:10,color:C.textMuted}}>LOADING…</div>
        : stats.error ? <div style={{color:C.danger,fontFamily:C.sans,fontSize:12}}>Could not load stats.</div>
        : (
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
            {[['Total syncs',selected?.total_sync_count],['Successful',selected?.successful_sync_count],['Failed',selected?.failed_sync_count],['Consec. failures',selected?.consecutive_failures],['Last sync',reltime(selected?.last_sync)],['Health check',reltime(selected?.last_health_check)]].map(([label,val])=>(
              <div key={label} style={{background:'rgba(255,255,255,0.03)',borderRadius:6,padding:'10px 14px'}}>
                <div style={{fontFamily:C.mono,fontSize:9,color:C.textMuted,letterSpacing:'0.1em',marginBottom:4}}>{label.toUpperCase()}</div>
                <div style={{fontFamily:C.display,fontSize:20,color:C.text}}>{val??'—'}</div>
              </div>
            ))}
          </div>
        )}
      </Modal>
    </div>
  )
}

const IS = { fontFamily:C.sans,fontSize:12,color:C.text,background:'rgba(255,255,255,0.04)',border:`1px solid ${C.border}`,borderRadius:5,padding:'7px 10px',outline:'none',minWidth:180 }
function Ico({size=14,children}){return <svg width={size} height={size} viewBox="0 0 16 16" fill="none">{children}</svg>}
function PingIco()  {return <Ico><circle cx="8" cy="8" r="5" stroke="currentColor" strokeWidth="1.3"/><circle cx="8" cy="8" r="1.5" fill="currentColor"/></Ico>}
function SyncIco()  {return <Ico><path d="M13 8A5 5 0 103 8M3 5v3H0" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></Ico>}
function StatsIco() {return <Ico><path d="M2 12l3-4 3 2 3-5 3 2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></Ico>}
function EditIco()  {return <Ico><path d="M11 2l3 3-9 9H2v-3L11 2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/></Ico>}
function TrashIco() {return <Ico><path d="M3 5h10M5 5V3h6v2M6 8v4M10 8v4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></Ico>}
function Spin()     {return <div style={{width:12,height:12,border:'2px solid rgba(255,255,255,0.15)',borderTop:'2px solid currentColor',borderRadius:'50%',animation:'ls-spin 0.7s linear infinite'}}><style>{`@keyframes ls-spin{to{transform:rotate(360deg)}}`}</style></div>}