/**
 * TransfersTab — Data Transfer Records
 * Audit trail for all data movement between systems.
 * Features: list, filter by status/type, view metrics, success rate bars
 */
import { useState, useEffect, useCallback } from 'react'
import { integrationsApi, extractError } from '../../../services/api'
import { useToast } from '../../../context/ToastContext'
import { C } from '../constants'
import {
  Card, Btn, StatusBadge, Table, THead, Th, Td, TRow,
  Empty, Skeleton, Select, Pagination, ProgressBar, reltime, fmtBytes,
} from '../shared'

const TRANSFER_TYPES = ['BATCH','REALTIME','SCHEDULED','MANUAL']
const STATUSES = ['QUEUED','TRANSFERRING','VERIFYING','COMPLETED','FAILED','PARTIAL','ROLLED_BACK']

export default function TransfersTab() {
  const [transfers, setTransfers] = useState([])
  const [loading,   setLoading]   = useState(true)
  const [page,      setPage]      = useState(1)
  const [total,     setTotal]     = useState(0)
  const [filter,    setFilter]    = useState({ status:'', transfer_type:'' })
  const [expanded,  setExpanded]  = useState(null)
  const { error: toastErr } = useToast()
  const PAGE_SIZE = 15

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE }
      if (filter.status)        params.status        = filter.status
      if (filter.transfer_type) params.transfer_type = filter.transfer_type
      const res = await integrationsApi.listTransfers(params)
      setTransfers(res.data.results || res.data)
      setTotal(res.data.count || 0)
    } catch(e) { toastErr(extractError(e)) }
    finally { setLoading(false) }
  }, [page, filter])

  useEffect(() => { load() }, [load])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const fmtDur = (sec) => {
    if (!sec) return '—'
    if (sec < 60) return `${sec.toFixed(1)}s`
    return `${(sec/60).toFixed(1)}m`
  }

  return (
    <div>
      <div style={{ display:'flex', gap:8, marginBottom:16, flexWrap:'wrap', alignItems:'center' }}>
        <Select value={filter.status} onChange={e=>{ setFilter(p=>({...p,status:e.target.value})); setPage(1) }} style={{minWidth:130}}>
          <option value="">All statuses</option>
          {STATUSES.map(s=><option key={s} value={s}>{s}</option>)}
        </Select>
        <Select value={filter.transfer_type} onChange={e=>{ setFilter(p=>({...p,transfer_type:e.target.value})); setPage(1) }} style={{minWidth:130}}>
          <option value="">All types</option>
          {TRANSFER_TYPES.map(t=><option key={t} value={t}>{t}</option>)}
        </Select>
        <div style={{flex:1}}/>
        <Btn variant="ghost" size="sm" onClick={load}>↻ Refresh</Btn>
      </div>

      <Card>
        {loading ? <div style={{padding:16}}><Skeleton rows={8} /></div> : (
          <>
            <Table>
              <THead>
                <Th>Transfer ID</Th>
                <Th>Source → Target</Th>
                <Th>Type</Th>
                <Th>Entity</Th>
                <Th>Status</Th>
                <Th>Records</Th>
                <Th>Success Rate</Th>
                <Th>Duration</Th>
                <Th>Size</Th>
                <Th>Started</Th>
              </THead>
              <tbody>
                {transfers.length===0 ? (
                  <tr><td colSpan={10}><Empty message="No transfer records" /></td></tr>
                ) : transfers.map(t=>(
                  <>
                    <TRow key={t.id} onClick={()=>setExpanded(expanded===t.id?null:t.id)}>
                      <Td style={{ fontFamily:C.mono, fontSize:9, color:C.accent }}>{t.transfer_id}</Td>
                      <Td style={{ fontSize:11 }}>
                        <div style={{ display:'flex', flexDirection:'column', gap:1 }}>
                          <span style={{ color:C.textSub }}>{t.source_name || '—'}</span>
                          <span style={{ color:C.textMuted, fontSize:9 }}>→ {t.target_name || '—'}</span>
                        </div>
                      </Td>
                      <Td>
                        <span style={{ fontFamily:C.mono, fontSize:9, color:C.info, background:'rgba(6,182,212,0.12)', padding:'2px 7px', borderRadius:4 }}>
                          {t.transfer_type}
                        </span>
                      </Td>
                      <Td style={{ fontSize:11, color:C.textSub }}>{t.entity_type}</Td>
                      <Td><StatusBadge status={t.status} /></Td>
                      <Td style={{ fontFamily:C.mono, fontSize:10 }}>
                        <span style={{ color:C.success }}>{t.transferred_records}</span>
                        {' / '}
                        <span style={{ color:C.textMuted }}>{t.record_count}</span>
                        {t.failed_records>0 && <span style={{ color:C.danger }}> ({t.failed_records} fail)</span>}
                      </Td>
                      <Td style={{ minWidth:90 }}>
                        {t.record_count > 0 ? (
                          <div style={{ display:'flex', flexDirection:'column', gap:3 }}>
                            <ProgressBar
                              pct={Math.round(t.transferred_records/t.record_count*100)}
                              color={t.failed_records>0?C.warning:C.success}
                            />
                            <span style={{ fontFamily:C.mono, fontSize:9, color:C.textMuted }}>
                              {Math.round(t.transferred_records/t.record_count*100)}%
                            </span>
                          </div>
                        ) : '—'}
                      </Td>
                      <Td style={{ fontFamily:C.mono, fontSize:10, color:C.textMuted }}>{fmtDur(t.duration_seconds)}</Td>
                      <Td style={{ fontFamily:C.mono, fontSize:10, color:C.textMuted }}>{fmtBytes(t.data_size_bytes)}</Td>
                      <Td style={{ fontFamily:C.mono, fontSize:10 }}>{reltime(t.started_at)}</Td>
                    </TRow>
                    {expanded===t.id && t.error_message && (
                      <tr key={`${t.id}-exp`}>
                        <td colSpan={10} style={{ padding:'0 16px 12px', background:'rgba(0,0,0,0.2)', borderBottom:`1px solid ${C.border}` }}>
                          <div style={{ fontFamily:C.mono, fontSize:10, color:C.danger, padding:'10px 0' }}>
                            <span style={{ color:C.textMuted, marginRight:8 }}>ERROR:</span>
                            {t.error_message}
                          </div>
                          {t.validation_errors?.length > 0 && (
                            <div style={{ fontFamily:C.mono, fontSize:10, color:C.warning }}>
                              {t.validation_errors.length} validation error(s)
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </Table>
            <div style={{padding:'10px 12px'}}>
              <Pagination page={page} totalPages={totalPages} total={total} pageSize={PAGE_SIZE} onPage={setPage} />
            </div>
          </>
        )}
      </Card>
    </div>
  )
}