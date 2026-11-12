/**
 * AnalyticsReports — OryxShield
 * ========================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Dedicated Reports sub-page under /dashboard/analytics/reports.
 * Manages StatisticalReports and ReportTemplates.
 *
 * API (analyticsApi):
 *   GET  /analytics/reports/           listStatisticalReports(params)
 *   GET  /analytics/reports/published/ publishedReports(params)
 *   GET  /analytics/reports/{id}/download/  downloadStatReport(id)  → blob
 *   POST /analytics/templates/{id}/generate/ generateFromTemplate(id)
 *   GET  /analytics/templates/         listReportTemplates(params)
 */

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { format, formatDistanceToNow } from 'date-fns'
import { analyticsApi, extractError } from '../../services/api'
import { useToast } from '../../context/ToastContext'

const C = {
  bg:          '#0a0f1e',
  surface:     '#111827',
  surfaceHigh: '#151e2e',
  border:      '#1f2937',
  accent:      '#3b82f6',
  accentBg:    'rgba(59,130,246,0.08)',
  danger:      '#ef4444',
  warning:     '#f59e0b',
  success:     '#10b981',
  text:        '#f9fafb',
  textSub:     '#9ca3af',
  textMuted:   '#6b7280',
}

const PAGE_SIZE = 25

const REPORT_TYPE_COLOR = {
  WHO_SITREP:  '#a78bfa',
  IHR:         C.accent,
  CUSTOM:      C.success,
  WEEKLY:      C.warning,
  MONTHLY:     '#f97316',
  OUTBREAK:    C.danger,
}

function ReportCard({ report, onDownload, downloading }) {
  const [hovered, setHovered] = useState(false)
  const color = REPORT_TYPE_COLOR[report.report_type] || C.textSub

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background:   hovered ? C.surfaceHigh : C.surface,
        border:       `1px solid ${C.border}`,
        borderLeft:   `3px solid ${report.is_published ? C.success : C.border}`,
        borderRadius: 8,
        padding:      '14px 18px',
        display:      'flex',
        alignItems:   'center',
        gap:          14,
        transition:   'background 0.15s',
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, color: C.text, fontSize: 14 }}>{report.title}</span>
          <span style={{
            padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 700,
            background: `${color}18`, color, border: `1px solid ${color}40`,
          }}>{report.report_type}</span>
          {report.is_published && (
            <span style={{
              padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 700,
              background: 'rgba(16,185,129,0.12)', color: C.success, border: `1px solid rgba(16,185,129,0.3)`,
            }}>PUBLISHED</span>
          )}
        </div>
        <div style={{ marginTop: 5, fontSize: 12, color: C.textMuted, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <span>By {report.author_username || '—'}</span>
          {report.start_date && <span>{report.start_date} → {report.end_date}</span>}
          <span>{formatDistanceToNow(new Date(report.created_at), { addSuffix: true })}</span>
        </div>
      </div>

      <div style={{ opacity: hovered ? 1 : 0.4, transition: 'opacity 0.15s', flexShrink: 0 }}>
        <button
          onClick={() => onDownload(report.id, report.title)}
          disabled={!!downloading}
          style={{
            padding: '5px 14px', borderRadius: 8,
            border: `1px solid ${C.accent}`, background: C.accentBg,
            color: C.accent, fontSize: 12,
            cursor: downloading ? 'not-allowed' : 'pointer',
            opacity: downloading === report.id ? 0.5 : 1,
          }}
        >
          {downloading === report.id ? 'Downloading…' : 'Download'}
        </button>
      </div>
    </motion.div>
  )
}

