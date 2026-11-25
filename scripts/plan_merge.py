"""Merge a fresh read-only GHL read of some WC6 workflows into plan.json (and config.json for a new workflow).

Usage (your Mac, after scripts/plan_read_chrome.js saved the read to data/raw/):
  python3 -I scripts/plan_merge.py data/raw/<read>.json                 # dry run: prints what would change
  python3 -I scripts/plan_merge.py data/raw/<read>.json --write         # updates plan.json
  python3 -I scripts/plan_merge.py data/raw/<read>.json --write --new <workflow id>=<promote|post_ticket|byb>:<short name>
      e.g. --new 1234...=post_ticket:"1.05 Emails"   (only after PJ confirmed the label in chat)

What it does, per workflow in the read:
- keeps planned steps that still exist (subject / SMS text and 'wait until' date refreshed from GHL),
- adds new email/SMS steps, drops steps deleted in GHL,
- stores the workflow's GHL version + last-updated time, so the daily run can tell when it was edited after this read,
- sets plan.json read_at to now.
Anything it can't place (an unusual wait type) is printed as CHECK BY HAND. It never talks to GHL.
"""
import json, os, re, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")


def clean_sms(body):
    t = re.sub(r"https?://\S+|\{\{[^}]*\}\}", "", body or "")
    t = re.sub(r"\s*(Reply|Text) STOP.*$", "", t, flags=re.I | re.S)
    return re.sub(r"\s+", " ", t).strip()[:90]


def when_from_wait(w, has_prev):
    if w is None:
        return {"type": "with_previous"} if has_prev else {"type": "on_enrollment"}, None
    a = w["attributes"]
    if a.get("type") == "specific_date":
        h = int(a.get("specificTimeHour") or 0) % 12 + (12 if a.get("specificTimePeriod") == "PM" else 0)
        return {"type": "date", "date": a["specificDate"], "time_et": f"{h:02d}:{int(a.get('specificTimeMinute') or 0):02d}",
                "plus_hours": int(a.get("specificDateOffsetDays") or 0) * 24 + int(a.get("specificDateOffsetHours") or 0)}, None
    sa = a.get("startAfter") or {}
    if a.get("type") == "time" and str(sa.get("type", "")).startswith("hour"):
        return {"type": "after_previous", "hours": sa.get("value")}, None
    if a.get("type") == "time" and str(sa.get("type", "")).startswith("day"):
        return {"type": "after_previous", "hours": 24 * (sa.get("value") or 0)}, None
    if a.get("type") == "time" and str(sa.get("type", "")).startswith("minute"):
        return {"type": "after_previous", "hours": round((sa.get("value") or 0) / 60, 2)}, None
    return {"type": "after_previous", "hours": 24}, f"wait '{a.get('name')}' (type {a.get('type')}) not understood; assumed 24 hours"


