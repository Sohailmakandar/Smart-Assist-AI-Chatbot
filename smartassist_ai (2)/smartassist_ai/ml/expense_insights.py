"""
Expense Insights Engine
--------------------------
Rule-based (fully local, no ML training needed) analytics over a user's
logged expenses: category breakdown, time-of-day breakdown, week-over-week
comparison, and personalized recommendations / automated responses.

This mirrors the same "transparent rules over raw signal" philosophy as
the priority scorer in classifier.py — every insight can be explained in
one sentence, which matters for a finance-adjacent feature.
"""

from collections import defaultdict
from datetime import datetime, timedelta

from models.database import TIME_BUCKETS


def _parse(spent_at: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(spent_at, fmt)
        except (ValueError, TypeError):
            continue
    return datetime.utcnow()


def _time_bucket(hour: int) -> str:
    for label, start, end in TIME_BUCKETS:
        if start <= hour < end:
            return label
    return TIME_BUCKETS[-1][0]


def summarize(expenses: list) -> dict:
    """Category / time-of-day / weekday / daily-trend breakdown, plus
    today / this-week / this-month totals."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    total_today = total_week = total_month = 0.0
    category_totals = defaultdict(float)
    bucket_totals = defaultdict(float)
    weekday_totals = defaultdict(float)
    daily_trend = defaultdict(float)

    for e in expenses:
        dt = _parse(e["spent_at"])
        amount = float(e["amount"])

        category_totals[e["category"]] += amount
        bucket_totals[_time_bucket(dt.hour)] += amount
        weekday_totals[dt.strftime("%A")] += amount
        daily_trend[dt.strftime("%Y-%m-%d")] += amount

        if dt >= today_start:
            total_today += amount
        if dt >= week_start:
            total_week += amount
        if dt >= month_start:
            total_month += amount

    top_category = max(category_totals.items(), key=lambda kv: kv[1])[0] if category_totals else None
    peak_time = max(bucket_totals.items(), key=lambda kv: kv[1])[0] if bucket_totals else None
    peak_day = max(weekday_totals.items(), key=lambda kv: kv[1])[0] if weekday_totals else None

    return {
        "total_today": round(total_today, 2),
        "total_week": round(total_week, 2),
        "total_month": round(total_month, 2),
        "category_totals": {k: round(v, 2) for k, v in sorted(category_totals.items(), key=lambda kv: -kv[1])},
        "time_bucket_totals": {k: round(bucket_totals.get(k, 0), 2) for k, _, _ in TIME_BUCKETS},
        "weekday_totals": {k: round(v, 2) for k, v in weekday_totals.items()},
        "daily_trend": dict(sorted(daily_trend.items())[-14:]),
        "top_category": top_category,
        "peak_time": peak_time,
        "peak_day": peak_day,
        "entry_count": len(expenses),
    }


def generate_recommendations(expenses: list) -> list:
    """Personalized, rule-based spending tips. Each tip is a short,
    explainable sentence — no black-box scoring."""
    if not expenses:
        return ["Log your first expense to start getting personalized spending insights."]

    now = datetime.utcnow()
    this_week_start = now - timedelta(days=7)
    last_week_start = now - timedelta(days=14)

    summary = summarize(expenses)
    tips = []

    if summary["top_category"]:
        share = 0
        total = sum(summary["category_totals"].values()) or 1
        share = summary["category_totals"][summary["top_category"]] / total * 100
        tips.append(
            f"{summary['top_category']} is your biggest spending category — "
            f"{share:.0f}% of your total tracked spend."
        )

    if summary["peak_time"]:
        tips.append(
            f"You tend to spend the most during the {summary['peak_time']} window. "
            "A quick check-in before purchases in that window could help you stay on budget."
        )

    # Week-over-week comparison
    this_week_total = sum(
        float(e["amount"]) for e in expenses if _parse(e["spent_at"]) >= this_week_start
    )
    last_week_total = sum(
        float(e["amount"]) for e in expenses
        if last_week_start <= _parse(e["spent_at"]) < this_week_start
    )
    if last_week_total > 0:
        change = (this_week_total - last_week_total) / last_week_total * 100
        if change >= 20:
            tips.append(f"Your spending is up {change:.0f}% compared to last week — worth a quick review.")
        elif change <= -20:
            tips.append(f"Nice — your spending is down {abs(change):.0f}% compared to last week.")

    # Frequent small purchases in one category (possible "death by a
    # thousand cuts" spending)
    cat_counts = defaultdict(int)
    for e in expenses:
        if _parse(e["spent_at"]) >= this_week_start:
            cat_counts[e["category"]] += 1
    frequent = [(c, n) for c, n in cat_counts.items() if n >= 4]
    if frequent:
        cat, n = max(frequent, key=lambda kv: kv[1])
        tips.append(f"You've logged {n} separate {cat} expenses this week — batching purchases could reduce impulse spend.")

    # Single outlier expense
    amounts = [float(e["amount"]) for e in expenses]
    if len(amounts) >= 5:
        avg = sum(amounts) / len(amounts)
        biggest = max(amounts)
        if biggest > avg * 3:
            tips.append(f"Your largest single expense (₹{biggest:,.0f}) is well above your average of ₹{avg:,.0f} — just flagging it in case it wasn't planned.")

    if not tips:
        tips.append("Your spending looks steady — keep logging expenses to unlock deeper trends.")

    return tips[:5]


def generate_entry_insight(new_expense: dict, todays_expenses: list) -> str:
    """The 'automated response' shown immediately after logging an
    expense — a short, chatbot-style acknowledgement grounded in the
    user's actual data for today."""
    category = new_expense["category"]
    amount = float(new_expense["amount"])

    same_cat_today = [e for e in todays_expenses if e["category"] == category]
    total_cat_today = sum(float(e["amount"]) for e in same_cat_today)
    total_today = sum(float(e["amount"]) for e in todays_expenses)

    if len(same_cat_today) > 1:
        return (
            f"Logged ₹{amount:,.0f} for {category}. That's your "
            f"{_ordinal(len(same_cat_today))} {category} expense today, totaling "
            f"₹{total_cat_today:,.0f} so far."
        )
    return f"Logged ₹{amount:,.0f} for {category}. You've spent ₹{total_today:,.0f} in total today."


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# ---------------------------------------------------------------------------
# Invoices (monthly / yearly expenditure statements)
# ---------------------------------------------------------------------------
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
]


