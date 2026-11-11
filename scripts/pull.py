"""WC6 KPI dashboard: pull GHL data (read-only), compute totals, write data.json, summary.json and report.txt.

Token: env GHL_TOKEN (GitHub Action) or macOS Keychain item "ghl-wuw-kpi" (your Mac).
Only totals are written. Per-contact data stays in memory or in data/raw/ on your Mac (never committed).

Two modes:
- Full (your Mac): reads every message since campaign start (uses a private cache in data/raw/).
- Daily (GitHub Action): re-reads only the last few days and keeps older days from the
  previous data.json, which holds per-day totals only. Set FULL=1 to force a full pull.
"""
import collections, gzip, hashlib, json, os, re, subprocess, sys, time, threading
import urllib.request, urllib.parse, urllib.error
from datetime import date as Date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
CFG = json.load(open(os.path.join(ROOT, "config.json")))
TZ = ZoneInfo(CFG["timezone"])                       # "yesterday" = midnight to midnight Pacific
SHOW_TZ = ZoneInfo(CFG["display_timezone"])          # "Last updated" shown in Eastern
LOC = CFG["location_id"]
BASE = "https://services.leadconnectorhq.com"
WINDOW = timedelta(hours=CFG["attribution_window_hours"])
RULE, UPS, TH, SR = CFG["ticket_holder_rule"], CFG["upsells"], CFG["thresholds"], CFG["summary_rules"]
STOP_WORDS = {"stop", "stopall", "stop all", "unsubscribe", "cancel", "end", "quit", "optout", "opt out", "revoke"}
ON_ACTIONS = bool(os.environ.get("GITHUB_ACTIONS"))
FLAGS = []


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def pt_day(s):
    return ts(s).astimezone(TZ).date().isoformat()


def pt_midnight_utc(day):
    """ISO UTC timestamp of midnight Pacific at the start of `day` (YYYY-MM-DD)."""
    d = datetime.fromisoformat(day).replace(tzinfo=TZ)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def pct(a, b):
    return round(100.0 * a / b, 1) if b else None


def fmt(n):
    return f"{int(round(n)):,}"


def money(n):
    return f"${int(round(n)):,}"


def short_day(day):
    d = Date.fromisoformat(day)
    return f"{d.strftime('%b')} {d.day}"


# ---------------------------------------------------------------- API (read-only GETs + one contact search)
def token():
    if os.environ.get("GHL_TOKEN"):
        return os.environ["GHL_TOKEN"].strip()
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", "ghl-wuw-kpi", "-w"], capture_output=True, text=True)
        return r.stdout.strip() or None
    except FileNotFoundError:
        return None


class API:
    def __init__(self, tok):
        self.tok = tok

    def req(self, method, path, params=None, body=None, version="2021-07-28"):
        url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
        data = json.dumps(body).encode() if body is not None else None
        for i in range(6):
            r = urllib.request.Request(url, data=data, method=method, headers={
                "Authorization": "Bearer " + self.tok, "Version": version, "Accept": "application/json",
                "Content-Type": "application/json", "User-Agent": "wc6-kpi/1.0"})
            try:
                with urllib.request.urlopen(r, timeout=180) as resp:
                    return json.loads(resp.read() or b"{}")
            except urllib.error.HTTPError as e:
                if e.code == 429 or e.code >= 500:
                    time.sleep(3 * (i + 1)); continue
                raise SystemExit(f"GHL API error on {path.split('?')[0]}: HTTP {e.code}")
            except urllib.error.URLError:
                time.sleep(3 * (i + 1))
        raise SystemExit(f"GHL API: gave up on {path.split('?')[0]} after retries")

    def workflows(self):
        return self.req("GET", "/workflows/", {"locationId": LOC}).get("workflows", [])

    def orders(self):
        out, off, start = [], 0, CFG["campaign_start"]
        while True:
            rows = self.req("GET", "/payments/orders", {"altId": LOC, "altType": "location", "limit": 100, "offset": off}).get("data", [])
            if not rows:
                break
            for o in rows:
                if o.get("createdAt", "") < start:
                    continue
                items = self.req("GET", f"/payments/orders/{o['_id']}", {"altId": LOC, "altType": "location"}).get("items", [])
                out.append({"contact": o.get("contactId"), "created": o.get("createdAt"), "amount": o.get("amount") or 0,
                            "paid": o.get("status") == "completed" and o.get("paymentStatus") == "paid",
                            "items": [(i.get("name") or "", item_amount(i)) for i in items]})
            if rows[-1].get("createdAt", "") < start:
                break
            off += 100
        return out

    def comps(self):
        ids, page = set(), 1
        while True:
            cs = self.req("POST", "/contacts/search", body={"locationId": LOC, "pageLimit": 500, "page": page,
                          "filters": [{"field": "tags", "operator": "eq", "value": RULE["comp_tag"]}]}).get("contacts", [])
            ids.update(c["id"] for c in cs)
            if len(cs) < 500:
                return ids
            page += 1

    def step_stats(self, wf_id, step_id):
        for attempt in range(3):   # GHL sometimes returns a one-off 404 here
            try:
                s = self.req("GET", f"/emails/locations/{LOC}/campaigns/stats/workflow-campaigns/{wf_id}",
                             {"subSourceId": step_id}, version="v3").get("stats", {})
                return {k: s.get(k) or 0 for k in ("sent", "delivered", "opened", "clicked", "unsubscribed", "complained", "permanentFail")}
            except SystemExit as e:
                log(f"  retrying email stats ({e})")
                time.sleep(5 * (attempt + 1))
        return None

    def messages(self, channel, since, matcher, contact=None, until=None):
        """Compact records: [id, contact, date, direction, status, key, is_stop]. Outbound kept only if matched.
        With `contact`, reads only that one contact's messages (used to credit new purchases)."""
        out, cur, n, total = [], None, 0, None
        while True:
            p = {"locationId": LOC, "channel": channel, "limit": 1000, "startDate": since, "sortOrder": "asc"}
            if contact:
                p["contactId"] = contact
            if until:
                p["endDate"] = until
            if cur:
                p["cursor"] = cur
            r = self.req("GET", "/conversations/messages/export", p)
            ms = r.get("messages", [])
            if total is None and isinstance(r.get("total"), int):
                total = r["total"]
            n += len(ms)
            for m in ms:
                d = m.get("direction")
                if d == "outbound":
                    k = matcher(channel, m.get("subject") if channel == "Email" else m.get("body"))
                    if k:
                        out.append([m["id"], m.get("contactId"), m.get("dateAdded"), d, m.get("status"), k, False])
                elif d == "inbound" and channel == "SMS":
                    out.append([m["id"], m.get("contactId"), m.get("dateAdded"), d, m.get("status"), None,
                                norm(m.get("body")) in STOP_WORDS])
            if n and n % 20000 < 1000:
                log(f"  {channel}: {n:,} records read")
            cur = r.get("nextCursor")
            if not cur or not ms:
                if not contact and not until:
                    log(f"  {channel}: {n:,} records read in total, {len(out):,} kept")
                # GHL sometimes returns an empty or short export; the count must match the total GHL reports
                # (GHL's total can include a handful of records the export never returns, so allow a small gap)
                if total is not None and n < total - max(10, 0.005 * total):
                    raise ShortRead(f"{channel} export returned {n:,} of {total:,} records")
                return [r for r in out if not until or r[2] < until]


