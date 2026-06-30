#!/usr/bin/env python3
"""Auto-enqueue newly-aired episodes of the shows you're watching/watchlisted.

This is "box 2" of the decoupled pipeline:

    Aevum app (player)              <- you only watch / watchlist here
        |
        v  (shared DB: what you're watching + episode air dates)
    THIS JOB  (the calendar's rails) <- decides what to download
        |
        v  (writes PENDING rows into download_queue)
    DownloadEngine                   <- finds + downloads the torrent
        |
        v
    DownloadSentry                   <- remuxes + files into the library
        |
        v
    Aevum scanner                    <- sees the new file, updates the library

It reads the SAME "tracked shows" set the TV calendar publishes (shows you've
played/watched/bookmarked OR have on a watchlist), finds episodes that have
aired recently and that you don't already have / aren't already getting, and
inserts download requests that are byte-for-byte the same shape the Aevum app
would have written — so DownloadEngine processes them exactly as normal.

It deliberately does NOT touch the Aevum app, its download UI, or the
half-built `series_monitor` table. Your watchlist IS the monitor.

Scope is "new airings from now on": only episodes whose air_date falls within
the last AUTO_DL_LOOKBACK_DAYS days. It never reaches back into a show's old
back-catalogue.

Safety:
  * Skips episodes already on disk (media_files).
  * Skips episodes already queued / downloading (download_queue, any live row).
  * Skips episodes already fetched before (download_history) so it won't
    re-grab something you downloaded and deleted.
  * AUTO_DL_DRY_RUN=1 reports what it WOULD enqueue and writes nothing.

Config via environment variables (all optional):
    AEVUM_DB                 path to media_search.db
                             (default ~/.local/share/media-search-engine/media_search.db)
    AEVUM_USER_ID            profile whose shows to follow (default: admin profile)
    AUTO_DL_LOOKBACK_DAYS    how many days back counts as "new" (default: 7)
    AUTO_DL_MIN_AGE_DAYS     wait this many days after air before grabbing, so
                             better rips have time to appear (default: 1)
    AUTO_DL_SOURCE           download_queue.source tag (default: 'auto_calendar')
    AUTO_DL_PRIORITY         queue priority (default: 5; user=10, upgrades=1)
    AUTO_DL_QUALITY_PROFILE  quality_profile_id to request (default: NULL = server default)
    AUTO_DL_DRY_RUN          '1' = report only, write nothing (default: '0')
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
LOOKBACK_DAYS = int(os.environ.get("AUTO_DL_LOOKBACK_DAYS", "7"))
# Ripen delay: don't grab an episode until it's at least this many days past its
# air date. The first rips that appear on air day are often rushed/low quality;
# waiting a couple of days lets the better WEB-DL / proper encodes show up so the
# ranker has good candidates to pick from.
MIN_AGE_DAYS = int(os.environ.get("AUTO_DL_MIN_AGE_DAYS", "1"))
SOURCE = os.environ.get("AUTO_DL_SOURCE", "auto_calendar")
PRIORITY = int(os.environ.get("AUTO_DL_PRIORITY", "5"))
DRY_RUN = os.environ.get("AUTO_DL_DRY_RUN", "0") == "1"
_qp = os.environ.get("AUTO_DL_QUALITY_PROFILE")
QUALITY_PROFILE_ID = int(_qp) if (_qp and _qp.strip()) else None

# "Watching + watchlist" for one profile — IDENTICAL to the calendar's sweep so
# the two always agree: if it's on your calendar, this job will fetch it.
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

# Episodes that aired within the lookback window (already aired, not future).
RECENT_EPISODES_SQL = """
SELECT season, episode_number, air_date
FROM series_episodes
WHERE title_id = :tid
  AND season IS NOT NULL AND episode_number IS NOT NULL
  AND air_date IS NOT NULL AND air_date != ''
  AND air_date >= :start AND air_date <= :ripe
