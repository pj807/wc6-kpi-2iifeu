# Changelog

The version only changes when the page itself changes. Daily data refreshes keep the same version.
New features go up a minor number (1.1, 1.2). Fixes go up a patch number (1.0.1).
The "What's new" panel on the page reads `changelog.json`, so update both files together.

## v1.3 · Ready to send · Nov 11, 2026

- **"Ready to send" status** at the top of Today's report, so you know at a glance whether to send it.
- **Ready to send** (green): today's 7am ET update is in. The report covers yesterday.
- **Not updated yet** (amber): before the 7am ET update lands, you're looking at the previous day's report. The button says "Copy anyway" and still copies it.
- **Out of date** (red outline): the 7am ET update hadn't arrived by 7:45am ET. Check the report before sending.
- Only the 7am ET update changes this status. The 1pm and 5pm updates don't.
- The copied report's first line now says which day it covers and when it was updated, for example "WarriorCon 6 — report for Nov 10 (updated Nov 11, 7:02am ET)".

## v1.2 · Countdown to the next update · Nov 11, 2026

- **Countdown to the next update** under "Last updated", for example "Next update in about 2h 15m". It refreshes every minute.
- **All times are Eastern (ET)**, wherever you are. The page uses Eastern time even if your phone or computer is set to Manila or anywhere else.
- When an update is due, it says **"Updating now — usually ready within 15 min"**. When the new numbers are in, the "New data in · Show" bar appears and the countdown moves to the next update.
- If an update hasn't arrived 45 minutes after it was due, it says **"Update is late — showing the last numbers"**. The numbers on the page are still the last good ones.

## v1.1.2 · Daily update now lands at 7am ET · Nov 11, 2026

- **The main daily update now lands at 7am ET** (8pm Manila), an hour earlier. It sets yesterday's numbers, the daily report and the executive summary.
- The 1pm and 5pm ET updates refresh the to-date numbers and "Today so far".

## v1.1.1 · Fixes · Nov 11, 2026

- The **View in GHL** menu now shows as one clean white box.
- **More reliable updates:** each update now double-checks the texts it reads from GoHighLevel. If anything is missing, it keeps the last good numbers instead of showing low ones.

## v1.1 · Links into GoHighLevel · Nov 11, 2026

- **Unsubscribed, bounced and failed counts are now clickable.** Hover or tap a count and pick "View in GHL" to open the workflow that lists those contacts.
- In the workflow, turn on **Stats view** (chart icon) and click Unsubscribed, Bounced or Failed on a step to see the contacts.
- Text opt-out counts will link to a saved GoHighLevel list once it's set up.
- No names, emails or phone numbers are on this page. The links only open GoHighLevel, where you need to be logged in.

## v1.0.1 · Fixes · Nov 11, 2026

- **Total sales** now adds ticket and Business Bible sales from each order's line items, so the Business Bible is no longer counted twice.
- **Business Bible take rate** counts people (16 of 134 paid buyers), not sales. Revenue still shows all 17 sales.
- **Daily report** is rebuilt on every update, so its time matches "Last updated". Yesterday's numbers still come from the 8am update.
- **Same number everywhere:** the summary uses the same figures as the tiles.
- **Tile descriptions** now use plain-English wording.

## v1.0 · First release · Nov 11, 2026

- **Executive summary**: Headline, Win and Watch, three lines at the top.
- **Daily report for Garrett** with a Copy button, updated every morning.
- **Campaign to date** tiles with an All / Ticket holders / Non-ticket holders switch.
- **Promote and Post-ticket tables**: sent, opens or delivered, clicks, unsubscribes or opt-outs, bounces or failed.
- **Counts under every %**. Hover or tap for the full number.
- **App & add-ons**: Power Plan and Business Bible, take rate and revenue.
- **Date filter**: Yesterday, Last 7 days, Last 30 days, Campaign to date, Custom dates.
- **Day-by-day chart** and a sortable list of every email and text.
- Warning colors when unsubscribes, bounces, opt-outs or failed texts run high.
