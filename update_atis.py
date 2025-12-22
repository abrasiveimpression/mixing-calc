import json
import re
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = "https://ids6.pitairport.com"
LANDING = BASE + "/IDS5Status/"
ATIS_UPDATE = BASE + "/IDS5Status/index.maincontent.status.atis:update"

OUT = Path("atis.json")

LETTER_RE = re.compile(
    r"data-grid-row=['\"]first['\"][\s\S]*?<td[^>]*>\s*([A-Z])\s*<br\s*/?>",
    re.IGNORECASE
)

def fetch_letter():
    with requests.Session() as s:
        s.get(LANDING, timeout=30)
        r = s.post(
            ATIS_UPDATE,
            json={},
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=30
        )
        r.raise_for_status()
        data = r.json()

        content = data.get("_tapestry", {}).get("content", [])
        for zone_id, html in content:
            if zone_id == "atisZone":
                m = LETTER_RE.search(html)
                if not m:
                    raise RuntimeError("ATIS letter not found")
                return m.group(1).upper()

        raise RuntimeError("atisZone not present")

def main():
    letter = fetch_letter()
    updated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    OUT.write_text(
        json.dumps({"letter": letter, "updated_utc": updated}, indent=2) + "\n",
        encoding="utf-8"
    )
    print(f"ATIS={letter}")

if __name__ == "__main__":
    main()
