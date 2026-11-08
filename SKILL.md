---
name: pr-backlog-audit
description: Audit every open PR by an author for work nobody is tracking — CodeRabbit body-only findings that later reviews stopped counting, CHANGES_REQUESTED reviews, CI that never ran on a fork, unresolved threads, conflicts and unchecked PR checklists. Use before declaring a repo clean, when asked to find unaddressed review comments across PRs, or when a maintainer says a gate was "incomplete or unchecked".
metadata:
  version: "1"
---

# PR backlog audit

"Everything is green" is a claim about *counts*, and counts lie in four specific ways. This skill finds
the work behind them.

## The four blind spots

| Blind spot | Why counts miss it | Evidence you need |
|---|---|---|
| **Body-only findings** (outside-diff, additional/unverified) | they carry no thread; a later review that only sees changed files drops them from its totals | the finding, plus a comment naming a fixing commit, or a change to that path after it was raised |
| **Human review state** | `CHANGES_REQUESTED` is not a CodeRabbit count; an old `APPROVED` predates your last push | `reviewDecision` and each review's state |
| **Absent CI** | on a fork PR the workflows sit in `action_required`, `gh pr checks` lists only the bot, and the combined status is `pending` because *nothing ran* | workflow-run conclusions, `check-suites`, and the empty `/statuses` (`total_count: 0`) |
| **Unchecked PR checklist** | a maintainer's gate ("run `cargo xtask ci` end to end, tick the checklist") lives in the template, not in CI | the body's `- [ ]` items |

## Run it

```bash
python scripts/audit_prs.py --repos storytold/gridcraft,storytold/deckcraft,storytold/wordcraft
python scripts/audit_prs.py --repo storytold/gridcraft --pr 3606      # one PR, full detail
python scripts/audit_prs.py --repo storytold/gridcraft --json         # machine-readable
```

Output per repo: a table of PRs with their blockers and the number of unaddressed findings, then a
list of findings that need a code check, each with the path, severity and when it was raised.

Finding statuses:

| status | meaning | action |
|---|---|---|
| `answered-with-commit` | a later comment names the path and a commit | spot-check the commit, then done |
| `answered` | a later comment names the path or the finding's title | read the answer; if it only explains, verify the code |
| `likely` | the path changed after the finding, with no comment | read the code — a change may not be the fix |
| `needs-review` | no evidence at all | the defect is probably still there |

## Triage

1. **`needs-review` and `likely` first.** For each, open the code at the current head and decide:
   fixed (reply with the commit that did it), or not fixed (implement it).
2. **Blockers next**, in the order a maintainer will hit them: conflicts → `CHANGES_REQUESTED` →
   absent CI → failing checks → unchecked checklist → unresolved threads.
3. **Reply where the reviewer will see it.** A body-only finding has no thread: answer in a PR comment
   naming the commit. A blocking review gets a reply **to that review**, naming the reviewer, with the
   commands and per-step results.
4. **Re-run after fixing.** The point is a truthful zero, not a quieter table.

## What "done" looks like

- No `needs-review` or `likely` rows left for the PRs you audited.
- No `CHANGES_REQUESTED` review left unanswered; the checklist matches what actually ran.
- CI either genuinely green, or its absence stated with the local gate transcript attached.
- 0 unresolved threads, 0 actionable/outside-diff/additional on the head, mergeable.

## Notes

- The audit is only as good as its evidence check. `likely` exists because a file changing is not the
  same as the finding being fixed; treat it as a prompt to read, never as a pass.
- `answered` can be an agent answering "fixed in <sha> for a different file" — check the path matches.
- This skill is the audit half of the loop; for driving a single PR to the stop condition, use
  `pr-review-loop`. The two share `scripts/prstate.py` (vendored copy).
- Budgets and cadence do not apply here: an audit is a snapshot. Re-run it after a fix round or before
  reporting a repo as clean.
