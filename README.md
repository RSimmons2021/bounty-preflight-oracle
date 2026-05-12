# Bounty Preflight Oracle

Tiny agent-callable reports for deciding whether a GitHub bounty is worth attempting.

The first product is intentionally manual: run a scan, send the Markdown report, and charge for the decision support. The same scoring output can later be wrapped in an HTTP/x402 endpoint.

## What It Produces

- Verdict: `attempt`, `watch`, or `skip`
- Score and reasons
- Payout path and payout friction
- Open PR collision check
- Assignment / gate warnings
- Estimated Codex hours
- Recommended next action

## Quick Start

```powershell
python -m bounty_oracle.cli scan-issue https://github.com/openstreetmap-ng/openstreetmap-ng/issues/90 --out reports/osm-ng-90.md --json-out reports/osm-ng-90.json
python -m bounty_oracle.cli collect-candidates --out data/candidates.json --csv data/candidates.csv --limit 50
python -m bounty_oracle.cli scan-repo openstreetmap-ng/openstreetmap-ng --out reports/openstreetmap-ng.md
```

The CLI uses the GitHub CLI (`gh`) for authenticated API calls.

## First Offer

I can run a Bounty Preflight report before you spend hours on a task:

- $10 for the first 5 reports
- $25 after that
- output includes a direct attempt/skip/watch recommendation and collision evidence

No private payout details are included in reports.

## Report Template

Each report answers:

1. Should an agent attempt this?
2. Is the payout path clear?
3. Are there competing PRs or stale attempts?
4. What is the implementation risk?
5. What is the fastest next action?
