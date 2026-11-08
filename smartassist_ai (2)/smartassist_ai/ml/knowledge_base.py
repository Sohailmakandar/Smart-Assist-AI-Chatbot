"""
Knowledge Base
----------------
A small static FAQ set surfaced in the user-facing "Browse FAQs" panel
and via the ``/api/faq`` endpoint. Kept as plain data (not a DB table)
since it changes rarely and is meant to be quickly editable here.
"""

FAQ_ITEMS = [
    {
        "category": "Billing",
        "question": "How do I get a refund for a duplicate charge?",
        "answer": "Duplicate charges are usually reversed automatically within 3-5 business days. If you don't see it, message us and we'll open a billing review ticket.",
    },
    {
        "category": "Billing",
        "question": "Can I switch from monthly to yearly billing?",
        "answer": "Yes — open Account Settings > Billing > Plan, and choose the yearly option. The switch is prorated against your current cycle.",
    },
    {
        "category": "Technical Support",
        "question": "The app crashes on startup — what should I try first?",
        "answer": "Clear the app cache, confirm you're on the latest version, and restart the app. If it still crashes, tell us your device and OS version so we can investigate.",
    },
    {
        "category": "Technical Support",
        "question": "Why am I not receiving the 2FA code?",
        "answer": "Check that your registered number/email is correct, and that SMS/email delivery isn't delayed. You can also switch to an authenticator app under Security Settings.",
    },
    {
        "category": "Account Issues",
        "question": "How do I change the email linked to my account?",
        "answer": "Go to Profile > Account > Email, enter the new address, and confirm via the verification link we send to it.",
    },
    {
        "category": "Account Issues",
        "question": "My account got locked after failed login attempts — now what?",
        "answer": "Wait 15 minutes and try again, or use 'Forgot password' to reset it immediately. If it's still locked, message us and we'll unlock it manually.",
    },
    {
        "category": "Order Tracking",
        "question": "My order status hasn't updated in days — is that normal?",
        "answer": "Tracking updates roughly every 24 hours. If it's been stuck for 3+ days, let us know the order number and we'll open a delivery investigation with the courier.",
    },
    {
        "category": "Order Tracking",
        "question": "Can I change my delivery address after ordering?",
        "answer": "Yes, as long as the order hasn't shipped yet. Share your order number in chat and we'll update it right away.",
    },
    {
        "category": "General FAQ",
        "question": "What are your support hours?",
        "answer": "Our chatbot is available 24/7. Human agents are online Monday-Saturday, 9 AM - 9 PM IST, with critical issues triaged around the clock.",
    },
    {
        "category": "General FAQ",
        "question": "Is my data backed up automatically?",
        "answer": "Yes, all account and order data is backed up continuously. You can also request a full data export from Account Settings > Privacy.",
    },
]


def get_faq(category=None):
    if not category or category == "All":
        return FAQ_ITEMS
    return [item for item in FAQ_ITEMS if item["category"] == category]
