/**
 * Integrations — shared UI atoms
 * Imports tokens from ./constants.js (no circular dependency).
 */
import { useState } from 'react'
import { C, HEALTH_COLOR, STATUS_COLOR, LOG_COLOR } from './constants'

export function Card({ children, style }) {
  return (
    <div style={{ background:C.bgCard, border:`1px solid ${C.border}`, borderRadius:8, ...style }}>
      {children}
    </div>
  )
}

export function SectionHead({ label, action }) {
  return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:14 }}>
      <span style={{ fontFamily:C.mono, fontSize:9, color:C.accent, letterSpacing:'0.18em', textTransform:'uppercase' }}>
        {label}
      </span>
      {action}
    </div>
  )
}

export function Btn({ children, onClick, variant='primary', size='md', disabled=false, style:extraStyle={} }) {
  const sizes = { sm:{fontSize:11,padding:'5px 10px'}, md:{fontSize:12,padding:'7px 14px'}, lg:{fontSize:13,padding:'9px 18px'} }
  const variants = {
    primary: { background:C.accent, color:'#fff' },
    danger:  { background:C.danger, color:'#fff' },
    ghost:   { background:'rgba(255,255,255,0.05)', color:C.textSub, border:`1px solid ${C.border}` },
    success: { background:C.success, color:'#fff' },
    warning: { background:C.warning, color:'#0a0f1e' },
  }
  return (
    <button onClick={disabled?undefined:onClick} style={{
      display:'inline-flex', alignItems:'center', gap:6, border:'none', borderRadius:5,
      cursor:disabled?'not-allowed':'pointer', fontFamily:C.sans, fontWeight:500,
      transition:'opacity 0.15s', opacity:disabled?0.45:1, whiteSpace:'nowrap',
      ...sizes[size], ...variants[variant], ...extraStyle,
    }}>
      {children}
    </button>
  )
}

export function IconBtn({ children, onClick, title, variant='ghost', disabled=false }) {
  const bg    = { ghost:'rgba(255,255,255,0.08)', danger:'rgba(239,68,68,0.12)', success:'rgba(16,185,129,0.12)', accent:'rgba(59,130,246,0.12)' }
  const color = { ghost:C.textSub, danger:C.danger, success:C.success, accent:C.accent }
  return (
    <button onClick={disabled?undefined:onClick} title={title} style={{
      width:33, height:33, display:'flex', alignItems:'center', justifyContent:'center',
      background:bg[variant]||bg.ghost, border:'none', borderRadius:5,
      cursor:disabled?'not-allowed':'pointer', opacity:disabled?0.4:1,
      color:color[variant]||color.ghost, flexShrink:0,
    }}>
      {children}
    </button>
  )
}

export function HealthBadge({ status }) {
  const col = HEALTH_COLOR[status] || C.textMuted
  return <span style={{ fontFamily:C.mono, fontSize:9, letterSpacing:'0.1em', color:col, background:`${col}18`, border:`1px solid ${col}33`, borderRadius:4, padding:'2px 7px', textTransform:'uppercase', whiteSpace:'nowrap' }}>{status||'UNKNOWN'}</span>
}

export function StatusBadge({ status }) {
  const col = STATUS_COLOR[status] || C.textMuted
  return <span style={{ fontFamily:C.mono, fontSize:9, letterSpacing:'0.1em', color:col, background:`${col}18`, border:`1px solid ${col}33`, borderRadius:4, padding:'2px 7px', textTransform:'uppercase', whiteSpace:'nowrap' }}>{status||'—'}</span>
}

export function LogLevelBadge({ level }) {
  const col = LOG_COLOR[level] || C.textMuted
  return <span style={{ fontFamily:C.mono, fontSize:9, letterSpacing:'0.1em', color:col, background:`${col}18`, border:`1px solid ${col}33`, borderRadius:4, padding:'2px 7px', textTransform:'uppercase', whiteSpace:'nowrap' }}>{level}</span>
}

export function Table({ children }) {
  return <div style={{ overflowX:'auto' }}><table style={{ width:'100%', borderCollapse:'collapse', fontFamily:C.sans, fontSize:12 }}>{children}</table></div>
}

export function THead({ children }) {
  return <thead><tr style={{ borderBottom:`1px solid ${C.border}` }}>{children}</tr></thead>
}

export function Th({ children, style }) {
  return <th style={{ fontFamily:C.mono, fontSize:9, color:C.textMuted, letterSpacing:'0.12em', textTransform:'uppercase', textAlign:'left', padding:'8px 12px', whiteSpace:'nowrap', fontWeight:400, ...style }}>{children}</th>
}

export function Td({ children, style }) {
  return <td style={{ padding:'10px 12px', color:C.textSub, verticalAlign:'middle', borderBottom:`1px solid ${C.borderSub}`, ...style }}>{children}</td>
}

