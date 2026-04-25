---
name: campaign-apidoc
description: 为 campaign 项目的 Gin Handler 自动生成 OpenAPI 3.0 接口文档，输出到 campaign-api-doc 仓库。触发场景：用户说 /campaign-apidoc、生成接口文档、更新API文档、为某模块生成文档，或提到 campaign-api-doc。参数格式：/campaign-apidoc {module} {layer}，例如 /campaign-apidoc meetup front、/campaign-apidoc meetup admin、/campaign-apidoc member front。也支持 URL 前缀模式：/campaign-apidoc /api/v1/contra-invite。
---

# gen-apidoc

为 campaign 项目 Gin Handler 生成符合 OpenAPI 3.0.0 规范的接口文档。

## 工作流

### 路径推导（每次执行前）

路径**自动推导**，无需任何配置文件：

- **`{campaign_dir}`**：当前工作目录（即 campaign 仓库根目录）
- **`{doc_dir}`**：`{campaign_dir}/../campaign-api-doc`（与 campaign 同级）

**检查：确认文档仓库是否存在**

检查 `{doc_dir}` 目录是否存在。若不存在，停止执行并提示用户先克隆仓库（在 campaign 的父目录下执行）：

```bash
git clone git@git.tigerbrokers.net:astro/campaign-api-doc.git
```

克隆完成后重新执行本命令。

**检查并拉取最新代码**

仓库存在后，执行以下命令检查远端是否有更新：

```bash
cd {doc_dir} && git fetch origin && git status -uno
```

- 若输出包含 `Your branch is behind`，说明有新提交，自动执行：
  ```bash
  git pull origin $(git rev-parse --abbrev-ref HEAD)
  ```
  拉取成功后输出：`✅ campaign-api-doc 已更新到最新`
- 若已是最新，输出：`✅ campaign-api-doc 已是最新，无需拉取`
- 若 git 命令失败（网络问题等），输出警告但**不中断执行**：
  `⚠️ 拉取失败，继续使用本地版本`

---

### 第 1 步：解析参数

支持两种输入格式，先判断类型再处理：

---

**格式 A：`module + layer`（标准模式）**

```
/gen-apidoc meetup front
/gen-apidoc rewardcenter infra
```

直接提取：
- `module`：`meetup`
- `layer`：`front`
- 输出文件：`{doc_dir}/reference/{module}_{layer}.json`

---

**格式 B：URL 前缀（前缀模式）**

输入以 `/` 开头，例如：

```
/gen-apidoc /api/v1/contra-invite
/gen-apidoc /public/api/v2/reward-center
```

执行前缀反查，四步完成：

**① 提取路由关键词**：去掉版本前缀，取最后一段有意义的词。
例：`/api/v1/contra-invite` → 关键词 `contra-invite`

**② Grep 找 handler 文件**：

```bash
grep -r "contra-invite" {campaign_dir}/internal \
  --include="*.go" -l | grep -v "_test.go"
```

**③ 从文件路径推导 module 和 layer**：

| 文件路径 | module | layer |
|---------|--------|-------|
| `internal/app/{module}/fronthandler.go` | `{module}` | `front` |
| `internal/app/{module}/adminhandler.go` | `{module}` | `admin` |
| `internal/app/{module}/front.go` | `{module}` | `front` |
| `internal/app/{module}/admin.go` | `{module}` | `admin` |
| `internal/services/{module}/front_handlers.go` | `{module}` | `front` |
| `internal/iface/http/{layer}/{module}/*.go` | `{module}` | `{layer}` |

文件名含 `front` → layer=`front`；含 `admin` → layer=`admin`；
含 `infra` → layer=`infra`；含 `intranet` → layer=`intranet`。

**④ 输出文件路径**：与标准模式相同：
`{doc_dir}/reference/{module}_{layer}.json`

> ⚠️ **前缀只用于定位 handler，文档覆盖该 handler 文件的全部接口。**
> 例如 `/api/v1/contra-invite` 定位到 `contra2025/front.go`，
> 则生成的文档包含该文件里所有接口（含 `/newcomer/index`）。

---

若 Grep 找到多个候选文件，列出来让用户确认后再继续。

### 第 2 步：并行读取规范

⚠️ **在同一条消息中同时读取以下两个文件（不要分两次读）：**
- `references/spec.md` — 文档生成完整规范
- `references/project-map.md` — 模块路径映射

layer 为 `admin`/`infra`/`intranet`/`internal` 时，同时加上：
- `references/admin_base_schemas.json` — 通用组件模板（必读）
  - `schemas` 部分（CommonResponse 等）所有非 front 层均需复用
  - `parameters` 部分（内网签名 Header）**仅**用于 intranet 层中 Handler 加了 `InnerSignMiddlewareWithApollo()` 的路由组，其他层跳过

### 第 3 步：一次性并行读取所有代码文件

⚠️ **核心原则：所有代码文件必须在同一条消息中并行读取，禁止串行逐文件读取。**

**第一轮（Glob/Grep 定位，不读全文）：**

