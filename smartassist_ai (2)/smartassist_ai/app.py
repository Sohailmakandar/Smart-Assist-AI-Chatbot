"""
SmartAssist AI - Main Application Server
==========================================
Flask routes, request handling, REST APIs.

An Intelligent Customer Service Chatbot and Support Management System
Using Machine Learning and Natural Language Processing — now extended
with a personal expense tracker, notifications, login history, incidents,
product feedback, and an admin correction/retraining workflow.

Run with:  python app.py
Then open: http://127.0.0.1:5000
"""

from flask import Flask, Response, render_template, request, jsonify
from datetime import datetime

from ml.classifier import classify_message, predict_intent, retrain_with_corrections, INTENTS
from ml.knowledge_base import get_faq, FAQ_ITEMS
from ml import expense_insights
from models import database as db

app = Flask(__name__)

URGENCY_LEVELS = ["Critical", "High", "Normal", "Low"]
STATUS_OPTIONS = ["Open", "Pending", "Resolved"]
FAQ_CATEGORIES = ["All"] + sorted({item["category"] for item in FAQ_ITEMS})


# ---------------------------------------------------------------------------
# Startup: ensure DB + ML model exist
# ---------------------------------------------------------------------------
def bootstrap():
    db.init_db()
    predict_intent("hello")  # warms / trains the model cache
    db.seed_demo_data()


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        intents=INTENTS,
        faq_categories=FAQ_CATEGORIES,
        expense_categories=db.EXPENSE_CATEGORIES,
        active_page="chat",
    )


@app.route("/dashboard")
def dashboard():
    return render_template(
        "dashboard.html",
        intents=["All"] + INTENTS,
        all_intents=INTENTS,
        urgencies=["All"] + URGENCY_LEVELS,
        statuses=["All"] + STATUS_OPTIONS,
        agents=["All"] + db.AGENTS,
        assign_agents=db.AGENTS,
        active_page="dashboard",
    )


# ---------------------------------------------------------------------------
# REST API - User identity, profile, login history
# ---------------------------------------------------------------------------
@app.route("/api/users/login", methods=["POST"])
def api_user_login():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()

    if not name or not email:
        return jsonify({"error": "Name and email are required."}), 400
    if "@" not in email:
        return jsonify({"error": "Please enter a valid email address."}), 400

    user = db.get_or_create_user(name, email)
    if user["is_blocked"]:
        return jsonify({"error": "This account has been blocked by an administrator."}), 403

    db.record_login(user["id"])
    return jsonify({"user": user})


@app.route("/api/users/<int:user_id>/history", methods=["GET"])
def api_user_history(user_id):
    tickets = db.get_user_ticket_history(user_id)
    return jsonify({"tickets": tickets, "count": len(tickets)})


@app.route("/api/users/<int:user_id>/profile", methods=["GET"])
def api_user_profile(user_id):
    profile = db.get_user_profile(user_id)
    if not profile:
        return jsonify({"error": "User not found."}), 404
    return jsonify({"profile": profile})


@app.route("/api/users/<int:user_id>/profile", methods=["POST"])
def api_update_user_profile(user_id):
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name cannot be empty."}), 400

    success = db.update_user_name(user_id, name)
    if not success:
        return jsonify({"error": "User not found."}), 404
    return jsonify({"success": True})


@app.route("/api/users/<int:user_id>/login-history", methods=["GET"])
def api_login_history(user_id):
    return jsonify({"history": db.get_login_history(user_id)})


# ---------------------------------------------------------------------------
# REST API - Chat / Classification
# ---------------------------------------------------------------------------
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    user_name = (data.get("user_name") or "Guest").strip() or "Guest"
    user_id = data.get("user_id")

    if not message:
        return jsonify({"error": "Message text is required."}), 400

    if user_id and db.is_user_blocked(user_id):
        return jsonify({"error": "This account has been blocked by an administrator."}), 403

    result = classify_message(message)

    ticket_id = db.insert_chat(
        user_name=user_name,
        query_text=message,
        response_text=result["response"],
        intent=result["intent"],
        confidence=result["confidence"],
        sentiment=result["sentiment"],
        urgency_level=result["urgency"],
        is_escalated=result["escalated"],
        user_id=user_id,
    )

    result["ticket_id"] = ticket_id
    return jsonify(result)


