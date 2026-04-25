# Campaign API 文档生成规范

本规范适用于 `campaign-api-doc` 仓库中所有 OpenAPI 文档的生成与维护。
文档托管于 **Stoplight**，格式为 **OpenAPI 3.0.0 JSON**。

---

## 一、文件组织规范

### 文件命名

每个业务模块按层级各一个文件，命名格式为 `{模块}_{层级}.json`：

```
reference/
  meetup_admin.json       # 会议活动 - 后台管理接口
  meetup_front.json       # 会议活动 - H5 前端接口
  score_admin.json        # 虎币商城 - 后台管理接口
  score_front.json        # 虎币商城 - 前端接口
  member_admin.json       # 会员 - 后台管理接口
  member_front.json       # 会员 - 前端接口
  ...
```

层级对应服务端点：

| 层级 | 端点 | 说明 |
|------|------|------|
| `admin` | `/campaign/admin` | 后台 CRM 管理接口 |
| `front` | `/campaign/front` | H5/App 前端接口 |
| `infra` | `/campaign/infra` | 基础设施接口 |
| `intranet` | `/campaign/intranet` | 内网服务间调用接口 |
| `internal` | `/campaign/internal` | 内部服务接口 |

### toc.json 维护

每新增一个文件，必须在 `toc.json` 的 `items` 中添加对应条目：

```json
{
  "type": "item",
  "title": "会议活动 admin 接口文档",
  "uri": "/reference/meetup_admin.json"
}
```

---

## 二、文档基本结构

```json
{
  "openapi": "3.0.0",
  "x-stoplight": {
    "id": "<16位随机小写字母+数字>"
  },
  "info": {
    "title": "{业务名} {层级} 接口文档",
    "version": "1.0.0",
    "description": "{功能简述}"
  },
  "servers": [
    {
      "url": "https://test-marketing.tigerfintech.com/campaign/{layer}",
      "description": "Staging development server"
    },
    {
      "url": "https://marketing.tigerfintech.com/campaign/{layer}",
      "description": "Production server"
    }
  ],
  "paths": { ... },
  "components": {
    "schemas": { ... }
  },
  "tags": [ ... ]
}
```

### info.title 命名示例

| 文件 | title |
|------|-------|
| meetup_admin.json | `"会议活动 admin 接口文档"` |
| meetup_front.json | `"会议活动 front 接口文档"` |
| score_admin.json  | `"虎币商城 admin 接口文档"` |

### x-stoplight id

- **根级必须**有 `x-stoplight.id`，Stoplight 用于识别文档
- 格式：16 位小写字母 + 数字随机组合，例如 `"7w3ftdm1pix8q"`
- AI 生成文档时**不需要**为每个字段加 `x-stoplight.id`，只加根级即可

---

## 三、路径定义规范

### 路径与代码保持一致

路径必须与 Handler 代码中的 `Group()` 定义完全一致，不做任何转换：

```go
// 代码 (meetup adminhandler)
meetup     := apiv1.Group("/meetups")
category   := apiv1.Group("/meetup-categories")   // kebab-case
scoreDraw  := apiv1.Group("/score")
tradeShare := apiv1.Group("/trade_share")          // snake_case（旧模块）
```

```json
// 对应文档路径
"/api/v1/meetups"
"/api/v1/meetup-categories"
"/api/v1/score"
"/api/v1/trade_share"
```

### 路径参数转换

Handler 中的 `:id` 转为 OpenAPI 的 `{id}`：

```go
// 代码
meetup.GET("/:id", ...)
meetup.GET("/:id/participation-policies", ...)
```

```json
// 文档
"/api/v1/meetups/{id}"
"/api/v1/meetups/{id}/participation-policies"
```

### HTTP 方法语义

| HTTP 方法 | 语义 |
|-----------|------|
| GET | 查询（列表或详情） |
| POST | 创建 / 提交 / 特殊操作 |
| PUT | 全量更新 |
| PATCH | 部分更新 |
| DELETE | 删除 |

---

## 四、operationId 规范

