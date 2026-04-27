# Worked Examples

All three examples below exercise a different **source form**, showing that
the adapter treats CodeBuddy's native forms as first-class citizens.

---

## Example A — Anthropic SKILL.md as source (fan-out)

### Input

```
my-pdf-skill/
├── SKILL.md
└── scripts/run.py
```

`SKILL.md`:

```markdown
---
name: pdf-helper
description: Use when the user works with .pdf files — extract, merge, split, or fill PDF forms.
---

# pdf-helper

## When to Use
- The user references a `.pdf` file.
- The user asks to merge/split/rotate/OCR a PDF.

## Workflow
1. Parse the user's intent.
2. Call `scripts/run.py <subcommand> <args>`.
3. Return the output path.
```

### Run

```bash
python3 scripts/convert.py build --src ./my-pdf-skill
```

### Output (abbreviated)

```
dist/
├── codebuddy/.codebuddy/
│   ├── skills/pdf-helper/SKILL.md   (+ scripts/)
│   ├── commands/pdf-helper.md       # /pdf-helper
│   └── rules/pdf-helper/RULE.mdc
├── workbuddy/.codebuddy/...         # same tripartite tree
├── claude-code/pdf-helper/SKILL.md
├── hermes/pdf-helper/SKILL.md
├── cursor/.cursor/rules/pdf-helper.mdc  (globs: **/*.pdf)
├── openclaw/pdf-helper/{system_prompt.md, openapi.json}
└── mcp/pdf-helper/{server.mjs, package.json}
```

One source → 3 CodeBuddy forms + 5 other ecosystems, no manual editing.

---

## Example B — CodeBuddy slash command as source (reverse)

### Input

A bare prompt file the user wrote as a CodeBuddy slash command, with **no
frontmatter**:

```
.codebuddy/commands/pre-mr-checklist.md
```

```markdown
# 代码提交前综合检查

对改动代码进行全面检查：依赖项审计、代码安全审查、基础设施安全。
输出 Markdown checklist。
```

### Run

```bash
python3 scripts/convert.py build --src .codebuddy/commands/pre-mr-checklist.md
```

### What happens

The adapter detects `source_kind = codebuddy-command`:
- `name` ← `pre-mr-checklist` (from filename)
- `description` ← `对改动代码进行全面检查：依赖项审计、代码安全审查、基础设施安全。`
  (first non-heading line)

### Output

```
dist/codebuddy/.codebuddy/
├── skills/pre-mr-checklist/SKILL.md    # auto-matched by description
├── commands/pre-mr-checklist.md        # /pre-mr-checklist (identity)
└── rules/pre-mr-checklist/RULE.mdc     # @pre-mr-checklist
dist/cursor/.cursor/rules/pre-mr-checklist.mdc
dist/claude-code/pre-mr-checklist/SKILL.md
...
```

The originally-prompt-only command is now available as a proper skill (with
metadata), as a rule (for auto-loading), and across other tools.

---

## Example C — CodeBuddy rule as source (reverse)

### Input

```
.codebuddy/rules/typescript-style/RULE.mdc
```

```markdown
---
description: TypeScript project coding style
alwaysApply: true
enabled: true
---

# TypeScript Style

- 使用 4 空格缩进
- 单引号、行末分号
- 函数必须有 JSDoc
```

### Run

```bash
python3 scripts/convert.py build \
    --src .codebuddy/rules/typescript-style \
    --targets codebuddy,cursor,claude-code
```

### What happens

The adapter detects `source_kind = codebuddy-rule`:
- `name` ← `typescript-style`
- `description` ← kept from frontmatter

### Output

```
dist/codebuddy/.codebuddy/
├── skills/typescript-style/SKILL.md    # wraps the style guide as a skill
├── commands/typescript-style.md        # /typescript-style to invoke on demand
└── rules/typescript-style/RULE.mdc     # identity output
dist/cursor/.cursor/rules/typescript-style.mdc
dist/claude-code/typescript-style/SKILL.md
```

The rule is now also a skill (agent can pick it up by description) and
available as a Cursor rule for anyone using Cursor on the same repo.

---

## How an Agent "auto-recognizes" the converted skill

The converter produces **per-tool native artifacts**. Each host agent
discovers them via its own normal mechanisms:

- CodeBuddy IDE / WorkBuddy
  - Skill package → semantic match on `description`.
  - Slash command → explicit `/<name>` trigger.
  - Rule → `alwaysApply: true` or `@<name>` reference.
- Claude Code / Hermes → `description` semantic match.
- Cursor → `description` + inferred `globs` activate the rule.
- OpenClaw / GPT → system prompt + `run` action.
- MCP-capable agents → the MCP tool is auto-listed.

No "skill-adapter aware" consumer is required — each tool sees a first-class,
native skill.
