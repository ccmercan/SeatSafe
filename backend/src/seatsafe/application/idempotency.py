from datetime import datetime
from typing import Protocol
from uuid import UUID


class StoredIdempotencyRecord(Protocol):
    request_fingerprint: str
    response_status: int
    response_body: str


class IdempotencyRepository(Protocol):
    async def lock_key(self, *, owner_id: UUID, operation: str, key: str) -> None: ...

    async def get_record(
        self, *, owner_id: UUID, operation: str, key: str
    ) -> StoredIdempotencyRecord | None: ...

    async def add_record(
        self,
        *,
        id: UUID,
        owner_id: UUID,
        operation: str,
        key: str,
        request_fingerprint: str,
        hold_id: UUID | None,
        reservation_id: UUID | None,
        completed_at: datetime,
        response_body: str,
    ) -> None: ...
