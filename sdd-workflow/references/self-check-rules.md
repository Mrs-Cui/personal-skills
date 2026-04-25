# 自检标准矩阵

各阶段自检规则，在阶段出口门禁前执行。所有检查项必须 PASS 才能进入下一阶段。

## Phase 1: DESIGN 自检矩阵

来源：req-to-design 阶段 6 定稿前的 13 项交叉一致性校验。

| # | 检查项 | 规则 | 判定 | 失败动作 |
|---|--------|------|------|----------|
| 1 | §2 目录结构 ↔ §11 代码变更清单 | 文件路径完全对齐 | PASS/FAIL | 修正不一致的文件路径 |
| 2 | §3 流程中的方法名 ↔ §5 接口定义 | 流程图调用的方法必须在接口定义中有对应签名 | PASS/FAIL | 补充缺失的接口签名或修正流程图 |
| 3 | §5 复用服务 ↔ 实际方法签名 | 列出的复用服务必须包含完整方法签名 | PASS/FAIL | 补充完整签名（参数+返回值） |
| 4 | §7 幂等声明 ↔ §4 约束定义 | 声称唯一键防重必须在数据模型中有对应约束 | PASS/FAIL | 在数据模型中新增约束 |
| 5 | §4 复用表 ↔ 字段语义映射 | 复用已有表必须列出字段清单和本业务语义映射 | PASS/FAIL | 补充字段语义映射 |
| 6 | §8 错误码 ↔ 全局冲突 | 错误码须声明命名空间/分配范围 | PASS/FAIL | 声明命名空间并确认不冲突 |
| 7 | §6 MQ 消费 ↔ 现有 handler | 新增 handler 须说明 consumer group 策略 | PASS/FAIL | 补充 consumer group 说明 |
| 8 | §10 配置项 ↔ 类型+校验规则 | 每个配置项须有值类型、合法范围、是否热更新 | PASS/FAIL | 补充配置项详情 |
| 9 | §12 Checklist ↔ 量化预期 | 每项必须有可验证的预期结果 | PASS/FAIL | 补充量化预期 |
| 10 | §3 流程格式 | 必须使用 Mermaid 图 | PASS/FAIL | 将纯文本流程转为 Mermaid |
| 11 | §0 术语表 | 非通用术语必须在术语表中定义 | PASS/FAIL | 补充术语定义 |
| 12 | §1 "不做什么" | 必须同时覆盖业务侧和技术侧 | PASS/FAIL | 补充缺失的不做项 |
| 13 | §13 容量估算 + 公共文件影响 | 须包含用户量级、峰值 QPS；修改公共文件须评估影响 | PASS/FAIL | 补充容量估算或影响评估 |

**无 knowledge/ 目录时的简化规则：**

跳过与知识库相关的检查（§5 复用服务签名验证、§6 MQ 现有 handler 验证），其余检查项仍需执行。标注跳过原因："项目无 knowledge/ 目录，无法验证现有实现"。

## Phase 2: PLAN 自检矩阵

来源：sdd-riper-one review_spec 评审模式。

| # | 检查项 | 规则 | 判定 | 失败动作 |
|---|--------|------|------|----------|
| 1 | 目标清晰性 | Goal 描述明确且可验证 | PASS/FAIL | 修正 Goal 描述 |
| 2 | 范围边界 | In Scope 和 Out of Scope 均已定义 | PASS/FAIL | 补充范围定义 |
| 3 | 验收标准 | 每个功能点有可验证的验收标准 | PASS/FAIL | 补充验收标准 |
| 4 | 文件路径存在性 | 所有文件路径可在项目中找到（或标注为新建） | PASS/FAIL | 修正文件路径 |
| 5 | 签名完整性 | 所有方法签名包含完整参数和返回值 | PASS/FAIL | 补充签名 |
| 6 | Checklist 原子化 | 每项 checklist 可独立验证且无歧义 | PASS/FAIL | 拆分粗粒度项 |
| 7 | 依赖排序 | Checklist 按依赖关系排序（被依赖的先做） | PASS/FAIL | 重新排序 |
| 8 | 风险识别 | 至少列出 1 个风险点及缓解方案 | PASS/FAIL | 补充风险分析 |
| 9 | 回滚方案 | 有明确的回滚策略（至少数据层和服务层） | PASS/FAIL | 补充回滚方案 |
| 10 | 设计一致性 | Plan 与 Design 文档无矛盾 | PASS/FAIL | 修正不一致项 |

