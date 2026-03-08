import { startTransition, useCallback, useEffect, useRef, useState } from 'react'
import { buildFilterSearchParams, type EntryFilters, type RealtimeEnvelope, type WorkspaceSnapshot } from '../../../entities/dashboard/api'
import {
  appendPendingRealtimeEntry,
  isDashboardEnvelope,
  isEntryCreatedEnvelope,
  preferIncomingSnapshot,
  projectRealtimeWorkspace,
  reconcilePendingRealtimeTransactions,
  reconcilePendingRealtimeEntries,
  releaseMatureRealtimeTransactions,
  upsertPendingRealtimeTransaction,
  withRealtimeEntry,
} from '../../../entities/dashboard/lib/realtime'
import { useReconnectSession } from '../../reconnect-session/model/useReconnectSession'

const TRANSACTION_HOLDBACK_MS = 120

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
  const baseWorkspaceRef = useRef<WorkspaceSnapshot | null>(initialWorkspace ?? null)
  const websocketRef = useRef<WebSocket | null>(null)
  const cancelledRef = useRef(false)
  const pausedRef = useRef(isPaused)
  const bufferedMessagesRef = useRef<Array<RealtimeEnvelope | WorkspaceSnapshot>>([])
  const pendingEntriesRef = useRef<ReturnType<typeof appendPendingRealtimeEntry>>([])
  const pendingTransactionsRef = useRef<ReturnType<typeof upsertPendingRealtimeTransaction>>([])
  const transactionFlushTimerRef = useRef<number | null>(null)
  const keepaliveTimerRef = useRef<number | null>(null)
  const connectionSerialRef = useRef(0)
  const filterQuery = buildFilterSearchParams(filters).toString()

  const { scheduleReconnect, clearReconnect } = useReconnectSession({ delayMs: 1500 })

  const rebuildProjectedWorkspace = useCallback(() => {
    const projectedBase = baseWorkspaceRef.current ?? seedWorkspaceRef.current
    return projectRealtimeWorkspace(projectedBase, pendingEntriesRef.current)
  }, [])

  const flushMatureTransactions = useCallback(() => {
    transactionFlushTimerRef.current = null
    pendingTransactionsRef.current = reconcilePendingRealtimeTransactions(
      baseWorkspaceRef.current ?? seedWorkspaceRef.current,
      pendingTransactionsRef.current,
    )

    const { ready, waiting } = releaseMatureRealtimeTransactions(pendingTransactionsRef.current, TRANSACTION_HOLDBACK_MS)
    pendingTransactionsRef.current = waiting

    if (ready.length > 0) {
      let nextPendingEntries = pendingEntriesRef.current
      for (const transaction of ready) {
        for (const entry of transaction.entries) {
          nextPendingEntries = appendPendingRealtimeEntry(nextPendingEntries, {
            event_id: entry.eventId,
            event_type: 'entry.created',
            version: '1.0.0',
            backend: entry.backend,
            ts: entry.ts,
            payload: entry.payload,
          }, entry.receivedAt)
        }
      }
      pendingEntriesRef.current = reconcilePendingRealtimeEntries(baseWorkspaceRef.current ?? seedWorkspaceRef.current, nextPendingEntries)
    }

    if (pendingTransactionsRef.current.length > 0) {
      transactionFlushTimerRef.current = window.setTimeout(flushMatureTransactions, TRANSACTION_HOLDBACK_MS)
    }

    const nextWorkspace = rebuildProjectedWorkspace()
    startTransition(() => {
      setLiveWorkspace(nextWorkspace)
    })

    return nextWorkspace
  }, [rebuildProjectedWorkspace])

  const scheduleTransactionFlush = useCallback(() => {
    if (transactionFlushTimerRef.current !== null) {
      return
    }
    transactionFlushTimerRef.current = window.setTimeout(flushMatureTransactions, TRANSACTION_HOLDBACK_MS)
  }, [flushMatureTransactions])

  const applyEnvelope = useCallback((current: WorkspaceSnapshot | null, parsed: RealtimeEnvelope | WorkspaceSnapshot) => {
    if (isEntryCreatedEnvelope(parsed)) {
      if (mode === 'snapshot-only') {
        return current ?? seedWorkspaceRef.current
      }

      pendingTransactionsRef.current = upsertPendingRealtimeTransaction(pendingTransactionsRef.current, parsed)
      scheduleTransactionFlush()
      return current ?? rebuildProjectedWorkspace()
    }

    if (isDashboardEnvelope(parsed)) {
      const nextBase = preferIncomingSnapshot(baseWorkspaceRef.current ?? seedWorkspaceRef.current, { ...parsed.payload, backend: parsed.backend })
      baseWorkspaceRef.current = nextBase
      pendingEntriesRef.current = reconcilePendingRealtimeEntries(nextBase, pendingEntriesRef.current)
      pendingTransactionsRef.current = reconcilePendingRealtimeTransactions(nextBase, pendingTransactionsRef.current)
      return projectRealtimeWorkspace(nextBase, pendingEntriesRef.current)
    }

    if ('event_type' in parsed) {
      return current
    }

    baseWorkspaceRef.current = parsed
    pendingEntriesRef.current = reconcilePendingRealtimeEntries(parsed, pendingEntriesRef.current)
    pendingTransactionsRef.current = reconcilePendingRealtimeTransactions(parsed, pendingTransactionsRef.current)
    return projectRealtimeWorkspace(parsed, pendingEntriesRef.current)
  }, [mode, rebuildProjectedWorkspace, scheduleTransactionFlush])

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
    baseWorkspaceRef.current = initialWorkspace ?? null
    pendingEntriesRef.current = []
    pendingTransactionsRef.current = []
    if (transactionFlushTimerRef.current !== null) {
      window.clearTimeout(transactionFlushTimerRef.current)
      transactionFlushTimerRef.current = null
    }
    startTransition(() => {
      setLiveWorkspace(projectRealtimeWorkspace(initialWorkspace ?? null, pendingEntriesRef.current))
    })
  }, [backend, filterQuery, initialWorkspace])

  useEffect(() => {
    if (enabled) {
      return
    }
    setSocketStatus('idle')
    if (keepaliveTimerRef.current !== null) {
      window.clearInterval(keepaliveTimerRef.current)
      keepaliveTimerRef.current = null
    }
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
      if (connectionSerialRef.current !== connectionSerial) {
        return
      }
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
      if (connectionSerialRef.current !== connectionSerial) {
        return
      }
      if (keepaliveTimerRef.current !== null) {
        window.clearInterval(keepaliveTimerRef.current)
        keepaliveTimerRef.current = null
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
      if (keepaliveTimerRef.current !== null) {
        window.clearInterval(keepaliveTimerRef.current)
        keepaliveTimerRef.current = null
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
      pendingTransactionsRef.current = []
      if (keepaliveTimerRef.current !== null) {
        window.clearInterval(keepaliveTimerRef.current)
        keepaliveTimerRef.current = null
      }
      if (transactionFlushTimerRef.current !== null) {
        window.clearTimeout(transactionFlushTimerRef.current)
        transactionFlushTimerRef.current = null
      }
    }
  }, [clearReconnect, connect])

  return { liveWorkspace, socketStatus, bufferedEventCount }
}