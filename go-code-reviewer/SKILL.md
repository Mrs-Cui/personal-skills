---
name: go-code-reviewer
description: "管道式Go代码审核工具，支持PR增量审核和全量代码审计。覆盖代码规范、潜在bug、边界条件、性能、安全、架构、业务逻辑七个维度。深度集成go-code-analyzer获取架构上下文，支持内置规则集（microservice/cli/general）和自定义规则扩展，严格度按代码类型自适应调整。所有输出为中文。当用户需要审核Go代码、review PR、做代码质量检查、或进行Go项目代码审计时使用。"
---

# Go Code Reviewer

管道式Go代码审核工具，分8个阶段**严格顺序**执行。

## 强制执行规则

> **以下规则不可跳过、不可简化、不可合并，无论审核对象是 diff、PR、单文件还是全量代码。**

1. **文件排除规则（最高优先级）：以下文件直接跳过，不进入任何审核阶段**：
   - 文件名或所在文件夹名包含 `test` 的文件（如 `*_test.go`、`testutil/`、`testdata/`、`internal/testing/` 等）
   - Wire 生成的文件（如 `wire_gen.go`）
2. **必须按阶段1→2→3→4→5→6→7→8的顺序逐阶段执行**，不得跳过任何阶段
3. **每个阶段执行前，必须先用工具读取对应的 `references/stage_N_xxx.md` 文件**，获取该阶段的检查指令后再开始审核。不得凭记忆或经验替代
4. **[硬性约束] 必须先通过 Skill 工具调用 `go-code-analyzer` skill，不可跳过**。获取函数调用树、服务依赖图、入口点列表。即使是审核单个文件的 diff，也必须调用。架构上下文是阶段6（架构设计）和阶段7（业务逻辑）的必要输入。**未执行 go-code-analyzer 的审核结果一律视为无效**
5. **阶段8中，必须读取 `references/output_format.md`**，按模板格式输出最终报告
6. **审核报告必须输出为文件**，保存到用户当前工作目录下，文件命名格式为 `{YYYYMMDD_HHmmss}_{分支名}_review.md`（例如 `20260228_143052_feature-payment_review.md`）。不得仅在终端输出而不生成文件
7. **违反以上任何一条，审核结果视为无效**

## 触发条件

当用户请求以下操作时激活：
- 审核Go代码 / review Go代码
- 审核PR / review PR / MR审核
- Go代码质量检查
- Go项目代码审计
- 全量代码审核
- 对本地分支与master/main的diff进行审核

## 审核架构

分为两大部分：

**第一部分：代码实现审核**
- 阶段2：代码规范
- 阶段3：潜在bug与边界条件
- 阶段4：性能问题
- 阶段5：安全漏洞
- 阶段6：架构设计

**第二部分：业务逻辑审核**
- 阶段7：业务逻辑

## 执行流程

### 阶段1：上下文收集

**前置动作（必须）：** 使用工具读取 `references/stage_1_context.md`

1. 识别审核模式（PR增量 / 全量审计）
2. **[必须] 通过 Skill 工具调用 `go-code-analyzer` skill** 获取架构上下文：
   - 函数调用树（从入口点到DAO/Client的完整调用链）
   - 服务依赖图（HTTP/gRPC/Kafka/Redis/MySQL等外部依赖）
   - 入口点列表（HTTP路由、MQ消费者、Cron任务、gRPC方法）
   - 将分析结果保存为架构上下文，供阶段2-7引用
3. 加载规则：检测项目根目录 `.go-review-rules.yaml`，无则使用 `general` 规则集
4. 使用工具读取 `references/builtin_rules.md` 加载对应规则集
5. 建立严格度映射（按文件路径和代码类型）
6. 输出上下文摘要，传递给后续阶段

### 阶段2-6：代码实现审核

**每个阶段执行前，必须先用工具读取对应的 reference 文件。**

依次执行，每个阶段：
1. **[必须] 读取对应的 `references/stage_N_xxx.md`** 获取检查指令
2. 接收阶段1的上下文摘要（含 go-code-analyzer 架构上下文）+ 待审核代码
3. 根据严格度映射调整检查深度
4. 输出该维度的问题列表

