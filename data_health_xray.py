#!/usr/bin/env python3
"""Aevum data-health X-RAY — 100% READ-ONLY.

Opens the live DB in read-only mode and reports the shape of the data so the
remaining (risky) consistency fixes can be designed from evidence instead of
guesswork. Writes NOTHING, changes NOTHING.

Covers:
  A) High-water shadow-diff  — does uts.last_season/last_episode match what a
     recompute-from-watched-episodes would produce? (ARCH-3 safety check)
  B) Two-list agreement      — does the 'next episode' cache (upcoming_episodes)
     agree with the master episode table (series_episodes)? (ARCH-1 sizing)
  C) Returning-Soon coverage — sanity counts for the row we just rewired.
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB = os.environ.get(
    "AEVUM_DB",
    os.path.expanduser("~/.local/share/media-search-engine/media_search.db"),
)


def main() -> int:
    if not os.path.exists(DB):
        print(f"ERROR: DB not found at {DB}")
        return 2
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row

    def has_table(name):
        return bool(c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,)).fetchone())

    def cols(name):
        try:
            return {r[1] for r in c.execute(f"PRAGMA table_info({name})")}
        except Exception:
            return set()

    # admin profile (the calendar + Up Next follow this user)
    uid = os.environ.get("AEVUM_USER_ID")
    if not uid:
        try:
            r = c.execute("SELECT id FROM profiles WHERE is_admin=1 "
                          "ORDER BY created_at LIMIT 1").fetchone()
            uid = r[0] if r and r[0] else "default"
        except Exception:
            uid = "default"

    print("=" * 64)
    print("AEVUM DATA-HEALTH X-RAY  (read-only)")
    print(f"DB: {DB}")
    print(f"Admin profile: {uid}")
    print(f"As of: {datetime.now(timezone.utc).date()}")
    print("=" * 64)

    # ---------------------------------------------------------------- A ----
    print("\n[A] HIGH-WATER MARK: stored vs recomputed-from-watched-episodes")
    print("    (ARCH-3 — is it safe to derive the marker from one source?)")
    sew_ok = has_table("series_episode_watched")
    if not sew_ok:
        print("    series_episode_watched table absent — skipping.")
    else:
        rows = c.execute(
            """SELECT title_id, last_season, last_episode
               FROM user_title_state
               WHERE user_id = ?
                 AND (last_season IS NOT NULL OR last_episode IS NOT NULL)""",
            (uid,)).fetchall()
        match = differ = no_sew = 0
        examples = []
        for r in rows:
            tid = r["title_id"]
            ms = c.execute(
                "SELECT MAX(season) FROM series_episode_watched "
                "WHERE user_id=? AND title_id=?", (uid, tid)).fetchone()[0]
            if ms is None:
                no_sew += 1
                continue
            me = c.execute(
                "SELECT MAX(episode) FROM series_episode_watched "
                "WHERE user_id=? AND title_id=? AND season=?",
                (uid, tid, ms)).fetchone()[0]
            cur = (r["last_season"] or 0, r["last_episode"] or 0)
            rec = (ms or 0, me or 0)
            if cur == rec:
                match += 1
            else:
                differ += 1
                if len(examples) < 12:
                    nm = c.execute("SELECT primary_title FROM titles WHERE id=?",
                                   (tid,)).fetchone()
                    examples.append((nm[0] if nm else tid, cur, rec))
        print(f"    shows with a stored marker: {len(rows)}")
        print(f"      MATCH  (stored == recompute): {match}")
        print(f"      DIFFER (would change if derived): {differ}")
        print(f"      NO local watched-rows (Trakt-only; must NOT be "
              f"overwritten): {no_sew}")
        if examples:
            print("    examples of DIFFER (stored -> recompute):")
            for nm, cur, rec in examples:
                print(f"      - {nm}: S{cur[0]}E{cur[1]} -> S{rec[0]}E{rec[1]}")

    # ---------------------------------------------------------------- B ----
    print("\n[B] TWO-LIST AGREEMENT: upcoming_episodes vs series_episodes")
    print("    (ARCH-1 — how far apart are the 'next-ep cache' and the master?)")
    if not (has_table("upcoming_episodes") and has_table("series_episodes")):
        print("    a required table is absent — skipping.")
    else:
        ucols = cols("upcoming_episodes")
        s_col = "season_number" if "season_number" in ucols else "season"
        e_col = "episode_number" if "episode_number" in ucols else "episode"
        ue = c.execute(
            f"SELECT title_id, {s_col} AS s, {e_col} AS e, air_date "
            f"FROM upcoming_episodes").fetchall()
        agree = missing = zero_se = 0
        zero_examples = []
        for r in ue:
            n = c.execute("SELECT COUNT(*) FROM series_episodes "
                          "WHERE title_id=?", (r["title_id"],)).fetchone()[0]
            if n == 0:
                zero_se += 1
                if len(zero_examples) < 12:
                    nm = c.execute("SELECT primary_title FROM titles WHERE id=?",
                                   (r["title_id"],)).fetchone()
                    zero_examples.append(nm[0] if nm else r["title_id"])
                continue
            hit = c.execute(
                "SELECT 1 FROM series_episodes WHERE title_id=? AND season=? "
                "AND episode_number=?",
                (r["title_id"], r["s"], r["e"])).fetchone()
            if hit:
                agree += 1
            else:
                missing += 1
        print(f"    rows in upcoming_episodes: {len(ue)}")
        print(f"      next-ep ALSO in series_episodes: {agree}")
        print(f"      next-ep MISSING from series_episodes: {missing}")
        print(f"      show has ZERO series_episodes rows (the SNW class): "
              f"{zero_se}")
        if zero_examples:
            print("      examples (in 'next-ep cache' but master is empty):")
            for nm in zero_examples:
                print(f"        - {nm}")

    # ---------------------------------------------------------------- C ----
    print("\n[C] RETURNING-SOON coverage (the row just rewired to the master)")
    today = datetime.now(timezone.utc).date().isoformat()
    cutoff = (datetime.now(timezone.utc).date() + timedelta(days=90)).isoformat()
    try:
        n = c.execute(
            """WITH followed AS (
                 SELECT DISTINCT t.id AS title_id FROM titles t
                 LEFT JOIN user_title_state uts ON uts.title_id=t.id AND uts.user_id=:u
                 LEFT JOIN playback_positions pp ON pp.title_id=t.id AND pp.user_id=:u
                 LEFT JOIN user_list_items uli ON uli.title_id=t.id
                 LEFT JOIN user_lists ul ON ul.id=uli.list_id AND ul.user_id=:u
                 WHERE t.type='show' AND (COALESCE(uts.plays,0)>0
                   OR COALESCE(uts.watched,0)=1 OR uts.watched_at IS NOT NULL
                   OR pp.title_id IS NOT NULL OR ul.id IS NOT NULL))
               SELECT COUNT(DISTINCT se.title_id) FROM series_episodes se
               JOIN followed f ON f.title_id=se.title_id
               WHERE se.season>0 AND se.air_date>=:t AND se.air_date<=:c
                 AND se.air_date IS NOT NULL AND se.air_date!=''""",
            {"u": uid, "t": today, "c": cutoff}).fetchone()[0]
        print(f"    followed shows with an upcoming episode in next 90d: {n}")
    except Exception as ex:
        print(f"    (could not compute: {ex})")

    print("\n" + "=" * 64)
    print("END X-RAY — nothing was modified. Paste this whole window to Claude.")
    print("=" * 64)
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
