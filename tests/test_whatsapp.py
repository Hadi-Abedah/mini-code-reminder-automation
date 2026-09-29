import json
import tempfile
import subprocess
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from helpers import Lesson
from whatsapp import build_messages, cairo_today, load_groups, send_messages, send_lock


class RoutingTests(unittest.TestCase):
    def test_routes_exact_names_and_deduplicates(self):
        lesson = Lesson(date(2026, 9, 27), "8pm", "scratch-1-177")
        messages = build_messages([lesson, lesson, Lesson(lesson.day, "9pm", "other")],
                                  {lesson.name: "120363123@g.us"})
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["text"], "Reminder: scratch-1-177\nToday, 2026-09-27 at 7pm (Dutch time)")
        self.assertEqual(messages[0]["groupId"], "120363123@g.us")
        self.assertEqual(messages[0]["time"], "8pm")

    def test_empty_lessons_do_not_launch_node(self):
        self.assertEqual(build_messages([], {}), [])
        with patch("whatsapp.subprocess.run") as run:
            send_messages([])
            run.assert_not_called()

    def test_bad_mapping_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "groups.json"
            for value in ([], {"lesson": "someone@s.whatsapp.net"}, {"lesson": 123}):
                filename.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    load_groups(filename)
            filename.write_text('{"lesson": "123-456@g.us"}')
            self.assertEqual(load_groups(filename), {"lesson": "123-456@g.us"})

    def test_cairo_date_crosses_utc_midnight_boundary(self):
        self.assertEqual(cairo_today(datetime(2026, 9, 26, 22, tzinfo=timezone.utc)), date(2026, 9, 27))
        self.assertEqual(cairo_today(datetime(2026, 1, 26, 22, 30, tzinfo=timezone.utc)), date(2026, 1, 27))

    def test_subprocess_gets_structured_json(self):
        payload = [{"name": "hello ' \" world"}]
        with patch("whatsapp.subprocess.run") as run:
            send_messages(payload)
            self.assertEqual(json.loads(run.call_args.kwargs["input"]), payload)
            self.assertTrue(run.call_args.kwargs["check"])

    def test_sender_error_keeps_exit_code_without_python_traceback(self):
        with patch("whatsapp.subprocess.run", side_effect=subprocess.CalledProcessError(1, "node")):
            with self.assertRaises(SystemExit) as error:
                send_messages([{"name": "test"}])
            self.assertEqual(error.exception.code, 1)

    def test_lock_prevents_overlapping_runs(self):
        with tempfile.TemporaryDirectory() as directory, patch("whatsapp.ROOT", Path(directory)):
            with send_lock():
                with self.assertRaisesRegex(RuntimeError, "Another WhatsApp"):
                    with send_lock():
                        self.fail("Second run acquired the lock")
            with send_lock():
                pass

    def test_default_command_does_not_load_groups_or_send(self):
        import main
        with patch("sys.argv", ["main.py"]), \
             patch.dict("os.environ", {"HUBSPOT_EMAIL": "test", "HUBSPOT_PASSWORD": "test", "HEADLESS": "true"}), \
             patch.object(main, "HubSpotDashboardClient") as client, \
             patch.object(main, "load_groups") as groups, \
             patch.object(main, "send_messages") as send:
            client.return_value.__enter__.return_value.get_todays_lessons.return_value = []
            main.main()
            groups.assert_not_called()
            send.assert_not_called()

    def test_dry_run_never_sends(self):
        import main
        with tempfile.TemporaryDirectory() as directory:
            mapping = Path(directory) / "groups.json"
            mapping.write_text('{"lesson": "123@g.us"}')
            with patch("sys.argv", ["main.py", "--send-whatsapp", "--dry-run", "--groups", str(mapping)]), \
                 patch.dict("os.environ", {"HUBSPOT_EMAIL": "test", "HUBSPOT_PASSWORD": "test", "HEADLESS": "true"}), \
                 patch.object(main, "HubSpotDashboardClient") as client, \
                 patch.object(main, "send_messages") as send:
                client.return_value.__enter__.return_value.get_todays_lessons.return_value = [Lesson(date(2026, 9, 27), "8pm", "lesson")]
                main.main()
                send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
