import { useCallback, useEffect, useRef, useState } from 'react'
import type { RealtimeEnvelope, WorkspaceSnapshot } from '../../../entities/dashboard/api'
import {
  isDashboardEnvelope,
  isEntryCreatedEnvelope,
  withRealtimeEntry,
} from '../../../entities/dashboard/lib/realtime'
import { useReconnectSession } from '../../reconnect-session/model/useReconnectSession'

type Params = {
  backend: string
  initialWorkspace?: WorkspaceSnapshot | null
}

export function useRealtimeDashboard({ backend, initialWorkspace }: Params) {
  const [liveWorkspace, setLiveWorkspace] = useState<WorkspaceSnapshot | null>(initialWorkspace ?? null)
  const [socketStatus, setSocketStatus] = useState<'idle' | 'connecting' | 'open' | 'closed' | 'error'>('idle')
  const seedWorkspaceRef = useRef<WorkspaceSnapshot | null>(initialWorkspace ?? null)
  const websocketRef = useRef<WebSocket | null>(null)
  const cancelledRef = useRef(false)

  const { scheduleReconnect, clearReconnect } = useReconnectSession({ delayMs: 1500 })

  useEffect(() => {
    seedWorkspaceRef.current = initialWorkspace ?? null
    if (!liveWorkspace && initialWorkspace) {
      setLiveWorkspace(initialWorkspace)
    }
  }, [initialWorkspace, liveWorkspace])

  const connect = useCallback(() => {
    clearReconnect()
    websocketRef.current?.close()

    const ws = new WebSocket(`${window.location.origin.replace('http', 'ws')}/ws/dashboard?backend=${backend}`)
    websocketRef.current = ws
    setSocketStatus('connecting')

    ws.onopen = () => setSocketStatus('open')
    ws.onclose = () => {
      if (cancelledRef.current) {
        return
      }
      setSocketStatus('closed')
      scheduleReconnect(connect)
    }
    ws.onerror = () => {
      setSocketStatus('error')
      ws.close()
    }
    ws.onmessage = (event) => {
      const parsed = JSON.parse(event.data) as RealtimeEnvelope | WorkspaceSnapshot
      if (isEntryCreatedEnvelope(parsed)) {
        setLiveWorkspace((current) => withRealtimeEntry(current ?? seedWorkspaceRef.current, parsed.payload, parsed.backend, parsed.ts))
        return
      }
      if (isDashboardEnvelope(parsed)) {
        setLiveWorkspace({ ...parsed.payload, backend: parsed.backend })
        return
      }
      if ('event_type' in parsed) {
        return
      }
      setLiveWorkspace(parsed)
    }
  }, [backend, clearReconnect, scheduleReconnect])

  useEffect(() => {
    cancelledRef.current = false
    connect()

    return () => {
      cancelledRef.current = true
      clearReconnect()
      websocketRef.current?.close()
      websocketRef.current = null
    }
  }, [clearReconnect, connect])

  return { liveWorkspace, socketStatus }
}