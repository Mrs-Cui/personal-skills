# 检查规则详解

> 本文档定义了 pre-release-check 各维度的具体识别规则，供 skill 执行时参考。

---

## 1. 数据库变更识别

### 新建表

**匹配条件**：diff 中的新增文件（A 状态），且文件内容满足以下任一：
- 包含 `func (*Xxx) TableName() string { return "t_xxx" }`
- 包含 `gorm:"column:` tag

**提取信息**：
- 表名：从 `TableName()` 返回值提取
- 字段列表：所有含 `gorm:"column:xxx"` 的字段，提取字段名 + Go 类型
- 索引：含 `gorm:"index:xxx"` 或 `gorm:"uniqueIndex:xxx"` 的字段

**输出示例**：
```
CREATE TABLE `t_xxx` (
  `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `user_id` BIGINT NOT NULL DEFAULT 0 COMMENT '用户ID',
  `status` TINYINT NOT NULL DEFAULT 0 COMMENT '状态',
  `amount` DECIMAL(20,4) NOT NULL DEFAULT 0 COMMENT '金额',
  INDEX idx_user_id (user_id)
);
```

### 新增字段

**匹配条件**：diff 中已有文件（M 状态）的新增行含 `gorm:"column:xxx"`

**提取信息**：
- 字段名（从 column tag）
- Go 类型 → 映射 MySQL 类型：
  - `int64`/`int` → `BIGINT`
  - `string` → `VARCHAR(255)`
  - `float64` → `DECIMAL(20,4)`
  - `bool` → `TINYINT(1)`
  - `time.Time` → `DATETIME`
- 默认值（从 `default:xxx` tag 或 Go 零值）
- 注释（从 `comment:xxx` tag）

### 删除字段（⚠️ 高危）

**匹配条件**：diff 删除行含 `gorm:"column:xxx"`

**特殊处理**：
- 标注 ⚠️ 前缀
- 提示"确认历史数据已迁移或不再需要"
- 提示"删除字段的 DDL 建议在代码上线并稳定运行后再执行"

---

## 2. Apollo / Nacos 配置识别

### 新增 Apollo 配置引用

**匹配模式**（正则）：
```
apollo\.Get\w+Config\(\)
apollo\.Get\w+\(\)
apollo\.\w+Config\b
nacos\.Get\w+\(\)
```

### 新增配置 struct 字段

**匹配条件**：在 `apollo/client.go` 或类似文件中，含 `json:"xxx"` tag 的新增行

**检查要点**：
- 字段是否有合理的零值/默认值（避免空配置导致 panic）
- 是否所有环境（QA/Staging/Prod）都需要配置
- 是否需要在 Apollo 管理界面手动添加

### YAML 配置变更

**匹配条件**：`config/*.yml` 文件有变更

**检查要点**：
- 新增的配置项是否有对应的环境变量占位符（`$$ENV_VAR$$`）
- 修改的配置项是否影响所有环境

---

## 3. 消息队列识别

### Kafka Topic

**匹配模式**：
```go
// Topic 常量
const XxxTopic = "topic_name"
Topic: "topic_name"

// 消费者注册
AddHandler("topic_name", ...)
consumer.Subscribe("topic_name", ...)
xkafka.NewConsumer(..., "topic_name", ...)

// 生产者调用
SendMessage(ctx, "topic_name", ...)
producer.Send(...)
xkafka.Send(...)
```

### RabbitMQ

**匹配模式**：
```go
Exchange: "exchange_name"
Queue: "queue_name"
RoutingKey: "routing_key"
```

### Asynq 异步任务

**匹配模式**：
```go
asynq.NewTask("task_type", ...)
xasynq.NewTask(...)
const TypeXxx = "xxx:yyy"
```

---

## 4. 外部服务依赖识别

### 分类规则

| import 路径模式 | 分类 | 检查要点 |
|---------------|------|---------|
| `internal/secondpart/*` | 外部服务客户端 | 服务可用性、接口版本 |
| `internal/services/*` | 内部跨模块服务 | 确认被依赖模块无 breaking change |
| `pb.New*Client` / `grpc.Dial` | gRPC 调用 | Consul/Starship 注册 |
| `xhttp.` / `http.NewRequest` | HTTP 外调 | URL 可达性、超时设置 |

### 仅标注新增依赖

如果一个 `import` 在 base branch 已存在，本次只是在新方法中使用，不作为检查项。只有**新增的 import 行**才产生检查项。

---

## 5. Redis 缓存识别

### Key 模式

**匹配模式**：
```go
// 常量定义
const XxxKey = "campaign:v1:xxx:%v"
var xxxCacheKey = fmt.Sprintf("xxx:%d", ...)

// 操作调用
xrds.Set(ctx, key, ...)
xrds.Get(ctx, key)
rds.HSet(...)
redis.SetEX(...)
```

### TTL 识别

从 `Set*` 调用的最后一个参数或 `Expiration` 字段提取：
```go
xrds.Set(ctx, key, val, 24*time.Hour)  // → TTL=24h
redis.SetEX(ctx, key, val, 3600)        // → TTL=1h
```

---

## 6. 定时任务识别

### 注册模式

```go
// 全局注册（iface/schedule/）
s.add("*/28 * * * *", "任务描述", s.Handler.Method)
cron.AddFunc("0 9 * * *", func() { ... })

