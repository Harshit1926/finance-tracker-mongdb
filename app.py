"""
app.py
------
Thin Flask routing layer. Every route delegates to a service class --
no business logic lives here, only request handling and template rendering.
"""

import os
import re
from functools import wraps
from datetime import datetime, timezone, timedelta

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from dotenv import load_dotenv

load_dotenv()

from models.database import DatabaseManager
from models.user import User
from models.role import RoleType
from models.transaction import Category, TxnType
from models.passbook import Passbook

from services.auth_service import AuthService
from services.otp_service import OTPStillActiveError, TooManyAttemptsError
from services.user_manager import UserManager
from services.transaction_manager import TransactionManager
from services.filter_service import FilterService
from services.finance_agent import FinanceAgent

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

db = DatabaseManager()
auth_service = AuthService(db)
user_manager = UserManager(db)
finance_agent = FinanceAgent(db)
transaction_manager = TransactionManager(db, finance_agent=finance_agent)
filter_service = FilterService(db)

# How long a signup-in-progress ("pending_email") stays valid before the
# person is forced to restart from /signup. Prevents an old, abandoned
# session from letting someone land on /verify-otp days later without
# having just submitted the signup form.
PENDING_SIGNUP_WINDOW_MINUTES = 15


# ---------------- helpers ----------------

PHONE_PATTERN = re.compile(r"^\d{10}$")


def is_valid_phone(phone):
    """Empty/None is fine -- phone is optional. If provided, must be exactly 10 digits."""
    if not phone:
        return True
    return bool(PHONE_PATTERN.match(phone.strip()))


def start_pending_signup(email):
    """Call this the moment signup is (re)submitted -- stamps both the
    email and the time it started, so staleness can be checked later."""
    session["pending_email"] = email
    session["pending_email_started_at"] = datetime.now(timezone.utc).isoformat()


def get_fresh_pending_email():
    """Returns the pending email ONLY if step 1 (signup) was genuinely
    just completed, within PENDING_SIGNUP_WINDOW_MINUTES. Otherwise clears
    the stale session data and returns None, so the caller redirects back
    to /signup instead of letting an old session skip straight to step 2."""
    email = session.get("pending_email")
    started_at_raw = session.get("pending_email_started_at")

    if not email or not started_at_raw:
        return None

    try:
        started_at = datetime.fromisoformat(started_at_raw)
    except ValueError:
        session.pop("pending_email", None)
        session.pop("pending_email_started_at", None)
        return None

    age = datetime.now(timezone.utc) - started_at
    if age > timedelta(minutes=PENDING_SIGNUP_WINDOW_MINUTES):
        session.pop("pending_email", None)
        session.pop("pending_email_started_at", None)
        return None

    return email


def clear_pending_signup():
    session.pop("pending_email", None)
    session.pop("pending_email_started_at", None)


def current_user():
    email = session.get("email")
    if not email:
        return None
    return User.find_by_email(db, email)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "email" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if session.get("role") not in roles:
                flash("You don't have access to that page.", "danger")
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


def dashboard_url_for(role):
    return {
        RoleType.USER: "user_dashboard",
        RoleType.ANALYST: "analyst_dashboard",
        RoleType.ADMIN: "admin_dashboard",
        RoleType.CREATOR: "admin_dashboard",
    }.get(role, "login")


# ---------------- auth ----------------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        user, error = auth_service.login(email, password)
        if error:
            flash(error, "danger")
            return render_template("login.html")

        session["email"] = user.email
        session["role"] = user.role.name
        session["name"] = user.name or user.email.split("@")[0]
        return redirect(url_for(dashboard_url_for(user.role.name)))

    if "email" in session:
        return redirect(url_for(dashboard_url_for(session.get("role"))))
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        name = request.form.get("name", "")
        phone = request.form.get("phone", "")
        dob = request.form.get("dob", "")

        if not is_valid_phone(phone):
            flash("Mobile number must be exactly 10 digits.", "danger")
            return render_template("signup.html")

        user, error = auth_service.start_signup(email, password, name=name, phone=phone, dob=dob)
        if error:
            flash(error, "danger")
            return render_template("signup.html")

        # Step 1 genuinely just happened -- stamp email + timestamp together.
        start_pending_signup(user.email)
        flash("We've sent a 6-digit code to your email.", "success")
        return redirect(url_for("verify_otp"))

    return render_template("signup.html")


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    email = get_fresh_pending_email()
    if not email:
        flash("Please start signup again to receive a new code.", "danger")
        return redirect(url_for("signup"))

    if request.method == "POST":
        code = request.form.get("code", "")
        try:
            success, error = auth_service.verify_signup(email, code)
        except TooManyAttemptsError as e:
            flash(str(e), "danger")
            return render_template("verify_otp.html", email=email)

        if not success:
            flash(error, "danger")
            return render_template("verify_otp.html", email=email)

        clear_pending_signup()
        flash("Account verified! You can log in now.", "success")
        return redirect(url_for("login"))

    return render_template("verify_otp.html", email=email)


