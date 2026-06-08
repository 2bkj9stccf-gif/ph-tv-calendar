#!/usr/bin/env python3
"""Dump how one show is stored across Aevum's tables (default: Strange New Worlds)."""
import os, sqlite3
DB = os.environ.get("AEVUM_DB", os.path.expanduser("~/.local/share/media-search-engine/media_search.db"))
NAME = os.environ.get("SHOW", "Strange New Worlds")
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); c.row_factory=sqlite3.Row
print(f"Searching titles for '%{NAME}%' …\n")
rows = c.execute("SELECT id, type, primary_title FROM titles WHERE primary_title LIKE ?", (f"%{NAME}%",)).fetchall()
if not rows:
    print("NOT FOUND in titles table at all."); raise SystemExit
for r in rows:
    tid = r["id"]
    print(f"titles: id={tid!r}  type={r['type']!r}  title={r['primary_title']!r}")
    uts = c.execute("SELECT user_id,watched,watched_at,plays,in_library FROM user_title_state WHERE title_id=?", (tid,)).fetchall()
    print(f"  user_title_state rows: {[dict(x) for x in uts] or 'NONE'}")
    pp = c.execute("SELECT user_id,COUNT(*) n FROM playback_positions WHERE title_id=? GROUP BY user_id", (tid,)).fetchall()
    print(f"  playback_positions: {[dict(x) for x in pp] or 'NONE'}")
    li = c.execute("SELECT ul.user_id,ul.name FROM user_list_items uli JOIN user_lists ul ON ul.id=uli.list_id WHERE uli.title_id=?", (tid,)).fetchall()
    print(f"  on watchlists: {[dict(x) for x in li] or 'NONE'}")
    se = c.execute("SELECT COUNT(*) n, MAX(air_date) m FROM series_episodes WHERE title_id=?", (tid,)).fetchone()
    print(f"  series_episodes: {se['n']} rows, latest air_date={se['m']}")
    ue = c.execute("SELECT COUNT(*) n, MAX(air_date) m FROM upcoming_episodes WHERE title_id=?", (tid,)).fetchone()
    print(f"  upcoming_episodes: {ue['n']} rows, latest air_date={ue['m']}")
    print()