每个接口必须有**全局唯一**的 operationId，使用 **camelCase** RESTful 风格：

| HTTP 方法 | 操作 | 格式 | 示例 |
|-----------|------|------|------|
| GET（列表） | 查询列表 | `list{Resources}` | `listMeetups` |
| GET（详情） | 查询详情 | `get{Resource}Detail` | `getMeetupDetail` |
| POST（创建） | 创建资源 | `create{Resource}` | `createMeetup` |
| PUT / PATCH（更新） | 更新资源 | `update{Resource}` | `updateMeetup` |
| DELETE（删除） | 删除资源 | `delete{Resource}` | `deleteMeetup` |
| POST（特殊操作） | 业务动作 | `{action}{Resource}` | `publishMeetup`、`submitMeetupApproval` |

---

## 五、Tags 规范

### 定义位置

Tags 在文件**末尾**统一声明，每个操作中引用：

```json
// 文件末尾
"tags": [
  { "name": "会议活动",       "description": "活动的增删改查" },
  { "name": "报名用户",       "description": "用户报名审核管理" },
  { "name": "品类管理",       "description": "活动品类的增删改查" },
  { "name": "聚合页",         "description": "聚合页的增删改查" },
  { "name": "黑白名单",       "description": "黑白名单管理" },
  { "name": "参与限制策略",   "description": "参与限制策略管理" }
]
```

### 规则

- Tag 名称使用**中文业务术语**
- 每个接口操作必须指定 `tags`
- 新增模块时，先在末尾声明 tag，再在操作中引用
- Tag 名称来源：对应 Service 文件的业务含义（如 `service/admin/category.go` → `品类管理`）

---

## 六、参数规范

### Query 参数

从 Handler 的 `ShouldBindQuery` 绑定的结构体提取，`type` 必须放在 `schema` 内：

```json
{
  "name": "page",
  "in": "query",
  "required": false,
  "schema": {
    "type": "integer",
    "default": 1
  },
  "description": "页码"
}
```

### 标准分页参数

```json
[
  {
    "name": "page",
    "in": "query",
    "schema": { "type": "integer", "default": 1 },
    "description": "页码"
  },
  {
    "name": "page_size",
    "in": "query",
    "schema": { "type": "integer", "default": 20 },
    "description": "每页数量"
  }
]
```

### Path 参数

```json
{
  "name": "id",
  "in": "path",
  "required": true,
  "schema": { "type": "integer" },
  "description": "活动ID"
}
```

### 各层认证方式

不同服务层的认证方式不同，生成文档时**不要统一声明认证参数**，按层级处理：

| 层级 | 认证方式 | 文档处理 |
|------|---------|---------|
| `front` | `Authorization: Bearer <access_token>`（AMS gRPC 验证），部分接口强制登录 | 无需声明认证参数，调用方自行携带 |
| `admin` | `Authorization: <CRM Token>`（CRM 系统验证），三个级别见下方说明 | 无需声明认证参数，在 description 中说明所需权限级别 |
| `intranet`（多数路由） | 无认证，依赖网络隔离 | 无需声明认证参数 |
| `intranet`（部分路由组） | 内网签名：`InnerSignMiddlewareWithApollo()` | 需声明 4 个 Header 参数，见下方 |
| `infra` `/internal/api/` | 无认证，依赖网络隔离 | 无需声明认证参数 |
| `infra` `/public/api/v1` | `Authorization: Bearer`（可选登录） | 无需声明认证参数 |
| `infra` `/public/api/v2~v3` | `Authorization: Bearer`（强制登录） | 无需声明认证参数 |

**内网签名参数**（仅用于 intranet 中加了 `InnerSignMiddlewareWithApollo()` 的路由组）：

识别方法：Handler 的 `HandleOnApiV2` 中路由组有 `.Use(h.SignMiddle.InnerSignMiddlewareWithApollo())`，例如 `rewardv2.Internal`、`member2.Internal`、`activity.Internal`、`score2.Internal`。

