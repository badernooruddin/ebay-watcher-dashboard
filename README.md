# eBay Watcher Dashboard

Static dashboard (`index.html`) that renders listings from `matches.json`,
which is kept up to date by an external watcher bot.

## Daily listing verification

`.github/workflows/verify-listings.yml` runs `scripts/verify_listings.py`
once a day (and on manual dispatch). It checks every listing in
`matches.json` against the live eBay Browse API and removes any that are
sold, ended, or no longer found, committing the change straight to the
default branch if anything was pruned.

Listings the API can't answer for confidently (timeouts, rate limits,
persistent server errors) are left in place rather than guessed away.

### Setup

The workflow needs an eBay production application keyset (Browse API,
`https://api.ebay.com/oauth/api_scope`) from the
[eBay Developers Program](https://developer.ebay.com/). Add it as repository
secrets under **Settings → Secrets and variables → Actions**:

- `EBAY_CLIENT_ID`
- `EBAY_CLIENT_SECRET`

Without these secrets set, the scheduled run will fail at the OAuth step and
`matches.json` will be left untouched.

To run it manually: **Actions → Verify eBay listings → Run workflow**, or
locally with `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` set:

```
pip install -r requirements.txt
python scripts/verify_listings.py
```
