/**
 * LogsTab — Integration Audit Logs
 * Full structured activity log with request/response capture.
 * Features: filter by level/category/system, expand for error detail, pagination
 */
import { useState, useEffect, useCallback } from 'react'
import { integrationsApi, extractError } from '../../../services/api'
import { useToast } from '../../../context/ToastContext'
import { C } from '../constants'
import {
  Card, Btn, LogLevelBadge, Table, THead, Th, Td, TRow,
  Empty, Skeleton, Select, Modal, Pagination, reltime,
} from '../shared'

const LOG_LEVELS   = ['DEBUG','INFO','WARNING','ERROR','CRITICAL']
const LOG_CATS     = ['SYNC','WEBHOOK','AUTH','MAPPING','TRANSFORM','VALIDATION','HEALTH','GENERAL']

export default function LogsTab() {
  const [logs,     setLogs]     = useState([])
  const [systems,  setSystems]  = useState([])
  const [loading,  setLoading]  = useState(true)
  const [page,     setPage]     = useState(1)
  const [total,    setTotal]    = useState(0)
  const [filter,   setFilter]   = useState({ log_level:'', category:'', system:'' })
  const [expanded, setExpanded] = useState(null)
  const { error: toastErr } = useToast()
  const PAGE_SIZE = 20

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE, ordering:'-created_at' }
      if (filter.log_level) params.log_level = filter.log_level
      if (filter.category)  params.category  = filter.category
      if (filter.system)    params.external_system = filter.system
      const [lRes, sRes] = await Promise.all([
        integrationsApi.listLogs ? integrationsApi.listLogs(params)
          : import('../../../services/api').then(m => m.default.get('/integrations/logs/', { params })),
        systems.length ? Promise.resolve(null) : integrationsApi.listSystems({ page_size:100 }),
      ])
      setLogs(lRes.data.results || lRes.data)
      setTotal(lRes.data.count || 0)
      if (sRes) setSystems(sRes.data.results || sRes.data)
    } catch(e) { toastErr(extractError(e)) }
    finally { setLoading(false) }
  }, [page, filter])

  useEffect(() => { load() }, [load])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div>
      <div style={{ display:'flex', gap:8, marginBottom:16, flexWrap:'wrap', alignItems:'center' }}>
        <Select value={filter.log_level} onChange={e=>{ setFilter(p=>({...p,log_level:e.target.value})); setPage(1) }} style={{minWidth:120}}>
          <option value="">All levels</option>
          {LOG_LEVELS.map(l=><option key={l} value={l}>{l}</option>)}
        </Select>
        <Select value={filter.category} onChange={e=>{ setFilter(p=>({...p,category:e.target.value})); setPage(1) }} style={{minWidth:130}}>
          <option value="">All categories</option>
          {LOG_CATS.map(c=><option key={c} value={c}>{c}</option>)}
        </Select>
        <Select value={filter.system} onChange={e=>{ setFilter(p=>({...p,system:e.target.value})); setPage(1) }} style={{minWidth:160}}>
          <option value="">All systems</option>
          {systems.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
        </Select>
        <div style={{flex:1}}/>
        <Btn variant="ghost" size="sm" onClick={load}>↻ Refresh</Btn>
      </div>

      <Card>
        {loading ? <div style={{padding:16}}><Skeleton rows={10} /></div> : (
          <>
            <Table>
              <THead>
                <Th>Time</Th>
                <Th>Level</Th>
                <Th>Category</Th>
                <Th>System</Th>
                <Th>Operation</Th>
                <Th>Message</Th>
                <Th>Duration</Th>
                <Th></Th>
              </THead>
              <tbody>
                {logs.length===0 ? (
                  <tr><td colSpan={8}><Empty message="No logs" /></td></tr>
                ) : logs.map(log=>(
                  <TRow key={log.id} onClick={() => setExpanded(expanded===log.id ? null : log.id)}>
                    <Td style={{ fontFamily:C.mono, fontSize:9, whiteSpace:'nowrap' }}>{reltime(log.created_at)}</Td>
                    <Td><LogLevelBadge level={log.log_level} /></Td>
                    <Td style={{ fontFamily:C.mono, fontSize:9, color:C.textMuted }}>{log.category}</Td>
                    <Td style={{ fontSize:11 }}>{log.system_name || '—'}</Td>
                    <Td style={{ fontFamily:C.mono, fontSize:10, color:C.textSub }}>{log.operation || '—'}</Td>
                    <Td style={{ maxWidth:260, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', fontSize:12 }}>
                      {log.message}
                    </Td>
                    <Td style={{ fontFamily:C.mono, fontSize:10, color:C.textMuted }}>
                      {log.duration_ms ? `${log.duration_ms}ms` : '—'}
                    </Td>
                    <Td style={{ color:C.textMuted, fontSize:12 }}>
                      {(log.error_detail || log.response_data || log.request_data) ? (expanded===log.id ? '▲' : '▼') : ''}
                    </Td>
                  </TRow>
                ))}
              </tbody>
            </Table>

            {/* Expanded detail */}
            {expanded && (() => {
              const log = logs.find(l => l.id === expanded)
              if (!log) return null
              return (
                <div style={{ background:'rgba(0,0,0,0.25)', borderTop:`1px solid ${C.border}`, padding:'14px 16px' }}>
                  {log.error_detail && (
                    <div style={{ marginBottom:10 }}>
                      <div style={{ fontFamily:C.mono, fontSize:9, color:C.danger, letterSpacing:'0.1em', marginBottom:4 }}>ERROR DETAIL</div>
                      <pre style={{ fontFamily:C.mono, fontSize:10, color:C.textSub, margin:0, whiteSpace:'pre-wrap', wordBreak:'break-word' }}>
                        {log.error_detail}
                      </pre>
                    </div>
                  )}
                  {log.response_data && Object.keys(log.response_data).length > 0 && (
                    <div style={{ marginBottom:10 }}>
                      <div style={{ fontFamily:C.mono, fontSize:9, color:C.success, letterSpacing:'0.1em', marginBottom:4 }}>RESPONSE</div>
                      <pre style={{ fontFamily:C.mono, fontSize:10, color:C.textSub, margin:0, whiteSpace:'pre-wrap', wordBreak:'break-word' }}>
                        {JSON.stringify(log.response_data, null, 2)}
                      </pre>
                    </div>
                  )}
                  {log.request_data && Object.keys(log.request_data).length > 0 && (
                    <div>
                      <div style={{ fontFamily:C.mono, fontSize:9, color:C.info, letterSpacing:'0.1em', marginBottom:4 }}>REQUEST</div>
                      <pre style={{ fontFamily:C.mono, fontSize:10, color:C.textSub, margin:0, whiteSpace:'pre-wrap', wordBreak:'break-word', maxHeight:200, overflow:'auto' }}>
                        {JSON.stringify(log.request_data, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )
            })()}

            <div style={{padding:'10px 12px'}}>
              <Pagination page={page} totalPages={totalPages} total={total} pageSize={PAGE_SIZE} onPage={setPage} />
            </div>
          </>
        )}
      </Card>
    </div>
  )
}