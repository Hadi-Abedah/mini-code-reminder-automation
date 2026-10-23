"""Exercise real browser locators against representative mobile card markup."""

import unittest
from contextlib import redirect_stdout
from datetime import date
from io import StringIO

from client import HubSpotDashboardClient


class InactiveLessonTests(unittest.TestCase):
    def test_mobile_status_dots_filter_only_inactive_cards(self):
        statuses = {
            "active-main": "bg-blue-500",
            "active-exercise": "bg-emerald-500",
            "postponed-mobile": "bg-slate-400",
            "postponed-gray": "bg-gray-400",
            "transferred-out": "bg-orange-400",
        }
        cards = "".join(
            f'<div class="rounded-2xl border px-3 py-3">'
            f'<span class="mt-1 h-2.5 w-2.5 rounded-full flex-shrink-0 {color}"></span>'
            f'<div><p>{name}</p><p>7pm</p></div>'
            '<span class="rounded-lg bg-slate-200 text-slate-400">Join</span>'
            '</div>'
            for name, color in statuses.items()
        )
        html = (
            '<div class="overflow-hidden">'
            '<button phx-click="calendar_view_day" phx-value-date="2026-10-23"></button>'
            f'<div class="space-y-2 p-3">{cards}</div></div>'
        )
        with HubSpotDashboardClient("unused", "unused") as client:
            client.page.set_content(html)
            output = StringIO()
            with redirect_stdout(output):
                lessons = client.get_todays_lessons(today=date(2026, 10, 23))
        self.assertEqual([lesson.name for lesson in lessons], ["active-main", "active-exercise"])
        for name in ("postponed-mobile", "postponed-gray", "transferred-out"):
            self.assertIn(f": {name}", output.getvalue())
