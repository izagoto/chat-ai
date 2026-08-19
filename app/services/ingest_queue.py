from __future__ import annotations

import asyncio
import logging

from app.services.ingest import process_staged_document

logger = logging.getLogger(__name__)


class IngestWorker:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[tuple[str, str] | None] | None = None
        self._task: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        return self._queue is not None

    async def start(self) -> None:
        if self._queue is not None:
            return
        self._queue = asyncio.Queue()
        self._task = asyncio.create_task(self._loop(), name="alder-ingest-worker")

    async def stop(self) -> None:
        queue = self._queue
        task = self._task
        if queue is not None:
            await queue.put(None)
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout=5)
            except (TimeoutError, asyncio.CancelledError):
                task.cancel()
        self._queue = None
        self._task = None

    async def submit(self, collection_id: str, document_id: str) -> None:
        if self._queue is None:
            await process_staged_document(collection_id, document_id)
            return
        await self._queue.put((collection_id, document_id))

    async def _loop(self) -> None:
        queue = self._queue
        assert queue is not None
        while True:
            job = await queue.get()
            try:
                if job is None:
                    return
                collection_id, document_id = job
                await process_staged_document(collection_id, document_id)
            except Exception:
                logger.exception("Ingest job failed")
            finally:
                queue.task_done()


ingest_worker = IngestWorker()
