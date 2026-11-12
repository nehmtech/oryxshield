/**
 * MappingsTab — Data Mappings
 * Field transformation rules between OryxShield and external systems.
 * Features: list, add, edit, delete, test mapping, filter by system/direction/entity
 */
import { useState, useEffect, useCallback } from 'react'
import { integrationsApi, extractError } from '../../../services/api'
import { useToast } from '../../../context/ToastContext'
import { C } from '../constants'
import {
  Card, Btn, IconBtn, Table, THead, Th, Td, TRow,
  Empty, Skeleton, Modal, Field, Input, Select, Pagination,
} from '../shared'

const DIRECTIONS  = ['INBOUND','OUTBOUND','BIDIRECTIONAL']
const TRANSFORMS  = ['NONE','UPPERCASE','LOWERCASE','DATE_FORMAT','CODE_LOOKUP','EXPRESSION','CONCAT','SPLIT']
const ERR_ACTIONS = ['SKIP','FAIL','DEFAULT']

const DIR_COLOR = { INBOUND:'#06b6d4', OUTBOUND:'#10b981', BIDIRECTIONAL:'#8b5cf6' }

const EMPTY_FORM = {
  external_system:'', entity_type:'', source_field:'', target_field:'',
  direction:'BIDIRECTIONAL', transform_type:'NONE', transformation_rule:'', default_value:'',
  is_required:false, validation_rule:'', validation_error_action:'SKIP', priority:0, is_active:true,
}

