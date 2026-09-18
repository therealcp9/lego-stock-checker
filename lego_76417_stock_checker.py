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
    soup =
