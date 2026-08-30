"""
Decline Phrase Detection
Deterministic hard-stop patterns - NO LLM involved.
If any pattern matches, intent = NOT_INTERESTED regardless of LLM output.
"""

import re

# Pattern: (regex, human_readable_label)
# Ordered by specificity - more specific patterns first
DECLINE_PATTERNS: list[tuple[str, str]] = [
    (r"\bwe\s+will\s+pass\s+on\s+this\s+opportunity\b", "We will pass on this opportunity"),
    (r"\bpass\s+on\s+this\s+opportunity\b", "Pass on this opportunity"),
    (r"\bwe\s+only\s+invest\s+in\b", "We only invest in"),
    (r"\bwe\s+only\s+do\b", "We only do"),
    # "we will pass" with negative lookahead to avoid "pass this along to team"
    (r"\bwe\s+will\s+pass\b(?!\s+(?:this|it|that|along)\s+(?:along|on|to|over)\b)", "We will pass"),
    (r"\bwe(?:'|'')\s*ll\s+pass\b(?!\s+(?:this|it|that|along)\s+(?:along|on|to|over)\b)", "We'll pass"),
    (r"\bnot\s+a\s+current\s+fit\b", "Not a current fit"),
    (r"\bnot\s+fit\s+for\s+us\b", "Not fit for us"),
    (r"\bno\s*,?\s*thank\s*(?:you|s)?\b", "No thank you"),
    (r"\bplease\s+share\s+a\s+detailed\s+deck\b", "Please share a detailed deck"),
    (r"\bpass\s+from\s+us\b", "Pass from us"),
    (r"\bpass\s+for\s+now\b", "Pass for now"),
    (r"\bnot\s+within\s+our\s+mandate\b", "Not within our mandate"),
    (r"\btoo\s+early\s+for\s+us\b", "Too early for us"),
    (r"\bnot\s+interested\b", "Not interested"),
    (r"\bwe\s+do\s+not\s+invest\b", "We do not invest"),
    (r"\bdecline\s+the\s+opportunity\b", "Decline the opportunity"),
    (r"\bnot\s+a\s+good\s+fit\b", "Not a good fit"),
]

# Compile patterns once at module load
_COMPILED_PATTERNS = [(re.compile(pattern, re.IGNORECASE), label) for pattern, label in DECLINE_PATTERNS]


def detect_decline_phrase(text: str | None) -> str | None:
    """
    Returns the readable label of the first decline phrase found in the reply text,
    or None if the text contains no known decline phrase.

    Matching is case-insensitive and robust to extra whitespace/punctuation.
    """
    if not text:
        return None

    # Normalize whitespace
    normalized = re.sub(r"\s+", " ", text).strip().lower()

    for pattern, label in _COMPILED_PATTERNS:
        if pattern.search(normalized):
            return label

    return None


def get_all_decline_patterns() -> list[tuple[str, str]]:
    """Return all patterns for testing/inspection"""
    return DECLINE_PATTERNS.copy()
