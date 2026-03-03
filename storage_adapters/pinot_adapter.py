import os

import httpx


class PinotAdapter:
	name = "pinot"

	def __init__(self) -> None:
		self.controller_url = os.getenv("PINOT_CONTROLLER_URL", "http://pinot-controller:9000")
		self.table = os.getenv("PINOT_TABLE", "ledger_events")
		self.client = httpx.AsyncClient(timeout=2.5)

	async def healthy(self) -> bool:
		try:
			response = await self.client.get(f"{self.controller_url}/health")
			return response.status_code < 500
		except Exception:
			return False

	async def write_event(self, event: dict) -> None:
		await self.client.post(
			f"{self.controller_url}/ingestFromFile",
			json={"tableName": self.table, "records": [event]},
		)


__all__ = ["PinotAdapter"]
