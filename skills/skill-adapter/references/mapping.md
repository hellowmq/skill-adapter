# Field Mapping Rules

Authoritative mapping between the **normalized `SourceSkill`** and each
supported input / output specification.

## Canonical source schema

Regardless of input form, the adapter normalizes everything to:

```
SourceSkill:
  name         : kebab-case identifier          (required)
  description  : 10–1024 chars, triggers         (required, auto-derived if missing)
  body         : Markdown                        (required)
  extra_dirs   : scripts/ | references/ | assets/ (optional, verbatim copy)
  source_kind  : anthropic-skill | codebuddy-command | codebuddy-rule
```

## Input form detection

| Input | Detection rule | `source_kind` |
|---|---|---|
| Dir with `SKILL.md` | `---` frontmatter with `name` + `description` | `anthropic-skill` |
| Dir with `RULE.mdc` | `---` frontmatter (CodeBuddy rule metadata) | `codebuddy-rule` |
| Dir with a single `*.md` command | no frontmatter, or frontmatter without `name` | `codebuddy-command` |
| File `foo.md` with `name:` | parsed as skill | `anthropic-skill` |
| File `foo.md` without `name:` | treated as a bare prompt | `codebuddy-command` |
| File `foo.mdc` | treated as rule | `codebuddy-rule` |

When a field is missing from the input, it's derived:
- `name` ← filename / directory stem
- `description` ← first non-heading body line, capped to 200 chars

## Per-target output mapping

### codebuddy (default, primary)

Emits the **full `.codebuddy/` tree with all three native forms** in one shot:

| Source field | Skill output | Command output | Rule output |
|---|---|---|---|
| `name` | frontmatter + dir | filename `/<name>.md` | dir name |
| `description` | frontmatter | one-liner under heading | `description:` in `.mdc` |
| `allowed-tools`, `disable` | preserved | — | — |
| — | — | — | `alwaysApply: false`, `enabled: true` (defaults) |
| body | verbatim | verbatim | verbatim |
| `scripts/`, `references/`, `assets/` | copied under skill dir | n/a | n/a |

Output path: `dist/codebuddy/.codebuddy/{skills,commands,rules}/<name>/...`

### workbuddy (default, primary)

WorkBuddy shares the CodeBuddy `.codebuddy/` convention (Knot-compatible).
Output is effectively the same tree as `codebuddy` without the extra
`allowed-tools` / `disable` fields. A zip of `skills/<name>/` is
Knot-importable via the settings page.

### codebuddy-command (standalone)

Emits only `.codebuddy/commands/<name>.md`. If the source had extras, they are
placed beside it under `_skill/<name>/` and referenced from the command body.

### codebuddy-rule (standalone)

Emits only `.codebuddy/rules/<name>/RULE.mdc`. Preserves `alwaysApply` /
`enabled` when present in the source, otherwise defaults to `false` / `true`.

### claude-code / hermes

Passthrough of the Anthropic `SKILL.md` package. Install under
`~/.claude/skills/<name>/` or `.hermes/skills/<name>/`.

### cursor

| Source | Target (`.cursor/rules/<name>.mdc`) |
|---|---|
| `name` | inferred from filename |
| `description` | `description:` in frontmatter |
| file-extension hints in body (backticked paths, "`.py` file" phrases) | `globs:` (auto-inferred, comma-separated) |
| body | appended as Markdown |
| `scripts/`, `references/`, `assets/` | copied under `_skill/<name>/` |
| — | `alwaysApply: false` (default) |

### openclaw / GPT-Actions

| Source | Target |
|---|---|
| `description` + body | `system_prompt.md` |
| name + description + scripts | `openapi.json` with single `run` operation |
| `scripts/` | must be hosted over HTTP by the user |

### mcp

| Source | Target |
|---|---|
| `name` | MCP server name + npm package name |
| `description` | tool description in `tools/list` |
| `scripts/run.{py,sh,js}` | auto-detected; server spawns the first match |
| no runner → body | `SKILL.md` returned as guidance text |

## Cross-form conversions (within CodeBuddy / WorkBuddy)

| From → To | What happens |
|---|---|
| skill → command | body transcribed under `# /<name>`; description becomes subtitle |
| skill → rule | body copied to `RULE.mdc`, frontmatter reduced to `description / alwaysApply / enabled` |
| command → skill | synthesizes `name` / `description`; body becomes the skill's instructions |
| command → rule | same normalization, then wrapped as rule |
| rule → skill | body becomes skill instructions; original rule metadata discarded from frontmatter |
| rule → command | body wrapped under `# /<name>` |

## Round-trip guarantees

- `name` is preserved byte-exact in every target that has such a field.
- `description` is preserved byte-exact in every target that has a description.
- Body content is never mutated, only wrapped.
- `scripts/`, `references/`, `assets/` are never mutated.

## Conflict resolution

- If a target already defines a conflicting field (e.g., Cursor `globs` set
  explicitly in the source), the explicit value wins; auto-inference only
  applies when absent.
- For CodeBuddy rule output, user-provided `alwaysApply` / `enabled` is
  preserved; otherwise safe defaults are used.
