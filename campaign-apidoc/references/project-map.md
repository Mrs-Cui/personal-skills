# Campaign 项目模块文件路径映射

## 项目根目录

路径变量来自 `{doc_dir}/.campaign-doc.json`：

- 代码仓库：`{campaign_dir}/`
- 文档仓库：`{doc_dir}/`
- 生成规范：`{doc_dir}/SPEC.md`
- 目录文件：`{doc_dir}/toc.json`
- 文档输出：`{doc_dir}/reference/{module}_{layer}.json`

## 两种模块代码结构

### 结构 A：app 模式（新模块）

路径规律：`internal/app/{module}/`

```
internal/app/{module}/
  ├── fronthandler.go         # front 层路由 + handler
  ├── adminhandler.go         # admin 层路由 + handler
  └── service/
      ├── h5/                 # front 层 service，含 Req/Res 结构体
      │   ├── activity.go
      │   ├── collection.go
      │   └── popup.go
      └── admin/              # admin 层 service，含 Req/Res 结构体
          ├── meetup.go
          ├── category.go
          └── ...
```

已知 app 模式模块：`meetup`、`hktransferingift2026`、`offlineevent`、`quizzes`、`contra2025`、`teamgame2026`

**URL 前缀 → 模块名对照（app 模式特殊情况）：**

| URL 前缀 | 模块目录 | 说明 |
|---------|---------|------|
| `/api/v1/contra-invite` | `contra2025` | 目录名与路由前缀不一致 |
| `/api/v1/newcomer` | `contra2025` | 同 handler，不同路由 group |
| `/api/v1/team-game-2026` | `teamgame2026` | 横杠与下划线转换 |

### 结构 B：services 模式（旧模块）

路径规律：`internal/services/{module}/`

```
internal/services/{module}/
  ├── handlers.go             # 或 front_handlers.go / admin_handler.go
  ├── front_handlers.go
  ├── admin_handler.go
  ├── internal_handler.go
  └── *.go                    # Req/Res 结构体散落在各文件中
```

已知 services 模式模块：`member`、`scorev2`（虎币商城v2）、`rewardcenterv3`

### 结构 C：iface 模式（旧模块）

路径规律：`internal/iface/http/{layer}/{module}/`

```
internal/iface/http/
  ├── front/{module}/*.go
  ├── admin/{module}/*.go
  ├── infra/{module}/*.go
  └── intranet/{module}/*.go
```

已知 iface 模式模块：旧的 member、score（已部分迁移）

## 快速定位策略

当模块路径不确定时，按顺序搜索：

```bash
# 1. 先找 handler 文件
find {campaign_dir}/internal -name "*{layer}*handler*" -o -name "*handler*{layer}*" | grep {module}

# 2. 找 Req/Res 结构体
grep -r "type Req\|type Res" {campaign_dir}/internal --include="*.go" -l | grep {module}

# 3. 找路由注册
grep -r "Group.*{module}\|{module}.*Group" {campaign_dir}/internal --include="*.go" | grep -v test
```

## 层级与 Server URL 对应关系

| 层级 | Server URL 路径 | 说明 |
|------|----------------|------|
| front | `/campaign/front` | H5/App 前端 |
| admin | `/campaign/admin` | CRM 后台管理 |
| infra | `/campaign/infra` | 基础设施 |
| intranet | `/campaign/intranet` | 内网服务间调用 |
| internal | `/campaign/internal` | 内部服务 |
