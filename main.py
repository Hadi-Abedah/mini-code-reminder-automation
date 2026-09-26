"""Entry point for dashboard automation."""

import os
from pathlib import Path

from dotenv import load_dotenv

from client import HubSpotDashboardClient


load_dotenv(Path(__file__).with_name(".env"))


def main() -> None:
    email = os.environ.get("HUBSPOT_EMAIL")
    password = os.environ.get("HUBSPOT_PASSWORD")
    if not email or not password:
        raise RuntimeError("Set HUBSPOT_EMAIL and HUBSPOT_PASSWORD before running")

    headless = os.environ.get("HEADLESS", "true").lower() not in {"0", "false", "no"}
    with HubSpotDashboardClient(email, password, headless=headless) as client:
        try:
            client.authenticate()
            lessons = client.get_todays_lessons()

            if not lessons:
                print("No lessons today")
            for lesson in lessons:
                print(f"{lesson.day:%a %Y-%m-%d} | {lesson.time} - {lesson.name}")
        finally:
            if not headless:
                input("Press Enter to close the browser...")


if __name__ == "__main__":
    main()
