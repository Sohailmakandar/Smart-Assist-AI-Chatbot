"""
ML / NLP Engine
----------------
Implements the classification pipeline described in the SmartAssist AI
synopsis (Chapter 4.2):

    Text Input -> Preprocessing -> TF-IDF Vectorization ->
    Multinomial Naive Bayes Classification -> Priority Scoring ->
    Result Output

The trained pipeline (vectorizer + classifier) is serialized with
``pickle`` so the Flask app never has to retrain on startup.
"""

import os
import pickle
import random

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

from .preprocess import preprocess_for_vectorizer
from .sentiment import analyze_sentiment, has_critical_keyword

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MODEL_PATH = os.path.join(MODEL_DIR, "smartassist_model.pkl")

INTENTS = ["Billing", "Technical Support", "Account Issues", "Order Tracking", "General FAQ"]

# ---------------------------------------------------------------------------
# 1. Seed training corpus (Chapter 4.2 - five support categories)
# ---------------------------------------------------------------------------
TRAINING_DATA = [
    # ---- Billing ----
    ("I was charged twice for my last subscription payment", "Billing"),
    ("Why is my invoice amount higher than usual this month", "Billing"),
    ("Can you explain the extra fee on my bill", "Billing"),
    ("I need a refund for a duplicate charge on my card", "Billing"),
    ("My credit card was billed but the payment failed on my end", "Billing"),
    ("How do I update my billing address and payment method", "Billing"),
    ("I want to cancel my subscription and get a prorated refund", "Billing"),
    ("The discount coupon was not applied to my invoice", "Billing"),
    ("Please send me a copy of last month's receipt", "Billing"),
    ("I am being charged for a plan I already cancelled", "Billing"),
    ("Is GST included in the subscription price", "Billing"),
    ("My payment is showing pending for three days now", "Billing"),
    ("Can I switch from monthly to yearly billing", "Billing"),
    ("There is an unauthorized charge on my account statement", "Billing"),
    ("How can I download my billing history as a PDF", "Billing"),
    ("I would like to dispute a charge on my invoice", "Billing"),
    ("My auto renewal charged me without notice", "Billing"),
    ("Do you offer student discounts on the premium plan", "Billing"),
    ("The price shown at checkout does not match my bill", "Billing"),
    ("I need an update on my pending refund request", "Billing"),
    ("Can you split my payment into installments", "Billing"),
    ("My free trial ended but I was still charged", "Billing"),

    # ---- Technical Support ----
    ("The app keeps crashing every time I open it", "Technical Support"),
    ("I cannot log in, the page just keeps loading forever", "Technical Support"),
    ("Getting an error 500 when I try to upload a file", "Technical Support"),
    ("The website is completely down for me right now", "Technical Support"),
    ("My dashboard is not loading any data at all", "Technical Support"),
    ("The mobile app freezes on the payment screen", "Technical Support"),
    ("I keep getting a sync error between devices", "Technical Support"),
    ("The search feature returns no results even for valid queries", "Technical Support"),
    ("Video calls keep dropping after a few minutes", "Technical Support"),
    ("I am unable to reset my password, the link is broken", "Technical Support"),
    ("Push notifications stopped working after the last update", "Technical Support"),
    ("The export button does nothing when I click it", "Technical Support"),
    ("My files failed to upload and I lost my progress", "Technical Support"),
    ("The app shows a blank white screen on startup", "Technical Support"),
    ("Two factor authentication code never arrives", "Technical Support"),
    ("The system logs me out randomly every few minutes", "Technical Support"),
    ("I found a bug where the totals do not add up correctly", "Technical Support"),
    ("Dark mode is broken and text is unreadable", "Technical Support"),
    ("The integration with our calendar keeps failing", "Technical Support"),
    ("My API requests are returning a 401 unauthorized error", "Technical Support"),
    ("The service has been down for over an hour", "Technical Support"),
    ("Uploading images larger than 5MB always fails", "Technical Support"),

    # ---- Account Issues ----
    ("I forgot my account password and cannot recover it", "Account Issues"),
    ("How do I change the email address linked to my account", "Account Issues"),
    ("My account was suspended and I do not know why", "Account Issues"),
    ("I want to delete my account and all my data permanently", "Account Issues"),
    ("Can I merge two accounts into one profile", "Account Issues"),
    ("Someone else may have accessed my account without permission", "Account Issues"),
    ("How do I update my profile picture and display name", "Account Issues"),
    ("I need to change my username but the option is missing", "Account Issues"),
    ("My account got locked after too many login attempts", "Account Issues"),
    ("How can I add a family member to my account plan", "Account Issues"),
    ("I am not receiving the account verification email", "Account Issues"),
    ("Please help me recover my account, it was hacked", "Account Issues"),
    ("How do I enable two factor authentication for my account", "Account Issues"),
    ("Can you transfer my account to a new phone number", "Account Issues"),
    ("My account shows the wrong subscription tier", "Account Issues"),
    ("I need to update my privacy and notification settings", "Account Issues"),
    ("How do I change my registered mobile number", "Account Issues"),
    ("My account was deactivated without any warning", "Account Issues"),
    ("I cannot find the option to close my account", "Account Issues"),
    ("Please restore my account, it was deleted by mistake", "Account Issues"),

    # ---- Order Tracking ----
    ("Where is my order, it has not arrived yet", "Order Tracking"),
    ("Can you tell me the tracking number for my last order", "Order Tracking"),
    ("My package shows delivered but I never received it", "Order Tracking"),
    ("I want to change the delivery address for my order", "Order Tracking"),
    ("The order status has not updated in five days", "Order Tracking"),
    ("How long will shipping take for my recent purchase", "Order Tracking"),
    ("I need to cancel my order before it ships", "Order Tracking"),
    ("My order arrived damaged, how do I get a replacement", "Order Tracking"),
    ("Can I track multiple orders at the same time", "Order Tracking"),
    ("The courier attempted delivery but no one contacted me", "Order Tracking"),
    ("I received the wrong item in my order", "Order Tracking"),
    ("When will my order be shipped out", "Order Tracking"),
    ("I would like to return an item from my recent order", "Order Tracking"),
    ("My order is stuck at the same location for a week", "Order Tracking"),
    ("Can I expedite shipping on an order I already placed", "Order Tracking"),
    ("The estimated delivery date keeps changing", "Order Tracking"),
    ("I need a replacement for a missing item in my order", "Order Tracking"),
    ("Is same day delivery available in my area", "Order Tracking"),
    ("My order confirmation email never arrived", "Order Tracking"),
    ("How do I check if my return has been processed", "Order Tracking"),

    # ---- General FAQ ----
    ("What are your customer support working hours", "General FAQ"),
    ("Do you have a mobile app for Android and iOS", "General FAQ"),
    ("What is your data privacy and security policy", "General FAQ"),
    ("How do I contact your support team directly", "General FAQ"),
    ("What payment methods do you accept", "General FAQ"),
    ("Is there a free trial available for new users", "General FAQ"),
    ("Where can I read your terms and conditions", "General FAQ"),
    ("Do you offer discounts for students or nonprofits", "General FAQ"),
    ("What languages does the platform support", "General FAQ"),
    ("How do I get started as a new user", "General FAQ"),
    ("Can I use this service outside my home country", "General FAQ"),
    ("What is included in the free plan", "General FAQ"),
    ("Do you have an affiliate or referral program", "General FAQ"),
    ("How can I provide feedback about your product", "General FAQ"),
    ("What browsers are supported by your platform", "General FAQ"),
    ("Is my data backed up automatically", "General FAQ"),
    ("How do I unsubscribe from marketing emails", "General FAQ"),
    ("Can I integrate this with other tools I use", "General FAQ"),
    ("What happens to my data if I close my account", "General FAQ"),
    ("Where can I find your API documentation", "General FAQ"),
]