@app.route("/resend-otp", methods=["POST"])
def resend_otp():
    email = get_fresh_pending_email()
    if not email:
        flash("Please start signup again to receive a new code.", "danger")
        return redirect(url_for("signup"))

    try:
        auth_service.resend_otp(email)
        flash("A new code has been sent.", "success")
    except OTPStillActiveError as e:
        flash(str(e), "danger")

    return redirect(url_for("verify_otp"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------- user dashboard ----------------

@app.route("/user")
@login_required
@role_required(RoleType.USER)
def user_dashboard():
    user = current_user()
    passbook = Passbook(db, user._id)

    from models.transaction import Transaction
    transactions = Transaction.find_by_user(db, user._id, limit=50)

    return render_template(
        "user.html",
        user=user,
        transactions=transactions,
        summary=passbook.summary(),
        category_totals=passbook.category_totals(),
        expense_breakdown=passbook.expense_breakdown(),
        monthly_trend=passbook.monthly_trend(),
        categories=Category.ALL,
        category_colors=Category.COLORS,
        today=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )


@app.route("/user/add-transaction", methods=["POST"])
@login_required
@role_required(RoleType.USER)
def add_transaction():
    user = current_user()
    try:
        transaction_manager.add(
            user=user,
            amount=float(request.form["amount"]),
            category=request.form["category"],
            txn_type=request.form["type"],
            date=datetime.strptime(request.form["date"], "%Y-%m-%d"),
            note=request.form.get("note", ""),
            custom_category=request.form.get("custom_category", "").strip() or None,
        )
        flash("Transaction added.", "success")
    except (ValueError, KeyError) as e:
        flash(f"Could not add transaction: {e}", "danger")

    return redirect(url_for("user_dashboard"))


@app.route("/user/delete-transaction/<txn_id>", methods=["POST"])
@login_required
@role_required(RoleType.USER)
def delete_transaction(txn_id):
    user = current_user()
    deleted = transaction_manager.delete(user, txn_id)
    flash("Transaction deleted." if deleted else "Transaction not found.",
          "success" if deleted else "danger")
    return redirect(url_for("user_dashboard"))


# ---------------- analyst dashboard ----------------

@app.route("/analyst")
@login_required
@role_required(RoleType.ANALYST, RoleType.ADMIN, RoleType.CREATOR)
def analyst_dashboard():
    users = User.find_all(db, role=RoleType.USER)
    return render_template("analyst.html", users=users, categories=Category.ALL,
                            filtered=None, summary=None, selected_email=None)


@app.route("/analyst/filter", methods=["POST"])
@login_required
@role_required(RoleType.ANALYST, RoleType.ADMIN, RoleType.CREATOR)
def analyst_filter():
    users = User.find_all(db, role=RoleType.USER)
    target_email = request.form.get("user_email", "")

    target = User.find_by_email(db, target_email)
    if not target:
        flash("Select a valid user to filter.", "danger")
        return render_template("analyst.html", users=users, categories=Category.ALL,
                                filtered=None, summary=None, selected_email=None)

    filtered = filter_service.filter_transactions(
        target._id,
        start_date=request.form.get("start_date") or None,
        end_date=request.form.get("end_date") or None,
        category=request.form.get("category") or None,
        txn_type=request.form.get("type") or None,
    )
    summary = filter_service.summarize(filtered)

    return render_template("analyst.html", users=users, categories=Category.ALL,
                            filtered=filtered, summary=summary, selected_email=target_email)


# ---------------- admin / creator dashboard ----------------

@app.route("/admin")
@login_required
@role_required(RoleType.ADMIN, RoleType.CREATOR)
def admin_dashboard():
    actor = current_user()
    users = User.find_all(db)
    assignable_roles = [r for r in RoleType.ALL if actor.role.can_assign(r)] or [RoleType.USER]
    return render_template("admin.html", actor=actor, users=users,
                            role_labels=RoleType.LABELS, assignable_roles=assignable_roles)


@app.route("/admin/create", methods=["POST"])
@login_required
@role_required(RoleType.ADMIN, RoleType.CREATOR)
def admin_create():
    actor = current_user()

    if not is_valid_phone(request.form.get("phone")):
        flash("Mobile number must be exactly 10 digits.", "danger")
        return redirect(url_for("admin_dashboard"))

    try:
        user_manager.create(
            actor=actor,
            email=request.form["email"],
            password=request.form["password"],
            role=request.form["role"],
            name=request.form.get("name"),
            phone=request.form.get("phone"),
            dob=request.form.get("dob"),
        )
        flash("Account created.", "success")
    except (PermissionError, ValueError) as e:
        flash(str(e), "danger")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/update", methods=["POST"])
@login_required
@role_required(RoleType.ADMIN, RoleType.CREATOR)
def admin_update():
    actor = current_user()
    field = request.form.get("field")
    value = request.form.get("value", "")

    if field == "phone" and not is_valid_phone(value):
        flash("Mobile number must be exactly 10 digits.", "danger")
        return redirect(url_for("admin_dashboard"))

    try:
        user_manager.update(
            actor=actor,
            target_email=request.form["email"],
            field=field,
            new_value=value,
        )
        flash("Account updated.", "success")
    except (PermissionError, ValueError) as e:
        flash(str(e), "danger")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete", methods=["POST"])
@login_required
@role_required(RoleType.ADMIN, RoleType.CREATOR)
def admin_delete():
    actor = current_user()
    try:
        user_manager.delete(actor=actor, target_email=request.form["email"])
        flash("Account deleted.", "success")
    except (PermissionError, ValueError) as e:
        flash(str(e), "danger")

    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)