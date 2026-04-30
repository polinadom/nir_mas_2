from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def new_id() -> str:
    return uuid4().hex


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


class Performative(str, Enum):
    REQUEST = "request"
    INFORM = "inform"
    RESULT = "result"
    ERROR = "error"
    HANDOFF = "handoff"


class ArtifactRef(BaseModel):
    artifact_id: str
    path: str
    stage: str
    producer: str
    checksum: str
    size_bytes: int
    summary: str | None = None
    version: int = 1


class A2AMessage(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    protocol: str = "a2a/0.1"
    message_id: str = Field(default_factory=new_id)
    thread_id: str = Field(default_factory=new_id)
    correlation_id: str | None = None
    parent_message_id: str | None = None
    sender: str
    recipient: str
    performative: Performative
    topic: str
    body: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
