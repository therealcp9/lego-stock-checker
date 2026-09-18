#!/usr/bin/env python3
"""
LEGO 76417 (Gringotts Wizarding Bank - Collectors' Edition) stock checker.

Checks the LEGO Australia product page every few minutes. Counts the set as
"in stock" only when:
  - the page shows an "Add to Bag" button, AND
  - the text "Temporarily out of stock" is NOT present, AND
  - LEGO's own embedded stock flag (a <meta property="product:availability">
    tag that LEGO renders server-side) doesn't say "out of stock".

When all three agree it's in stock, it sends you a phone notification and
stops.

--- ABOUT THE NOTIFICATION ---
Optus (like Australian carriers generally) doesn't offer a free "email an
address, it arrives as an SMS" gateway the way some US carriers do, so your
carrier isn't actually relevant here. This script uses ntfy.sh by default:
it's free, needs no signup/API key, and pushes a notification straight to
your phone via an app. A Twilio option (real SMS, ~$0.06/message, works
regardless of carrier) is included below, commented out, if you'd rather
receive an actual text.

--- SETUP ---
1. pip install requests beautifulsoup4
2. Install the ntfy app on your phone (Google Play / Apple App Store) and
   subscribe to a topic name of your choosing (make it hard to guess, e.g.
   "lego76417-yourname-a8f3" - anyone who knows the topic name can read or
   post to it, since ntfy.sh's free tier is public-by-topic-name).
3. Put that topic name in NTFY_TOPIC below.
4. Run: python3 lego_76417_stock_checker.py
   Leave it running (it checks every 5 minutes by default), or see the
   note at the bottom about running it via cron/Task Scheduler instead.
"""

import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# CONFIG - edit these
# ---------------------------------------------------------------------------

PRODUCT_URL = "https://www.lego.com/en-au/product/gringotts-wizarding-bank-collectors-edition-76417"
CHECK_INTERVAL_SECONDS = 5 * 60  # how often to check (5 minutes)

NTFY_TOPIC = "lego76417-check-if-instock-or-not-987654321"  # <-- set this to your own private topic name

# Optional: real SMS via Twilio instead of/as well as ntfy.
# Sign up at twilio.com, buy/verify a number, then fill these in and set
# USE_TWILIO = True. Carrier (Optus) doesn't matter for this - it just needs
# your number in international format.
USE_TWILIO = False
TWILIO_ACCOUNT_SID = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TWILIO_AUTH_TOKEN = "your_auth_token"
TWILIO_FROM_NUMBER = "+1xxxxxxxxxx"       # the Twilio number you were assigned
TWILIO_TO_NUMBER = "+614xxxxxxxx"         # your phone, Australian format e.g. +61412345678

# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-AU,en;q=0.9",
}


def check_stock():
    """Fetch the product page and work out whether the set is buyable.

    Returns (in_stock: bool, availability_meta: str | None, add_to_bag: bool,
    out_of_stock_text: bool) for logging/debugging.
    """
    resp = requests.get(PRODUCT_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # LEGO renders this Open Graph / schema.org-style meta tag server-side
    # with the real stock status - it's the most reliable signal.
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
    if not NTFY_TOPIC or "CHANGE-ME" in NTFY_TOPIC:
        print("!! NTFY_TOPIC is not set - skipping ntfy notification. "
              "Edit NTFY_TOPIC in the script.")
        return
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": "LEGO 76417 back in stock!", "Priority": "urgent", "Tags": "lego"},
            timeout=10,
        )
        print("Sent ntfy notification.")
    except requests.RequestException as e:
        print(f"Failed to send ntfy notification: {e}")


def notify_twilio(message: str):
    try:
        resp = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
            data={"From": TWILIO_FROM_NUMBER, "To": TWILIO_TO_NUMBER, "Body": message},
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=15,
        )
        if resp.status_code >= 300:
            print(f"Twilio error {resp.status_code}: {resp.text}")
        else:
            print("Sent SMS via Twilio.")
    except requests.RequestException as e:
        print(f"Failed to send Twilio SMS: {e}")


def notify(message: str):
    notify_ntfy(message)
    if USE_TWILIO:
        notify_twilio(message)


def main():
    print(f"Watching {PRODUCT_URL}")
    print(f"Checking every {CHECK_INTERVAL_SECONDS // 60} minutes. Ctrl+C to stop.\n")

    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            in_stock, availability_meta, add_to_bag, oos_text = check_stock()
            print(
                f"[{timestamp}] availability_meta={availability_meta!r} "
                f"add_to_bag={add_to_bag} out_of_stock_text={oos_text} "
                f"-> in_stock={in_stock}"
            )

            if in_stock:
                message = f"LEGO 76417 Gringotts Wizarding Bank is BACK IN STOCK! {PRODUCT_URL}"
                notify(message)
                print("Done - stopping checker.")
                sys.exit(0)

        except requests.RequestException as e:
            # If LEGO starts blocking these requests (403s etc.), this is
            # where you'd see it - it may mean their bot protection has
            # kicked in and a plain requests script isn't enough anymore.
            print(f"[{timestamp}] Request failed: {e}")

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
