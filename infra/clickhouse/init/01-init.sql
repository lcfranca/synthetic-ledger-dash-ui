CREATE DATABASE IF NOT EXISTS ledger;

CREATE USER IF NOT EXISTS ledger_app IDENTIFIED WITH plaintext_password BY 'ledger_app_pass';
CREATE USER IF NOT EXISTS ledger_ro IDENTIFIED WITH plaintext_password BY 'ledger_ro_pass';

GRANT ALL ON ledger.* TO ledger_app;
GRANT SELECT ON ledger.* TO ledger_ro;

CREATE TABLE IF NOT EXISTS ledger.events (
  event_id String,
  schema_version String,
  event_type String,
  company_id String,
  tenant_id String,
  occurred_at DateTime64(3, 'UTC'),
  ingested_at DateTime64(3, 'UTC'),
  product_id String,
  supplier_id Nullable(String),
  customer_id Nullable(String),
  warehouse_id String,
  quantity Float64,
  unit_price Float64,
  discount Float64,
  tax Float64,
  currency String,
  cost_basis Float64,
  cmv Float64,
  debit_account String,
  credit_account String,
  channel String
)
ENGINE = MergeTree
ORDER BY (company_id, occurred_at, event_id);
