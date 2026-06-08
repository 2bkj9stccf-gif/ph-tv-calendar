#!/usr/bin/env python3
"""One-shot: copy each show's upcoming "next episode" from the next-episode
cache (upcoming_episodes) into the master episode catalog (series_episodes).

Why: the next episode is fetched from TMDB into `upcoming_episodes` but was
never written to `series_episodes`, so the TV calendar (which reads the master
catalog) missed the next drop for ~250 shows. This copies the data already in
your DB — no internet needed.

SAFETY:
  • ADD-ONLY. Uses INSERT OR IGNORE, so a show/episode already in the catalog
    is left completely untouched. Nothing is overwritten or deleted.
  • Skips sentinel/ended rows (season 0, blank or 9999-12-31 dates).
  • Backs the DB up first (local disk) before writing.
  • Future-dated rows can't affect "Up Next" (which only shows aired episodes).
Re-runnable any time; a second run adds 0 rows.
"""
import os
import sqlite3
import sys
import time
from datetime import datetime

DB = os.environ.get(
    "AEVUM_DB",
    os.path.expanduser("~/.local/share/media-search-engine/media_search.db"),
)

SELECT_NEW = """
SELECT COUNT(*) FROM upcoming_episodes ue
WHERE ue.season_number > 0 AND ue.episode_number > 0
  AND ue.air_date IS NOT NULL AND ue.air_date != '' AND ue.air_date != '9999-12-31'
  AND NOT EXISTS (
      SELECT 1 FROM series_episodes se
      WHERE se.title_id = ue.title_id
        AND se.season = ue.season_number
        AND se.episode_number = ue.episode_number
  )
"""

INSERT = """
INSERT OR IGNORE INTO series_episodes
    (title_id, season, episode_number, episode_title, overview, air_date, checked_at)
SELECT ue.title_id, ue.season_number, ue.episode_number,
       COALESCE(ue.episode_title, ''), COALESCE(ue.episode_overview, ''),
       ue.air_date, ?
FROM upcoming_episodes ue
WHERE ue.season_number > 0 AND ue.episode_number > 0
  AND ue.air_date IS NOT NULL AND ue.air_date != '' AND ue.air_date != '9999-12-31'
"""


def main() -> int:
    if not os.path.exists(DB):
        print(f"ERROR: DB not found at {DB}")
        return 2

    # ---- back up first (local disk, next to the live DB) ----
    backup_dir = os.path.join(os.path.dirname(DB), "db-backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(backup_dir, f"media_search.before-nextep-backfill.{stamp}.db")
    try:
        src = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        dst = sqlite3.connect(backup_path)
        with dst:
            src.backup(dst)
        src.close(); dst.close()
        print(f"Backup written: {backup_path}")
    except Exception as e:
        print(f"ERROR: backup failed ({e}). Aborting — no changes made.")
        return 1

    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA busy_timeout=30000")
    try:
        before_se = con.execute("SELECT COUNT(*) FROM series_episodes").fetchone()[0]
        to_add = con.execute(SELECT_NEW).fetchone()[0]
        print(f"series_episodes rows before: {before_se}")
        print(f"upcoming next-episodes missing from the catalog: {to_add}")
        if to_add == 0:
            print("Nothing to add — catalog already has every upcoming next episode.")
            return 0
        with con:
            cur = con.execute(INSERT, (time.time(),))
            added = cur.rowcount
        after_se = con.execute("SELECT COUNT(*) FROM series_episodes").fetchone()[0]
        print(f"Added {added} upcoming episodes to the catalog.")
        print(f"series_episodes rows after: {after_se}")
        print("Done. Re-run the X-Ray to confirm section B dropped, then rebuild "
              "the TV calendar to see the new drops.")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