// 模块内注册
schedule.Register("0 8 * * *", task.Run)
```

### Cron 表达式含义速查

生成检查清单时，自动附加 cron 的人类可读描述：
- `*/5 * * * *` → 每 5 分钟
- `0 * * * *` → 每小时整点
- `0 9 * * *` → 每天 09:00
- `0 9 * * 1-5` → 工作日 09:00
- `*/28 * * * *` → 每 28 分钟

---

## 7. Wire / 路由注册识别

### Wire 变更

**匹配条件**：
- 新增或修改 `provider.go` 文件
- 新增或修改 `wire.go` / `wire_us.go`
- 新增 `wire.NewSet`、`wire.Bind`、`wire.Struct` 调用

**检查要点**：
- `wire_gen.go` 是否已重新生成（`make gen`）
- 如果 `wire_gen.go` 不在 diff 中但 `provider.go` 有变更 → ⚠️ 遗漏

### 路由注册

**匹配条件**：`register/application_primary.go` 或 `register/application_us.go` 有变更

**检查要点**：
- 新增的 handler 是否有对应的路由注册
- 是否同时需要注册 primary 和 us

---

## 8. API 接口变更识别

### 新增接口

**匹配模式**：
```go
group.GET("/path", handler.Method)
group.POST("/path", handler.Method)
router.Handle("GET", "/path", handler)
```

### 接口契约变更

**匹配条件**：DTO struct（请求/响应）的字段发生变更

**兼容性判断**：
- 新增可选字段（`json:"xxx,omitempty"`）→ ✅ 向后兼容
- 新增必选字段 → ⚠️ 需前端适配
- 删除字段 → ⚠️ Breaking Change
- 修改字段类型 → ⚠️ Breaking Change
- 修改 JSON tag 名 → ⚠️ Breaking Change

---

## 高危操作汇总

以下变更无论出现在哪个维度，都需要特别标注：

| 模式 | 风险 | 提醒 |
|------|------|------|
| 删除 DB 字段 | 数据丢失 | DDL 延后执行，代码先上 |
| 删除 API 路由 | 客户端报错 | 确认无流量后再删 |
| 修改 Redis key 格式 | 缓存击穿 | 需考虑新旧 key 并存过渡期 |
| 修改 Kafka consumer group | 消息重消费 | 确认 offset 策略 |
| 修改分布式锁 key | 并发安全 | 确认新旧锁不冲突 |
| 修改金额计算逻辑 | 资金安全 | 必须 double check + 灰度 |
| 修改 cron 表达式 | 任务频率 | 确认不影响上下游时序 |