@app.route("/api/chat/<int:chat_id>/feedback", methods=["POST"])
def api_chat_feedback(chat_id):
    data = request.get_json(silent=True) or {}
    rating = data.get("rating")
    if rating not in (1, -1):
        return jsonify({"error": "rating must be 1 or -1"}), 400

    success = db.set_chat_rating(chat_id, rating)
    if not success:
        return jsonify({"error": "Chat not found."}), 404
    return jsonify({"success": True})


@app.route("/api/live-preview", methods=["POST"])
def api_live_preview():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text or len(text) < 3:
        return jsonify({"intent": None, "confidence": 0, "probabilities": {}})

    intent, confidence, prob_dict = predict_intent(text)
    return jsonify({"intent": intent, "confidence": confidence, "probabilities": prob_dict})


# ---------------------------------------------------------------------------
# REST API - FAQ / Knowledge base
# ---------------------------------------------------------------------------
@app.route("/api/faq", methods=["GET"])
def api_faq():
    category = request.args.get("category", "All")
    return jsonify({"faq": get_faq(category)})


# ---------------------------------------------------------------------------
# REST API - Incidents (user side: escalated / critical / high tickets)
# ---------------------------------------------------------------------------
@app.route("/api/incidents", methods=["GET"])
def api_incidents():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id is required."}), 400
    return jsonify({"incidents": db.get_user_incidents(user_id)})


@app.route("/api/incidents/<int:chat_id>/update", methods=["POST"])
def api_incident_update(chat_id):
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message is required."}), 400

    update_id = db.add_incident_update(chat_id, user_id, message)
    return jsonify({"success": True, "update_id": update_id})


# ---------------------------------------------------------------------------
# REST API - Product feedback (user side, star rating + comment)
# ---------------------------------------------------------------------------
@app.route("/api/feedback", methods=["POST"])
def api_submit_feedback():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    rating = data.get("rating")
    comment = (data.get("comment") or "").strip()[:1000]

    if rating not in (1, 2, 3, 4, 5):
        return jsonify({"error": "rating must be between 1 and 5."}), 400

    feedback_id = db.add_feedback(user_id, rating, comment)
    return jsonify({"success": True, "feedback_id": feedback_id})


@app.route("/api/admin/feedback", methods=["GET"])
def api_admin_feedback():
    return jsonify({"feedback": db.get_feedback(), "stats": db.get_feedback_stats()})


# ---------------------------------------------------------------------------
# REST API - Notifications (user side)
# ---------------------------------------------------------------------------
@app.route("/api/notifications", methods=["GET"])
def api_notifications():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id is required."}), 400
    notifications = db.get_notifications(user_id)
    unread = db.unread_notification_count(user_id)
    return jsonify({"notifications": notifications, "unread_count": unread})


@app.route("/api/notifications/<int:notification_id>/read", methods=["POST"])
def api_notification_read(notification_id):
    db.mark_notification_read(notification_id)
    return jsonify({"success": True})


@app.route("/api/notifications/read-all", methods=["POST"])
def api_notifications_read_all():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required."}), 400
    db.mark_all_notifications_read(user_id)
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# REST API - Expenses (Personal Daily Expenditure Tracker)
# ---------------------------------------------------------------------------
@app.route("/api/expenses", methods=["POST"])
def api_add_expense():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    category = data.get("category")
    amount = data.get("amount")
    note = (data.get("note") or "").strip()[:200]
    spent_at = data.get("spent_at")  # optional "YYYY-MM-DD HH:MM:SS"

    if not user_id:
        return jsonify({"error": "user_id is required."}), 400
    if category not in db.EXPENSE_CATEGORIES:
        return jsonify({"error": f"category must be one of {db.EXPENSE_CATEGORIES}"}), 400
    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be a positive number."}), 400

    expense = db.add_expense(user_id, category, amount, note, spent_at)

    todays = [e for e in db.get_user_expenses(user_id, days=1)]
    insight = expense_insights.generate_entry_insight(expense, todays)

    db.create_notification(
        user_id, "Transaction recorded",
        f"₹{amount:,.0f} logged under {category}." + (f" Note: {note}" if note else ""),
        "success",
    )

    return jsonify({"expense": expense, "insight": insight})


