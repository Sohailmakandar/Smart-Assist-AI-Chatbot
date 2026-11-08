# SmartAssist AI

**An Intelligent Customer Service Chatbot and Support Management System
Using Machine Learning and Natural Language Processing**

A full-stack Python project (Flask + scikit-learn + SQLite) that classifies
customer support queries in real time, tracks personal daily expenditure,
manages tickets and users, and continuously improves itself from admin
corrections — all wrapped in an attractive, fully responsive UI.

## Features

### User side ("My Space")
- **Sign in** with name + email (no password) — ties everything to a
  returning identity
- **Live chat widget** with a real-time "what intent am I typing" preview,
  quick-prompt chips, and 👍/👎 feedback on every bot reply
- **Profile** — name (editable), email, member-since date, ticket /
  escalation / login / expense counts, and full **login history**
- **Expense tracker** — log daily spending by category, see totals for
  today / this week / this month, a **category breakdown chart**, and a
  **time-of-day breakdown chart** (Morning/Afternoon/Evening/Night) so you
  can see exactly *when* you spend the most
- **Personalized, automated recommendations** on your spending (top
  category, peak spending time, week-over-week change, frequent small
  purchases, outlier expenses) — and an automated one-line insight the
  moment you log a new expense
- **Monthly / yearly invoices** — a printable expenditure statement
  (print-to-PDF from the browser) for any month or year
- **Recycle Bin** — deleted expenses aren't gone forever; restore them
  any time
- **Incidents** — your escalated / high-urgency tickets tracked
  separately, with the ability to add follow-up notes
- **Feedback** — a dedicated star-rating + comment form (separate from
  per-message 👍/👎)
- **Notification center** — a bell in the nav plus a full tab; you're
  notified the moment a ticket is escalated, resolved, or a transaction
  completes
- **My Tickets** and **FAQ** tabs, plus a light/dark theme toggle

### Admin side
- **Sidebar-navigated console** (Overview / Tickets / Users / Expenses /
  Feedback / Model & Corrections)
- **Overview**: 8 stat cards + 4 interactive Chart.js charts (intent
  distribution, urgency breakdown, sentiment split, 7-day volume)
- **Tickets**: search, filter by intent/urgency/status/agent, inline
  status updates, **agent assignment** (with automatic rule-based
  routing — Critical → Tier-2 team, High → round-robin agent), internal
  notes, and a **"Correct?" dropdown** to relabel a misclassified intent
- **Users**: every account with ticket/escalation counts, last-active
  time, a full ticket-history detail view, and block/unblock
- **Expenses**: aggregate spend across all users, category breakdown,
  14-day trend, and a top-spenders leaderboard
- **Feedback**: average rating, response count, 5-star share, and the
  full comment feed
- **Model & Corrections**: every admin re-label is logged, and a
  **"Retrain model"** button folds those corrections back into the
  training set — the classifier literally learns from its own mistakes
- **CSV export** of the full ticket table
- Full **REST API** for everything above

## Project structure

```
smartassist_ai/
├── app.py                      # Flask routes & REST APIs
├── requirements.txt
├── ml/
│   ├── preprocess.py           # Text cleaning, tokenization
│   ├── sentiment.py            # Lexicon-based sentiment detector
│   ├── classifier.py           # TF-IDF + Naive Bayes, priority scoring, retraining
│   ├── expense_insights.py     # Spending analytics, recommendations, invoices
│   └── knowledge_base.py       # Static FAQ content
├── models/
│   └── database.py             # SQLite schema (8 tables), CRUD, statistics
├── templates/
│   ├── base.html
│   ├── index.html              # Chat, My Space, About
│   └── dashboard.html          # Sidebar admin console
├── static/
│   ├── css/style.css
│   └── js/{main,chat,myspace,dashboard}.js
└── data/                       # auto-created: smartassist.db, model pickle
```

## Setup & run

```bash
# 1. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python app.py
```

Open **http://127.0.0.1:5000** for the chat + My Space, and
**http://127.0.0.1:5000/dashboard** for the admin console.

