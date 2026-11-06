#!/usr/bin/env python3
"""One-time sign-in for gbp_post.py. Run it on your own computer.

The publisher posts as the profile's owner or manager without anyone signing
in again, using a refresh token. This script produces that token: it opens
Google's sign-in in your browser, catches the reply on a local port, and prints
the token together with the account and location IDs the publisher needs.

    python3 gbp_auth.py --client-id <id> --client-secret <secret>

Sign in as the account that owns or manages the Business Profile. The OAuth
client must be a "Desktop app" client, and the consent screen must be "In
production": in "Testing", Google expires the refresh token after 7 days and
posting stops without warning.

Put the printed values in the routine environment: GBP_CLIENT_ID,
GBP_CLIENT_SECRET and GBP_REFRESH_TOKEN under API credentials (they are
secrets), GBP_ACCOUNT_ID and GBP_LOCATION_ID as plain variables.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import os
import secrets
import sys
import urllib.parse
import webbrowser

import requests

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/business.manage"
ACCOUNTS_API = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
LOCATIONS_API = "https://mybusinessbusinessinformation.googleapis.com/v1/{account}/locations"


def catch_code(state: str) -> tuple[http.server.HTTPServer, str, dict[str, str]]:
    """A one-shot server on a free local port, its redirect URI, and the dict
    the reply's code (or error) lands in once the server handles a request."""
    result: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (stdlib name)
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] != state:
                result["error"] = "state mismatch"
            elif "error" in q:
                result["error"] = q["error"][0]
            else:
                result["code"] = q.get("code", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Signed in. You can close this tab and return to the terminal.")

        def log_message(self, *args):  # keep the terminal quiet
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}"
    return server, redirect_uri, result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-id", default=os.environ.get("GBP_CLIENT_ID", ""))
    ap.add_argument("--client-secret", default=os.environ.get("GBP_CLIENT_SECRET", ""))
    args = ap.parse_args()
    if not args.client_id or not args.client_secret:
        sys.exit("Pass --client-id and --client-secret (from the Desktop app OAuth client).")

    state = secrets.token_urlsafe(16)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()

    server, redirect_uri, result = catch_code(state)
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": args.client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256",
    })
    print("Opening Google sign-in. If no browser opens, paste this into one:\n\n" + url + "\n")
    webbrowser.open(url)
    server.handle_request()
    server.server_close()
    if "error" in result or not result.get("code"):
        sys.exit(f"Sign-in failed: {result.get('error', 'no code returned')}")

    r = requests.post(TOKEN_URL, data={
        "client_id": args.client_id, "client_secret": args.client_secret,
        "code": result["code"], "code_verifier": verifier,
        "grant_type": "authorization_code", "redirect_uri": redirect_uri,
    }, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Token exchange failed ({r.status_code}): {r.text[:300]}")
    tokens = r.json()
    refresh = tokens.get("refresh_token")
    if not refresh:
        sys.exit("Google returned no refresh token. Remove the app's access at "
                 "myaccount.google.com/permissions and run this again.")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    print("GBP_REFRESH_TOKEN (secret, goes under API credentials):")
    print(f"  {refresh}\n")

    accounts = requests.get(ACCOUNTS_API, headers=headers, timeout=30)
    if accounts.status_code != 200:
        sys.exit(f"Listing accounts failed ({accounts.status_code}): {accounts.text[:300]}\n"
                 "Check that the My Business Account Management API is enabled in the project.")
    for acc in accounts.json().get("accounts", []):
        print(f"Account: {acc.get('accountName', '')}  ({acc.get('type', '')})")
        print(f"  GBP_ACCOUNT_ID={acc['name'].split('/')[-1]}")
        locs = requests.get(LOCATIONS_API.format(account=acc["name"]), headers=headers,
                            params={"readMask": "name,title,websiteUri", "pageSize": 100}, timeout=30)
        if locs.status_code != 200:
            print(f"  (could not list locations: {locs.status_code} {locs.text[:200]})")
            continue
        for loc in locs.json().get("locations", []):
            print(f"  Location: {loc.get('title', '')}  {loc.get('websiteUri', '')}")
            print(f"    GBP_LOCATION_ID={loc['name'].split('/')[-1]}")
    print("\nUse the account and location of the verified profile you want to post to.")


if __name__ == "__main__":
    main()
