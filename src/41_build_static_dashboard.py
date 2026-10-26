"""Step 41: Build a static dashboard page for GitHub Pages.

Takes the dashboard layout (dashboard/dashboard_body.html), puts it in a
plain page shell (dashboard/shell.html), and inlines the CSV files from
step 40, so the page works with no server and no API.

Output: docs/index.html
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "reports" / "dashboard_data"
OUT = ROOT / "docs" / "index.html"


def main():
    body = (ROOT / "dashboard" / "dashboard_body.html").read_text(encoding="utf-8")
    shell = (ROOT / "dashboard" / "shell.html").read_text(encoding="utf-8")

    # The layout script must run after the data stand-in, so split it off.
    cut = body.index("<script>")
    markup, script = body[:cut], body[cut:]

    data = {}
    for p in sorted(DATA.glob("*.csv")):
        with p.open(encoding="utf-8", newline="") as f:
            data[p.stem] = list(csv.DictReader(f))  # values stay as text, like a CSV loader

    page = (shell.replace("<!--BODY-->", markup)
                 .replace("/*DATA*/", json.dumps(data, ensure_ascii=False))
                 .replace("<!--SCRIPT-->", script))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} with {len(data)} datasets")


if __name__ == "__main__":
    main()
