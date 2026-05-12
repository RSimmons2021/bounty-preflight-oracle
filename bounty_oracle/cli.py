from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


GH = r"C:\Program Files\GitHub CLI\gh.exe"


BOUNTY_QUERIES = [
    '"/bounty" is:issue is:open archived:false',
    '"💎 Bounty" is:issue is:open archived:false',
    '"Price:" "USD" is:issue is:open archived:false',
    '"bounty:$" is:issue is:open archived:false',
    'label:bounty is:issue is:open archived:false',
    '"Bounty:" is:issue is:open archived:false',
]


ATTEMPT_RE = re.compile(
    r"(/attempt|/start|/claim|claiming|working on|i can take|i(?:'|’)m working|pr submitted|pull request|opened pr)",
    re.IGNORECASE,
)
PR_RE = re.compile(r"github\.com/[^/\s]+/[^/\s]+/pull/\d+|#\d+")
MONEY_RE = re.compile(r"(\$\s?\d+(?:\.\d+)?|\b\d+(?:\.\d+)?\s?(?:USD|USDC|USD1|sats|RTC|XMR|BNUT)\b)", re.IGNORECASE)


@dataclass
class IssueRef:
    repo: str
    number: int


@dataclass
class PullRef:
    repo: str
    number: int


def run_gh(args: list[str]) -> Any:
    cmd = [GH, *args]
    completed = subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"gh failed: {' '.join(args)}\n{completed.stderr.strip()}")
    output = completed.stdout.strip()
    if not output:
        return None
    return json.loads(output)


def parse_issue_ref(value: str) -> IssueRef:
    if value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 4 and parts[2] == "issues":
            return IssueRef(repo=f"{parts[0]}/{parts[1]}", number=int(parts[3]))
    match = re.match(r"^([^/\s]+/[^#\s]+)#(\d+)$", value)
    if match:
        return IssueRef(repo=match.group(1), number=int(match.group(2)))
    raise ValueError("Expected a GitHub issue URL or owner/repo#123")


def parse_pull_ref(value: str) -> PullRef:
    if value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 4 and parts[2] == "pull":
            return PullRef(repo=f"{parts[0]}/{parts[1]}", number=int(parts[3]))
    match = re.match(r"^([^/\s]+/[^#\s]+)#(\d+)$", value)
    if match:
        return PullRef(repo=match.group(1), number=int(match.group(2)))
    raise ValueError("Expected a GitHub pull request URL or owner/repo#123")


def is_bounty_like(item: dict[str, Any]) -> bool:
    title = item.get("title", "").lower()
    if "bounty claim" in title or title.startswith("claim:") or title.startswith("[claim"):
        return False
    haystack = " ".join(
        [
            item.get("title", ""),
            item.get("body", "") or "",
            " ".join(label.get("name", "") for label in item.get("labels", [])),
        ]
    ).lower()
    label_text = " ".join(label.get("name", "") for label in item.get("labels", [])).lower()
    strong_markers = [
        "/bounty",
        "bounty:",
        "bounty $",
        "[bounty",
        "reward:",
        "price:",
        "paid",
        "payout",
        "algora",
        "opire",
    ]
    money_with_bounty = bool(MONEY_RE.search(haystack)) and ("bounty" in haystack or "reward" in haystack)
    bounty_label = "bounty" in label_text or "price:" in label_text
    return bounty_label or money_with_bounty or any(marker in haystack for marker in strong_markers)


def issue_view(ref: IssueRef) -> dict[str, Any]:
    return run_gh(
        [
            "issue",
            "view",
            str(ref.number),
            "--repo",
            ref.repo,
            "--comments",
            "--json",
            "number,title,url,body,labels,assignees,comments,state,updatedAt",
        ]
    )


def repo_view(repo: str) -> dict[str, Any]:
    return run_gh(
        [
            "repo",
            "view",
            repo,
            "--json",
            "nameWithOwner,description,url,isArchived,isFork,stargazerCount,forkCount,defaultBranchRef,licenseInfo,createdAt,updatedAt",
        ]
    )


