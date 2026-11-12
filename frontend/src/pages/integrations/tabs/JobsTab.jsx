/**
 * JobsTab — Integration Jobs
 * Full lifecycle view: PENDING → RUNNING → COMPLETED/FAILED/CANCELLED
 * Features: list, filter by status/type/system, cancel, retry, progress bars
 */
import { useState, useEffect, useCallback } from 'react'
import { integrationsApi, extractError } from '../../../services/api'
import { useToast } from '../../../context/ToastContext'
import { C } from '../constants'
import {
  Card, Btn, IconBtn, StatusBadge, Table, THead, Th, Td, TRow,
  Empty, Skeleton, Select, Pagination, ProgressBar, reltime,
} from '../shared'

const JOB_TYPES = ['IMPORT','EXPORT','SYNC','WEBHOOK','VALIDATION','MIGRATION']
const STATUSES  = ['PENDING','QUEUED','RUNNING','PAUSED','COMPLETED','FAILED','CANCELLED','RETRYING']

export default function JobsTab() {
  const [jobs, setJobs]         = useState([])
  const [loading, setLoading]   = useState(true)
  const [page, setPage]         = useState(1)
  const [total, setTotal]       = useState(0)
  const [filter, setFilter]     = useState({ status:'', job_type:'', search:'' })
  const [actioning, setActioning] = useState({})
  const [errorLog, setErrorLog] = useState(null)  // { jobId, log } — shown in inline panel
  const { success, error: toastErr } = useToast()
  const PAGE_SIZE = 15

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE }
      if (filter.status)   params.status   = filter.status
      if (filter.job_type) params.job_type = filter.job_type
      if (filter.search)   params.search   = filter.search
      const res = await integrationsApi.listJobs(params)
      setJobs(res.data.results || res.data)
      setTotal(res.data.count || 0)
    } catch (e) { toastErr(extractError(e)) }
    finally { setLoading(false) }
  }, [page, filter])

  useEffect(() => { load() }, [load])

  // Auto-refresh running jobs
  useEffect(() => {
    const hasRunning = jobs.some(j => ['RUNNING','QUEUED','RETRYING'].includes(j.status))
    if (!hasRunning) return
    const id = setInterval(() => load(), 5000)
    return () => clearInterval(id)
  }, [jobs, load])

  const cancel = async (job) => {
    setActioning(p=>({...p,[job.id]:'cancel'}))
    try {
      await integrationsApi.cancelJob(job.id)
      success(`Job ${job.job_id} cancelled.`)
      load()
    } catch(e) { toastErr(extractError(e)) }
    finally { setActioning(p=>({...p,[job.id]:null})) }
  }

  const retry = async (job) => {
    setActioning(p=>({...p,[job.id]:'retry'}))
    try {
      await integrationsApi.retryJob(job.id)
      success(`Job ${job.job_id} queued for retry.`)
      load()
    } catch(e) { toastErr(extractError(e)) }
    finally { setActioning(p=>({...p,[job.id]:null})) }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const runningCount = jobs.filter(j => j.status==='RUNNING').length

  return (
    <div>
      {/* Filters */}
      <div style={{ display:'flex', gap:8, marginBottom:16, flexWrap:'wrap', alignItems:'center' }}>
        <input
          value={filter.search}
          onChange={e => { setFilter(p=>({...p,search:e.target.value})); setPage(1) }}
          placeholder="Search jobs…"
          style={inputStyle}
        />
        <Select value={filter.status} onChange={e=>{ setFilter(p=>({...p,status:e.target.value})); setPage(1) }} style={{minWidth:130}}>
          <option value="">All statuses</option>
          {STATUSES.map(s=><option key={s} value={s}>{s}</option>)}
        </Select>
        <Select value={filter.job_type} onChange={e=>{ setFilter(p=>({...p,job_type:e.target.value})); setPage(1) }} style={{minWidth:130}}>
          <option value="">All types</option>
          {JOB_TYPES.map(t=><option key={t} value={t}>{t}</option>)}
        </Select>
        {runningCount > 0 && (
          <span style={{ fontFamily:C.mono, fontSize:9, color:C.accent, background:C.accentBg, padding:'3px 9px', borderRadius:10 }}>
            {runningCount} RUNNING
          </span>
        )}
        <div style={{flex:1}}/>
        <Btn variant="ghost" onClick={load} size="sm">↻ Refresh</Btn>
      </div>

      <Card>
        {loading ? <div style={{padding:16}}><Skeleton rows={8} /></div> : (
          <>
            <Table>
              <THead>
                <Th>Job ID</Th>
                <Th>System</Th>
                <Th>Type</Th>
                <Th>Entity</Th>
                <Th>Status</Th>
                <Th>Progress</Th>
                <Th>Records</Th>
                <Th>Started</Th>
                <Th>Actions</Th>
              </THead>
              <tbody>
                {jobs.length === 0 ? (
                  <tr><td colSpan={9}><Empty message="No jobs found" /></td></tr>
                ) : jobs.map(job => (
                  <TRow key={job.id}>
                    <Td style={{ fontFamily:C.mono, fontSize:10, color:C.text }}>{job.job_id}</Td>
                    <Td style={{ fontSize:11 }}>{job.external_system_detail?.name || '—'}</Td>
                    <Td>
                      <span style={{ fontFamily:C.mono, fontSize:9, color:C.textSub, background:'rgba(255,255,255,0.05)', padding:'2px 7px', borderRadius:4 }}>
                        {job.job_type}
                      </span>
                    </Td>
                    <Td style={{ fontSize:11 }}>{job.entity_type}</Td>
                    <Td><StatusBadge status={job.status} /></Td>
                    <Td style={{ minWidth:100 }}>
                      <div style={{ display:'flex', flexDirection:'column', gap:3 }}>
                        <ProgressBar pct={job.progress_percent} />
                        <span style={{ fontFamily:C.mono, fontSize:9, color:C.textMuted }}>{job.progress_percent||0}%</span>
                      </div>
                    </Td>
                    <Td style={{ fontFamily:C.mono, fontSize:10 }}>
                      <span style={{ color:C.success }}>{job.successful_records||0}</span>
                      {' / '}
                      <span style={{ color:job.failed_records>0?C.danger:C.textMuted }}>{job.total_records||0}</span>
                    </Td>
                    <Td style={{ fontFamily:C.mono, fontSize:10 }}>{reltime(job.started_at)}</Td>
                    <Td>
                      <div style={{ display:'flex', gap:4 }}>
                        {['RUNNING','QUEUED','PENDING'].includes(job.status) && (
                          <Btn size="sm" variant="warning" onClick={() => cancel(job)} disabled={actioning[job.id]==='cancel'}>
                            {actioning[job.id]==='cancel' ? '…' : 'Cancel'}
                          </Btn>
                        )}
                        {['FAILED','CANCELLED'].includes(job.status) && (
                          <Btn size="sm" variant="ghost" onClick={() => retry(job)} disabled={actioning[job.id]==='retry'}>
                            {actioning[job.id]==='retry' ? '…' : '↩ Retry'}
                          </Btn>
                        )}
                        {job.error_log && (
                          <Btn size="sm" variant="ghost" onClick={() =>
                            setErrorLog({ jobId: job.id, log: typeof job.error_log === 'object'
                              ? JSON.stringify(job.error_log, null, 2)
                              : job.error_log
                            })
                          }>Errors</Btn>
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

      {/* Inline error log panel — replaces native alert() */}
      {errorLog && (
        <div style={{
          position:'fixed', inset:0, background:'rgba(0,0,0,0.6)',
          display:'flex', alignItems:'center', justifyContent:'center', zIndex:1000,
        }} onClick={() => setErrorLog(null)}>
          <div style={{
            background:C.surface, border:`1px solid ${C.border}`, borderRadius:8,
            padding:24, maxWidth:640, width:'90%', maxHeight:'70vh',
            display:'flex', flexDirection:'column', gap:12,
          }} onClick={e => e.stopPropagation()}>
            <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
              <span style={{fontFamily:C.mono, fontSize:11, color:C.danger, letterSpacing:'0.1em', textTransform:'uppercase'}}>
                Job Error Log
              </span>
              <Btn size="sm" variant="ghost" onClick={() => setErrorLog(null)}>✕ Close</Btn>
            </div>
            <pre style={{
              fontFamily:C.mono, fontSize:11, color:C.textSub,
              background:'rgba(0,0,0,0.3)', borderRadius:4, padding:12,
              overflowY:'auto', whiteSpace:'pre-wrap', wordBreak:'break-all',
              flex:1, margin:0,
            }}>
              {errorLog.log}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}

const inputStyle = { fontFamily:C.sans,fontSize:12,color:C.text,background:'rgba(255,255,255,0.04)',border:`1px solid ${C.border}`,borderRadius:5,padding:'7px 10px',outline:'none',minWidth:180 }