@app.route("/api/expenses", methods=["GET"])
def api_get_expenses():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id is required."}), 400

    expenses = db.get_user_expenses(user_id)
    summary = expense_insights.summarize(expenses)
    recommendations = expense_insights.generate_recommendations(expenses)

    return jsonify({
        "expenses": expenses[:50],
        "summary": summary,
        "recommendations": recommendations,
        "categories": db.EXPENSE_CATEGORIES,
    })


@app.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
def api_delete_expense(expense_id):
    """Soft delete — moves the expense into the user's Recycle Bin."""
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id is required."}), 400
    success = db.delete_expense(expense_id, user_id)
    if not success:
        return jsonify({"error": "Expense not found."}), 404
    return jsonify({"success": True})


@app.route("/api/expenses/recycle-bin", methods=["GET"])
def api_recycle_bin():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id is required."}), 400
    return jsonify({"expenses": db.get_deleted_expenses(user_id)})


@app.route("/api/expenses/<int:expense_id>/restore", methods=["POST"])
def api_restore_expense(expense_id):
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required."}), 400
    success = db.restore_expense(expense_id, user_id)
    if not success:
        return jsonify({"error": "Expense not found in Recycle Bin."}), 404
    return jsonify({"success": True})


@app.route("/api/expenses/<int:expense_id>/permanent", methods=["DELETE"])
def api_permanently_delete_expense(expense_id):
    data = request.get_json(silent=True) or {}
    user_id = request.args.get("user_id", type=int) or data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required."}), 400
    success = db.permanently_delete_expense(expense_id, user_id)
    if not success:
        return jsonify({"error": "Expense not found in Recycle Bin."}), 404
    return jsonify({"success": True})


@app.route("/api/expenses/invoice", methods=["GET"])
def api_expense_invoice():
    user_id = request.args.get("user_id", type=int)
    period = request.args.get("period", "monthly")
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    if not user_id:
        return jsonify({"error": "user_id is required."}), 400

    profile = db.get_user_profile(user_id)
    if not profile:
        return jsonify({"error": "User not found."}), 404

    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month

    try:
        invoice = expense_insights.build_invoice(profile, period, year, month)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"invoice": invoice})


@app.route("/api/admin/expenses/overview", methods=["GET"])
def api_admin_expense_overview():
    return jsonify(db.get_admin_expense_overview())


# ---------------------------------------------------------------------------
# REST API - Tickets / Escalation console (admin side)
# ---------------------------------------------------------------------------
@app.route("/api/tickets", methods=["GET"])
def api_get_tickets():
    status = request.args.get("status", "All")
    urgency = request.args.get("urgency", "All")
    intent = request.args.get("intent", "All")
    agent = request.args.get("agent", "All")
    search = request.args.get("search", "").strip()

    tickets = db.get_tickets(status=status, urgency=urgency, intent=intent, agent=agent, search=search or None)
    return jsonify({"tickets": tickets, "count": len(tickets)})


