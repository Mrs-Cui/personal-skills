# Handoff 文档模板

阶段间交接文档，确保上下文在阶段切换时完整传递。

保存路径：`.sdd-workflow/<topic>/handoff-phase-N.md`

---

## Handoff: Phase 1 (DESIGN) → Phase 2 (PLAN)

> topic: <topic>
> from_phase: DESIGN
> to_phase: PLAN
> generated: YYYY-MM-DD HH:MM

### Context

- 设计文档路径：`docs/plans/YYYY-MM-DD-<topic>-design.md`
- 设计流程：<完整流程 / 简化流程（无 knowledge/）>
- 确认轮次：<N 轮确认循环>
- 自检结果：13 项交叉一致性校验全部通过

### Findings

- 架构决策摘要：
  1. <决策 1>
  2. <决策 2>
- 数据模型变更摘要：
  - 新增表：<表名列表>
  - 修改表：<表名 + 变更描述>
- 接口设计摘要：
  - 新增 API：<路由 + 方法>
  - 新增 MQ 消费者：<topic + handler>
- 代码变更清单摘要：<N 个文件需新建/修改>

### Files Modified

- `docs/plans/YYYY-MM-DD-<topic>-design.md` (新建)
- `.design-cache/<topic>/` (缓存目录，可选保留)

### Open Questions

- <遗留问题 1>
- <遗留问题 2>

### Recommendations

- Plan 阶段应重点关注：<依赖排序 / 并发设计 / 数据迁移 / ...>
- 建议先实现的模块：<基础设施 / 数据层 / ...>

---

## Handoff: Phase 2 (PLAN) → Phase 3 (CODE)

> topic: <topic>
> from_phase: PLAN
> to_phase: CODE
> generated: YYYY-MM-DD HH:MM

### Context

- 计划文档路径：`.sdd-workflow/<topic>/plan.md`
- Checklist 总项数：<N>
- review_spec 评审结论：<GO / NO-GO（用户决定继续）>
- 批准关键词确认：Plan Approved

### Findings

- 实现顺序（按依赖排序）：
  1. <阶段/模块 1>：<文件列表>
  2. <阶段/模块 2>：<文件列表>
- 关键接口签名：
  - `<InterfaceName.Method(params) (returns)>` — 用途
- 风险点：
  - <风险 1>：缓解方案 <...>

### Files Modified

- `.sdd-workflow/<topic>/plan.md` (新建)

### Open Questions

- <遗留问题>

### Recommendations

- 建议按 checklist 顺序实现，每完成一个逻辑单元运行 `go build`
- 关注点：<并发安全 / 错误处理 / ...>

---

## Handoff: Phase 3 (CODE) → Phase 4 (CODE REVIEW)

> topic: <topic>
> from_phase: CODE
> to_phase: CODE REVIEW
> generated: YYYY-MM-DD HH:MM

### Context

- 构建状态：`go build` PASS, `go vet` PASS
- Checklist 完成度：<N/N>
- 实现耗时：<约 N 轮对话>

### Findings

- 已实现的核心模块：
  1. <模块 1>：<简述>
  2. <模块 2>：<简述>
- 实现过程中的偏差：
  - <与设计的差异点及原因>
- 已知的技术债务：
  - <TODO / 临时方案 / 待优化项>

### Files Modified

- <文件路径 1> (新建/修改)
- <文件路径 2> (新建/修改)

### Open Questions

- <遗留问题>

### Recommendations

- Review 应重点关注：<并发安全 / SQL注入 / 错误处理 / ...>
- 与设计有偏差的部分需要重点审查

---

## Handoff: Phase 4 (CODE REVIEW) → Phase 5 (UNIT TEST)

> topic: <topic>
> from_phase: CODE REVIEW
> to_phase: UNIT TEST
> generated: YYYY-MM-DD HH:MM

### Context

- Review 循环轮次：<N>
- 最终问题统计：CRITICAL: <N>, HIGH: <N>, MEDIUM: <N>
- 用户决策记录：
  - Cycle 1: <修复/跳过>
  - Cycle N: <确认>

### Findings

- 已修复的问题：
  1. <问题摘要 + 修复方式>
- 用户选择跳过的问题（如有）：
  1. <问题摘要 + 跳过理由>
- Review 中发现的需要测试覆盖的关键路径：
  1. <路径描述>

### Files Modified

- <修复过程中修改的文件列表>

### Open Questions

- <遗留问题>

### Recommendations

- 测试应重点覆盖：<Review 中标记的关键路径>
- 建议为以下接口编写 mock 测试：<接口列表>
- 覆盖率目标：80%+

---

## Handoff: Phase 5 (UNIT TEST) → Phase 6 (FINAL VERIFICATION)

> topic: <topic>
> from_phase: UNIT TEST
> to_phase: FINAL VERIFICATION
> generated: YYYY-MM-DD HH:MM

### Context

- 测试循环轮次：<N>
- 测试统计：总计 <X> 个测试，全部通过
- 覆盖率：<X>%（目标 80%+）
- mock 策略：<gomock / testify-mock>

### Findings

- 生成的测试文件：
  1. `<path>_test.go` — 覆盖 <N> 个测试用例
- 测试过程中发现并修复的实现 bug：
  1. <bug 描述 + 修复方式>
- 覆盖率薄弱区域：
  - <未充分覆盖的代码路径>

### Files Modified

- <_test.go 文件列表>
- <因测试发现 bug 而修复的源文件>

### Open Questions

- <遗留问题>

### Recommendations

- Final Verification 应确认 `-race` 检测无竞态条件
- 关注安全扫描结果（如 govulncheck 可用）
