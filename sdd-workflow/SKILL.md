---
name: sdd-workflow
description: >
  端到端的 Spec 驱动开发管线，串联 Design → Plan → Code → Code Review(循环修复) → Unit Test → Final Verification
  六个阶段为自动化工作流。每阶段内嵌自检规则和反馈循环，由状态文件驱动断点恢复。
  触发条件："SDD 工作流"、"sdd-workflow"、"全流程开发"、"端到端开发"，
  或用户希望从需求到交付跑完完整管线。
  Go 语言优先，但验证命令隔离在 references 中，可扩展其他语言。
---

# SDD Workflow Skill

端到端的 Spec 驱动开发管线：**Design → Plan → Code → Code Review → Unit Test → Final Verification**。

## 全局安全底线 (Global Safeguards)

以下规则优先级最高，不可被任何其他规则覆盖：

1. **No Design, No Plan**：必须完成 Design 阶段并获得用户确认，才能进入 Plan
2. **No Plan Approved, No Code**：必须用户明确说 "Plan Approved" 才能进入 Code 实现
3. **No Build, No Review**：代码必须 `go build` + `go vet` 通过才能进入 Code Review
4. **Review Loop = Human-in-the-Loop**：Code Review 每轮结束必须询问用户，三选项（修复 / 跳过 / 中止），无自动上限
5. **中文沟通**：所有输出使用中文（代码、文件路径、方法签名、Git 消息除外）
6. **高危操作阻断**：永远不要静默执行 `git clean`、`rm -rf`、`git reset --hard` 等不可逆操作

## 工作流全景

```
[用户输入: PRD/需求]
      │
      ▼
 Phase 1: DESIGN (req-to-design)
   自检: 13项交叉一致性校验
   门禁: 用户说"确认"
      │
      ▼
 Phase 2: PLAN (sdd-riper-one 启发)
   自检: review_spec 式评审矩阵
   门禁: 用户说"Plan Approved"
      │
      ▼
 Phase 3: CODE (Go 实现)
   自检: go build + go vet
   门禁: 构建通过
      │
      ▼
 Phase 4: CODE REVIEW ◄──── 循环 ────┐
   (go-code-reviewer 8阶段管道)       │
   解析报告严重级别                    │
   ├─ CRITICAL/HIGH → 用户选"修复" ──┘
   ├─ CRITICAL/HIGH → 用户选"跳过" → 继续
   ├─ CRITICAL/HIGH → 用户选"中止" → 停止
   └─ 无严重问题 → 用户说"确认" → 继续
      │
      ▼
 Phase 5: UNIT TEST ◄──── 循环 ────┐
   (go-unit-test-expert)            │
   ├─ 测试失败 → 修复 ────────────┘
   ├─ 覆盖率<80% → 补充测试 ──────┘
   └─ 全部通过+80%+ → 继续
      │
      ▼
 Phase 6: FINAL VERIFICATION
   (verification-loop Go适配版)
   输出: READY / NOT READY
```

## 6 阶段定义

### Phase 1: DESIGN

- **入口条件**：用户提供 PRD、需求文档或简要描述
- **执行**：调用 `req-to-design` skill 完整 6 阶段流程
  - 如果项目有 `knowledge/` 目录：走完整知识库驱动设计流程
  - 如果没有 `knowledge/` 目录：执行简化设计流程（跳过 KB 扫描，直接从需求理解 → 业务流程图 → 影响分析 → 设计输出）
- **自检**：13 项交叉一致性校验（见 `references/self-check-rules.md` Phase 1 矩阵）
- **出口门禁**：用户消息包含 **"确认"** 二字（与 req-to-design 一致）
- **产出**：设计文档 `docs/plans/YYYY-MM-DD-<topic>-design.md`
- **失败处理**：自检不通过 → 修正后重新进入确认循环

### Phase 2: PLAN

- **入口条件**：Phase 1 确认通过，设计文档已落盘
- **执行**：受 sdd-riper-one 方法论启发，生成可执行实现计划
  1. 读取设计文档，提取架构决策、数据模型、接口设计、代码变更清单
  2. 将变更清单转化为原子化 checklist（每项包含：文件路径 + 方法签名 + 预期行为）
  3. 按依赖关系排序（基础设施 → 数据层 → 服务层 → 接口层 → 路由/消费者注册）
  4. 识别风险点和回滚方案
