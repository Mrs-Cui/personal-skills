---
name: claude-context
description: |
  为任意代码模块生成或更新 CLAUDE.md 上下文文件，让 AI 在开发时自动获取业务知识，无需每次重复解释背景。

  Use when:
  - 用户请求为模块生成 CLAUDE.md，如"帮我生成上下文"、"建立这个模块的文档"
  - 用户请求更新已有 CLAUDE.md，如"更新文档"、"同步文档"、"我改了表结构"
  - 用户开始开发一个没有 CLAUDE.md 的模块
  - 代码变更涉及数据库表结构、HTTP 接口、业务规则或外部依赖
  - 用户运行 /gen-claude 或 /update-claude 命令

argument-hint: "<module-path> [update-reason]"
---

# Claude Context — 模块知识文档生成与维护

## 工作模式判断

收到请求后，先判断工作模式：

- **Generate 模式**：目标目录不存在 CLAUDE.md，或用户明确要求重新生成
- **Update 模式**：目标目录已有 CLAUDE.md，且用户提供了变更原因

---

## Generate 模式

### Step 1：确定模板来源

按优先级查找：

1. 项目根目录是否有 `docs/CLAUDE.md设计规范.md` → 提取其中的「标准模板」章节使用
2. 无则使用内置默认模板（见 [template.md](references/template.md)）

### Step 2：扫描目标目录

读取以下文件（存在则读，不存在跳过）：

| 文件模式 | 提取内容 |
|---------|---------|
| `*_mdl.go` / `*_model.go` | 数据表结构（TableName、字段名、字段类型、注释） |
| `front.go` / `router.go` / `handler.go` | HTTP API 端点、路由路径、认证方式 |
| `admin.go` | 管理后台 API 端点 |
| `service/` 或 `services/` 目录 | 核心业务逻辑、方法签名 |
| `provider.go` | Wire 依赖关系 |
| 根目录 `*.go` 文件 | 业务说明、入口逻辑 |

**Go 项目补充规则**：
- `TableName()` 方法的返回值 = 表名
- 带 `gorm:"column:xxx"` tag 的字段 = 关键字段（忽略 id/created_at/updated_at）
- `gin.RouterGroup` 的 `.GET`/`.POST` 调用 = API 端点
- import 中的 `internal/secondpart/` 路径 = 外部服务依赖

### Step 3：填写模板并写入文件

- 无法从代码推断的内容写 `暂无`，不删除章节
- `Code Review 关键点` 章节基于代码推断，不确定的写 `待补充`
- 文件头时间戳填写今天日期，格式：`> 最后更新：YYYY-MM-DD | 状态：✅ 有效`
- 写入路径：`<module-path>/CLAUDE.md`

生成完成后输出：
```
✅ 已生成 <module-path>/CLAUDE.md
⚠️  请人工检查「Code Review 关键点」章节并补充业务约束
```

---

## Update 模式

### Step 1：读取现有文件

读取 `<module-path>/CLAUDE.md` 完整内容，记录各章节现有内容。

### Step 2：按变更原因有针对性地读代码

| 变更原因关键词 | 需要重新读取的文件 |
|-------------|----------------|
| 表结构、字段、新增表 | 对应 `*_mdl.go` 文件 |
| 接口、路由、API | `front.go` / `router.go` / `admin.go` |
| 业务规则、流程 | `service/` 目录相关文件 |
| 外部依赖 | `provider.go` 及相关调用处 |

### Step 3：只更新相关章节

**严格遵守以下规则：**

- ✅ 更新与变更直接相关的章节
- ✅ 更新文件头时间戳为今天
- ❌ 不修改其他章节的内容
- ❌ 不覆盖「常见错误模式」中人工积累的内容（即使为空也保留结构）
- ❌ 不删除任何章节

更新完成后输出变更摘要：
```
✅ 已更新 <module-path>/CLAUDE.md
📝 变更章节：[列出更新了哪些章节]
🔒 保留章节：[列出未修改的章节]
```

---

## 适用范围

- **主要面向 Go 项目**，兼容其他语言（无法识别特定文件时，扫描所有 `.go` / `.py` / `.java` 等源文件）
- 适用于任何按模块组织的代码库（`internal/app/xxx`、`src/modules/xxx` 等）
- 跨项目通用：优先读取项目自己的 `docs/CLAUDE.md设计规范.md`，无则用默认模板

---

## 参考文档

- **默认模板**：[template.md](references/template.md)
- **章节更新策略**：[update-guide.md](references/update-guide.md)
