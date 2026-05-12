# Day 1 Execution Log

## Built

- Working CLI for `scan-issue`, `scan-pr`, `scan-repo`, and `collect-candidates`.
- Seed database of 50 live bounty-like GitHub candidates in `data/candidates.json` and `data/candidates.csv`.
- Buyer-facing offer page in `OFFER.md`.
- Report template in `templates/preflight-report.md`.

## Sample Reports

- `reports/osm-ng-90.md`: issue preflight where open PR collisions make a fresh attempt poor expected value.
- `reports/dasharo-602.md`: issue preflight where active competing PRs suggest skip/rescue instead of direct attempt.
- `reports/tailcall-1.md`: Algora payout path is clear, but active/stale PR collisions make it a rescue/watch candidate.
- `reports/tailcall-pr-6.md`: PR rescue scan for a stale, merge-clean PR.

## Initial Positioning

Use this message for low-friction outreach:

> I built a small Bounty Preflight report that checks whether a GitHub bounty is worth attempting before someone spends hours on it. It checks payout path, PR collisions, attempts, assignment gates, and stale rescue opportunities. I can run the first few manually for $10 each and send Markdown/JSON output.

## Next Manual Sales Targets

- Bounty hunters who repeatedly comment on crowded Algora issues.
- Maintainers with many open AI bounty PRs.
- Developers with stale/failing bounty PRs.
- Agent builders who need a task-selection feed.

## Avoid

- Public spam comments.
- Private payout details in issue threads.
- Opire-only bounties until account setup is confirmed.
- Core-team-only Ubiquity tasks.
