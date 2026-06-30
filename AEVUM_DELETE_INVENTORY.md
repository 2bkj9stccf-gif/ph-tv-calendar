# Aevum download code — delete-vs-keep inventory

A review list for trimming Aevum down to "just a player" once box 2 (the
calendar-side auto-enqueue) is proven in production. **Nothing here is deleted
yet.** Order of operations: enable box 2 → confirm episodes flow end-to-end for
a week → then remove the items in "Safe to delete."

> Rule of thumb: the **data layer** (shared DB, episode/air-date sync, the
> `download_queue` table, the scanner) is load-bearing and stays. The **app's
> download UI** and the **half-built `series_monitor`** feature are what go.

## ✅ Safe to delete (after box 2 is verified)

### tvOS app — the whole download UI
The app becomes browse + play only. These have no other consumers:

* `Aevum/clients/apple/tvos/Aevum/AevumTV/Views/DownloadsView.swift`
* `Aevum/clients/apple/tvos/Aevum/AevumTV/ViewModels/DownloadsViewModel.swift`
* `Aevum/clients/apple/tvos/Aevum/AevumTV/Views/DownloadFlowView.swift`
* `Aevum/clients/apple/tvos/Aevum/AevumTV/Views/DownloadFlowViewModel.swift`
* `Aevum/clients/apple/tvos/Aevum/AevumTV/Views/DownloadScopeView.swift`
* `Aevum/clients/apple/tvos/Aevum/AevumTV/Views/ShowDownloadsView.swift`

Plus the entry points into them: any "Download" / "Follow show" buttons and the
Downloads tab/menu navigation, and the `APIClient` download methods
(`queueForDownload`, `enqueueDownload`, `fetchDownloadStatus`, pause/resume).
*Verify by grep for these symbols before cutting; remove the now-dead nav.*

### Server — the half-built monitor feature
Your watchlist replaces it entirely:

* `handlers_download.py` → `ApiSeriesMonitorH` (POST `/api/v1/download/monitor`, ~line 1556)
* `handlers_download.py` → `ApiSeriesMonitorDeleteH` (DELETE `/api/v1/download/monitor/...`, ~line 1594)
* The `series_monitor` table (defined in `core.py`) and its index.
* References to clean up when the table goes: `handlers_download.py` lines ~381
  and ~396 (quality-profile delete touches `series_monitor`), and the scanner's
  title-retention join in `scanner.py` (~line 2055, `SELECT … FROM series_monitor`).
* Remove the two monitor routes from the route table in `main.py`.

## 🟡 Optional — only the app consumed these
Harmless to keep for observability/debugging; remove only if you want a fully
minimal server. If kept, they just sit idle once the app UI is gone:

* `handlers_download.py` → `ApiDownloadQueueAddH` (POST enqueue). Box 2 writes to
  the DB directly, so the app was its only caller. **Recommend keep** — it's the
  supported, validated insert path and a useful manual/automation hook.
* `handlers_download.py` → `ApiDownloadQueueListH` and the other queue *status*
  endpoints (the app's Downloads screen polled these). Safe to keep for a future
  read-only "what's downloading" view.

## ⛔ Must keep (load-bearing — do NOT delete)

* **`download_queue` table** + its claim/lock columns — DownloadEngine reads it;
  box 2 and (optionally) the enqueue endpoint write it; the scanner clears rows.
* **Episode / air-date sync** — whatever Aevum job populates `series_episodes`
  and `upcoming_episodes` from TMDB. Box 2 *and* the calendar read this; killing
  it blinds both.
* **Watch/watchlist tracking** — `user_title_state`, `playback_positions`,
  `user_lists` / `user_list_items`. This is now the single source of truth for
  "what to download."
* **Scanner + library-scan endpoint** (`scanner.py`, the
  `/api/settings/library-scan` handler) — box 5; how new files become visible.
* **`download_history`** — box 2 reads it to avoid re-grabbing deleted episodes.

## 🤔 Separate decision — not part of this change

* `general_upgrade_worker.py` (quality upgrades of existing files). This is a
  *different* feature from new-episode fetching. Leave it unless you also want to
  drop automatic quality upgrades — say the word and it's a clean separate cut.

## Suggested sequence

1. Ship box 2; watch `auto_enqueue.log` and the library for ~a week.
2. Delete the tvOS download UI (lowest risk — pure client cleanup).
3. Remove `series_monitor` (table + 2 endpoints + the 3 references above).
4. Decide on the optional enqueue/status endpoints.
5. Leave everything under "Must keep" untouched.
