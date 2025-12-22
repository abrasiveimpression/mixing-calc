#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://ids6.pitairport.com"
LANDING_URL = f"{BASE}/IDS5Status/"
ATIS_UPDATE_URL = f"{BASE}/IDS5Status/index.maincontent.status.atis:update"

OUT_PATH = Path(__file__).resolve().parent.parent / "atis.json"
CERT_BUNDLE_PATH = Path(__file__).resolve().parent.parent / "certs" / "ids6_chain.pem"

def find_atis_zone_html(tapestry_json: dict) -> str:
    content = tapestry_json.get("_tapestry", {}).get("content", [])
    for item in content:
        if isinstance(item, (list, tuple)) and len(item) >= 2 and item[0] == "atisZone":
            return item[1] or ""
    return ""

def extract_letter(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Primary (what your browser showed)
    row = soup.select_one("tr[data-grid-row='first']")
    if row:
        td = row.find("td")
        if td:
            val = td.get_text(strip=True)
            if val and len(val) >= 1:
                return val[0].upper()

    # Fallback 1: if it’s still a table but without data-grid-row
    td = soup.select_one("table.t-data-grid tbody tr td")
    if td:
        val = td.get_text(strip=True)
        if val and len(val) >= 1:
            return val[0].upper()

    # Fallback 2: any single-letter token before <br>
    # (works even if the markup is simplified)
    text = soup.get_text("\n", strip=True)
    # Look for a single-letter line (A-Z)
    for line in text.splitlines():
        line = line.strip()
        if len(line) == 1 and line.isalpha():
            return line.upper()

    raise RuntimeError("ATIS letter not found in HTML (all extraction methods failed)")

def fetch_atis_letter(session: requests.Session) -> str:
    # Prime cookies/session
    session.get(LANDING_URL, timeout=30)

    r = session.post(
        ATIS_UPDATE_URL,
        json={},
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Origin": BASE,
            "Referer": LANDING_URL,
            "User-Agent": "Mozilla/5.0",
        },
        timeout=30,
    )
    r.raise_for_status()

    data = r.json()
    html = find_atis_zone_html(data)
    if not html:
        # If atisZone missing, print keys for debugging
        print("DEBUG: _tapestry keys:", list(data.get("_tapestry", {}).keys()))
        print("DEBUG: content entries:", [c[0] for c in data.get("_tapestry", {}).get("content", []) if isinstance(c, (list, tuple)) and c])
        raise RuntimeError("atisZone not found in response")

    try:
        return extract_letter(html)
    except Exception as e:
        # Print the fragment so we can see what GitHub runner is receiving
        print("DEBUG: atisZone HTML fragment (first 2000 chars):")
        print(html[:2000])
        print("DEBUG: atisZone HTML fragment (last 500 chars):")
        print(html[-500:])
        raise

def main():
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
