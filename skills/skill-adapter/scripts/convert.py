#!/usr/bin/env python3
"""
skill-adapter: convert a skill package between multiple agent-tool specifications.

Primary (native) formats — auto-detected on input, first-class on output:
    - anthropic-skill   : SKILL.md + scripts/references/assets  (Claude Code / Hermes / CodeBuddy skills)
    - codebuddy-command : a bare Markdown prompt under commands/  (/<name> slash command)
    - codebuddy-rule    : RULE.mdc with description/alwaysApply frontmatter

Usage:
    python3 convert.py validate --src <dir-or-file>
    python3 convert.py build    --src <dir-or-file> [--out <dir>] [--targets a,b,c]

Supported output targets:
    claude-code, codebuddy, codebuddy-command, codebuddy-rule,
    workbuddy, hermes, cursor, openclaw, mcp
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# Frontmatter parsing (no PyYAML dependency; we support the subset we need)
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("SKILL.md must start with YAML frontmatter delimited by '---'.")
    raw, body = m.group(1), m.group(2)
    meta: dict = {}
    current_key: str | None = None
    buffer: list[str] = []

    def flush():
        nonlocal buffer, current_key
        if current_key is not None:
            joined = " ".join(s.strip() for s in buffer).strip()
            # strip surrounding quotes
            if (joined.startswith('"') and joined.endswith('"')) or (
                joined.startswith("'") and joined.endswith("'")
            ):
                joined = joined[1:-1]
            meta[current_key] = joined
        buffer = []

    for line in raw.splitlines():
        if not line.strip():
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*\s*:", line):
            flush()
            key, _, rest = line.partition(":")
            current_key = key.strip()
            buffer = [rest.strip()] if rest.strip() else []
        else:
            # continuation line
            buffer.append(line.strip())
    flush()
    return meta, body


def dump_frontmatter(meta: dict) -> str:
    lines = ["---"]
    for k, v in meta.items():
        if v is None:
            continue
        sv = str(v).replace("\n", " ").strip()
        # quote if contains ':' or starts with special chars
        needs_quote = any(c in sv for c in [":", "#", "'", '"']) or sv != sv.strip()
        if needs_quote:
            sv = '"' + sv.replace('"', '\\"') + '"'
        lines.append(f"{k}: {sv}")
    lines.append("---")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Source skill model
# ---------------------------------------------------------------------------


@dataclass
class SourceSkill:
    src_dir: Path
    meta: dict
    body: str
    extra_dirs: list[str] = field(default_factory=list)
    source_kind: str = "anthropic-skill"  # anthropic-skill | codebuddy-command | codebuddy-rule

    @property
    def name(self) -> str:
        return self.meta["name"]

    @property
    def description(self) -> str:
        return self.meta.get("description", "")

    # --- Loaders ----------------------------------------------------------

    @classmethod
    def load(cls, src: Path) -> "SourceSkill":
        """Auto-detect the source form and normalize to a SourceSkill.

        Accepted forms:
          1. Directory containing SKILL.md (Anthropic/CodeBuddy/Hermes skill package).
          2. Directory containing RULE.mdc (CodeBuddy rule).
          3. A bare .md file with no frontmatter   -> codebuddy-command.
          4. A .md file with frontmatter + `name`  -> treated as skill.
        """
        src = Path(src)
        if src.is_dir():
            skill_md = src / "SKILL.md"
            rule_mdc = src / "RULE.mdc"
            if skill_md.exists():
                return cls._load_skill_md(src, skill_md)
            if rule_mdc.exists():
                return cls._load_rule_mdc(src, rule_mdc)
            # Directory of slash commands — pick single *.md if unique
            mds = [p for p in src.glob("*.md") if p.name.lower() != "readme.md"]
            if len(mds) == 1:
                return cls._load_command_md(mds[0])
            raise FileNotFoundError(
                f"{src} contains neither SKILL.md nor RULE.mdc; "
                "if it's a slash-command dir, pass the .md file directly."
            )
        if src.is_file():
            if src.name == "RULE.mdc":
                return cls._load_rule_mdc(src.parent, src)
            if src.suffix.lower() in (".md", ".mdc"):
                text = src.read_text(encoding="utf-8")
                if FRONTMATTER_RE.match(text):
                    if src.name == "SKILL.md":
                        return cls._load_skill_md(src.parent, src)
                    # mdc with frontmatter -> treat as rule
                    if src.suffix.lower() == ".mdc":
                        return cls._load_rule_mdc(src.parent, src)
                    # .md with frontmatter: if it has `name:` treat as skill, else command
                    meta, _ = parse_frontmatter(text)
                    if "name" in meta:
                        return cls._load_skill_md(src.parent, src)
                return cls._load_command_md(src)
        raise FileNotFoundError(f"Unsupported source: {src}")

    @classmethod
    def _load_skill_md(cls, src_dir: Path, path: Path) -> "SourceSkill":
        meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        for required in ("name", "description"):
            if required not in meta or not meta[required]:
                raise ValueError(f"{path} frontmatter missing required field: {required}")
        extras = [
            d for d in ("scripts", "references", "assets") if (src_dir / d).is_dir()
        ]
        return cls(
            src_dir=src_dir, meta=meta, body=body, extra_dirs=extras,
            source_kind="anthropic-skill",
        )

    @classmethod
    def _load_command_md(cls, path: Path) -> "SourceSkill":
        text = path.read_text(encoding="utf-8")
        # A command file may or may not carry frontmatter; parse best-effort.
        if FRONTMATTER_RE.match(text):
            meta, body = parse_frontmatter(text)
        else:
            meta, body = {}, text
        name = meta.get("name") or path.stem
        # Derive description: first non-empty, non-heading line, capped to ~200 chars.
        description = meta.get("description") or _first_sentence(body) or f"Slash command /{name}"
        meta = {**meta, "name": name, "description": description}
        return cls(
            src_dir=path.parent, meta=meta, body=body.strip(),
            extra_dirs=[], source_kind="codebuddy-command",
        )

    @classmethod
    def _load_rule_mdc(cls, src_dir: Path, path: Path) -> "SourceSkill":
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        name = meta.get("name") or src_dir.name or path.stem
        description = meta.get("description") or _first_sentence(body) or f"Rule {name}"
        meta = {**meta, "name": name, "description": description}
        extras = [
            d for d in ("scripts", "references", "assets") if (src_dir / d).is_dir()
        ]
        return cls(
            src_dir=src_dir, meta=meta, body=body, extra_dirs=extras,
            source_kind="codebuddy-rule",
        )

    # --- Utilities --------------------------------------------------------

    def copy_extras(self, dest: Path) -> None:
        for d in self.extra_dirs:
            src = self.src_dir / d
            dst = dest / d
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)


def _first_sentence(body: str, max_len: int = 200) -> str:
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("---"):
            continue
        # Strip markdown emphasis
        cleaned = re.sub(r"[*_`]+", "", line)
        return cleaned[:max_len]
    return ""


# ---------------------------------------------------------------------------
# Target plugins
# ---------------------------------------------------------------------------


TargetFn = Callable[[SourceSkill, Path], None]
TARGETS: dict[str, TargetFn] = {}


def register(name: str):
    def deco(fn: TargetFn):
        TARGETS[name] = fn
        return fn

    return deco


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _install_md(path: Path, content: str) -> None:
    _write(path / "INSTALL.md", content)


@register("claude-code")
def build_claude_code(skill: SourceSkill, out: Path) -> None:
    dest = out / "claude-code" / skill.name
    dest.mkdir(parents=True, exist_ok=True)
    _write(dest / "SKILL.md", dump_frontmatter(skill.meta) + skill.body)
    skill.copy_extras(dest)
    _install_md(
        out / "claude-code",
        f"""# Claude Code installation

