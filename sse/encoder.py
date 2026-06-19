import json
from typing import Any
from uuid import UUID

from sse.repository import EventRecord


def _safe_event_name(value: str) -> str:
    return value.replace("\r", "").replace("\n", "")


def _json_data(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def encode_event(event: EventRecord) -> str:
    payload = {
        "job_id": str(event.job_id),
        "event_id": event.event_id,
        "event_type": event.event_type,
        "message": event.message,
        "created_at": event.created_at.isoformat(),
    }
    return (
        f"id: {event.event_id}\n"
        f"event: {_safe_event_name(event.event_type)}\n"
        f"data: {_json_data(payload)}\n\n"
    )


def encode_control(event_name: str, job_id: UUID, **data: Any) -> str:
    payload = {"job_id": str(job_id), **data}
    return (
        f"event: {_safe_event_name(event_name)}\n"
        f"data: {_json_data(payload)}\n\n"
    )