# ---------------------------------------------------------------------------
# 2. Canned resolution responses per intent (Knowledge Base)
# ---------------------------------------------------------------------------
RESPONSE_TEMPLATES = {
    "Billing": [
        "I've located your billing details. Duplicate charges and pending "
        "payments are usually reversed automatically within 3-5 business "
        "days. I've logged a billing review ticket for your account.",
        "Thanks for flagging this billing concern. I can see your invoice "
        "history — a refund or adjustment request has been queued for "
        "our finance team to verify.",
    ],
    "Technical Support": [
        "Sorry about the trouble. I've logged this as a technical issue. "
        "Try clearing your app cache and reloading — if it persists, our "
        "engineering queue will pick this up with priority.",
        "That sounds like a bug on our end. I've recorded the details "
        "(device, error, and time) and routed it to the technical team "
        "for investigation.",
    ],
    "Account Issues": [
        "I can help with your account. For security, sensitive changes "
        "(password resets, email updates) are verified through your "
        "registered email — check your inbox for a secure link.",
        "Got it — I've flagged this account request. If it involves "
        "recovery or suspicious access, our account-security team will "
        "reach out within one business day.",
    ],
    "Order Tracking": [
        "Let me check that for you. Orders typically update every 24 "
        "hours — I've pulled the latest tracking status and forwarded a "
        "delivery investigation request to logistics.",
        "Thanks for the details. I've flagged this order for our "
        "fulfillment team so they can confirm the delivery status and "
        "follow up if anything looks off.",
    ],
    "General FAQ": [
        "Great question! Here's a quick answer based on our knowledge "
        "base — if you need more detail, our documentation covers this "
        "topic in depth, and I'm happy to point you there.",
        "Thanks for asking. This is a common question — I've shared the "
        "relevant info from our help center, let me know if anything's "
        "unclear.",
    ],
}

