/**
 * WebhooksTab — Outbound Webhooks
 * Manages event delivery endpoints for external consumers.
 * Features: CRUD, test, toggle, view delivery logs, success rate
 */
import { useState, useEffect, useCallback } from 'react'
import { integrationsApi, extractError } from '../../../services/api'
import { useToast } from '../../../context/ToastContext'
import { C } from '../constants'
import {
  Card, Btn, StatusBadge, Table, THead, Th, Td, TRow,
  Empty, Skeleton, Modal, Field, Input, Select, Pagination, reltime,
} from '../shared'

const EVENT_TYPES = [
  'CASE_CREATED','CASE_UPDATED','ALERT_GENERATED','ALERT_RESOLVED',
  'OUTBREAK_DETECTED','RESPONSE_ACTIVATED','SYNC_COMPLETED','HEALTH_STATUS_CHANGED',
]
const SIGNING_ALGOS = ['HMAC_SHA256','HMAC_SHA512','NONE']

const EMPTY_FORM = {
  name:'', webhook_url:'', event_type:'CASE_CREATED',
  secret_key:'', signing_algorithm:'HMAC_SHA256',
  max_retries:3, retry_delay_seconds:60, timeout_seconds:30,
  is_active:true, headers:{},
}

export default function WebhooksTab() {
  const [webhooks, setWebhooks] = useState([])
  const [loading,  setLoading]  = useState(true)
  const [page,     setPage]     = useState(1)
  const [total,    setTotal]    = useState(0)
  const [modal,    setModal]    = useState(null)  // null|'form'|'logs'
  const [selected, setSelected] = useState(null)
  const [form,     setForm]     = useState(EMPTY_FORM)
  const [saving,   setSaving]   = useState(false)
  const [testing,  setTesting]  = useState({})
  const [toggling, setToggling] = useState({})
  const [logs,     setLogs]     = useState([])
  const [logsLoading, setLogsLoading] = useState(false)
  const { success, error: toastErr } = useToast()
  const PAGE_SIZE = 12

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await integrationsApi.listWebhooks({ page, page_size: PAGE_SIZE })
      setWebhooks(res.data.results || res.data)
      setTotal(res.data.count || 0)
    } catch(e) { toastErr(extractError(e)) }
    finally { setLoading(false) }
  }, [page])

  useEffect(() => { load() }, [load])

  const openAdd = () => { setForm({...EMPTY_FORM}); setSelected(null); setModal('form') }
  const openEdit = (wh) => {
    setForm({
      name:wh.name, webhook_url:wh.webhook_url, event_type:wh.event_type,
      secret_key:'', signing_algorithm:wh.signing_algorithm||'HMAC_SHA256',
      max_retries:wh.max_retries||3, retry_delay_seconds:wh.retry_delay_seconds||60,
      timeout_seconds:wh.timeout_seconds||30, is_active:wh.is_active, headers:{},
    })
    setSelected(wh); setModal('form')
  }

  const openLogs = async (wh) => {
    setSelected(wh); setLogs([]); setLogsLoading(true); setModal('logs')
    try {
      const res = await integrationsApi.webhookDeliveries(wh.id, { page_size:20 })
      setLogs(res.data.results || res.data)
    } catch(e) { toastErr(extractError(e)) }
    finally { setLogsLoading(false) }
  }

  const save = async () => {
    setSaving(true)
    try {
      if (!selected) {
        await integrationsApi.createWebhook(form); success('Webhook created.')
      } else {
        await integrationsApi.updateWebhook(selected.id, form); success('Webhook updated.')
      }
      setModal(null); load()
    } catch(e) { toastErr(extractError(e)) }
    finally { setSaving(false) }
  }

  const [pendingDelete, setPendingDelete] = useState(null)

  const del = async (wh) => {
    if (pendingDelete?.id !== wh.id) { setPendingDelete(wh); return }
    setPendingDelete(null)
    try {
      await integrationsApi.deleteWebhook(wh.id); success('Webhook deleted.'); load()
    } catch(e) { toastErr(extractError(e)) }
  }

  const test = async (wh) => {
    setTesting(p=>({...p,[wh.id]:true}))
    try {
      const res = await integrationsApi.testWebhook(wh.id)
      success(`Test delivery: ${res.data?.status || 'sent'}`)
    } catch(e) { toastErr(extractError(e)) }
    finally { setTesting(p=>({...p,[wh.id]:false})) }
  }

  const toggle = async (wh) => {
    setToggling(p=>({...p,[wh.id]:true}))
    try {
      await integrationsApi.toggleWebhook(wh.id)
      success(`Webhook ${wh.is_active?'disabled':'enabled'}.`); load()
    } catch(e) { toastErr(extractError(e)) }
    finally { setToggling(p=>({...p,[wh.id]:false})) }
  }

  const set = (k,v) => setForm(p=>({...p,[k]:v}))
  const totalPages = Math.ceil(total/PAGE_SIZE)

  return (
    <div>
      <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:16 }}>
        <Btn onClick={openAdd}>+ Add Webhook</Btn>
      </div>

      <Card>
        {loading ? <div style={{padding:16}}><Skeleton /></div> : (
          <>
            <Table>
              <THead>
                <Th>Name</Th>
                <Th>Event</Th>
                <Th>URL</Th>
                <Th>Status</Th>
                <Th>Success Rate</Th>
                <Th>Total Calls</Th>
                <Th>Last Triggered</Th>
                <Th>Actions</Th>
              </THead>
              <tbody>
                {webhooks.length===0 ? (
                  <tr><td colSpan={8}><Empty message="No webhooks registered" /></td></tr>
                ) : webhooks.map(wh => {
                  const rate = wh.total_calls > 0
                    ? Math.round(wh.successful_calls / wh.total_calls * 100)
                    : null
                  return (
                    <TRow key={wh.id}>
                      <Td style={{ color:C.text, fontWeight:500 }}>{wh.name}</Td>
                      <Td>
                        <span style={{ fontFamily:C.mono, fontSize:9, color:C.purple, background:'rgba(139,92,246,0.12)', padding:'2px 7px', borderRadius:4 }}>
                          {wh.event_type}
                        </span>
                      </Td>
                      <Td style={{ fontFamily:C.mono, fontSize:9, color:C.textMuted, maxWidth:200, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                        {wh.webhook_url}
                      </Td>
                      <Td>
                        <span style={{ fontFamily:C.mono, fontSize:9, color:wh.is_active?C.success:C.textMuted, background:`${wh.is_active?C.success:C.textMuted}18`, padding:'2px 7px', borderRadius:4 }}>
                          {wh.is_active ? 'ACTIVE' : 'PAUSED'}
                        </span>
                      </Td>
                      <Td>
                        {rate !== null ? (
                          <div style={{ display:'flex', flexDirection:'column', gap:3 }}>
                            <div style={{ width:80, height:3, background:'rgba(255,255,255,0.07)', borderRadius:2 }}>
                              <div style={{ width:`${rate}%`, height:'100%', background:rate>80?C.success:rate>50?C.warning:C.danger, borderRadius:2 }} />
                            </div>
                            <span style={{ fontFamily:C.mono, fontSize:9, color:C.textMuted }}>{rate}%</span>
                          </div>
                        ) : '—'}
                      </Td>
                      <Td style={{ fontFamily:C.mono, fontSize:10 }}>{wh.total_calls}</Td>
                      <Td style={{ fontFamily:C.mono, fontSize:10 }}>{reltime(wh.last_triggered)}</Td>
                      <Td>
                        <div style={{ display:'flex', gap:4 }}>
                          <Btn size="sm" variant="ghost" onClick={()=>test(wh)} disabled={testing[wh.id]}>
                            {testing[wh.id] ? '…' : 'Test'}
                          </Btn>
                          <Btn size="sm" variant={wh.is_active?'warning':'success'} onClick={()=>toggle(wh)} disabled={toggling[wh.id]}>
                            {wh.is_active ? 'Pause' : 'Enable'}
                          </Btn>
                          <Btn size="sm" variant="ghost" onClick={()=>openLogs(wh)}>Logs</Btn>
                          <Btn size="sm" variant="ghost" onClick={()=>openEdit(wh)}>Edit</Btn>
                          {pendingDelete?.id === wh.id ? (
                            <>
                              <Btn size="sm" variant="danger" onClick={()=>del(wh)}>Confirm</Btn>
                              <Btn size="sm" variant="ghost" onClick={()=>setPendingDelete(null)}>Cancel</Btn>
                            </>
                          ) : (
                            <Btn size="sm" variant="danger" onClick={()=>del(wh)}>Del</Btn>
                          )}
                        </div>
                      </Td>
                    </TRow>
                  )
                })}
              </tbody>
            </Table>
            <div style={{padding:'10px 12px'}}>
              <Pagination page={page} totalPages={totalPages} total={total} pageSize={PAGE_SIZE} onPage={setPage} />
            </div>
          </>
        )}
      </Card>

      {/* ── Form Modal ── */}
      <Modal open={modal==='form'} onClose={()=>setModal(null)} title={selected?'Edit Webhook':'New Webhook'} width={520}>
        <Field label="Name" required>
          <Input value={form.name} onChange={e=>set('name',e.target.value)} placeholder="e.g. DHIS2 case alert" />
        </Field>
        <Field label="URL" required>
          <Input value={form.webhook_url} onChange={e=>set('webhook_url',e.target.value)} placeholder="https://your-system/webhook" />
        </Field>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
          <Field label="Event Type" required>
            <Select value={form.event_type} onChange={e=>set('event_type',e.target.value)} style={{width:'100%'}}>
              {EVENT_TYPES.map(t=><option key={t} value={t}>{t}</option>)}
            </Select>
          </Field>
          <Field label="Signing Algorithm">
            <Select value={form.signing_algorithm} onChange={e=>set('signing_algorithm',e.target.value)} style={{width:'100%'}}>
              {SIGNING_ALGOS.map(a=><option key={a} value={a}>{a}</option>)}
            </Select>
          </Field>
          <Field label="Secret Key">
            <Input type="password" value={form.secret_key} onChange={e=>set('secret_key',e.target.value)} placeholder="HMAC signing key" />
          </Field>
          <Field label="Timeout (s)">
            <Input type="number" value={form.timeout_seconds} onChange={e=>set('timeout_seconds',+e.target.value)} />
          </Field>
          <Field label="Max Retries">
            <Input type="number" value={form.max_retries} onChange={e=>set('max_retries',+e.target.value)} />
          </Field>
          <Field label="Retry Delay (s)">
            <Input type="number" value={form.retry_delay_seconds} onChange={e=>set('retry_delay_seconds',+e.target.value)} />
          </Field>
        </div>
        <label style={{ display:'flex', alignItems:'center', gap:6, cursor:'pointer', fontFamily:C.sans, fontSize:12, color:C.textSub, marginTop:8 }}>
          <input type="checkbox" checked={form.is_active} onChange={e=>set('is_active',e.target.checked)}/> Active
        </label>
        <div style={{ display:'flex', gap:8, justifyContent:'flex-end', marginTop:20 }}>
          <Btn variant="ghost" onClick={()=>setModal(null)}>Cancel</Btn>
          <Btn onClick={save} disabled={saving}>{saving?'Saving…':'Save Webhook'}</Btn>
        </div>
      </Modal>

      {/* ── Delivery Logs Modal ── */}
      <Modal open={modal==='logs'} onClose={()=>setModal(null)} title={`${selected?.name} — Deliveries`} width={620}>
        {logsLoading ? <Skeleton rows={5} /> : logs.length===0 ? (
          <Empty message="No delivery records" />
        ) : (
          <Table>
            <THead>
              <Th>Time</Th>
              <Th>Event</Th>
              <Th>Status</Th>
              <Th>HTTP</Th>
              <Th>Latency</Th>
              <Th>Attempt</Th>
            </THead>
            <tbody>
              {logs.map(log=>(
                <TRow key={log.id}>
                  <Td style={{fontFamily:C.mono,fontSize:9}}>{reltime(log.created_at)}</Td>
                  <Td style={{fontFamily:C.mono,fontSize:9,color:C.textSub}}>{log.event_type}</Td>
                  <Td>
                    <span style={{fontFamily:C.mono,fontSize:9,color:log.is_successful?C.success:C.danger}}>
                      {log.is_successful ? '✓ OK' : '✗ FAIL'}
                    </span>
                  </Td>
                  <Td style={{fontFamily:C.mono,fontSize:10,color:log.response_status_code>=400?C.danger:C.success}}>
                    {log.response_status_code || '—'}
                  </Td>
                  <Td style={{fontFamily:C.mono,fontSize:10}}>{log.response_time_ms ? `${log.response_time_ms}ms` : '—'}</Td>
                  <Td style={{fontFamily:C.mono,fontSize:10,color:C.textMuted}}>{log.attempt_number}</Td>
                </TRow>
              ))}
            </tbody>
          </Table>
        )}
      </Modal>
    </div>
  )
}