export default function MappingsTab() {
  const [mappings, setMappings] = useState([])
  const [systems,  setSystems]  = useState([])
  const [loading,  setLoading]  = useState(true)
  const [page,     setPage]     = useState(1)
  const [total,    setTotal]    = useState(0)
  const [filter,   setFilter]   = useState({ system:'', direction:'', entity_type:'' })
  const [modal,    setModal]    = useState(null)
  const [selected, setSelected] = useState(null)
  const [form,     setForm]     = useState(EMPTY_FORM)
  const [saving,   setSaving]   = useState(false)
  const [testResult, setTestResult] = useState(null)
  const { success, error: toastErr } = useToast()
  const PAGE_SIZE = 15

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE }
      if (filter.system)      params.external_system = filter.system
      if (filter.direction)   params.direction       = filter.direction
      if (filter.entity_type) params.entity_type     = filter.entity_type
      const [mRes, sRes] = await Promise.all([
        integrationsApi.listMappings(params),
        systems.length ? Promise.resolve(null) : integrationsApi.listSystems({ page_size:100 }),
      ])
      setMappings(mRes.data.results || mRes.data)
      setTotal(mRes.data.count || 0)
      if (sRes) setSystems(sRes.data.results || sRes.data)
    } catch(e) { toastErr(extractError(e)) }
    finally { setLoading(false) }
  }, [page, filter])

  useEffect(() => { load() }, [load])

  const openAdd = () => { setForm({...EMPTY_FORM}); setSelected(null); setTestResult(null); setModal('form') }
  const openEdit = (m) => {
    setForm({
      external_system:m.external_system, entity_type:m.entity_type,
      source_field:m.source_field, target_field:m.target_field,
      direction:m.direction, transform_type:m.transform_type,
      transformation_rule:m.transformation_rule||'', default_value:m.default_value||'',
      is_required:m.is_required, validation_rule:m.validation_rule||'',
      validation_error_action:m.validation_error_action, priority:m.priority, is_active:m.is_active,
    })
    setSelected(m); setTestResult(null); setModal('form')
  }

  const save = async () => {
    setSaving(true)
    try {
      if (!selected) {
        await integrationsApi.createMapping(form)
        success('Mapping created.')
      } else {
        await integrationsApi.updateMapping(selected.id, form)
        success('Mapping updated.')
      }
      setModal(null); load()
    } catch(e) { toastErr(extractError(e)) }
    finally { setSaving(false) }
  }

  const [pendingDelete, setPendingDelete] = useState(null)

  const del = async (m) => {
    if (pendingDelete?.id !== m.id) { setPendingDelete(m); return }
    setPendingDelete(null)
    try {
      await integrationsApi.deleteMapping(m.id)
      success('Mapping deleted.'); load()
    } catch(e) { toastErr(extractError(e)) }
  }

  const testMapping = async () => {
    if (!selected) return
    try {
      const res = await integrationsApi.testMapping(selected.id, { test_value: 'SAMPLE' })
      setTestResult(res.data)
    } catch(e) { setTestResult({ error: extractError(e) }) }
  }

  const set = (k, v) => setForm(p=>({...p,[k]:v}))
  const totalPages = Math.ceil(total/PAGE_SIZE)

  return (
    <div>
      <div style={{ display:'flex', gap:8, marginBottom:16, flexWrap:'wrap', alignItems:'center' }}>
        <Select value={filter.system} onChange={e=>{ setFilter(p=>({...p,system:e.target.value})); setPage(1) }} style={{minWidth:160}}>
          <option value="">All systems</option>
          {systems.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
        </Select>
        <Select value={filter.direction} onChange={e=>{ setFilter(p=>({...p,direction:e.target.value})); setPage(1) }} style={{minWidth:140}}>
          <option value="">All directions</option>
          {DIRECTIONS.map(d=><option key={d} value={d}>{d}</option>)}
        </Select>
        <input
          value={filter.entity_type}
          onChange={e=>{ setFilter(p=>({...p,entity_type:e.target.value})); setPage(1) }}
          placeholder="Entity type filter…"
          style={inputStyle}
        />
        <div style={{flex:1}}/>
        <Btn onClick={openAdd}>+ Add Mapping</Btn>
      </div>

      <Card>
        {loading ? <div style={{padding:16}}><Skeleton /></div> : (
          <>
            <Table>
              <THead>
                <Th>Entity</Th>
                <Th>Source Field</Th>
                <Th>→</Th>
                <Th>Target Field</Th>
                <Th>Direction</Th>
                <Th>Transform</Th>
                <Th>Required</Th>
                <Th>Active</Th>
                <Th>Actions</Th>
              </THead>
              <tbody>
                {mappings.length===0 ? (
                  <tr><td colSpan={9}><Empty message="No mappings configured" /></td></tr>
                ) : mappings.map(m=>(
                  <TRow key={m.id}>
                    <Td style={{ fontFamily:C.mono, fontSize:10, color:C.accent }}>{m.entity_type}</Td>
                    <Td style={{ fontFamily:C.mono, fontSize:10, color:C.text }}>{m.source_field}</Td>
                    <Td style={{ color:C.textMuted }}>→</Td>
                    <Td style={{ fontFamily:C.mono, fontSize:10, color:C.text }}>{m.target_field}</Td>
                    <Td>
                      <span style={{ fontFamily:C.mono, fontSize:9, color:DIR_COLOR[m.direction]||C.textMuted, background:`${DIR_COLOR[m.direction]||C.textMuted}18`, padding:'2px 7px', borderRadius:4 }}>
                        {m.direction}
                      </span>
                    </Td>
                    <Td style={{ fontFamily:C.mono, fontSize:9, color:C.textSub }}>{m.transform_type}</Td>
                    <Td style={{ fontFamily:C.mono, fontSize:9, color:m.is_required?C.warning:C.textMuted }}>{m.is_required?'YES':'—'}</Td>
                    <Td>
                      <span style={{ width:8,height:8,borderRadius:'50%',background:m.is_active?C.success:C.textMuted,display:'inline-block' }}/>
                    </Td>
                    <Td>
                      <div style={{display:'flex',gap:4}}>
                        <Btn size="sm" variant="ghost" onClick={()=>openEdit(m)}>Edit</Btn>
                        {pendingDelete?.id === m.id ? (
                          <>
                            <Btn size="sm" variant="danger" onClick={()=>del(m)}>Confirm</Btn>
                            <Btn size="sm" variant="ghost" onClick={()=>setPendingDelete(null)}>Cancel</Btn>
                          </>
                        ) : (
                          <Btn size="sm" variant="danger" onClick={()=>del(m)}>Del</Btn>
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

      <Modal open={modal==='form'} onClose={()=>setModal(null)} title={selected?'Edit Mapping':'New Mapping'} width={580}>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
          <Field label="External System" required style={{gridColumn:'span 2'}}>
            <Select value={form.external_system} onChange={e=>set('external_system',e.target.value)} style={{width:'100%'}}>
              <option value="">Select system…</option>
              {systems.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
            </Select>
          </Field>
          <Field label="Entity Type" required>
            <Input value={form.entity_type} onChange={e=>set('entity_type',e.target.value)} placeholder="e.g. Case, Contact" />
          </Field>
          <Field label="Direction">
            <Select value={form.direction} onChange={e=>set('direction',e.target.value)} style={{width:'100%'}}>
              {DIRECTIONS.map(d=><option key={d} value={d}>{d}</option>)}
            </Select>
          </Field>
          <Field label="Source Field" required>
            <Input value={form.source_field} onChange={e=>set('source_field',e.target.value)} placeholder="e.g. disease_code" />
          </Field>
          <Field label="Target Field" required>
            <Input value={form.target_field} onChange={e=>set('target_field',e.target.value)} placeholder="e.g. disease" />
          </Field>
          <Field label="Transform">
            <Select value={form.transform_type} onChange={e=>set('transform_type',e.target.value)} style={{width:'100%'}}>
              {TRANSFORMS.map(t=><option key={t} value={t}>{t}</option>)}
            </Select>
          </Field>
          <Field label="Default Value">
            <Input value={form.default_value} onChange={e=>set('default_value',e.target.value)} placeholder="Fallback value" />
          </Field>
          {form.transform_type!=='NONE' && (
            <Field label="Transform Rule / Expression" style={{gridColumn:'span 2'}}>
              <Input value={form.transformation_rule} onChange={e=>set('transformation_rule',e.target.value)} placeholder="Rule or expression…" />
            </Field>
          )}
          <Field label="Validation Rule">
            <Input value={form.validation_rule} onChange={e=>set('validation_rule',e.target.value)} placeholder="Optional regex / rule" />
          </Field>
          <Field label="On Validation Error">
            <Select value={form.validation_error_action} onChange={e=>set('validation_error_action',e.target.value)} style={{width:'100%'}}>
              {ERR_ACTIONS.map(a=><option key={a} value={a}>{a}</option>)}
            </Select>
          </Field>
          <Field label="Priority">
            <Input type="number" value={form.priority} onChange={e=>set('priority',+e.target.value)} />
          </Field>
          <div style={{gridColumn:'span 2', display:'flex', gap:16, paddingTop:4}}>
            <label style={{display:'flex',alignItems:'center',gap:6,cursor:'pointer',fontFamily:C.sans,fontSize:12,color:C.textSub}}>
              <input type="checkbox" checked={form.is_required} onChange={e=>set('is_required',e.target.checked)}/> Required
            </label>
            <label style={{display:'flex',alignItems:'center',gap:6,cursor:'pointer',fontFamily:C.sans,fontSize:12,color:C.textSub}}>
              <input type="checkbox" checked={form.is_active} onChange={e=>set('is_active',e.target.checked)}/> Active
            </label>
          </div>
        </div>

        {testResult && (
          <div style={{ marginTop:12, padding:'10px 14px', background:testResult.error?'rgba(239,68,68,0.08)':'rgba(16,185,129,0.08)', borderRadius:6, border:`1px solid ${testResult.error?C.danger:C.success}33` }}>
            <span style={{ fontFamily:C.mono, fontSize:10, color:testResult.error?C.danger:C.success }}>
              {testResult.error ? `Error: ${testResult.error}` : `Result: ${JSON.stringify(testResult.output)}`}
            </span>
          </div>
        )}

        <div style={{ display:'flex', gap:8, justifyContent:'flex-end', marginTop:20 }}>
          {selected && <Btn variant="ghost" onClick={testMapping}>Test</Btn>}
          <Btn variant="ghost" onClick={()=>setModal(null)}>Cancel</Btn>
          <Btn onClick={save} disabled={saving}>{saving?'Saving…':'Save Mapping'}</Btn>
        </div>
      </Modal>
    </div>
  )
}

const inputStyle = { fontFamily:C.sans,fontSize:12,color:C.text,background:'rgba(255,255,255,0.04)',border:`1px solid ${C.border}`,borderRadius:5,padding:'7px 10px',outline:'none',minWidth:180 }