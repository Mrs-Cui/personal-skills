# 输出格式规范

## 标准输出格式

```markdown
## 🔴 严重问题（必须修复，建议阻塞合并）

- [service/core.go:42] 发奖调用未传幂等 key，存在重复发奖风险
  → 在调用 award.Send() 时增加参数 `IdempotencyKey: inviteInfo.ID`

- [dao/member.go:88] 直接操作 DAO 跳过了 service 层
  → 将此调用移至 services/member/member.go 中

## 🟡 建议改进（不阻塞，建议处理）

- [service/core.go:65] 等级变更后没有发送 Kafka 事件
  → 参考同模块其他等级变更操作，补充事件发送逻辑

## ✅ 通过的关键检查项

- 跨表操作（invite_info + award_record）已使用事务保护
- 外部服务调用（Award Service）传入了正确的 context

## 📋 Review 依据

- 检查模块：`internal/app/membershipinvite`、`internal/services/member`
- CLAUDE.md 最后更新：2026-03-18（`membershipinvite`）、2026-03-15（`member`）
- 本次检查的约束：不变式 3 条、常见错误模式 2 条、通用架构规范 4 项
```

---

## 输出规则

### 必须遵守

1. **每个问题必须有文件和行号**：格式 `[文件路径:行号]`，不接受只说"某处"
2. **每个问题必须有修改建议**：用 `→` 引导，一句话说清楚怎么改
3. **Review 依据必须列出**：哪些模块的 CLAUDE.md 被加载了、时间戳是什么

### 分级标准

| 级别 | 标准 | 典型场景 |
|------|------|---------|
| 🔴 严重 | 确定违反了 CLAUDE.md 中的不变式，或确定的架构违规 | 漏写 change_log、绕过 service 层 |
| 🟡 建议 | 可能有风险但不确定，或有更好的写法 | 缺少日志、存疑的业务逻辑 |
| ✅ 通过 | 明确检查并确认没问题 | 事务保护、幂等处理 |

**原则：宁可少报 🔴，不要乱报 🔴。** 不确定的问题一律用 🟡。

### 没有 CLAUDE.md 时的输出

```markdown
## ℹ️ 上下文说明

未找到以下模块的 CLAUDE.md，无法进行业务规则检查：
- `internal/app/xxx`（建议运行 `/gen-claude internal/app/xxx` 生成）

以下 Review 仅基于通用架构规范，不包含业务规则检查。

---
[正常输出格式...]
```

### 没有发现任何问题时的输出

```markdown
## ✅ 通过的关键检查项

- [列出所有检查了什么，确认没问题]

## 📋 Review 依据

- 检查模块：[...]
- CLAUDE.md 最后更新：[...]
- 本次检查的约束：[...]

本次变更未发现严重问题或建议改进点。
```