def pr_view(ref: PullRef) -> dict[str, Any]:
    return run_gh(
        [
            "pr",
            "view",
            str(ref.number),
            "--repo",
            ref.repo,
            "--json",
            "number,title,url,state,isDraft,author,headRefName,baseRefName,body,createdAt,updatedAt,mergeStateStatus,statusCheckRollup,reviewDecision,labels",
        ]
    )


def search_open_prs(repo: str, issue_number: int, title: str) -> list[dict[str, Any]]:
    queries = [
        f"repo:{repo} is:pr is:open #{issue_number}",
        f'repo:{repo} is:pr is:open "{title[:80]}"',
    ]
    found: dict[int, dict[str, Any]] = {}
    for query in queries:
        try:
            data = run_gh(
                [
                    "api",
                    "--method",
                    "GET",
                    "/search/issues",
                    "-f",
                    f"q={query}",
                    "-f",
                    "per_page=20",
                ]
            )
        except RuntimeError:
            continue
        for item in data.get("items", []):
            found[item["number"]] = {
                "number": item["number"],
                "title": item["title"],
                "url": item["html_url"],
                "updated_at": item["updated_at"],
                "state": item["state"],
                "author": item.get("user", {}).get("login", ""),
            }
    return list(found.values())


def candidate_search(limit: int) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for query in BOUNTY_QUERIES:
        data = run_gh(
            [
                "api",
                "--method",
                "GET",
                "/search/issues",
                "-f",
                f"q={query}",
                "-f",
                "sort=updated",
                "-f",
                "order=desc",
                "-f",
                "per_page=50",
            ]
        )
        for item in data.get("items", []):
            if not is_bounty_like(item):
                continue
            repo = item["repository_url"].split("/repos/", 1)[1]
            key = f"{repo}#{item['number']}"
            found[key] = {
                "repo": repo,
                "number": item["number"],
                "title": item["title"],
                "url": item["html_url"],
                "comments": item["comments"],
                "labels": [label["name"] for label in item.get("labels", [])],
                "assignees": [user["login"] for user in item.get("assignees", [])],
                "updated_at": item["updated_at"],
                "body_excerpt": (item.get("body") or "")[:500],
            }
            if len(found) >= limit:
                break
        if len(found) >= limit:
            break
    return list(found.values())[:limit]


def age_days(timestamp: str | None) -> int | None:
    if not timestamp:
        return None
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).days


def detect_platform(issue: dict[str, Any]) -> tuple[str, str]:
    text = "\n".join(
        [
            issue.get("body") or "",
            " ".join(label.get("name", "") for label in issue.get("labels", [])),
            "\n".join(comment.get("body", "") for comment in issue.get("comments", [])),
        ]
    )
    lower = text.lower()
    if "algora" in lower:
        return "Algora", "clear"
    if "opire" in lower:
        return "Opire", "avoid unless account exists"
    if "ubiquity" in lower or "price:" in lower:
        if "core team member" in lower or "administrator to start" in lower:
            return "Ubiquity/Devpool", "gated"
        return "Ubiquity/Devpool", "check wallet/start eligibility"
    if "bountypay" in lower:
        return "BountyPay", "unclear/demo risk"
    if "bounty" in lower or MONEY_RE.search(text):
        return "GitHub/manual", "unclear"
    return "unknown", "unclear"


