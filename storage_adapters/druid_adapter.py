import os

import httpx


class DruidAdapter:
	name = "druid"

	def __init__(self) -> None:
		self.router_url = os.getenv("DRUID_ROUTER_URL", "http://druid-router:8888")
		self.datasource = os.getenv("DRUID_DATASOURCE", "ledger_events")
		self.client = httpx.AsyncClient(timeout=2.5)

	async def healthy(self) -> bool:
		try:
			response = await self.client.get(f"{self.router_url}/status/health")
			return response.status_code < 500
		except Exception:
			return False

	async def write_event(self, event: dict) -> None:
		payload = [{**event, "__time": event.get("occurred_at")}]
		await self.client.post(
			f"{self.router_url}/druid/indexer/v1/task",
			json={
				"type": "index_parallel",
				"spec": {
					"ioConfig": {"type": "index_parallel", "inputSource": {"type": "inline", "data": payload}},
					"dataSchema": {
						"dataSource": self.datasource,
						"timestampSpec": {"column": "__time", "format": "auto"},
						"dimensionsSpec": {"dimensions": [k for k in event.keys()]},
					},
				},
			},
		)


__all__ = ["DruidAdapter"]
