# 💰 Finance Tracker

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?logo=flask&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB_Atlas-47A248?logo=mongodb&logoColor=white)
![Chart.js](https://img.shields.io/badge/Chart.js-FF6384?logo=chartdotjs&logoColor=white)
![Groq](https://img.shields.io/badge/LLM-Groq-F55036)
![Deploy](https://img.shields.io/badge/Deploy-Render-46E3B7?logo=render&logoColor=white)

**🔗 Live demo:** [finance-tracker-mongdb.onrender.com](https://finance-tracker-mongdb.onrender.com)

> Hosted on Render's free tier, so the first load after inactivity can take about a minute.

A full-stack, role-based personal finance tracker with a four-tier permission system, OTP-verified signup, automated email notifications, and an agentic anomaly-detection layer powered by an LLM.

## 📌 Project Evolution

This is the third iteration of the project:

| Version | Storage | Architecture |
|---|---|---|
| v1 | Flat JSON file | Function-based |
| v2 | MySQL | Function-based |
| **v3 (this one)** | **MongoDB Atlas** | **OOP, service-layer architecture, LLM agent** |

## 📑 Table of Contents

- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Getting Started](#-getting-started)
- [Environment Variables](#-environment-variables)
- [Deployment on Render](#-deployment-on-render)
- [Project Structure](#-project-structure)
- [Technical Notes](#-technical-notes)

## ✨ Features

### 🔐 Access Control
- **4-tier role hierarchy:** `Creator → Admin → Analyst → User`, enforced via `Role.can_manage()`.
- The Creator account is seeded manually via `.env`, never through the UI. It can never be deleted or demoted by anyone. This is a hard rule, not just a level comparison.

### 📧 Authentication
- **Email + OTP signup:** 6-digit code, valid for 1 minute, hashed at rest (never stored in plaintext).
- Resend is blocked until the previous code expires, and verification is brute-force capped at 5 attempts.
- Login uses **email + password only**. OTP is a one-time signup verification step.
- Phone number is stored for reference only and validated to exactly 10 digits on both client and server.

### 💸 Transactions
- **Fixed categories:** Food, Travel, Rent, Salary, Utilities, Shopping, Healthcare, Entertainment, Other.
- "Other" accepts a free-text label, which keeps analytics and anomaly detection reliable while staying flexible.

### 🤖 FinanceAgent (Agentic Layer)
- Every new expense is checked against the user's own **30-day category average** using a cheap MongoDB aggregation (no LLM call for ordinary transactions).
- Only genuinely unusual transactions (**> 2.5× average**) are escalated to an LLM (Groq, `openai/gpt-oss-120b`), which reasons about the context and writes the notification itself.
- **Graceful fallback:** if `GROQ_API_KEY` is missing or the LLM call fails, a plain templated email is sent instead. Anomaly detection never blocks or breaks the transaction itself.

### 📬 Automated Emails
Sent on: transaction added, transaction deleted, account created, account updated, and account deleted.

### 🎨 UI
- Dark, editorial dashboard.
- Password show/hide toggle on every password field.
- Chart.js visuals: doughnut chart for category breakdown, gradient line chart for monthly income/expense trend.

### 🛠️ Diagnostics
- `check_mongo_connection.py` and `check_smtp_connection.py` verify infrastructure works before you debug through the UI.

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask, Gunicorn |
| Database | MongoDB Atlas (PyMongo) |
| Frontend | Jinja2 templates, CSS, vanilla JS, Chart.js |
| AI | Groq API (`openai/gpt-oss-120b`) |
| Email | Mailjet HTTPS API in production, SMTP (Gmail) for local development |
| Hosting | Render |

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- A [MongoDB Atlas](https://www.mongodb.com/atlas) cluster
- A free [Mailjet](https://www.mailjet.com) account with a verified sender address (for production email)
- *(Local development only)* A Gmail App Password for SMTP
- *(Optional)* A [Groq](https://console.groq.com) API key

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/Harshit1926/finance-tracker-mongdb.git
cd finance-tracker-mongdb

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env            # Windows: copy .env.example .env
# Then fill in the values (see below)

# 5. Verify your infrastructure
python check_mongo_connection.py   # confirm MongoDB Atlas connectivity
python check_smtp_connection.py    # confirm email sending works

# 6. Seed the Creator account (run once)
python seed_creator.py

# 7. Start the app
python app.py
```

Visit **http://127.0.0.1:5000**.

## 🔑 Environment Variables

Copy `.env.example` to `.env` and fill in the values. **Never commit `.env`.**

| Variable | Description |
|---|---|
| `MONGO_URI` | MongoDB Atlas connection string |
| `MONGO_DB_NAME` | Database name (e.g. `finance_tracker`) |
| `MAILJET_API_KEY` | Mailjet API key (production email) |
| `MAILJET_SECRET_KEY` | Mailjet secret key (production email) |
| `MAILJET_SENDER_EMAIL` | Sender address verified in Mailjet |
| `SMTP_*` | *(Local development only)* SMTP host, port, username, password, and from-name for Gmail |
| `CREATOR_*` | Credentials for the seeded Creator account |
| `GROQ_API_KEY` | *(Optional)* Enables LLM-written anomaly alerts |
| `GROQ_MODEL` | *(Optional)* Defaults to `openai/gpt-oss-120b` |
| `OTP_VALIDITY_SECONDS` | OTP lifetime in seconds (default `60`) |

See `.env.example` for the exact variable names.

### How email is sent

The notifier picks a delivery method automatically:

1. **Mailjet HTTPS API** when `MAILJET_API_KEY` and `MAILJET_SECRET_KEY` are set (used in production).
2. **SMTP** otherwise (local development with a Gmail App Password).

## ☁️ Deployment on Render

1. **Push to GitHub.** `.gitignore` already excludes `.env`.
2. **MongoDB Atlas → Network Access** → allow `0.0.0.0/0` (Render's free tier has no static outbound IP).
3. **Render → New → Web Service** → connect the repository. Use these settings:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT` (also defined in the `Procfile`)
4. **Environment tab:** add every variable from your `.env` manually. In production you need `MONGO_URI`, `MONGO_DB_NAME`, `SECRET_KEY`, the three `MAILJET_*` variables, `OTP_VALIDITY_SECONDS`, `PYTHON_VERSION`, and optionally `GROQ_API_KEY` / `GROQ_MODEL`. The `SMTP_*` variables are not needed on Render.
5. **Deploy.**
6. **Seed the Creator:** run `python seed_creator.py` locally once, pointed at the same `MONGO_URI`, to create the Creator account in the live database.

> **Note:** `gunicorn` and `requests` must be listed in `requirements.txt`.

> **Why not SMTP on Render?** Render's free web services block outbound traffic on SMTP ports 25, 465, and 587, so Gmail SMTP times out in production. This project therefore sends email over HTTPS through the Mailjet API, which is not blocked. Verify a sender address in Mailjet, then set the `MAILJET_*` variables.

## 📁 Project Structure

```
finance-tracker/
├── app.py                    # Flask routes only, thin, delegates to services
├── seed_creator.py           # one-time Creator seeding script
├── check_mongo_connection.py # standalone MongoDB connectivity diagnostic
├── check_smtp_connection.py  # standalone SMTP/email diagnostic
├── Procfile                  # tells Render how to start the app (gunicorn)
├── requirements.txt
├── .env.example
├── models/
│   ├── database.py           # DatabaseManager (singleton Mongo connection,
│   │                         #   tz_aware=True, index creation)
│   ├── role.py               # Role, RoleType: permission hierarchy
│   ├── user.py               # User
│   ├── transaction.py        # Transaction, Category, TxnType
│   └── passbook.py           # aggregation: balance, category totals, trend
├── services/
│   ├── auth_service.py        # login + signup orchestration
│   ├── otp_service.py         # OTP generate/verify, hashed, rate-limited
│   ├── email_notifier.py      # async sender (Mailjet API, SMTP fallback), console-visible logging
│   ├── audit_logger.py        # append-only action trail
│   ├── user_manager.py        # admin create/update/delete accounts
│   ├── transaction_manager.py # add/delete transactions
│   ├── filter_service.py      # analyst filtering
│   └── finance_agent.py       # anomaly pre-filter + LLM reasoning + JSON repair
├── templates/                 # dark-themed Jinja templates
├── preview/                   # standalone HTML copies (no Flask needed) for
│                              #   checking the design directly in a browser
└── static/{css,js}/           # theme + Chart.js + password-toggle + phone
                               #   validation JS
```

## 📝 Technical Notes

- **Indexes:** MongoDB indexes are created automatically on first connection (see `models/database.py`). This includes the partial unique index that guarantees only one Creator document can ever exist, and the TTL index that auto-expires OTP records.
- **Timezone-aware datetimes:** `MongoClient` is configured with `tz_aware=True` so datetimes read back from MongoDB are timezone-aware, matching the `datetime.now(timezone.utc)` values written throughout the app. Without this, OTP expiry comparisons raise `TypeError: can't compare offset-naive and offset-aware datetimes`.
- **Email delivery:** emails are sent in a background thread so a slow or failed send never blocks the request. Failures are logged (look for `[EMAIL FAILED]` in the logs) and never raised to the caller. OTP emails from a free-tier sender may land in spam, so check there when testing.
- **LLM fallback:** If `GROQ_API_KEY` is empty, the FinanceAgent still runs its statistical anomaly check and sends a plain (non-LLM-authored) alert. Nothing breaks, it just loses the reasoned copy.
- **Model choice:** `llama-3.3-70b-versatile` was deprecated by Groq on the free/developer tier in 2026. This project defaults to `openai/gpt-oss-120b`, Groq's recommended replacement, still on the free tier via the same API.

## 📄 License

This project is for learning and portfolio purposes. Add a license of your choice (e.g. MIT) if you plan to share it publicly.