```bash
# app 模式——直接用 Glob 确认路径是否存在
{campaign_dir}/internal/app/{module}/{layer}handler.go
{campaign_dir}/internal/app/{module}/service/h5/*.go      # front 层
{campaign_dir}/internal/app/{module}/service/admin/*.go   # admin 层
{campaign_dir}/internal/app/{module}/model/*.go

# services 模式——同上
{campaign_dir}/internal/services/{module}/{layer}_handler*.go
{campaign_dir}/internal/services/{module}/*.go

# 不确定时用 Grep 找含 Req/Res 的文件
grep "type Req\|type Res" {campaign_dir}/internal/ --include="*.go" -l | grep {module}
```

**第二轮（一次性并行 Read）：**

拿到路径后，在**同一条消息**中发出全部 Read 调用：
- handler 文件（完整读取，含 HandleOnApiV1/V2/V3 所有路由）
- service 目录下所有 `.go` 文件
- model 目录下相关 `.go` 文件

> **文件较多时的替代方案**：用一次 Grep 批量拿到所有结构体字段，避免 Read 大文件：
> ```bash
> grep -n "^type Req\|^type Res\|^\t[A-Z].*json:" \
>   {campaign_dir}/internal/app/{module}/service/{layer}/*.go
> ```
> 一次 Grep 即可拿到全部字段定义，只对信息不完整的结构体补充 Read。

### 第 4 步：从读取结果提取接口信息

**不需要额外的文件读取**——第 3 步已拿到所有信息。如有个别字段不确定，用 Grep 查特定常量，不要 Read 整个文件。

从 Handler 文件提取：
- 路由：`Group()` 路径 + HTTP 方法 → 完整 path（`/api/v1/...`）
- 参数绑定：`ShouldBindQuery` → query params；`ShouldBindJSON/ShouldBind` → requestBody
- 返回类型：追踪 Service 方法返回的 `Res*` 结构体

从 Service 文件提取：
- `Req*` 结构体：json tag、类型、`binding:"required"` → required 数组
- `Res*` 结构体：json tag、类型、行尾注释 → description
- `const` 块：enum 值和说明

**嵌套类型递归扫描（提取完顶层结构体后立即执行）：**

遍历所有字段类型，对非基础类型（非 `string/int/bool/float64` 等）批量 Grep 定义：
```bash
# 一次性 Grep 所有未知类型
grep -n "^type (TypeA|TypeB|TypeC) struct" {campaign_dir}/internal/ -r
```
对每个找到的子结构体，重复上述过程，直到所有字段都是基础类型或已知 schema 为止。

> **目的：** 在第 6 步生成前保证所有嵌套类型定义完整，避免用裸 `object` 占位后被用户发现再补。

### 第 5 步：输出接口清单（生成前确认）

在写入任何文件之前，先以表格形式输出本次将要生成的接口清单：

```
共 N 个接口（V1: xx, V2: xx, V3: xx）

| # | operationId | 方法 | 路径 |
|---|-------------|------|------|
| 1 | listMeetups | GET  | /api/v1/meetups |
| 2 | createMeetup | POST | /api/v1/meetups |
...

需人工确认：
- [字段名]：类型不确定（TODO）
```

**目的：** 让用户在生成前验证接口数量和路径是否正确，避免生成后才发现路由理解有误。
如果用户有异议，在此阶段修正，不要继续生成。

### 第 6 步：生成 JSON 文档

严格按照 spec.md 规范生成。

**通用组件复用（admin/infra/intranet/internal 层）：**
将 `references/admin_base_schemas.json` 中的内容粘贴到 `components` 中，但注意区分：
- `schemas`（CommonResponse 等 5 个）：**所有非 front 层**均需粘贴，不要重新手写
- `parameters`（内网签名 Header 4 个）：**仅** intranet 层中路由组加了 `InnerSignMiddlewareWithApollo()` 时才引用；admin/infra 及其他 intranet 路由不要加这 4 个参数

**结构顺序：**
```
openapi → x-stoplight → info → servers → paths → components/schemas → tags
```

**响应必须两步走（违反此规则是最常见的错误）：**
1. 在 `components/schemas` 定义 `Response{Xxx}` schema（用 allOf + $ref CommonResponse）
2. 在 `responses` 中只用 `$ref` 引用，**禁止在 responses 中直接写 allOf**

**operationId 命名（camelCase RESTful）：**
- GET 列表 → `list{Resources}`
- GET 详情 → `get{Resource}Detail`
- POST 创建 → `create{Resource}`
- PUT 更新 → `update{Resource}`
- DELETE 删除 → `delete{Resource}`
- POST 特殊操作 → `{action}{Resource}`（如 `submitApproval`、`publishMeetup`）
- 多版本接口加版本后缀：`getUserInfoV3`、`listMeetupCollectionsV2`

**接口数量 > 30 时分两次写入（避免单次输出过长）：**
1. 第一次 Write：写入完整 paths + 空的 components 占位
2. 第二次 Edit：用 `components` 完整内容替换占位

接口数量 ≤ 30 时一次 Write 完成。

