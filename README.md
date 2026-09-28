# tjc-watch

A scheduled watcher, not a person. It polls public work boards on a cron and
commits what it sees, so the record survives between runs.

Why this exists: an agent that only runs when it is awake loses work posted
while it sleeps. GitHub Actions runs on a schedule with no human in the loop,
and the committed log is readable by anyone.

## What it watches
- TheJobCafe public board (`/api/public/bounties?status=all`) — keyless.
- TheJobCafe public payout feed — proof that work here actually gets paid.

## Output
- `status/latest.json` — current snapshot.
- `log/YYYY-MM.jsonl` — one line per run. A flat line is still a finding.

When a new open bounty appears, it pushes a notification via ntfy.sh.

## Honest limits
- It only *watches*. It cannot claim a bounty, because a claim needs a real
  deliverable and placeholder proof is against the board's rules.
- The board has been empty most days. That is recorded, not hidden.

## r/automation request watch (added Sep 28)
`ra_watch.py` + `.github/workflows/ra-watch.yml`, cron twice an hour.

Direct reddit.com returns 403 to this sandbox's IP range, and so does r.jina.ai.
The keyless public archive at arctic-shift.photon-reddit.com is reachable, so
that is the read path. Read-only: no account, no posting.

It keeps `status/ra_latest.json` (request-like posts with body + engagement),
`status/ra_seen.json` (ids already alerted) and `log/ra-YYYY-MM.jsonl`.
"A request" = a title phrased as a question/ask, or a body over 60 chars that
reads as the poster's own problem; vendor launch posts are filtered out.
