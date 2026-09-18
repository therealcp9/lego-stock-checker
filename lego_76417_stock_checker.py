#!/usr/bin/env python3
"""
LEGO 76417 (Gringotts Wizarding Bank - Collectors' Edition) stock checker.

Does ONE check of the LEGO Australia product page and exits. Designed to be
run on a schedule (GitHub Actions, cron, Task Scheduler, etc.) rather than
looping forever itself.

Counts the set as "in stock" only when:
  - the page shows an "Add to Bag" button, AND
  - the text "Temporarily out of stock" is NOT present, AND
  - LEGO's own embedded stock flag (a <meta property="product:availability">
    tag LEGO renders server-side) doesn't say "out of stock".

--- NOTIFICATIONS ---
Reads config from environment variables (so secrets never sit in the code):
  NTFY_TOPIC        - required. Your private ntfy.sh topic name.
  USE_TWILIO        - optional, set to "true" to also send a real SMS.
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, TWILIO_TO_NUMBER
                    - required if USE_TWILIO is true.

Exit codes: 0 = ran fine (in stock or not), 1 = the request/page check failed.
"""

import os
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

PRODUCT_URL = "https://www.lego.com/en-au/product/gringotts-wizarding-bank-collectors-edition-76417"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-AU,en;q=0.9",
}

# (connect_timeout, read_timeout) in seconds - a plain float timeout only
# bounds gaps between bytes once a connection exists; it does NOT reliably
# bound a hanging connection attempt. Passing a tuple bounds both phases
# explicitly, so this can never hang indefinitely.
REQUEST_TIMEOUT = (10, 20)


def log(msg: str):
    print(msg, flush=True)


def check_stock():
    log(f"Requesting {PRODUCT_URL} (timeout={REQUEST_TIMEOUT}) ...")
    resp = requests.get(PRODUCT_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    log(f"Got response: HTTP {resp.status_code}, {len(resp.content)} bytes")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    meta_tag = soup.find("meta", attrs={"property": "product:availability"})
    availability_meta = meta_tag["content"].strip().lower() if meta_tag and meta_tag.get("content") else None

    page_text = soup.get_text(" ", strip=True).lower()
    out_of_stock_text = "temporarily out of stock" in page_text
    add_to_bag_present = bool(re.search(r"add to bag", page_text))

    in_stock = (
        add_to_bag_present
        and not out_of_stock_text
        and availability_meta != "out of stock"
    )
    return in_stock, availability_meta, add_to_bag_present, out_of_stock_text


def notify_ntfy(message: str):
    topic = os.environ.get("NTFY_TOPIC", "")
    if not topic:
        log("!! NTFY_TOPIC env var not set - skipping ntfy notification.")
        return
    try:
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers={"Title": "LEGO 76417 back in stock!", "Priority": "urgent", "Tags": "lego"},
            timeout=REQUEST_TIMEOUT,
        )
        log("Sent ntfy notification.")
    except requests.RequestException as e:
        log(f"Failed to send ntfy notification: {e}")


def notify_twilio(message: str):
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_number = os.environ.get("TWILIO_FROM_NUMBER", "")
    to_number = os.environ.get("TWILIO_TO_NUMBER", "")
    if not all([sid, token, from_number, to_number]):
        log("!! Twilio env vars incomplete - skipping SMS.")
        return
    try:
        resp = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data={"From": from_number, "To": to_number, "Body": message},
            auth=(sid, token),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code >= 300:
            log(f"Twilio error {resp.status_code}: {resp.text}")
        else:
            log("Sent SMS via Twilio.")
    except requests.RequestException as e:
        log(f"Failed to send Twilio SMS: {e}")


def main():
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    log(f"=== Run started {timestamp} ===")
    try:
        in_stock, availability_meta, add_to_bag, oos_text = check_stock()
    except requests.RequestException as e:
        # If LEGO is blocking/dropping traffic from this runner (common
        # anti-bot behaviour against cloud/CI IP ranges), this is where
        # you'd see it - now bounded to ~30 seconds max instead of hanging.
        log(f"Request failed: {type(e).__name__}: {e}")
        sys.exit(1)

    log(
        f"availability_meta={availability_meta!r} "
        f"add_to_bag={add_to_bag} out_of_stock_text={oos_text} "
        f"-> in_stock={in_stock}"
    )

    if in_stock:
        message = f"LEGO 76417 Gringotts Wizarding Bank is BACK IN STOCK! {PRODUCT_URL}"
        notify_ntfy(message)
        if os.environ.get("USE_TWILIO", "").lower() == "true":
            notify_twilio(message)

    log("=== Run finished ===")
    sys.exit(0)


if __name__ == "__main__":
    main()