@app.route("/api/tickets/<int:ticket_id>/status", methods=["POST"])
def api_update_ticket_status(ticket_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in STATUS_OPTIONS:
        return jsonify({"error": f"status must be one of {STATUS_OPTIONS}"}), 400

    success = db.update_ticket_status(ticket_id, new_status)
    if not success:
        return jsonify({"error": "Ticket not found."}), 404
    return jsonify({"success": True, "ticket_id": ticket_id, "status": new_status})


@app.route("/api/tickets/<int:ticket_id>/assign", methods=["POST"])
def api_assign_ticket(ticket_id):
    data = request.get_json(silent=True) or {}
    agent = (data.get("agent") or "").strip()
    if agent not in db.AGENTS:
        return jsonify({"error": f"agent must be one of {db.AGENTS}"}), 400

    success = db.assign_ticket_agent(ticket_id, agent)
    if not success:
        return jsonify({"error": "Ticket not found."}), 404
    return jsonify({"success": True, "ticket_id": ticket_id, "agent": agent})


@app.route("/api/tickets/<int:ticket_id>/notes", methods=["POST"])
def api_ticket_notes(ticket_id):
    data = request.get_json(silent=True) or {}
    notes = (data.get("notes") or "").strip()[:2000]

    success = db.update_ticket_notes(ticket_id, notes)
    if not success:
        return jsonify({"error": "Ticket not found."}), 404
    return jsonify({"success": True, "ticket_id": ticket_id})


@app.route("/api/tickets/<int:ticket_id>/correct", methods=["POST"])
def api_correct_ticket(ticket_id):
    """Admin relabels a misclassified ticket. Stored as a training
    correction so the model can be retrained on its own mistakes."""
    data = request.get_json(silent=True) or {}
    corrected_intent = data.get("corrected_intent")
    corrected_by = (data.get("corrected_by") or "Admin").strip()

    if corrected_intent not in INTENTS:
        return jsonify({"error": f"corrected_intent must be one of {INTENTS}"}), 400

    correction_id = db.add_correction(ticket_id, corrected_intent, corrected_by)
    if not correction_id:
        return jsonify({"error": "Ticket not found."}), 404
    return jsonify({"success": True, "correction_id": correction_id})


@app.route("/api/admin/corrections", methods=["GET"])
def api_admin_corrections():
    return jsonify({"corrections": db.get_corrections()})


@app.route("/api/admin/retrain", methods=["POST"])
def api_admin_retrain():
    """Fold every admin correction back into the training set and
    retrain the classifier — the 'learns from its mistakes' loop."""
    pairs = db.get_correction_training_pairs()
    report = retrain_with_corrections(pairs)
    return jsonify({"success": True, "report": report})


@app.route("/api/tickets/export", methods=["GET"])
def api_export_tickets():
    csv_data = db.export_tickets_csv()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=smartassist_tickets.csv"},
    )


# ---------------------------------------------------------------------------
# REST API - Users management (admin side)
# ---------------------------------------------------------------------------
@app.route("/api/admin/users", methods=["GET"])
def api_admin_users():
    search = request.args.get("search", "").strip()
    users = db.list_users(search=search or None)
    return jsonify({"users": users, "count": len(users)})


@app.route("/api/admin/users/<int:user_id>", methods=["GET"])
def api_admin_user_detail(user_id):
    user = db.get_user_with_tickets(user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404
    return jsonify({"user": user})


@app.route("/api/admin/users/<int:user_id>/block", methods=["POST"])
def api_admin_block_user(user_id):
    data = request.get_json(silent=True) or {}
    blocked = bool(data.get("blocked", True))

    success = db.set_user_blocked(user_id, blocked)
    if not success:
        return jsonify({"error": "User not found."}), 404
    return jsonify({"success": True, "user_id": user_id, "is_blocked": blocked})


# ---------------------------------------------------------------------------
# REST API - Analytics
# ---------------------------------------------------------------------------
@app.route("/api/stats", methods=["GET"])
def api_stats():
    return jsonify(db.get_stats())


# ---------------------------------------------------------------------------
# REST API - Meta / About
# ---------------------------------------------------------------------------
@app.route("/api/about", methods=["GET"])
def api_about():
    return jsonify({
        "project": "SmartAssist AI",
        "full_title": (
            "SmartAssist AI: An Intelligent Customer Service Chatbot and "
            "Support Management System Using Machine Learning and "
            "Natural Language Processing"
        ),
        "stack": {
            "backend": "Flask 3.0",
            "ml": "scikit-learn (TF-IDF + Multinomial Naive Bayes)",
            "database": "SQLite3",
            "frontend": "HTML5 / CSS3 / JavaScript / Jinja2",
            "charts": "Chart.js",
        },
        "intents": INTENTS,
        "urgency_levels": URGENCY_LEVELS,
        "features": [
            "Real-time ML query classification", "Sentiment analysis",
            "Rule-based priority scoring & auto-escalation",
            "Personal expenditure tracker with time-of-day insights",
            "Notification center", "Login history", "Incident tracking",
            "Product feedback capture", "Admin correction & retraining loop",
        ],
    })


if __name__ == "__main__":
    bootstrap()
    app.run(debug=True, host="0.0.0.0", port=5000)
else:
    bootstrap()
