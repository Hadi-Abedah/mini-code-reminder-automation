"""Entry point for dashboard automation and optional WhatsApp reminders."""

import argparse
import os
from contextlib import nullcontext
from pathlib import Path

from dotenv import load_dotenv

from client import HubSpotDashboardClient
from whatsapp import ROOT, build_messages, cairo_today, load_groups, send_lock, send_messages

load_dotenv(Path(__file__).with_name(".env"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send-whatsapp", action="store_true", help="Send mapped lessons via Baileys")
    parser.add_argument("--dry-run", action="store_true", help="Preview routing and messages without connecting to WhatsApp")
    parser.add_argument("--groups", type=Path, default=ROOT / "groups.json", help="Lesson-to-group JSON mapping")
    args = parser.parse_args()
    groups = load_groups(args.groups) if args.send_whatsapp or args.dry_run else None
    email = os.environ.get("HUBSPOT_EMAIL")
    password = os.environ.get("HUBSPOT_PASSWORD")
    if not email or not password:
        raise RuntimeError("Set HUBSPOT_EMAIL and HUBSPOT_PASSWORD before running")

    headless = os.environ.get("HEADLESS", "true").lower() not in {"0", "false", "no"}
    with send_lock() if args.send_whatsapp and not args.dry_run else nullcontext():
        with HubSpotDashboardClient(email, password, headless=headless) as client:
            try:
                client.authenticate()
                lessons = client.get_todays_lessons(today=cairo_today())
                if not lessons:
                    print("No lessons today", flush=True)
                for lesson in lessons:
                    print(f"{lesson.day:%a %Y-%m-%d} | {lesson.time} - {lesson.name}", flush=True)
            finally:
                if not headless:
                    input("Press Enter to close the browser...")
        if groups is not None:
            messages = build_messages(lessons, groups)
            if args.dry_run:
                for message in messages:
                    print(f"[Preview → {message['groupId']}]\n{message['text']}")
                print(f"Dry run: {len(messages)} message(s); nothing sent")
            else:
                send_messages(messages)


if __name__ == "__main__":
    main()
