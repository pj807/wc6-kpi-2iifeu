"""Privacy scan: blocks a push if any file about to be committed contains an email, phone number,
GHL contact ID or token. Usage: python3 scripts/privacy_scan.py [files...]  (default: files staged in git)
Exit code 1 = something found (push must stop)."""
import re, subprocess, sys

PATTERNS = {
    "email address": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone number": re.compile(r"(?<![\w.])\+?1?[\s.-]?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?![\w])|\+\d{10,15}\b"),
    "GHL token": re.compile(r"\bpit-[0-9a-f]{8}-|\beyJ[A-Za-z0-9_-]{20,}\.|\bBearer\s+[A-Za-z0-9._-]{20,}", re.I),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "contact ID field": re.compile(r'"(contactId|contact_id|phone|email|firstName|lastName|fullName)"\s*:\s*"', re.I),
}
# Strings that look like a match but are safe to publish
ALLOW = {"noreply@anthropic.com", "41898282+github-actions[bot]@users.noreply.github.com"}


def staged():
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                         capture_output=True, text=True).stdout
    return [f for f in out.splitlines() if f]


def main():
    files = sys.argv[1:] or staged()
    hits = []
    for f in files:
        if f.startswith("data/raw/") or f.endswith(".env"):
            hits.append((f, 0, "raw/secret file staged", f))
            continue
        try:
            lines = open(f, encoding="utf-8", errors="ignore").read().splitlines()
        except (IsADirectoryError, FileNotFoundError):
            continue
        for n, line in enumerate(lines, 1):
            for label, rx in PATTERNS.items():
                for m in rx.finditer(line):
                    if m.group(0) not in ALLOW:
                        hits.append((f, n, label, m.group(0)[:6] + "…"))
    if hits:
        print("PRIVACY SCAN FAILED. Nothing was pushed. Found:")
        for f, n, label, snip in hits:
            print(f"  {f}:{n}  {label}  ({snip})")
        sys.exit(1)
    print(f"Privacy scan passed ({len(files)} files).")


if __name__ == "__main__":
    main()
