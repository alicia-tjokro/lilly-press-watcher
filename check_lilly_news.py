#!/usr/bin/env python3
"""
Check Eli Lilly's press release RSS feed for new entries and email
a notification to everyone listed in recipients.txt if anything new
has been published.

State (the IDs of entries we've already seen) is stored in
last_seen.json so the script knows what's "new" between runs.
"""

import json
import os
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

import feedparser

RSS_URL = "https://investor.lilly.com/rss/news-releases.xml?items=10"
STATE_FILE = Path("last_seen.json")
RECIPIENTS_FILE = Path("recipients.txt")


def load_last_seen():
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()


def save_last_seen(ids):
    STATE_FILE.write_text(json.dumps(sorted(ids)))


def load_recipients():
    """One email address per line. Blank lines and lines starting
    with # are ignored, so someone can be paused without deleting
    their line."""
    if not RECIPIENTS_FILE.exists():
        raise SystemExit(f"{RECIPIENTS_FILE} not found -- add at least one email address to it.")
    addrs = []
    for line in RECIPIENTS_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            addrs.append(line)
    if not addrs:
        raise SystemExit(f"{RECIPIENTS_FILE} has no active addresses.")
    return addrs


def entry_id(entry):
    return entry.get("id") or entry.get("link")


def send_email(new_entries, recipients):
    smtp_server = os.environ["SMTP_SERVER"]
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    from_addr = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]

    blocks = []
    for entry in new_entries:
        title = entry.get("title", "Untitled")
        link = entry.get("link", "")
        published = entry.get("published", "")
        blocks.append(f"{title}\n{published}\n{link}")
    body = "\n\n---\n\n".join(blocks)

    subject = (
        "New Eli Lilly press release"
        if len(new_entries) == 1
        else f"{len(new_entries)} new Eli Lilly press releases"
    )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_addr
    # Each recipient just sees themself in "To" -- the real delivery
    # list is passed separately below, so nobody's address is exposed
    # to everyone else on the list (same trick a Bcc does).
    msg["To"] = from_addr

    with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
        server.login(from_addr, password)
        server.sendmail(from_addr, recipients, msg.as_string())

    print(f"Sent email to {len(recipients)} recipient(s): {subject}")


def main():
    feed = feedparser.parse(RSS_URL)

    if feed.bozo:
        print(f"Warning: feed did not parse cleanly: {feed.bozo_exception}")

    if not feed.entries:
        print("No entries found in feed. Nothing to do.")
        return

    last_seen = load_last_seen()
    first_run = len(last_seen) == 0

    current_ids = {entry_id(e) for e in feed.entries}
    new_ids = current_ids - last_seen
    new_entries = [e for e in feed.entries if entry_id(e) in new_ids]

    if first_run:
        print(f"First run: recording {len(current_ids)} existing entries, no email sent.")
    elif new_entries:
        plural = "y" if len(new_entries) == 1 else "ies"
        print(f"Found {len(new_entries)} new entr{plural}.")
        recipients = load_recipients()
        send_email(new_entries, recipients)
    else:
        print("No new entries.")

    save_last_seen(current_ids)


if __name__ == "__main__":
    main()
