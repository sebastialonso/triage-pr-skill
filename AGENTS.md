# AGENTS.md

This repo hosts the `sebastialonso-skills` Claude Code plugin marketplace —
one plugin per public skill. This file is for whoever (human or agent) adds
or edits a skill here. If you just want to *use* a skill, see `README.md`
instead.

## Layout convention

```
.claude-plugin/marketplace.json   # marketplace index — every plugin must be listed here
README.md                         # marketplace-level index for end users
plugins/
  <skill-name>/
    .claude-plugin/plugin.json    # plugin manifest
    README.md                     # this plugin's own install/usage docs
    skills/
      <skill-name>/
        SKILL.md                  # required
        scripts/                  # optional — deterministic/repetitive logic
        references/               # optional — docs loaded into context as needed
        assets/                   # optional — templates, icons, etc.
```

`plugins/triage-pr/` is the reference example — copy its shape for a new
skill rather than inventing a new layout.

## Adding a new skill

1. Create `plugins/<skill-name>/.claude-plugin/plugin.json`:
   ```json
   {
     "name": "<skill-name>",
     "version": "0.1.0",
     "description": "...",
     "author": { "name": "Sebastian Gonzalez" },
     "keywords": ["..."]
   }
   ```
   `name` must be kebab-case and match the skill directory name.

2. Write `plugins/<skill-name>/skills/<skill-name>/SKILL.md`. The
   frontmatter `description` is the *only* thing that determines whether
   Claude triggers the skill — make it specific about what the skill does
   and when to use it, and lean slightly "pushy" (models tend to
   under-trigger skills otherwise). Keep the body under ~500 lines;
   push anything large into `references/`. Prefer imperative instructions
   and explain *why* a step matters over bare MUST/NEVER — see
   `plugins/triage-pr/skills/triage-pr/SKILL.md` for the tone to match.

3. If the skill needs deterministic logic (API calls, parsing, pagination),
   bundle it as a script under `scripts/` rather than leaving Claude to
   improvise it at runtime — and **actually run it against real data**
   before calling it done. Syntax-checking is not enough: when building
   `fetch_pr_threads.py`, `py_compile` passed clean but a live run caught
   that `gh api --paginate` alone prints concatenated JSON documents (not
   one parseable array — you need `--paginate --slurp` and to flatten the
   per-page arrays yourself). GraphQL vs REST: default to REST
   (`gh api <endpoint> --paginate --slurp`) for simplicity; only reach for
   `gh api graphql` when REST genuinely has no equivalent (e.g. PR
   review-thread resolved-state and thread grouping are GraphQL-only).

4. Add an entry to the root `.claude-plugin/marketplace.json`:
   ```json
   {
     "name": "<skill-name>",
     "description": "...",
     "author": { "name": "Sebastian Gonzalez" },
     "category": "development",
     "source": "./plugins/<skill-name>"
   }
   ```

5. Write `plugins/<skill-name>/README.md` documenting prerequisites,
   install, usage, update, and uninstall for that specific skill — mirror
   `plugins/triage-pr/README.md`.

6. Add a row for it to the table in the root `README.md`.

## Validate and test before committing

Don't just eyeball the JSON — run the actual validator and a real
install/uninstall cycle:

```bash
claude plugin validate .                       # marketplace manifest
claude plugin validate ./plugins/<skill-name>   # plugin manifest

claude plugin marketplace add ./
claude plugin install <skill-name>@sebastialonso-skills
claude plugin list                              # confirm it shows up enabled

# clean up afterward so the test doesn't linger in your local config:
claude plugin uninstall <skill-name>
claude plugin marketplace remove sebastialonso-skills
```

## Known gotchas

- **Marketplace name is reserved-word sensitive.** `claude plugin
  marketplace add` rejects some names outright — e.g. `agent-skills` is
  reserved for Anthropic-org GitHub sources only, which is why the
  marketplace here is named `sebastialonso-skills` and not something more
  generic. If you ever rename it, every `@sebastialonso-skills` reference
  across both READMEs and this file needs updating too.
- **`.claude/settings.local.json` and `__pycache__/` are gitignored** —
  don't force-add them.
- Match existing style in files you're touching rather than reformatting
  unrelated content; keep changes scoped to the skill you're adding.
