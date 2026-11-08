#!/usr/bin/env python3
"""Audit open PRs for work nobody is tracking.

Three kinds of open work hide behind a green-looking PR:

  * CodeRabbit **body-only findings** (outside-diff, additional/unverified). They carry no thread, so a
    later review that only sees the changed files drops them from its counts while the defect is
    still in the code.
  * **Human review state**: `CHANGES_REQUESTED` blocks even at zero findings; an `APPROVED` from
    before the last push is stale.
  * **Absent CI**: on a fork PR the workflows sit in `action_required`, `gh pr checks` lists only the
    bot, and the combined status is `pending` because nothing ran. That is not green.
  * Plus the cheap ones: unresolved threads, a failed check, merge conflicts, unchecked items in the
    PR template.

Usage:
    python audit_prs.py --repo storytold/gridcraft [--author alosslessdev] [--pr 3606] [--json]
    python audit_prs.py --repos storytold/gridcraft,storytold/deckcraft

Requires `gh` authenticated for the host.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prstate  # noqa: E402  (sibling module, vendored in this skill)

CR_LOGINS = ("coderabbitai", "coderabbitai[bot]")
OUTSIDE = re.compile(r"Outside diff range comments \((\d+)\)")
ADDITIONAL = re.compile(r"Additional comments:\s*(\d+)")
ITEM = re.compile(
    r"<summary>.*?</picture>\s*(?P<sev>Critical|Major|Minor|Trivial)\s*</strong>\s*·\s*"
    r"(?P<title>[^<]+?)\s*·\s*<code>(?P<loc>[^<]+)</code>",
    re.S,
)
SHA = re.compile(r"\b[0-9a-f]{7,40}\b")


def body_findings(review):
    """[(severity, title, path, line)] for one review's body-only findings."""
    body = review.get("body") or ""
    if not (OUTSIDE.search(body) or ADDITIONAL.search(body)):
        return []
    out = []
    for m in ITEM.finditer(body):
        loc = m.group("loc").strip()
        path, _, line = loc.rpartition(":")
        if not path:
            path, line = loc, ""
        out.append({
            "severity": m.group("sev").strip(),
            "title": " ".join(m.group("title").split()),
            "path": path.strip().strip("`"),
            "line": line.strip().strip("`"),
        })
    return out


def findings_for(repo, pr, head):
    reviews = [r for r in prstate.paginated(f"repos/{repo}/pulls/{pr}/reviews?per_page=100")
               if (r.get("user") or {}).get("login") in CR_LOGINS]
    comments = prstate.paginated(f"repos/{repo}/pulls/{pr}/comments?per_page=100")
    issues = prstate.paginated(f"repos/{repo}/issues/{pr}/comments?per_page=100")
    convo = [{"at": c.get("created_at"), "body": c.get("body") or "", "url": c.get("html_url")}
             for c in comments]
    convo += [{"at": c.get("created_at"), "body": c.get("body") or "", "url": c.get("html_url")}
              for c in issues if (c.get("user") or {}).get("login") not in CR_LOGINS]

    compares = {}

    def changed_since(commit):
        if commit not in compares:
            files = set()
            cmp = prstate.ghj("api", f"repos/{repo}/compare/{commit}...{head}")
            for f in cmp.get("files") or []:
                files.add(f.get("filename") or "")
            compares[commit] = files
        return compares[commit]

    out = []
    for r in reviews:
        raised = r.get("submitted_at") or ""
        commit = (r.get("commit") or {}).get("oid") or ""
        for f in body_findings(r):
            later = [c for c in convo if (c["at"] or "") > raised]
            by_path = [c for c in later if f["path"] and f["path"] in c["body"]]
            key = " ".join(f["title"].lower().split()[:4])
            by_title = [c for c in later if key and key in " ".join(c["body"].lower().split())]
            status, evidence = "needs-review", None
            if by_path and any(SHA.search(c["body"]) for c in by_path):
                status, evidence = "answered-with-commit", by_path[0]["url"]
            elif by_path:
                status, evidence = "answered", by_path[0]["url"]
            elif by_title:
                status, evidence = "answered", by_title[0]["url"]
            elif commit and f["path"] in changed_since(commit):
                status = "likely"
            out.append({"raised_at": raised, "review_commit": commit[:8], **f,
                        "status": status, "evidence": evidence})
    return out


def audit_pr(repo, pr):
    state = prstate.gather(repo, pr)
    if "error" in state:
        return None
    head = state["head"]
    findings = findings_for(repo, pr, head)
    needs = [f for f in findings if f["status"] == "needs-review"]
    return {
        "repo": repo, "pr": pr, "head": head[:8], "title": state.get("branch"),
        "mergeable": state.get("mergeable"),
        "blockers": state.get("blockers") or [],
        "findings": findings,
        "unaddressed": len(needs) + len([f for f in findings if f["status"] == "likely"]),
    }


def main():
    argv = sys.argv[1:]
    if "--repos" in argv:
        repos = argv[argv.index("--repos") + 1].split(",")
    elif "--repo" in argv:
        repos = [argv[argv.index("--repo") + 1]]
    else:
        print(__doc__)
        return 2
    author = argv[argv.index("--author") + 1] if "--author" in argv else "alosslessdev"
    only = int(argv[argv.index("--pr") + 1]) if "--pr" in argv else None
    as_json = "--json" in argv

    results = []
    for repo in repos:
        nums = [only] if only else [
            p["number"] for p in prstate.paginated(f"repos/{repo}/pulls?state=open&per_page=100")
            if (p.get("user") or {}).get("login") == author
        ]
        for n in nums:
            r = audit_pr(repo, n)
            if r:
                results.append(r)

    if as_json:
        print(json.dumps(results, indent=1))
        return 0

    for repo in repos:
        rows = [r for r in results if r["repo"] == repo]
        if not rows:
            continue
        bad = [r for r in rows if r["blockers"] or r["unaddressed"]]
        print(f"\n# {repo} — {len(rows)} open PRs, {len(bad)} with open work\n")
        print("| PR | head | blockers | unaddressed findings |")
        print("|---|---|---|---|")
        for r in sorted(rows, key=lambda r: r["pr"]):
            bl = "; ".join(r["blockers"]) or "—"
            print(f"| #{r['pr']} | {r['head']} | {bl} | {r['unaddressed']} |")
        flagged = [f for r in rows for f in r["findings"]
                   if f["status"] in ("needs-review", "likely")]
        if flagged:
            print("\n## findings that need a code check\n")
            for r in sorted(rows, key=lambda r: r["pr"]):
                for f in r["findings"]:
                    if f["status"] in ("needs-review", "likely"):
                        print(f"- #{r['pr']} `{f['path']}:{f['line']}` — {f['title']} "
                              f"({f['severity']}, {f['status']}, raised {f['raised_at'][:16]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
