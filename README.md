# WarriorCon 6 campaign dashboard

A one-page scoreboard of the WC6 email and text campaigns, split into
**Promote** (people without a ticket) and **Post-ticket seduction** (ticket holders).

## How it updates

- **Every 6 hours:** a GitHub Action puts fresh numbers on the page by 7am, 1pm, 7pm and 1am Eastern (7am ET = 8pm Manila). Each run starts 45 minutes early: 11:15, 17:15, 23:15 and 05:15 UTC, since all dates through Dec 4 are EST. If a pull stops (GHL sometimes returns short or empty data), the run waits 3 minutes and tries once more. It runs on GitHub's computers, so your Mac can be off. GitHub sometimes starts scheduled runs a few minutes late.
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

**Yesterday's numbers, the daily report and the executive summary** come from the last full day (midnight to midnight Pacific). They're set by the 7am run and stay the same at 1pm, 7pm and 1am. The rest of the page updates each run, including the "Today so far" line.

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
| `config.json` | Settings: workflows, the 48-hour credit window, red-line thresholds, summary rules, product names, team test orders, Bring Your Brother |
| `scripts/pull.py` | Reads GHL and builds the data files |
| `scripts/privacy_scan.py` | The privacy check |
| `.github/workflows/daily-refresh.yml` | The daily GitHub Action |
| `data/raw/` | Private cache on your Mac. **Never published** (blocked by `.gitignore`). |

## How the numbers work

- **Yesterday:** the previous full day, midnight to midnight Pacific. "Last updated" is shown in Eastern time.
- **Ticket holder:** a paid WC6 ticket order of $199 or more, the comp tag, or a free Bring Your Brother ticket (below). A person counts as a ticket holder for a message only if they bought or claimed before it was sent. Other $0 and $1 test orders don't count.
- **Refunds (v1.5.3):** GHL keeps a refunded order "Completed" and shows the refund only as `paymentSummary.refundedAmount` on the order. A ticket whose refund covers the ticket line is left out of ticket holders, sales, credit, Power Plan and Business Bible. It's shown as "X refunded ($Y) · not counted" on the page and as a "Refunds:" line in Garrett's report. GHL gives no refund date, so the order's last update is used, fixed the first time the refund is seen (`data.json` → `refunds.seen`, keyed by a hash of the order ID). Refunded buyers still count as ticket holders for messages sent before the refund, so sent counts don't move.
- **Team test orders (v1.5.4):** team test buys are listed in `config.json` → `ticket_holder_rule.team_test_orders`, by order ID, date and amount only. They're left out like the $0/$1 tests and never count as refunds. Right now there are 2: Oct 21 and Oct 30, $199 each, both refunded. The refund line counts real customer refunds only. When there are none, the report says "Refunds: 0 to date" and the tile hides the line.
- **Bring Your Brother (v1.6):** a ticket holder sends a friend to warriorcon6.com/bring-your-brother, and the friend gets a free ($0) WarriorCon6 Virtual Ticket with code FREEMAN. Settings are in `config.json` → `bring_your_brother`.
  - **How a brother is found:** a paid $0 order with the WarriorCon6 Virtual Ticket where the order's `sourceId` is the "WC6 – Bring a Brother" funnel, or `couponCode` is FREEMAN. These fields come from the orders list (`GET /payments/orders`). If GHL ever leaves both out, the fallback is a $0 ticket order on or after Nov 19 on a contact tagged `wc6_brother_free`. The tag is also checked every run as a cross-check, and the run log prints both counts and whether they agree.
  - **Counted once, by person:** a brother who also has a paid ticket or the comp tag counts as paid or comp, not as a brother. Team test claims are listed in `ticket_holder_rule.team_test_orders` (order ID, date and amount only) and are left out. So far there are 2 (Nov 19 and Nov 20, $0).
  - **Ticket holders = paid + comps + brothers.** A brother counts as a ticket holder for messages sent after his claim, the same rule as buyers.
  - **Stays paid-only:** total sales, ticket sales (brother tickets are $0), tickets from campaigns, the Business Bible take rate and refunds.
  - **Warrior App:** a Power Plan sign-up on a brother's contact, or one from the BYB Warrior AI step, counts only in Bring Your Brother. The Upsells number and % stay "of paid + comp ticket holders".
  - **Yesterday:** the same Pacific day and 7am snapshot as the rest. The brother counts are saved in `data.json` → `frozen.byb`.
  - **No names:** the page, the repo and the report show totals only. Code FREEMAN is shared by everyone, so nobody can tell who invited whom. There are no invite emails or texts; Garrett shares the link himself.
