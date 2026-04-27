# skill-adapter

> 一份 Skill，适配所有工具。

**skill-adapter** 是一个「元技能」（meta-skill），能将一份技能包在 **CodeBuddy、WorkBuddy、Claude Code、Hermes、Cursor、OpenClaw/GPT、MCP** 之间自由转换。

## 为什么需要它

各 Agent 工具的技能规范各不相同——有的用 `SKILL.md`，有的用 `.mdc` 规则，有的用斜杠命令。手动维护多套格式既低效又易出错。skill-adapter **以 CodeBuddy / WorkBuddy 为主阵地**，一行命令完成：

- 斜杠命令 → 完整 skill 包 + 规则 + 其他生态产物
- 规则 → skill + 命令 + 其他生态产物
- Anthropic skill → CodeBuddy 三件套（skill / command / rule）+ Cursor / OpenClaw / MCP ...

## 快速开始

```bash
# 校验任意 skill / command / rule（自动识别来源形态）
python3 skills/skill-adapter/scripts/convert.py validate --src <路径>

# 一键构建所有默认目标
python3 skills/skill-adapter/scripts/convert.py build --src <路径>

# 仅构建指定目标
python3 skills/skill-adapter/scripts/convert.py build \
    --src <路径> --targets codebuddy,cursor,mcp
```

产出在 `<src>/dist/<target>/` 下，每个目标附带 `INSTALL.md` 说明如何安装。

## 支持的输入形态（自动检测）

| 输入 | 识别为 |
|---|---|
| 目录含 `SKILL.md` | Anthropic skill 包 |
| 目录含 `RULE.mdc` | CodeBuddy 规则 |
| 单个 `.md` 文件（无 frontmatter） | CodeBuddy 斜杠命令 |
| 单个 `.md` 文件（含 `name:` frontmatter） | Anthropic skill |

## 支持的输出目标

| 目标 | 产物 | 默认构建 |
|---|---|---|
| `codebuddy` | skill + 斜杠命令 + rule 三件套 | ✓ |
| `workbuddy` | 同上（Knot 可导入） | ✓ |
| `claude-code` | `SKILL.md` 包 | ✓ |
| `hermes` | `SKILL.md` 包 | ✓ |
| `cursor` | `.cursor/rules/<name>.mdc` | ✓ |
| `openclaw` | system prompt + OpenAPI | ✓ |
| `mcp` | Node.js MCP stdio server | ✓ |
| `codebuddy-command` | 仅斜杠命令 | 按需 |
| `codebuddy-rule` | 仅规则 | 按需 |

## 项目结构

```
.
├── README.md                                   ← 你正在看的文件
├── skills/skill-adapter/
│   ├── SKILL.md                                # Skill 定义（Anthropic 规范）
│   ├── README.md                               # Skill 内部说明
│   ├── scripts/
│   │   └── convert.py                          # 核心转换引擎（零依赖 Python 3）
│   ├── references/
│   │   ├── mapping.md                          # 字段映射规则
│   │   ├── example.md                          # 完整输入→输出示例
│   │   └── target-interface.md                 # 新增目标的插件接口
│   └── examples/                               # 可运行的示例 fixtures
│       ├── anthropic-skill/                    # SKILL.md 输入示例
│       ├── codebuddy-command/                  # 斜杠命令输入示例
│       └── codebuddy-rule/                     # 规则输入示例
└── .gitignore
```

## 作为 CodeBuddy Skill 安装使用

```bash
# 项目级
cp -r skills/skill-adapter .codebuddy/skills/

# 用户级（全局生效）
cp -r skills/skill-adapter ~/.codebuddy/skills/
```

安装后在对话中直接说「把这个 command 转成 skill」即可自动触发。

## 扩展

在 `scripts/convert.py` 中添加一个 `@register("<新工具名>")` 函数即可支持新目标，无需改动 CLI 或其他文件。详见 `references/target-interface.md`。

## 依赖

- Python 3.9+（标准库，零第三方依赖）
- MCP 目标需要 Node.js 18+（仅构建后运行时）

## License

MIT