export function TRow({ children, onClick }) {
  const [hover, setHover] = useState(false)
  return (
    <tr onClick={onClick} onMouseEnter={()=>setHover(true)} onMouseLeave={()=>setHover(false)}
      style={{ background:hover?'rgba(255,255,255,0.02)':'transparent', cursor:onClick?'pointer':'default' }}>
      {children}
    </tr>
  )
}

export function Empty({ message='No data.' }) {
  return <div style={{ textAlign:'center', padding:'40px 0', color:C.textMuted, fontFamily:C.mono, fontSize:11, letterSpacing:'0.12em' }}>{message.toUpperCase()}</div>
}

export function Skeleton({ rows=5 }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:8, padding:'8px 0' }}>
      <style>{`@keyframes ls-shimmer{0%{opacity:.04}50%{opacity:.09}100%{opacity:.04}}`}</style>
      {Array.from({length:rows}).map((_,i)=>(
        <div key={i} style={{ height:36, borderRadius:6, background:'rgba(255,255,255,0.06)', animation:`ls-shimmer 1.4s ease-in-out infinite`, animationDelay:`${i*0.1}s`, opacity:1-i*0.1 }} />
      ))}
    </div>
  )
}

export function Input({ value, onChange, placeholder, type='text', style:extra={} }) {
  return <input type={type} value={value} onChange={onChange} placeholder={placeholder} style={{ fontFamily:C.sans, fontSize:12, color:C.text, background:'rgba(255,255,255,0.04)', border:`1px solid ${C.border}`, borderRadius:5, padding:'7px 10px', outline:'none', width:'100%', boxSizing:'border-box', ...extra }} />
}

export function Select({ value, onChange, children, style:extra={} }) {
  return <select value={value} onChange={onChange} style={{ fontFamily:C.sans, fontSize:12, color:C.text, background:'#0d1425', border:`1px solid ${C.border}`, borderRadius:5, padding:'7px 10px', outline:'none', ...extra }}>{children}</select>
}

export function Field({ label, children, required, style:extra={} }) {
  return (
    <div style={{ marginBottom:14, ...extra }}>
      <label style={{ fontFamily:C.mono, fontSize:9, color:C.textMuted, letterSpacing:'0.12em', textTransform:'uppercase', display:'block', marginBottom:5 }}>
        {label}{required&&<span style={{color:C.danger}}> *</span>}
      </label>
      {children}
    </div>
  )
}

export function Modal({ open, onClose, title, children, width=540 }) {
  if (!open) return null
  return (
    <div onClick={onClose} style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.72)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:1000, padding:16 }}>
      <div onClick={e=>e.stopPropagation()} style={{ background:C.bgCard, border:`1px solid ${C.border}`, borderRadius:10, width:'100%', maxWidth:width, maxHeight:'90vh', overflow:'auto' }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'18px 20px', borderBottom:`1px solid ${C.border}` }}>
          <span style={{ fontFamily:C.display, fontSize:18, color:C.text, letterSpacing:'0.04em' }}>{title}</span>
          <button onClick={onClose} style={{ background:'none', border:'none', color:C.textMuted, cursor:'pointer', fontSize:18 }}>✕</button>
        </div>
        <div style={{ padding:'20px' }}>{children}</div>
      </div>
    </div>
  )
}

export function Pagination({ page, totalPages, total, pageSize, onPage }) {
  if (totalPages <= 1) return null
  return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginTop:14, padding:'0 4px' }}>
      <span style={{ fontFamily:C.mono, fontSize:9, color:C.textMuted }}>
        SHOWING {Math.min((page-1)*pageSize+1,total)}–{Math.min(page*pageSize,total)} OF {total}
      </span>
      <div style={{ display:'flex', gap:4 }}>
        <Btn size="sm" variant="ghost" onClick={()=>onPage(page-1)} disabled={page<=1}>←</Btn>
        <Btn size="sm" variant="ghost" disabled>{page} / {totalPages}</Btn>
        <Btn size="sm" variant="ghost" onClick={()=>onPage(page+1)} disabled={page>=totalPages}>→</Btn>
      </div>
    </div>
  )
}

export function ProgressBar({ pct, color }) {
  const c = color || C.accent
  return (
    <div style={{ width:'100%', height:4, background:'rgba(255,255,255,0.07)', borderRadius:2, overflow:'hidden' }}>
      <div style={{ width:`${Math.min(100,pct||0)}%`, height:'100%', background:c, borderRadius:2, transition:'width 0.3s' }} />
    </div>
  )
}

export function reltime(ts) {
  if (!ts) return '—'
  const diff = (Date.now()-new Date(ts))/1000
  if (diff<60)    return `${Math.round(diff)}s ago`
  if (diff<3600)  return `${Math.round(diff/60)}m ago`
  if (diff<86400) return `${Math.round(diff/3600)}h ago`
  return `${Math.round(diff/86400)}d ago`
}

export function fmtBytes(b) {
  if (!b) return '—'
  if (b<1024)    return `${b} B`
  if (b<1048576) return `${(b/1024).toFixed(1)} KB`
  return `${(b/1048576).toFixed(1)} MB`
}