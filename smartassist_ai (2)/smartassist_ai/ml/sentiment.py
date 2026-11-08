"""
Sentiment / Emotional-Tone Detector
------------------------------------
A lightweight, transparent lexicon + rule based polarity scorer.
Deliberately avoids heavyweight NLP dependencies (no corpus downloads)
so the whole system stays fast and fully local, matching the
"lightweight, interpretable" design goal in the project synopsis.
"""

from .preprocess import clean_text

POSITIVE_WORDS = {
    "thanks", "thank", "great", "good", "excellent", "awesome", "love",
    "happy", "pleased", "appreciate", "perfect", "amazing", "helpful",
    "wonderful", "fantastic", "nice", "easy", "smooth", "quick", "fast",
    "resolved", "works", "working", "satisfied", "glad", "cool",
}

NEGATIVE_WORDS = {
    "angry", "frustrated", "upset", "annoyed", "terrible", "awful",
    "horrible", "bad", "worst", "hate", "broken", "fail", "failed",
    "failing", "error", "bug", "crash", "crashed", "issue", "problem",
    "disappointed", "unacceptable", "useless", "slow", "stuck", "wrong",
    "never", "refund", "cancel", "cancelled", "complain", "complaint",
    "waiting", "delay", "delayed", "missing", "lost", "charged", "scam",
    "not working", "doesn't work", "unhappy", "furious", "ridiculous",
}

# Phrases that strongly signal urgency / distress regardless of the
# ML confidence score. Used by the priority scorer as well.
CRITICAL_KEYWORDS = {
    "urgent", "asap", "immediately", "emergency", "right now",
    "not working", "down", "outage", "hacked", "unauthorized",
    "fraud", "scam", "refund", "cancel my account", "legal",
    "lawyer", "furious", "extremely disappointed", "third time",
    "still not fixed", "money", "charged twice", "overcharged",
}

INTENSIFIERS = {"very", "extremely", "really", "so", "totally", "completely"}
NEGATORS = {"not", "no", "never", "cannot", "cant", "dont", "doesnt"}


def analyze_sentiment(text: str):
    """Return (label, score) where score is roughly in [-1, 1].

    label is one of "Positive", "Neutral", "Negative".
    """
    cleaned = clean_text(text)
    tokens = cleaned.split()

    score = 0.0
    intensifier_active = False

    for tok in tokens:
        weight = 1.0
        if tok in INTENSIFIERS:
            intensifier_active = True
            continue
        if tok in POSITIVE_WORDS:
            score += weight * (1.5 if intensifier_active else 1.0)
        elif tok in NEGATIVE_WORDS:
            score -= weight * (1.5 if intensifier_active else 1.0)
        intensifier_active = False

    # Phrase-level negative boosts (multi-word phrases won't show up
    # in the token loop above).
    for phrase in NEGATIVE_WORDS | CRITICAL_KEYWORDS:
        if " " in phrase and phrase in cleaned:
            score -= 1.0

    if len(tokens) > 0:
        normalized = max(-1.0, min(1.0, score / max(3, len(tokens))))
    else:
        normalized = 0.0

    if normalized > 0.12:
        label = "Positive"
    elif normalized < -0.12:
        label = "Negative"
    else:
        label = "Neutral"

    return label, round(normalized, 3)


def has_critical_keyword(text: str) -> bool:
    cleaned = clean_text(text)
    return any(kw in cleaned for kw in CRITICAL_KEYWORDS)
