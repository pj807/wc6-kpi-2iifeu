# WarriorCon 6 campaign dashboard

A one-page scoreboard of the WC6 email and text campaigns, split into
**Promote** (people without a ticket) and **Post-ticket seduction** (ticket holders).

## How it updates

- **3 times a day:** a GitHub Action puts fresh numbers on the page by 7am, 1pm and 5pm Eastern (7am ET = 8pm Manila). Each run starts 30 minutes early: 11:30, 17:30 and 21:30 UTC, since all dates through Dec 4 are EST. It runs on GitHub's computers, so your Mac can be off. GitHub sometimes starts scheduled runs a few minutes late.
- **Any time:** on GitHub, open the repo's **Actions** tab, click **Daily refresh** on the left, then **Run workflow** (top right of the list) and the green **Run workflow** button.
- **From your Mac:** open Terminal and run:

```
cd "~/Library/Mobile Documents/com~apple~CloudDocs/Claude/Claude WUW/assets/code/wc6-kpi-dashboard"
./refresh.sh
```

Each update:

1. Reads the latest numbers from GHL. It's read-only, so nothing in GHL changes.
2. Checks every file for emails, phone numbers, contact IDs and keys. If it finds any, it stops and publishes nothing.
3. Publishes the new numbers. If any step fails, the page keeps the last good numbers.

Each GitHub run reads only what's new:

- **Emails:** only those sent since the last run.
- **Texts:** the last 3 days, because delivery status can change after a text is sent.
- **New ticket buyers:** only their own recent messages, to credit the sale.

Older numbers come from `data.json`, which holds totals only. Your Mac's `./refresh.sh` re-reads the whole campaign using a private cache in `data/raw/`.

**Yesterday's numbers, the daily report and the executive summary** come from the last full day (midnight to midnight Pacific). They're set by the 7am run and stay the same at 1pm and 5pm. The rest of the page updates each run, including the "Today so far" line.

If the page is open when new numbers arrive, a bar says "New data in" with a Show button. The page checks every 2 minutes.

## Checking that the daily run worked

- On the page, **Last updated** (Eastern time) shows when the last run finished. Under it you'll see the update times and when the next one is due.
- On GitHub, the **Actions** tab shows each run. A green tick means it worked, and a red cross means it failed. Click a run to see which step failed. A failed run changes nothing on the page.
- GitHub also emails the repo owner when a scheduled run fails.

## What's in this folder

| File | What it is |
|---|---|
| `index.html` | The dashboard page |
| `data.json` | Every number the page shows, per day (Pacific days). Totals only. |
| `summary.json` | Garrett's daily numbers only |
| `report.txt` | The copy-and-send daily report, the same text as the Copy button |
| `changelog.json` / `CHANGELOG.md` | Version history. The "What's new" panel reads `changelog.json`. |
| `config.json` | Settings: workflows, the 48-hour credit window, red-line thresholds, summary rules, product names |
| `scripts/pull.py` | Reads GHL and builds the data files |
| `scripts/privacy_scan.py` | The privacy check |
| `.github/workflows/daily-refresh.yml` | The daily GitHub Action |
| `data/raw/` | Private cache on your Mac. **Never published** (blocked by `.gitignore`). |

## How the numbers work

- **Yesterday:** the previous full day, midnight to midnight Pacific. "Last updated" is shown in Eastern time.
- **Ticket holder:** a paid WC6 ticket order of $199 or more, or the comp tag. A person counts as a ticket holder for a message only if they bought before it was sent. $0 and $1 test orders don't count.
- **Credited sale:** a ticket purchase is credited to the last Promote email or text the buyer got in the 48 hours before buying. To change the window, edit `attribution_window_hours` in `config.json`.
- **Email rates:** opens, clicks, unsubscribes and bounces come from GHL **per email, not per day**. For a date range, they count only the emails sent (95%+) inside it. If none fit, the page shows "totals only". Sends, text deliveries, failures and opt-outs are true per-day counts.
- **Click rates** are out of emails delivered, the same way GHL calculates them. Apple Mail opens emails automatically, which inflates open rates, so clicks are the more reliable signal.
- **Ticket holder emails** have no links except unsubscribe, so their click rate shows as "no links".
- **Text clicks:** GHL doesn't provide click counts for text links through the API, so they show as "pending".
- **Power Plan:** paid sign-ups by ticket holders. **Business Bible:** every paid sale, whether added at ticket checkout or bought on its own.

## Executive summary rules (set in `config.json` → `summary_rules`)

- **Headline:** new paid tickets yesterday compared with the average of the 7 days before it. Within 20% counts as "in line".
- **Win:** the first rule that applies:
  1. A send from yesterday with a click rate at least 1.5× its campaign's average.
  2. The upsell with the highest take rate.
  3. The best open rate among sends with 100+ recipients.
- **Watch:** the metric furthest past its red line in `thresholds`. If nothing is past its line, it shows "Nothing needs attention today."

Each refresh prints which rule picked each line.

## Versions

The version only changes when the page itself changes. Daily data refreshes keep the same version.

1. Update `PAGE_VERSION` in `index.html`. Use a new feature number (1.1, 1.2) for new features or a fix number (1.0.1) for fixes.
2. Add an entry at the top of `changelog.json` and `CHANGELOG.md`.

After that:
- Each browser sees an "Updated" popup once per new version.
- Pages left open check every 10 minutes and show a "New version available" bar.

## Keeping it private

- The GHL key lives in your Mac's Keychain (`ghl-wuw-kpi`) and, for the daily run, as the GitHub secret `GHL_TOKEN`. It is never in these files.
- The page tells search engines not to list it, and the web address is hard to guess. Anyone with the link can still open it, so share the link only with people who should see it.
