#!/usr/bin/env python3
"""Watch public boards for open, fundable work. Runs on a schedule from GitHub
Actions, so it keeps looking while the agent is asleep.

Writes:
  status/latest.json   current snapshot (cheap to read from anywhere)
  log/YYYY-MM.jsonl    one line per run (a time series, not just a headline)
Pushes an ntfy.sh notification when a NEW open bounty appears.
"""
import json, os, sys, urllib.request, datetime, pathlib

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
UA = {"User-Agent": "tjc-watch/1.0 (github actions)"}

def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def push(topic, title, msg, url, priority="high"):
    if not topic:
        return
    data = msg.encode()
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}", data=data, method="POST",
        headers={"Title": title, "Priority": priority, "Tags": "bell", "Click": url, **UA})
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        print("ntfy failed:", e, file=sys.stderr)

def main():
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out = {"checked_at": now, "sources": {}}

    # TheJobCafe: keyless public board + public payout proof.
    # status=open is the only thing worth alerting on; status=all is context.
    try:
        b = get("https://thejobcafe.com/api/public/bounties?status=open&limit=100")
        open_bs = []
        for x in b.get("bounties", []):
            open_bs.append({
                "slug": x.get("slug"), "title": x.get("title"),
                "price_cents": x.get("price_cents"),
                "escrowed": (x.get("funding") or {}).get("escrowed"),
                "url": f"https://thejobcafe.com/bounty/{x.get('slug')}",
                "status": x.get("status"),
            })
        out["sources"]["thejobcafe"] = {
            "ok": True, "open": open_bs, "open_count": len(open_bs),
            "count_field": b.get("count"),
        }
    except Exception as e:
        out["sources"]["thejobcafe"] = {"ok": False, "error": str(e)}

    try:
        a = get("https://thejobcafe.com/api/public/bounties?status=all&limit=100")
        out["sources"]["thejobcafe_all_count"] = {"ok": True, "count": a.get("count")}
    except Exception as e:
        out["sources"]["thejobcafe_all_count"] = {"ok": False, "error": str(e)}

    try:
        p = get("https://thejobcafe.com/api/public/payouts")
        out["sources"]["thejobcafe_payouts"] = {
            "ok": True, "total_paid_cents": p.get("total_paid_cents"),
            "paid_count": p.get("paid_count"),
        }
    except Exception as e:
        out["sources"]["thejobcafe_payouts"] = {"ok": False, "error": str(e)}

    pathlib.Path("status").mkdir(exist_ok=True)
    pathlib.Path("log").mkdir(exist_ok=True)
    latest = pathlib.Path("status/latest.json")
    prev_slugs = set()
    if latest.exists():
        try:
            prev = json.loads(latest.read_text())
            prev_slugs = {x["slug"] for x in prev["sources"].get("thejobcafe", {}).get("open", [])}
        except Exception:
            pass
    latest.write_text(json.dumps(out, indent=2) + "\n")

    with open(f"log/{now[:7]}.jsonl", "a") as f:
        f.write(json.dumps(out, separators=(",", ":")) + "\n")

    new = [x for x in out["sources"].get("thejobcafe", {}).get("open", []) if x["slug"] not in prev_slugs]
    for x in new:
        usd = (x["price_cents"] or 0) / 100
        push(NTFY_TOPIC, f"TJC: new bounty ${usd:.2f}", x["title"], x["url"])
        print("NEW:", x["slug"], x["title"], usd)

    print(json.dumps({"checked_at": now,
                      "tjc_open": out["sources"].get("thejobcafe", {}).get("open_count"),
                      "new": len(new)}))

if __name__ == "__main__":
    main()
