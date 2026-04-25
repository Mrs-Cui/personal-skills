---
name: pre-release-check
description: |
  基于 git diff 自动分析代码变更，生成结构化上线检查清单。识别 DB 变更、配置依赖、
  消息队列、外部服务、缓存 Key 等维度的待办项，防止上线遗漏。

  **适用项目**：当前仅适用于 campaign 项目（营销活动微服务），需要在 campaign 仓库目录下执行。

  Use when:
  - 用户请求上线检查，如"帮我生成上线清单"、"检查下这次上线要注意什么"
  - 用户提到"上线"、"发布"、"release"、"deploy"、"检查清单"、"checklist"
  - 用户运行 /pre-release-check 命令
  - 用户说"我要提 MR 了"、"准备上线了"

argument-hint: "[base-branch] [-- path/to/module]"
---

# Pre-Release Check — 上线检查清单自动生成

## 概述

基于当前分支与目标分支的 git diff，自动扫描代码变更，按 8 个维度生成结构化上线检查清单。每个检查项标注**来源文件和行号**，让开发者可以快速定位和确认。

---

## 执行流程

### Step 1：确定对比范围

1. **解析参数**：
   - 用户指定了 base branch → 使用指定的
   - 未指定 → 自动检测：`main` > `master` > `develop`，取存在的第一个
   - 用户指定了 `-- path/` → 只分析该路径下的变更
2. **获取 diff**：
   - 运行 `git diff <base>...HEAD --name-status` 获取变更文件列表（新增 A / 修改 M / 删除 D）
   - 运行 `git diff <base>...HEAD` 获取完整 diff 内容
   - 运行 `git log <base>...HEAD --oneline` 获取 commit 列表，用于输出摘要
3. **过滤无关文件**：忽略 `*_test.go`、`testmocks/`、`*.md`、`go.sum`

### Step 2：分维度扫描变更

对每个维度，扫描 diff 中的**新增行（+开头）**和变更文件的**完整内容**，提取需要检查的项目。

#### 维度 1：数据库变更（DB Migration）

**扫描目标**：`*_mdl.go`、`*_model.go`、`model/*.go`、`dal/model/*.go`

**识别规则**：
- 新增文件含 `TableName()` 方法 → **新建表**，提取表名和完整字段列表
- 已有文件新增 `gorm:"column:xxx"` 字段 → **新增字段**，提取字段名、类型、默认值
- 已有文件修改 `gorm:"column:xxx"` tag → **字段变更**，提取前后差异
- 新增 `gorm:"index:xxx"` / `gorm:"uniqueIndex:xxx"` → **新增索引**
- 删除含 `gorm:` tag 的字段 → **删除字段**（⚠️ 高危操作，需特别标注）

**输出格式**：
```
## 📦 数据库变更
- [ ] 新建表 `t_xxx`（来源：path/to/model.go:L42）
      字段：field1 (varchar), field2 (int), field3 (timestamp)
- [ ] 新增字段 `t_yyy.new_column` BIGINT NOT NULL DEFAULT 0（来源：path/to/model.go:L87）
- [ ] ⚠️ 删除字段 `t_yyy.old_column`（来源：path/to/model.go:L-65）— 确认数据已迁移
```

#### 维度 2：Apollo / Nacos 配置变更

**扫描目标**：所有变更的 `.go` 文件

**识别规则**：
- diff 新增行含 `apollo.Get*`、`apollo.*Config`、`nacos.Get*` 调用 → 新增配置依赖
- diff 新增行含 Apollo 配置 struct 新字段（JSON tag `json:"xxx"`） → 新增配置字段
- 新增 `config/` 目录下的 YAML 变更 → 配置文件变更

**输出格式**：
```
## ⚙️ 配置变更（Apollo / Nacos / YAML）
- [ ] 新增 Apollo 配置字段 `xxxConfig.newField`（来源：path/to/apollo.go:L123）
      ↳ 确认 Apollo 各环境（QA/Staging/Prod）已配置
- [ ] 引用了新的 Apollo 配置 `GetXxxConfig()`（来源：path/to/service.go:L45）
      ↳ 确认配置命名空间已存在
```

