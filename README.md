# triage-pr

A Claude Code skill that triages every review and conversation comment on a
GitHub pull request into one decision table, gets an explicit Approve or
Ignore call from you on each item, then implements what you approved.

See [`plugins/triage-pr/skills/triage-pr/SKILL.md`](plugins/triage-pr/skills/triage-pr/SKILL.md)
for the full step-by-step behavior.

## Prerequisites

- [Claude Code](https://claude.com/claude-code)
- [GitHub CLI](https://cli.github.com) (`gh`), installed and authenticated
  (`gh auth login`) with access to the repo whose PRs you want to triage

The skill checks for both itself before doing anything, but installing it
still requires `claude` on your PATH.

## Install

Add this repo as a plugin marketplace, then install the plugin from it:

```bash
claude plugin marketplace add sebastialonso/triage-pr-skill
claude plugin install triage-pr@triage-pr-skill
```

Or, from inside an interactive Claude Code session:

```
/plugin marketplace add sebastialonso/triage-pr-skill
/plugin install triage-pr@triage-pr-skill
```

Restart Claude Code (or start a new session) after installing so the skill
loads.

## Use

From inside a Claude Code session, just ask for it in plain language:

```
triage the comments on https://github.com/OWNER/REPO/pull/123
```

or, from within a checkout of the target repo, on the PR for your current
branch:

```
triage PR comments
```

Claude will:

1. Verify `gh` is installed and authenticated.
2. Fetch every review-thread and conversation comment on the PR (including
   bot/tool comments — nothing is filtered out except already-resolved
   review threads).
3. Present them as a table: a summary of each thread, Claude's own merit
   analysis of it, and a link to the thread on GitHub.
4. Ask you to Approve or Ignore each row.
5. Confirm with you before implementing anything.
6. Implement only the approved rows, run the project's linter/tests if it
   has them, and report what was done.

Replying to or resolving the actual GitHub threads is left to you — the
skill stops after implementing and reporting.

## Update

```bash
claude plugin marketplace update triage-pr-skill
claude plugin update triage-pr
```

## Uninstall

```bash
claude plugin uninstall triage-pr
claude plugin marketplace remove triage-pr-skill
```
