import { startTransition, useCallback, useEffect, useRef, useState } from 'react'
import { buildFilterSearchParams, type EntryFilters, type RealtimeEnvelope, type WorkspaceSnapshot } from '../../../entities/dashboard/api'
import {
  isDashboardEnvelope,
  isEntryCreatedEnvelope,
  preferIncomingSnapshot,
  withRealtimeEntry,
} from '../../../entities/dashboard/lib/realtime'
import { useReconnectSession } from '../../reconnect-session/model/useReconnectSession'

type Params = {
  backend: string
  filters: EntryFilters
  initialWorkspace?: WorkspaceSnapshot | null
  isPaused?: boolean
  enabled?: boolean
  mode?: 'mixed' | 'snapshot-only'
}

export function useRealtimeDashboard({ backend, filters, initialWorkspace, isPaused = false, enabled = true, mode = 'mixed' }: Params) {
  const [liveWorkspace, setLiveWorkspace] = useState<WorkspaceSnapshot | null>(initialWorkspace ?? null)
  const [socketStatus, setSocketStatus] = useState<'idle' | 'connecting' | 'open' | 'closed' | 'error'>('idle')
  const [bufferedEventCount, setBufferedEventCount] = useState(0)
  const seedWorkspaceRef = useRef<WorkspaceSnapshot | null>(initialWorkspace ?? null)
  const websocketRef = useRef<WebSocket | null>(null)
  const cancelledRef = useRef(false)
  const pausedRef = useRef(isPaused)
  const bufferedMessagesRef = useRef<Array<RealtimeEnvelope | WorkspaceSnapshot>>([])
  const connectionSerialRef = useRef(0)
  const filterQuery = buildFilterSearchParams(filters).toString()

  const { scheduleReconnect, clearReconnect } = useReconnectSession({ delayMs: 1500 })

  const applyEnvelope = useCallback((current: WorkspaceSnapshot | null, parsed: RealtimeEnvelope | WorkspaceSnapshot) => {
    if (isEntryCreatedEnvelope(parsed)) {
      if (mode === 'snapshot-only') {
        return current ?? seedWorkspaceRef.current
      }
      return withRealtimeEntry(current ?? seedWorkspaceRef.current, parsed.payload, parsed.backend, parsed.ts)
    }
    if (isDashboardEnvelope(parsed)) {
      return preferIncomingSnapshot(current, { ...parsed.payload, backend: parsed.backend })
    }
    if ('event_type' in parsed) {
      return current
    }
    return parsed
  }, [mode])

  const flushBufferedMessages = useCallback(() => {
    if (bufferedMessagesRef.current.length === 0) {
      return
    }
    const buffered = bufferedMessagesRef.current
    bufferedMessagesRef.current = []
    setBufferedEventCount(0)
    startTransition(() => {
      setLiveWorkspace((current) => buffered.reduce((workspace, parsed) => applyEnvelope(workspace, parsed), current ?? seedWorkspaceRef.current))
    })
  }, [applyEnvelope])

  useEffect(() => {
    bufferedMessagesRef.current = []
    setBufferedEventCount(0)
    pausedRef.current = isPaused
    if (!isPaused) {
      flushBufferedMessages()
    }
  }, [flushBufferedMessages, isPaused])

  useEffect(() => {
    bufferedMessagesRef.current = []
    setBufferedEventCount(0)
    seedWorkspaceRef.current = initialWorkspace ?? null
    startTransition(() => {
      setLiveWorkspace(initialWorkspace ?? null)
    })
  }, [backend, filterQuery, initialWorkspace])

  useEffect(() => {
    if (enabled) {
      return
    }
    setSocketStatus('idle')
    websocketRef.current?.close()
    websocketRef.current = null
  }, [enabled])

  const connect = useCallback(() => {
    if (!enabled) {
      setSocketStatus('idle')
      return () => undefined
    }

    clearReconnect()
    websocketRef.current?.close()
    const connectionSerial = connectionSerialRef.current + 1
    connectionSerialRef.current = connectionSerial

    const search = new URLSearchParams(filterQuery)
    search.set('backend', backend)
    const ws = new WebSocket(`${window.location.origin.replace('http', 'ws')}/ws/dashboard?${search.toString()}`)
    websocketRef.current = ws
    setSocketStatus('connecting')

    ws.onopen = () => {
      if (connectionSerialRef.current !== connectionSerial) {
        return
      }
      setSocketStatus('open')
    }
    ws.onclose = () => {
      if (connectionSerialRef.current !== connectionSerial) {
        return
      }
      if (cancelledRef.current) {
        return
      }
      setSocketStatus('closed')
      scheduleReconnect(connect)
    }
    ws.onerror = () => {
      if (connectionSerialRef.current !== connectionSerial) {
        return
      }
      setSocketStatus('error')
      ws.close()
    }
    ws.onmessage = (event) => {
      if (connectionSerialRef.current !== connectionSerial) {
        return
      }
      const parsed = JSON.parse(event.data) as RealtimeEnvelope | WorkspaceSnapshot
      if (pausedRef.current) {
        bufferedMessagesRef.current.push(parsed)
        if (isEntryCreatedEnvelope(parsed)) {
          setBufferedEventCount((current) => current + 1)
        }
        return
      }
      startTransition(() => {
        setLiveWorkspace((current) => applyEnvelope(current ?? seedWorkspaceRef.current, parsed))
      })
    }
    return () => {
      if (connectionSerialRef.current === connectionSerial) {
        connectionSerialRef.current += 1
      }
      ws.close()
    }
  }, [applyEnvelope, backend, clearReconnect, enabled, filterQuery, scheduleReconnect])

  useEffect(() => {
    cancelledRef.current = false
    const cleanup = connect()

    return () => {
      cancelledRef.current = true
      clearReconnect()
      cleanup?.()
      websocketRef.current?.close()
      websocketRef.current = null
      bufferedMessagesRef.current = []
      setBufferedEventCount(0)
    }
  }, [clearReconnect, connect])

  return { liveWorkspace, socketStatus, bufferedEventCount }
}