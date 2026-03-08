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
}

export function useRealtimeDashboard({ backend, filters, initialWorkspace, isPaused = false }: Params) {
  const [liveWorkspace, setLiveWorkspace] = useState<WorkspaceSnapshot | null>(initialWorkspace ?? null)
  const [socketStatus, setSocketStatus] = useState<'idle' | 'connecting' | 'open' | 'closed' | 'error'>('idle')
  const [bufferedEventCount, setBufferedEventCount] = useState(0)
  const seedWorkspaceRef = useRef<WorkspaceSnapshot | null>(initialWorkspace ?? null)
  const websocketRef = useRef<WebSocket | null>(null)
  const cancelledRef = useRef(false)
  const pausedRef = useRef(isPaused)
  const bufferedMessagesRef = useRef<Array<RealtimeEnvelope | WorkspaceSnapshot>>([])
  const keepaliveTimerRef = useRef<number | null>(null)
  const filterQuery = buildFilterSearchParams(filters).toString()

  const { scheduleReconnect, clearReconnect } = useReconnectSession({ delayMs: 1500 })

  const applyEnvelope = useCallback((current: WorkspaceSnapshot | null, parsed: RealtimeEnvelope | WorkspaceSnapshot) => {
    if (isEntryCreatedEnvelope(parsed)) {
      return withRealtimeEntry(current ?? seedWorkspaceRef.current, parsed.payload, parsed.backend, parsed.ts)
    }
    if (isDashboardEnvelope(parsed)) {
      return preferIncomingSnapshot(current, { ...parsed.payload, backend: parsed.backend })
    }
    if ('event_type' in parsed) {
      return current
    }
    return parsed
  }, [])

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
    pausedRef.current = isPaused
    if (!isPaused) {
      flushBufferedMessages()
    }
  }, [flushBufferedMessages, isPaused])

  useEffect(() => {
    seedWorkspaceRef.current = initialWorkspace ?? null
    if (!pausedRef.current) {
      startTransition(() => {
        setLiveWorkspace(initialWorkspace ?? null)
      })
    }
  }, [initialWorkspace])

  const connect = useCallback(() => {
    clearReconnect()
    if (keepaliveTimerRef.current !== null) {
      window.clearInterval(keepaliveTimerRef.current)
      keepaliveTimerRef.current = null
    }
    websocketRef.current?.close()

    const search = new URLSearchParams(filterQuery)
    search.set('backend', backend)
    const ws = new WebSocket(`${window.location.origin.replace('http', 'ws')}/ws/dashboard?${search.toString()}`)
    websocketRef.current = ws
    setSocketStatus('connecting')

    ws.onopen = () => {
      setSocketStatus('open')
      if (keepaliveTimerRef.current !== null) {
        window.clearInterval(keepaliveTimerRef.current)
      }
      keepaliveTimerRef.current = window.setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping')
        }
      }, 15000)
    }
    ws.onclose = () => {
      if (keepaliveTimerRef.current !== null) {
        window.clearInterval(keepaliveTimerRef.current)
        keepaliveTimerRef.current = null
      }
      if (cancelledRef.current) {
        return
      }
      setSocketStatus('closed')
      scheduleReconnect(connect)
    }
    ws.onerror = () => {
      if (keepaliveTimerRef.current !== null) {
        window.clearInterval(keepaliveTimerRef.current)
        keepaliveTimerRef.current = null
      }
      setSocketStatus('error')
      ws.close()
    }
    ws.onmessage = (event) => {
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
  }, [applyEnvelope, backend, clearReconnect, filterQuery, scheduleReconnect])

  useEffect(() => {
    cancelledRef.current = false
    connect()

    return () => {
      cancelledRef.current = true
      clearReconnect()
      if (keepaliveTimerRef.current !== null) {
        window.clearInterval(keepaliveTimerRef.current)
        keepaliveTimerRef.current = null
      }
      websocketRef.current?.close()
      websocketRef.current = null
      bufferedMessagesRef.current = []
    }
  }, [clearReconnect, connect])

  return { liveWorkspace, socketStatus, bufferedEventCount }
}