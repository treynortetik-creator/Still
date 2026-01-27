"""Stream manager for live agent streaming via SSE."""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Global registry of active streams per job
_job_streams: dict[str, "StreamManager"] = {}


@dataclass
class StreamEvent:
    """A single stream event."""
    event_type: str  # step, chunk, complete, error
    data: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class StreamManager:
    """Manages SSE streams for a job."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.queue: asyncio.Queue[StreamEvent] = asyncio.Queue()
        self.active = True
        self._subscribers: int = 0

    async def emit(self, event_type: str, data: str):
        """Emit an event to all subscribers."""
        if not self.active:
            return
        event = StreamEvent(event_type=event_type, data=data)
        await self.queue.put(event)

    async def emit_step(self, step_name: str, description: str = ""):
        """Emit a step marker."""
        await self.emit("step", json.dumps({
            "step": step_name,
            "description": description
        }))

    async def emit_chunk(self, text: str):
        """Emit a text chunk (for streaming LLM output)."""
        await self.emit("chunk", text)

    async def emit_complete(self, message: str = "Processing complete"):
        """Emit completion event."""
        await self.emit("complete", message)
        self.active = False

    async def emit_error(self, error: str):
        """Emit error event."""
        await self.emit("error", error)
        self.active = False

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Subscribe to the stream and yield SSE-formatted events."""
        self._subscribers += 1
        try:
            while self.active or not self.queue.empty():
                try:
                    # Wait for event with timeout to allow checking active state
                    event = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                    yield f"event: {event.event_type}\ndata: {event.data}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive comment to prevent connection timeout
                    yield ": keepalive\n\n"
        finally:
            self._subscribers -= 1
            if self._subscribers <= 0:
                # Cleanup when no subscribers
                unregister_stream(self.job_id)


def get_stream(job_id: str) -> Optional[StreamManager]:
    """Get existing stream for a job."""
    return _job_streams.get(job_id)


def get_or_create_stream(job_id: str) -> StreamManager:
    """Get or create a stream for a job."""
    if job_id not in _job_streams:
        _job_streams[job_id] = StreamManager(job_id)
        logger.info(f"Created stream for job {job_id}")
    return _job_streams[job_id]


def unregister_stream(job_id: str):
    """Remove a stream from the registry."""
    if job_id in _job_streams:
        del _job_streams[job_id]
        logger.info(f"Unregistered stream for job {job_id}")
