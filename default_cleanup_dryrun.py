#!/usr/bin/env python3
"""DRY-RUN: what the legacy 'default' profile holds vs your real (admin)
profile, across the user-scoped tables. Read-only — changes NOTHING."""
import os, sqlite3
DB = os.environ.get("AEVUM_DB", os.path.expanduser("~/.local/share/media-search-engine/media_search.db"))
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); c.row_factory=sqlite3.Row

print("Profiles in the app:")
for p in c.execute("SELECT id,name,is_admin FROM profiles ORDER BY is_admin DESC"):
    print(f"  - {p['name']:<18} admin={p['is_admin']}  id={p['id']}")
admins = [r["id"] for r in c.execute("SELECT id FROM profiles WHERE is_admin=1")]
admin = admins[0] if admins else None
print(f"\nAdmin (Dale) = {admin}\nLegacy       = 'default'\n")

def overlap(table, keycols):
    try:
        d = c.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id='default'").fetchone()[0]
        a = c.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id=?", (admin,)).fetchone()[0]
        only = c.execute(f"""SELECT COUNT(*) FROM {table} dft WHERE dft.user_id='default'
            AND NOT EXISTS (SELECT 1 FROM {table} adm WHERE adm.user_id=?
              AND {' AND '.join(f'adm.{k} IS dft.{k}' for k in keycols)})""", (admin,)).fetchone()[0]
        print(f"{table:<22} default={d:<6} admin={a:<6} only on default (would be lost): {only}")
    except Exception as e:
        print(f"{table:<22} (skipped: {e})")

if admin and admin != 'default':
    overlap("user_title_state",      ["title_id"])
    overlap("series_episode_watched",["title_id","season","episode"])
    overlap("playback_positions",    ["title_id","season","episode"])
    d_lists = [r["name"] for r in c.execute("SELECT name FROM user_lists WHERE user_id='default'")]
    a_lists = {r["name"] for r in c.execute("SELECT name FROM user_lists WHERE user_id=?", (admin,))}
    print(f"\nwatchlists on default: {d_lists or 'none'}")
    print(f"  names NOT already on your profile: {[n for n in d_lists if n not in a_lists] or 'none'}")
    # how many watchlist *items* sit under default's lists
    items = c.execute("""SELECT COUNT(*) FROM user_list_items uli
        JOIN user_lists ul ON ul.id=uli.list_id WHERE ul.user_id='default'""").fetchone()[0]
    print(f"  total items in default's watchlists: {items}")
else:
    print("No real admin profile distinct from 'default'.")