```json
[
  { "name": "inner-app-id", "in": "header", "required": true, "schema": { "type": "string" }, "description": "调用方应用标识" },
  { "name": "timestamp",    "in": "header", "required": true, "schema": { "type": "string" }, "description": "毫秒时间戳" },
  { "name": "nonce",        "in": "header", "required": true, "schema": { "type": "string" }, "description": "随机数" },
  { "name": "sign",         "in": "header", "required": true, "schema": { "type": "string" }, "description": "签名，算法：MD5(inner-app-id + secret + timestamp + nonce)" }
]
```

这 4 个参数已在 `admin_base_schemas.json` 的 `parameters` 中定义（`HeaderInnerAppId` 等），**仅在上述签名路由中**通过 `$ref` 引用，其他层直接跳过 parameters 部分。

**Admin 层三级认证详解**

Admin 层全局挂载 `Login.AdminMiddleware()`（宽松解析 CRM Token），在此基础上路由级别还有：

| 中间件 | 使用场景 | 识别方式 |
|--------|---------|---------|
| 无额外中间件 | 只读/查询接口，允许未登录访问 | Handler 注册时无额外鉴权中间件 |
| `Login.AdminCheckMiddleware()` | 写操作（创建/修改/删除）等需要登录的接口 | Handler 注册时有 `a.Login.AdminCheckMiddleware()` |
| `Crm.PermissionMiddleware(code...)` | 敏感操作，需要特定 CRM 权限 | Handler 注册时有 `a.Crm.PermissionMiddleware(...)` |
| `Login.InnerTokenCheck()` | 内部服务调用（极少数，如 `/handover`） | `Authorization: Basic <token>` |

> 文档生成时无需在 OpenAPI parameters 中声明这些 Header，但建议在接口 `description` 字段注明权限要求，例如：`"需要 CRM 登录"` 或 `"需要权限：PermissionCode_MeetupActivity"`。

### ❌ 禁止：Swagger 2.0 风格的参数写法

```json
// ❌ 错误：type 不能在参数顶层（这是 Swagger 2.0 写法）
{ "name": "page", "in": "query", "type": "integer" }

// ✅ 正确：type 在 schema 内
{ "name": "page", "in": "query", "schema": { "type": "integer" } }
```

---

## 七、RequestBody 规范

从 Handler 的 `ShouldBindJSON` 绑定的结构体提取：

```json
"requestBody": {
  "required": true,
  "content": {
    "application/json": {
      "schema": {
        "type": "object",
        "properties": {
          "license": {
            "type": "string",
            "enum": ["TBNZ", "TBAU", "TFNZ", "TBSG", "TBHK", "TBMS"],
            "description": "牌照"
          },
          "name": {
            "type": "string",
            "description": "品类名称，最大长度100字符"
          }
        },
        "required": ["license", "name"]
      }
    }
  }
}
```

### 必填字段

Go struct 中带 `binding:"required"` tag 的字段，必须出现在 `required` 数组中：

```go
// Go 代码
type ReqCreateCategory struct {
    License string `json:"license" binding:"required"`
    Name    string `json:"name"    binding:"required"`
    Remark  string `json:"remark"`                      // 非必填
}
```

```json
// 对应文档
"required": ["license", "name"]
```

---

## 八、响应规范（最重要）

### 统一响应格式

所有接口的响应格式：

```json
{
  "code":     0,
  "message":  "success",
  "data":     { ... },
  "trace_id": "ba7743f092a59efd6a9b077d32aa7c20",
  "is_succ":  true
}
```

### 响应定义两步走

**第一步**：在 `components/schemas` 中定义响应 schema

```json
"components": {
  "schemas": {
    "ResponseCategoryList": {
      "allOf": [
        { "$ref": "#/components/schemas/CommonResponse" },
        {
          "type": "object",
          "properties": {
            "data": {
              "type": "object",
              "properties": {
                "total_count": { "type": "integer", "description": "总数量" },
                "items": {
                  "type": "array",
                  "items": { "$ref": "#/components/schemas/CategoryItem" }
                }
              }
            }
          },
          "required": ["data"]
        }
      ]
    }
  }
}
```