On first run the app auto-creates/migrates `data/smartassist.db`, trains
and pickles the ML model, and seeds a few demo users, tickets, and sample
expenses so nothing looks empty on first look.

To force a clean retrain, delete `data/smartassist_model.pkl` and restart.
To reset all data, delete the whole `data/` folder and restart.

## Database schema (8 tables)

| Table              | Purpose                                              |
| ------------------- | ------------------------------------------------------ |
| `users`             | Lightweight identity (name + email, no password)      |
| `support_chats`     | Classified conversations / tickets                     |
| `expenses`          | Daily spending log (soft-deletable → Recycle Bin)       |
| `login_history`     | One row per sign-in                                     |
| `notifications`     | In-app notification center                              |
| `product_feedback`  | Star rating + comment                                   |
| `incident_updates`  | User follow-up notes on escalated tickets                |
| `corrections`       | Admin re-labels, feeds the retraining loop               |

## REST API quick reference

| Method | Endpoint                                | Purpose                                        |
| ------ | ----------------------------------------- | ------------------------------------------------ |
| POST   | `/api/users/login`                        | Get-or-create a user, records a login             |
| GET/POST | `/api/users/<id>/profile`               | View / update profile (name)                      |
| GET    | `/api/users/<id>/login-history`           | Login history                                      |
| GET    | `/api/users/<id>/history`                 | Ticket history                                     |
| POST   | `/api/chat`                               | Classify a message, get a bot response             |
| POST   | `/api/chat/<id>/feedback`                 | 👍/👎 a bot reply                                   |
| POST   | `/api/live-preview`                       | Live intent preview while typing                   |
| GET    | `/api/faq`                                | Knowledge-base FAQ                                 |
| GET    | `/api/incidents`                          | A user's escalated/critical tickets                |
| POST   | `/api/incidents/<chat_id>/update`         | Add a follow-up note                               |
| POST   | `/api/feedback`                           | Submit star-rating product feedback                |
| GET    | `/api/notifications`                      | A user's notifications                             |
| POST   | `/api/notifications/<id>/read`            | Mark one notification read                          |
| POST   | `/api/notifications/read-all`             | Mark all read                                       |
| POST   | `/api/expenses`                           | Log an expense (returns an automated insight)       |
| GET    | `/api/expenses`                           | List + summary + recommendations                    |
| DELETE | `/api/expenses/<id>`                      | Soft-delete → Recycle Bin                            |
| GET    | `/api/expenses/recycle-bin`               | List deleted expenses                                |
| POST   | `/api/expenses/<id>/restore`              | Restore from Recycle Bin                             |
| GET    | `/api/expenses/invoice`                   | Monthly/yearly invoice                               |
| GET    | `/api/tickets`                            | List/filter tickets                                  |
| POST   | `/api/tickets/<id>/status`                | Update status                                        |
| POST   | `/api/tickets/<id>/assign`                | Assign an agent                                      |
| POST   | `/api/tickets/<id>/notes`                 | Save internal notes                                  |
| POST   | `/api/tickets/<id>/correct`               | Relabel intent (feeds retraining)                    |
| GET    | `/api/tickets/export`                     | CSV export                                           |
| GET    | `/api/admin/users`, `/api/admin/users/<id>` | User management                                    |
| POST   | `/api/admin/users/<id>/block`             | Block / unblock                                      |
| GET    | `/api/admin/expenses/overview`            | Aggregate spending analytics                         |
| GET    | `/api/admin/feedback`                     | Feedback list + stats                                |
| GET    | `/api/admin/corrections`                  | Correction history                                   |
| POST   | `/api/admin/retrain`                      | Retrain the classifier on corrections                |
| GET    | `/api/stats`                              | Dashboard aggregate stats                             |
| GET    | `/api/about`                              | Project metadata / tech stack                         |

## Tech stack

Flask 3.0+ · scikit-learn 1.3+ · NumPy · SQLite3 · HTML5/CSS3/JavaScript ·
Jinja2 · Chart.js 4.4

## Notes

This is an educational/demonstration prototype — the seed training corpus
is intentionally compact. For production use, retrain on a larger, real
conversation dataset (the "Retrain from corrections" admin workflow is a
starting point for exactly that).
