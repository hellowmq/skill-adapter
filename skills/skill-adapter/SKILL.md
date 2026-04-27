---
name: skill-adapter
description: Use this skill when the user wants to convert, adapt, or port a skill between agent-tool specifications. Primary active ecosystem is CodeBuddy + WorkBuddy (accepts SKILL.md, slash commands, RULE.mdc as input, emits all three as output); also supports Claude Code, Hermes, Cursor, OpenClaw/GPT and MCP. Trigger on phrases like "把这个 skill 适配到 …"、"让这个 skill 跨工具使用"、"转换 skill 格式"、"slash command 转 skill"、"rule 转 skill"、"generate skill for multiple tools"、"port skill to". Auto-detects the source form (SKILL.md / commands/*.md / RULE.mdc) and produces per-tool artifacts in a dist/ directory.
---

# skill-adapter

A meta-skill that converts a skill package between the specs of multiple agent
tools. The **primary active ecosystem is CodeBuddy + WorkBuddy** (they share
`.codebuddy/` conventions), so this skill treats their three native forms —
**skill package**, **slash command**, **rule** — as first-class citizens on
both the input and output sides. Other target ecosystems (Claude Code, Hermes,
Cursor, OpenClaw, MCP) are supported as secondary fan-out targets.

## When to Use

- The user has a skill / command / rule in one tool and wants it in another.
- The user authors for CodeBuddy or WorkBuddy and wants all three native forms
  (skill, slash command, rule) produced from a single source.
- The user asks to "port / adapt / convert / migrate" a skill.
- The user mentions two or more of: `CodeBuddy`, `WorkBuddy`, `Claude Code`,
  `Hermes`, `Cursor`, `OpenClaw`, `GPT`, `MCP`.

Do NOT use for:
- Authoring the original skill content (that's the user's domain logic).
- Runtime skill execution (this skill only produces artifacts).

## Accepted Input Forms (auto-detected)

| Input | Detection | Normalized to |
|---|---|---|
| Directory with `SKILL.md` | YAML frontmatter with `name` + `description` | `anthropic-skill` |
| Directory with `RULE.mdc` | `.codebuddy/rules/<name>/RULE.mdc` | `codebuddy-rule` |
| A bare `.md` file | No frontmatter or frontmatter without `name` | `codebuddy-command` |
| A `.md` file with `name:` in frontmatter | — | `anthropic-skill` |

For rule/command inputs, `description` is derived from the first
non-heading line when absent; `name` falls back to the file/directory stem.

## Supported Output Targets

| Target | Output Format | Output Path |
|---|---|---|
| `codebuddy` **(default)** | All 3 native forms at once | `dist/codebuddy/.codebuddy/{skills,commands,rules}/<name>/...` |
| `workbuddy` **(default)** | Same tree as codebuddy (Knot-importable) | `dist/workbuddy/.codebuddy/...` |
| `codebuddy-command` | Only the slash command | `dist/codebuddy-command/.codebuddy/commands/<name>.md` |
| `codebuddy-rule` | Only the rule | `dist/codebuddy-rule/.codebuddy/rules/<name>/RULE.mdc` |
| `claude-code` | SKILL.md package | `dist/claude-code/<name>/` |
| `hermes` | SKILL.md package | `dist/hermes/<name>/` |
| `cursor` | `.cursor/rules/<name>.mdc` | `dist/cursor/...` |
| `openclaw` | System prompt + OpenAPI | `dist/openclaw/<name>/` |
| `mcp` | MCP stdio server (Node) | `dist/mcp/<name>/` |

`codebuddy` and `workbuddy` are **the default active targets** — if the user
just says "convert this skill", both get built automatically.

## Workflow

### Step 1 — Locate the source

Ask the user (or infer from context) for:
- a directory containing `SKILL.md` or `RULE.mdc`, **or**
- a single `.md` file (slash command or skill frontmatter file).

### Step 2 — Validate

```bash
python3 scripts/convert.py validate --src <path>
```

This auto-detects the source form, prints the detected kind, and warns on
missing `## When to Use` / `## Workflow` sections (only for `anthropic-skill`
sources — command / rule sources don't require them).

### Step 3 — Decide targets

If the user specifies targets, use them. Otherwise use the default list
(`codebuddy, workbuddy, claude-code, hermes, cursor, openclaw, mcp`) which
puts the active ecosystem first.

### Step 4 — Convert

```bash
python3 scripts/convert.py build --src <path> \
    [--targets codebuddy,workbuddy,cursor] \
    [--out <dir>] [--clean]
```

The converter will:
1. Normalize the source into a common `SourceSkill` (frontmatter + body +
   optional `scripts/` `references/` `assets/`).
2. For CodeBuddy / WorkBuddy targets, emit **all three native forms**
   (`skills/<name>/SKILL.md`, `commands/<name>.md`, `rules/<name>/RULE.mdc`)
   so the user can trigger the skill via description match, slash command,
   or rule activation.
3. For other targets, emit the native adapter files.
4. Write an `INSTALL.md` per target.

### Step 5 — Report

Point the user at `dist/` and summarize what was produced for each target.

## Quick Examples

Convert a slash command into a full cross-tool skill:
```bash
python3 scripts/convert.py build --src .codebuddy/commands/my-cmd.md
```

Convert a rule into its skill / command equivalents:
```bash
python3 scripts/convert.py build --src .codebuddy/rules/my-rule
```

Build only for CodeBuddy + WorkBuddy (the primary scenario):
```bash
python3 scripts/convert.py build --src ./my-skill --targets codebuddy,workbuddy
```

## Design Principles

1. **Active ecosystem first**: CodeBuddy / WorkBuddy are the default targets
   and accept any of their three native forms as input.
2. **SSOT stays simple**: regardless of input form, everything is normalized
   into a single `SourceSkill` (name + description + body + extras).
3. **Round-trip safety**: any of `skill ↔ command ↔ rule` conversions
   preserve `name` and `description` byte-exact; body content is wrapped, not
   mutated.
4. **No logic in prompts**: executable behavior lives in `scripts/` so every
   target just invokes the same CLI.
5. **Thin adapters**: each non-CodeBuddy target is a small wrapper.

## Extending

To add a new target, append an `@register("<name>")` function in
`scripts/convert.py` following the interface in `references/target-interface.md`.
No CLI changes required.

## References

- Full mapping rules: `references/mapping.md`
- Target plugin interface: `references/target-interface.md`
- Worked examples (incl. reverse conversions): `references/example.md`

