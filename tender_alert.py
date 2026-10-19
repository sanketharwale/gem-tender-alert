import json
import os
import re
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://bidplus.gem.gov.in"
LIST_URL = f"{BASE_URL}/all-bids"
SEEN_FILE = Path("seen_bids.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GeMTenderAlert/1.0; public listing monitor)",
    "Accept": "text/html,application/xhtml+xml",
}


def load_seen():
    try:
        return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return set()


def extract_bids(html):
    """Extract bid-like records from the public listing HTML; portal markup can change."""
    soup = BeautifulSoup(html, "html.parser")
    found = {}
    for link in soup.find_all("a", href=True):
        text = " ".join(link.get_text(" ", strip=True).split())
        href = urljoin(BASE_URL, link["href"])
        combined = f"{text} {href}"
        # Keep links that look like GeM bid detail links and have useful visible text.
        if not text or not re.search(r"(bid|bids|bid-details|showbid|bidid)", combined, re.I):
            continue
        if len(text) < 8:
            continue
        container = link
        for _ in range(4):
            if container.parent:
                container = container.parent
        details = " ".join(container.get_text(" ", strip=True).split())
        if len(details) < len(text):
            details = text
        key_match = re.search(r"(GEM/[A-Z0-9/_-]{5,}|\b\d{5,}\b)", details, re.I)
        bid_id = key_match.group(1) if key_match else href
        found[bid_id] = {
            "bid_id": bid_id,
            "title": text[:300],
            "details": details[:1800],
            "url": href,
        }
    return list(found.values())


def send_email(new_bids):
    sender = os.environ.get("EMAIL_SENDER", "").strip()
    password = os.environ.get("EMAIL_APP_PASSWORD", "").strip()
    recipient = os.environ.get("ALERT_TO_EMAIL", sender).strip()
    if not sender or not password or not recipient:
        raise RuntimeError(
            "Missing EMAIL_SENDER, EMAIL_APP_PASSWORD, or ALERT_TO_EMAIL GitHub Actions secrets."
        )

    msg = EmailMessage()
    msg["Subject"] = f"GeM Tender Alert: {len(new_bids)} new public listing(s)"
    msg["From"] = sender
    msg["To"] = recipient
    lines = [
        f"Daily GeM public bid listing check — {datetime.now().astimezone():%d %b %Y, %I:%M %p %Z}",
        "",
        "Newly detected listings (verify all details and deadlines on the official portal):",
        "",
    ]
    for bid in new_bids:
        lines.extend([
            f"Bid ID: {bid['bid_id']}",
            f"Title/link text: {bid['title']}",
            f"Details: {bid['details']}",
            f"Official link: {bid['url']}",
            "-" * 72,
        ])
    msg.set_content("\n".join(lines))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)


def main():
    response = requests.get(LIST_URL, headers=HEADERS, timeout=45)
    response.raise_for_status()
    bids = extract_bids(response.text)
    if not bids:
        raise RuntimeError(
            "No bid records were extracted. GeM may have changed its public page markup or requires a session; check the workflow log before relying on alerts."
        )

    seen = load_seen()
    new_bids = [bid for bid in bids if bid["bid_id"] not in seen]
    if new_bids:
        send_email(new_bids)
        seen.update(bid["bid_id"] for bid in new_bids)
        SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2), encoding="utf-8")
        print(f"Sent {len(new_bids)} newly detected listing(s).")
    else:
        # Persist an empty file on the first successful run so the workflow can commit state.
        if not SEEN_FILE.exists():
            SEEN_FILE.write_text("[]", encoding="utf-8")
        print(f"No new listings detected. Checked {len(bids)} extracted listing(s).")


if __name__ == "__main__":
    main()
