/**
 * ApiKeysTab — External API Key Management
 * Generates, displays prefix, revokes, rotates API keys for external consumers.
 * Features: create, revoke, rotate, show raw key once on creation
 */
import { useState, useEffect, useCallback } from 'react'
import { integrationsApi, extractError } from '../../../services/api'
import { useToast } from '../../../context/ToastContext'
import { C } from '../constants'
import {
  Card, Btn, Table, THead, Th, Td, TRow, Empty, Skeleton,
  Modal, Field, Input, Select, Pagination, reltime,
} from '../shared'

const SCOPES = ['READ','WRITE','ADMIN','WEBHOOK']

const EMPTY_FORM = {
  name:'', scope:'READ', expires_at:'', description:'', allowed_ips:'',
}

export default function ApiKeysTab() {
  const [keys,       setKeys]       = useState([])
  const [loading,    setLoading]    = useState(true)
  const [page,       setPage]       = useState(1)
  const [total,      setTotal]      = useState(0)
  const [modal,      setModal]      = useState(null) // null|'add'|'newkey'
  const [form,       setForm]       = useState(EMPTY_FORM)
  const [saving,     setSaving]     = useState(false)
  const [revoking,   setRevoking]   = useState({})
  const [rotating,   setRotating]   = useState({})
  const [newKey,     setNewKey]     = useState(null)  // raw key shown once
  const [pendingAction, setPendingAction] = useState(null) // { id, type: 'revoke'|'rotate' }
  const { success, error: toastErr } = useToast()
  const PAGE_SIZE = 12

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await integrationsApi.listExternalApiKeys({ page, page_size: PAGE_SIZE })
      setKeys(res.data.results || res.data)
      setTotal(res.data.count || 0)
    } catch(e) { toastErr(extractError(e)) }
    finally { setLoading(false) }
  }, [page])

  useEffect(() => { load() }, [load])

  const create = async () => {
    setSaving(true)
    try {
      const res = await integrationsApi.createExternalApiKey(form)
      const raw = res.data.raw_key
      setNewKey(raw)
      setModal('newkey')
      load()
    } catch(e) { toastErr(extractError(e)) }
    finally { setSaving(false) }
  }

  const revoke = async (key) => {
    if (pendingAction?.id !== key.id || pendingAction?.type !== 'revoke') {
      setPendingAction({ id: key.id, type: 'revoke' }); return
    }
    setPendingAction(null)
    setRevoking(p=>({...p,[key.id]:true}))
    try {
      await integrationsApi.revokeExternalApiKey(key.id)
      success('Key revoked.'); load()
    } catch(e) { toastErr(extractError(e)) }
    finally { setRevoking(p=>({...p,[key.id]:false})) }
  }

  const rotate = async (key) => {
    if (pendingAction?.id !== key.id || pendingAction?.type !== 'rotate') {
      setPendingAction({ id: key.id, type: 'rotate' }); return
    }
    setPendingAction(null)
    setRotating(p=>({...p,[key.id]:true}))
    try {
      const res = await integrationsApi.rotateExternalApiKey(key.id)
      const raw = res.data.raw_key
      setNewKey(raw); setModal('newkey')
      load()
    } catch(e) { toastErr(extractError(e)) }
    finally { setRotating(p=>({...p,[key.id]:false})) }
  }

  const set = (k,v) => setForm(p=>({...p,[k]:v}))
  const totalPages = Math.ceil(total/PAGE_SIZE)

  return (
    <div>
      <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:16 }}>
        <Btn onClick={()=>{ setForm({...EMPTY_FORM}); setModal('add') }}>+ Generate Key</Btn>
      </div>

      <Card>
        {loading ? <div style={{padding:16}}><Skeleton /></div> : (
          <>
            <Table>
              <THead>
                <Th>Name</Th>
                <Th>Prefix</Th>
                <Th>Scope</Th>
                <Th>Status</Th>
                <Th>Requests</Th>
                <Th>Last Used</Th>
                <Th>Expires</Th>
                <Th>Actions</Th>
              </THead>
              <tbody>
                {keys.length===0 ? (
                  <tr><td colSpan={8}><Empty message="No API keys" /></td></tr>
                ) : keys.map(key=>(
                  <TRow key={key.id}>
                    <Td style={{ color:C.text, fontWeight:500 }}>{key.name}</Td>
                    <Td style={{ fontFamily:C.mono, fontSize:10, color:C.accent }}>
                      {key.key_prefix}…
                    </Td>
                    <Td>
                      <span style={{ fontFamily:C.mono, fontSize:9, color:C.info, background:'rgba(6,182,212,0.12)', padding:'2px 7px', borderRadius:4 }}>
                        {key.scope}
                      </span>
                    </Td>
                    <Td>
                      {key.revoked_at ? (
                        <span style={{ fontFamily:C.mono, fontSize:9, color:C.danger }}>REVOKED</span>
                      ) : key.is_expired ? (
                        <span style={{ fontFamily:C.mono, fontSize:9, color:C.warning }}>EXPIRED</span>
                      ) : (
                        <span style={{ fontFamily:C.mono, fontSize:9, color:C.success }}>ACTIVE</span>
                      )}
                    </Td>
                    <Td style={{ fontFamily:C.mono, fontSize:10 }}>
                      <span style={{ color:C.success }}>{key.successful_requests}</span>
                      {' / '}
                      <span style={{ color:key.failed_requests>0?C.danger:C.textMuted }}>{key.total_requests}</span>
                    </Td>
                    <Td style={{ fontFamily:C.mono, fontSize:10 }}>{reltime(key.last_used)}</Td>
                    <Td style={{ fontFamily:C.mono, fontSize:10, color:C.textMuted }}>
                      {key.expires_at ? new Date(key.expires_at).toLocaleDateString('en-NA') : 'Never'}
                    </Td>
                    <Td>
                      <div style={{ display:'flex', gap:4, flexWrap:'wrap' }}>
                        {!key.revoked_at && (
                          <>
                            {pendingAction?.id === key.id && pendingAction?.type === 'rotate' ? (
                              <>
                                <Btn size="sm" variant="danger" onClick={()=>rotate(key)}>Confirm Rotate</Btn>
                                <Btn size="sm" variant="ghost" onClick={()=>setPendingAction(null)}>Cancel</Btn>
                              </>
                            ) : (
                              <Btn size="sm" variant="ghost" onClick={()=>rotate(key)} disabled={rotating[key.id]}>
                                {rotating[key.id]?'…':'Rotate'}
                              </Btn>
                            )}
                            {pendingAction?.id === key.id && pendingAction?.type === 'revoke' ? (
                              <>
                                <Btn size="sm" variant="danger" onClick={()=>revoke(key)}>Confirm Revoke</Btn>
                                <Btn size="sm" variant="ghost" onClick={()=>setPendingAction(null)}>Cancel</Btn>
                              </>
                            ) : (
                              <Btn size="sm" variant="danger" onClick={()=>revoke(key)} disabled={revoking[key.id]}>
                                {revoking[key.id]?'…':'Revoke'}
                              </Btn>
                            )}
                          </>
                        )}
                      </div>
                    </Td>
                  </TRow>
                ))}
              </tbody>
            </Table>
            <div style={{padding:'10px 12px'}}>
              <Pagination page={page} totalPages={totalPages} total={total} pageSize={PAGE_SIZE} onPage={setPage} />
            </div>
          </>
        )}
      </Card>

      {/* ── Create Modal ── */}
      <Modal open={modal==='add'} onClose={()=>setModal(null)} title="Generate API Key" width={460}>
        <Field label="Key Name" required>
          <Input value={form.name} onChange={e=>set('name',e.target.value)} placeholder="e.g. Namibia Red Cross integration" />
        </Field>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
          <Field label="Scope">
            <Select value={form.scope} onChange={e=>set('scope',e.target.value)} style={{width:'100%'}}>
              {SCOPES.map(s=><option key={s} value={s}>{s}</option>)}
            </Select>
          </Field>
          <Field label="Expires At">
            <Input type="date" value={form.expires_at} onChange={e=>set('expires_at',e.target.value)} />
          </Field>
        </div>
        <Field label="Allowed IPs (comma-separated)">
          <Input value={form.allowed_ips} onChange={e=>set('allowed_ips',e.target.value)} placeholder="Leave blank for any" />
        </Field>
        <Field label="Description">
          <Input value={form.description} onChange={e=>set('description',e.target.value)} placeholder="Optional notes" />
        </Field>
        <div style={{ display:'flex', gap:8, justifyContent:'flex-end', marginTop:20 }}>
          <Btn variant="ghost" onClick={()=>setModal(null)}>Cancel</Btn>
          <Btn onClick={create} disabled={saving}>{saving?'Generating…':'Generate Key'}</Btn>
        </div>
      </Modal>

      {/* ── New Key Display — shown ONCE ── */}
      <Modal open={modal==='newkey'} onClose={()=>{ setModal(null); setNewKey(null) }} title="API Key Generated" width={480}>
        <div style={{ background:'rgba(16,185,129,0.07)', border:`1px solid ${C.success}33`, borderRadius:8, padding:16, marginBottom:16 }}>
          <p style={{ fontFamily:C.mono, fontSize:11, color:C.warning, marginBottom:10 }}>
            ⚠ Copy this key now. It will not be shown again.
          </p>
          <div style={{ display:'flex', gap:8, alignItems:'center' }}>
            <code style={{ flex:1, fontFamily:C.mono, fontSize:12, color:C.success, background:'rgba(0,0,0,0.3)', padding:'8px 12px', borderRadius:5, wordBreak:'break-all' }}>
              {newKey}
            </code>
            <Btn size="sm" onClick={()=>{ navigator.clipboard.writeText(newKey); success('Copied!') }}>Copy</Btn>
          </div>
        </div>
        <Btn onClick={()=>{ setModal(null); setNewKey(null) }}>Done</Btn>
      </Modal>
    </div>
  )
}