def analyze_issue(ref: IssueRef) -> dict[str, Any]:
    issue = issue_view(ref)
    repo = repo_view(ref.repo)
    prs = search_open_prs(ref.repo, ref.number, issue["title"])
    labels = [label["name"] for label in issue.get("labels", [])]
    comments = issue.get("comments", [])
    body_and_comments = "\n".join([issue.get("body") or "", *[c.get("body", "") for c in comments]])
    title_lower = issue["title"].lower()
    platform, payout_friction = detect_platform(issue)
    attempts = [c for c in comments if ATTEMPT_RE.search(c.get("body", ""))]
    linked_pr_mentions = sorted(set(PR_RE.findall(body_and_comments)))
    warnings: list[str] = []
    positives: list[str] = []
    score = 0

    if not issue.get("assignees"):
        score += 2
        positives.append("No assignee on the issue.")
    else:
        score -= 3
        warnings.append("Issue is assigned.")

    if not prs:
        score += 3
        positives.append("No open PR collision found by issue-number/title search.")
    else:
        score -= 3
        warnings.append(f"{len(prs)} open PR collision(s) found.")

    if payout_friction == "clear":
        score += 2
        positives.append(f"Payout path appears clear via {platform}.")
    elif payout_friction == "gated":
        score -= 4
        warnings.append("Payout/start flow appears gated.")
    else:
        score -= 1
        warnings.append(f"Payout path needs confirmation: {payout_friction}.")

    if len(attempts) == 0:
        score += 2
        positives.append("No attempt comments detected.")
    elif len(attempts) <= 2:
        score += 1
        positives.append("Low attempt count.")
    else:
        score -= 2
        warnings.append(f"{len(attempts)} attempt-like comments detected.")

    if issue.get("state") != "OPEN":
        score -= 10
        warnings.append("Issue is not open.")

    if "bounty claim" in title_lower or title_lower.startswith("claim:") or title_lower.startswith("[claim"):
        score -= 10
        warnings.append("This looks like a claim/payment bookkeeping issue, not a fresh bounty.")

    if "rewarded" in " ".join(labels).lower() or "paid" in body_and_comments.lower():
        score -= 3
        warnings.append("Reward/payment language detected; check whether bounty is still available.")

    if issue.get("comments", []) and len(comments) > 20:
        score -= 2
        warnings.append("High comment count suggests crowding or stale debate.")
    elif len(comments) <= 5:
        score += 1
        positives.append("Low comment count.")

    if repo.get("isArchived"):
        score -= 5
        warnings.append("Repository is archived.")

    if score >= 5:
        verdict = "attempt"
    elif score >= 1:
        verdict = "watch"
    else:
        verdict = "skip"

    estimated_hours = estimate_hours(score, len(prs), len(attempts), len(comments), labels)
    return {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "issue": {
            "repo": ref.repo,
            "number": issue["number"],
            "title": issue["title"],
            "url": issue["url"],
            "state": issue["state"],
            "labels": labels,
            "assignees": [a["login"] for a in issue.get("assignees", [])],
            "updated_at": issue.get("updatedAt"),
        },
        "repo": repo,
        "platform": platform,
        "payout_friction": payout_friction,
        "score": score,
        "verdict": verdict,
        "estimated_codex_hours": estimated_hours,
        "open_pr_collisions": prs,
        "attempt_count": len(attempts),
        "linked_pr_mentions": linked_pr_mentions[:20],
        "positives": positives,
        "warnings": warnings,
        "recommended_next_action": recommend(verdict, payout_friction, prs, attempts),
    }


def estimate_hours(score: int, pr_count: int, attempt_count: int, comment_count: int, labels: list[str]) -> str:
    label_text = " ".join(labels).lower()
    if "size l" in label_text or "large" in label_text:
        return "6-12+"
    if pr_count or attempt_count > 3 or comment_count > 20:
        return "3-8"
    if score >= 5:
        return "1-4"
    return "2-6"


def recommend(verdict: str, payout_friction: str, prs: list[dict[str, Any]], attempts: list[dict[str, Any]]) -> str:
    if verdict == "attempt":
        return "Comment intent only after a quick local repo sanity check, then open a focused PR with tests/proof."
    if prs:
        return "Skip direct attempt; inspect stale/failing PRs and look for a rescue opportunity instead."
    if payout_friction != "clear":
        return "Watch until payout/start process is confirmed, or use as a free sample report."
    if attempts:
        return "Watch for maintainer feedback; avoid joining unless existing attempts stall."
    return "Watch; needs clearer acceptance or lower setup risk before attempting."


