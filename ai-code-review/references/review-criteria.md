# Review 标准详解

## 一、基于 CLAUDE.md 的业务规则检查

### 1.1 不变式检查

读取 CLAUDE.md 的 `### 不变式` 章节，对每条规则：

- 在 diff 中搜索涉及该规则的代码变更
- 判断变更是否违反该规则
- **只要不确定，标为 🟡 建议而不是 🔴 严重**

**示例**：
- 规则："等级变更必须同时写 change_log"
- 检查：diff 中有 `UPDATE member_level_record` 的调用 → 搜索同一事务/函数内是否有 `INSERT change_log`
- 没有 → 🔴 严重问题

### 1.2 常见错误模式检查

读取 CLAUDE.md 的 `### 常见错误模式` 章节，每条 ❌ 描述都作为一个检测规则：

- 从描述中提取"错误特征"（如"直接调 DAO"、"漏掉幂等 key"）
- 在 diff 中查找是否出现该特征
- 出现则标为 🔴 严重问题

---

## 二、通用架构规范检查（无需 CLAUDE.md）

### 2.1 分层架构

| 问题 | 严重级别 | 检测方式 |
|------|---------|---------|
| HTTP handler 直接调用 DAO（跳过 service 层） | 🔴 | handler 文件中 import 了 dao 包 |
| service 层直接操作 HTTP context | 🟡 | service 文件中 import 了 gin 包 |

### 2.2 数据一致性

| 问题 | 严重级别 | 检测方式 |
|------|---------|---------|
| 跨多张表的写操作没有事务 | 🔴 | 多个 DAO 写操作，没有 `db.Transaction` 或 `Begin/Commit` |
| 重要操作缺少错误处理（err 被忽略）| 🟡 | `_, err` 或 `err :=` 后没有 `if err != nil` |

### 2.3 可观测性

| 问题 | 严重级别 | 检测方式 |
|------|---------|---------|
| 关键状态变更没有日志 | 🟡 | 状态字段更新操作附近没有 log/event 调用 |
| 外部服务调用没有超时设置 | 🟡 | HTTP 或 gRPC 调用没有 context deadline |

---

## 三、文档新鲜度警告

当 CLAUDE.md 时间戳早于代码文件的 git 最后修改时间超过 30 天时：

```
⚠️  CLAUDE.md 可能已过期（文档：YYYY-MM-DD，代码最后变更：YYYY-MM-DD）
   Review 结论中的业务规则部分仅供参考，建议先运行 /gen-claude 更新文档
```

---

## 三·五、DAO 层命名契约检查

| 问题 | 严重级别 | 检测方式 |
|------|---------|---------|
| `GetActive*`/`GetValid*`/`GetCurrent*` 命名的 DAO 方法，WHERE 子句只有时间过滤（`end_time > now`），没有 `status = 'active'` 过滤 | 🔴 | 在 diff 中查找方法名含 Active/Valid/Current 的 DAO 函数，检查 WHERE 子句是否同时包含时间条件和状态条件 |
| 优先级/竞争决策函数（如 `calculateFinal*`/`calculateBest*`），只覆盖了"胜出"路径，未覆盖"不变更"路径 | 🟡 | 在 diff 中查找优先级比较逻辑，确认有处理 `currentWins` / `noChange` 的分支 |

**`GetActive*` 命名契约**：方法名中含 `Active`/`Valid`/`Current` 语义时，调用方有权假设返回的记录在业务上处于"生效"状态。如果只按时间过滤而没有按 `status` 字段过滤，则存在"状态幽灵"问题：已被业务标记为 `expired`/`inactive` 但时间还未到期的记录会被误返回，导致下游逻辑错误。

**示例**：
- 方法 `GetActiveTrialStatusByUserID` 的 WHERE 子句仅为 `target_end_time > now` → 🔴 缺少 `AND status = 'active'`
- 正确写法：`WHERE target_end_time > ? AND status = 'active'`

---

## 四、不在 Review 范围内的事项

以下内容**不应该**出现在 Review 结论中：
- 代码风格（缩进、命名）→ 这是 linter 的工作
- 性能优化建议（除非明显的 N+1 查询）→ 超出 diff 范围
- 重构建议 → 不在本次变更范围内
- 业务需求合理性 → 超出代码范围