**第二步**：在接口的 `responses` 中用 `$ref` 引用

```json
"responses": {
  "200": {
    "description": "品类列表",
    "content": {
      "application/json": {
        "schema": {
          "$ref": "#/components/schemas/ResponseCategoryList"
        }
      }
    }
  }
}
```

### ❌ 禁止：在 responses 中直接写 allOf

```json
// ❌ 错误：不允许在 responses 块中直接使用 allOf
"responses": {
  "200": {
    "content": {
      "application/json": {
        "schema": {
          "allOf": [
            { "$ref": "#/components/schemas/CommonResponse" },
            { ... }
          ]
        }
      }
    }
  }
}
```

---

## 九、Components/Schemas 规范

### 必须定义的通用组件

每个文档都必须包含以下通用 schema：

```json
"components": {
  "schemas": {

    "CommonResponse": {
      "type": "object",
      "description": "统一响应结构",
      "properties": {
        "code":     { "type": "integer", "description": "业务状态码，0表示成功，非0表示失败" },
        "message":  { "type": "string",  "description": "业务提示信息或错误信息" },
        "data":     { "description": "业务数据载体，结构由具体接口定义", "nullable": true },
        "trace_id": { "type": "string",  "description": "链路追踪ID" },
        "is_succ":  { "type": "boolean", "description": "是否成功，code==0为true" }
      },
      "required": ["code", "message", "data", "trace_id", "is_succ"]
    },

    "ResponseSuccess": {
      "allOf": [
        { "$ref": "#/components/schemas/CommonResponse" },
        { "type": "object", "properties": { "data": { "nullable": true, "description": "操作成功，无返回数据" } } }
      ]
    },

    "ResponseCreated": {
      "allOf": [
        { "$ref": "#/components/schemas/CommonResponse" },
        { "type": "object", "properties": { "data": { "type": "object", "properties": { "id": { "type": "integer", "description": "创建的资源ID" } } } }, "required": ["data"] }
      ]
    },

    "ResponseDeleted": {
      "allOf": [
        { "$ref": "#/components/schemas/CommonResponse" },
        { "type": "object", "properties": { "data": { "nullable": true, "description": "删除成功，无返回数据" } } }
      ]
    },

    "ResponseUpdated": {
      "allOf": [
        { "$ref": "#/components/schemas/CommonResponse" },
        { "type": "object", "properties": { "data": { "nullable": true, "description": "更新成功，无返回数据" } } }
      ]
    }
  }
}
```

### Schema 命名规范

| 类型 | 命名格式 | 示例 |
|------|---------|------|
| 列表项数据模型 | `{Resource}Item` | `MeetupItem`、`CategoryItem` |
| 详情数据模型 | `{Resource}Detail` | `MeetupDetail`、`CategoryDetail` |
| 配置数据模型 | `{Resource}Config` | `MeetupConfig`、`NotifyConfig` |
| 请求体 schema | `Req{Action}{Resource}` | `ReqCreateMeetup`、`ReqListCategory` |
| 具体响应 schema | `Response{Resource}{Action}` | `ResponseMeetupList`、`ResponseMeetupDetail` |

### Schema 定义顺序

```
1. CommonResponse
2. ResponseSuccess / ResponseCreated / ResponseDeleted / ResponseUpdated
3. 业务数据模型（XxxItem、XxxDetail、XxxConfig 等）
4. 具体接口响应（ResponseXxxList、ResponseXxxDetail 等）
```

---

## 十、字段类型规范

### 整数类型

| 场景 | 写法 |
|------|------|
| 普通整数（ID、计数、状态码） | `"type": "integer"` |
| 时间戳、大数值（金额、UUID） | `"type": "integer", "format": "int64"` |

### 时间戳统一格式

```json
{
  "open_time": {
    "type": "integer",
    "format": "int64",
    "description": "活动开始时间(13位毫秒时间戳)"
  }
}
```

### 枚举值