Copy `{skill.name}/` into one of:

- Project-level:  `<repo>/.claude/skills/{skill.name}/`
- User-level:     `~/.claude/skills/{skill.name}/`

Then restart Claude Code; the skill is auto-discovered by its `description`.
""",
    )


@register("codebuddy")
def build_codebuddy(skill: SourceSkill, out: Path) -> None:
    """First-class CodeBuddy output: produce ALL three native forms.

    Layout mirrors a real `.codebuddy/` tree so the user can drop it in place:
        dist/codebuddy/.codebuddy/skills/<name>/SKILL.md + extras
        dist/codebuddy/.codebuddy/commands/<name>.md
        dist/codebuddy/.codebuddy/rules/<name>/RULE.mdc
    """
    root = out / "codebuddy" / ".codebuddy"

    # --- 1) skill package ------------------------------------------------
    skill_dir = root / "skills" / skill.name
    skill_dir.mkdir(parents=True, exist_ok=True)
    # CodeBuddy accepts Anthropic-style frontmatter + two optional fields.
    cb_meta = {
        "name": skill.meta["name"],
        "description": skill.meta["description"],
    }
    if "allowed-tools" in skill.meta:
        cb_meta["allowed-tools"] = skill.meta["allowed-tools"]
    if "disable" in skill.meta:
        cb_meta["disable"] = skill.meta["disable"]
    _write(skill_dir / "SKILL.md", dump_frontmatter(cb_meta) + skill.body)
    skill.copy_extras(skill_dir)

    # --- 2) slash command ------------------------------------------------
    cmd_path = root / "commands" / f"{skill.name}.md"
    cmd_body = f"""# /{skill.name}

