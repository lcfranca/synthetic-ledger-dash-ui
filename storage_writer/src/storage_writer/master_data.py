import json
from functools import lru_cache
from importlib import resources
from typing import Any


@lru_cache(maxsize=1)
def load_accounts_by_code() -> dict[str, dict[str, Any]]:
    data_path = resources.files("storage_writer").joinpath("domain_data", "accounts.json")
    rows = json.loads(data_path.read_text(encoding="utf-8"))
    return {item["account_code"]: item for item in rows}


@lru_cache(maxsize=1)
def load_accounts_by_role() -> dict[str, dict[str, Any]]:
    by_code = load_accounts_by_code()
    return {item["account_role"]: item for item in by_code.values()}
