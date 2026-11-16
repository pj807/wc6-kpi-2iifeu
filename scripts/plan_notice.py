"""GitHub email notice for the plan check (runs in the GitHub Action after Publish; never fails the update).

- Plan out of date and no open notice: opens an issue "WC6 plan out of date" that mentions the owner, so GitHub emails them.
- Already open and the list changed: adds a comment (another email). Same list as last time: does nothing (no repeat
  emails 4 times a day).
- Plan up to date again: closes the open issue with a note.
Uses the gh CLI with the workflow's own GITHUB_TOKEN. Only workflow names go into the issue; no contact data.
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TITLE = "WC6 plan out of date"
OWNER = "pj807"


def gh(*a):
    r = subprocess.run(["gh", *a], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:300])
    return r.stdout


def main():
    pc = json.load(open(os.path.join(ROOT, "data.json"), encoding="utf-8")).get("plan_check") or {}
    run = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"
    open_issues = [i for i in json.loads(gh("issue", "list", "--state", "open", "--search", f'"{TITLE}" in:title',
                                            "--json", "number,title,body,comments") or "[]") if i["title"] == TITLE]
    issue = open_issues[0] if open_issues else None
    if not pc.get("stale"):
        if issue:
            gh("issue", "close", str(issue["number"]), "--comment",
               f"Plan re-read (last read {pc.get('read_label')}). The warning is cleared on the page. Run: {run}")
            print(f"Closed notice #{issue['number']}: plan is up to date.")
        else:
            print("Plan is up to date. No notice needed.")
        return
    lines = "\n".join(f"- {i['text']}" for i in pc["items"])
    sig = "<!-- sig:" + "|".join(sorted(i["text"] for i in pc["items"])) + " -->"
    body = (f"@{OWNER} the dashboard's **What's left.** counts may be too low until the plan is re-read.\n\n{lines}\n\n"
            f"Plan last read {pc.get('read_label')}. To update, use **⧉ Copy update command** on the page "
            f"(or double-click \"Update WC6 plan\" on the Mac desktop) and paste it into Claude Code.\n\nRun: {run}\n{sig}")
    if not issue:
        gh("issue", "create", "--title", TITLE, "--body", body)
        print("Opened a 'WC6 plan out of date' notice (GitHub emails the owner).")
        return
    seen = [issue.get("body") or ""] + [c.get("body") or "" for c in issue.get("comments") or []]
    if any(sig in s for s in seen):
        print(f"Notice #{issue['number']} already lists these changes. No new email.")
        return
    gh("issue", "comment", str(issue["number"]), "--body", body)
    print(f"Added the new changes to notice #{issue['number']} (GitHub emails the owner).")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:   # a notice problem must never fail the update
        print(f"::warning title=Plan notice not sent::{e}")
        sys.exit(0)