def render_markdown(report: dict[str, Any]) -> str:
    issue = report["issue"]
    pr_lines = "\n".join(
        f"- #{pr['number']} [{pr['title']}]({pr['url']}) by `{pr['author']}`, updated {pr['updated_at']}"
        for pr in report["open_pr_collisions"]
    ) or "- None found."
    warnings = "\n".join(f"- {warning}" for warning in report["warnings"]) or "- None."
    positives = "\n".join(f"- {positive}" for positive in report["positives"]) or "- None."
    labels = ", ".join(f"`{label}`" for label in issue["labels"]) or "none"
    assignees = ", ".join(f"`{a}`" for a in issue["assignees"]) or "none"
    return f"""# Bounty Preflight Report: {issue['repo']}#{issue['number']}

**Verdict:** `{report['verdict']}`  
**Score:** `{report['score']}`  
**Estimated Codex hours:** `{report['estimated_codex_hours']}`  
**Payout path:** `{report['platform']}` ({report['payout_friction']})

## Issue
- Title: [{issue['title']}]({issue['url']})
- State: `{issue['state']}`
- Labels: {labels}
- Assignees: {assignees}
- Updated: `{issue['updated_at']}`

## Collision Check
{pr_lines}

Attempt-like comments detected: `{report['attempt_count']}`

## Positives
{positives}

## Risks
{warnings}

## Recommended Next Action
{report['recommended_next_action']}

---
Generated by Bounty Preflight Oracle. Do not include private payout details in public PRs or comments.
"""


def write_text(path: str | None, content: str) -> None:
    if not path:
        sys.stdout.buffer.write(content.encode("utf-8", errors="replace"))
        if not content.endswith("\n"):
            sys.stdout.buffer.write(b"\n")
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def write_json(path: str | None, data: Any) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def scan_issue(args: argparse.Namespace) -> None:
    report = analyze_issue(parse_issue_ref(args.issue))
    write_text(args.out, render_markdown(report))
    write_json(args.json_out, report)


def scan_repo(args: argparse.Namespace) -> None:
    candidates = []
    for candidate in candidate_search(args.limit * 5):
        if candidate["repo"].lower() == args.repo.lower():
            try:
                candidates.append(analyze_issue(IssueRef(args.repo, candidate["number"])))
            except Exception as exc:  # keep repo scan resilient
                candidates.append({"issue": candidate, "error": str(exc), "verdict": "error", "score": -999})
        if len(candidates) >= args.limit:
            break
    candidates.sort(key=lambda item: item.get("score", -999), reverse=True)
    lines = [f"# Repo Bounty Scan: {args.repo}", ""]
    for item in candidates:
        issue = item["issue"]
        lines.append(f"## {issue.get('repo', args.repo)}#{issue['number']} - {issue['title']}")
        lines.append(f"- Verdict: `{item.get('verdict')}`")
        lines.append(f"- Score: `{item.get('score')}`")
        lines.append(f"- URL: {issue['url']}")
        if "recommended_next_action" in item:
            lines.append(f"- Next: {item['recommended_next_action']}")
        if "error" in item:
            lines.append(f"- Error: {item['error']}")
        lines.append("")
    write_text(args.out, "\n".join(lines))
    write_json(args.json_out, candidates)


def collect_candidates(args: argparse.Namespace) -> None:
    candidates = candidate_search(args.limit)
    write_json(args.out, candidates)
    if args.csv:
        target = Path(args.csv)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "repo",
                    "number",
                    "title",
                    "url",
                    "comments",
                    "labels",
                    "assignees",
                    "updated_at",
                    "body_excerpt",
                ],
                extrasaction="ignore",
            )
            writer.writeheader()
            for item in candidates:
                writer.writerow(
                    {
                        **item,
                        "labels": ";".join(item["labels"]),
                        "assignees": ";".join(item["assignees"]),
                    }
                )


