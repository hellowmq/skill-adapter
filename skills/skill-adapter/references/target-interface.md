# Target Plugin Interface

A "target" is a function that converts a parsed `SourceSkill` into artifacts
under a dedicated subdirectory of the output path.

## Signature

```python
TargetFn = Callable[[SourceSkill, Path], None]
```

Where:

- `SourceSkill` exposes:
  - `name: str`
  - `description: str`
  - `meta: dict` — full frontmatter
  - `body: str` — Markdown body (frontmatter stripped)
  - `src_dir: Path`
  - `extra_dirs: list[str]` — subset of `["scripts","references","assets"]`
  - `copy_extras(dest: Path) -> None`
- `out: Path` is the root `dist/` directory. The target MUST write under
  `out/<target-name>/`.

## Registration

```python
@register("my-tool")
def build_my_tool(skill: SourceSkill, out: Path) -> None:
    dest = out / "my-tool" / skill.name
    dest.mkdir(parents=True, exist_ok=True)
    # ... write transformed files ...
    skill.copy_extras(dest)
```

## Requirements

1. **Deterministic**: given the same input, produce byte-identical output.
2. **Self-contained**: the target's directory must be installable on its own.
3. **Include an `INSTALL.md`** at `out/<target-name>/INSTALL.md` explaining
   where the user should place the artifacts.
4. **Never mutate source files**; only read from `skill.src_dir`.
5. **Preserve** `scripts/`, `references/`, `assets/` relative paths whenever
   the target supports arbitrary files.

## Adding a new target

1. Append a new `@register("<name>")` function to `scripts/convert.py`.
2. Update `references/mapping.md` with the field mapping table.
3. Add a one-liner to `SKILL.md`'s "Supported Target Specifications" table.

No other changes required — the CLI picks it up via the `TARGETS` registry.