- **Credited sale:** a ticket purchase is credited to the last Promote email or text the buyer got in the 48 hours before buying. To change the window, edit `attribution_window_hours` in `config.json`.
- **Email rates:** opens, clicks, unsubscribes and bounces come from GHL **per email, not per day**. For a date range, they count only the emails sent (95%+) inside it. If none fit, the page shows "totals only". Sends, text deliveries, failures and opt-outs are true per-day counts.
- **Click rates** are out of emails delivered, the same way GHL calculates them. Apple Mail opens emails automatically, which inflates open rates, so clicks are the more reliable signal.
- **Ticket holder emails** have no links except unsubscribe, so their click rate shows as "no links".
- **Text clicks:** GHL doesn't provide click counts for text links through the API, so they show as "pending".
- **Not delivered (v1.5.4):** a text counts as "Not delivered" when GHL marks it **failed** or **undelivered** in the conversation history (the message export). Each one is split by GHL's error text into **blocked · Texas SMS safeguard** (GHL's own block on texts to or from Texas numbers) and **carrier / other** (for example unreachable numbers, UK numbers, carrier errors). The Watch card names the main cause when one reason is half or more of them.
  - **Why GHL's workflow panel shows fewer:** the Failed tile in a workflow's Stats view counts only some of these. On Nov 15, Promote SMS 12 showed 430 failed in the panel, while the message history had 580 failed + 23 undelivered (603). GHL doesn't say which ones the panel leaves out. Sent and delivered match the panel exactly. The page uses the message history because it covers every text and gives the reason.
- **Power Plan:** paid sign-ups by ticket holders. **Business Bible:** every paid sale, whether added at ticket checkout or bought on its own.

## Executive summary rules (set in `config.json` → `summary_rules`)

- **Headline:** new tickets yesterday, including brothers (shown as "5 new tickets yesterday (2 paid + 3 brothers)" when there are some). The "in line / above / below" check compares paid tickets with the average of the 7 days before. Within 20% counts as "in line".
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

**What's left (v1.5):** `plan.json` is the WC6 send plan, read once from the GoHighLevel workflows (read-only). Each run marks a step sent once 10+ sends show up and counts what's left up to Dec 2. Runs never change `plan.json`. If a send shows up that isn't in the plan, or a planned send doesn't go out, the page and the run log say "Plan may be out of date". Re-read the plan only when PJ asks.

**Plan check (v1.5.1):** every run lists the GHL workflows through the official API. It returns `id, name, status, version, createdAt, updatedAt, locationId`. The page shows the amber **"! Plan out of date"** warning at the top of "What's left." when either of these is true:
- a WC6-named workflow exists that isn't in `config.json` and isn't excluded;
- a planned workflow's `version` or `updatedAt` is newer than the baseline that `plan.json` stored at the last re-read.

When the warning comes on, the run log says so and the "Plan check notice" step opens a "WC6 plan out of date" issue, which emails PJ. That step never fails the update. Garrett's report is unchanged. Note that any save in GHL counts as an edit, including a rename or a setting change.

### Re-read the WC6 plan (what Claude Code does for "Re-read the WC6 plan: …")

Read-only in GHL. Never create or change anything there.

1. `git pull`. In `data.json` → `plan_check.items`, find the flagged workflow IDs. If the page data is old, list them fresh with the API, as `check_workflows` does.
2. **New workflow?** Tell PJ its name and ask whether it's **Promote** or **Post-ticket seduction**, or whether to exclude it (add its ID to `workflow_name_rules.excluded`). Don't guess.
3. Start `python3 -I scripts/plan_receive.py data/raw/<YYYY-MM-DD>_plan-read.json` in the background. In Chrome (WUW profile), open `https://app.gohighlevel.com/v2/location/BDeGaczWUBVqlvyWoI7l/automation/workflows`. Check the domain, the location ID and the sub-account name "Wake Up Warrior". Then run `scripts/plan_read_chrome.js` in the javascript tool with `IDS` set to the flagged IDs.
4. `python3 -I scripts/plan_merge.py data/raw/<read>.json`. This is a dry run, so check the changes first. Then add `--write`, plus `--new <id>=<promote|post_ticket>:"<x.xx Emails|Texts>"` for a workflow PJ labelled. If anything prints CHECK BY HAND, fix those steps by hand.
5. `python3 -I scripts/privacy_scan.py plan.json config.json`, then commit and push.
6. `gh workflow run "Daily refresh" -R pj807/wc6-kpi-2iifeu`. When it's done, confirm that the warning has cleared (`plan_check.stale` is false) and the notice issue has closed. Report the new "X left of Y" per audience, the last date and the next send.
