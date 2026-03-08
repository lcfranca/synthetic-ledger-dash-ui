import { useCallback, useEffect, useRef } from 'react'

type Params = {
  enabled: boolean
  debounceMs?: number
  heartbeatMs?: number
  onRefresh: () => Promise<unknown> | unknown
}

export function useAuthoritativeRealtimeRefresh({ enabled, debounceMs = 900, heartbeatMs = 5000, onRefresh }: Params) {
  const debounceTimerRef = useRef<number | null>(null)
  const heartbeatTimerRef = useRef<number | null>(null)

  const clearTimers = useCallback(() => {
    if (debounceTimerRef.current !== null) {
      window.clearTimeout(debounceTimerRef.current)
      debounceTimerRef.current = null
    }
    if (heartbeatTimerRef.current !== null) {
      window.clearInterval(heartbeatTimerRef.current)
      heartbeatTimerRef.current = null
    }
  }, [])

  const refreshNow = useCallback(() => {
    void onRefresh()
  }, [onRefresh])

  const signalActivity = useCallback(() => {
    if (!enabled) {
      return
    }
    if (debounceTimerRef.current !== null) {
      window.clearTimeout(debounceTimerRef.current)
    }
    debounceTimerRef.current = window.setTimeout(() => {
      debounceTimerRef.current = null
      refreshNow()
    }, debounceMs)
  }, [debounceMs, enabled, refreshNow])

  useEffect(() => {
    if (!enabled) {
      clearTimers()
      return
    }

    heartbeatTimerRef.current = window.setInterval(() => {
      refreshNow()
    }, heartbeatMs)

    return clearTimers
  }, [clearTimers, enabled, heartbeatMs, refreshNow])

  return { signalActivity, refreshNow }
}