"""
Follow-up Engine
Pure logic: given lead + config → returns (should_send, subject, body, stage, campaign)
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from app.core.config import get_followup_settings, get_scheduler_config
from app.core.followup.campaign_resolver import CampaignResolver, LeadData


@dataclass
class FollowUpAction:
    """Result of follow-up evaluation"""
    should_send: bool
    reason: str = ""
    subject: str = ""
    body: str = ""
    stage: int = 0
    campaign: str = ""
    lead_type: str = "INVESTOR"
    max_stage: int = 3
    days_since_last: int = 0
    interval_required: int = 0


class FollowUpEngine:
    """
    Evaluates whether a lead is due for follow-up and prepares the email content.
    No side effects - pure function suitable for testing.
    """

    def __init__(self):
        self.followup_settings = get_followup_settings()
        self.scheduler_config = get_scheduler_config()
        self.campaign_resolver = CampaignResolver()

    def _get_lead_config(self, lead_type: str) -> dict:
        """Get max_stage and intervals for lead type"""
        if lead_type == "CLIENT":
            return {
                "max_stage": self.followup_settings.client_max_stage,
                "intervals": dict(
                    item.split(":") for item in self.followup_settings.client_intervals.split(",")
                ),
            }
        return {
            "max_stage": self.followup_settings.investor_max_stage,
            "intervals": dict(
                item.split(":") for item in self.followup_settings.investor_intervals.split(",")
            ),
        }

    def _is_defence(self, lead: LeadData) -> bool:
        """Check if lead is defence/deeptech (user requested no followups)"""
        defence_keywords = ["defence", "deeptech", "idex"]
        for field in [lead.original_subject, lead.email_draft, lead.persona, lead.sector]:
            if field and any(kw in field.lower() for kw in defence_keywords):
                return True
        return False

    def _get_last_outreach_ist(self, lead: dict) -> datetime | None:
        """Convert last_outreach_at to IST naive datetime"""
        last_sent = lead.get("last_outreach_at")
        if not last_sent:
            return None

        IST = timezone(timedelta(hours=5, minutes=30))
        if last_sent.tzinfo:
            return last_sent.astimezone(IST).replace(tzinfo=None)
        else:
            # Assume UTC if no timezone
            return last_sent.replace(tzinfo=UTC).astimezone(IST).replace(tzinfo=None)

    def evaluate(self, lead: dict) -> FollowUpAction:
        """
        Evaluate if lead is due for follow-up.
        Returns FollowUpAction with should_send=True if ready to send.
        """
        # Convert to LeadData for campaign resolver
        lead_data = LeadData(
            id=lead.get("id", 0),
            draft_template_used=lead.get("draft_template_used", "") or "",
            original_subject=lead.get("last_outreach_subject", "") or lead.get("first_outreach_subject", "") or "",
            email_draft=lead.get("email_draft", "") or "",
            persona=lead.get("persona", "") or "",
            sector=lead.get("sector", "") or "",
            sender_name=lead.get("sender_name", "") or lead.get("full_name", "") or "",
            sender_email=lead.get("sender_email", "") or "",
            lead_type=lead.get("lead_type", "INVESTOR") or "INVESTOR",
        )

        # 1. Working hours guard (followup scheduler: 8:30AM-8PM)
        if not self.scheduler_config.is_followup_working_hours_now():
            return FollowUpAction(
                should_send=False,
                reason="Outside followup working hours (8:30AM-8PM)",
                lead_type=lead_data.lead_type,
            )

        # 2. Stage limit check
        cfg = self._get_lead_config(lead_data.lead_type)
        current_stage = lead.get("followup_stage", 0) or 0

        if current_stage >= cfg["max_stage"]:
            return FollowUpAction(
                should_send=False,
                reason=f"Stage {current_stage} >= max {cfg['max_stage']} ({lead_data.lead_type})",
                lead_type=lead_data.lead_type,
                max_stage=cfg["max_stage"],
                stage=current_stage,
            )

        # 3. Interval check
        last_sent_ist = self._get_last_outreach_ist(lead)
        if not last_sent_ist:
            return FollowUpAction(
                should_send=False,
                reason="No last outreach timestamp",
                lead_type=lead_data.lead_type,
                stage=current_stage,
            )

        now = datetime.now(timezone(timedelta(hours=5, minutes=30))).replace(tzinfo=None)
        days_since_last = (now - last_sent_ist).days

        interval_days = cfg["intervals"].get(str(current_stage))
        if interval_days is None:
            return FollowUpAction(
                should_send=False,
                reason=f"No interval defined for stage {current_stage}",
                lead_type=lead_data.lead_type,
                stage=current_stage,
            )

        interval_days = int(interval_days)

        if days_since_last < interval_days:
            return FollowUpAction(
                should_send=False,
                reason=f"Interval not met: {days_since_last}/{interval_days} days",
                lead_type=lead_data.lead_type,
                stage=current_stage,
                days_since_last=days_since_last,
                interval_required=interval_days,
            )

        # 4. Defence skip
        if self._is_defence(lead_data):
            return FollowUpAction(
                should_send=False,
                reason="Defence campaign - skip per user request",
                lead_type=lead_data.lead_type,
                stage=current_stage,
            )

        # 5. Build email content
        next_stage = current_stage + 1
        campaign = self.campaign_resolver.resolve(lead_data)
        template = CampaignResolver.get_template(campaign, next_stage)

        lead_name = (lead.get("first_name") or "").strip() or "there"
        body = template.format(name=lead_name)
        subject = f"Re: {lead.get('last_outreach_subject', 'Following up')}"

        return FollowUpAction(
            should_send=True,
            reason="Ready to send",
            subject=subject,
            body=body,
            stage=next_stage,
            campaign=campaign,
            lead_type=lead_data.lead_type,
            max_stage=cfg["max_stage"],
            days_since_last=days_since_last,
            interval_required=interval_days,
        )

    def evaluate_legacy(self, lead: dict) -> FollowUpAction:
        """Legacy compatibility wrapper for dict-based leads"""
        # Convert dict to include computed fields
        lead_dict = dict(lead)
        return self.evaluate(lead_dict)


# Singleton
_engine: FollowUpEngine | None = None


def get_followup_engine() -> FollowUpEngine:
    global _engine
    if _engine is None:
        _engine = FollowUpEngine()
    return _engine
