# sebastialonso-skills

A personal collection of public [Claude Code](https://claude.com/claude-code)
skills, distributed as a single plugin marketplace.

## Add the marketplace

```bash
claude plugin marketplace add sebastialonso/skills
```

Or, from inside an interactive Claude Code session:

```
/plugin marketplace add sebastialonso/skills
```

You only need to do this once — after that, install any skill below by
name.

## Skills

| Skill | What it does | Install |
|-------|---------------|---------|
| [triage-pr](plugins/triage-pr) | Triage every review and conversation comment on a GitHub PR into one decision table, get an explicit Approve/Ignore call on each item, then implement what's approved. | `claude plugin install triage-pr@sebastialonso-skills` |

See each skill's own README (linked above) for detailed prerequisites and
usage.

## Update / uninstall the marketplace itself

```bash
claude plugin marketplace update sebastialonso-skills
claude plugin marketplace remove sebastialonso-skills
```

Updating or removing an individual skill is covered in its own README.