> {skill.description}

{skill.body.strip()}
"""
    _write(cmd_path, cmd_body)

    # --- 3) rule ---------------------------------------------------------
    rule_dir = root / "rules" / skill.name
    rule_meta = {
        "description": skill.description,
        "alwaysApply": "false",
        "enabled": "true",
    }
    _write(rule_dir / "RULE.mdc", dump_frontmatter(rule_meta) + skill.body)

    _install_md(
        out / "codebuddy",
        f"""# CodeBuddy / WorkBuddy installation

This target emits all THREE native CodeBuddy forms. Pick whichever entry point
matches your use case:

| Form | Path | Trigger |
|---|---|---|
| Skill package | `.codebuddy/skills/{skill.name}/` | Auto-matched via description |
| Slash command | `.codebuddy/commands/{skill.name}.md` | Type `/{skill.name}` in chat |
| Rule | `.codebuddy/rules/{skill.name}/RULE.mdc` | `@{skill.name}` or alwaysApply |

Merge the `.codebuddy/` tree in this directory into your project (or user home)
`.codebuddy/`. The same tree works for both the CodeBuddy IDE and WorkBuddy.

Source kind detected: `{skill.source_kind}`
""",
    )


@register("codebuddy-command")
def build_codebuddy_command(skill: SourceSkill, out: Path) -> None:
    """Emit ONLY the CodeBuddy slash-command form."""
    dest = out / "codebuddy-command"
    path = dest / ".codebuddy" / "commands" / f"{skill.name}.md"
    body = f"""# /{skill.name}

> {skill.description}

{skill.body.strip()}
"""
    _write(path, body)
    if skill.extra_dirs:
        skill.copy_extras(dest / "_skill" / skill.name)
    _install_md(
        dest,
        f"""# CodeBuddy slash command — standalone

Drop `.codebuddy/commands/{skill.name}.md` into your project's `.codebuddy/commands/`
directory (or the user-level equivalent `~/.codebuddy/commands/`).
Trigger with `/{skill.name}` in the chat input.
""",
    )


@register("codebuddy-rule")
def build_codebuddy_rule(skill: SourceSkill, out: Path) -> None:
    """Emit ONLY the CodeBuddy rule form."""
    dest = out / "codebuddy-rule"
    rule_dir = dest / ".codebuddy" / "rules" / skill.name
    rule_meta = {
        "description": skill.description,
        "alwaysApply": skill.meta.get("alwaysApply", "false"),
        "enabled": skill.meta.get("enabled", "true"),
    }
    _write(rule_dir / "RULE.mdc", dump_frontmatter(rule_meta) + skill.body)
    if skill.extra_dirs:
        skill.copy_extras(dest / "_skill" / skill.name)
    _install_md(
        dest,
        f"""# CodeBuddy rule — standalone

