#!/usr/bin/env node

import fs from 'node:fs/promises'

function argValue(flag, fallback = null) {
  const index = process.argv.indexOf(flag)
  if (index === -1 || index + 1 >= process.argv.length) {
    return fallback
  }
  return process.argv[index + 1]
}

const backend = argValue('--backend')
const frontendPort = Number(argValue('--frontend-port', '5175'))
const durationSeconds = Number(argValue('--duration-seconds', '90'))
const output = argValue('--output')

if (!backend || !output) {
  console.error('usage: collect_ws_convergence.mjs --backend <backend> --frontend-port <port> --output <file> [--duration-seconds <seconds>]')
  process.exit(1)
}

const wsUrl = `ws://localhost:${frontendPort}/ws/dashboard?backend=${backend}`
const startedAt = Date.now()
const startedIso = new Date().toISOString()
const counts = {}
const samples = []

let firstEntryAt = null
let firstSnapshotAt = null
let firstMeaningfulAt = null
let firstSaleEntryAt = null
let firstSnapshotAfterSaleAt = null
let lastSnapshotTimestamp = null

const socket = new WebSocket(wsUrl)

const finish = async (reason) => {
  const endedAt = Date.now()
  const elapsedSeconds = Math.max((endedAt - startedAt) / 1000, 0.001)
  const snapshotCount = counts['dashboard.snapshot'] || 0
  const entryCount = counts['entry.created'] || 0
  const payload = {
    backend,
    frontendPort,
    wsUrl,
    startedAt: startedIso,
    endedAt: new Date().toISOString(),
    durationSeconds,
    reason,
    counts,
    metrics: {
      frontend_time_to_first_meaningful_state_ms: firstMeaningfulAt === null ? null : firstMeaningfulAt - startedAt,
      first_snapshot_visible_ms: firstSnapshotAt === null ? null : firstSnapshotAt - startedAt,
      entry_to_queue_visible_ms: firstEntryAt === null ? null : firstEntryAt - startedAt,
      event_to_snapshot_visible_ms: firstEntryAt !== null && firstSnapshotAt !== null && firstSnapshotAt >= firstEntryAt ? firstSnapshotAt - firstEntryAt : null,
      sale_to_sales_workspace_visible_ms: firstSaleEntryAt !== null && firstSnapshotAfterSaleAt !== null ? firstSnapshotAfterSaleAt - firstSaleEntryAt : null,
      snapshot_rate_per_second: snapshotCount / elapsedSeconds,
      entry_rate_per_second: entryCount / elapsedSeconds,
    },
    samples,
  }

  await fs.writeFile(output, JSON.stringify(payload, null, 2), 'utf-8')
  try {
    socket.close()
  } catch {
    // no-op
  }
}

socket.onopen = () => {
  socket.send('benchmark-probe')
}

socket.onmessage = (event) => {
  const receivedAt = Date.now()
  const payload = JSON.parse(event.data)
  const type = payload.event_type || 'workspace.snapshot'
  counts[type] = (counts[type] || 0) + 1

  if (firstMeaningfulAt === null) {
    firstMeaningfulAt = receivedAt
  }
  if (type === 'entry.created' && firstEntryAt === null) {
    firstEntryAt = receivedAt
  }
  if (type === 'dashboard.snapshot' && firstSnapshotAt === null) {
    firstSnapshotAt = receivedAt
  }
  if (type === 'entry.created' && payload?.payload?.ontology_event_type === 'sale' && firstSaleEntryAt === null) {
    firstSaleEntryAt = receivedAt
  }
  if (type === 'dashboard.snapshot') {
    const snapshotTimestamp = payload?.payload?.timestamp || payload?.ts || null
    if (firstSaleEntryAt !== null && firstSnapshotAfterSaleAt === null && snapshotTimestamp && snapshotTimestamp !== lastSnapshotTimestamp) {
      firstSnapshotAfterSaleAt = receivedAt
    }
    lastSnapshotTimestamp = snapshotTimestamp
  }

  samples.push({
    receivedAt: new Date(receivedAt).toISOString(),
    event_type: type,
    backend: payload.backend,
    ts: payload.ts || null,
    snapshotTimestamp: payload?.payload?.timestamp || null,
    ontology_event_type: payload?.payload?.ontology_event_type || null,
  })
}

socket.onerror = async () => {
  await finish('socket-error')
  process.exit(1)
}

setTimeout(async () => {
  await finish('completed')
  process.exit(0)
}, Math.max(durationSeconds, 1) * 1000)