```json
{
  "status": {
    "type": "string",
    "enum": ["created", "approval_pending", "enabled", "disabled", "deleted"],
    "description": "活动状态: created 已创建, approval_pending 审批中, enabled 已启用, disabled 已禁用, deleted 已删除"
  }
}
```

- `enum` 只用于 `type: string` 或 `type: integer` 字段
- **禁止**在 `type: string` 字段上使用 `items`（`items` 是 `type: array` 专用）

### 废弃字段

```json
{
  "activity_start_time": {
    "type": "integer",
    "format": "int64",
    "deprecated": true,
    "description": "[已废弃] 活动开始时间(13位毫秒时间戳)"
  }
}
```

> ⚠️ 注意拼写：`deprecated`，不是 `depcrecated`

### 字段描述规范

| 规则 | 示例 |
|------|------|
| 主要用中文 | `"description": "活动名称"` |
| 数字类型说明单位 | `"description": "净入金金额，单位 HKD"` |
| 时间戳说明位数 | `"description": "活动开始时间(13位毫秒时间戳)"` |
| 枚举值逐一说明 | `"description": "状态: active 生效中, deleted 已删除"` |
| 废弃字段加前缀 | `"description": "[已废弃] xxx"` |

---

## 十一、从代码生成文档的流程

### 第 1 步：分析 Handler 路由

从 `HandleOnApiV1` / `HandleOnApiV2` 等方法提取路由定义：

```go
// 从代码
category := apiv1.Group("/meetup-categories").Use(login, check)
category.GET("", h.listMeetupCategories)
category.POST("", h.createMeetupCategory)
category.DELETE("/:id", h.deleteMeetupCategory)
```

提取信息：
- 路径：`/api/v1/meetup-categories`
- Tag：`品类管理`
- operationId 映射：
  - `GET /api/v1/meetup-categories` → `listMeetupCategories`
  - `POST /api/v1/meetup-categories` → `createMeetupCategory`
  - `DELETE /api/v1/meetup-categories/{id}` → `deleteMeetupCategory`

### 第 2 步：查找 Request / Response 结构体

在 Service 层查找对应的 Req/Res struct，从 `json` tag 提取字段名，从 `binding` tag 判断是否必填：

```go
// service/admin/category.go
type ReqCreateCategory struct {
    License string `json:"license" binding:"required,max=20"`
    Name    string `json:"name"    binding:"required"`
}

type ResListCategory struct {
    TotalCount int64                 `json:"total_count"`
    Items      []ResListCategoryItem `json:"items"`
}
```

### 第 3 步：按顺序定义 components/schemas

1. 确认 CommonResponse 及通用 CRUD 响应已定义
2. 定义业务数据模型（`CategoryItem` 等）
3. 定义具体响应（`ResponseCategoryList` 等）

### 第 4 步：定义 paths

- 每个操作引用 components/schemas 中的响应 schema
- 确保 operationId 全局唯一
- 确保每个操作都有 tags

### 第 5 步：声明 tags（文件末尾）

### 第 6 步：更新 toc.json

---

## 十二、常见错误速查

| 错误 | 正确做法 |
|------|---------|
| `"depcrecated": true` | `"deprecated": true` |
| `string` 类型使用 `"items": [...]` | 改用 `"enum": [...]` |
| `trace_id`/`is_succ` 写在 `properties` 外 | 必须在 `properties` 对象内 |
| 在 `responses` 中直接写 `allOf` | 先在 `components/schemas` 定义，再用 `$ref` 引用 |
| 参数 `type` 写在顶层 | `type` 放在 `schema` 对象内 |
| 使用 `"in": "body"` | 改用 `requestBody` 对象 |
| 内联重复写 code/message/data/trace_id/is_succ | 通过 `$ref: CommonResponse` + `allOf` 组合 |
| 多个字段共用同一个 `x-stoplight.id` | 每个 id 必须全局唯一（或不加字段级 id） |
| 缺少根级 `x-stoplight.id` | 每个文档根级必须有唯一 id |
| 新文件未加入 toc.json | 每次新增文件后同步更新 toc.json |

---

## 十三、生成检查清单

生成或更新文档时逐项确认：