Drop `.codebuddy/rules/{skill.name}/` into your project's `.codebuddy/rules/`
directory. Flip `alwaysApply: true` in the `RULE.mdc` frontmatter if you want
the rule loaded on every conversation, otherwise use `@{skill.name}` to invoke.
""",
    )


@register("workbuddy")
def build_workbuddy(skill: SourceSkill, out: Path) -> None:
    """WorkBuddy shares the CodeBuddy directory layout (skills + commands + rules).

    We emit the same tripartite bundle plus a Knot-importable zip hint.
    """
    root = out / "workbuddy" / ".codebuddy"

    skill_dir = root / "skills" / skill.name
    skill_dir.mkdir(parents=True, exist_ok=True)
    _write(
        skill_dir / "SKILL.md",
        dump_frontmatter(
            {"name": skill.name, "description": skill.description}
        ) + skill.body,
    )
    skill.copy_extras(skill_dir)

    _write(
        root / "commands" / f"{skill.name}.md",
        f"""# /{skill.name}

> {skill.description}

{skill.body.strip()}
""",
    )

    _install_md(
        out / "workbuddy",
        f"""# WorkBuddy installation

WorkBuddy reuses the CodeBuddy `.codebuddy/` convention. Two options:

1. **Direct drop-in**: merge the `.codebuddy/` tree in this directory with your
   workspace's `.codebuddy/` (or user-level `~/.codebuddy/`).
2. **Knot import (zip)**: zip `.codebuddy/skills/{skill.name}/` and import via
   the WorkBuddy / CodeBuddy settings page → "导入 Skill".

Trigger forms after install:
- Auto-match:   describe your task, the agent picks the skill by description.
- Slash:        `/{skill.name}`
- Explicit:     `@Skills` then pick `{skill.name}`.
""",
    )


@register("hermes")
def build_hermes(skill: SourceSkill, out: Path) -> None:
    dest = out / "hermes" / skill.name
    dest.mkdir(parents=True, exist_ok=True)
    _write(dest / "SKILL.md", dump_frontmatter(skill.meta) + skill.body)
    skill.copy_extras(dest)
    _install_md(
        out / "hermes",
        f"""# Hermes installation

Place `{skill.name}/` under the Hermes skills directory
(configurable; commonly `~/.hermes/skills/` or project-level `.hermes/skills/`).
Hermes is compatible with the Anthropic SKILL.md format.
""",
    )


GLOB_HINT_RE = re.compile(r"`([^`\s]+\.\w{1,6})`|\.(\w{1,6})\s+file", re.IGNORECASE)


def _infer_globs(body: str) -> list[str]:
    globs: set[str] = set()
    for m in GLOB_HINT_RE.finditer(body):
        token = m.group(1) or (m.group(2) and f"*.{m.group(2).lower()}")
        if not token:
            continue
        if "." in token and not token.startswith("."):
            ext = token.split(".")[-1].lower()
            if 1 <= len(ext) <= 6 and ext.isalnum():
                globs.add(f"**/*.{ext}")
    return sorted(globs)


@register("cursor")
def build_cursor(skill: SourceSkill, out: Path) -> None:
    dest = out / "cursor"
    rules_dir = dest / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    globs = _infer_globs(skill.body)
    fm = {
        "description": skill.description,
        "globs": ", ".join(globs) if globs else "",
        "alwaysApply": "false",
    }
    # Cursor .mdc uses a similar frontmatter; keep empty fields out
    fm = {k: v for k, v in fm.items() if v != ""}

    adapter_body = f"""# {skill.name}

> Ported from Anthropic SKILL.md by skill-adapter.

{skill.body.strip()}
"""
    _write(rules_dir / f"{skill.name}.mdc", dump_frontmatter(fm) + adapter_body)

    # Scripts / references / assets go alongside so relative paths still work.
    skill.copy_extras(dest / "_skill" / skill.name)
    if skill.extra_dirs:
        note = (
            f"\n> Runtime assets are at `_skill/{skill.name}/`. "
            "Adjust script paths if your project layout differs.\n"
        )
        mdc = rules_dir / f"{skill.name}.mdc"
        mdc.write_text(mdc.read_text(encoding="utf-8") + note, encoding="utf-8")

    _install_md(
        dest,
        f"""# Cursor installation

