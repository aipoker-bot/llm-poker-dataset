#!/usr/bin/env python3
"""Rebuild the results table in index.html from aipoker.bot's public API.

Only rows (model, seat) with at least MIN_DECISIONS decisions in games people
played get a line; everything else goes into the totals under the table.
Exit 0 either way; the workflow commits only when the file changed.

  python scripts/update_results.py index.html
"""

import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

API = "https://aipoker.bot/api/blunders"
MIN_DECISIONS = 1000
START, END = "<!-- results:start -->", "<!-- results:end -->"


def pct(v):
    return "–" if v is None else f"{v:.1f}%"


def build(rows: list[dict]) -> str:
    human = [r for r in rows if r["bucket"] == "human"]
    top = sorted((r for r in human if r["decisions"] >= MIN_DECISIONS),
                 key=lambda r: -r["decisions"])
    lines = ["<table>",
             "<thead><tr><th>Model</th><th>Decisions</th><th>Hands</th><th>Illegal</th>"
             "<th>Misfire</th><th>Claimed a hand it didn't have</th><th>Folded the best hand</th>"
             "<th>Called dead</th><th>Won at showdown</th></tr></thead>", "<tbody>"]
    for r in top:
        name = html.escape(r.get("name") or r["model_id"])
        lines.append(
            f"<tr><td>{name}<br><code>{html.escape(r['model_id'])}</code></td>"
            f"<td>{r['decisions']:,}</td><td>{r['hands']:,}</td>"
            f"<td>{pct(r['illegal_pct'])}</td><td>{pct(r['misfire_pct'])}</td>"
            f"<td>{pct(r['hallucinated_pct'])}</td><td>{pct(r['folded_best_pct'])}</td>"
            f"<td>{pct(r['called_dead_pct'])}</td><td>{pct(r['showdown_won_pct'])}</td></tr>")
    if not top:
        lines.append('<tr><td colspan="9">No model has reached the bar yet.</td></tr>')
    lines += ["</tbody>", "</table>"]
    total = sum(r["decisions"] for r in human)
    models = len({r["model_id"] for r in human})
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines.append(f'<p class="note">All models: {total:,} decisions in games people played, '
                 f"{models} models, {len(top)} over the bar. Updated {day}.</p>")
    return "\n".join(lines)


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "index.html"
    req = urllib.request.Request(API, headers={"User-Agent": "llm-poker-dataset results updater"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        rows = json.load(resp)["models"]
    page = open(path, encoding="utf-8").read()
    block = f"{START}\n{build(rows)}\n{END}"
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, page, flags=re.S)
    if new.count(START) != 1:
        sys.exit(f"{path}: results markers not found")
    # the date line changes every run; only a change in the numbers is worth a commit
    strip = lambda s: re.sub(r"Updated \d{4}-\d{2}-\d{2}", "", s)
    if strip(new) != strip(page):
        open(path, "w", encoding="utf-8").write(new)
        print("results updated")
    else:
        print("no change")
    return 0


if __name__ == "__main__":
    sys.exit(main())
