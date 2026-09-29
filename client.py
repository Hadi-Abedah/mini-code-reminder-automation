"""Playwright client for the HubSpot dashboard."""

import os
from datetime import date
from types import TracebackType
from typing import Self

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from auth import login
from helpers import Lesson
from selectors import MOBILE_DAY_CARD, MOBILE_LESSON_CARD


class HubSpotDashboardClient:
    def __init__(
        self,
        email: str,
        password: str,
        *,
        base_url: str = "https://hubspot-dashboard.fly.dev/",
        headless: bool = True,
    ) -> None:
        self.email = email
        self.password = password
        self.base_url = base_url
        self.headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def start(self) -> Self:
        # Store browsers alongside Playwright inside the active virtual environment.
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self.context = self._browser.new_context()
        self.page = self.context.new_page()
        return self

    def authenticate(self) -> None:
        if self.page is None:
            raise RuntimeError("Client is not started; use it as a context manager")
        login(self.page, self.base_url, self.email, self.password)

    def get_todays_lessons(self, today: date | None = None) -> list[Lesson]:
        """Return every lesson in today's weekday column."""
        if self.page is None:
            raise RuntimeError("Client is not started; use it as a context manager")

        target_day = today or date.today()
        date_value = target_day.isoformat()
        open_button = self.page.locator(
            f'button[phx-click="calendar_view_day"][phx-value-date="{date_value}"]'
        ).first
        open_button.wait_for(state="attached")
        day_card = open_button.locator(MOBILE_DAY_CARD)
        cards = day_card.locator(MOBILE_LESSON_CARD)

        lessons: list[Lesson] = []
        for index in range(cards.count()):
            details = cards.nth(index).locator("p")
            if details.count() >= 2:
                lessons.append(
                    Lesson(
                        day=target_day,
                        name=details.nth(0).inner_text().strip(),
                        time=details.nth(1).inner_text().strip(),
                    )
                )
        return lessons

    def close(self) -> None:
        if self.context is not None:
            self.context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
