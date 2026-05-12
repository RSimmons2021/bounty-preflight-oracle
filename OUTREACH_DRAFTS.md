# Outreach Drafts

Use these as private DMs, Discord posts where allowed, or replies only when the report is clearly relevant. Do not paste private payout details.

## 1. Bounty Hunter DM

Subject: quick preflight before you attempt crowded bounties

I built a small GitHub bounty preflight scanner that checks whether a bounty is worth attempting before spending hours on it.

It checks:
- payout path
- assignees and start gates
- open PR collisions
- stale/rescue opportunities
- attempt/comment crowding
- estimated Codex implementation time

Sample reports are here: https://gist.github.com/RSimmons2021/34632479c75f74dd6bddf2174b49dde9

I’m testing the first few manual reports at $10 each. Send me an issue URL and I’ll return Markdown + JSON with an `attempt / watch / skip` verdict.

## 2. Maintainer With Crowded Bounty Threads

Subject: free sample triage report for crowded bounty PRs

I noticed some bounty issues attract many overlapping AI PRs. I built a small report that summarizes collisions, stale PRs, payout friction, and the cleanest next action.

This is meant to reduce duplicate PR noise and help contributors avoid issues that are already saturated.

I can run one free sample against a crowded bounty issue if useful. Example output: https://gist.github.com/RSimmons2021/34632479c75f74dd6bddf2174b49dde9

## 3. Developer With Stale/Failing Bounty PR

Subject: PR rescue report for bounty submissions

I’m testing a PR-rescue scanner for bounty submissions. It checks stale status, merge state, failing checks, review state, and whether a minimal unblock patch is likely.

If you have a bounty PR that is stuck, I can run a rescue report and suggest the fastest unblock path. Intro price is $10; deeper patch review is $35.

Sample PR report: https://gist.github.com/RSimmons2021/34632479c75f74dd6bddf2174b49dde9

## 4. Agent Builder / Automation User

Subject: agent-ready bounty scoring feed

I’m turning public GitHub bounty data into an agent-ready scoring feed. It ranks issues by payout clarity, crowding, assignment gates, PR collisions, and likely Codex implementation time.

Current prototype:
- CLI: https://github.com/RSimmons2021/bounty-preflight-oracle
- samples: https://gist.github.com/RSimmons2021/34632479c75f74dd6bddf2174b49dde9

I can generate a daily 5-candidate digest manually while I test pricing.

## 5. Public Non-Spam Reply Template

Only use this when the thread already discusses duplicate PRs, stale attempts, or bounty confusion.

I ran a small preflight check on this bounty because there are multiple overlapping attempts. The useful signal: this looks better as a PR-rescue/maintainer-triage task than a fresh attempt, because there are already open PR collisions.

I can share the Markdown report if helpful. No payout details included.
