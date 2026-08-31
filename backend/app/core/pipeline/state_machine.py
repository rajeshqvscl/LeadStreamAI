"""
Lead Pipeline State Machine
Single source of truth for lead lifecycle transitions.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum


class LeadState(StrEnum):
    NEW = "NEW"
    DRAFT_PENDING = "DRAFT_PENDING"
    SCHEDULED = "SCHEDULED"
    SENT = "SENT"
    FOLLOWUP_ACTIVE = "FOLLOWUP_ACTIVE"
    FOLLOWUP_PAUSED = "FOLLOWUP_PAUSED"
    REPLIED = "REPLIED"
    MEETING_REQUIRED = "MEETING_REQUIRED"
    CLOSED_WON = "CLOSED_WON"
    CLOSED_LOST = "CLOSED_LOST"
    UNSUBSCRIBED = "UNSUBSCRIBED"
    BOUNCED = "BOUNCED"


# Terminal states - no transitions out
TERMINAL_STATES: set[LeadState] = {
    LeadState.CLOSED_WON,
    LeadState.CLOSED_LOST,
    LeadState.UNSUBSCRIBED,
    LeadState.BOUNCED,
}

# Explicit allowed transitions: from_state -> set of valid to_states
TRANSITIONS: dict[LeadState, set[LeadState]] = {
    LeadState.NEW: {LeadState.DRAFT_PENDING},
    LeadState.DRAFT_PENDING: {LeadState.SCHEDULED, LeadState.NEW},
    LeadState.SCHEDULED: {LeadState.SENT, LeadState.NEW},
    LeadState.SENT: {LeadState.FOLLOWUP_ACTIVE, LeadState.REPLIED, LeadState.BOUNCED},
    LeadState.FOLLOWUP_ACTIVE: {
        LeadState.FOLLOWUP_ACTIVE,  # Next followup sent
        LeadState.REPLIED,
        LeadState.FOLLOWUP_PAUSED,
        LeadState.CLOSED_LOST,
        LeadState.MEETING_REQUIRED,
    },
    LeadState.FOLLOWUP_PAUSED: {LeadState.FOLLOWUP_ACTIVE, LeadState.CLOSED_LOST},
    LeadState.REPLIED: {LeadState.MEETING_REQUIRED, LeadState.CLOSED_LOST, LeadState.FOLLOWUP_ACTIVE},
    LeadState.MEETING_REQUIRED: {LeadState.CLOSED_WON, LeadState.CLOSED_LOST, LeadState.REPLIED},
}

# Reverse mapping for validation
REVERSE_TRANSITIONS: dict[LeadState, set[LeadState]] = {}
for from_state, to_states in TRANSITIONS.items():
    for to_state in to_states:
        if to_state not in REVERSE_TRANSITIONS:
            REVERSE_TRANSITIONS[to_state] = set()
        REVERSE_TRANSITIONS[to_state].add(from_state)


@dataclass
class Lead:
    """Minimal lead data needed for state transitions"""
    id: int
    pipeline_state: str
    followup_stage: int = 0
    followup_status: str = ""
    email_status: str = ""
    is_responded: bool = False
    replied_at: datetime | None = None
    reply_intent: str = ""
    email_opt_in: bool = True
    is_unsubscribed: bool = False
    last_outreach_at: datetime | None = None
    lead_type: str = "INVESTOR"
    user_id: int = 0
    auto_followup: bool = True
    google_refresh_token: str | None = None


class TransitionGuard:
    """Pre-condition checks for state transitions"""

    @staticmethod
    def sent_to_followup_active(lead: Lead, config: 'SchedulerConfig') -> bool:
        if lead.followup_stage >= config.get_max_stage(lead.lead_type):
            return False
        if lead.is_responded or lead.replied_at is not None:
            return False
        if not config.is_followup_working_hours_now():
            return False
        if not lead.auto_followup:
            return False
        return lead.google_refresh_token

    @staticmethod
    def followup_active_to_next(lead: Lead, config: 'SchedulerConfig') -> bool:
        return TransitionGuard.sent_to_followup_active(lead, config)

    @staticmethod
    def sent_to_replied(lead: Lead) -> bool:
        return lead.is_responded or lead.replied_at is not None or bool(lead.reply_intent)

    @staticmethod
    def any_to_unsubscribed(lead: Lead) -> bool:
        return not lead.email_opt_in or lead.is_unsubscribed

    @staticmethod
    def any_to_bounced(lead: Lead) -> bool:
        return lead.email_status == 'BOUNCED'


class SchedulerConfig:
    """Configuration for scheduler-dependent guards"""

    def __init__(self):
        from app.core.config import get_followup_settings, get_scheduler_settings
        self.scheduler = get_scheduler_settings()
        self.followup = get_followup_settings()

    def is_working_hours_now(self) -> bool:
        """Check if current IST time is within working hours"""
        IST = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(IST)
        if now.weekday() >= 5:  # Weekend
            return False
        return not (now.hour < self.scheduler.working_hours_start or now.hour >= self.scheduler.working_hours_end)

    def get_max_stage(self, lead_type: str) -> int:
        if lead_type == "CLIENT":
            return self.followup.client_max_stage
        return self.followup.investor_max_stage

    def get_intervals(self, lead_type: str) -> dict:
        if lead_type == "CLIENT":
            return dict(item.split(":") for item in self.followup.client_intervals.split(","))
        return dict(item.split(":") for item in self.followup.investor_intervals.split(","))


class LeadPipeline:
    """
    Lead Pipeline State Machine
    Enforces valid state transitions with pre-condition guards.
    """

    def __init__(self, config: SchedulerConfig | None = None):
        self.config = config or SchedulerConfig()
        self._guards = {
            (LeadState.SENT, LeadState.FOLLOWUP_ACTIVE): TransitionGuard.sent_to_followup_active,
            (LeadState.FOLLOWUP_ACTIVE, LeadState.FOLLOWUP_ACTIVE): TransitionGuard.followup_active_to_next,
            (LeadState.SENT, LeadState.REPLIED): TransitionGuard.sent_to_replied,
            (LeadState.FOLLOWUP_ACTIVE, LeadState.REPLIED): TransitionGuard.sent_to_replied,
            (LeadState.NEW, LeadState.UNSUBSCRIBED): TransitionGuard.any_to_unsubscribed,
            (LeadState.DRAFT_PENDING, LeadState.UNSUBSCRIBED): TransitionGuard.any_to_unsubscribed,
            (LeadState.SCHEDULED, LeadState.UNSUBSCRIBED): TransitionGuard.any_to_unsubscribed,
            (LeadState.SENT, LeadState.UNSUBSCRIBED): TransitionGuard.any_to_unsubscribed,
            (LeadState.FOLLOWUP_ACTIVE, LeadState.UNSUBSCRIBED): TransitionGuard.any_to_unsubscribed,
            (LeadState.REPLIED, LeadState.UNSUBSCRIBED): TransitionGuard.any_to_unsubscribed,
            (LeadState.NEW, LeadState.BOUNCED): TransitionGuard.any_to_bounced,
            (LeadState.SCHEDULED, LeadState.BOUNCED): TransitionGuard.any_to_bounced,
            (LeadState.SENT, LeadState.BOUNCED): TransitionGuard.any_to_bounced,
        }

    def can_transition(self, from_state: LeadState, to_state: LeadState, lead: Lead) -> bool:
        """Check if transition is allowed (structural + guards)"""
        # Structural check
        if from_state in TERMINAL_STATES:
            return False
        if to_state not in TRANSITIONS.get(from_state, set()):
            return False

        # Guard check
        guard = self._guards.get((from_state, to_state))
        return not (guard and not guard(lead, self.config))

    def transition(self, lead: Lead, to_state: LeadState) -> bool:
        """
        Attempt transition, returning success.
        Does NOT persist - caller must update DB.
        """
        from_state = LeadState(lead.pipeline_state)

        if not self.can_transition(from_state, to_state, lead):
            return False

        lead.pipeline_state = to_state.value
        return True

    def get_valid_next_states(self, lead: Lead) -> list[LeadState]:
        """Get all valid next states for current lead"""
        current = LeadState(lead.pipeline_state)
        valid = TRANSITIONS.get(current, set())
        return [s for s in valid if self.can_transition(current, s, lead)]

    def force_transition(self, lead: Lead, to_state: LeadState) -> bool:
        """Force transition bypassing guards (admin only)"""
        from_state = LeadState(lead.pipeline_state)
        if from_state in TERMINAL_STATES:
            return False
        lead.pipeline_state = to_state.value
        return True


# Singleton instance
_pipeline: LeadPipeline | None = None


def get_pipeline() -> LeadPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = LeadPipeline()
    return _pipeline