#### 维度 3：消息队列变更（Kafka / RabbitMQ / Asynq）

**扫描目标**：所有变更的 `.go` 文件

**识别规则**：
- 新增 Kafka topic 常量或字符串 → 新增 Topic
- 新增 `consumer` 注册（`AddHandler`/`Subscribe`/`HandleFunc`） → 新增消费者
- 新增 `SendMessage`/`Produce`/`Publish` 调用 → 新增生产者
- 新增 Asynq task type 或 handler → 新增异步任务
- 新增 RabbitMQ exchange/queue 声明 → 新增 RabbitMQ 资源

**输出格式**：
```
## 📨 消息队列变更
- [ ] 新增 Kafka 消费者：topic=`xxx`（来源：consumer.go:L34）
      ↳ 确认 topic 在 Kafka 集群已创建，partition 数量合理
- [ ] 新增 Kafka 生产消息：topic=`yyy`（来源：service.go:L89）
      ↳ 确认下游消费者已就绪
```

#### 维度 4：外部服务依赖变更

**扫描目标**：所有变更的 `.go` 文件的 `import` 块和函数调用

**识别规则**：
- 新增 `import "xxx/internal/secondpart/xxx"` → 新增外部服务依赖
- 新增 `import "xxx/internal/services/xxx"` → 新增内部跨模块依赖
- 新增 gRPC client 调用（`pb.NewXxxClient`、`xxxClient.Xxx(ctx, req)`） → 新增 RPC 依赖
- 新增 HTTP 外部调用（`http.Get`/`http.Post`/`xhttp.`） → 新增 HTTP 依赖

**输出格式**：
```
## 🔗 外部服务依赖变更
- [ ] 新增依赖：`internal/secondpart/auth`（来源：provider.go:L12）
      ↳ 确认该服务在目标环境可用，接口版本兼容
- [ ] 新增 gRPC 调用：`MarketAttrService.GetUserAttr`（来源：service.go:L67）
      ↳ 确认 gRPC 服务已注册到 Consul/Starship
```

#### 维度 5：Redis 缓存变更

**扫描目标**：所有变更的 `.go` 文件

**识别规则**：
- 新增 Redis key 常量（含 `Key`/`key`/`Cache`/`cache` 命名，值含 `%v`/`%s`/`%d`） → 新增缓存 Key
- 新增 `xrds.`/`redis.`/`rds.` 调用 → 新增缓存操作
- 变更 TTL 值（`time.Hour`/`time.Minute`/`Expiration`） → TTL 变更

**输出格式**：
```
## 🗄️ Redis 缓存变更
- [ ] 新增缓存 Key：`campaign:v1:xxx:%v`，TTL=24h（来源：const.go:L15）
      ↳ 评估热点 Key 的内存占用，确认 Redis 容量充足
```

#### 维度 6：定时任务变更

**扫描目标**：`schedule*.go`、`tasks*.go`、`cron*.go`、`internal/iface/schedule/`

**识别规则**：
- 新增 `s.add("cron-expr", ...)` 或 `cron.AddFunc` → 新增定时任务
- 修改 cron 表达式 → 调度频率变更
- 新增 schedule 进程的任务注册 → 需确认 schedule 进程重启

**输出格式**：
```
## ⏰ 定时任务变更
- [ ] 新增定时任务：`*/28 * * * *` → `PatchSendMsg`（来源：schedule_primary.go:L45）
      ↳ 确认 schedule 进程需要重启
```

#### 维度 7：Wire 依赖注入变更

**扫描目标**：`provider.go`、`wire.go`、`providers.go`、`register/application*.go`

**识别规则**：
- 新增/修改 `provider.go` → 需要 `make gen`
- 新增 Wire provider 或 interface binding → 需要重新生成
- 新增 `register/application_primary.go` 中的 handler 注册 → 需确认路由生效

