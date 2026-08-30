"""
Scheduler Configuration
All tunable parameters from env - no hardcoded constants in code.
"""

from datetime import datetime, timedelta, timezone
from functools import lru_cache

from pydantic_settings import BaseSettings


class SchedulerConfig(BaseSettings):
    followup_interval_sec: int = 5
    scheduled_interval_sec: int = 15
    reply_poll_interval_sec: int = 30  # legacy: unused now (fixed-hours polling)
    reply_poll_hours_ist: str = "9,13,17"  # reply detector runs at these IST hours
    working_hours_start: int = 10
    working_hours_end: int = 17
    working_days: str = "1-5"
    timezone: str = "Asia/Kolkata"
    reply_cleanup_hours_ist: str = "10,16"
    # Drip-send pacing
    drip_interval_minutes: int = 1      # seconds between scheduled slots per email
    drip_jitter_seconds: int = 30       # random jitter added to each slot (human-like)
    drip_grace_minutes: int = 30        # first email goes out at least this long after scheduling
    cooldown_every_n_emails: int = 25   # after this many sends in the rolling window...
    cooldown_window_minutes: int = 25   # ...window length for the rolling count
    scheduled_max_per_cycle: int = 5    # max sends per dispatcher cycle (burst protection)
    # Maintenance window (Gmail watch renewal / cache cleanup)
    maintenance_enabled: bool = True
    maintenance_hours_ist: str = "8,20"  # 8 AM and 8 PM IST
    maintenance_days: str = "0-5"        # Mon=0 … Sat=5  (Monday–Saturday)
    # Email-scheduler startup cooldown: hold ALL automated dispatch for the first
    # N seconds after boot so freshly-created drafts stay in the review queue
    # (PENDING_APPROVAL) and can be manually sent/rejected before the auto-pilot
    # sweep promotes them to SCHEDULED.
    scheduler_startup_cooldown_sec: int = 600  # 10 minutes

    class Config:
        env_prefix = "SCHEDULER_"
        case_sensitive = False

    def is_working_hours_now(self) -> bool:
        tz = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(tz)
        if now.weekday() >= 5:
            return False
        return not (now.hour < self.working_hours_start or now.hour >= self.working_hours_end)

    def next_working_time(self, dt) -> datetime:
        """Roll a naive datetime forward to the next allowed sending slot.
        Blackout: before start hour, at/after end hour, and weekends.
        Returns a NAIVE datetime in IST (matching leads_raw.scheduled_at usage).
        """
        tz = timezone(timedelta(hours=5, minutes=30))
        timedelta(hours=5, minutes=30)
        if dt.tzinfo is not None:
            dt = dt.astimezone(tz).replace(tzinfo=None)
        cur = dt
        for _ in range(10):  # safety bound — never loops more than ~2 weekends
            # Roll weekend (Sat=5, Sun=6) → Monday at start hour
            while cur.weekday() >= 5:
                days_to_monday = 7 - cur.weekday()
                cur = (cur + timedelta(days=days_to_monday)).replace(
                    hour=self.working_hours_start, minute=0, second=0, microsecond=0
                )
            if cur.hour < self.working_hours_start:
                cur = cur.replace(hour=self.working_hours_start, minute=0, second=0, microsecond=0)
            elif cur.hour >= self.working_hours_end:
                nxt = (cur + timedelta(days=1)).replace(
                    hour=self.working_hours_start, minute=0, second=0, microsecond=0
                )
                cur = nxt
                continue  # re-check weekend for the new day
            break
        return cur

    def get_reply_cleanup_hours(self) -> list[int]:
        return [int(h.strip()) for h in self.reply_cleanup_hours_ist.split(",")]

    def get_reply_poll_hours(self) -> list[int]:
        return [int(h.strip()) for h in self.reply_poll_hours_ist.split(",")]

    def get_maintenance_hours(self) -> list[int]:
        return sorted(int(h.strip()) for h in self.maintenance_hours_ist.split(",") if h.strip())

    def get_maintenance_days(self) -> list[int]:
        s = self.maintenance_days.strip()
        if "-" in s:
            lo, hi = s.split("-", 1)
            return list(range(int(lo), int(hi) + 1))
        return [int(x.strip()) for x in s.split(",") if x.strip()]


@lru_cache
def get_scheduler_config() -> SchedulerConfig:
    return SchedulerConfig()
