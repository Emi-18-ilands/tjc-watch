#!/usr/bin/env python3
"""Watch r/automation for people describing a real problem they already have.

Direct reddit.com blocks this sandbox's IP (HTTP 403, datacenter range), and so
does r.jina.ai. The public Reddit archive at arctic-shift.photon-reddit.com is
keyless and reachable, so that is the read path (read-only; no posting, no
account).

Runs on a cron from GitHub Actions, so it keeps looking while the agent sleeps.
Writes:
  status/ra_latest.json     current request-like posts (title, body, engagement)
  status/ra_seen.json       ids already reported, so alerts are once-only
  log/ra-YYYY-MM.jsonl      one line per run (a time series, not just a headline)
Pushes one ntfy.sh notification per run when NEW request-like posts appear.
"""
import json, os, re, sys, urllib.request, datetime, pathlib

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
UA = {"User-Agent": "ra-watch/1.0 (github actions)"}
API = "https://arctic-shift.photon-reddit.com/api/posts/search"
SUBREDDIT = "automation"

# A request is someone's own problem, phrased as a question or a plea:
# not a vendor's how-to post, not a launch announcement.
TITLE_REQUEST = re.compile(
    r"(how (do|to|would|can|should)|any ?one|any ?body|recommend|looking for|"
    r"what (do|should|tool|am|are) |which |help|advice|suggest|is it worth|"
    r"does anyone|best way|instead of|trying to|struggl)", re.I)
BODY_REQUEST = re.compile(
    r"(i'?m trying to|i am trying to|i need|i'?m looking|i keep|"
    r"we hit this|we'?re trying|anyone know|does anyone|is there a way|"
    r"how do i|what'?s the best)", re.I)
# Titles that are clearly a vendor's own content, not a request.
VENDOR_NOISE = re.compile(r"(made \$|here'?s how|my (guide|course|tool)|launch|i built|we built)", re.I)


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def push(topic, title, msg, url, priority="default"):
    if not topic:
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}", data=msg.encode(), method="POST",
        headers={"Title": title, "Priority": priority, "Tags": "books", "Click": url, **UA})
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        print("ntfy failed:", e, file=sys.stderr)


def is_request(p):
    t = p.get("title") or ""
    b = (p.get("selftext") or "").strip()
    if VENDOR_NOISE.search(t):
        return False
    return bool(TITLE_REQUEST.search(t) or (len(b) > 60 and BODY_REQUEST.search(b)))


def main():
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out = {"checked_at": now, "subreddit": SUBREDDIT, "ok": False, "requests": []}
    try:
        d = get(f"{API}?subreddit={SUBREDDIT}&limit=100&sort=desc")
        posts = d.get("data", [])
        reqs = []
        for p in posts:
            if not is_request(p):
                continue
            reqs.append({
                "id": p.get("id"),
                "created_utc": p.get("created_utc"),
                "title": p.get("title"),
                "score": p.get("score"),
                "num_comments": p.get("num_comments"),
                "author": p.get("author"),
                "url": "https://www.reddit.com" + (p.get("permalink") or ""),
                "body": re.sub(r"\s+", " ", (p.get("selftext") or ""))[:600],
            })
        out["ok"] = True
        out["requests"] = reqs
        out["scanned"] = len(posts)
    except Exception as e:
        out["error"] = str(e)

    pathlib.Path("status").mkdir(exist_ok=True)
    pathlib.Path("log").mkdir(exist_ok=True)
    seen_path = pathlib.Path("status/ra_seen.json")
    seen = set()
    if seen_path.exists():
        try:
            seen = set(json.loads(seen_path.read_text()))
        except Exception:
            pass

    for r in out["requests"]:
        r["new"] = r["id"] not in seen

    pathlib.Path("status/ra_latest.json").write_text(json.dumps(out, indent=2) + "\n")
    with open(f"log/ra-{now[:7]}.jsonl", "a") as f:
        f.write(json.dumps(out, separators=(",", ":")) + "\n")

    fresh = [r for r in out["requests"] if r["new"]]
    if fresh:
        seen.update(r["id"] for r in fresh)
        seen_path.write_text(json.dumps(sorted(seen)) + "\n")

    if fresh:
        lines = [f"- {r['title'][:90]} ({r['num_comments']}c)" for r in fresh[:6]]
        top = fresh[0]
        push(NTFY_TOPIC, f"r/automation: {len(fresh)} new request(s)",
             "\n".join(lines), top["url"])

    print(json.dumps({"checked_at": now, "scanned": out.get("scanned"),
                      "requests": len(out["requests"]), "new": len(fresh)}))


if __name__ == "__main__":
    main()
