#!/usr/bin/env node

const backend = (process.env.BACKEND || process.argv[2] || 'druid').trim().toLowerCase()
const port = process.env.FRONTEND_PORT || process.argv[3] || (backend === 'pinot' ? '5175' : backend === 'clickhouse' ? '5173' : backend === 'materialize' ? '5176' : '5174')
const timeoutMs = Number(process.env.REALTIME_VERIFY_TIMEOUT_MS || 8000)
const minEvents = Number(process.env.REALTIME_VERIFY_MIN_EVENTS || 5)
const isMaterialize = backend === 'materialize'
const minSnapshots = Number(process.env.REALTIME_VERIFY_MIN_SNAPSHOTS || (isMaterialize ? 2 : 1))
const maxSnapshotEvents = Number(process.env.REALTIME_VERIFY_MAX_SNAPSHOTS || (isMaterialize ? 32 : 1))

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
  if (isMaterialize) {
    if (snapshotCount >= minSnapshots) {
      finish(0, 'stream-active')
      return
    }
    finish(1, 'stream-timeout')
    return
  }
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
  if (!isMaterialize && snapshotCount > maxSnapshotEvents) {
    clearTimeout(timer)
    finish(1, 'too-many-snapshots')
    return
  }
  if (isMaterialize && snapshotCount >= minSnapshots) {
    clearTimeout(timer)
    finish(0, 'stream-active')
    return
  }
  if (isMaterialize) {
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