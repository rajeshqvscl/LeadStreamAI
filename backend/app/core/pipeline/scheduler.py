"""
Scheduler Configuration
All tunable parameters from env - no hardcoded constants in code.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from datetime import datetime, timezone, timedelta


class SchedulerConfig(BaseSettings):
    followup_interval_sec: int = 5
    scheduled_interval_sec: int = 15
    reply_poll_interval_sec: int = 30
    working_hours_start: int = 10
    working_hours_end: int = 17
    working_days: str = "1-5"
    timezone: str = "Asia/Kolkata"
    reply_cleanup_hours_ist: str = "10,16"

    class Config:
        env_prefix = "SCHEDULER_"
        case_sensitive = False

    def is_working_hours_now(self) -> bool:
        tz = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(tz)
        if now.weekday() >= 5:
            return False
        if now.hour < self.working_hours_start or now.hour >= self.working_hours_end:
            return False
        return True

    def get_reply_cleanup_hours(self) -> list[int]:
        return [int(h.strip()) for h in self.reply_cleanup_hours_ist.split(",")]


@lru_cache()
def get_scheduler_config() -> SchedulerConfig:
    return SchedulerConfig()