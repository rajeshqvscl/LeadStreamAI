"""
Email Job Definition
Typed, serializable dataclass for queue operations.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any


class EmailPriority(IntEnum):
    """Priority levels - lower number = higher priority"""
    HIGH = 1       # Manual sends, replies
    NORMAL = 5     # Scheduled, followups
    LOW = 10       # Bulk, reports


@dataclass
class EmailJob:
    # Required fields
    to_email: str
    subject: str
    html_content: str
    user_id: int

    # Optional fields
    from_email: str | None = None
    from_name: str | None = None
    cc: str | None = None
    bcc: str | None = None
    lead_id: int | None = None
    thread_id: str | None = None
    in_reply_to: str | None = None

    # Attachments: [{filename, content_base64, mime_type}]
    attachments: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    priority: EmailPriority = EmailPriority.NORMAL
    template_name: str | None = None
    signature_id: int | None = None
    tracking_enabled: bool = True
    idempotency_key: str | None = None

    # Scheduling
    scheduled_at: datetime | None = None
    max_retries: int = 3
    retry_count: int = 0

    # System timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    queued_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Error tracking
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for Redis storage"""
        data = asdict(self)
        # Convert enum to int
        data['priority'] = int(self.priority)
        # Convert datetimes to ISO strings
        for key in ['created_at', 'queued_at', 'started_at', 'completed_at', 'scheduled_at']:
            if data.get(key):
                data[key] = data[key].isoformat()
        return data

    def to_json(self) -> str:
        """Serialize to JSON string"""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'EmailJob':
        """Deserialize from dict"""
        # Handle priority conversion
        if isinstance(data.get('priority'), int):
            data['priority'] = EmailPriority(data['priority'])

        # Handle datetime conversion
        for key in ['created_at', 'queued_at', 'started_at', 'completed_at', 'scheduled_at']:
            if data.get(key) and isinstance(data[key], str):
                data[key] = datetime.fromisoformat(data[key])

        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'EmailJob':
        """Deserialize from JSON string"""
        return cls.from_dict(json.loads(json_str))

    def with_idempotency_key(self, key: str) -> 'EmailJob':
        """Set idempotency key on this job (mutates self, returns self for chaining)"""
        self.idempotency_key = key
        return self

    def increment_retry(self) -> 'EmailJob':
        """Increment retry count on this job (mutates self, returns self for chaining)"""
        self.retry_count += 1
        return self