ESCALATION_NOTE = (
    " This conversation has been escalated to a human support agent "
    "who will follow up shortly."
)


def _build_pipeline() -> Pipeline:
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=5000,
        stop_words="english",
        preprocessor=preprocess_for_vectorizer,
    )
    classifier = MultinomialNB(alpha=0.1)
    return Pipeline([("tfidf", vectorizer), ("nb", classifier)])


def train_and_save(path: str = MODEL_PATH, extra_samples=None) -> Pipeline:
    """Train the TF-IDF + Multinomial Naive Bayes pipeline and pickle it.

    ``extra_samples``: optional list of (text, label) tuples — used by the
    admin "Retrain from corrections" workflow so the model literally
    learns from its own past misclassifications.
    """
    data = list(TRAINING_DATA)
    if extra_samples:
        data.extend(extra_samples)

    texts = [t for t, _ in data]
    labels = [l for _, l in data]

    pipeline = _build_pipeline()
    pipeline.fit(texts, labels)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(pipeline, f)

    global _PIPELINE
    _PIPELINE = pipeline
    return pipeline


def retrain_with_corrections(correction_pairs) -> dict:
    """Retrain the classifier, folding in admin-corrected (text, intent)
    pairs as extra labeled examples. Returns a small report dict."""
    valid_pairs = [(t, l) for t, l in correction_pairs if l in INTENTS]
    train_and_save(extra_samples=valid_pairs)
    return {
        "base_samples": len(TRAINING_DATA),
        "correction_samples_used": len(valid_pairs),
        "total_samples": len(TRAINING_DATA) + len(valid_pairs),
    }


_PIPELINE = None


def load_model(path: str = MODEL_PATH) -> Pipeline:
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE
    if not os.path.exists(path):
        _PIPELINE = train_and_save(path)
    else:
        with open(path, "rb") as f:
            _PIPELINE = pickle.load(f)
    return _PIPELINE


def predict_intent(text: str):
    """Return (intent, confidence, probability_dict)."""
    pipeline = load_model()
    proba = pipeline.predict_proba([text])[0]
    classes = pipeline.classes_
    prob_dict = {cls: round(float(p), 4) for cls, p in zip(classes, proba)}
    best_idx = proba.argmax()
    intent = classes[best_idx]
    confidence = round(float(proba[best_idx]), 4)
    return intent, confidence, prob_dict


def score_priority(confidence: float, sentiment_label: str, text: str):
    """Rule-based urgency scorer combining ML confidence, sentiment and
    critical-keyword detection (Figure 1.1: 'Rules + Confidence').

    Returns (urgency_level, escalate: bool, points: int) for transparency.
    """
    points = 0

    if confidence < 0.50:
        points += 3
    elif confidence < 0.65:
        points += 2
    elif confidence < 0.80:
        points += 1

    if sentiment_label == "Negative":
        points += 2
    elif sentiment_label == "Positive":
        points -= 1

    critical = has_critical_keyword(text)
    if critical:
        points += 3

    if points >= 6:
        urgency = "Critical"
    elif points >= 4:
        urgency = "High"
    elif points >= 2:
        urgency = "Normal"
    else:
        urgency = "Low"

    escalate = confidence < 0.60 or urgency == "Critical"
    return urgency, escalate, points


def generate_response(intent: str, escalate: bool) -> str:
    template = random.choice(RESPONSE_TEMPLATES.get(intent, RESPONSE_TEMPLATES["General FAQ"]))
    if escalate:
        template += ESCALATION_NOTE
    return template


def classify_message(text: str):
    """Full pipeline used by the /api/chat endpoint.

    Text Input -> Preprocessing -> TF-IDF -> Naive Bayes ->
    Sentiment -> Priority Scoring -> Escalation -> Response
    """
    intent, confidence, prob_dict = predict_intent(text)
    sentiment_label, sentiment_score = analyze_sentiment(text)
    urgency, escalate, points = score_priority(confidence, sentiment_label, text)
    response = generate_response(intent, escalate)

    return {
        "intent": intent,
        "confidence": confidence,
        "probabilities": prob_dict,
        "sentiment": sentiment_label,
        "sentiment_score": sentiment_score,
        "urgency": urgency,
        "escalated": escalate,
        "priority_points": points,
        "response": response,
    }


if __name__ == "__main__":
    # Allows manual retraining: python -m ml.classifier
    train_and_save()
    print(f"Model trained on {len(TRAINING_DATA)} samples across {len(INTENTS)} intents.")