function TemplateCard({ tmpl, onGenerate, generating }) {
  const [hovered, setHovered] = useState(false)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background:   hovered ? C.surfaceHigh : C.surface,
        border:       `1px solid ${C.border}`,
        borderLeft:   `3px solid ${tmpl.is_active ? C.accent : C.border}`,
        borderRadius: 8,
        padding:      '14px 18px',
        display:      'flex',
        alignItems:   'center',
        gap:          14,
        transition:   'background 0.15s',
      }}
    >
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, color: C.text, fontSize: 14 }}>{tmpl.name}</div>
        <div style={{ marginTop: 5, fontSize: 12, color: C.textMuted, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <span>{tmpl.template_type_display || tmpl.template_type}</span>
          <span>·</span>
          <span>{tmpl.output_format_display || tmpl.output_format}</span>
          {!tmpl.is_active && <span style={{ color: C.danger }}>INACTIVE</span>}
        </div>
      </div>
      {tmpl.is_active && (
        <button
          onClick={() => onGenerate(tmpl.id)}
          disabled={generating === tmpl.id}
          style={{
            padding: '5px 14px', borderRadius: 8, flexShrink: 0,
            border: `1px solid ${C.success}`, background: 'rgba(16,185,129,0.08)',
            color: C.success, fontSize: 12,
            cursor: generating === tmpl.id ? 'not-allowed' : 'pointer',
            opacity: generating === tmpl.id ? 0.5 : 1,
          }}
        >
          {generating === tmpl.id ? 'Generating…' : 'Generate'}
        </button>
      )}
    </motion.div>
  )
}