class ShortRead(Exception):
    pass


def item_amount(i):
    """Line total for an order item (price can be a number or {amount})."""
    p = i.get("price")
    amt = p.get("amount") if isinstance(p, dict) else p
    if amt is None:
        amt = i.get("amount") or 0
    return float(amt or 0) * (i.get("qty") or 1)


# ---------------------------------------------------------------- message matching
EMAIL_KEYS, SMS_KEYS, STEPS = {}, [], {}
for wf in CFG["workflows"]:
    for s in wf["steps"]:
        key = ("e:" if wf["channel"] == "email" else "s:") + norm(s["text"])[:40]
        STEPS.setdefault(key, {"label": wf["label"], "channel": wf["channel"], "text": s["text"], "names": [], "steps": [],
                               "no_links": bool(wf.get("no_links"))})
        STEPS[key]["names"].append(f"{wf['name'].split(' - ')[0]} {s['name']}")
        STEPS[key]["steps"].append((wf["id"], s["id"]))
        if wf["channel"] == "email":
            EMAIL_KEYS[norm(s["text"])] = key
        else:
            SMS_KEYS.append((norm(s["text"])[:40], key))


def mid(key):
    return hashlib.sha1(key.encode()).hexdigest()[:8]


def matcher(channel, text):
    t = norm(text)
    if channel == "Email":
        return EMAIL_KEYS.get(t)
    for prefix, key in SMS_KEYS:
        if t.startswith(prefix):
            return key
    return None


