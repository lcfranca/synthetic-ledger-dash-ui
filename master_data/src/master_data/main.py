import json
import sqlite3
from contextlib import closing
from importlib import resources
from pathlib import Path
from typing import Any

from fastapi import FastAPI

app = FastAPI(title="synthetic-ledger-master-data", version="0.1.0")
DB_PATH = Path("/data/master_data.db")


def load_seed(name: str) -> Any:
    seed_path = resources.files("master_data").joinpath("domain_data", name)
    return json.loads(seed_path.read_text(encoding="utf-8"))


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_column(cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    existing_columns = {
        row[1]
        for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing_columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def seed_master_data() -> None:
    company = load_seed("company_profile.json")
    channels = load_seed("channels.json")
    suppliers = load_seed("suppliers.json")
    warehouses = load_seed("warehouses.json")
    products = load_seed("products.json")
    accounts = load_seed("accounts.json")

    with closing(get_connection()) as connection:
        cursor = connection.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS company_profile (
                company_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                legal_name TEXT NOT NULL,
                trade_name TEXT NOT NULL,
                description TEXT NOT NULL,
                segment TEXT NOT NULL,
                currency TEXT NOT NULL,
                headquarters_city TEXT NOT NULL,
                headquarters_state TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS channels (
                channel_id TEXT PRIMARY KEY,
                channel_name TEXT NOT NULL,
                commission_rate REAL NOT NULL,
                settlement_days INTEGER NOT NULL,
                price_multiplier REAL NOT NULL,
                demand_weight REAL NOT NULL,
                channel_type TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS suppliers (
                supplier_id TEXT PRIMARY KEY,
                supplier_name TEXT NOT NULL,
                payment_terms_days INTEGER NOT NULL,
                lead_time_days INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS warehouses (
                warehouse_id TEXT PRIMARY KEY,
                warehouse_name TEXT NOT NULL,
                city TEXT NOT NULL,
                state TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accounts (
                account_code TEXT PRIMARY KEY,
                account_name TEXT NOT NULL,
                statement_section TEXT NOT NULL,
                normal_side TEXT NOT NULL,
                entry_category TEXT NOT NULL,
                account_role TEXT NOT NULL,
                documentation TEXT NOT NULL,
                usage_notes TEXT NOT NULL,
                financial_statement_group TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                product_category TEXT NOT NULL,
                product_brand TEXT NOT NULL,
                preferred_supplier_id TEXT NOT NULL,
                default_warehouse_id TEXT NOT NULL,
                base_cost REAL NOT NULL,
                base_price REAL NOT NULL,
                tax_rate REAL NOT NULL,
                reorder_point INTEGER NOT NULL,
                target_stock INTEGER NOT NULL,
                demand_weight REAL NOT NULL,
                initial_stock_json TEXT NOT NULL,
                channel_ids_json TEXT NOT NULL,
                FOREIGN KEY (preferred_supplier_id) REFERENCES suppliers (supplier_id),
                FOREIGN KEY (default_warehouse_id) REFERENCES warehouses (warehouse_id)
            );
            """
        )

        ensure_column(cursor, "accounts", "documentation", "TEXT NOT NULL DEFAULT ''")
        ensure_column(cursor, "accounts", "usage_notes", "TEXT NOT NULL DEFAULT ''")
        ensure_column(cursor, "accounts", "financial_statement_group", "TEXT NOT NULL DEFAULT ''")

        cursor.execute(
            """
            INSERT OR REPLACE INTO company_profile (
                company_id, tenant_id, legal_name, trade_name, description, segment, currency, headquarters_city, headquarters_state
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company["company_id"],
                company["tenant_id"],
                company["legal_name"],
                company["trade_name"],
                company["description"],
                company["segment"],
                company["currency"],
                company["headquarters_city"],
                company["headquarters_state"],
            ),
        )

        cursor.executemany(
            """
            INSERT OR REPLACE INTO channels (
                channel_id, channel_name, commission_rate, settlement_days, price_multiplier, demand_weight, channel_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["channel_id"],
                    item["channel_name"],
                    item["commission_rate"],
                    item["settlement_days"],
                    item["price_multiplier"],
                    item["demand_weight"],
                    item["channel_type"],
                )
                for item in channels
            ],
        )

        cursor.executemany(
            """
            INSERT OR REPLACE INTO suppliers (
                supplier_id, supplier_name, payment_terms_days, lead_time_days
            ) VALUES (?, ?, ?, ?)
            """,
            [
                (
                    item["supplier_id"],
                    item["supplier_name"],
                    item["payment_terms_days"],
                    item["lead_time_days"],
                )
                for item in suppliers
            ],
        )

        cursor.executemany(
            """
            INSERT OR REPLACE INTO warehouses (
                warehouse_id, warehouse_name, city, state
            ) VALUES (?, ?, ?, ?)
            """,
            [
                (item["warehouse_id"], item["warehouse_name"], item["city"], item["state"])
                for item in warehouses
            ],
        )

        cursor.executemany(
            """
            INSERT OR REPLACE INTO accounts (
                account_code, account_name, statement_section, normal_side, entry_category, account_role,
                documentation, usage_notes, financial_statement_group
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["account_code"],
                    item["account_name"],
                    item["statement_section"],
                    item["normal_side"],
                    item["entry_category"],
                    item["account_role"],
                    item["documentation"],
                    item["usage_notes"],
                    item["financial_statement_group"],
                )
                for item in accounts
            ],
        )

        cursor.executemany(
            """
            INSERT OR REPLACE INTO products (
                product_id, product_name, product_category, product_brand, preferred_supplier_id, default_warehouse_id,
                base_cost, base_price, tax_rate, reorder_point, target_stock, demand_weight, initial_stock_json, channel_ids_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["product_id"],
                    item["product_name"],
                    item["product_category"],
                    item["product_brand"],
                    item["preferred_supplier_id"],
                    item["default_warehouse_id"],
                    item["base_cost"],
                    item["base_price"],
                    item["tax_rate"],
                    item["reorder_point"],
                    item["target_stock"],
                    item["demand_weight"],
                    json.dumps(item["initial_stock"], separators=(",", ":")),
                    json.dumps(item["channel_ids"], separators=(",", ":")),
                )
                for item in products
            ],
        )
        connection.commit()


@app.on_event("startup")
def startup() -> None:
    seed_master_data()


@app.get("/health")
def health() -> dict[str, Any]:
    with closing(get_connection()) as connection:
        counts = {
            "products": connection.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "accounts": connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
            "channels": connection.execute("SELECT COUNT(*) FROM channels").fetchone()[0],
            "suppliers": connection.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0],
            "warehouses": connection.execute("SELECT COUNT(*) FROM warehouses").fetchone()[0],
        }
    return {"status": "ok", "counts": counts}


@app.get("/api/v1/master-data/company")
def get_company() -> dict[str, Any]:
    with closing(get_connection()) as connection:
        row = connection.execute("SELECT * FROM company_profile LIMIT 1").fetchone()
    return dict(row) if row else {}


@app.get("/api/v1/master-data/products")
def get_products() -> list[dict[str, Any]]:
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT p.*, s.supplier_name, w.warehouse_name
            FROM products p
            JOIN suppliers s ON s.supplier_id = p.preferred_supplier_id
            JOIN warehouses w ON w.warehouse_id = p.default_warehouse_id
            ORDER BY p.product_category, p.product_name
            """
        ).fetchall()
    payload = []
    for row in rows:
        item = dict(row)
        item["initial_stock"] = json.loads(item.pop("initial_stock_json"))
        item["channel_ids"] = json.loads(item.pop("channel_ids_json"))
        payload.append(item)
    return payload


@app.get("/api/v1/master-data/accounts")
def get_accounts() -> list[dict[str, Any]]:
    with closing(get_connection()) as connection:
        rows = connection.execute("SELECT * FROM accounts ORDER BY account_code").fetchall()
    return [dict(row) for row in rows]


@app.get("/api/v1/master-data/channels")
def get_channels() -> list[dict[str, Any]]:
    with closing(get_connection()) as connection:
        rows = connection.execute("SELECT * FROM channels ORDER BY channel_name").fetchall()
    return [dict(row) for row in rows]