**输出格式**：
```
## 🔌 Wire / 路由注册变更
- [ ] 修改了 provider.go（来源：internal/app/xxx/provider.go）
      ↳ 上线前确认已执行 `make gen`，wire_gen.go 已提交
- [ ] 新增路由注册（来源：register/application_primary.go:L89）
      ↳ 确认 front/admin 进程需要重启
```

#### 维度 8：API 接口变更

**扫描目标**：路由注册文件、handler 文件、DTO 文件

**识别规则**：
- 新增 `.GET`/`.POST`/`.PUT`/`.DELETE` 路由 → 新增接口
- 删除路由 → 下线接口（⚠️ 高危）
- 修改请求/响应 DTO 字段 → 接口契约变更（⚠️ 需前端感知）

**输出格式**：
```
## 🌐 API 接口变更
- [ ] 新增接口：POST `/api/v1/xxx/create`（来源：front.go:L34）
      ↳ 确认前端/文档已同步
- [ ] ⚠️ 接口响应字段变更：`XxxResp` 新增 `new_field`（来源：dto.go:L78）
      ↳ 确认客户端兼容（字段为新增则向后兼容，删除/改名则需协调）
```

### Step 3：生成检查清单

将所有维度的检查项汇总为一份结构化清单：

```markdown
# 🚀 上线检查清单

**分支**: feature/xxx → main
**变更文件**: N 个
**Commits**: M 个

---

[各维度检查项，仅展示有内容的维度]

---

## ✅ 基础检查（每次上线必做）
- [ ] 代码已通过 CI（lint + build + test）
- [ ] MR 已通过 Code Review
- [ ] 涉及的进程已标记需要重启：[front/admin/schedule/kafka/...]
- [ ] 回滚方案已确认（是否可直接回滚，是否有 DB 变更阻碍回滚）
```

### Step 4：输出

1. **终端输出**：先将完整的 Markdown 检查清单输出到终端，让用户预览
2. **询问是否输出到飞书**：清单输出后，使用 `AskUserQuestion` 工具询问用户：

   ```
   question: "是否将上线检查清单输出到飞书文档？"
   options:
     - label: "输出到飞书"
       description: "创建飞书云文档，方便团队协作和逐项确认"
     - label: "不需要"
       description: "仅保留终端输出即可"
   ```

3. **飞书文档输出**（用户选择"输出到飞书"时）：
   - 使用 `create-doc` 工具创建飞书文档
   - 文档标题格式：`上线检查清单 - {分支名} ({日期})`
   - 将完整检查清单作为 Markdown 内容写入
   - 输出文档链接给用户

---

## 智能判断规则

### 跳过规则

以下变更**不生成检查项**（减少噪音）：
- 纯注释变更（`//` 或 `/* */` 内容）
- 纯格式化变更（空行、缩进）
- 测试文件（`*_test.go`、`testmocks/`）
- 文档文件（`*.md`、`*.txt`）
- `go.sum` / `go.mod`（除非新增了外部依赖）

### 高危标注规则

以下变更标注 ⚠️ 并排在对应维度最前面：
- 删除数据库字段
- 删除/修改已有 API 路由
- 修改发奖/扣款相关逻辑（含 `reward`/`award`/`deduct`/`transfer`/`issue`）
- 修改分布式锁 key 或 TTL
- 修改 Kafka consumer group ID

### 进程重启判断

根据变更文件路径自动判断需要重启的进程：
- `iface/http/front/` 或 handler 路由 → front 进程
- `iface/http/admin/` → admin 进程
- `iface/http/infra/` → infra 进程
- `iface/schedule/` 或 task 文件 → schedule 进程
- `iface/consumer/` 或 consumer 文件 → kafka/mq 进程
- `service/` 或 `dao/` → 取决于被哪些 handler/consumer/schedule 引用

---

## 参考文档

- **检查规则详解**：[checklist-rules.md](references/checklist-rules.md)