def build_invoice(user, period: str, year: int, month: int = None) -> dict:
    """Build a monthly or yearly expenditure invoice for a user.

    period: 'monthly' or 'yearly'. For 'monthly', ``month`` (1-12) is
    required. Line items come from models.database.get_expenses_in_range.
    """
    from models.database import get_expenses_in_range  # local import avoids a cycle

    if period == "monthly":
        if not month:
            raise ValueError("month is required for a monthly invoice")
        start = datetime(year, month, 1)
        end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
        period_label = f"{MONTH_NAMES[month - 1]} {year}"
        invoice_number = f"INV-{user['id']}-{year}{month:02d}"
    elif period == "yearly":
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)
        period_label = f"Year {year}"
        invoice_number = f"INV-{user['id']}-{year}"
    else:
        raise ValueError("period must be 'monthly' or 'yearly'")

    line_items = get_expenses_in_range(user["id"], start, end)
    category_totals = defaultdict(float)
    for item in line_items:
        category_totals[item["category"]] += float(item["amount"])

    total = sum(category_totals.values())

    return {
        "invoice_number": invoice_number,
        "period_label": period_label,
        "period": period,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "user_name": user["name"],
        "user_email": user["email"],
        "line_items": line_items,
        "category_totals": {k: round(v, 2) for k, v in sorted(category_totals.items(), key=lambda kv: -kv[1])},
        "total": round(total, 2),
        "entry_count": len(line_items),
    }
