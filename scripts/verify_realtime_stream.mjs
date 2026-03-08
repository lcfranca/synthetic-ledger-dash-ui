#!/usr/bin/env node

const backend = (process.env.BACKEND || process.argv[2] || 'druid').trim().toLowerCase()
const port = process.env.FRONTEND_PORT || process.argv[3] || (backend === 'pinot' ? '5175' : backend === 'clickhouse' ? '5173' : '5174')
const timeoutMs = Number(process.env.REALTIME_VERIFY_TIMEOUT_MS || 8000)
const minEvents = Number(process.env.REALTIME_VERIFY_MIN_EVENTS || 5)
const maxSnapshotEvents = Number(process.env.REALTIME_VERIFY_MAX_SNAPSHOTS || 1)

const websocketUrl = `ws://localhost:${port}/ws/dashboard?backend=${backend}`
const counts = {}
let total = 0

const socket = new WebSocket(websocketUrl)

const finish = (exitCode, reason) => {
  const payload = { backend, port: Number(port), websocketUrl, total, counts, reason }
  console.log(JSON.stringify(payload, null, 2))
  try {
    socket.close()
  } catch {
    // no-op
  }
  process.exit(exitCode)
}

const timer = setTimeout(() => {
  const snapshotCount = counts['dashboard.snapshot'] || 0
  const entryCount = counts['entry.created'] || 0
  if (entryCount >= minEvents && snapshotCount <= maxSnapshotEvents) {
    finish(0, 'stream-active')
    return
  }
  finish(1, 'stream-timeout')
}, timeoutMs)

socket.onopen = () => {
  socket.send('probe')
}

socket.onmessage = (event) => {
  const payload = JSON.parse(event.data)
  const type = payload.event_type || 'workspace.snapshot'
  counts[type] = (counts[type] || 0) + 1
  total += 1

  const snapshotCount = counts['dashboard.snapshot'] || 0
  const entryCount = counts['entry.created'] || 0
  if (snapshotCount > maxSnapshotEvents) {
    clearTimeout(timer)
    finish(1, 'too-many-snapshots')
    return
  }
  if (entryCount >= minEvents && snapshotCount <= maxSnapshotEvents) {
    clearTimeout(timer)
    finish(0, 'stream-active')
  }
}

socket.onerror = () => {
  clearTimeout(timer)
  finish(1, 'socket-error')
}