# Auto-download new episodes (box 2)

Downloads new episodes of the shows you're **watching or have on a watchlist**,
automatically, without going through the Aevum app's download screen. It runs on
the same dependable rails as the TV calendar: a small scheduled job that reads
the shared Aevum database directly.

## The decoupled pipeline

```
1. Aevum app            you just watch / watchlist here (pure player)
        |
        v   shared DB: "what I'm watching" + episode air dates
2. THIS JOB             decides what to fetch  (auto_enqueue_episodes.py)
        |
        v   writes PENDING rows into download_queue
3. DownloadEngine       finds + downloads the torrent
        |
        v
4. DownloadSentry       remuxes + files it into the library
        |
        v
5. Aevum scanner        sees the new file, updates the library
```

Boxes 1, 3, 4, 5 already existed. This adds box 2 — the missing link that turns
"shows I follow" into actual download requests. The mental model: **if it's on
your TV calendar, this job will fetch it.** Same source, same schedule, same
reliability.

## What it does, precisely

* Reads the *identical* tracked-show set the calendar publishes — shows you've
  played/watched/bookmarked, or have on any watchlist, for your profile.
* For each, finds episodes whose `air_date` falls in a window: at least
  `AUTO_DL_MIN_AGE_DAYS` old (default **1** — the "ripen" delay) and no older
  than `AUTO_DL_LOOKBACK_DAYS` (default **7**). So it grabs **new airings only**,
  but waits a day first — the first rips on air day are often rushed /
  low quality, and waiting lets the better WEB-DL / proper encodes appear so the
  ranker has good candidates. It never reaches into a show's old back-catalogue.
* Skips anything already **on disk**, already **queued/downloading**, or
  already **fetched before** (so it won't re-grab something you deleted).
* Inserts download requests that are the same shape the app would write
  (`status=PENDING`, `media_type=episode`, `source=auto_calendar`, `priority=5`).
  DownloadEngine then handles them exactly as normal.

It does **not** touch the Aevum app, its download UI, or the half-built
`series_monitor` table. Your watchlist is the monitor.

## Files

| File | Role |
|------|------|
| `auto_enqueue_episodes.py` | The job itself (stdlib only, no installs). |
| `auto_enqueue.sh` | Runner: invokes the job, logs to MediaStack. |
| `Preview Auto-Download (dry run).command` | **Run this first** — shows what it *would* queue, writes nothing. |
| `Setup Auto-Download Schedule.command` | Installs the launchd agent (login + every 3h). |
| `../shared/launchd/com.media.autoenqueue.plist` | Schedule template. |

## Getting started

1. Double-click **`Preview Auto-Download (dry run).command`** and check the list
   of episodes looks right.
2. If happy, double-click **`Setup Auto-Download Schedule.command`** to enable it.

That's it — from then on, new episodes of your shows queue themselves.

## Tuning (optional env vars)

| Variable | Default | Meaning |
|----------|---------|---------|
| `AUTO_DL_LOOKBACK_DAYS` | `7` | How many days back counts as "new". Widen if the Mac is often off. |
| `AUTO_DL_MIN_AGE_DAYS` | `1` | Ripen delay — wait this many days after air before grabbing, so better rips appear. Set `0` to grab on air day. |
| `AUTO_DL_PRIORITY` | `5` | Queue priority (manual user requests are 10, upgrades 1). |
| `AUTO_DL_QUALITY_PROFILE` | unset | `quality_profile_id` to request; unset = server default. |
| `AUTO_DL_SOURCE` | `auto_calendar` | Tag on the queue rows (handy for filtering/cleanup). |
| `AUTO_DL_DRY_RUN` | `0` | `1` = report only, write nothing. |
| `AEVUM_USER_ID` | admin profile | Whose shows to follow. |

## Notes / caveats

* This fixes the **trigger** ("new episodes don't auto-grab"). It does **not**
  fix torrents that **stall or fail** — that's DownloadEngine tuning, tracked
  separately.
* Rows are tagged `source=auto_calendar`, so you can always see/clean what this
  job added: `… WHERE source='auto_calendar'`.
* Because requests go straight into the shared queue, the Aevum *app* can be
  closed and this still works. It only needs the Aevum **database** (and the
  DownloadEngine/Sentry services) running, exactly like the calendar.
