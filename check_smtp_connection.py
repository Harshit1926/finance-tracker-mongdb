"""
check_smtp_connection.py
--------------------------
Standalone diagnostic script -- verifies your Gmail SMTP credentials work
by sending one real test email, before you try the full signup/OTP flow.

Usage:
    python check_smtp_connection.py
    python check_smtp_connection.py --to someone@example.com
"""

import os
import sys
import smtplib
import argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Send a test email to verify SMTP setup.")
    parser.add_argument("--to", help="Email address to send the test to. Defaults to SMTP_USERNAME.")
    args = parser.parse_args()

    print("=" * 60)
    print("SMTP Connection Check")
    print("=" * 60)

    host = os.getenv("SMTP_HOST")
    port = os.getenv("SMTP_PORT")
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_name = os.getenv("SMTP_FROM_NAME", "Finance Tracker")

    # ---------- Step 1: are all required values set? ----------
    missing = [name for name, val in [
        ("SMTP_HOST", host), ("SMTP_PORT", port),
        ("SMTP_USERNAME", username), ("SMTP_PASSWORD", password),
    ] if not val]

    if missing:
        print(f"\n[FAIL] Missing from .env: {', '.join(missing)}")
        print("       Fill these in before testing.")
        sys.exit(1)

    if "your-16-char-app-password" in password or "youraddress" in username:
        print("\n[FAIL] .env still contains placeholder values.")
        print("       Replace SMTP_USERNAME and SMTP_PASSWORD with your real Gmail")
        print("       address and App Password.")
        sys.exit(1)

    if " " in password:
        print("\n[WARN] SMTP_PASSWORD contains spaces. Gmail displays App Passwords")
        print("       with spaces for readability, but you should paste it WITHOUT")
        print("       spaces into .env. Trying anyway...")

    to_addr = args.to or username
    port = int(port)

    print(f"\n[OK] Host: {host}:{port}")
    print(f"[OK] From: {from_name} <{username}>")
    print(f"[OK] Sending test email to: {to_addr}")

    # ---------- Step 2: build the message ----------
    msg = MIMEMultipart()
    msg["From"] = f"{from_name} <{username}>"
    msg["To"] = to_addr
    msg["Subject"] = "Finance Tracker - SMTP Test"
    msg.attach(MIMEText(
        "If you're reading this, your SMTP credentials are working correctly.\n\n"
        "This was a test email sent by check_smtp_connection.py.",
        "plain",
    ))

    # ---------- Step 3: attempt to connect and send ----------
    print("\nConnecting to SMTP server...")
    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            print("[OK] TLS handshake successful.")

            print("Logging in...")
            server.login(username, password)
            print("[OK] Login successful.")

            print("Sending test email...")
            server.sendmail(username, to_addr, msg.as_string())
            print("[OK] Email sent successfully.")

    except smtplib.SMTPAuthenticationError as e:
        print(f"\n[FAIL] Authentication failed: {e}")
        print("       Likely causes:")
        print("       - You're using your normal Gmail password instead of an App Password")
        print("       - 2-Step Verification isn't enabled on this Google account")
        print("         (required before App Passwords can be generated)")
        print("       - The App Password was mistyped or has extra spaces")
        sys.exit(1)
    except smtplib.SMTPConnectError as e:
        print(f"\n[FAIL] Could not connect to {host}:{port} -- {e}")
        print("       Check SMTP_HOST and SMTP_PORT are correct, and that your")
        print("       network/firewall isn't blocking outbound port 587.")
        sys.exit(1)
    except TimeoutError:
        print(f"\n[FAIL] Connection to {host}:{port} timed out.")
        print("       Check your internet connection or firewall settings.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"Success. Check the inbox for {to_addr} (and spam folder).")
    print("=" * 60)


if __name__ == "__main__":
    main()