1. Merge the `.cursor/rules/{skill.name}.mdc` into your repo's `.cursor/rules/`.
2. If the skill uses scripts/references/assets, copy `_skill/{skill.name}/` to a
   stable location in your repo and update paths in the `.mdc` if needed.
3. Cursor will pick the rule up via description match and inferred globs.
""",
    )


@register("openclaw")
def build_openclaw(skill: SourceSkill, out: Path) -> None:
    dest = out / "openclaw" / skill.name
    dest.mkdir(parents=True, exist_ok=True)

    system_prompt = f"""You have a skill called "{skill.name}".

{skill.description}

Follow the workflow below exactly when the skill is triggered.

{skill.body.strip()}
"""
    _write(dest / "system_prompt.md", system_prompt)

    # Minimal OpenAPI stub describing a single "run" action that execs scripts/
    openapi = {
        "openapi": "3.1.0",
        "info": {"title": skill.name, "version": "1.0.0", "description": skill.description},
        "paths": {
            f"/{skill.name}/run": {
                "post": {
                    "operationId": f"{skill.name.replace('-', '_')}_run",
                    "summary": skill.description,
                    "requestBody": {
                        "required": False,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "args": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        }
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    _write(dest / "openapi.json", json.dumps(openapi, indent=2, ensure_ascii=False))
    skill.copy_extras(dest)

    _install_md(
        out / "openclaw",
        f"""# OpenClaw / GPT-Actions installation

- Paste the contents of `{skill.name}/system_prompt.md` into the custom GPT's
  **Instructions** field.
- Upload `{skill.name}/openapi.json` as a custom action (adjust the host/base
  URL to point at wherever you host the `scripts/` as an HTTP endpoint).
""",
    )


MCP_SERVER_TEMPLATE = '''#!/usr/bin/env node
/**
 * Minimal MCP server wrapping the "{name}" skill.
 * Exposes a single tool `{tool}` that shells out to scripts/run.* if present,
 * otherwise returns the skill's workflow as guidance text.
 */
import {{ Server }} from "@modelcontextprotocol/sdk/server/index.js";
import {{ StdioServerTransport }} from "@modelcontextprotocol/sdk/server/stdio.js";
import {{ spawn }} from "node:child_process";
import {{ readFileSync, existsSync }} from "node:fs";
import path from "node:path";
import {{ fileURLToPath }} from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const GUIDE = readFileSync(path.join(__dirname, "SKILL.md"), "utf8");

const server = new Server(
  {{ name: "{name}", version: "1.0.0" }},
  {{ capabilities: {{ tools: {{}} }} }}
);

server.setRequestHandler("tools/list", async () => ({{
  tools: [
    {{
      name: "{tool}",
      description: {desc_json},
      inputSchema: {{
        type: "object",
        properties: {{
          args: {{ type: "array", items: {{ type: "string" }} }}
        }}
      }}
    }}
  ]
}}));

server.setRequestHandler("tools/call", async (req) => {{
  if (req.params.name !== "{tool}") {{
    return {{ content: [{{ type: "text", text: "Unknown tool" }}], isError: true }};
  }}
  const runners = ["scripts/run.py", "scripts/run.sh", "scripts/run.js"];
  const found = runners.map(r => path.join(__dirname, r)).find(existsSync);
  if (!found) {{
    return {{ content: [{{ type: "text", text: GUIDE }}] }};
  }}
  const args = (req.params.arguments?.args) ?? [];
  const cmd = found.endsWith(".py") ? "python3"
            : found.endsWith(".sh") ? "bash"
            : "node";
  return await new Promise((resolve) => {{
    const p = spawn(cmd, [found, ...args]);
    let out = "", err = "";
    p.stdout.on("data", d => out += d);
    p.stderr.on("data", d => err += d);
    p.on("close", code => resolve({{
      content: [{{ type: "text", text: out || err || `exit ${{code}}` }}],
      isError: code !== 0
    }}));
  }});
}});

await server.connect(new StdioServerTransport());
'''


@register("mcp")
def build_mcp(skill: SourceSkill, out: Path) -> None:
    dest = out / "mcp" / skill.name
    dest.mkdir(parents=True, exist_ok=True)

    tool_name = skill.name.replace("-", "_")
    _write(
        dest / "server.mjs",
        MCP_SERVER_TEMPLATE.format(
            name=skill.name,
            tool=tool_name,
            desc_json=json.dumps(skill.description, ensure_ascii=False),
        ),
    )
    _write(
        dest / "package.json",
        json.dumps(
            {
                "name": f"mcp-skill-{skill.name}",
                "version": "1.0.0",
                "type": "module",
                "bin": {f"mcp-skill-{skill.name}": "./server.mjs"},
                "dependencies": {"@modelcontextprotocol/sdk": "^1.0.0"},
            },
            indent=2,
        ),
    )
    _write(dest / "SKILL.md", dump_frontmatter(skill.meta) + skill.body)
    skill.copy_extras(dest)

    _install_md(
        out / "mcp",
        f"""# MCP server installation

