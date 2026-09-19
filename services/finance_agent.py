"""
FinanceAgent
------------
Invoked once per new EXPENSE transaction:

  1. Cheap statistical pre-filter (MongoDB aggregation + Python compare)
     runs first. Most transactions are ordinary and get rejected here --
     no LLM call, no extra cost, no extra latency.

  2. Only when a transaction looks unusual (> 2.5x the user's own 30-day
     category average) does the LLM get invoked. It receives small,
     pre-aggregated numbers scoped to that one user -- never raw bulk
     data -- and writes the notification copy itself.

  3. The agent's decision drives the final email and audit log entry.

Model note: llama-3.3-70b-versatile was deprecated by Groq on the free/
developer tier in 2026. We now default to openai/gpt-oss-120b, Groq's
recommended replacement -- still hosted on Groq's own infrastructure,
still on the free tier, same API/SDK. If GROQ_API_KEY isn't configured,
the agent degrades gracefully: the statistical layer still runs and a
generic templated anomaly email is sent.
"""

import os
import json
import logging

from models.passbook import Passbook
from services.email_notifier import EmailNotifier
from services.audit_logger import AuditLogger

logger = logging.getLogger("finance_agent")

ANOMALY_MULTIPLIER = 2.5


class FinanceAgent:
    def __init__(self, db):
        self.db = db
        self.notifier = EmailNotifier()
        self.audit = AuditLogger(db)
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    def observe_transaction(self, txn):
        """Returns True if the agent sent its own richer notification, so
        the caller knows not to also send a plain confirmation email."""
        passbook = Passbook(self.db, txn.user_id)
        avg = passbook.category_average(txn.category)

        if avg is None or txn.amount <= avg * ANOMALY_MULTIPLIER:
            return False

        context = {
            "amount": txn.amount,
            "category": txn.display_category(),
            "user_category_average_30d": round(avg, 2),
            "ratio_to_average": round(txn.amount / avg, 2),
            "note": txn.note or "(none)",
        }

        decision = self._decide(context)

        self.audit.log(txn.user_email, "ANOMALY_FLAGGED", json.dumps(context))
        self.notifier.notify_async(
            subject=decision["subject"],
            body=decision["message"],
            to=txn.user_email,
        )
        return True

    def _decide(self, context):
        if not self.groq_api_key:
            return self._fallback_decision(context)

        try:
            from groq import Groq
            client = Groq(api_key=self.groq_api_key)

            prompt = f"""You are a personal finance monitoring agent. A user just
recorded an expense noticeably above their own recent average for this
category. Decide how to notify them.

Context (this user's own data only):
{json.dumps(context, indent=2)}

Respond with ONLY a JSON object, no other text, no markdown, no code fences.
Write the "message" value as a SINGLE line with no line breaks inside it --
use spaces between sentences, never a newline character.
Shape:
{{"subject": "short email subject", "message": "2-3 sentence friendly email body explaining why this transaction stands out compared to their usual spending in this category, written as one continuous line"}}
"""
            response = client.chat.completions.create(
                model=self.groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=400,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                # Some models slip a literal newline inside a JSON string
                # value, which is invalid JSON (must be \n, not a real
                # line break). Repair by escaping stray control characters
                # that appear inside quoted strings, then retry once.
                repaired = self._repair_json_string(raw)
                parsed = json.loads(repaired)

            if "subject" in parsed and "message" in parsed:
                # Belt-and-suspenders: collapse any remaining real newlines
                # in the message so the email body renders as intended.
                parsed["message"] = " ".join(parsed["message"].split())
                return parsed
        except Exception as exc:
            logger.error("FinanceAgent LLM call failed, falling back: %s", exc)

        return self._fallback_decision(context)

    @staticmethod
    def _repair_json_string(raw):
        """Escape literal newlines/tabs/carriage returns that appear INSIDE
        JSON string values (between quotes) without escaping the structural
        whitespace between keys. This fixes the common failure mode where a
        model writes a real line break inside a string instead of \\n."""
        out = []
        in_string = False
        escape_next = False
        for ch in raw:
            if escape_next:
                out.append(ch)
                escape_next = False
                continue
            if ch == "\\":
                out.append(ch)
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                out.append(ch)
                continue
            if in_string and ch == "\n":
                out.append("\\n")
                continue
            if in_string and ch == "\r":
                continue
            if in_string and ch == "\t":
                out.append("\\t")
                continue
            out.append(ch)
        return "".join(out)

    @staticmethod
    def _fallback_decision(context):
        return {
            "subject": f"Unusual spending noticed: {context['category']}",
            "message": (
                f"You just spent Rs. {context['amount']:,.2f} on {context['category']}, "
                f"which is about {context['ratio_to_average']}x your usual average "
                f"of Rs. {context['user_category_average_30d']:,.2f} in this category "
                f"over the last 30 days. Just flagging it in case it wasn't expected."
            ),
        }