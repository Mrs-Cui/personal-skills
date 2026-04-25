---
name: check-apidoc
description: 校验 OpenAPI 3.0 接口文档的结构合法性与接口完整性。分两层执行：脚本层（结构校验）+ AI 层（接口完整性）。触发场景：用户说 /check-apidoc、检查API文档、验证接口文档、文档校验；或由 campaign-apidoc skill 在生成完成后自动调用。参数支持文件路径或 module+layer 格式，例如 /check-apidoc /path/to/member_front.json 或 /check-apidoc meetup front。
---

# check-apidoc

对已生成的 OpenAPI JSON 文档执行两层校验，输出结构化报告。

## 工作流

### 第 1 步：解析参数，定位文件

支持两种参数格式：

**格式 A：直接传文件路径**

```
/check-apidoc /path/to/member_front.json
```

直接使用该路径作为目标文件。

---

**格式 B：module + layer（campaign 项目快捷方式）**

```
/check-apidoc meetup front
/check-apidoc rewardcenter infra
```

自动推导路径：`{cwd}/../campaign-api-doc/reference/{module}_{layer}.json`

（`cwd` 为当前工作目录，即 campaign 仓库根目录）

---

若文件不存在，立即报错退出。

---

### 第 2 步：脚本层校验（结构性）

运行内置校验脚本：

```bash
python3 ~/.claude/skills/check-apidoc/scripts/validate.py <文件路径>
```

脚本检查项：
- JSON 格式合法性
- 顶级字段完整性（`openapi`、`info`、`paths`、`components`、`tags`）
- 所有 `$ref` 引用的 schema 是否在 `components/schemas` 中已定义
- 每个接口是否含 `operationId`、`summary`、`tags`、`responses`
- `responses` 中禁止直接写 `allOf`（必须用 `$ref` 引用 schema）
- `deprecated` 拼写检查
- `CommonResponse` 若存在，检查是否有 `properties` 字段
- 时间戳字段是否有 `"format": "int64"`（警告级别）
- `x-stoplight.id` 是否存在（警告级别，Stoplight 平台专用）
- `x-last-updated`、`x-source-handler` 是否存在（警告级别，可选元数据）

**若脚本报告 ❌ 错误，直接在报告中列出并终止，不进入第 3 步。**
若只有 ⚠️ 警告，继续执行第 3 步。

---

### 第 3 步：AI 层校验（接口完整性）

从 JSON 的 `info.x-source-handler` 获取 handler 文件路径。若该字段不存在，跳过此步并在报告中注明。

**第一步：统计 JSON 中的接口数**

```python
json_count = len(doc["paths"])
```

**第二步：统计源码中的路由数**

grep handler 文件中的路由注册行：

```bash
grep -n "\.Handle\|\.GET\|\.POST\|\.PUT\|\.DELETE\|\.PATCH" \
  <handler_path> | grep -v "^\s*//"
```

若结果为空，说明该文件本身不含路由注册，可能注册在主路由文件中（如 campaign 的 `cmd/campaign/1_front.go`）。此时提示用户手动确认，不强制报错。

统计有效路由行数（排除注释行）= `source_count`

**第三步：对比**

| 情况 | 结论 |
|------|------|
| `json_count == source_count` | ✅ 接口数匹配 |
| `json_count < source_count` | ❌ 文档缺少接口，列出源码中有但 JSON paths 中没有的路径 |
| `json_count > source_count` | ⚠️ 文档接口数多于源码，可能有多余条目 |

**路径对比方法：**
从 Grep 结果提取路由字符串（引号内的路径），与 JSON paths 的 key 做差集，列出缺失项。

---

### 第 4 步：输出报告

格式如下：

```
╔══════════════════════════════════════════════════╗
║  check-apidoc 校验报告：{filename}               ║
╚══════════════════════════════════════════════════╝

【脚本层】结构校验
  ✅ 无结构性错误
  ⚠️  1 条警告：info 缺少 x-source-handler

【AI 层】接口完整性
  ✅ 接口数匹配：JSON 75 个 / 源码 75 个
  — 或 —
  ❌ 缺少 3 个接口：
     · POST /api/v1/xxx/activate
     · GET  /api/v1/yyy/list
     · ...

【总结】
  ✅ 校验通过  — 或 —  ❌ 发现 N 个问题，需要修复
```

若发现 ❌ 错误，给出具体修复建议（是哪步骤出错、如何补充）。

---

## 注意事项

- 脚本层是客观检查，有 ❌ 就必须修复后重新生成
- AI 层路由计数允许 ±1 的误差（handler 文件偶有非标准注册方式）
- 若 `x-source-handler` 不存在，跳过 AI 层并在报告中注明
- `x-last-updated`、`x-source-handler`、`x-stoplight.id` 均为可选元数据，缺失只产生警告不报错
