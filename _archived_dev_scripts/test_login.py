"""Manual login checker; requires an explicitly supplied non-production URL."""

import getpass
import os
import sys

import requests


url = os.getenv("LOGIN_TEST_URL", "").strip()
username = os.getenv("LOGIN_TEST_USERNAME", "").strip()
if not url or not username:
    raise SystemExit("Set LOGIN_TEST_URL and LOGIN_TEST_USERNAME explicitly before running.")
if "railway.app" in url or "railway.com" in url:
    raise SystemExit("Refusing to submit credentials to a production Railway URL from this script.")

session = requests.Session()
response = session.get(url, timeout=15)
csrf = session.cookies.get("csrf_token")
if not csrf:
    raise SystemExit("The site did not issue a CSRF token.")

response = session.post(
    url,
    data={"email": username, "password": getpass.getpass("Password: "), "csrf_token": csrf},
    headers={"X-CSRF-Token": csrf},
    allow_redirects=False,
    timeout=15,
)
print(f"HTTP {response.status_code}")
if response.status_code in (302, 303):
    print(f"Redirect: {response.headers.get('Location', '')}")
