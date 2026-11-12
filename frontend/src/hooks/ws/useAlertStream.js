import { useState, useEffect, useRef } from 'react'
import { tokenStorage } from '../../services/api'
import { useUI } from '../../context/UIContext'

export function useAlertStream() {
  const [data,   setData]   = useState([])
  const [status, setStatus] = useState('connecting')
  const { setWsStatus } = useUI()
  const wsRef     = useRef(null)
  const retryRef  = useRef(null)
  const retries   = useRef(0)
  const mountedRef = useRef(true)

  const connect = () => {
    if (!mountedRef.current) return
    const token = tokenStorage.getAccess()
    const base  = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'
    // Token passed as query param — Django Channels JWTAuthMiddleware reads ?token=
    // The subprotocol approach requires consumers to echo back the selected protocol
    // during accept(), which is not wired up in all consumers. Query param is reliable.
    const url = token ? `${base}/alerts/?token=${token}` : `${base}/alerts/`
    const ws  = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) { ws.close(1000, 'unmounted'); return }
      setStatus('open')
      setWsStatus('open')
      retries.current = 0
    }
    ws.onmessage = (e) => {
      if (!mountedRef.current) return
      try {
        const msg = JSON.parse(e.data)
        setData((prev) => [msg, ...prev].slice(0, 200))
      } catch (_) {}
    }
    ws.onerror = () => {
      if (mountedRef.current) { setStatus('error'); setWsStatus('error') }
    }
    ws.onclose = () => {
      if (!mountedRef.current) return
      setStatus('closed')
      setWsStatus('closed')
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
        wsRef.current.onclose = null  // prevent retry scheduling on intentional close
        wsRef.current.close(1000, 'component unmounted')
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return { data, status }
}
