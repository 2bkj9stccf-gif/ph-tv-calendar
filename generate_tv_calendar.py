#!/usr/bin/env python3
"""Build the "My Shows" TV-episode calendar (.ics) from the Aevum database.

Runs on the Mac that hosts Aevum (the live DB is local). It reads the same
"tracked show" set Aevum's own episode-refresh job uses — shows you're watching
(played / watched / have a resume bookmark) OR on a watchlist — and emits one
all-day event per episode on its air date, for episodes airing within
-90 .. +180 days of today.

No third-party dependencies (writes the .ics by hand) so it can run under the
Aevum Python without installing anything.

Config via environment variables (all optional):
    AEVUM_DB        path to media_search.db
                    (default: ~/.local/share/media-search-engine/media_search.db)
    AEVUM_USER_ID   profile whose shows to track (default: 'default')
    TV_CAL_OUT      output .ics path (default: ./public/calendar.ics)
    DAYS_BACK       days to look back  (default: 90)
    DAYS_FWD        days to look ahead (default: 180)
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone

DB_PATH = os.environ.get(
    "AEVUM_DB",
    os.path.expanduser("~/.local/share/media-search-engine/media_search.db"),
)
OUT_FILE = os.environ.get("TV_CAL_OUT", os.path.join(os.path.dirname(__file__), "public", "calendar.ics"))
DAYS_BACK = int(os.environ.get("DAYS_BACK", "90"))
DAYS_FWD = int(os.environ.get("DAYS_FWD", "180"))

ICON = "\U0001F37F"  # 🍿 popcorn (TV calendar)
PRODID = "-//ph-tv-calendar//aevum//EN"
CALNAME = "My Shows"
CALDESC = "Upcoming and recent episodes of the shows you're watching."
MIN_EVENTS = 1

# "Watching + watchlist" for one profile — mirrors Aevum's tracked-show sweep
# (engagement OR watchlist membership), scoped to the chosen user_id.
TRACKED_SHOWS_SQL = """
SELECT DISTINCT t.id, t.primary_title
FROM titles t
LEFT JOIN user_title_state uts
       ON uts.title_id = t.id AND uts.user_id = :uid
LEFT JOIN playback_positions pp
       ON pp.title_id = t.id AND pp.user_id = :uid
LEFT JOIN user_list_items uli
       ON uli.title_id = t.id
LEFT JOIN user_lists ul
       ON ul.id = uli.list_id AND ul.user_id = :uid
WHERE t.type = 'show'
  AND (
        COALESCE(uts.plays, 0) > 0
     OR COALESCE(uts.watched, 0) = 1
     OR uts.watched_at IS NOT NULL
     OR pp.title_id IS NOT NULL
     OR ul.id IS NOT NULL
  )
"""

EPISODES_SQL = """
SELECT season, episode_number, episode_title, air_date, overview
FROM series_episodes
WHERE title_id = :tid
  AND air_date IS NOT NULL AND air_date != ''
  AND air_date >= :start AND air_date <= :end
ORDER BY air_date, season, episode_number
"""


# ------------------------------------------------------------------ .ics ----
def _esc(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Fold a content line to <=75 octets per RFC 5545, never splitting a
    multi-byte UTF-8 character."""
    out, cur, cur_len = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        if cur_len + n > 75:
            out.append(cur)
            cur, cur_len = " " + ch, 1 + n  # continuation starts with a space
        else:
            cur += ch
            cur_len += n
    out.append(cur)
    return "\r\n".join(out)


def _trim(text: str, limit: int = 280) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in (". ", "! ", "? "):
        idx = cut.rfind(sep)
        if idx > limit * 0.5:
            return cut[: idx + 1].strip()
    return cut.rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def build_ics(events: list[dict], stamp: datetime) -> bytes:
    stamp_s = stamp.strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{CALNAME}",
        f"X-WR-CALDESC:{CALDESC}",
        "X-WR-TIMEZONE:Asia/Manila",
        "X-PUBLISHED-TTL:PT12H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
    ]
    for ev in events:
        d = ev["date"]
        dtstart = d.strftime("%Y%m%d")
        dtend = (d + timedelta(days=1)).strftime("%Y%m%d")
        lines += [
            "BEGIN:VEVENT",
            _fold(f"UID:{ev['uid']}"),
            f"DTSTAMP:{stamp_s}",
            _fold(f"SUMMARY:{_esc(ev['summary'])}"),
            f"DTSTART;VALUE=DATE:{dtstart}",
            f"DTEND;VALUE=DATE:{dtend}",
            f"LAST-MODIFIED:{stamp_s}",
            "TRANSP:TRANSPARENT",
        ]
        if ev.get("description"):
            lines.append(_fold(f"DESCRIPTION:{_esc(ev['description'])}"))
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


# ------------------------------------------------------------------ data ----
def resolve_user_id(conn: sqlite3.Connection) -> str:
    """Whose shows to track. Explicit override wins; otherwise follow the
    real admin profile (Dale); fall back to the legacy 'default' only if
    there's no profiles table yet."""
    env = os.environ.get("AEVUM_USER_ID")
    if env:
        return env
    try:
        row = conn.execute(
            "SELECT id FROM profiles WHERE is_admin=1 ORDER BY created_at LIMIT 1"
        ).fetchone()
        if row and row[0]:
            return row[0]
    except Exception:
        pass
    return "default"


def gather_events(conn: sqlite3.Connection, today: date) -> list[dict]:
    conn.row_factory = sqlite3.Row
    start = (today - timedelta(days=DAYS_BACK)).isoformat()
    end = (today + timedelta(days=DAYS_FWD)).isoformat()

    user_id = resolve_user_id(conn)
    shows = conn.execute(TRACKED_SHOWS_SQL, {"uid": user_id}).fetchall()
    print(f"Tracked shows for profile '{user_id}': {len(shows)}")

    events: list[dict] = []
    for show in shows:
        tid, name = show["id"], (show["primary_title"] or "").strip()
        if not name:
            continue
        eps = conn.execute(
            EPISODES_SQL, {"tid": tid, "start": start, "end": end}
        ).fetchall()
        for ep in eps:
            try:
                d = date.fromisoformat((ep["air_date"] or "")[:10])
            except ValueError:
                continue
            s, n = ep["season"], ep["episode_number"]
            tag = f"S{s}E{n}"
            etitle = (ep["episode_title"] or "").strip()
            summary = f"{ICON} {name} — {tag}" + (f": {etitle}" if etitle else "")
            events.append({
                "uid": f"aevum-{str(tid).replace(' ', '')}-s{s}e{n}@ph-tv-calendar",
                "summary": summary,
                "date": d,
                "description": _trim(ep["overview"] or ""),
            })

    # de-dup + sort
    seen, kept = set(), []
    for ev in sorted(events, key=lambda x: (x["date"], x["summary"])):
        if ev["uid"] in seen:
            continue
        seen.add(ev["uid"])
        kept.append(ev)
    return kept


def main() -> int:
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Aevum DB not found at {DB_PATH}", file=sys.stderr)
        return 2
    today = datetime.now(timezone.utc).date()
    stamp = datetime.now(timezone.utc)  # build time → reliably signals updates

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        events = gather_events(conn, today)
    finally:
        conn.close()

    if len(events) < MIN_EVENTS:
        print(f"ERROR: only {len(events)} episodes in window — refusing to "
              f"publish (won't overwrite a good calendar).", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "wb") as f:
        f.write(build_ics(events, stamp))
    print(f"Wrote {OUT_FILE}: {len(events)} episodes "
          f"({DAYS_BACK}d back, {DAYS_FWD}d ahead, as of {today}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