- **自检**：review_spec 式评审矩阵（见 `references/self-check-rules.md` Phase 2 矩阵）
  - 目标/范围/验收标准是否清晰且可验证
  - 文件路径是否存在（或明确标注为新建）
  - 签名是否完整（参数 + 返回值）
  - Checklist 是否原子化（每项可独立验证）
- **出口门禁**：用户消息包含精确字样 **"Plan Approved"**
- **产出**：实现计划写入 `.sdd-workflow/<topic>/plan.md`
- **失败处理**：评审矩阵有 FAIL 项 → 修正后重新进入确认循环

### Phase 3: CODE

- **入口条件**：Phase 2 Plan Approved
- **执行**：按计划逐项实现 Go 代码
  1. 读取 `.sdd-workflow/<topic>/plan.md` 获取 checklist
  2. 按依赖顺序逐项实现
  3. 每完成一个逻辑单元（如一个 service 或一个 handler），运行构建验证
- **自检**：每个逻辑单元完成后执行（见 `references/go-verification-commands.md`）
  ```
  go build ./...
  go vet ./...
  ```
- **出口门禁**：所有代码实现完毕且 `go build` + `go vet` 通过
- **产出**：Go 源代码文件
- **失败处理**：构建失败 → 修复编译错误 → 重新验证

### Phase 4: CODE REVIEW

- **入口条件**：Phase 3 构建通过
- **执行**：调用 `go-code-reviewer` skill 完整 8 阶段管道
  - 先调用 `go-code-analyzer` 获取架构上下文（硬性约束）
  - 按阶段 1→8 顺序执行，不可跳过
  - 输出审核报告文件
- **自检**：解析审核报告中的严重级别统计
- **出口门禁**：循环协议（见下方"Code Review 循环协议"）
- **产出**：审核报告 `{YYYYMMDD_HHmmss}_{branch}_review.md`
- **失败处理**：用户选择"中止" → 工作流停止，状态记录为 ABORTED

**Code Review 循环协议：**

```
cycle = 1
LOOP:
  调用 go-code-reviewer（完整 8 阶段）
  解析报告 → 统计 CRITICAL/HIGH 数量

  IF CRITICAL > 0 OR HIGH > 0:
    显示问题摘要（CRITICAL: N, HIGH: N, MEDIUM: N）
    显示 CRITICAL 和 HIGH 问题的详细列表
    询问用户: "修复 / 跳过 / 中止"
    ├─ 修复 → 执行修复 → go build 验证 → cycle++ → REPEAT
    ├─ 跳过 → 记录用户决策到状态文件 → EXIT LOOP
    └─ 中止 → 标记 ABORTED → STOP WORKFLOW

  ELSE (无 CRITICAL/HIGH):
    显示审核通过摘要
    询问用户: "确认 / 继续审查 / 修复建议项"
    ├─ 确认 → EXIT LOOP
    ├─ 继续审查 → cycle++ → REPEAT
    └─ 修复建议项 → 修复 MEDIUM 问题 → cycle++ → REPEAT
END LOOP
```

### Phase 5: UNIT TEST

- **入口条件**：Phase 4 Code Review 通过或跳过
- **执行**：调用 `go-unit-test-expert` skill
  1. 读取 `references/main_prompt.md` 核心指令
  2. 为变更的 Go 源文件生成单元测试
  3. 运行测试并收集覆盖率
- **自检**：
  - `go test ./... -v` 全部通过
  - `go test ./... -coverprofile=coverage.out` 覆盖率 >= 80%
- **出口门禁**：全部测试通过 + 覆盖率 >= 80%
- **产出**：`_test.go` 文件 + 覆盖率报告
- **失败处理**：
  - 测试失败 → 分析失败原因 → 修复实现代码（非修改测试，除非测试本身有 bug） → 重新运行
  - 覆盖率不足 → 补充测试用例 → 重新运行

### Phase 6: FINAL VERIFICATION

- **入口条件**：Phase 5 测试全部通过且覆盖率达标
- **执行**：Go 适配版 verification-loop（见 `references/go-verification-commands.md`）
  1. Build Verification: `go build ./...`
  2. Vet Check: `go vet ./...`
  3. Lint Check: `golangci-lint run`（如可用）
  4. Test Suite: `go test ./... -race -coverprofile=coverage.out`
  5. Security Scan: `govulncheck ./...`（如可用）+ 硬编码密钥扫描
  6. Diff Review: `git diff --stat` + 逐文件审查
