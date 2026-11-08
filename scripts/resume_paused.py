#!/usr/bin/env python3
"""Find PRs whose CodeRabbit review series is paused, and resume them.

A paused series is not a clean PR. CodeRabbit stops reviewing — its summary says "reviews paused",
its check run reads "Review paused"/"Skipped", and no review will ever land until someone posts
`@coderabbitai resume`. In a stack it can pause every PR at once.

Usage:
    python resume_paused.py --repos storytold/gridcraft,storytold/deckcraft [--dry-run] [--author X]

For every paused PR it posts `@coderabbitai resume`, waits briefly, then requests one
`@coderabbitai full review` if the head still has no completed review. Rate-limited waits are the
caller's problem: run it again later rather than looping here.
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prstate  # noqa: E402


def post(repo, pr, body):
    p = subprocess.run(["gh", "pr", "comment", str(pr), "--repo", repo, "--body", body],
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode == 0


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
    dry = "--dry-run" in argv

    paused, resumed, healthy = [], [], []
    for repo in repos:
        nums = [p["number"] for p in prstate.paginated(f"repos/{repo}/pulls?state=open&per_page=100")
                if (p.get("user") or {}).get("login") == author]
        for n in nums:
            st = prstate.gather(repo, n)
            if "error" in st:
                continue
            cr = st["cr"]
            row = (repo, n, st["head"][:8], cr.get("review_state"), cr.get("paused"))
            if not cr.get("paused"):
                healthy.append(row)
                continue
            paused.append(row)
            if dry:
                continue
            ok = post(repo, n, "@coderabbitai resume")
            time.sleep(8)
            if ok and cr.get("review_state") == "paused" and not cr.get("on_head"):
                post(repo, n, "@coderabbitai full review")
            resumed.append((repo, n, ok))

    print(f"\npaused: {len(paused)}   resumed: {len(resumed)}   healthy: {len(healthy)}\n")
    if paused:
        print("| repo | PR | head | review state |")
        print("|---|---|---|---|")
        for repo, n, head, state, _ in paused:
            print(f"| {repo} | #{n} | {head} | {state} |")
    for repo, n, ok in resumed:
        print(f"  posted '@coderabbitai resume' on {repo}#{n}: {'ok' if ok else 'failed'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
