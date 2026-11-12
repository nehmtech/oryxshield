/**
 * Notifications — OryxShield
 * =====================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Full notification centre: list, mark read, delete, bulk clear.
 *
 * API (all from coreApi — verified against core URLs):
 *   GET  /notifications/              listNotifications(params)
 *   GET  /notifications/unread/       unreadNotifications()
 *   GET  /notifications/unread_count/ unreadCount()
 *   POST /notifications/{id}/mark_read/  markNotifRead(id)
 *   POST /notifications/mark_all_read/   markAllNotifsRead()
 *   DELETE /notifications/{id}/      deleteNotification(id)
 */

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { formatDistanceToNow, format } from 'date-fns'
import { coreApi, extractError } from '../../services/api'
import { useToast } from '../../context/ToastContext'

// ─── Design tokens ─────────────────────────────────────────────────────────────
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

const PAGE_SIZE = 30

const NOTIF_ICON = {
  ALERT:    '🚨',
  WARNING:  '⚠️',
  INFO:     'ℹ️',
  SUCCESS:  '✅',
  SYSTEM:   '⚙️',
}

const PRIORITY_COLOR = {
  CRITICAL: C.danger,
  HIGH:     '#f97316',
  MEDIUM:   C.warning,
  LOW:      C.success,
  INFO:     C.accent,
}

function NotifCard({ notif, onMarkRead, onDelete }) {
  const [hovered, setHovered] = useState(false)
  const isUnread = !notif.is_read
  const icon = NOTIF_ICON[notif.notification_type] || NOTIF_ICON.INFO
  const priColor = PRIORITY_COLOR[notif.priority] || C.accent

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -20 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display:      'flex',
        alignItems:   'flex-start',
        gap:          14,
        padding:      '14px 18px',
        background:   hovered ? C.surfaceHigh : (isUnread ? 'rgba(59,130,246,0.04)' : C.surface),
        border:       `1px solid ${isUnread ? 'rgba(59,130,246,0.2)' : C.border}`,
        borderLeft:   `3px solid ${isUnread ? priColor : 'transparent'}`,
        borderRadius: 8,
        cursor:       'default',
        transition:   'background 0.15s',
        position:     'relative',
      }}
    >
      {/* Icon */}
      <div style={{ fontSize: 22, flexShrink: 0, lineHeight: 1.2, marginTop: 2 }}>{icon}</div>

      {/* Body */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontWeight: isUnread ? 600 : 400, color: C.text, fontSize: 14 }}>
            {notif.title}
          </span>
          {isUnread && (
            <span style={{
              background: priColor,
              color: '#fff',
              fontSize: 10,
              fontWeight: 700,
              padding: '1px 6px',
              borderRadius: 10,
              letterSpacing: '0.05em',
              flexShrink: 0,
            }}>NEW</span>
          )}
        </div>
        {notif.message && (
          <p style={{ margin: '4px 0 0', fontSize: 13, color: C.textSub, lineHeight: 1.5 }}>
            {notif.message}
          </p>
        )}
        <div style={{ marginTop: 6, fontSize: 11, color: C.textMuted }}>
          {formatDistanceToNow(new Date(notif.created_at), { addSuffix: true })}
          {' · '}
          {format(new Date(notif.created_at), 'dd MMM yyyy HH:mm')}
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 6, flexShrink: 0, opacity: hovered ? 1 : 0, transition: 'opacity 0.15s' }}>
        {isUnread && (
          <button
            onClick={() => onMarkRead(notif.id)}
            title="Mark as read"
            style={{
              background: C.accentBg,
              border:     `1px solid ${C.accent}`,
              borderRadius: 6,
              color:      C.accent,
              fontSize:   11,
              padding:    '3px 8px',
              cursor:     'pointer',
            }}
          >Read</button>
        )}
        <button
          onClick={() => onDelete(notif.id)}
          title="Delete"
          style={{
            background: 'rgba(239,68,68,0.08)',
            border:     '1px solid rgba(239,68,68,0.3)',
            borderRadius: 6,
            color:      C.danger,
            fontSize:   11,
            padding:    '3px 8px',
            cursor:     'pointer',
          }}
        >Delete</button>
      </div>
    </motion.div>
  )
}