ORDER BY season, episode_number
"""

# Dedup probes — each returns a row if the episode is already accounted for.
ON_DISK_SQL = """
SELECT 1 FROM media_files
WHERE title_id = :tid AND season = :s AND episode_number = :e
LIMIT 1
"""
IN_QUEUE_SQL = """
SELECT 1 FROM download_queue
WHERE title_id = :tid AND season = :s AND episode_number = :e
LIMIT 1
"""
IN_HISTORY_SQL = """
SELECT 1 FROM download_history
WHERE title_id = :tid AND season = :s AND episode_number = :e
LIMIT 1
"""

# Exact shape the Aevum app uses (handlers_download.py), minus the human
# source/priority: status PENDING, media_type 'episode'.
INSERT_SQL = """
INSERT INTO download_queue
    (title_id, tmdb_id, title_name, year, media_type, season,
     episode_number, quality_profile_id, source, priority,
     status, requested_at)
VALUES
    (:tid, :tmdb_id, :title_name, NULL, 'episode', :s,
     :e, :qp, :source, :priority,
     'PENDING', CURRENT_TIMESTAMP)
"""


def resolve_user_id(conn: sqlite3.Connection) -> str:
    """Whose shows to follow. Explicit override wins; else the admin profile;
    else legacy 'default'. Mirrors the calendar's resolver."""
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


def derive_tmdb_id(title_id: str) -> int | None:
    """Same rule Aevum's v11 migration uses: trailing int of a 'tmdb-...' id
    (e.g. 'tmdb-tv-1399' -> 1399)."""
    try:
        return int(str(title_id).rsplit("-", 1)[-1])
    except (ValueError, AttributeError):
        return None


def _exists(conn: sqlite3.Connection, sql: str, params: dict) -> bool:
    return conn.execute(sql, params).fetchone() is not None


def main() -> int:
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Aevum DB not found at {DB_PATH}", file=sys.stderr)
        return 2

    today = datetime.now(timezone.utc).date()
    start = (today - timedelta(days=LOOKBACK_DAYS)).isoformat()
    ripe = (today - timedelta(days=MIN_AGE_DAYS)).isoformat()

    # Read-only when dry-running; read-write otherwise.
    mode = "ro" if DRY_RUN else "rw"
    conn = sqlite3.connect(f"file:{DB_PATH}?mode={mode}", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")

    enqueued, skipped = [], 0
    try:
        user_id = resolve_user_id(conn)
        shows = conn.execute(TRACKED_SHOWS_SQL, {"uid": user_id}).fetchall()
        print(f"Tracked shows for profile '{user_id}': {len(shows)} "
              f"(airdate window {start} .. {ripe} [waiting {MIN_AGE_DAYS}d after air], "
              f"dry_run={DRY_RUN})")

        for show in shows:
            tid = show["id"]
            name = (show["primary_title"] or "").strip()
            if not name:
                continue
            eps = conn.execute(
                RECENT_EPISODES_SQL, {"tid": tid, "start": start, "ripe": ripe}
            ).fetchall()
            for ep in eps:
                s, e = ep["season"], ep["episode_number"]
                key = {"tid": tid, "s": s, "e": e}
                if _exists(conn, ON_DISK_SQL, key) \
                        or _exists(conn, IN_QUEUE_SQL, key) \
                        or _exists(conn, IN_HISTORY_SQL, key):
                    skipped += 1
                    continue
                enqueued.append((tid, name, s, e, ep["air_date"]))

        if not DRY_RUN and enqueued:
            for tid, name, s, e, _air in enqueued:
                conn.execute(INSERT_SQL, {
                    "tid": tid,
                    "tmdb_id": derive_tmdb_id(tid),
                    "title_name": name,
                    "s": s,
                    "e": e,
                    "qp": QUALITY_PROFILE_ID,
                    "source": SOURCE,
                    "priority": PRIORITY,
                })
            conn.commit()
    finally:
        conn.close()

    verb = "WOULD enqueue" if DRY_RUN else "Enqueued"
    print(f"{verb} {len(enqueued)} new episode(s); skipped {skipped} "
          f"(already on disk / queued / fetched).")
    for tid, name, s, e, air in enqueued:
        print(f"  + {name} S{s}E{e}  (aired {air})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