export default function AnalyticsReports() {
  const { success: toastSuccess, error: toastError } = useToast()

  const [tab, setTab]           = useState('reports')
  const [reports, setReports]   = useState([])
  const [templates, setTemplates] = useState([])
  const [loading, setLoading]   = useState(true)
  const [page, setPage]         = useState(1)
  const [total, setTotal]       = useState(0)
  const [publishedOnly, setPublishedOnly] = useState(false)
  const [downloading, setDownloading] = useState(null)
  const [generating, setGenerating] = useState(null)

  const loadReports = useCallback(async () => {
    setLoading(true)
    try {
      const res = publishedOnly
        ? await analyticsApi.publishedReports({ page, page_size: PAGE_SIZE })
        : await analyticsApi.listStatisticalReports({ page, page_size: PAGE_SIZE })
      const data = res.data
      setReports(data.results || (Array.isArray(data) ? data : []))
      setTotal(data.count || (Array.isArray(data) ? data.length : 0))
    } catch (e) {
      toastError(extractError(e))
    } finally {
      setLoading(false)
    }
  }, [page, publishedOnly, toastError])

  const loadTemplates = useCallback(async () => {
    setLoading(true)
    try {
      const res = await analyticsApi.listReportTemplates({ page_size: 100 })
      const data = res.data
      setTemplates(data.results || (Array.isArray(data) ? data : []))
    } catch (e) {
      toastError(extractError(e))
    } finally {
      setLoading(false)
    }
  }, [toastError])

  useEffect(() => {
    if (tab === 'reports')   loadReports()
    if (tab === 'templates') loadTemplates()
  }, [tab, loadReports, loadTemplates])

  const handleDownload = async (id, title) => {
    setDownloading(id)
    try {
      const res = await analyticsApi.downloadStatReport(id)
      // Derive filename from Content-Disposition header, fall back to title.json
      const disposition = res.headers?.['content-disposition'] || ''
      const match = disposition.match(/filename="?([^";\n]+)"?/)
      const filename = match?.[1] || `${title.replace(/\s+/g, '_')}.pdf`
      const url = URL.createObjectURL(new Blob([res.data], { type: res.headers?.['content-type'] || 'application/octet-stream' }))
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      toastError(extractError(e))
    } finally {
      setDownloading(null)
    }
  }

  const handleGenerate = async (id) => {
    setGenerating(id)
    try {
      const res = await analyticsApi.generateFromTemplate(id)
      const title = res.data?.title || 'Report'
      toastSuccess(`"${title}" created — switching to Reports tab.`)
      // Switch to reports tab and reload so the new report appears
      setTab('reports')
      setPage(1)
      setPublishedOnly(false)
      await loadReports()
    } catch (e) {
      toastError(extractError(e))
    } finally {
      setGenerating(null)
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const TabBtn = ({ id, label }) => (
    <button
      onClick={() => { setTab(id); setPage(1) }}
      style={{
        padding: '8px 18px', borderRadius: 8, fontSize: 13,
        border: `1px solid ${tab === id ? C.accent : C.border}`,
        background: tab === id ? C.accentBg : 'transparent',
        color: tab === id ? C.accent : C.textSub,
        cursor: 'pointer',
      }}
    >{label}</button>
  )

  return (
    <div style={{ minHeight: '100vh', background: C.bg, padding: '24px 20px' }}>
      <div style={{ maxWidth: 900, margin: '0 auto' }}>

        {/* ── Header ────────────────────────────────────────────────────────── */}
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: C.text }}>Reports</h1>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: C.textSub }}>
            Statistical reports, WHO SitReps, IHR submissions, and report templates
          </p>
        </div>

        {/* ── Tabs ──────────────────────────────────────────────────────────── */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
          <TabBtn id="reports"   label="Statistical Reports" />
          <TabBtn id="templates" label="Report Templates" />
        </div>

        {/* ── Reports tab ───────────────────────────────────────────────────── */}
        {tab === 'reports' && (
          <>
            <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
              <button
                onClick={() => { setPublishedOnly(v => !v); setPage(1) }}
                style={{
                  padding: '7px 14px', borderRadius: 8,
                  border: `1px solid ${publishedOnly ? C.success : C.border}`,
                  background: publishedOnly ? 'rgba(16,185,129,0.08)' : 'transparent',
                  color: publishedOnly ? C.success : C.textSub,
                  fontSize: 13, cursor: 'pointer',
                }}
              >{publishedOnly ? 'All Reports' : 'Published Only'}</button>
              <span style={{ fontSize: 13, color: C.textMuted }}>{total} reports</span>
            </div>

            {loading ? (
              <p style={{ color: C.textMuted, textAlign: 'center', padding: 40 }}>Loading reports…</p>
            ) : reports.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 60, background: C.surface, borderRadius: 12, border: `1px solid ${C.border}` }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>📋</div>
                <p style={{ color: C.textSub, margin: 0 }}>No reports found.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <AnimatePresence>
                  {reports.map(r => (
                    <ReportCard key={r.id} report={r} onDownload={handleDownload} downloading={downloading} />
                  ))}
                </AnimatePresence>
              </div>
            )}

            {totalPages > 1 && (
              <div style={{ display: 'flex', justifyContent: 'center', gap: 10, marginTop: 20 }}>
                <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
                  style={{ padding: '6px 16px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: page <= 1 ? C.textMuted : C.text, cursor: page <= 1 ? 'default' : 'pointer', fontSize: 13 }}>Prev</button>
                <span style={{ padding: '6px 12px', color: C.textSub, fontSize: 13 }}>{page} / {totalPages}</span>
                <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
                  style={{ padding: '6px 16px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: page >= totalPages ? C.textMuted : C.text, cursor: page >= totalPages ? 'default' : 'pointer', fontSize: 13 }}>Next</button>
              </div>
            )}
          </>
        )}

        {/* ── Templates tab ─────────────────────────────────────────────────── */}
        {tab === 'templates' && (
          <>
            {loading ? (
              <p style={{ color: C.textMuted, textAlign: 'center', padding: 40 }}>Loading templates…</p>
            ) : templates.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 60, background: C.surface, borderRadius: 12, border: `1px solid ${C.border}` }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>📄</div>
                <p style={{ color: C.textSub, margin: 0 }}>No report templates configured.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <AnimatePresence>
                  {templates.map(t => (
                    <TemplateCard key={t.id} tmpl={t} onGenerate={handleGenerate} generating={generating} />
                  ))}
                </AnimatePresence>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