export default function Notifications() {
  const { success: toastSuccess, error: toastError } = useToast()

  const [notifs, setNotifs]       = useState([])
  const [loading, setLoading]     = useState(true)
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [page, setPage]           = useState(1)
  const [total, setTotal]         = useState(0)
  const [unreadCount, setUnreadCount] = useState(0)
  const [acting, setActing]       = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE }
      const res = unreadOnly
        ? await coreApi.unreadNotifications()
        : await coreApi.listNotifications(params)
      const data = res.data
      setNotifs(Array.isArray(data) ? data : (data.results || []))
      setTotal(data.count ?? (Array.isArray(data) ? data.length : 0))
    } catch (e) {
      toastError(extractError(e))
    } finally {
      setLoading(false)
    }
  }, [page, unreadOnly, toastError])

  const loadCount = useCallback(async () => {
    try {
      const res = await coreApi.unreadCount()
      setUnreadCount(res.data.count ?? 0)
    } catch { /* silent */ }
  }, [])

  useEffect(() => { load(); loadCount() }, [load, loadCount])

  const handleMarkRead = async (id) => {
    try {
      await coreApi.markNotifRead(id)
      setNotifs(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n))
      setUnreadCount(c => Math.max(0, c - 1))
    } catch (e) {
      toastError(extractError(e))
    }
  }

  const handleDelete = async (id) => {
    try {
      await coreApi.deleteNotification(id)
      setNotifs(prev => prev.filter(n => n.id !== id))
      setTotal(c => Math.max(0, c - 1))
    } catch (e) {
      toastError(extractError(e))
    }
  }

  const handleMarkAllRead = async () => {
    setActing(true)
    try {
      await coreApi.markAllNotifsRead()
      setNotifs(prev => prev.map(n => ({ ...n, is_read: true })))
      setUnreadCount(0)
      toastSuccess('All notifications marked as read.')
    } catch (e) {
      toastError(extractError(e))
    } finally {
      setActing(false)
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div style={{ minHeight: '100vh', background: C.bg, padding: '24px 20px' }}>

      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div style={{ maxWidth: 800, margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: C.text }}>Notifications</h1>
            <p style={{ margin: '4px 0 0', fontSize: 13, color: C.textSub }}>
              {unreadCount > 0 ? `${unreadCount} unread` : 'All caught up'}
              {total > 0 && ` · ${total} total`}
            </p>
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {/* Toggle filter */}
            <button
              onClick={() => { setUnreadOnly(v => !v); setPage(1) }}
              style={{
                padding:      '7px 14px',
                borderRadius: 8,
                border:       `1px solid ${unreadOnly ? C.accent : C.border}`,
                background:   unreadOnly ? C.accentBg : 'transparent',
                color:        unreadOnly ? C.accent : C.textSub,
                fontSize:     13,
                cursor:       'pointer',
              }}
            >
              {unreadOnly ? 'Show All' : 'Unread Only'}
            </button>

            {/* Mark all read */}
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                disabled={acting}
                style={{
                  padding:      '7px 14px',
                  borderRadius: 8,
                  border:       `1px solid ${C.success}`,
                  background:   'rgba(16,185,129,0.08)',
                  color:        C.success,
                  fontSize:     13,
                  cursor:       acting ? 'not-allowed' : 'pointer',
                  opacity:      acting ? 0.6 : 1,
                }}
              >
                Mark All Read
              </button>
            )}

            {/* Refresh */}
            <button
              onClick={() => load()}
              style={{
                padding:      '7px 14px',
                borderRadius: 8,
                border:       `1px solid ${C.border}`,
                background:   'transparent',
                color:        C.textSub,
                fontSize:     13,
                cursor:       'pointer',
              }}
            >
              Refresh
            </button>
          </div>
        </div>

        {/* ── List ──────────────────────────────────────────────────────────── */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: 60, color: C.textMuted, fontSize: 14 }}>
            Loading notifications…
          </div>
        ) : notifs.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: 60,
            background: C.surface,
            borderRadius: 12,
            border: `1px solid ${C.border}`,
          }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>🔔</div>
            <p style={{ color: C.textSub, margin: 0 }}>
              {unreadOnly ? 'No unread notifications.' : 'No notifications yet.'}
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <AnimatePresence mode="popLayout">
              {notifs.map(n => (
                <NotifCard
                  key={n.id}
                  notif={n}
                  onMarkRead={handleMarkRead}
                  onDelete={handleDelete}
                />
              ))}
            </AnimatePresence>
          </div>
        )}

        {/* ── Pagination ────────────────────────────────────────────────────── */}
        {!unreadOnly && totalPages > 1 && (
          <div style={{ display: 'flex', justifyContent: 'center', gap: 10, marginTop: 24 }}>
            <button
              disabled={page <= 1}
              onClick={() => setPage(p => p - 1)}
              style={{
                padding: '6px 16px', borderRadius: 8,
                border: `1px solid ${C.border}`, background: 'transparent',
                color: page <= 1 ? C.textMuted : C.text,
                cursor: page <= 1 ? 'default' : 'pointer', fontSize: 13,
              }}
            >Prev</button>
            <span style={{ padding: '6px 12px', color: C.textSub, fontSize: 13, lineHeight: '24px' }}>
              {page} / {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage(p => p + 1)}
              style={{
                padding: '6px 16px', borderRadius: 8,
                border: `1px solid ${C.border}`, background: 'transparent',
                color: page >= totalPages ? C.textMuted : C.text,
                cursor: page >= totalPages ? 'default' : 'pointer', fontSize: 13,
              }}
            >Next</button>
          </div>
        )}
      </div>
    </div>
  )
}
