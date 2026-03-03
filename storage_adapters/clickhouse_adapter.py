import os

import httpx


class ClickHouseAdapter:
	name = "clickhouse"

	def __init__(self) -> None:
		self.base_url = os.getenv("CLICKHOUSE_URL", "http://clickhouse:8123")
		self.db = os.getenv("CLICKHOUSE_DB", "ledger")
		self.user = os.getenv("CLICKHOUSE_USER", "default")
		self.password = os.getenv("CLICKHOUSE_PASSWORD", "")
		self.client = httpx.AsyncClient(timeout=2.0)

	async def healthy(self) -> bool:
		try:
			response = await self.client.get(f"{self.base_url}/ping")
			return response.status_code == 200
		except Exception:
			return False

	async def write_event(self, event: dict) -> None:
		query = """
			INSERT INTO ledger.events FORMAT JSONEachRow
		""".strip()
		await self.client.post(
			f"{self.base_url}/?database={self.db}&query={query}",
			content=(str(event).replace("'", '"') + "\n").encode("utf-8"),
			auth=(self.user, self.password),
		)


__all__ = ["ClickHouseAdapter"]
