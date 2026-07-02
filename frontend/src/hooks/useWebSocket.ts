import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useStrategyStore } from '../store/strategyStore'
import type { WSMessage } from '../types'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'

export function useWebSocket() {
  const ws = useRef<WebSocket | null>(null)
  const { handleWSMessage, setWsConnected } = useStrategyStore()
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()
  const qc = useQueryClient()

  const connect = () => {
    if (ws.current?.readyState === WebSocket.OPEN) return
    const token = localStorage.getItem('pyramid_token')
    if (!token) {
      console.warn('WS connection aborted: No token found in localStorage')
      return
    }
    const wsUrl = `${WS_URL}?token=${encodeURIComponent(token)}`
    ws.current = new WebSocket(wsUrl)

    ws.current.onopen = () => {
      setWsConnected(true)
      // Keep-alive ping every 30s
      const ping = setInterval(() => {
        ws.current?.send(JSON.stringify({ command: 'ping' }))
      }, 30_000)
      ws.current!.onclose = () => clearInterval(ping)
    }

    ws.current.onmessage = (ev) => {
      try {
        const msg: WSMessage = JSON.parse(ev.data)
        handleWSMessage(msg)
        if (msg.type === 'trade_event') {
          qc.invalidateQueries({ queryKey: ['trades-today'] })
          qc.invalidateQueries({ queryKey: ['pnl-today'] })
          qc.invalidateQueries({ queryKey: ['trades-log-data'] })
        }
      } catch (e) {
        console.error('WS parse error', e)
      }
    }

    ws.current.onerror = () => {
      setWsConnected(false)
    }

    ws.current.onclose = (event) => {
      setWsConnected(false)
      // Do not attempt to reconnect if authentication failed on backend
      if (event.code === 4001 || event.code === 4002) {
        console.warn(`WebSocket authentication failed (code ${event.code}). Reconnection aborted.`)
        return
      }
      // Reconnect after 3 seconds
      reconnectTimer.current = setTimeout(connect, 3000)
    }
  }

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [])
}