def render_digest(reports: list[dict[str, Any]], scan_limit: int) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Daily Bounty Preflight Digest",
        "",
        f"Generated: `{generated}`",
        f"Candidates analyzed: `{scan_limit}`",
        "",
        "This digest ranks GitHub bounty-like issues by attemptability and rescue value.",
        "",
    ]
    for index, report in enumerate(reports, start=1):
        issue = report["issue"]
        collision_count = len(report.get("open_pr_collisions", []))
        lines.extend(
            [
                f"## {index}. {issue['repo']}#{issue['number']} - {issue['title']}",
                f"- Verdict: `{report['verdict']}`",
                f"- Score: `{report['score']}`",
                f"- Payout path: `{report['platform']}` ({report['payout_friction']})",
                f"- Estimated Codex hours: `{report['estimated_codex_hours']}`",
                f"- Open PR collisions: `{collision_count}`",
                f"- Attempts detected: `{report['attempt_count']}`",
                f"- URL: {issue['url']}",
                f"- Next: {report['recommended_next_action']}",
                "",
            ]
        )
    if not reports:
        lines.append("No candidates survived analysis.")
    return "\n".join(lines)


def daily_digest(args: argparse.Namespace) -> None:
    candidates = candidate_search(args.scan_limit)
    reports: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for candidate in candidates:
        try:
            reports.append(analyze_issue(IssueRef(candidate["repo"], candidate["number"])))
        except Exception as exc:
            errors.append({"url": candidate["url"], "error": str(exc)})
    reports.sort(key=lambda item: item.get("score", -999), reverse=True)
    selected = reports[: args.limit]
    write_text(args.out, render_digest(selected, len(candidates)))
    write_json(
        args.json_out,
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scan_limit": args.scan_limit,
            "selected": selected,
            "errors": errors,
        },
    )


def analyze_pr(ref: PullRef) -> dict[str, Any]:
    pr = pr_view(ref)
    checks = pr.get("statusCheckRollup") or []
    failed = []
    pending = []
    passed = []
    for check in checks:
        conclusion = (check.get("conclusion") or check.get("state") or "").upper()
        name = check.get("name") or check.get("workflowName") or check.get("context") or "unknown"
        entry = {
            "name": name,
            "conclusion": conclusion,
            "url": check.get("detailsUrl") or check.get("url"),
        }
        if conclusion in {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}:
            failed.append(entry)
        elif conclusion in {"SUCCESS", "NEUTRAL", "SKIPPED"}:
            passed.append(entry)
        else:
            pending.append(entry)
    age = age_days(pr.get("updatedAt"))
    stale = age is not None and age >= 7
    score = 0
    warnings = []
    positives = []
    if failed:
        score += 3
        positives.append("PR has failing checks that may be fixable.")
    if stale:
        score += 2
        positives.append(f"PR appears stale: last updated {age} day(s) ago.")
    if pr.get("isDraft"):
        score += 1
        positives.append("Draft PR may need completion or cleanup.")
    if pr.get("mergeStateStatus") == "CLEAN":
        score += 1
        positives.append("PR is mergeable by GitHub merge-state check.")
    if not failed and not stale:
        warnings.append("No obvious CI/rescue angle found.")
        score -= 2
    if pr.get("reviewDecision") == "CHANGES_REQUESTED":
        score += 2
        positives.append("Review changes requested; targeted fix may unblock it.")
    verdict = "rescue" if score >= 4 else "watch" if score >= 1 else "skip"
    return {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "pr": {
            "repo": ref.repo,
            "number": pr["number"],
            "title": pr["title"],
            "url": pr["url"],
            "state": pr["state"],
            "is_draft": pr["isDraft"],
            "author": pr.get("author", {}).get("login"),
            "head": pr["headRefName"],
            "base": pr["baseRefName"],
            "updated_at": pr["updatedAt"],
            "merge_state": pr.get("mergeStateStatus"),
            "review_decision": pr.get("reviewDecision"),
        },
        "score": score,
        "verdict": verdict,
        "failed_checks": failed,
        "pending_checks": pending,
        "passed_check_count": len(passed),
        "positives": positives,
        "warnings": warnings,
        "recommended_next_action": recommend_pr(verdict, failed, stale),
    }


