# mini-code-reminder-automation

## Setup

Run these commands from this directory:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PLAYWRIGHT_BROWSERS_PATH=0 .venv/bin/python -m playwright install chromium
```

Browser binaries are installed alongside Playwright inside `.venv`, instead of
the shared user cache. The client defaults to this location at runtime.
Repeat the browser install command after upgrading Playwright.

Copy `.env.example` to `.env` and fill in your credentials, then run:

```bash
.venv/bin/python main.py
```


## WhatsApp reminders with Baileys

The Python scraper sends structured lesson data to a Node.js Baileys process.
Each exact lesson name maps to one WhatsApp group. The default command still
only prints lessons. Scraping dates use `Africa/Cairo`. WhatsApp messages display
the dashboard time minus one hour, labeled `Dutch time`. This is a fixed offset,
not an automatic daylight-saving timezone conversion. Lesson times use the
dashboard format, such as `6pm`.

Node.js 22.23.3 and its bundled npm are installed locally in `.venv/node` on this
computer. From the project root, make them available in your terminal:

```bash
export PATH="$PWD/.venv/node/bin:$PATH"
node --version
npm ci
```

For another computer, install Node.js 22 or newer and npm first. Python finds the
local runtime automatically, or uses `NODE_BINARY` / `node` from PATH. Baileys is
pinned to `7.0.0-rc14` (the registry's current latest release at setup); its
transitive dependencies are locked in `package-lock.json`.

### Configure and pair

Edit `groups.json` (initially `{}`) using `groups.example.json` as a guide.
Replace the example placeholder with your actual numeric group ID, including
`@g.us`. Keys must match lesson names exactly. Older IDs such as
`123456-7890@g.us` also work. Keep only the first test group's mapping until the
live test succeeds. The linked account must already be able to post in that group.

```bash
npm run pair
```

Scan the displayed QR from **WhatsApp → Linked devices → Link a device**.
Pairing sends no messages. The local session is stored in `.whatsapp/auth` and
reused by scheduled runs. If the account is logged out, scheduled runs exit with
an instruction to pair again. If pairing an expired session repeatedly fails,
stop any active reminder run, rename `.whatsapp/auth` to a private backup outside
the repository, and pair again. Keep `.whatsapp/sent.json` to retain send history.

Session files, group configuration, dependencies, and runtime files are ignored
by Git. Protect the session like a password. Baileys uses WhatsApp Web and is
not an official WhatsApp API.

### Preview, test, and send

```bash
HEADLESS=true .venv/bin/python main.py --dry-run
HEADLESS=true .venv/bin/python main.py --send-whatsapp
```

Dry-run prints the intended recipients and text without connecting to WhatsApp
or changing send history. It previews all mapped lessons, including those already
sent. `--groups /path/to/mapping.json` selects an alternate mapping; use this to
test a single group. `--dry-run` takes precedence over `--send-whatsapp`.

Messages look like:

```text
Reminder: scratch-1-177
Today, 2026-09-27 at 7pm (Dutch time)
```

Unmapped lessons are logged and skipped. No lessons means no messages. A lesson
is identified by the original dashboard date, exact name, original time, and destination group.
The display adjustment does not change the send-history identity. Success
is recorded immediately after Baileys returns a message ID; this is not a read
receipt. Reruns skip recorded successes and attempt remaining messages.
Failures are logged per recipient and return a nonzero exit code. A corrupt or
unwritable history stops sending rather than silently resetting it.

Do not delete `.whatsapp/sent.json` to retry a failed recipient: that could resend
successful reminders. A crash after delivery but before recording, or a send
timeout, leaves delivery uncertain; inspect the group before rerunning. Changing
a lesson's time or group creates a new reminder identity. There are no automatic
retries. A shared file lock prevents pairing and Python sending runs from
running concurrently. Invoke sending through Python, not the internal Node entry
point directly.

### Scheduling with cron

Cron can invoke the program directly using absolute paths:

```bash
HEADLESS=true /absolute/path/to/project/.venv/bin/python /absolute/path/to/project/main.py --send-whatsapp
```

Replace `/absolute/path/to/project` with your project directory. The program
loads its `.env`, group mapping, Node runtime, and WhatsApp session relative to
the project. `HEADLESS=true` avoids waiting for keyboard input. Configure the
schedule and output logging in your crontab; the computer must be awake and online.

### Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
npm test
```

Tests use mocked WhatsApp sending and connections. They cover routing, empty
results, Cairo date boundaries, dry-run behavior, partial
failures, persistent deduplication, invalid history, and expired sessions.
