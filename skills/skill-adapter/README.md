# skill-adapter

A meta-skill that converts a skill between multiple agent-tool specifications.
**Primary active ecosystem: CodeBuddy + WorkBuddy.** Accepts any of their
three native forms (SKILL.md / slash command / RULE.mdc) as input, and emits
all three as output — plus fan-out to Claude Code, Hermes, Cursor, OpenClaw,
and MCP.

## Quick Start

```bash
# Validate any skill / command / rule (auto-detects form)
python3 scripts/convert.py validate --src <path>

# Build for the default target set (CodeBuddy + WorkBuddy + 5 others)
python3 scripts/convert.py build --src <path>

# Build for selected targets only
python3 scripts/convert.py build \
    --src <path> \
    --targets codebuddy,workbuddy,cursor
```

Outputs land in `<src>/dist/<target>/...` with a per-target `INSTALL.md`.

## Accepted Inputs (auto-detected)

- **Anthropic skill dir**: `<dir>/SKILL.md` + optional `scripts/`, `references/`, `assets/`
- **CodeBuddy rule dir**: `<dir>/RULE.mdc`
- **CodeBuddy slash command file**: a bare `.md` file (with or without frontmatter)

## Output Targets

**Primary (built by default):**
- `codebuddy` — all 3 native forms at once
- `workbuddy` — same tripartite tree, Knot-importable
- `claude-code`, `hermes` — SKILL.md passthrough
- `cursor` — `.mdc` with auto-inferred `globs`
- `openclaw` — system prompt + OpenAPI
- `mcp` — executable Node stdio server

**Additional (on request):**
- `codebuddy-command` — only the slash command form
- `codebuddy-rule` — only the rule form

## Docs

- `SKILL.md` — full spec & workflow
- `references/mapping.md` — authoritative field mapping
- `references/example.md` — worked examples (incl. reverse conversions)
- `references/target-interface.md` — how to add a new target