**嵌套结构体必须展开（不能用裸 object）：**
Req/Res 中引用了其他包（如 `pkg.Award`、`pkg.BaseAward`）或同包的子结构体时，必须追踪并展开所有层级：
1. Grep 找到子结构体定义（可能在 `internal/services/pkg/`、`internal/services/activity/` 等处）
2. 为每个子结构体在 `components/schemas` 中单独定义 schema
3. 父结构体字段用 `"$ref"` 引用，**不允许写成 `"type": "object"` 占位**

示例：`DisplayAwardResp` → `AwardPack` → `BaseAward` → `Award`，每一层都要展开。

**常见易错点（每次生成后自查）：**
- `deprecated` 拼写，不是 `depcrecated`
- string 枚举用 `enum: [...]`，不用 `items: [...]`
- 时间戳：`"type": "integer", "format": "int64"`，description 注明"13位毫秒时间戳"
- 参数 `type` 必须在 `schema` 内，不能在参数顶层
- `trace_id` 和 `is_succ` 必须在 `properties` 内，不能是 schema 的同级字段
- 嵌套结构体不能用裸 `object` 占位，必须展开所有层级（见上方规则）

### 第 7 步：写入文件并更新 toc.json

1. 生成 JSON 前，在 `info` 对象中加入以下两个字段（与 title/version 同级）：
   ```json
   "x-last-updated": "<今天日期，格式 YYYY-MM-DD>",
   "x-source-handler": "<handler 文件的相对路径，相对于 campaign 仓库根目录>"
   ```
   示例：
   ```json
   "info": {
     "title": "奖励中心 infra 接口文档",
     "version": "1.0.0",
     "x-last-updated": "2026-03-20",
     "x-source-handler": "internal/iface/http/infra/rewardcenter/rewardcenter.go"
   }
   ```

2. 将生成的 JSON 写入输出文件

3. 检查 `{doc_dir}/toc.json`：
   - 若已有该条目则跳过
   - 否则在 `items` 数组末尾追加：
     ```json
     { "type": "item", "title": "{模块名} {layer} 接口文档", "uri": "/reference/{module}_{layer}.json" }
     ```

> **说明：** `x-last-updated` 和 `x-source-handler` 供 `scripts/summary.sh` 使用，
> 可一键查看所有模块的接口数、更新时间，以及源码是否在文档生成后有过新提交（过期检测）。

### 第 8 步：输出总结并自动校验

1. 先输出生成总结：
   - 生成的文件路径
   - 接口列表（operationId + HTTP方法 + 路径）
   - 是否有需要人工确认的字段（类型不确定、描述缺失等）

2. 立即使用 Agent 工具启动 check-apidoc 校验 agent（**foreground，等待结果后再结束**）：

   ```
   subagent_type: general-purpose
   prompt: |
     对以下文件执行 check-apidoc 校验（执行 check-apidoc skill 的第 2~4 步）：
     - 文件路径：{doc_dir}/reference/{module}_{layer}.json
     - module: {module}，layer: {layer}
     请完整输出校验报告。
   ```

3. 将 agent 返回的校验报告追加到本次总结中，一并展示给用户。

### 第 9 步：更新知识库

每次成功生成文档后，执行以下操作。

---

**① 更新 `{doc_dir}/references/module-index.json`（必做）**

读取当前文件，在 `modules` 对象中添加或更新当前 module/layer 条目：

```json
"{module}": {
  "{layer}": {
    "handler": "<handler 文件相对路径，相对 campaign 仓库根目录>",
    "doc": "reference/{module}_{layer}.json",
    "notes": "<若为直接注册模式，注明 '路由注册在 cmd/campaign/1_front.go XXX 块'；否则省略>"
  }
}
```

若 `url_prefix_hints` 中没有该模块的路由前缀，也一并追加：

```json
"/api/v1/{prefix}": "{module}/{layer}"
```

> 只追加/更新，不删除已有条目。若该模块已存在，覆盖旧内容。

---

**② 更新 `~/.claude/projects/-Users-tiger-project-campaign/memory/MEMORY.md`（按需）**

仅在生成过程中**发现了新的规律性知识**时才更新，例如：
- 新的路由注册模式（不同于已记录的两种）
- 新的 Go 类型序列化特例（如新的 decimal/time 处理方式）
- 特殊的参数绑定或响应结构约定

**不要** 在 MEMORY.md 中维护模块列表——模块信息已由 `module-index.json` 统一管理。

---

## 处理特殊情况

**文件已存在（更新模式）：** 追加新接口，更新已有接口，不删除旧接口（除非用户明确要求）。

**接口无返回数据：** 使用 `$ref: "#/components/schemas/ResponseSuccess"`。

**Req/Res 找不到：** 用 Grep 搜整个 `{campaign_dir}/internal/`；若确实找不到，标注 `// TODO: 需要确认类型`。

## 参考文件

- `references/spec.md` — OpenAPI 文档生成完整规范（第 2 步必读）
- `references/project-map.md` — 模块路径映射和定位策略（第 2 步必读）
- `references/admin_base_schemas.json` — admin/infra/intranet/internal 层通用组件模板（第 2、5 步必读）