```bash
cd {skill.name}
npm install
```

Register in any MCP-compatible client (Claude Code, Cursor, CodeBuddy, ...):

```json
{{
  "mcpServers": {{
    "{skill.name}": {{
      "command": "node",
      "args": ["{{absolute-path}}/{skill.name}/server.mjs"]
    }}
  }}
}}
```
""",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> int:
    skill = SourceSkill.load(Path(args.src).resolve())
    desc_len = len(skill.description)
    issues: list[str] = []
    if desc_len < 10:
        issues.append(f"description is very short ({desc_len} chars); agents may fail to match it.")
    if desc_len > 1024:
        issues.append(f"description is long ({desc_len} chars); consider trimming.")
    # For skills we recommend the two canonical sections; not for raw commands/rules.
    if skill.source_kind == "anthropic-skill":
        if "## When to Use" not in skill.body:
            issues.append('Recommended section "## When to Use" not found.')
        if "## Workflow" not in skill.body:
            issues.append('Recommended section "## Workflow" not found.')

    print(f"Skill:       {skill.name}")
    print(f"Source kind: {skill.source_kind}")
    print(f"  description ({desc_len} chars): {skill.description[:80]}{'...' if desc_len > 80 else ''}")
    print(f"  extra dirs: {', '.join(skill.extra_dirs) or '(none)'}")
    if issues:
        print("  WARNINGS:")
        for i in issues:
            print(f"   - {i}")
    else:
        print("  OK")
    return 0


# Default target order: CodeBuddy / WorkBuddy first (primary active ecosystem),
# then the broader multi-tool fan-out.
DEFAULT_TARGETS = [
    "codebuddy",
    "workbuddy",
    "claude-code",
    "hermes",
    "cursor",
    "openclaw",
    "mcp",
]


def cmd_build(args: argparse.Namespace) -> int:
    src = Path(args.src).resolve()
    skill = SourceSkill.load(src)
    out = Path(args.out).resolve() if args.out else src / "dist"
    if out.exists() and args.clean:
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    requested = args.targets.split(",") if args.targets else list(DEFAULT_TARGETS)
    unknown = [t for t in requested if t not in TARGETS]
    if unknown:
        print(f"Unknown targets: {unknown}. Available: {list(TARGETS)}", file=sys.stderr)
        return 2

    for t in requested:
        print(f"[build] {t}")
        TARGETS[t](skill, out)

    print(f"\nDone. Artifacts in: {out}")
    for t in requested:
        install = out / t / "INSTALL.md"
        if install.exists():
            print(f"  - {t}: see {install.relative_to(out.parent)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skill-adapter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate", help="Validate a source SKILL.md package")
    p_val.add_argument("--src", required=True, help="Path to directory containing SKILL.md")
    p_val.set_defaults(func=cmd_validate)

    p_build = sub.add_parser("build", help="Build multi-target artifacts")
    p_build.add_argument("--src", required=True)
    p_build.add_argument("--out", default=None, help="Output dir (default: <src>/dist)")
    p_build.add_argument(
        "--targets",
        default=None,
        help=f"Comma-separated. Default: {','.join(DEFAULT_TARGETS)}. "
             f"Also available: {','.join(sorted(set(TARGETS) - set(DEFAULT_TARGETS)))}",
    )
    p_build.add_argument("--clean", action="store_true", help="Wipe output dir first")
    p_build.set_defaults(func=cmd_build)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
