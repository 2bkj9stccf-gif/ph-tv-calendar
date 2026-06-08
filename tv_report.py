#!/usr/bin/env python3
"""Diagnostic: what the TV calendar catches (follows the admin profile)."""
import os, sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
DB = os.environ.get("AEVUM_DB", os.path.expanduser("~/.local/share/media-search-engine/media_search.db"))
BACK, FWD = int(os.environ.get("DAYS_BACK","90")), int(os.environ.get("DAYS_FWD","180"))
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); c.row_factory=sqlite3.Row
def resolve_uid():
    env=os.environ.get("AEVUM_USER_ID")
    if env: return env
    try:
        r=c.execute("SELECT id FROM profiles WHERE is_admin=1 ORDER BY created_at LIMIT 1").fetchone()
        if r and r[0]: return r[0]
    except Exception: pass
    return "default"
UID=resolve_uid()
TRACKED = """
SELECT DISTINCT t.id, t.primary_title FROM titles t
LEFT JOIN user_title_state uts ON uts.title_id=t.id AND uts.user_id=:u
LEFT JOIN playback_positions pp ON pp.title_id=t.id AND pp.user_id=:u
LEFT JOIN user_list_items uli ON uli.title_id=t.id
LEFT JOIN user_lists ul ON ul.id=uli.list_id AND ul.user_id=:u
WHERE t.type='show' AND (COALESCE(uts.plays,0)>0 OR COALESCE(uts.watched,0)=1
   OR uts.watched_at IS NOT NULL OR pp.title_id IS NOT NULL OR ul.id IS NOT NULL)"""
today = datetime.now(timezone.utc).date()
start, end = (today-timedelta(days=BACK)).isoformat(), (today+timedelta(days=FWD)).isoformat()
shows = c.execute(TRACKED, {"u":UID}).fetchall()
months=Counter(); in_win=0; zero=[]; total=0
for s in shows:
    eps=c.execute("SELECT air_date FROM series_episodes WHERE title_id=:t AND air_date>=:s AND air_date<=:e",{"t":s["id"],"s":start,"e":end}).fetchall()
    allc=c.execute("SELECT COUNT(*) FROM series_episodes WHERE title_id=:t",{"t":s["id"]}).fetchone()[0]; total+=allc
    if not eps:
        latest=c.execute("SELECT MAX(air_date) FROM series_episodes WHERE title_id=:t",{"t":s["id"]}).fetchone()[0]
        zero.append((s["primary_title"],allc,latest or "—"))
    for e in eps: in_win+=1; months[e["air_date"][:7]]+=1
print(f"Profile: {UID}")
print(f"Tracked shows: {len(shows)} | episodes in window: {in_win} | episode rows known: {total}")
print("\nEpisodes per month (window):")
for m in sorted(months): print(f"  {m}: {months[m]}")
print(f"\nTracked shows with 0 episodes in window: {len(zero)}")
for t,n,l in sorted(zero,key=lambda x:(x[2] or '')): print(f"  - {t}  | {n} | {l}")
