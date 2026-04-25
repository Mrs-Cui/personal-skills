# claude-context — 安装与使用指南

> 为代码模块生成或更新 CLAUDE.md，让 AI 在每次开发时自动获取业务知识，无需重复解释背景。

---

## 目录

1. [前提条件](#前提条件)
2. [安装](#安装)
3. [验证安装](#验证安装)
4. [使用方式](#使用方式)
   - [生成新的 CLAUDE.md（Generate 模式）](#生成新的-claudemd)
   - [更新已有 CLAUDE.md（Update 模式）](#更新已有-claudemd)
5. [CLAUDE.md 标准结构](#claudemd-标准结构)
6. [项目自定义模板](#项目自定义模板)
7. [常见问题](#常见问题)

---

## 前提条件

- 已安装 Claude Code CLI（`claude` 命令可用）
- Git 仓库（skill 需要读取项目文件）
- 目标模块有代码（`*_mdl.go`、`front.go`、`service/` 等）

---

## 安装

### 方式一：项目级安装（推荐）

将 skill 复制到项目的 `.claude/skills/` 目录，只在该项目生效。

```bash
# 克隆 market-skills 仓库（如果还没有）
git clone https://git.tigerbrokers.net/astro/market-skills /tmp/market-skills

# 在你的项目根目录执行
mkdir -p .claude/skills
cp -r /tmp/market-skills/skills/claude-context .claude/skills/
```

### 方式二：全局安装

安装到用户级配置，对所有项目生效。

```bash
mkdir -p ~/.claude/skills
cp -r /tmp/market-skills/skills/claude-context ~/.claude/skills/
```

### 方式三：脚本一键安装（同时安装两个 skill）

```bash
#!/bin/bash
MARKET_SKILLS=/tmp/market-skills  # 修改为实际路径
PROJECT_ROOT=$(git rev-parse --show-toplevel)

mkdir -p "$PROJECT_ROOT/.claude/skills"
cp -r "$MARKET_SKILLS/skills/claude-context" "$PROJECT_ROOT/.claude/skills/"
cp -r "$MARKET_SKILLS/skills/ai-code-review" "$PROJECT_ROOT/.claude/skills/"

echo "✅ Skills 安装完成：$PROJECT_ROOT/.claude/skills/"
ls "$PROJECT_ROOT/.claude/skills/"
```

---

## 验证安装

```bash
# 确认文件存在
ls .claude/skills/claude-context/
# 应输出：SKILL.md  references/

# 在项目目录启动 Claude Code，输入：
# /claude-context
# 如果能看到 skill 的响应说明安装成功
```

---

## 使用方式

### 生成新的 CLAUDE.md

**适用场景**：新模块还没有 CLAUDE.md，第一次为它建立业务上下文。

**基本用法**：

```
/claude-context internal/app/member
```

**Claude Code 会自动执行**：

1. 扫描 `internal/app/member/` 目录下的关键文件：
   - `*_mdl.go` → 提取数据表结构和字段
   - `front.go` / `router.go` → 提取 HTTP API 端点
   - `service/core.go` 等 → 理解核心业务流程
   - `provider.go` → 识别外部依赖

2. 检查项目是否有 `docs/CLAUDE.md设计规范.md`，若有则按项目规范生成，否则使用默认模板

3. 在 `internal/app/member/CLAUDE.md` 生成结构化文档，包含：
   - 业务说明
   - 关键文件索引
   - 主要数据表（含关键字段）
   - 核心业务流程
   - 外部依赖
   - API 端点
   - Code Review 关键点（初始为占位符，等待积累）

**生成后效果示例**：

```markdown
# 会员（member）
> 最后更新：2026-03-20 | 状态：✅ 有效

## 业务说明
会员模块管理用户等级体系（普通/高级/专业），负责等级评定、升降级通知和权益发放。

## 主要数据表
| 表名 | 说明 | 关键字段 |
|------|------|---------|
| `member_level_record` | 用户等级记录 | `user_id`, `level`, `status` |
| `member_change_log` | 等级变更日志 | `user_id`, `from_level`, `to_level`, `reason` |

## Code Review 关键点

### 不变式（每次修改必须保证）
- 暂无（待开发过程中补充）

### 常见错误模式
- ❌ 暂无（待 Code Review 过程中积累）
```

**生成后，手动补充 Code Review 关键点**（这是最关键的一步）：

```markdown
### 不变式（每次修改必须保证）
- 等级变更必须同时写 member_change_log，否则无法追溯变更原因
- 发奖调用必须传 IdempotencyKey，使用 inviteInfo.ID 作为幂等 key

### 常见错误模式
- ❌ 直接调 dao.MemberLevel.Update() 而不经过 service 层，导致绕过变更日志写入
- ❌ award.Send() 调用时未传 IdempotencyKey，存在重复发奖风险
```

---

### 更新已有 CLAUDE.md

**适用场景**：代码发生变更，需要同步 CLAUDE.md 文档内容。

**基本用法**：

```
/claude-context internal/app/member update 新增了 member_vip_record 表，用于存储 VIP 权益记录
```

格式：`/claude-context <模块路径> update <变更原因>`

**各种变更场景示例**：

```bash
# 新增了数据表
/claude-context internal/app/member update 新增 member_benefit_record 表

# 修改了 API
/claude-context internal/app/member update 新增了 /api/member/upgrade 接口

# 新增了外部依赖
/claude-context internal/app/member update 新增了对 benefit-service 的调用

# 业务规则变更
/claude-context internal/app/member update 等级评定逻辑变更，从月度改为季度统计
```

**更新时的保护规则**：

Claude 会按变更原因**精准更新对应章节**，并遵守以下保护规则：

| 内容类型 | 处理方式 |
|---------|---------|
| 手动填写的"不变式" | **永远不覆盖** |
| 手动积累的"常见错误模式" | **永远不覆盖** |
| 数据表结构（来自 `*_mdl.go`） | 以代码为准，更新文档 |
| API 端点（来自路由文件） | 以代码为准，更新文档 |
| 业务规则描述冲突 | 输出 ⚠️ 警告，需人工确认 |

**更新后，时间戳自动同步**：

```
> 最后更新：2026-03-20 | 状态：✅ 有效
```

---

## CLAUDE.md 标准结构

生成的 CLAUDE.md 包含以下 8 个章节：

```
# <模块名>（<目录名>）
> 最后更新：YYYY-MM-DD | 状态：✅ 有效

## 业务说明          ← 1-3 句话说清楚这个模块做什么
## 关键文件          ← 核心文件索引（文件名 + 一行说明）
## 主要数据表        ← 表名、说明、关键字段（状态/金额/时间/外键）
## 核心业务流程      ← 主流程步骤，突出判断节点
## 外部依赖          ← 调用了哪些外部服务/内部服务
## API 端点          ← HTTP 接口列表
## Code Review 关键点
  ### 不变式         ← 操作 A 必须触发操作 B（人工维护）
  ### 高风险变更      ← 改这里时必须额外检查哪里（人工维护）
  ### 常见错误模式    ← 具体的错误写法，❌ 开头（人工积累）
```

---

## 项目自定义模板

如果你的项目有自己的 CLAUDE.md 规范，在项目根目录创建 `docs/CLAUDE.md设计规范.md`，skill 会优先读取该文件中的模板和约束，而不是使用内置默认模板。

这让 skill 能适配不同团队的规范差异。

---

## 常见问题

**Q：skill 扫描不到文件怎么办？**

A：确保模块路径正确，且该路径下有 `.go` 文件。skill 会扫描 `*_mdl.go`、`front.go`、`router.go`、`service/` 目录等标准文件。

**Q：生成的内容不准确？**

A：生成后需要人工校验，特别是"核心业务流程"和"业务说明"章节，AI 理解可能不到位。关键是在生成后手动补充 `Code Review 关键点` 章节。

**Q：多人维护 CLAUDE.md 会不会冲突？**

A：CLAUDE.md 跟随代码提交，走 Git 版本管理，冲突解法和代码冲突一样。建议每次修改业务代码时顺手更新，不要堆积。

**Q：CLAUDE.md 有多大作用？**

A：主要价值在 Code Review 关键点，这是 AI 检查业务规则合规性的核心依据。越早积累越有价值。
