# pre-release-check

基于 git diff 自动分析代码变更，生成结构化上线检查清单。

> **适用项目**：当前仅适用于 **campaign** 项目（营销活动微服务），需要在 campaign 仓库目录下执行。

## 解决什么问题

每次上线前需要人工检查：DB migration 是否执行、Apollo 配置是否同步、Kafka topic 是否创建、依赖服务是否感知……项目越大、变更越多，遗漏的概率越高。

本 skill 自动扫描 git diff，按 8 个维度生成检查清单，每个检查项标注来源文件和行号，让你在 5 分钟内完成原本需要 30 分钟的上线准备工作。

## 检查维度

| 维度 | 识别内容 |
|------|---------|
| 📦 数据库变更 | 新建表、新增字段、删除字段、新增索引 |
| ⚙️ 配置变更 | Apollo/Nacos 新增配置项、YAML 变更 |
| 📨 消息队列 | Kafka topic、consumer/producer、Asynq 任务 |
| 🔗 外部依赖 | secondpart 服务、跨模块服务、gRPC/HTTP 调用 |
| 🗄️ Redis 缓存 | 新增 Key、TTL 变更 |
| ⏰ 定时任务 | cron 表达式、任务注册 |
| 🔌 Wire/路由 | provider 变更、路由注册、make gen 提醒 |
| 🌐 API 接口 | 新增/删除接口、DTO 字段兼容性 |

## 安装

### 项目级安装（推荐）

```bash
# 在项目根目录执行
mkdir -p .claude/skills
ln -s /path/to/market-skills/skills/pre-release-check .claude/skills/pre-release-check
```

或直接复制：
```bash
cp -r /path/to/market-skills/skills/pre-release-check .claude/skills/
```

### 全局安装

```bash
mkdir -p ~/.claude/skills
ln -s /path/to/market-skills/skills/pre-release-check ~/.claude/skills/pre-release-check
```

### 脚本安装

```bash
cd /path/to/market-skills
bash skills/install-skills.sh pre-release-check
```

## 使用方式

### 基本用法

```
/pre-release-check
```

自动检测 base branch（main/master/develop），分析当前分支的所有变更。

### 指定 base branch

```
/pre-release-check develop
```

### 限定分析范围

```
/pre-release-check main -- internal/app/membershipinvite
```

只分析 `membershipinvite` 模块的变更。

### 自然语言触发

以下表达都会触发本 skill：

- "帮我生成上线清单"
- "这次上线要注意什么"
- "检查下变更有没有遗漏"
- "我要提 MR 了，帮我过一遍"

## 输出示例

```markdown
# 🚀 上线检查清单

**分支**: feat_blacklist → main
**变更文件**: 7 个
**Commits**: 3 个

---

## 📦 数据库变更
- [ ] 新增字段 `t_membership_invite_info.a_blacklisted` TINYINT(1) NOT NULL DEFAULT 0
      （来源：internal/app/membershipinvite/model/invite_info.go:L64）
      ↳ 执行 ALTER TABLE DDL

## ⚙️ 配置变更（Apollo / Nacos / YAML）
- [ ] 新增 Apollo 配置字段 `MembershipInivteConfig.BlackUserIDList`
      （来源：internal/secondpart/apollo/client.go:L2180）
      ↳ 确认 Apollo 各环境已配置 `blackUserIdList` 字段

## 🌐 API 接口变更
- [ ] 新增响应字段 `IndexResp.IsBlacklisted`
      （来源：internal/app/membershipinvite/api/index.go:L42）
      ↳ 新增字段，向后兼容，确认前端已适配

---

## ✅ 基础检查（每次上线必做）
- [ ] 代码已通过 CI（lint + build + test）
- [ ] MR 已通过 Code Review
- [ ] 涉及的进程需要重启：front, mq2, schedule
- [ ] 回滚方案：代码可直接回滚，新增字段有默认值不影响旧代码
```

## 与其他 skill 配合

| 配合 skill | 场景 |
|-----------|------|
| `/ai-code-review` | 先 review 代码质量，再生成上线清单 |
| `/generate-test-doc` | 上线清单 + 提测文档一起准备 |
| `/campaign-apidoc` | 如果有 API 变更，同步更新接口文档 |

## 输出到飞书

生成检查清单后，会询问是否输出到飞书云文档。选择"输出到飞书"后自动创建文档并返回链接，方便团队协作和逐项确认。

## FAQ

**Q: 检查清单是否会有误报？**

A: 会有少量。skill 倾向于"宁多勿漏"——多一个不需要的检查项比漏掉一个关键项安全得多。你可以快速划掉不适用的项。

**Q: 只改了测试文件，会生成清单吗？**

A: 不会。测试文件（`*_test.go`）、mock 文件、文档文件会被自动过滤。

**Q: 支持非 Go 项目吗？**

A: 部分维度支持（DB migration、配置文件、API 变更等通用维度）。Go 特有维度（Wire、gorm tag）在非 Go 项目中会被跳过。
