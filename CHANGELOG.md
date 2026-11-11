# Changelog

The version only changes when the page itself changes. Daily data refreshes keep the same version.
New features go up a minor number (1.1, 1.2). Fixes go up a patch number (1.0.1).
The "What's new" panel on the page reads `changelog.json`, so update both files together.

## v1.5 · What's left to send · Nov 11, 2026

- **New: "What's left."** at the very bottom of the page shows how many emails and texts are still to go for each audience, up to Dec 2.
- Each audience shows **"X left of Y"**, a progress bar, how many have sent and the date of the last one.
- **Next send** shows the day and time (ET), which workflow step it is, and the subject line. Upcoming email subjects are listed below it.
- This section covers the whole campaign. **The date filter doesn't change it**, and the date bar stops at the line above it.
- Garrett's report now has a **LEFT TO SEND** block under SUMMARY.
- The plan was read once from the GoHighLevel workflows, without changing anything there. If a send shows up that isn't in the plan, or a planned send doesn't go out, the section says **"Plan may be out of date"** instead of guessing.
- Sends added in GoHighLevel after launch are now counted on the page as they go out: Promote Emails 23–28, Promote texts 9–14 and the Nov 13–17 ticket-holder emails.
- The message list leaves out test sends (fewer than 10).

## v1.4.1 · Fixes · Nov 11, 2026

- **Fewer false alarms:** the text count from GoHighLevel can shift by a few between updates. A drop of up to 10 texts (or 0.1%, whichever is larger) is now treated as normal and published. A bigger drop still stops the update and keeps the last good numbers.
- Emails sent must still never go down.

## v1.4 · Updates every 6 hours · Nov 11, 2026

- **Updates every 6 hours:** fresh numbers by 7am, 1pm, 7pm and 1am ET. The countdown follows the new times.
- The 7am ET update is still the main one. It sets yesterday's report, the executive summary and the "Ready to send" status. The other three refresh the to-date numbers and "Today so far".
- The small grey "Next: …" line under the countdown is gone. "Last updated" and "Next update in about …" stay.

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
