#!/usr/bin/env python3
"""
Fetch KPIT ATIS letter from PIT IDS Tapestry zone update
and write it to atis.json (repo root).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


# ---------------- Configuration ----------------

BASE = "https://ids6.pitairport.com"
LANDING_URL = f"{BASE}/IDS5Status/"
ATIS_UPDATE_URL = f"{BASE}/IDS5Status/index.maincontent.status.atis:update"

OUT_PATH = Path(__file__).resolve().parent.parent / "atis.json"
CERT_BUNDLE_PATH = Path(__file__).resolve().parent.parent / "certs" / "ids6_chain.pem"


# ---------------- Logic ----------------

def extract_letter_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    row = soup.select_one("tr[data-grid-row='first']")
    if not row:
        raise RuntimeError("ATIS row not found in HTML")

    td = row.find("td")
    if not td:
        raise RuntimeError("ATIS cell not found in HTML")

    letter = td.get_text(strip=True)
    if not letter or len(letter) != 1:
        raise RuntimeError(f"Invalid ATIS letter extracted: {letter!r}")

    return letter.upper()


def fetch_atis_letter(session: requests.Session) -> str:
    # Prime cookies/session
    session.get(LANDING_URL, timeout=30)

    r = session.post(
        ATIS_UPDATE_URL,
        json={},
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json; charset=UTF-8",
            "Origin": BASE,
            "Referer": LANDING_URL,
            "User-Agent": "Mozilla/5.0",
        },
        timeout=30,
    )
    r.raise_for_status()

    data = r.json()
    content = data.get("_tapestry", {}).get("content", [])

    for zone_id, html in content:
        if zone_id == "atisZone":
            return extract_letter_from_html(html)

    raise RuntimeError("atisZone not found in Tapestry response")


def main() -> None:
    if not CERT_BUNDLE_PATH.exists():
        raise FileNotFoundError(f"Missing cert bundle: {CERT_BUNDLE_PATH}")

    with requests.Session() as session:
        session.verify = str(CERT_BUNDLE_PATH)
        letter = fetch_atis_letter(session)

    payload = {
        "letter": letter,
        "updated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"SUCCESS: ATIS={letter}")


if __name__ == "__main__":
    main()
