import { useCallback, useEffect, useRef } from 'react'

type Params = {
  delayMs?: number
}

export function useReconnectSession({ delayMs = 1500 }: Params = {}) {
  const timerRef = useRef<number | undefined>(undefined)

  const clearReconnect = useCallback(() => {
    if (timerRef.current !== undefined) {
      window.clearTimeout(timerRef.current)
      timerRef.current = undefined
    }
  }, [])

  const scheduleReconnect = useCallback((onReconnect: () => void) => {
    clearReconnect()
    timerRef.current = window.setTimeout(onReconnect, delayMs)
  }, [clearReconnect, delayMs])

  useEffect(() => clearReconnect, [clearReconnect])

  return { scheduleReconnect, clearReconnect }
}