# examples/

这里包含三种输入形态的可运行示例，用于演示 `skill-adapter` 的自动识别与转换能力。

## 使用方法

```bash
cd skills/skill-adapter

# 示例 A：Anthropic SKILL.md 包
python3 scripts/convert.py validate --src examples/anthropic-skill
python3 scripts/convert.py build    --src examples/anthropic-skill --clean

# 示例 B：CodeBuddy 斜杠命令（裸 .md）
python3 scripts/convert.py validate --src examples/codebuddy-command/pre-mr-checklist.md
python3 scripts/convert.py build    --src examples/codebuddy-command/pre-mr-checklist.md --clean

# 示例 C：CodeBuddy 规则（RULE.mdc）
python3 scripts/convert.py validate --src examples/codebuddy-rule/typescript-style
python3 scripts/convert.py build    --src examples/codebuddy-rule/typescript-style --clean
```

构建产物在各示例目录下的 `dist/` 中（已被 `.gitignore` 忽略）。
