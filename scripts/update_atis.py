#!/usr/bin/env python3
"""
Fetch the current KPIT ATIS letter from PIT Airport IDS zone-update endpoint
and write it to atis.json (repo root) for GitHub Pages / your board to consume.

This version is GitHub-Actions-friendly and fixes SSL chain issues by using a
bundled PEM chain file:

  certs/ids6_chain.pem   (download from browser: "PEM (chain)")

Repo layout expected:
  scripts/update_atis.py
  certs/ids6_chain.pem   <-- you add this
  atis.json              <-- generated/updated by workflow
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests


# --- Configuration -----------------------------------------------------------

BASE = "https://ids6.pitairport.com"
LANDING_URL = f"{BASE}/IDS5Status/"
ATIS_UPDATE_URL = f"{BASE}/IDS5Status/index.maincontent.status.atis:update"

# Output file (repo root)
OUT_PATH = Path(__file__).resolve().parent.parent / "atis.json"

# Certificate chain bundle (you must add this file to the repo)
CERT_BUNDLE_PATH = Path(__file__).resolve().parent.parent / "certs" / "ids6_chain.pem"

# Extract single letter from the returned HTML fragment in the zone payload
LETTER_RE = re.compile(
    r"data-grid-row=['\"]first['\"][\s\S]*?<td[^>]*>\s*([A-Z])\s*<br\s*/?>",
    re.IGNORECASE,
)


# --- Logic -------------------------------------------------------------------

def fetch_atis_letter(session: requests.Session) -> str:
    """
    Calls the Tapestry zone update endpoint and returns the ATIS letter (A-Z).
    """
    # Prime cookies/session (JSESSIONID) – mirrors browser behavior.
    session.get(LANDING_URL, timeout=30)

    # Zone update call (browser does POST with "{}")
    r = session.post(
        ATIS_UPDATE_URL,
        json={},
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        },
        timeout=30,
    )
    r.raise_for_status()

    data = r.json()

    # Tapestry format: {"_tapestry": {"content": [[zoneId, htmlString], ...], ...}}
    content = data.get("_tapestry", {}).get("content", [])
    html_fragment = ""

    for item in content:
        # item should be [zoneId, html]
        if isinstance(item, (list, tuple)) and len(item) >= 2 and item[0] == "atisZone":
            html_fragment = item[1] or ""
            break

    if not html_fragment:
        raise RuntimeError("atisZone not found in _tapestry.content response")

    m = LETTER_RE.search(html_fragment)
    if not m:
        raise RuntimeError("Could not extract ATIS letter from atisZone HTML fragment")

    return m.group(1).upper()


def write_output(letter: str) -> None:
    """
    Writes atis.json at repo root.
    """
    payload = {
        "letter": letter,
        "updated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    # Validate cert bundle exists (fail fast with a helpful message)
    if not CERT_BUNDLE_PATH.exists():
        raise FileNotFoundError(
            f"Missing certificate chain bundle: {CERT_BUNDLE_PATH}\n"
            "Download it from your browser certificate viewer: Download -> 'PEM (chain)'\n"
            "and save it to certs/ids6_chain.pem in the repo."
        )

    with requests.Session() as session:
        # Fix SSL chain validation on GitHub runners by using your bundled chain file.
        session.verify = str(CERT_BUNDLE_PATH)

        letter = fetch_atis_letter(session)

    write_output(letter)
    print(f"OK: ATIS={letter} -> {OUT_PATH}")


if __name__ == "__main__":
    main()