def parse(wf_read):
    """Email/SMS steps in send order. GHL links each action to the one before it (parentKey); 'parent' is the
    if/else branch it sits in. Each message takes the nearest wait before it, back to the previous message."""
    T = wf_read["templates"]
    by_id = {t["id"]: t for t in T}

    def chain(t):   # ancestors, nearest first
        out, seen = [], set()
        p = by_id.get(t.get("parentKey"))
        while p and p["id"] not in seen:
            seen.add(p["id"]); out.append(p)
            p = by_id.get(p.get("parentKey"))
        return out

    msgs = [t for t in T if t["type"] in ("email", "sms")]
    msgs.sort(key=lambda t: len(chain(t)))
    out = []
    for t in msgs:
        wait, has_prev = None, False
        for a in chain(t):
            if a["type"] in ("email", "sms"):
                has_prev = True
                break
            if a["type"] == "wait" and wait is None:
                wait = a
        when, warn = when_from_wait(wait, has_prev)
        br = by_id.get(t.get("parent"))
        a = t.get("attributes") or {}
        out.append({"step_id": t["id"], "name": t.get("name") or "", "channel": t["type"],
                    "branch": (br.get("name") if br else None) or "main",
                    "text": (a.get("subject") or "").strip() if t["type"] == "email" else clean_sms(a.get("body")),
                    "when": when, "warn": warn})
    return out


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    read = json.load(open(args[0], encoding="utf-8"))
    write = "--write" in args
    new = {}
    for i, a in enumerate(args):
        if a == "--new":
            wid, rest = args[i + 1].split("=", 1)
            label, short = rest.split(":", 1)
            assert label in ("promote", "post_ticket", "byb"), "label must be promote, post_ticket or byb"
            new[wid] = (label, short)
    plan = json.load(open(os.path.join(ROOT, "plan.json"), encoding="utf-8"))
    cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
    now = datetime.now(timezone.utc)
    changes = []
    for wid, w in read.items():
        pw = next((x for x in plan["workflows"] if x["id"] == wid), None)
        if pw is None:
            if wid not in new:
                print(f"SKIPPED {w['name']}: not in the plan. Ask PJ for its label (Promote, Post-ticket or Bring Your Brother), then pass --new.")
                continue
            label, short = new[wid]
            parsed = parse(w)
            channels = {s["channel"] for s in parsed}
            if len(channels) != 1:
                print(f"CHECK BY HAND {w['name']}: has both emails and texts; the plan expects one channel per workflow.")
                continue
            ch = channels.pop()
            pw = {"id": wid, "name": w["name"], "wf": short, "audience": label, "channel": ch}
            plan["workflows"].append(pw)
            if not any(x["id"] == wid for x in cfg["workflows"]):
                cfg["workflows"].append({"id": wid, "name": w["name"], "label": label, "channel": ch, "steps": []})
                key = "email_workflows" if ch == "email" else "sms_workflows"
                cfg["ghl_links"][label][key].append(wid)
            changes.append(f"NEW workflow {w['name']} labelled {label} ({short})")
        old = [s for s in plan["steps"] if s["workflow"] == wid]
        old_by_id = {s["step_id"]: s for s in old}
        parsed = parse(w)
        merged, num = [], 0
        for p in parsed:
            num += 1
            o = old_by_id.get(p["step_id"])
            if p["warn"]:
                print(f"CHECK BY HAND {w['name']} {p['name']}: {p['warn']}")
            if o:
                s = dict(o)
                if p["text"] and s["text"].strip() != p["text"].strip() and (p["channel"] == "email" or not p["text"].startswith(s["text"][:40])):
                    changes.append(f"{pw['wf']} {s['name']}: text '{s['text'][:50]}' -> '{p['text'][:50]}'")
                    s["text"] = p["text"]
                # keep hand-read timings the parser can't express: rolling sends, and "date + N hours" (a date wait
                # followed by a time wait, e.g. 0.1 Emails 16 behind the Nov 4 2027 wait)
                hand = s["when"]["type"] == "relative_to_purchase" or (s["when"]["type"] == "date" and s["when"].get("plus_hours")
                                                                        and p["when"]["type"] == "after_previous")
                if s["when"] != p["when"] and not hand:
                    changes.append(f"{pw['wf']} {s['name']}: time {s['when']} -> {p['when']}")
                    s["when"] = p["when"]
                if s["name"] != p["name"]:
                    s["name"] = p["name"]
            else:
                s = {"workflow": wid, "wf": pw["wf"], "audience": pw["audience"], "channel": pw["channel"], "num": 0,
                     "step_id": p["step_id"], "name": p["name"], "branch": p["branch"], "when": p["when"], "text": p["text"]}
                if p["channel"] == "sms":
                    m = re.search(r"wc-(?:day|pm|byb)\d+", p["name"])
                    if m:
                        s["link"] = m.group(0)
                changes.append(f"{pw['wf']} + {p['name']} · {p['text'][:60]} · {p['when']}")
            s["num"] = num
            merged.append(s)
        for s in old:
            if s["step_id"] not in {p["step_id"] for p in parsed}:
                changes.append(f"{pw['wf']} - {s['name']} (deleted in GHL)")
        if w["name"] != pw["name"]:
            changes.append(f"{pw['wf']}: renamed '{pw['name']}' -> '{w['name']}'")
            pw["name"] = w["name"]
            for c in cfg["workflows"]:
                if c["id"] == wid:
                    c["name"] = w["name"]
        pw["version"], pw["updated_at"] = w.get("version"), w.get("updatedAt")
        # keep the plan's step order: replace this workflow's steps in place
        first = next((i for i, s in enumerate(plan["steps"]) if s["workflow"] == wid), len(plan["steps"]))
        rest = [s for s in plan["steps"] if s["workflow"] != wid]
        plan["steps"] = rest[:first] + merged + rest[first:]
    plan["read_at"] = now.astimezone(ET).date().isoformat()
    plan["read_at_utc"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    names = ", ".join(x["wf"] for x in plan["workflows"] if x["id"] in read)
    print(f"{len(changes)} change(s):" if changes else "No step changes.")
    for c in changes:
        print("  " + c)
    if not write:
        print("Dry run. Add --write to save.")
        return
    plan.setdefault("_read_log", []).append(
        f"{now.astimezone(ET).strftime('%Y-%m-%d %-I:%M%p').lower()} ET re-read {names}: " + ("; ".join(changes)[:600] if changes else "no step changes"))
    json.dump(plan, open(os.path.join(ROOT, "plan.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump(cfg, open(os.path.join(ROOT, "config.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"Saved plan.json ({len(plan['steps'])} steps). Plan last read {plan['read_at_utc']}.")


if __name__ == "__main__":
    main()