- **自检**：每项必须 PASS 或标注为 N/A（工具不可用时）
- **出口门禁**：所有可用检查项 PASS
- **产出**：最终验证报告
- **输出格式**：
  ```
  ═══════════════════════════════
  SDD WORKFLOW FINAL VERIFICATION
  ═══════════════════════════════

  Build:     [PASS/FAIL]
  Vet:       [PASS/FAIL]
  Lint:      [PASS/FAIL/N/A]
  Tests:     [PASS/FAIL] (X/Y passed, Z% coverage)
  Security:  [PASS/FAIL/N/A]
  Diff:      [X files changed]

  Overall:   [READY / NOT READY]

  Issues to Fix:
  1. ...
  ```

## 上下文管理

### 热上下文（每轮必带）

- 当前阶段（Phase 1-6）
- 当前审批状态（等待确认 / 已确认 / 等待 Plan Approved / 已批准 / ...）
- 状态文件路径：`.sdd-workflow/<topic>/workflow-state.md`
- 当前活跃 checklist（Code 阶段的实现进度 / Review 循环轮次 / 测试通过情况）

### 温上下文（阶段切换时加载）

- Phase 1 → 2：设计文档核心内容（架构决策、变更清单）
- Phase 2 → 3：实现计划 checklist
- Phase 3 → 4：变更文件列表、构建日志
- Phase 4 → 5：审核报告摘要、未修复问题列表
- Phase 5 → 6：测试结果、覆盖率数据

### 冷上下文（按需加载）

- 完整设计文档
- 完整审核报告
- 历史 Review 循环记录
- 完整 codemap

## 状态跟踪

所有工作流状态持久化到 `.sdd-workflow/<topic>/workflow-state.md`（模板见 `references/workflow-state-template.md`）。

### 写出时机

| 事件 | 动作 |
|------|------|
| 工作流启动 | 创建状态文件，Phase 1 标记为 IN_PROGRESS |
| 任意阶段确认通过 | 更新对应 Phase 为 COMPLETED，下一阶段为 IN_PROGRESS |
| Review 循环每轮结束 | 更新 cycle 计数、问题统计、用户决策 |
| 用户选择"中止" | 标记当前 Phase 为 ABORTED |
| 工作流完成 | 所有 Phase 标记为 COMPLETED，Overall 标记为 READY/NOT READY |

### 恢复机制

当用户输入 `RESUME` 或 `/sdd-workflow resume` 时：

1. 扫描 `.sdd-workflow/` 目录下的 `workflow-state.md` 文件
2. 找到最近一个非 COMPLETED/ABORTED 的工作流
3. 显示状态摘要，请求用户确认恢复
4. 从上次中断的阶段继续执行

## 阶段间交接

每个阶段完成后生成 Handoff 文档（模板见 `references/handoff-format.md`），保存到 `.sdd-workflow/<topic>/handoff-phase-N.md`。

Handoff 文档包含：
1. **Context**：当前阶段的执行摘要
2. **Findings**：关键发现和决策
3. **Files Modified**：本阶段修改/创建的文件列表
4. **Open Questions**：遗留问题
5. **Recommendations**：对下一阶段的建议

下一阶段启动时读取 Handoff 作为输入上下文。

## 集成点映射表

| 阶段 | 调用的 Skill | 方式 | 备注 |
|------|-------------|------|------|
| Design | req-to-design | 完整 6 阶段流程 | 无 knowledge/ 时走简化流程 |
| Plan | (原生，sdd-riper-one 启发) | 生成可执行计划 | 复用 review_spec 评审矩阵 |
| Code | (原生) | 按计划实现 + go build/vet | 逐单元构建验证 |
| Review | go-code-reviewer | 8 阶段管道 | 必须先调用 go-code-analyzer |
| Test | go-unit-test-expert | 加载 main_prompt.md | 表驱动测试 + gomock |
| Verify | (原生，verification-loop Go 适配) | 6 项综合验证 | 命令集见 references |

## 触发词

- `SDD 工作流` / `sdd-workflow` / `全流程开发` / `端到端开发` → 从 Phase 1 开始完整流程
- `STATUS` / `状态` → 显示当前工作流状态
- `RESUME` / `恢复` / `继续` → 恢复上次未完成的工作流
- `ABORT` / `中止` / `终止` → 中止当前工作流
- `SKIP` / `跳过` → 跳过当前阶段的门禁（需记录决策理由）

## 参考文件

- `references/workflow-state-template.md` — 工作流状态持久化模板
- `references/handoff-format.md` — 阶段间交接文档模板
- `references/self-check-rules.md` — 各阶段自检标准矩阵
- `references/go-verification-commands.md` — Go 专用的构建/测试/安全命令集
