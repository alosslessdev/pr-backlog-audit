# pr-backlog-audit

An agent skill that audits every open pull request by an author for work nobody is tracking:

- **CodeRabbit body-only findings** (outside-diff, additional/unverified) that a later review stopped
  counting while the defect stayed in the code;
- **`CHANGES_REQUESTED` reviews** — blocking even when every count is zero;
- **CI that never ran** on a fork PR (`action_required`, empty commit status, `pending` combined
  status);
- **paused CodeRabbit series**, which never restart themselves and freeze every count at its last
  value;
- unresolved threads, failing **and pending** checks, and unchecked items in the PR template.

Conflicts with the base branch are deliberately not audited: in a fast-moving repository a branch goes
dirty within hours, so a conflict is expected state, not untended work.

The audit half of [pr-review-loop](https://github.com/alosslessdev/pr-review-loop); that skill drives
a single PR to its stop condition, this one finds what is still open across a repo.

## Install

```bash
git clone https://github.com/<owner>/pr-backlog-audit.git
cp -r pr-backlog-audit ~/.agents/skills/pr-backlog-audit     # or .claude/skills/pr-backlog-audit
```

Requires `gh`, authenticated for the host you target.

## Run

```bash
python scripts/audit_prs.py --repos storytold/gridcraft,storytold/deckcraft,storytold/wordcraft
python scripts/audit_prs.py --repo storytold/gridcraft --pr 3606
python scripts/audit_prs.py --repo storytold/gridcraft --json
```

Output: per repo, a table of open PRs with blockers and unaddressed-finding counts, then the findings
that need a code check.

## Why it exists

A real case: a Major performance finding ("limit gallery texture work to visible thumbnails") was
raised as an outside-diff comment. It has no thread, so the next review — which only looked at the
changed files — reported **0 outside-diff findings**. The PR looked clean, the code was unchanged, and
"the latest review says 0" was read as proof. That is the failure this audit detects mechanically:

| status | meaning |
|---|---|
| `answered-with-commit` | a later comment names the path and a commit |
| `answered` | a later comment names the path or the finding's title |
| `likely` | the path changed after the finding, with no comment — read the code |
| `needs-review` | no evidence at all; the defect is probably still there |

## Contents

| Path | What |
|---|---|
| `SKILL.md` | the four blind spots, the statuses, the triage order |
| `scripts/audit_prs.py` | the audit itself (per-PR blockers + body-only findings with evidence) |
| `scripts/prstate.py` | one-PR state: findings, threads, review decision, checklist, absent CI, review state, blockers |
| `scripts/resume_paused.py` | resume PRs whose CodeRabbit review series is paused |
| `scripts/human_scan.py` | PRs whose human reviews/comments were never answered |

## Licence

MIT.
