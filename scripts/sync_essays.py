#!/usr/bin/env python3
"""
Sync essays from the Substack RSS feed into index.html.

Fetches the RSS feed from writing.dangrimm.ai, parses essay metadata,
and regenerates the "Recent writing" section of index.html. Only the
most recent MAX_ESSAYS are shown on the homepage; the rest are linked
via "Read all essays".

The script uses HTML marker comments to identify the region to replace,
so the rest of the page can be freely edited without breaking sync.
"""

import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from html import escape
from pathlib import Path

FEED_URL = "https://writing.dangrimm.ai/feed"
INDEX_PATH = Path(__file__).resolve().parent.parent / "index.html"
MAX_ESSAYS = 5  # Number of essays to show on the homepage

# Markers in index.html that delimit the auto-generated essay block
START_MARKER = "<!-- ESSAYS:START -->"
END_MARKER = "<!-- ESSAYS:END -->"


def fetch_feed() -> str:
    """Fetch the Substack RSS feed."""
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "dangrimm-ai-sync/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def parse_essays(feed_xml: str) -> list[dict]:
    """Parse RSS items into essay dicts."""
    root = ET.fromstring(feed_xml)
    essays = []

    for item in root.findall(".//item"):
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        pub_date_str = item.findtext("pubDate", "").strip()
        description = item.findtext("description", "").strip()

        if not title or not link:
            continue

        # Parse the RFC 822 date from RSS
        # Example: "Fri, 07 Feb 2026 12:00:00 GMT"
        try:
            pub_date = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %Z")
        except ValueError:
            try:
                pub_date = datetime.strptime(pub_date_str[:25], "%a, %d %b %Y %H:%M:%S")
            except ValueError:
                pub_date = datetime.now()

        # Clean up description: strip HTML tags, truncate
        description = re.sub(r"<[^>]+>", "", description)
        description = re.sub(r"\s+", " ", description).strip()
        if len(description) > 180:
            description = description[:177].rsplit(" ", 1)[0] + "..."

        essays.append({
            "title": title,
            "link": link,
            "date": pub_date,
            "description": description,
        })

    # Sort newest first
    essays.sort(key=lambda e: e["date"], reverse=True)
    return essays


def render_essays(essays: list[dict]) -> str:
    """Render essay entries as HTML."""
    lines = []
    # Only show most recent essays on homepage
    shown = essays[:MAX_ESSAYS]

    for i, essay in enumerate(shown):
        # Number essays from total count down (newest = highest number)
        num = len(essays) - essays.index(essay)
        date_str = essay["date"].strftime("%b %-d, %Y")
        title_escaped = escape(essay["title"])
        desc_escaped = escape(essay["description"]).replace("&amp;mdash;", "&mdash;")

        lines.append(f'    <div class="essay">')
        lines.append(f'      <a href="{escape(essay["link"])}">')
        lines.append(f"        <h3>{title_escaped}</h3>")
        lines.append(f'        <span class="meta">#{num} &middot; {date_str}</span>')
        lines.append(f"        <p>{desc_escaped}</p>")
        lines.append(f"      </a>")
        lines.append(f"    </div>")
        if i < len(shown) - 1:
            lines.append("")

    return "\n".join(lines)


def update_index(essay_html: str) -> bool:
    """Replace the essay block in index.html. Returns True if changed."""
    content = INDEX_PATH.read_text(encoding="utf-8")

    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )

    if not pattern.search(content):
        print(f"ERROR: Could not find markers in {INDEX_PATH}")
        print(f"  Expected: {START_MARKER} ... {END_MARKER}")
        print("  Add these markers around the essay entries in index.html.")
        return False

    new_block = f"{START_MARKER}\n{essay_html}\n    {END_MARKER}"
    new_content = pattern.sub(new_block, content)

    if new_content == content:
        print("No changes detected.")
        return False

    INDEX_PATH.write_text(new_content, encoding="utf-8")
    print(f"Updated {INDEX_PATH} with latest essays.")
    return True


def main():
    print(f"Fetching RSS feed from {FEED_URL}...")
    feed_xml = fetch_feed()

    print("Parsing essays...")
    essays = parse_essays(feed_xml)
    print(f"  Found {len(essays)} essays.")

    if not essays:
        print("No essays found in feed. Skipping update.")
        return

    for e in essays[:5]:
        print(f"  #{len(essays) - essays.index(e)}: {e['title']} ({e['date'].strftime('%b %d, %Y')})")

    essay_html = render_essays(essays)
    update_index(essay_html)


if __name__ == "__main__":
    main()
