"""Route scraped lessons to the local Baileys sender."""

import fcntl
import json
import os
import re
import shutil
import subprocess
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent


def lesson_today(now=None):
    source_zone = ZoneInfo(os.environ.get("LESSON_TIMEZONE", "Asia/Damascus")) # default to mine LOL
    return (now or datetime.now(source_zone)).astimezone(source_zone).date()


def load_groups(path):
    mapping = json.loads(Path(path).read_text())
    if not isinstance(mapping, dict) or any(
        not isinstance(name, str) or not name.strip()
        or not isinstance(jid, str) or not re.fullmatch(r"[0-9]+(?:-[0-9]+)?@g\.us", jid)
        for name, jid in mapping.items()
    ):
        raise ValueError("Group mapping must contain lesson names and numeric WhatsApp group IDs ending in @g.us")
    return mapping


def build_messages(lessons, groups):
    source_zone = ZoneInfo(os.environ.get("LESSON_TIMEZONE", "Asia/Damascus"))
    dutch_zone = ZoneInfo("Europe/Amsterdam")
    messages = []
    seen = set()
    for lesson in lessons:
        group = groups.get(lesson.name)
        if group is None:
            print(f"Skipping unmapped lesson: {lesson.name}", flush=True)
            continue
        key = (lesson.day.isoformat(), lesson.name, lesson.time, group)
        if key in seen:
            continue
        seen.add(key)
        time_format = "%I:%M%p" if ":" in lesson.time else "%I%p"
        parsed_time = datetime.strptime(lesson.time.strip(), time_format).time()
        source_time = datetime.combine(lesson.day, parsed_time, tzinfo=source_zone)
        dutch_time = source_time.astimezone(dutch_zone)
        displayed_time = dutch_time.strftime(time_format).lstrip("0").lower()
        displayed_date = dutch_time.date().isoformat()
        if dutch_time.date() == lesson.day:
            displayed_date = f"Today, {displayed_date}"
        # Keep the original time in the identity so template edits do not resend reminders.
        messages.append(dict(date=key[0], name=lesson.name, time=lesson.time,
                             groupId=group,
                             text=(f"Reminder: {lesson.name}\n{displayed_date} at "
                                   f"{displayed_time} "
                                   "(Dutch time)"
                                   )))
    return messages


@contextmanager
def send_lock():
    with (ROOT / ".whatsapp.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB) # Acquire an exclusive lock, non blocking, works only on Unix. I plan to remove it if I move it to Windows.
        except BlockingIOError as exc:
            raise RuntimeError("Another WhatsApp run or pairing process is active") from exc
        yield


def send_messages(messages):
    if not messages:
        print("No mapped lessons to send", flush=True)
        return
    local_node = ROOT / ".venv/node/bin/node" #code installed node in .venv, but we keep the option to use a system node if available(like my rasperry pi)
    node = os.environ.get("NODE_BINARY") or (str(local_node) if local_node.exists() else shutil.which("node"))
    if not node:
        raise RuntimeError("Node.js is missing; install it or set NODE_BINARY")
    try:
        subprocess.run([node, str(ROOT / "whatsapp/sender.mjs")],
                       input=json.dumps(messages), text=True, check=True, cwd=ROOT,
                       timeout=120 + 45 * len(messages))
    except subprocess.CalledProcessError as exc:
        # The sender has already printed the actionable error.
        raise SystemExit(exc.returncode) from None
