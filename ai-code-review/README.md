# ai-code-review — 安装与使用指南

> 基于 git diff + CLAUDE.md 业务上下文，对代码变更进行结构化 Code Review，输出分级问题清单。

---

## 目录

1. [前提条件](#前提条件)
2. [安装](#安装)
3. [验证安装](#验证安装)
4. [使用方式](#使用方式)
   - [手动触发（/review 命令）](#手动触发)
   - [自动触发（pre-push hook）](#自动触发pre-push-hook)
   - [CI 触发（GitLab MR 流水线）](#ci-触发gitlab-mr-流水线)
5. [理解 Review 输出](#理解-review-输出)
6. [Review 的检查范围](#review-的检查范围)
7. [最佳实践](#最佳实践)
8. [常见问题](#常见问题)

---

## 前提条件

- 已安装 Claude Code CLI（`claude` 命令可用）
- Git 仓库（skill 需要执行 `git diff`）
- 可选但推荐：相关模块已有 CLAUDE.md（否则只做通用检查，无业务规则检查）

---

## 安装

### 方式一：项目级安装（推荐）

```bash
# 克隆 market-skills 仓库（如果还没有）
git clone https://git.tigerbrokers.net/astro/market-skills /tmp/market-skills

# 在你的项目根目录执行
mkdir -p .claude/skills
cp -r /tmp/market-skills/skills/ai-code-review .claude/skills/
```

### 方式二：同时安装两个配套 skill

`ai-code-review` 和 `claude-context` 配合使用效果最佳：

```bash
mkdir -p .claude/skills
cp -r /tmp/market-skills/skills/ai-code-review .claude/skills/
cp -r /tmp/market-skills/skills/claude-context .claude/skills/
```

### 方式三：全局安装

```bash
mkdir -p ~/.claude/skills
cp -r /tmp/market-skills/skills/ai-code-review ~/.claude/skills/
```

---

## 验证安装

```bash
ls .claude/skills/ai-code-review/
# 应输出：SKILL.md  references/

# 在项目目录启动 Claude Code，输入：
# /ai-code-review
# 看到 Review 输出说明安装成功
```

---

## 使用方式

### 手动触发

在 Claude Code 中输入命令即可触发 Review：

```
/ai-code-review
```

**触发逻辑**：
- 优先检查 `git diff HEAD`（未提交的工作区变更）
- 若为空，检查 `git diff HEAD~1`（最近一次提交）
- 若仍为空，提示"当前没有检测到代码变更"

**实际使用场景**：

```bash
# 场景一：提交前自查（最常用）
# 在 git add 之后，git commit 之前运行
/ai-code-review

# 场景二：Review 已提交的代码
git add .
git commit -m "feat: add member upgrade flow"
/ai-code-review   # 此时会 review 刚提交的内容（HEAD~1 diff）

# 场景三：Review 特定文件的变更（描述给 Claude）
# 告诉 Claude "只 review internal/app/member/ 下的变更"
```

---

### 自动触发（pre-push hook）

在每次 `git push` 前自动运行 Review，有问题时在终端输出提醒。

**安装 pre-push hook**：

```bash
# 在项目根目录执行
cat > .git/hooks/pre-push << 'EOF'
#!/bin/bash

echo "🔍 正在运行 AI Code Review..."

# 检查是否有 Claude Code
if ! command -v claude &> /dev/null; then
    echo "⚠️  Claude Code 未安装，跳过 AI Review"
    exit 0
fi

# 检查 diff 大小
DIFF_LINES=$(git diff HEAD~1 --stat | tail -1 | grep -o '[0-9]* insertion' | head -1 | grep -o '[0-9]*')
if [ "${DIFF_LINES:-0}" -gt 500 ]; then
    echo "⚠️  变更较大（${DIFF_LINES} 行），建议拆分后分批 review"
fi

# 高风险文件检测
HIGH_RISK_FILES=$(git diff HEAD~1 --name-only | grep -E "(award|payment|settlement|finance)")
if [ -n "$HIGH_RISK_FILES" ]; then
    echo ""
    echo "⚠️  检测到高风险文件变更，请确认 CLAUDE.md 是否已更新："
    echo "$HIGH_RISK_FILES" | sed 's/^/   - /'
    echo ""
fi

# 运行 AI Review（非阻塞，仅输出提醒）
claude --print "/ai-code-review" 2>/dev/null || true

exit 0
EOF

chmod +x .git/hooks/pre-push
echo "✅ pre-push hook 安装完成"
```

> **说明**：hook 使用 `exit 0` 不阻塞 push，只输出提醒。如需阻塞，将 `exit 0` 改为让用户确认。

---

### CI 触发（GitLab MR 流水线）

在 MR 创建/更新时自动运行 Review，结果作为 MR comment 或 pipeline job 展示。

**在 `.gitlab-ci.yml` 中添加**：

```yaml
ai-code-review:
  stage: review
  image: your-claude-code-image:latest  # 需要包含 claude CLI
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  script:
    - mkdir -p .claude/skills
    - cp -r $MARKET_SKILLS_PATH/skills/ai-code-review .claude/skills/
    - git fetch origin $CI_MERGE_REQUEST_TARGET_BRANCH_NAME
    - export REVIEW_DIFF=$(git diff origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME...HEAD)
    - claude --print "/ai-code-review" > review_result.txt 2>&1
    - cat review_result.txt
  artifacts:
    reports:
      dotenv: review_result.txt
    expire_in: 7 days
  allow_failure: true  # Review 失败不阻塞 MR 合并
```

**GitLab MR 模板（可选）**：

在 `.gitlab/merge_request_templates/Default.md` 加入 checklist：

```markdown
## 变更说明

[描述本次变更的内容和原因]

## Checklist

- [ ] 已运行 `/ai-code-review`，🔴 严重问题已处理
- [ ] 涉及数据表/接口/业务规则变更时，已更新对应 CLAUDE.md
- [ ] 跨表写操作已添加事务保护
```

---

## 理解 Review 输出

### 标准输出格式

```markdown
## 🔴 严重问题（必须修复，建议阻塞合并）

- [service/core.go:42] 发奖调用未传幂等 key，存在重复发奖风险
  → 在调用 award.Send() 时增加参数 `IdempotencyKey: inviteInfo.ID`

## 🟡 建议改进（不阻塞，建议处理）

- [service/core.go:65] 等级变更后没有发送 Kafka 事件
  → 参考同模块其他等级变更操作，补充事件发送逻辑

## ✅ 通过的关键检查项

- 跨表操作（invite_info + award_record）已使用事务保护
- 外部服务调用（Award Service）传入了正确的 context

## 📋 Review 依据

- 检查模块：`internal/app/membershipinvite`
- CLAUDE.md 最后更新：2026-03-18
- 本次检查的约束：不变式 3 条、常见错误模式 2 条、通用架构规范 4 项
```

### 分级说明

| 标志 | 含义 | 处理建议 |
|------|------|---------|
| 🔴 严重 | 确定违反了 CLAUDE.md 不变式，或明确的架构违规 | **合并前必须修复** |
| 🟡 建议 | 可能有风险但不确定，或有更好的写法 | 酌情处理，不阻塞合并 |
| ✅ 通过 | 明确检查了该项目，确认没有问题 | 无需操作 |
| 📋 依据 | 本次 Review 用了哪些规则和文档 | 用于追溯和验证 |

**重要原则**：AI Review 宁可少报 🔴，也不乱报 🔴。不确定的问题一律用 🟡。

### 没有 CLAUDE.md 时的输出

```markdown
## ℹ️ 上下文说明

未找到以下模块的 CLAUDE.md，无法进行业务规则检查：
- `internal/app/xxx`（建议运行 `/claude-context internal/app/xxx` 生成）

以下 Review 仅基于通用架构规范，不包含业务规则检查。
---
[通用架构检查结果...]
```

**解决方法**：先运行 `claude-context` skill 为模块生成 CLAUDE.md，Review 质量会显著提升。

### CLAUDE.md 过期警告

```
⚠️  CLAUDE.md 可能已过期（文档：2025-12-01，代码最后变更：2026-03-10）
   Review 结论中的业务规则部分仅供参考，建议先运行 /claude-context update 更新文档
```

出现此警告时，先用 `claude-context` 更新文档，再重新 Review。

---

## Review 的检查范围

### 有 CLAUDE.md 时检查

1. **不变式合规**：CLAUDE.md 中的强制规则是否被遵守（如"等级变更必须写 change_log"）
2. **常见错误模式**：是否出现已知的错误写法（如"直接调 DAO 绕过 service 层"）
3. **分层架构**：handler 是否直接调用了 DAO
4. **数据一致性**：跨表写操作是否有事务
5. **可观测性**：关键状态变更是否有日志/事件
6. **外部依赖规范**：调用方式是否符合模块 CLAUDE.md 的外部依赖描述

### 只做通用检查时

仅检查第 3-6 项，无法检查业务规则。

### 不在检查范围内

- 代码风格（缩进、命名）→ linter 的工作
- 性能优化建议 → 超出 diff 范围
- 重构建议 → 不在本次变更范围内
- 业务需求合理性 → 超出代码范围

---

## 最佳实践

**1. 先建立 CLAUDE.md，再做 Review**

Review 的核心价值来自业务规则检查，而业务规则保存在 CLAUDE.md 中。没有 CLAUDE.md 的模块 Review 效果有限。

建议顺序：
```
/claude-context internal/app/member    # 先生成 CLAUDE.md
↓ 手动补充 Code Review 关键点
/ai-code-review                        # 再做 Review
```

**2. 把 🔴 问题当成 bug 对待**

🔴 问题意味着确定违反了你们团队积累的业务规则，是真实的风险，而不是 AI 的建议。

**3. 把 🟡 问题当成 review comment 对待**

🟡 问题不是必须修复的，根据实际情况判断。但如果觉得确实是个规律性问题，可以把它加到 CLAUDE.md 的"常见错误模式"中，下次就能变成 🔴 检测。

**4. 逐步完善 CLAUDE.md 的 Code Review 关键点**

每次 Review 发现了新的业务规则约束，立刻添加到 CLAUDE.md 的"不变式"或"常见错误模式"，让后续 Review 越来越准。

---

## 常见问题

**Q：Review 说的问题是真的问题吗？**

A：🔴 问题基本可信（基于你们团队积累的不变式），🟡 问题需要人工判断。AI 设计为宁可少报，不乱报。

**Q：diff 太大怎么办？**

A：diff 超过 500 行时 skill 会提示"变更较大，建议拆分"，同时仍然继续但降低精度预期。建议保持单次提交 diff 在 300 行以内。

**Q：Review 输出了错误的文件行号？**

A：行号来自 git diff 的行信息，如果有误请在反馈时附上原文，考虑将该场景记录到 CLAUDE.md 的已知限制中。

**Q：两个 skill 要一起用吗？**

A：不强制，但配合使用效果最佳。`claude-context` 负责建立和维护业务上下文，`ai-code-review` 负责利用这些上下文做 Review。单独使用 `ai-code-review` 也有价值（通用架构检查），但无法检查业务规则。
