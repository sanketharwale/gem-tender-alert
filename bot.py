#!/usr/bin/env python3
"""GeM tender alerts for Maharashtra / Osmanabad-Dharashiv.

Uses only GeM's publicly accessible bid listing endpoint. No login, CAPTCHA,
or access-control bypass is attempted. The portal may change its interface.
"""
import json
import os
import re
import smtplib
import ssl
import sys
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, HTTPCookieProcessor, build_opener
from http.cookiejar import CookieJar

BASE_URL = "https://bidplus.gem.gov.in"
ALL_BIDS_URL = f"{BASE_URL}/all-bids"
DATA_URL = f"{BASE_URL}/all-bids-data"
STATE_FILE = Path("seen_bids.json")
USER_AGENT = "GeM-Tender-Alert/1.0 (public tender monitoring; contact via repository owner)"
SEARCH_TERMS = ["Osmanabad", "Dharashiv", "Maharashtra"]
LOCATION_TERMS = ("osmanabad", "dharashiv")
MAX_PAGES_PER_TERM = int(os.getenv("MAX_PAGES_PER_TERM", "3"))
REQUEST_PAUSE_SECONDS = 1.0

class GeMSession:
    def __init__(self):
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self.csrf = None

    def request(self, url, data=None, headers=None):
        headers = dict(headers or {})
        headers.setdefault("User-Agent", USER_AGENT)
        req = Request(url, data=data.encode() if isinstance(data, str) else data, headers=headers)
        with self.opener.open(req, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")

    def init(self):
        html = self.request(ALL_BIDS_URL, headers={"Accept": "text/html"})
        match = re.search(r"csrf_bd_gem_nk.*?'([a-f0-9]{32})'", html, re.I)
        if not match:
            raise RuntimeError("Could not find GeM CSRF token; portal page may have changed.")
        self.csrf = match.group(1)

    def search(self, query, page):
        if not self.csrf:
            self.init()
        payload = {
            "page": page,
            "param": {"searchBid": query, "searchType": "fullText"},
            "filter": {
                "bidStatusType": "ongoing_bids",
                "byType": "all",
                "highBidValue": "",
                "byEndDate": {"from": "", "to": ""},
                "sort": "Bid-End-Date-Latest",
            },
        }
        body = urlencode({
            "payload": json.dumps(payload, separators=(",", ":")),
            "csrf_bd_gem_nk": self.csrf,
        })
        raw = self.request(DATA_URL, data=body, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Referer": ALL_BIDS_URL,
            "Origin": BASE_URL,
            "X-Requested-With": "XMLHttpRequest",
        })
        data = json.loads(raw)
        if data.get("code") in (404, "404"):
            return 0, []
        if data.get("code") != 200:
            raise RuntimeError(f"GeM returned unexpected response code: {data.get('code')}")
        response = data.get("response", {}).get("response", {})
        return int(response.get("numFound", 0) or 0), response.get("docs", []) or []

def first(doc, *keys):
    for key in keys:
        value = doc.get(key)
        if isinstance(value, list):
            value = value[0] if value else ""
        if value not in (None, ""):
            return str(value).strip()
    return ""

def normalize(doc):
    bid_number = first(doc, "b_bid_number", "bid_number")
    bid_id = first(doc, "b_id", "bid_id")
    title = first(doc, "bbt_title", "b_category_name", "title", "category")
    category = first(doc, "b_category_name", "category")
    department = first(doc, "ba_official_details_deptName", "department", "deptName")
    ministry = first(doc, "ba_official_details_minName", "ministry", "minName")
    start = first(doc, "final_start_date_sort", "start_date")
    deadline = first(doc, "final_end_date_sort", "end_date", "deadline")
    url = f"{BASE_URL}/showbidDocument/{bid_id}" if bid_id else ALL_BIDS_URL
    return {
        "bid_number": bid_number,
        "bid_id": bid_id,
        "title": title or category or "GeM bid",
        "category": category,
        "department": department,
        "ministry": ministry,
        "start_date": start,
        "deadline": deadline,
        "url": url,
        "raw_search_text": " ".join(str(v) for v in doc.values()).lower(),
    }

def is_target_bid(bid):
    text = " ".join([
        bid.get("title", ""), bid.get("category", ""), bid.get("department", ""),
        bid.get("ministry", ""), bid.get("raw_search_text", ""),
    ]).lower()
    return any(term in text for term in LOCATION_TERMS)

def load_seen():
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data.get("seen", []))
    except FileNotFoundError:
        return set()
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Warning: could not read saved state: {exc}", file=sys.stderr)
        return set()

def save_seen(seen):
    STATE_FILE.write_text(
        json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(),
                    "seen": sorted(seen)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

def send_email(bids):
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "465"))
    sender = os.environ["EMAIL_SENDER"]
    password = os.environ["EMAIL_APP_PASSWORD"]
    recipient = os.getenv("EMAIL_RECIPIENT", "sanketharwale0078@gmail.com")
    msg = EmailMessage()
    msg["Subject"] = f"GeM Tender Alert: {len(bids)} new Maharashtra / Dharashiv bid(s)"
    msg["From"] = sender
    msg["To"] = recipient
    lines = [
        f"New public GeM bid(s) found at {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}.",
        "",
        "Please verify every detail and deadline on the official GeM portal.",
        "",
    ]
    for bid in bids:
        lines.extend([
            f"Bid: {bid['bid_number'] or bid['bid_id'] or 'Not listed'}",
            f"Title: {bid['title']}",
            f"Department: {bid['department'] or 'Not listed'}",
            f"Ministry: {bid['ministry'] or 'Not listed'}",
            f"Start date: {bid['start_date'] or 'Not listed'}",
            f"Deadline: {bid['deadline'] or 'Not listed'}",
            f"Official document: {bid['url']}",
            "-" * 60,
        ])
    msg.set_content("\n".join(lines))
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
        server.login(sender, password)
        server.send_message(msg)

def main():
    seen = load_seen()
    found = {}
    session = GeMSession()
    for term in SEARCH_TERMS:
        print(f"Searching GeM public bids for: {term}")
        try:
            total, _ = session.search(term, 1)
            pages = min(MAX_PAGES_PER_TERM, max(1, (total + 9) // 10))
            for page in range(1, pages + 1):
                _, docs = session.search(term, page)
                for raw in docs:
                    bid = normalize(raw)
                    key = bid["bid_number"] or bid["bid_id"]
                    if key and is_target_bid(bid):
                        found[key] = bid
                time.sleep(REQUEST_PAUSE_SECONDS)
        except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError) as exc:
            print(f"Search failed for '{term}': {exc}", file=sys.stderr)
            raise
    new_bids = [bid for key, bid in found.items() if key not in seen]
    print(f"Matching bids: {len(found)}; new bids: {len(new_bids)}")
    if new_bids:
        send_email(new_bids)
        print(f"Sent alert email to {os.getenv('EMAIL_RECIPIENT', 'sanketharwale0078@gmail.com')}")
    else:
        print("No new matching bids; no email sent.")
    seen.update(found.keys())
    save_seen(seen)

if __name__ == "__main__":
    main()
