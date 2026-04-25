---
name: ai-code-review
description: |
  基于 git diff 和 CLAUDE.md 业务上下文，对代码变更进行结构化 Code Review，输出分级问题清单。

  Use when:
  - 用户请求 Code Review，如"帮我 review"、"review 一下代码"、"/review 命令"
  - 开发者提交前自查代码质量
  - 用户想验证代码是否符合业务规则约束
  - pre-push hook 或 CI 流水线中自动触发
  - 用户说"看看我这次改了哪些问题"、"有没有漏掉什么"
---

# AI Code Review — 基于业务上下文的代码审查

## 工作流程

### Step 1：获取变更内容

按以下优先级获取 diff：

1. `git diff HEAD`（未提交的工作区变更）
2. 若为空，执行 `git diff HEAD~1`（最近一次提交）
3. 若仍为空，提示用户"当前没有检测到代码变更"

**限制**：diff 超过 500 行时，提示用户"变更较大，建议拆分后分批 review"，仍然继续但降低精度预期。

### Step 2：识别涉及模块

从 diff 的文件路径中提取模块路径，规则：

| diff 文件路径模式 | 识别为模块路径 |
|----------------|-------------|
| `internal/app/<module>/` | `internal/app/<module>` |
| `internal/services/<service>/` | `internal/services/<service>` |
| `internal/dao/<dao>/` | 查找对应 service（`internal/services/<dao>`），若无则跳过 |
| 其他路径 | 提取到第三级目录，尝试查找 CLAUDE.md |

对每个识别到的模块路径：
- 检查 `<module-path>/CLAUDE.md` 是否存在
- 存在则读取，记录其「最后更新」时间戳
- 不存在则标注「无上下文」，仅做通用检查

### Step 3：执行 Review

**当 CLAUDE.md 存在时**，按以下标准逐条检查（见 [review-criteria.md](references/review-criteria.md)）：

1. `Code Review 关键点 — 不变式` 中每条规则是否被遵守
2. `Code Review 关键点 — 常见错误模式` 中的写法是否出现
3. 是否绕过 service 层直接操作 DAO
4. 跨表操作是否有事务保护
5. 关键状态变更是否有日志 / 事件发送
6. 外部依赖调用方式是否符合 `外部依赖` 章节描述

**当 CLAUDE.md 不存在时**，仅执行通用检查（第 3-6 条）。

### Step 4：输出结构化结论

按 [output-format.md](references/output-format.md) 格式输出。

---

## 关键行为约束

- **只看 diff**，不主动读取未变更的文件
- 发现问题时，必须标注 `[文件:行号]`，不接受泛泛描述
- CLAUDE.md 时间戳早于代码最后变更时间时，在 Review 依据中标注 ⚠️
- 误判时不强迫用户接受，用 🟡 而不是 🔴 标注存疑的问题

---

## 参考文档

- **Review 标准详解**：[review-criteria.md](references/review-criteria.md)
- **输出格式规范**：[output-format.md](references/output-format.md)
