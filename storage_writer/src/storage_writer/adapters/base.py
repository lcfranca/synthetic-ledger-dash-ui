from abc import ABC, abstractmethod


class StorageAdapter(ABC):
    name: str

    @abstractmethod
    async def healthy(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def write_event(self, event: dict) -> None:
        raise NotImplementedError

    async def write_events(self, events: list[dict]) -> None:
        for event in events:
            await self.write_event(event)