- [ ] `openapi: "3.0.0"`
- [ ] 根级有 `x-stoplight.id`（唯一值）
- [ ] `servers` 包含 staging 和 production 两个地址
- [ ] 所有路径与 Handler 代码中 `Group()` 定义一致
- [ ] 每个操作有唯一的 `operationId`（camelCase RESTful 风格）
- [ ] 每个操作有 `tags`
- [ ] 所有 `tags` 在文件末尾统一声明
- [ ] Query/Path 参数的 `type` 在 `schema` 内，不在顶层
- [ ] POST/PUT 接口有 `requestBody`，struct `binding:"required"` 字段在 `required` 数组中
- [ ] 所有响应 schema 定义在 `components/schemas` 中
- [ ] `responses` 中用 `$ref` 引用，不直接写 `allOf`
- [ ] `CommonResponse` 及通用 CRUD 响应已定义
- [ ] 时间戳字段有 `format: int64` 且描述说明"13位毫秒时间戳"
- [ ] 枚举字段使用 `enum` 数组，不使用 `items`
- [ ] 废弃字段标记 `deprecated: true`（注意拼写）
- [ ] 所有 `$ref` 引用路径有效
- [ ] `toc.json` 已更新

---

## 附录：完整文件模板

```json
{
  "openapi": "3.0.0",
  "x-stoplight": {
    "id": "请替换为唯一16位随机id"
  },
  "info": {
    "title": "{模块名} {层级} 接口文档",
    "version": "1.0.0",
    "description": "{功能简述}"
  },
  "servers": [
    {
      "url": "https://test-marketing.tigerfintech.com/campaign/{layer}",
      "description": "Staging development server"
    },
    {
      "url": "https://marketing.tigerfintech.com/campaign/{layer}",
      "description": "Production server"
    }
  ],
  "paths": {
    "/api/v1/{resource}": {
      "get": {
        "operationId": "list{Resources}",
        "summary": "获取列表",
        "tags": ["{Tag名称}"],
        "parameters": [],
        "responses": {
          "200": {
            "description": "列表数据",
            "content": {
              "application/json": {
                "schema": { "$ref": "#/components/schemas/Response{Resource}List" }
              }
            }
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "CommonResponse": {
        "type": "object",
        "description": "统一响应结构",
        "properties": {
          "code":     { "type": "integer", "description": "业务状态码，0表示成功，非0表示失败" },
          "message":  { "type": "string",  "description": "业务提示信息或错误信息" },
          "data":     { "description": "业务数据载体，结构由具体接口定义", "nullable": true },
          "trace_id": { "type": "string",  "description": "链路追踪ID" },
          "is_succ":  { "type": "boolean", "description": "是否成功，code==0为true" }
        },
        "required": ["code", "message", "data", "trace_id", "is_succ"]
      },
      "ResponseSuccess": {
        "allOf": [
          { "$ref": "#/components/schemas/CommonResponse" },
          { "type": "object", "properties": { "data": { "nullable": true, "description": "操作成功，无返回数据" } } }
        ]
      },
      "ResponseCreated": {
        "allOf": [
          { "$ref": "#/components/schemas/CommonResponse" },
          {
            "type": "object",
            "properties": {
              "data": {
                "type": "object",
                "description": "创建成功返回的数据",
                "properties": {
                  "id": { "type": "integer", "description": "创建的资源ID" }
                }
              }
            },
            "required": ["data"]
          }
        ]
      },
      "ResponseDeleted": {
        "allOf": [
          { "$ref": "#/components/schemas/CommonResponse" },
          { "type": "object", "properties": { "data": { "nullable": true, "description": "删除成功，无返回数据" } } }
        ]
      },
      "ResponseUpdated": {
        "allOf": [
          { "$ref": "#/components/schemas/CommonResponse" },
          { "type": "object", "properties": { "data": { "nullable": true, "description": "更新成功，无返回数据" } } }
        ]
      }
    }
  },
  "tags": [
    { "name": "{Tag名称}", "description": "{Tag说明}" }
  ]
}
```
