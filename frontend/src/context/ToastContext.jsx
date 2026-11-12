import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const ToastContext = createContext(null)

const VARIANTS = {
  success: { bg: 'rgba(16,185,129,0.12)', border: '#10b981', icon: '✓' },
  error:   { bg: 'rgba(239, 68, 68,0.12)',  border: '#ef4444', icon: '✕' },
  warning: { bg: 'rgba(245,158,11,0.12)',  border: '#f59e0b', icon: '⚠' },
  info:    { bg: 'rgba(59,130,246,0.12)',  border: '#3b82f6', icon: 'ℹ' },
}

let toastId = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toast = useCallback((message, type = 'info', duration = 4000) => {
    const id = ++toastId
    setToasts((prev) => [...prev.slice(-4), { id, message, type, duration }])
    return id
  }, [])

  const success = useCallback((msg, dur) => toast(msg, 'success', dur), [toast])
  const error   = useCallback((msg, dur) => toast(msg, 'error',   dur), [toast])
  const warning = useCallback((msg, dur) => toast(msg, 'warning', dur), [toast])
  const info    = useCallback((msg, dur) => toast(msg, 'info',    dur), [toast])

  return (
    <ToastContext.Provider value={{ toast, success, error, warning, info, dismiss }}>
      {children}
      {/* Toast renderer */}
      <div style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        pointerEvents: 'none',
      }}>
        <AnimatePresence mode="popLayout">
          {toasts.map((t) => (
            <ToastItem key={t.id} toast={t} dismiss={dismiss} />
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}

function ToastItem({ toast: t, dismiss }) {
  const v = VARIANTS[t.type] || VARIANTS.info
  const timerRef = useRef(null)

  useEffect(() => {
    timerRef.current = setTimeout(() => dismiss(t.id), t.duration)
    return () => clearTimeout(timerRef.current)
  }, [t.id, t.duration, dismiss])

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 60, scale: 0.94 }}
      animate={{ opacity: 1, x: 0,  scale: 1 }}
      exit={{    opacity: 0, x: 60, scale: 0.94 }}
      transition={{ duration: 0.22, ease: 'easeOut' }}
      style={{
        pointerEvents: 'all',
        background: v.bg,
        border: `1px solid ${v.border}`,
        borderLeft: `3px solid ${v.border}`,
        borderRadius: 4,
        padding: '12px 16px',
        minWidth: 280,
        maxWidth: 380,
        display: 'flex',
        alignItems: 'flex-start',
        gap: 12,
        backdropFilter: 'blur(8px)',
        cursor: 'pointer',
      }}
      onClick={() => dismiss(t.id)}
    >
      <span style={{
        fontFamily: 'Space Mono, monospace',
        fontSize: 12,
        color: v.border,
        flexShrink: 0,
        marginTop: 1,
        fontWeight: 700,
      }}>
        {v.icon}
      </span>
      <span style={{
        fontFamily: 'IBM Plex Sans, sans-serif',
        fontSize: 13,
        color: '#f9fafb',
        lineHeight: 1.5,
        fontWeight: 400,
      }}>
        {t.message}
      </span>
    </motion.div>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}