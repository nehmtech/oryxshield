import { useState, useEffect, useRef } from 'react'
import { tokenStorage } from '../../services/api'

export function useResponseStream() {
  const [data,   setData]   = useState([])
  const [status, setStatus] = useState('connecting')
  const wsRef      = useRef(null)
  const retryRef   = useRef(null)
  const retries    = useRef(0)
  const mountedRef = useRef(true)

  const connect = () => {
    if (!mountedRef.current) return
    const token = tokenStorage.getAccess()
    const base  = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'
    const url   = `${base}/response/`
    const ws    = token ? new WebSocket(url, ['bearer', token]) : new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) { ws.close(1000, 'unmounted'); return }
      setStatus('open')
      retries.current = 0
    }
    ws.onmessage = (e) => {
      if (!mountedRef.current) return
      try {
        const msg = JSON.parse(e.data)
        setData((prev) => {
          const idx = prev.findIndex((r) => r.id === msg.id)
          if (idx >= 0) {
            const next = [...prev]
            next[idx] = { ...next[idx], ...msg }
            return next
          }
          return [msg, ...prev].slice(0, 100)
        })
      } catch (_) {}
    }
    ws.onerror = () => {
      if (mountedRef.current) setStatus('error')
    }
    ws.onclose = () => {
      if (!mountedRef.current) return
      setStatus('closed')
      const delay = Math.min(1000 * 2 ** retries.current, 30000)
      retries.current++
      retryRef.current = setTimeout(connect, delay)
    }
  }

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      clearTimeout(retryRef.current)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close(1000, 'component unmounted')
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return { data, status }
}
