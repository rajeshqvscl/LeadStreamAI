"""
Reply Classifier
Combines deterministic decline phrase detection with LLM classification.
"""

from dataclasses import dataclass
from typing import Any

from app.core.config import get_llm_settings
from app.core.reply.decline_phrases import detect_decline_phrase


@dataclass
class ClassificationResult:
    intent: str  # MEETING_REQUESTED, INTERESTED, NEEDS_MORE_INFO, NOT_INTERESTED, UNKNOWN
    source: str  # DECLINE_PHRASE, LLM, FALLBACK
    sentiment_score: int = 0
    urgency_level: str = "MEDIUM"
    deal_size: str | None = None
    rejection_reason: str | None = None
    confidence: float = 1.0
    raw_llm_output: dict[str, Any] | None = None


# JSON Schema for structured LLM output
REPLY_CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["MEETING_REQUESTED", "INTERESTED", "NEEDS_MORE_INFO", "NOT_INTERESTED"]
        },
        "deal_size": {"type": ["string", "null"]},
        "has_pitch_deck": {"type": "boolean"},
        "pitch_deck_url": {"type": ["string", "null"]},
        "sentiment_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "urgency_level": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
        "proposed_meeting_date": {"type": ["string", "null"]},
        "proposed_meeting_text": {"type": ["string", "null"]},
        "rejection_reason": {"type": ["string", "null"]},
    },
    "required": ["intent", "sentiment_score", "urgency_level"],
    "additionalProperties": False,
}


REPLY_CLASSIFICATION_PROMPT = """
Analyze this email reply from a potential investor/client and extract details in JSON format.

CRITICAL RULES:
1. Identify the new response/reply at the very beginning/top of the text. Ignore any quoted historical thread or original outreach text trailing after it.
2. If the lead declines the opportunity in the new reply—even in a short sentence like "Pass from us", "Pass for now", "Not interested", "Not within our mandate", "Too early for us", "No thank you", "We will pass", "Not fit for us", "No, thankyou", "not a current fit for us", "We will pass on this opportunity", "we only invest in", "we only do", "Please share a detailed deck", "We will pass. Thanks for sharing."—you MUST classify the intent as "NOT_INTERESTED" and set the sentiment_score between 0 and 20.
3. Do NOT let the details of the original outreach email (which is positive) confuse you. Focus 100% on the lead's new reply at the top.
4. CRITICAL — deal_size: Extract the ticket size, investment range, check size, or revenue criteria (MONETARY VALUES ONLY, e.g., '$1M', '$500K-$1M', 'INR 100 cr+', '10-20 Cr') explicitly mentioned in the lead's NEW reply (the top part). Crucially: DO NOT include stage names like 'Series A', 'Series B', 'Seed', or 'Pre-Seed' — only extract numeric monetary values/ranges. If none is mentioned, set null.
5. CRITICAL — pitch_deck_url: ONLY set if the lead's NEW reply explicitly includes a URL or attachment reference. Do not fabricate or copy from the quoted thread.

REPLY TEXT:
{reply_text}

Return ONLY valid JSON matching the schema.
"""


class ReplyClassifier:
    """
    Classifies lead replies into intent categories.
    Uses deterministic decline phrases as first-pass, then LLM as fallback.
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self._llm_available = llm_client is not None

    def classify(self, body: str) -> ClassificationResult:
        """
        Classify a reply body.

        Priority:
        1. Deterministic decline phrase detection (100% confidence)
        2. LLM classification with structured output
        3. Safe fallback (UNKNOWN intent -> ACTIVE followup)
        """
        # 1. Deterministic override FIRST - no LLM needed
        decline = detect_decline_phrase(body)
        if decline:
            return ClassificationResult(
                intent="NOT_INTERESTED",
                source="DECLINE_PHRASE",
                rejection_reason=decline,
                sentiment_score=10,
                confidence=1.0,
            )

        # 2. LLM classification
        if self._llm_available:
            try:
                return self._classify_with_llm(body)
            except Exception as e:
                # Log and fall through to fallback
                import logging
                logging.getLogger(__name__).warning(f"LLM classification failed: {e}")

        # 3. Safe fallback - UNKNOWN intent keeps sequence ACTIVE for manual review
        return ClassificationResult(
            intent=None,  # Maps to ACTIVE in workflow
            source="FALLBACK",
            sentiment_score=50,
            confidence=0.0,
        )

    def _classify_with_llm(self, body: str) -> ClassificationResult:
        """Call LLM with structured output"""
        import json
        import logging
        _log = logging.getLogger(__name__)

        prompt = REPLY_CLASSIFICATION_PROMPT.format(reply_text=body)

        settings = get_llm_settings()

        # Try Groq first
        if settings.groq_api_key:
            try:
                from groq import Groq
                client = Groq(api_key=settings.groq_api_key)
                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=settings.groq_model,
                    max_tokens=512,
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
                result = json.loads(response.choices[0].message.content)
                return self._parse_llm_result(result, body)
            except Exception as e:
                _log.debug(f"Groq classification failed: {e}")

        # Try Gemini
        if settings.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.gemini_api_key)
                model = genai.GenerativeModel(settings.gemini_model)
                response = model.generate_content(prompt)
                result = json.loads(response.text)
                return self._parse_llm_result(result, body)
            except Exception as e:
                _log.debug(f"Gemini classification failed: {e}")

        # Try Anthropic
        if settings.anthropic_api_key:
            try:
                from anthropic import Anthropic
                client = Anthropic(api_key=settings.anthropic_api_key)
                response = client.messages.create(
                    model=settings.claude_model,
                    max_tokens=512,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}],
                )
                result = json.loads(response.content[0].text)
                return self._parse_llm_result(result, body)
            except Exception as e:
                _log.debug(f"Anthropic classification failed: {e}")

        # All LLMs failed
        return ClassificationResult(
            intent=None,
            source="FALLBACK",
            sentiment_score=50,
            confidence=0.0,
        )

    def _parse_llm_result(self, result: dict, body: str) -> ClassificationResult:
        """Parse and validate LLM result"""
        intent = result.get("intent")

        # Validate intent
        valid_intents = ["MEETING_REQUESTED", "INTERESTED", "NEEDS_MORE_INFO", "NOT_INTERESTED"]
        if intent not in valid_intents:
            intent = None

        # Extract fields with defaults
        sentiment = result.get("sentiment_score", 50)
        if not isinstance(sentiment, int):
            sentiment = 50

        return ClassificationResult(
            intent=intent,
            source="LLM",
            sentiment_score=max(0, min(100, sentiment)),
            urgency_level=result.get("urgency_level", "MEDIUM"),
            deal_size=result.get("deal_size"),
            rejection_reason=result.get("rejection_reason"),
            confidence=0.9,
            raw_llm_output=result,
        )


# Singleton
_classifier: ReplyClassifier | None = None


def get_reply_classifier() -> ReplyClassifier:
    global _classifier
    if _classifier is None:
        _classifier = ReplyClassifier()
    return _classifier
