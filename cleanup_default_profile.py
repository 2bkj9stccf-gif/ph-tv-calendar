#!/usr/bin/env python3
"""Consolidate the legacy 'default' profile onto the real admin profile,
then remove 'default'. Backs the DB up first. One transaction; rolls back
on any error. Idempotent (a second run finds nothing to do)."""
import os, sqlite3, datetime
DB = os.environ.get("AEVUM_DB", os.path.expanduser("~/.local/share/media-search-engine/media_search.db"))
LEGACY = "default"

con = sqlite3.connect(DB, timeout=15)
con.execute("PRAGMA busy_timeout=15000")
con.execute("PRAGMA foreign_keys=ON")
cur = con.cursor()

admin_row = cur.execute("SELECT id,name FROM profiles WHERE is_admin=1 ORDER BY created_at LIMIT 1").fetchone()
if not admin_row or admin_row[0] == LEGACY:
    print("No real admin profile distinct from 'default' — nothing to clean."); raise SystemExit
ADMIN, ADMIN_NAME = admin_row
print(f"Admin profile: {ADMIN_NAME} ({ADMIN})\n")

def dcount(t): return cur.execute(f"SELECT COUNT(*) FROM {t} WHERE user_id=?", (LEGACY,)).fetchone()[0]
tables = ("user_title_state","series_episode_watched","playback_positions","user_lists")
before = {t: dcount(t) for t in tables}
print("'default' rows BEFORE:", before)
if sum(before.values()) == 0:
    print("\nNothing on 'default'. Already clean."); raise SystemExit

# Backup first (consistent snapshot via SQLite backup API)
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
bkdir = os.path.join(os.path.dirname(DB), "db-backups")  # local disk, next to live DB
os.makedirs(bkdir, exist_ok=True)
bkpath = os.path.join(bkdir, f"pre_default_cleanup_{ts}.db")
bk = sqlite3.connect(bkpath)
with bk: con.backup(bk)
bk.close()
print(f"\nBackup written: {bkpath}\n")

try:
    cur.execute("BEGIN")
    # 1. merge resume points that exist ONLY on 'default'
    cur.execute("""
      INSERT INTO playback_positions (user_id,title_id,season,episode,position_seconds,duration_seconds,updated_at)
      SELECT ?,title_id,season,episode,position_seconds,duration_seconds,updated_at
      FROM playback_positions p WHERE p.user_id=?
        AND NOT EXISTS (SELECT 1 FROM playback_positions a WHERE a.user_id=?
            AND a.title_id IS p.title_id AND a.season IS p.season AND a.episode IS p.episode)
    """, (ADMIN, LEGACY, ADMIN))
    moved_pp = cur.rowcount
    # 2. move 'default' watchlists whose name isn't already on admin (items follow via list_id)
    cur.execute("UPDATE user_lists SET user_id=? WHERE user_id=? AND name NOT IN (SELECT name FROM user_lists WHERE user_id=?)",
                (ADMIN, LEGACY, ADMIN))
    moved_lists = cur.rowcount
    # 3. delete leftovers (uts/sew already fully on admin; any name-collision lists + their items; remaining pp)
    cur.execute("DELETE FROM user_list_items WHERE list_id IN (SELECT id FROM user_lists WHERE user_id=?)", (LEGACY,))
    cur.execute("DELETE FROM user_lists WHERE user_id=?", (LEGACY,))
    cur.execute("DELETE FROM playback_positions WHERE user_id=?", (LEGACY,))
    cur.execute("DELETE FROM series_episode_watched WHERE user_id=?", (LEGACY,))
    cur.execute("DELETE FROM user_title_state WHERE user_id=?", (LEGACY,))
    con.commit()
    print(f"Merged onto {ADMIN_NAME}: {moved_pp} resume point(s), {moved_lists} watchlist(s).")
    print("'default' rows AFTER:", {t: dcount(t) for t in tables})
    print("\n✅ Cleanup complete. You should now have just Dale and Shezza.")
    print("   Next: restart Aevum (Restart Media.command) so it reloads clean.")
except Exception as e:
    con.rollback()
    print(f"\n❌ Failed — rolled back, NO changes made. Error: {e}")
    print(f"   Your backup is safe at: {bkpath}")
    print("   (If it said 'database is locked', quit Aevum and run this again.)")
finally:
    con.close()
