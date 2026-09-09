#!/usr/bin/env python3
"""Check every listing in matches.json against the live eBay Browse API and
prune any that are no longer active (sold, ended, or removed).

Requires EBAY_CLIENT_ID / EBAY_CLIENT_SECRET env vars for an eBay production
application keyset (client credentials grant, public Browse API scope).
Run manually with `python scripts/verify_listings.py`, or via the
"Verify eBay listings" GitHub Actions workflow, which runs this daily.
"""

import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone

import requests

MATCHES_PATH = os.path.join(os.path.dirname(__file__), "..", "matches.json")
TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
ITEM_URL = "https://api.ebay.com/buy/browse/v1/item/{item_id}"
SCOPE = "https://api.ebay.com/oauth/api_scope"
MARKETPLACE_ID = os.environ.get("EBAY_MARKETPLACE_ID", "EBAY_US")
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30


def get_access_token():
    client_id = os.environ["EBAY_CLIENT_ID"]
    client_secret = os.environ["EBAY_CLIENT_SECRET"]
    resp = requests.post(
        TOKEN_URL,
        auth=(client_id, client_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials", "scope": SCOPE},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def is_still_listed(item_id, token):
    """True if the listing is still active, False if it's gone (sold/ended/
    removed). Raises if the API couldn't be reached or answered ambiguously,
    so the caller can choose to keep the item rather than guess."""
    url = ITEM_URL.format(item_id=urllib.parse.quote(item_id, safe=""))
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE_ID,
    }

    resp = None
    for attempt in range(1, MAX_RETRIES + 1):
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 404:
            return False
        if resp.status_code == 200:
            end_date = resp.json().get("itemEndDate")
            if end_date:
                try:
                    dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                    if dt < datetime.now(timezone.utc):
                        return False
                except ValueError:
                    pass
            return True
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        resp.raise_for_status()

    raise RuntimeError(
        f"could not verify {item_id} after {MAX_RETRIES} attempts "
        f"(last status {resp.status_code if resp is not None else 'n/a'})"
    )


def main():
    with open(MATCHES_PATH) as f:
        matches = json.load(f)

    token = get_access_token()

    kept, removed, errors = [], [], []
    for m in matches:
        item_id = m.get("item_id")
        if not item_id:
            kept.append(m)
            continue
        try:
            if is_still_listed(item_id, token):
                kept.append(m)
            else:
                removed.append(m)
        except Exception as e:
            print(f"WARNING: {item_id} ({m.get('title')}): {e}", file=sys.stderr)
            errors.append(m)
            kept.append(m)
        time.sleep(0.1)  # stay well under the API's rate limit

    print(
        f"Checked {len(matches)} listings: {len(removed)} no longer listed, "
        f"{len(errors)} could not be verified, {len(kept)} kept."
    )

    if removed:
        for m in removed:
            print(f"  removing: {m.get('item_id')} - {m.get('title')}")
        with open(MATCHES_PATH, "w") as f:
            json.dump(kept, f)
        print(f"Updated {MATCHES_PATH}")
    else:
        print("No changes needed.")


if __name__ == "__main__":
    main()
