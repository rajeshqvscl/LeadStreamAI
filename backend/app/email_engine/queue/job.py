"""
Email Job Definition
Typed, serializable dataclass for queue operations.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import IntEnum
import json


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
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    cc: Optional[str] = None
    bcc: Optional[str] = None
    lead_id: Optional[int] = None
    thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    
    # Attachments: [{filename, content_base64, mime_type}]
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    priority: EmailPriority = EmailPriority.NORMAL
    template_name: Optional[str] = None
    tracking_enabled: bool = True
    idempotency_key: Optional[str] = None
    
    # Scheduling
    scheduled_at: Optional[datetime] = None
    max_retries: int = 3
    retry_count: int = 0
    
    # System timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Error tracking
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
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
    def from_dict(cls, data: Dict[str, Any]) -> 'EmailJob':
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
        """Return new job with idempotency key set"""
        self.idempotency_key = key
        return self
    
    def increment_retry(self) -> 'EmailJob':
        """Return new job with incremented retry count"""
        self.retry_count += 1
        return self