def recommend_pr(verdict: str, failed: list[dict[str, Any]], stale: bool) -> str:
    if verdict == "rescue" and failed:
        return "Inspect failing check logs, reproduce locally, then offer a minimal patch or replacement PR."
    if verdict == "rescue" and stale:
        return "Compare against the bounty issue and prepare a cleaner replacement PR if rules allow it."
    if verdict == "watch":
        return "Monitor for 48 hours or wait for maintainer feedback before spending implementation time."
    return "Skip unless a maintainer asks for help."


def render_pr_markdown(report: dict[str, Any]) -> str:
    pr = report["pr"]
    failed = "\n".join(
        f"- `{check['name']}`: {check['conclusion']} {check.get('url') or ''}" for check in report["failed_checks"]
    ) or "- None."
    pending = "\n".join(
        f"- `{check['name']}`: {check['conclusion']} {check.get('url') or ''}" for check in report["pending_checks"]
    ) or "- None."
    positives = "\n".join(f"- {positive}" for positive in report["positives"]) or "- None."
    warnings = "\n".join(f"- {warning}" for warning in report["warnings"]) or "- None."
    return f"""# PR Rescue Report: {pr['repo']}#{pr['number']}

**Verdict:** `{report['verdict']}`  
**Score:** `{report['score']}`

## Pull Request
- Title: [{pr['title']}]({pr['url']})
- State: `{pr['state']}`
- Draft: `{pr['is_draft']}`
- Author: `{pr['author']}`
- Branch: `{pr['head']}` -> `{pr['base']}`
- Merge state: `{pr['merge_state']}`
- Review decision: `{pr['review_decision']}`
- Updated: `{pr['updated_at']}`

## Failing Checks
{failed}

## Pending Checks
{pending}

Passed checks: `{report['passed_check_count']}`

## Positives
{positives}

## Risks
{warnings}

## Recommended Next Action
{report['recommended_next_action']}
"""


def scan_pr(args: argparse.Namespace) -> None:
    report = analyze_pr(parse_pull_ref(args.pr))
    write_text(args.out, render_pr_markdown(report))
    write_json(args.json_out, report)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bounty preflight reports for GitHub issues.")
    sub = parser.add_subparsers(dest="command", required=True)

    issue = sub.add_parser("scan-issue", help="Scan one GitHub issue URL or owner/repo#123.")
    issue.add_argument("issue")
    issue.add_argument("--out")
    issue.add_argument("--json-out")
    issue.set_defaults(func=scan_issue)

    pr = sub.add_parser("scan-pr", help="Scan one GitHub PR for stale/failing-check rescue potential.")
    pr.add_argument("pr")
    pr.add_argument("--out")
    pr.add_argument("--json-out")
    pr.set_defaults(func=scan_pr)

    repo = sub.add_parser("scan-repo", help="Scan bounty-like open issues in one repo.")
    repo.add_argument("repo")
    repo.add_argument("--limit", type=int, default=10)
    repo.add_argument("--out")
    repo.add_argument("--json-out")
    repo.set_defaults(func=scan_repo)

    collect = sub.add_parser("collect-candidates", help="Collect a seed database of bounty-like issues.")
    collect.add_argument("--limit", type=int, default=50)
    collect.add_argument("--out", default="data/candidates.json")
    collect.add_argument("--csv")
    collect.set_defaults(func=collect_candidates)

    digest = sub.add_parser("daily-digest", help="Analyze live candidates and output a ranked digest.")
    digest.add_argument("--scan-limit", type=int, default=25)
    digest.add_argument("--limit", type=int, default=5)
    digest.add_argument("--out", default="reports/daily-digest.md")
    digest.add_argument("--json-out", default="reports/daily-digest.json")
    digest.set_defaults(func=daily_digest)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
