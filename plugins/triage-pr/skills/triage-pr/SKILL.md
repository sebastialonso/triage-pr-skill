---
name: triage-pr
description: Triage every review and conversation comment on a GitHub pull request into one decision table, get an explicit Approve or Ignore call from the engineer on each item, implement what's approved, then reply to and resolve each thread according to its outcome. Use this whenever the user asks to "triage PR comments", "go through the review feedback", "process comments on PR #N", pastes a GitHub PR URL and asks what to do with the feedback on it, or wants to work through a pile of reviewer comments on a pull request systematically instead of reading them one at a time in the GitHub UI.
---

# Triage PR

Pull requests that have been through a few review rounds mix three things
together: comments still awaiting a decision, comments a coding agent
already replied to in an earlier pass, and comments that were never more
than a passing remark. Scrolling GitHub's UI to sort that out is slow and
error-prone — it's easy to miss a comment, or to implement something the
engineer never actually signed off on. This skill turns that mess into one
table, gets an explicit decision on every row before anything is touched,
implements only what was approved, and closes the loop by replying to and
resolving each thread.

Do not skip steps or reorder them — implementing before every row has a
decision, or resolving before implementation is done and confirmed, defeats
the point of having the engineer sign off at each gate.

## Step 0 — Verify `gh` is installed and authenticated (required)

This skill cannot do anything without `gh`. Before doing anything else, run:

```bash
gh auth status
```

If this fails because `gh` isn't installed, stop and tell the engineer to
install the GitHub CLI (https://cli.github.com) and re-run. If it fails
because they aren't logged in, stop and tell them to run `gh auth login`
first. Do not attempt to fetch or post anything until `gh auth status`
succeeds — every later step shells out to `gh`, and a partial run (e.g.
fetching comments but failing to reply) is worse than not starting.

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
follow-up replies in the same thread. It already:

- Drops resolved review threads (presumably already settled).
- Drops threads/groups made up entirely of bot or coding-agent comments —
  there's no human ask in them to decide on.
- Folds a coding agent's prior reply into the row it's replying to, so the
  table shows one unified item per human ask rather than the raw back-and-forth.

The script's bot/agent detection is a login-pattern list at the top of the
file (`BOT_LOGIN_PATTERNS`). If your org's coding agent posts under a login
that isn't already covered (the defaults cover common ones like `[bot]`
suffixes, `copilot`, `claude`, `coderabbitai`), add its login there before
relying on the fold/drop behavior — otherwise its comments will show up as
their own rows needing a decision, which is harmless but noisy.

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

## Step 7 — Resolve threads

After implementation is complete (and, if this project has a verify/test
step, after that passes), ask the engineer explicitly whether you're clear
to reply-and-resolve every thread now. Once confirmed, for each row call:

```bash
# review_thread rows (resolve_id and reply_to_comment_id are non-null):
python3 <plugin-dir>/skills/triage-pr/scripts/apply_pr_decision.py review-thread \
  OWNER REPO NUMBER <reply_to_comment_id> <resolve_id> "<reply body>"

# general_comment rows (resolve_id is null — reply only, GitHub has no
# resolve concept for non-diff comments):
python3 <plugin-dir>/skills/triage-pr/scripts/apply_pr_decision.py general-comment \
  OWNER REPO NUMBER "<reply body>"
```

Write a short, specific reply for each row rather than a generic one:

- **Approved**: say what was done and, if useful, reference the commit or
  the specific change (e.g. "Done in `path/to/file.py` — switched to X
  because Y.").
- **Ignored**: say why in one sentence (e.g. "Not doing this — out of scope
  for this PR" or "Skipping, current behavior is intentional because Z").
  An honest reason is more useful to the reviewer than a vague brush-off.

`general_comment` rows get a reply but are never "resolved" — there's
nothing in the GitHub API to resolve for a non-diff comment, so don't claim
otherwise to the engineer.
