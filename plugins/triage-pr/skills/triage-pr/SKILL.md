---
name: triage-pr
description: Triage every review and conversation comment on a GitHub pull request into one decision table, get an explicit Approve or Ignore call from the engineer on each item, then implement what's approved. Use this whenever the user asks to "triage PR comments", "go through the review feedback", "process comments on PR #N", pastes a GitHub PR URL and asks what to do with the feedback on it, or wants to work through a pile of reviewer comments on a pull request systematically instead of reading them one at a time in the GitHub UI.
---

# Triage PR

Pull requests that have been through a few review rounds pile up comments of
very different weight: real blocking issues, nitpicks, bot/tool suggestions,
and things already discussed to death. Scrolling GitHub's UI to sort that
out is slow and error-prone — it's easy to miss a comment, or to implement
something the engineer never actually signed off on. This skill turns that
mess into one table, gets an explicit decision on every row before anything
is touched, and implements only what was approved.

Do not skip steps or reorder them — implementing before every row has a
decision defeats the point of having the engineer sign off first.

## Step 0 — Verify `gh` is installed and authenticated (required)

This skill cannot do anything without `gh`. Before doing anything else, run:

```bash
gh auth status
```

If this fails because `gh` isn't installed, stop and tell the engineer to
install the GitHub CLI (https://cli.github.com) and re-run. If it fails
because they aren't logged in, stop and tell them to run `gh auth login`
first. Do not attempt to fetch anything until `gh auth status` succeeds —
the fetch step shells out to `gh`.

## Step 1 — Identify the PR

You need `owner`, `repo`, and the PR number. Get them the most direct way
available:

- If the engineer gave a full URL (`https://github.com/OWNER/REPO/pull/N`),
  parse owner/repo/number straight out of it — don't shell out for this.
- If they gave just a number or nothing, and you're running inside a checkout
  of the target repo, get owner/repo from `gh repo view --json nameWithOwner
  -q .nameWithOwner` and the PR number from context (current branch's PR via
  `gh pr view --json number -q .number`, or ask if ambiguous).
- If neither is available, ask the engineer for the PR URL rather than
  guessing.

## Step 2 — Fetch and normalize every comment

Run the bundled script:

```bash
python3 <plugin-dir>/skills/triage-pr/scripts/fetch_pr_threads.py OWNER REPO NUMBER
```

This returns JSON with one row per decision-worthy thread — diff-anchored
review comment threads and top-level PR conversation comments (including
non-empty review summaries) are both included, each already merged with any
follow-up replies in the same thread. The only filtering it does is dropping
already-resolved review threads, since those are presumably already
settled.

Include every comment: human reviewers, bot/agent reviewers (CodeRabbit,
Copilot, coding agents, etc.), and the PR author's own replies all get a
row. Bot and automated-review comments often carry real, actionable
analysis — treat them the same as human feedback rather than filtering or
downgrading them.

If the JSON comes back with zero rows, tell the engineer the PR has nothing
outstanding to triage and stop here — don't invent rows.

## Step 3 — Present the table

Build one Markdown table from the JSON, most-recent-first or PR-order
(either is fine — pick whichever the JSON already gives you, don't re-sort).
One row per JSON row:

| # | Summary | Merit analysis | Thread |
|---|---------|-----------------|--------|
| 1 | *One or two sentences capturing what's being asked or proposed across the whole thread — if a coding agent already replied, fold that context in rather than listing it separately.* | *Your own technical read: is this correct, worth doing, in scope, risky, already handled elsewhere, or a style nit? Say so plainly — this is your actual judgment, not a restatement of the comment.* | [`OWNER/REPO#N` thread](url) |

The merit-analysis column is the point of this table — don't leave it as a
neutral summary. Actually assess whether each proposal holds up: check it
against the relevant code if needed, flag when a suggestion is factually
wrong, out of scope, already addressed, or would introduce a regression, and
say so directly. The engineer is relying on this column to decide quickly.

## Step 4 — Get an Approve/Ignore decision on every row

Every row needs an explicit decision — Approve (gets implemented) or Ignore
(discarded, not implemented) — before you move on. Use `AskUserQuestion`,
batching rows into the same call where you can (it supports up to 4
questions per call) rather than asking one at a time; for more than 4 rows,
make multiple calls back to back. Don't infer a decision from the merit
analysis, however confident you are — a row with an obviously bad proposal
still needs the engineer to say Ignore.

## Step 5 — Confirm before implementing

Once every row has a decision, summarize the approved list back to the
engineer and explicitly ask for the go-ahead to start implementing. Wait for
a clear yes before touching any code.

## Step 6 — Implement the approved rows

Implement only what was approved, the same way you would any other coding
task in this repo — read the surrounding code first, keep changes scoped to
what each row actually asked for, and follow this project's existing
conventions rather than introducing new ones. If an approved row turns out
to be more involved or different in scope than the table suggested once you
look at the code, flag that to the engineer before proceeding rather than
quietly doing something else.

After implementing, run this project's linter/type checker and test suite
if it has them, fixing any failures before reporting done. Then tell the
engineer which approved rows were addressed — replying to or resolving the
actual GitHub threads is left to them.