## Phase 3: CODE 自检矩阵

每个逻辑单元实现后执行。

| # | 检查项 | 命令 | 判定 | 失败动作 |
|---|--------|------|------|----------|
| 1 | 编译通过 | `go build ./...` | PASS/FAIL | 修复编译错误 |
| 2 | Vet 通过 | `go vet ./...` | PASS/FAIL | 修复 vet 警告 |
| 3 | Plan 一致性 | 对比 checklist 与实现 | PASS/FAIL | 补充遗漏实现或更新 plan |
| 4 | 无硬编码密钥 | 扫描 `sk-`、`api_key`、`password` 等模式 | PASS/FAIL | 移到环境变量或配置 |
| 5 | 错误处理 | 检查 `_` 忽略的 error 返回值 | PASS/WARN | 添加错误处理 |

## Phase 4: CODE REVIEW 自检矩阵

每轮 Review 循环后执行。

| # | 检查项 | 规则 | 判定 | 失败动作 |
|---|--------|------|------|----------|
| 1 | go-code-analyzer 已调用 | 架构上下文已获取 | PASS/FAIL | 调用 go-code-analyzer |
| 2 | 8 阶段全部执行 | 无跳过的阶段 | PASS/FAIL | 补执行遗漏阶段 |
| 3 | 报告已输出为文件 | 文件存在且格式正确 | PASS/FAIL | 重新输出报告 |
| 4 | CRITICAL 问题处理 | 所有 CRITICAL 已修复或用户明确跳过 | PASS/FAIL | 询问用户决策 |
| 5 | 修复后重新构建 | 修复代码后 go build 通过 | PASS/FAIL | 修复构建错误 |

## Phase 5: UNIT TEST 自检矩阵

| # | 检查项 | 命令/规则 | 判定 | 失败动作 |
|---|--------|----------|------|----------|
| 1 | 测试全部通过 | `go test ./... -v` exit code = 0 | PASS/FAIL | 修复失败测试（优先修实现，非测试） |
| 2 | 覆盖率达标 | `go test ./... -coverprofile=coverage.out` >= 80% | PASS/FAIL | 补充测试用例 |
| 3 | Race 检测 | `go test ./... -race` 无竞态报告 | PASS/WARN | 修复竞态条件 |
| 4 | Mock 完整性 | 所有 interface 依赖已 mock | PASS/FAIL | 补充 mock |
| 5 | 表驱动测试 | 核心函数使用 table-driven tests | PASS/WARN | 重构为表驱动 |

## Phase 6: FINAL VERIFICATION 自检矩阵

| # | 检查项 | 命令 | 判定 | 失败动作 |
|---|--------|------|------|----------|
| 1 | Build | `go build ./...` | PASS/FAIL | 修复构建错误 |
| 2 | Vet | `go vet ./...` | PASS/FAIL | 修复 vet 问题 |
| 3 | Lint | `golangci-lint run` | PASS/FAIL/N/A | 修复 lint 问题 |
| 4 | Tests + Coverage | `go test ./... -race -coverprofile=coverage.out` | PASS/FAIL | 修复测试/补覆盖率 |
| 5 | Security | `govulncheck ./...` | PASS/FAIL/N/A | 修复已知漏洞 |
| 6 | 密钥扫描 | grep 敏感模式 | PASS/FAIL | 移除硬编码密钥 |
| 7 | Diff 审查 | `git diff --stat` 逐文件审查 | PASS/WARN | 移除非预期变更 |

**N/A 处理**：如果工具不可用（如 golangci-lint、govulncheck 未安装），标注为 N/A 并在报告中说明原因。N/A 不阻塞工作流。

## 汇总判定规则

- 全部 PASS → 阶段通过
- 任一 FAIL → 必须修复后重新检查
- WARN → 记录到状态文件，不阻塞但建议修复
- N/A → 工具不可用，不阻塞
