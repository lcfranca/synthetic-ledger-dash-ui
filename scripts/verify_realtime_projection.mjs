#!/usr/bin/env node

const backend = (process.env.BACKEND || process.argv[2] || 'druid').trim().toLowerCase()
const frontendPort = Number(process.env.FRONTEND_PORT || process.argv[3] || (backend === 'pinot' ? '5175' : backend === 'clickhouse' ? '5173' : backend === 'materialize' ? '5176' : '5174'))
const timeoutMs = Number(process.env.REALTIME_PROJECTION_TIMEOUT_MS || 10000)
const isMaterialize = backend === 'materialize'

const baseUrl = `http://localhost:${frontendPort}`
const wsUrl = `ws://localhost:${frontendPort}/ws/dashboard?backend=${backend}`

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function round(value, digits = 2) {
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

function projectSummary(summary, entry) {
  const next = clone(summary)
  const assets = next.balance_sheet.assets
  const liabilities = next.balance_sheet.liabilities
  const income = next.income_statement

  switch (entry.account_role) {
    case 'cash':
      assets.cash = round(assets.cash + entry.signed_amount)
      break
    case 'bank_accounts':
      assets.bank_accounts = round(assets.bank_accounts + entry.signed_amount)
      break
    case 'recoverable_tax':
      assets.recoverable_tax = round(assets.recoverable_tax + entry.signed_amount)
      break
    case 'inventory':
      assets.inventory = round(assets.inventory + entry.signed_amount)
      break
    case 'accounts_payable':
      liabilities.accounts_payable = round(Math.abs(-liabilities.accounts_payable + entry.signed_amount))
      break
    case 'short_term_loans':
      liabilities.short_term_loans = round(Math.abs(-liabilities.short_term_loans + entry.signed_amount))
      break
    case 'tax_payable':
      liabilities.tax_payable = round(Math.abs(-liabilities.tax_payable + entry.signed_amount))
      break
    case 'revenue':
      income.revenue = round(Math.abs(-income.revenue + entry.signed_amount))
      break
    case 'returns':
      income.returns = round(income.returns + entry.signed_amount)
      break
    case 'marketplace_fees':
      income.marketplace_fees = round(income.marketplace_fees + entry.signed_amount)
      break
    case 'outbound_freight':
      income.freight_out = round(income.freight_out + entry.signed_amount)
      break
    case 'bank_fees':
      income.bank_fees = round(income.bank_fees + entry.signed_amount)
      break
    case 'interest_expense':
      income.financial_expenses = round(income.financial_expenses + entry.signed_amount)
      break
    case 'cogs':
      income.cmv = round(income.cmv + entry.signed_amount)
      break
    default:
      return { changed: false, summary: next, field: null }
  }

  assets.total = round(assets.cash + assets.bank_accounts + assets.recoverable_tax + assets.inventory)
  liabilities.total = round(liabilities.accounts_payable + liabilities.short_term_loans + liabilities.tax_payable)
  income.net_revenue = round(income.revenue - income.returns)
  income.operating_expenses = round(income.marketplace_fees + income.freight_out + income.bank_fees + income.other_expenses)
  income.gross_profit = round(income.net_revenue - income.cmv)
  income.expenses = round(income.operating_expenses + income.financial_expenses + income.cmv)
  income.net_income = round(income.net_revenue - income.expenses)
  next.balance_sheet.equity.current_earnings = income.net_income
  next.balance_sheet.equity.total = round(assets.total - liabilities.total)
  next.balance_sheet.total_liabilities_and_equity = round(liabilities.total + next.balance_sheet.equity.total)
  next.balance_sheet.difference = round(assets.total - next.balance_sheet.total_liabilities_and_equity)

  return { changed: true, summary: next, field: entry.account_role }
}

const response = await fetch(`${baseUrl}/api/v1/dashboard/workspace`)
if (!response.ok) {
  throw new Error(`workspace bootstrap failed: ${response.status}`)
}

const workspace = await response.json()
let projectedSummary = clone(workspace.summary)
let lastSnapshotTimestamp = workspace.timestamp || null

const finish = (code, reason, extra = {}) => {
  console.log(JSON.stringify({ backend, frontendPort, wsUrl, reason, ...extra }, null, 2))
  process.exit(code)
}

const socket = new WebSocket(wsUrl)
const timer = setTimeout(() => finish(1, 'projection-timeout'), timeoutMs)

socket.onmessage = (event) => {
  const envelope = JSON.parse(event.data)
  if (isMaterialize && envelope.event_type === 'dashboard.snapshot') {
    const nextTimestamp = envelope.payload?.timestamp || envelope.ts || null
    const nextSummary = envelope.payload?.summary
    if (!nextSummary) {
      return
    }

    const summaryChanged = JSON.stringify(nextSummary) !== JSON.stringify(projectedSummary)
    const timestampAdvanced = nextTimestamp && nextTimestamp !== lastSnapshotTimestamp
    projectedSummary = clone(nextSummary)
    lastSnapshotTimestamp = nextTimestamp

    if (!summaryChanged && !timestampAdvanced) {
      return
    }

    clearTimeout(timer)
    finish(0, 'projection-active', {
      snapshotTimestamp: nextTimestamp,
      mode: 'snapshot-authoritative',
    })
    return
  }

  if (envelope.event_type !== 'entry.created') {
    return
  }

  const result = projectSummary(projectedSummary, envelope.payload)
  projectedSummary = result.summary
  if (!result.changed) {
    return
  }

  clearTimeout(timer)
  finish(0, 'projection-active', {
    field: result.field,
    eventId: envelope.event_id,
    accountCode: envelope.payload.account_code,
    signedAmount: envelope.payload.signed_amount,
    projectedTimestamp: envelope.ts,
  })
}

socket.onerror = () => {
  clearTimeout(timer)
  finish(1, 'socket-error')
}