def fetch_messages(api, channel, since):
    """On your Mac: private cache in data/raw/ so only recent messages are re-read. On GitHub: no cache."""
    path = os.path.join(RAW, f"cache_{channel.lower()}.json.gz")
    old = []
    if not ON_ACTIONS and os.path.exists(path):
        try:
            old = json.load(gzip.open(path, "rt"))
        except Exception:
            old = []
    frm = since
    if old:
        frm = max(since, (ts(max(r[2] for r in old)) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S.000Z"))
    log(f"{channel}: reading since {frm[:10]}" + (" (plus local cache)" if old else ""))
    for attempt in range(5):
        try:
            new = api.messages(channel, frm, matcher)
            break
        except ShortRead as e:
            log(f"  {e}; retrying")
            time.sleep(15 * (attempt + 1))
    else:
        raise SystemExit(f"{channel} export never read completely. Nothing written; the page keeps the last good numbers.")
    merged = {r[0]: r for r in old}
    merged.update({r[0]: r for r in new})
    rows = sorted(merged.values(), key=lambda r: r[2])
    if not ON_ACTIONS:
        os.makedirs(RAW, exist_ok=True)
        json.dump(rows, gzip.open(path, "wt"))
    return [r for r in rows if r[2] >= since]


def fetch_sms_by_day(api, first_day, last_day):
    """Quick mode: read texts one Pacific day at a time. GHL's export sometimes skips a page, so each day
    must return as many records as the total GHL reports, or it's read again (up to 5 tries); otherwise the run
    stops and nothing is published."""
    out, d = [], Date.fromisoformat(first_day)
    while d.isoformat() <= last_day:
        a, b = pt_midnight_utc(d.isoformat()), pt_midnight_utc((d + timedelta(days=1)).isoformat())
        rows = None
        for attempt in range(5):
            try:
                rows = api.messages("SMS", a, matcher, until=b)
                break
            except ShortRead as e:
                log(f"  SMS {d.isoformat()}: {e}; retrying")
                time.sleep(15 * (attempt + 1))
        if rows is None:
            raise SystemExit(f"Texts for {d.isoformat()} never read completely. Nothing written; the page keeps the last good numbers.")
        log(f"  SMS {d.isoformat()}: {len(rows):,} records kept")
        out += rows
        d += timedelta(days=1)
    return out


def check_workflows(api):
    known = {w["id"] for w in CFG["workflows"]}
    rules = CFG["workflow_name_rules"]
    excluded = set(rules["excluded"])
    for w in api.workflows():
        name = w.get("name", "")
        if w["id"] in known or w["id"] in excluded or not re.search(rules["wc6_any"], name, re.I):
            continue
        if re.search(r"^(TEST|BACKUP|Copy)\b", name, re.I):
            continue
        if re.search(rules["promote"], name, re.I):
            FLAGS.append(f"New Promote workflow not in config yet (needs step IDs): {name}")
        elif re.search(rules["post_ticket"], name, re.I):
            FLAGS.append(f"New Post-ticket workflow not in config yet (needs step IDs): {name}")
        else:
            FLAGS.append(f"WC6 workflow that doesn't fit the naming rules, not counted: {name}")


# ---------------------------------------------------------------- main
def main():
    tok = token()
    if not tok:
        raise SystemExit("No GHL token found (Keychain ghl-wuw-kpi or GHL_TOKEN). Nothing written.")
    api = API(tok)
    now = datetime.now(timezone.utc)
    today = now.astimezone(TZ).date()
    yday = (today - timedelta(days=1)).isoformat()

    # Baseline: previous data.json (per-day totals only). Daily runs re-read the last few days on top of it.
    prev = None
    try:
        prev = json.load(open(os.path.join(ROOT, "data.json")))
        if prev.get("schema") != 2:
            prev = None
    except Exception:
        prev = None
    # Quick mode (GitHub runs): emails only since the last run; texts re-read for the last few days because
    # their delivery status changes after sending. Full mode (your Mac, or FULL=1): everything since campaign start.
    incremental = ON_ACTIONS and bool(prev and prev.get("email_watermark")) and not os.environ.get("FULL")
    cutoff = (today - timedelta(days=CFG["refresh_days"] - 1)).isoformat() if incremental else CFG["campaign_start"]
    sms_since = pt_midnight_utc((Date.fromisoformat(cutoff) - timedelta(days=1)).isoformat())   # +1 day for STOP replies
    email_since = prev["email_watermark"] if incremental else pt_midnight_utc(CFG["campaign_start"])
    log(f"Quick refresh: emails since the last run ({email_since[:16]}Z), texts from {cutoff}" if incremental
        else "Full pull from campaign start")

    check_workflows(api)
    res = {}
    since_by = {"Email": email_since, "SMS": sms_since}
    def _get(c):
        if c == "SMS" and incremental:
            first = (Date.fromisoformat(cutoff) - timedelta(days=1)).isoformat()
            res[c] = fetch_sms_by_day(api, first, today.isoformat())
        else:
            res[c] = fetch_messages(api, c, since_by[c])
    # One export at a time: GHL returns empty or missing pages when two message exports run at once.
    for c in ("Email", "SMS"):
        _get(c)
    log("orders + comps…")
    orders, comps = api.orders(), api.comps()
    log("email step stats…")
    stats = {}
    for key, st in STEPS.items():
        if st["channel"] == "email":
            for wid, sid in st["steps"]:
                v = api.step_stats(wid, sid)
                if v is not None:
                    stats[sid] = v
    if set(res) != {"Email", "SMS"}:
        raise SystemExit("Message pull failed. Nothing written.")
    msgs = res
    if incremental:   # the export's start time can be inclusive: keep only emails after the last one already counted
        msgs["Email"] = [r for r in msgs["Email"] if r[2] > email_since]
    marks = [r[2] for r in msgs["Email"]]
    email_watermark = max(marks) if marks else (email_since if incremental else now.strftime("%Y-%m-%dT%H:%M:%S.000Z"))

    # ---- ticket holders, upsells (orders are always read in full: they're small)
    has = lambda o, prefix: any(n.startswith(prefix) for n, _ in o["items"])
    first_buy, ticket_orders = {}, []
    for o in orders:
        if o["paid"] and has(o, RULE["ticket_product_name_prefix"]) and o["amount"] >= RULE["min_paid_amount"]:
            ticket_orders.append(o)
            if o["contact"] not in first_buy or o["created"] < first_buy[o["contact"]]["created"]:
                first_buy[o["contact"]] = o
    comps_only = comps - set(first_buy)
    holder_since = {c: o["created"] for c, o in first_buy.items()}
    all_holders = set(first_buy) | comps_only

    def is_holder(contact, when):
        return contact in comps_only or (contact in holder_since and holder_since[contact] <= when)

    def tick_amt(o):   # ticket line items only; order totals also include Business Bible bumps
        return sum(a for n, a in o["items"] if n.startswith(RULE["ticket_product_name_prefix"]))

    days = collections.defaultdict(lambda: {"tk": 0, "tkr": 0.0, "pp": 0, "bb": 0, "bbr": 0.0})
    for c, o in first_buy.items():
        d = days[pt_day(o["created"])]
        d["tk"] += 1; d["tkr"] += tick_amt(o)

    # Power Plan: first sign-up per contact, ticket holders only
    pp_first, pp_non_holders = {}, set()
    for o in orders:
        if o["paid"] and has(o, UPS["power_plan"]["name_prefix"]):
            if o["contact"] in all_holders:
                if o["contact"] not in pp_first or o["created"] < pp_first[o["contact"]]:
                    pp_first[o["contact"]] = o["created"]
            else:
                pp_non_holders.add(o["contact"])
    for c, when in pp_first.items():
        days[pt_day(when)]["pp"] += 1

    # Business Bible: every paid sale, whether added at ticket checkout (bump) or bought on its own
    bb = {"count": 0, "bump": 0, "standalone": 0, "revenue": 0.0}
    bb_people = set()
    for o in orders:
        if o["paid"] and has(o, UPS["business_bible"]["name_prefix"]):
            amt = sum(a for n, a in o["items"] if n.startswith(UPS["business_bible"]["name_prefix"]))
            bb["count"] += 1; bb["revenue"] += amt
            bb_people.add(o["contact"])
            bb["bump" if has(o, RULE["ticket_product_name_prefix"]) else "standalone"] += 1
            d = days[pt_day(o["created"])]
            d["bb"] += 1; d["bbr"] += amt

    # ---- per-message, per-day counts (right audience only; wrong-audience sends counted separately)
    fresh = collections.defaultdict(lambda: collections.defaultdict(lambda: [0] * 6))   # key -> day -> counts
    #   email: [sent, wrong_audience, 0, 0, 0, 0]
    #   sms:   [sent, wrong_audience, delivered, failed, optouts, replies]
    sends_by_contact = collections.defaultdict(list)
    for ch in ("Email", "SMS"):
        for _id, contact, when, direction, status, key, stop in msgs[ch]:
            if direction != "outbound" or not key:
                continue
            lab = STEPS[key]["label"]
            holder = is_holder(contact, when)
            right = (lab == "promote" and not holder) or (lab == "post_ticket" and holder)
            day = pt_day(when)
            sends_by_contact[contact].append((when, key, ch, right))
            if ch == "SMS" and day < cutoff:
                continue
            c = fresh[key][day]
            if not right:
                c[1] += 1
                continue
            c[0] += 1
            if ch == "SMS":
                if status == "delivered":
                    c[2] += 1
                elif status in ("failed", "undelivered"):
                    c[3] += 1

    # SMS replies / STOP: inbound within 24h after the contact's latest campaign text; counted on that text's day
    for _id, contact, when, direction, status, key, stop in msgs["SMS"]:
        if direction != "inbound":
            continue
        prior = [(d, k) for d, k, ch, right in sends_by_contact.get(contact, [])
                 if ch == "SMS" and right and d <= when and ts(when) - ts(d) <= timedelta(hours=24)]
        if prior:
            d, k = max(prior)
            if pt_day(d) >= cutoff:
                fresh[k][pt_day(d)][4 if stop else 5] += 1

    # Purchase credit: each first ticket purchase goes to the last Promote email/text within the window before it
    credit = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0.0]))   # key -> purchase day -> [n, $]
    for c, o in first_buy.items():
        bday = pt_day(o["created"])
        if bday < cutoff:
            continue
        bt = o["created"]
        if incremental:   # quick mode: read just this buyer's messages from the window before the purchase
            frm = (ts(bt) - WINDOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            sends = []
            for ch in ("Email", "SMS"):
                for _id, contact, when, direction, status, key, stop in api.messages(ch, frm, matcher, contact=c):
                    if direction == "outbound" and key and when < bt:
                        lab = STEPS[key]["label"]
                        holder = is_holder(c, when)
                        sends.append((when, key, ch, (lab == "promote" and not holder) or (lab == "post_ticket" and holder)))
        else:
            sends = sends_by_contact.get(c, [])
        cands = [(d, k) for d, k, ch, right in sends
                 if right and d < bt and ts(bt) - ts(d) <= WINDOW and STEPS[k]["label"] == "promote"]
        if cands:
            k = max(cands)[1]
            credit[k][bday][0] += 1; credit[k][bday][1] += tick_amt(o)

    # ---- merge with baseline (older days kept from the previous data.json)
    base_days, base_credit = {}, {}
    if incremental:
        for m in prev["messages"]:
            if m["ch"] == "email":   # emails: new sends are added on top of everything counted before
                base_days[m["key"]] = {d: list(v) for d, v in m["days"].items()}
            else:                    # texts: days from the cutoff are re-counted from scratch
                base_days[m["key"]] = {d: v for d, v in m["days"].items() if d < cutoff}
            base_credit[m["key"]] = {d: v for d, v in m.get("credit", {}).items() if d < cutoff}

    messages = []
    for key, st in STEPS.items():
        dd = dict(base_days.get(key, {}))
        for d, v in fresh[key].items():
            if st["channel"] == "email" and d in dd:
                dd[d] = [a + b for a, b in zip(dd[d], v)]
            else:
                dd[d] = list(v)
        cr = dict(base_credit.get(key, {}))
        cr.update({d: [v[0], round(v[1], 2)] for d, v in credit[key].items()})
        dd = {d: dd[d] for d in sorted(dd)}
        sent = sum(v[0] for v in dd.values())
        wrong = sum(v[1] for v in dd.values())
        main_day = max(dd, key=lambda d: dd[d][0] + dd[d][1]) if dd else None
        m = {"id": mid(key), "key": key, "ch": st["channel"], "camp": st["label"], "text": st["text"], "steps": st["names"],
             "day": main_day, "sent": sent, "wrong_audience": wrong, "days": dd, "credit": cr,
             "tickets": sum(v[0] for v in cr.values()), "ticket_revenue": round(sum(v[1] for v in cr.values()), 2), "no_links": st["no_links"]}
        if st["channel"] == "email":
            s = collections.Counter()
            for wid, sid in st["steps"]:
                s.update(stats.get(sid, {}))
                if sid not in stats:
                    FLAGS.append(f"Email step missing stats (re-read step IDs): {st['text'][:50]}")
            m.update(ghl_sent=s["sent"], delivered=s["delivered"], opened=s["opened"], clicked=s["clicked"],
                     unsub=s["unsubscribed"], bounced=s["permanentFail"], complaints=s["complained"])
            # GHL's own count is the source of truth for sends; the export can miss some (e.g. an older subject line)
            if s["sent"] - wrong > sent:
                if s["sent"] - wrong - sent > 0.05 * s["sent"]:
                    m["flag"] = "Check subject"
                    FLAGS.append(f"Email matched only {sent + wrong:,} of {s['sent']:,} GHL sends (subject may have changed): {st['text'][:50]}")
                m["sent"] = s["sent"] - wrong
            m["share_main"] = round((dd[main_day][0] / sent), 3) if main_day and sent else None
        else:
            m.update(delivered=sum(v[2] for v in dd.values()), failed=sum(v[3] for v in dd.values()),
                     optouts=sum(v[4] for v in dd.values()), replies=sum(v[5] for v in dd.values()))
        messages.append(m)

    # ---- campaign totals: to date + any day range (same rules the page uses)
    def totals(camp, ch, frm=None, to=None):
        t = collections.Counter()
        for m in messages:
            if m["camp"] != camp or m["ch"] != ch:
                continue
            if frm is None:                       # campaign to date
                in_r = m["sent"]; whole = True
            else:
                in_r = sum(v[0] for d, v in m["days"].items() if frm <= d <= to)
                tot = sum(v[0] for v in m["days"].values())
                whole = bool(tot) and in_r / tot >= SR["email_whole_send_share"]
            if not in_r:
                continue
            t["sent"] += in_r
            if ch == "email":
                t["emails"] += 1
                if whole:   # GHL gives opens/clicks/unsubs/bounces per email, not per day
                    t["whole"] += 1
                    t["rated"] += in_r
                    for k in ("delivered", "opened", "clicked", "unsub", "bounced", "ghl_sent"):
                        t[k] += m[k]
            else:
                for d, v in m["days"].items():
                    if frm is None or frm <= d <= to:
                        t["delivered"] += v[2]; t["failed"] += v[3]; t["optouts"] += v[4]
        return t

    T = {c: {ch: totals(c, ch) for ch in ("email", "sms")} for c in ("promote", "post_ticket")}
    Y = {c: {ch: totals(c, ch, yday, yday) for ch in ("email", "sms")} for c in ("promote", "post_ticket")}

    # ---- headline numbers
    n_paid, n_comps = len(first_buy), len(comps_only)
    n_holders = n_paid + n_comps
    revenue = sum(tick_amt(o) for o in ticket_orders)          # ticket line items only
    bb["people"] = len(bb_people)
    total_sales = revenue + bb["revenue"]
    credited_n = sum(m["tickets"] for m in messages)
    credited_rev = sum(m["ticket_revenue"] for m in messages)
    new_y = days[yday]["tk"]
    event = Date.fromisoformat(CFG["event_start"])
    days_to_go = max((event - today).days, 0)
    pp_n = len(pp_first)
    pp_cfg = UPS["power_plan"]
    shown_at = now.astimezone(SHOW_TZ)
    as_of = f"{shown_at.strftime('%b')} {shown_at.day}, {shown_at.strftime('%-I:%M%p').lower()} ET"
    sales_line = f"{money(total_sales)} total sales ({money(revenue)} tickets + {money(bb['revenue'])} Business Bible)"
    pp_rate = 100 * pp_n / n_holders if n_holders else 0
    bb_rate = 100 * bb["people"] / n_paid if n_paid else 0     # people, not sales

    # ---- yesterday + summary picks: set by the first run after midnight Pacific (the 7am ET run), kept by later runs.
    # Numbers in the summary and report are always filled from this run, so every number on the page agrees.
    frozen = prev.get("frozen") if prev else None
    keep = bool(frozen and frozen.get("yesterday") == yday and frozen.get("picks") and not os.environ.get("REBUILD_SUMMARY"))
    Yd = frozen["Y"] if keep else {c: {ch: dict(Y[c][ch]) for ch in Y[c]} for c in Y}

    wr = SR["win"]
    avg_click = {c: pct(T[c]["email"]["clicked"], T[c]["email"]["delivered"]) for c in T}
    msg_by_key = {m["key"]: m for m in messages}

    def pick_summary():
        rules = {}
        cands = []
        for m in messages:
            if m["ch"] != "email" or m["day"] != yday or m["sent"] < wr["min_sends"] or not m["delivered"] or m["no_links"]:
                continue
            if (m["share_main"] or 0) < SR["email_whole_send_share"]:
                continue
            cr = 100 * m["clicked"] / m["delivered"]
            a = avg_click[m["camp"]] or 0
            if a and cr >= wr["click_multiple"] * a:
                cands.append((cr / a, m["key"]))
        if cands:
            win = {"rule": 1, "key": max(cands)[1]}
            rules["win"] = f"Win: rule 1, a send from {short_day(yday)} clicked at {wr['click_multiple']}x or more its campaign average."
        elif pp_n or bb["count"]:
            win = {"rule": 2, "which": "pp" if pp_rate >= bb_rate else "bb"}
            rules["win"] = (f"Win: rule 2, the upsell with the highest take rate (Power Plan {pp_rate:.1f}% vs Business Bible "
                            f"{bb_rate:.1f}%). Rule 1 didn't apply: no send from {short_day(yday)} clicked at {wr['click_multiple']}x its campaign average.")
        else:
            best = max((m for m in messages if m["ch"] == "email" and m["sent"] >= wr["min_sends"] and m["delivered"]),
                       key=lambda m: m["opened"] / m["delivered"], default=None)
            win = {"rule": 3, "key": best["key"]} if best else {"rule": 0}
            rules["win"] = "Win: rule 3, best open rate among sends with 100+ recipients." if best else "Win: no rule applied."
        over = [x for x in watch_checks() if x["v"] > x["lim"]]
        if over:
            w = max(over, key=lambda x: x["v"] / x["lim"])
            watch = {"camp": w["camp"], "name": w["name"]}
            rules["watch"] = (f"Watch: {w['cname']} {w['name']} {w['v']:.1f}% is the furthest past its red line ({w['lim']:g}%). Also over: "
                              + (", ".join(f"{x['cname']} {x['name']} {x['v']:.1f}%" for x in over if x is not w) or "nothing else") + ".")
        else:
            watch = None
            rules["watch"] = "Watch: no metric is past its red line."
        return {"win": win, "watch": watch}, rules

    def watch_checks():
        out = []
        for c, cname in (("promote", "Promote"), ("post_ticket", "Post-ticket")):
            e, s_ = T[c]["email"], T[c]["sms"]
            if e["delivered"]:
                out.append(dict(camp=c, cname=cname, name="email unsubscribes", v=100 * e["unsub"] / e["delivered"], lim=TH["email_unsub_pct"], n=e["unsub"], what="emails unsubscribed", base=e["delivered"]))
            if e["ghl_sent"]:
                out.append(dict(camp=c, cname=cname, name="email bounces", v=100 * e["bounced"] / e["ghl_sent"], lim=TH["email_bounce_pct"], n=e["bounced"], what="emails bounced", base=e["ghl_sent"]))
            if s_["delivered"]:
                out.append(dict(camp=c, cname=cname, name="text opt-outs", v=100 * s_["optouts"] / s_["delivered"], lim=TH["sms_optout_pct"], n=s_["optouts"], what="delivered texts got a STOP reply", base=s_["delivered"]))
            if s_["sent"]:
                out.append(dict(camp=c, cname=cname, name="text failures", v=100 * s_["failed"] / s_["sent"], lim=TH["sms_failed_pct"], n=s_["failed"], what="texts failed", base=s_["sent"]))
        return out

    if keep:
        picks = frozen["picks"]
        rules_used = {k: v + " (picked at the first run today)" for k, v in frozen["rules"].items()}
    else:
        picks, rules_used = pick_summary()
        frozen = {"yesterday": yday, "as_of": as_of, "Y": Yd, "picks": picks, "rules": rules_used}

    hr = SR["headline"]
    prior = [(today - timedelta(days=i)).isoformat() for i in range(2, 2 + hr["compare_days"])]
    avg = sum(days[d]["tk"] for d in prior) / hr["compare_days"]
    tol = hr["in_line_tolerance_pct"] / 100
    word = ("above" if new_y > 0 else "in line") if avg == 0 else \
        "above" if new_y > avg * (1 + tol) else "below" if new_y < avg * (1 - tol) else "in line"
    tickets_word = f"{new_y} new ticket{'s' if new_y != 1 else ''} yesterday"
    headline = {"big": tickets_word,
                "sub": f"{n_holders} ticket holders · {sales_line} · {days_to_go} days to go",
                "cmp": f"vs {hr['compare_days']}-day average of {avg:.1f}/day: {word}",
                "line": f"{tickets_word} ({n_holders} total, {days_to_go} days to go)"}
    rules_used["headline"] = (f"Headline: {new_y} new paid tickets on {short_day(yday)} vs {avg:.1f}/day over the "
                              f"{hr['compare_days']} days before it ({word}; 'in line' = within {hr['in_line_tolerance_pct']}%).")

    wp = picks["win"]
    billing = short_day(pp_cfg["billing_start"])
    if wp["rule"] == 1 and wp["key"] in msg_by_key:
        m = msg_by_key[wp["key"]]
        cr = 100 * m["clicked"] / m["delivered"] if m["delivered"] else 0
        a = avg_click[m["camp"]] or 0
        mult = cr / a if a else 0
        win = {"big": f"{mult:.1f}x the usual click rate",
               "sub": f"\u201c{m['text']}\u201d got {cr:.1f}% clicks ({fmt(m['clicked'])} of {fmt(m['delivered'])} delivered) vs the {a:.1f}% campaign average.",
               "line": f"\u201c{m['text']}\u201d clicked at {cr:.1f}%, {mult:.1f}x the campaign average"}
    elif wp["rule"] == 2 and wp["which"] == "pp":
        win = {"big": f"{fraction_word(pp_rate)} of ticket holders signed up for the app",
               "sub": f"{pp_n} of {n_holders} ({pp_rate:.1f}%) signed up for the Power Plan. It's free until {billing}, then ${pp_cfg['price_per_month']}/month: {money(pp_n * pp_cfg['price_per_month'])}/month if they all stay.",
               "line": f"{pp_n} of {n_holders} ticket holders ({pp_rate:.1f}%) signed up for the Warrior App (free until {billing})"}
    elif wp["rule"] == 2:
        win = {"big": f"{fraction_word(bb_rate)} of paid buyers added the Business Bible",
               "sub": f"{bb['people']} of {n_paid} paid buyers ({bb_rate:.1f}%) · {bb['count']} sales · {money(bb['revenue'])}.",
               "line": f"{bb['people']} of {n_paid} paid buyers ({bb_rate:.1f}%) added the Business Bible"}
    elif wp["rule"] == 3 and wp["key"] in msg_by_key:
        m = msg_by_key[wp["key"]]
        o = 100 * m["opened"] / m["delivered"] if m["delivered"] else 0
        win = {"big": f"Best open rate: {o:.1f}%", "sub": f"\u201c{m['text']}\u201d · {fmt(m['opened'])} of {fmt(m['delivered'])} opened.",
               "line": f"best open rate {o:.1f}% on \u201c{m['text']}\u201d"}
    else:
        win = {"big": "No standout yet", "sub": "Nothing met a win rule today.", "line": "no standout yet"}

    wpk = picks["watch"]
    w = next((x for x in watch_checks() if wpk and x["camp"] == wpk["camp"] and x["name"] == wpk["name"]), None)
    if w:
        extra = ""
        if w["name"] == "text failures":
            ys = Yd[w["camp"]]["sms"]
            if ys.get("sent"):
                extra = f" Yesterday: {100 * ys['failed'] / ys['sent']:.1f}%."
        watch = {"big": f"{w['cname']} {w['name']}: {w['v']:.1f}%",
                 "sub": f"Above the {w['lim']:g}% limit: {fmt(w['n'])} of {fmt(w['base'])} {w['what']} to date.{extra}",
                 "line": f"{w['cname'].lower()} {w['name']} {w['v']:.1f}% to date ({fmt(w['n'])} of {fmt(w['base'])} {w['what']}), above {w['lim']:g}%"}
    else:
        watch = {"big": "All clear", "sub": "Nothing needs attention today.", "line": "Nothing needs attention today."}

    # ---- report text: rebuilt every run (report.txt matches "Last updated"); yesterday lines stay from the 7am run
    def e_line(t, click=True):
        if not t.get("sent"):
            return "none sent"
        parts = [f"{fmt(t['sent'])} sent"]
        if t.get("rated"):
            parts.append(f"{pct(t['opened'], t['delivered'])}% open")
            if click:
                parts.append(f"{pct(t['clicked'], t['delivered'])}% click")
        return " · ".join(parts)

    def s_line(t):
        if not t.get("sent"):
            return "none sent"
        return f"{fmt(t['sent'])} sent · {pct(t['delivered'], t['sent'])}% delivered"

    report = "\n".join([
        f"WarriorCon 6 — numbers as of {as_of}",
        "",
        "SUMMARY",
        f"• {headline['line']}",
        f"• Win: {win['line']}",
        f"• Watch: {watch['line']}",
        "",
        f"TICKET HOLDERS: {n_holders} ({n_paid} paid + {n_comps} comps) · {new_y} new yesterday",
        sales_line,
        f"{credited_n} of {n_paid} tickets were bought within {CFG['attribution_window_hours']} hrs of an email/text",
        "",
        "PROMOTE (non-ticket holders)",
        f"Yesterday — Email: {e_line(Yd['promote']['email'])}",
        f"Yesterday — SMS: {s_line(Yd['promote']['sms'])}",
        f"To date — Email: {e_line(T['promote']['email'])}",
        f"To date — SMS: {s_line(T['promote']['sms'])}",
        "",
        "POST-TICKET SEDUCTION (ticket holders)",
        f"Yesterday — Email: {e_line(Yd['post_ticket']['email'], click=False)}",
        f"Yesterday — SMS: {s_line(Yd['post_ticket']['sms'])}",
        f"To date — Email: {e_line(T['post_ticket']['email'], click=False)}",
        f"To date — SMS: {s_line(T['post_ticket']['sms'])}",
        "",
        "UPSELLS",
        f"Warrior App (Power Plan): {pp_n} · {pp_rate:.1f}% of ticket holders",
        f"Business Bible: {bb['count']} sales · {money(bb['revenue'])} · bought by {bb['people']} of {n_paid} paid buyers ({bb_rate:.1f}%)",
        "(Texts have no open rate.)",
    ])

    # ---- daily series
    day_list = []
    d = Date.fromisoformat(CFG["campaign_start"])
    while d <= today:
        x = days.get(d.isoformat(), {"tk": 0, "tkr": 0, "pp": 0, "bb": 0, "bbr": 0})
        day_list.append({"d": d.isoformat(), "tk": x["tk"], "tkr": round(x["tkr"], 2), "pp": x["pp"], "bb": x["bb"], "bbr": round(x["bbr"], 2)})
        d += timedelta(days=1)

    # Fixed GHL links (from config.json; never created or changed by this script)
    GL = CFG.get("ghl_links", {})
    names = {w["id"]: w["name"].split(" - ")[0] + " " + ("Emails" if w["channel"] == "email" else "Texts") for w in CFG["workflows"]}
    ghl_links = {}
    for camp in ("promote", "post_ticket"):
        g = GL.get(camp, {})
        wl = lambda ids: [{"label": names.get(i, "Workflow"), "url": f"{GL['base']}/automation/workflow/{i}"} for i in ids]
        ghl_links[camp] = {"email": wl(g.get("email_workflows", [])), "sms": wl(g.get("sms_workflows", [])),
                           "optout": [{"label": "Smart List", "url": g["sms_optout_smart_list"]}] if g.get("sms_optout_smart_list") else []}
    linked = {i for camp in ("promote", "post_ticket") for k in ("email_workflows", "sms_workflows") for i in GL.get(camp, {}).get(k, [])}
    for w in CFG["workflows"]:
        if w["id"] not in linked:
            FLAGS.append(f"No GHL link set up yet for {w['name']} (add it to ghl_links in config.json by hand)")

    # Today so far (Pacific day), as of this run
    t_day = today.isoformat()
    today_so_far = {"date": t_day, "tickets": days[t_day]["tk"],
                    "emails": sum(m["days"].get(t_day, [0])[0] for m in messages if m["ch"] == "email"),
                    "texts": sum(m["days"].get(t_day, [0])[0] for m in messages if m["ch"] == "sms")}

    data = {
        "schema": 2,
        "email_watermark": email_watermark,
        "update_times_et": CFG["update_times_et"],
        "today_so_far": today_so_far,
        "ghl_links": ghl_links,
        "yesterday_totals": Yd,
        "generated_at": now.isoformat(timespec="minutes"), "as_of": as_of,
        "today": today.isoformat(), "yesterday": yday, "campaign_start": CFG["campaign_start"],
        "event_start": CFG["event_start"], "days_to_go": days_to_go,
        "attribution_window_hours": CFG["attribution_window_hours"],
        "thresholds": TH, "email_whole_send_share": SR["email_whole_send_share"],
        "holders": {"total": n_holders, "paid": n_paid, "comps": n_comps, "new_yesterday": new_y},
        "sales": {"tickets": n_paid, "revenue": round(revenue, 2), "total": round(total_sales, 2),
                  "credited": credited_n, "credited_revenue": round(credited_rev, 2)},
        "upsells": {"power_plan": {"count": pp_n, "price_per_month": pp_cfg["price_per_month"], "billing_start": pp_cfg["billing_start"]},
                    "business_bible": {"count": bb["count"], "people": bb["people"], "bump": bb["bump"], "standalone": bb["standalone"],
                                       "revenue": round(bb["revenue"], 2)}},
        "todate": {c: {ch: dict(T[c][ch]) for ch in T[c]} for c in T},
        "summary": {"headline": headline, "win": win, "watch": watch},
        "report": report, "report_as_of": as_of,
        "frozen": frozen,
        "days": day_list,
        "messages": sorted(messages, key=lambda m: (m["day"] or "9", m["ch"])),
        "flags": sorted(set(FLAGS)),
    }
    summary = {"date": today.isoformat(), "as_of": as_of, "yesterday": yday, "ticket_holders": data["holders"],
               "summary": {k: v["line"] for k, v in data["summary"].items()},
               "promote": {"yesterday": Yd["promote"], "to_date": data["todate"]["promote"]},
               "post_ticket": {"yesterday": Yd["post_ticket"], "to_date": data["todate"]["post_ticket"]},
               "upsells": data["upsells"]}

    # Safety check: sends, deliveries and failures only ever go up. If a total drops compared with the last good
    # data (e.g. GHL returned an empty export), stop without writing so the page keeps the last good numbers.
    if prev and prev.get("todate"):
        for c in ("promote", "post_ticket"):
            for ch, keys in (("email", ("sent",)), ("sms", ("sent", "delivered", "failed"))):
                for k in keys:
                    old = (prev["todate"].get(c, {}).get(ch, {}) or {}).get(k, 0) or 0
                    new = T[c][ch].get(k, 0) or 0
                    if new < old - max(5, 0.002 * old):
                        raise SystemExit(f"Safety check failed: {c} {ch} {k} dropped from {old:,} to {new:,}. "
                                         "Nothing written; the page keeps the last good numbers.")

    # write to temp files first, then swap in, so a failed run never leaves half-written data
    for name, content in (("data.json", json.dumps(data, indent=1, ensure_ascii=False)),
                          ("summary.json", json.dumps(summary, indent=1, ensure_ascii=False)),
                          ("report.txt", report + "\n")):
        tmp = os.path.join(ROOT, name + ".tmp")
        open(tmp, "w", encoding="utf-8").write(content)
        os.replace(tmp, os.path.join(ROOT, name))

    log(f"Wrote data.json, summary.json, report.txt. Ticket holders {n_holders}.")
    log("Which rule picked each summary line:")
    for k in ("headline", "win", "watch"):
        log("  " + rules_used[k])
    if pp_non_holders:
        log(f"Power Plan: {len(pp_non_holders)} sign-up(s) are not ticket holders and were left out.")
    log(f"Business Bible: {bb['count']} paid ({bb['bump']} at ticket checkout, {bb['standalone']} on their own).")
    for f in data["flags"]:
        log("FLAG:", f)


def fraction_word(p):
    for target, word in ((25, "A quarter"), (33.3, "A third"), (50, "Half"), (66.7, "Two-thirds"), (75, "Three-quarters")):
        if abs(p - target) <= 3:
            return word
    return f"{p:.0f}%"


if __name__ == "__main__":
    main()