阶段文件：
- 阶段2：`references/stage_2_style.md` — 代码规范
- 阶段3：`references/stage_3_bugs.md` — 潜在bug与边界条件
- 阶段4：`references/stage_4_perf.md` — 性能问题
- 阶段5：`references/stage_5_security.md` — 安全漏洞（可引用阶段3发现）
- 阶段6：`references/stage_6_arch.md` — 架构设计（**依赖 go-code-analyzer 输出，无架构上下文则本阶段无法正确执行**）

### 阶段7：业务逻辑审核

**前置动作（必须）：** 使用工具读取 `references/stage_7_business.md`

1. **利用 go-code-analyzer 产出的架构上下文**理解服务间调用关系
2. 依赖代码注释和命名推断业务意图
3. 不明确时标记 `[业务意图不明确]`，不强行猜测

### 阶段8：汇总报告

**前置动作（必须）：** 使用工具读取 `references/stage_8_report.md` 和 `references/output_format.md`

1. 合并去重所有阶段的问题
2. **[必须] 将阶段1中 go-code-analyzer 产出的架构分析以 Mermaid 图表形式嵌入报告**，位于结构化摘要之后、问题列表之前。必须包含以下图表：
   - **入口点列表**（表格形式：类型、触发方式、入口函数、说明）
   - **函数调用层级图**（Mermaid graph TD，从入口层到DAO层的完整调用链，按层分 subgraph，节点标注文件名）
   - **服务依赖图**（Mermaid graph LR，标注调用方式和关键参数如超时、TTL等）
   - **核心业务流程图**（Mermaid flowchart TD，每个关键入口点一张，包含所有分支和错误处理路径）
   - **数据库表关系图**（Mermaid erDiagram，仅包含本次变更涉及的表，标注新增表和新增字段）
3. 按 `output_format.md` 模板生成结构化摘要 + 架构分析图表 + 逐条详细评论 + 末尾总结
4. **[必须] 将最终报告写入文件**，保存到用户当前工作目录下，命名格式 `{YYYYMMDD_HHmmss}_{分支名}_review.md`

## 执行检查清单

每次审核时，按此清单逐项确认（内部自检，不输出给用户）：

```
□ 阶段1: 已按排除规则过滤文件（test相关文件、wire_gen.go）
□ 阶段1: 已读取 references/stage_1_context.md
□ 阶段1: 已通过 Skill 工具调用 go-code-analyzer skill（硬性约束，不可跳过）
□ 阶段1: 已获取函数调用树 + 服务依赖图 + 入口点列表
□ 阶段1: 已读取 references/builtin_rules.md
□ 阶段1: 已建立严格度映射
□ 阶段2: 已读取 references/stage_2_style.md → 执行代码规范检查
□ 阶段3: 已读取 references/stage_3_bugs.md → 执行bug扫描
□ 阶段4: 已读取 references/stage_4_perf.md → 执行性能检查
□ 阶段5: 已读取 references/stage_5_security.md → 执行安全检查
□ 阶段6: 已读取 references/stage_6_arch.md → 基于架构上下文执行架构检查
□ 阶段7: 已读取 references/stage_7_business.md → 基于架构上下文执行业务逻辑检查
□ 阶段8: 已读取 references/stage_8_report.md + references/output_format.md
□ 阶段8: 已将 go-code-analyzer 架构分析以 Mermaid 图表嵌入报告（入口点表 + 调用层级图 + 服务依赖图 + 核心流程图 + 数据库ER图）
□ 阶段8: 已按模板格式输出最终报告
□ 阶段8: 已将报告写入文件 {YYYYMMDD_HHmmss}_{分支名}_review.md
```

## 使用示例

```
审核这个PR的Go代码变更
```

```
对 internal/service/ 目录做全面代码审核
```

```
使用microservice规则集审核这段代码
```

```
审核 internal/payment/ 的代码，重点关注安全和业务逻辑
```

```
对本地分支与master的diff进行审核
```

## 自定义规则

项目根目录放置 `.go-review-rules.yaml` 可自定义规则。模板参见 `assets/.go-review-rules.example.yaml`。

支持：
- 选择基础规则集（general/microservice/cli）
- 按路径覆盖严格度
- 添加团队自定义规则
- 忽略特定检查项
