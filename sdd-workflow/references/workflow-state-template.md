# SDD Workflow State

> topic: <topic>
> task: <任务描述的前 80 字>
> created: YYYY-MM-DD HH:MM
> last_updated: YYYY-MM-DD HH:MM
> overall_status: NOT_STARTED | IN_PROGRESS | COMPLETED | ABORTED

## Phase 1: DESIGN

- status: NOT_STARTED | IN_PROGRESS | COMPLETED | SKIPPED
- started_at:
- completed_at:
- design_doc_path:
- confirmation_keyword: 确认
- self_check_passed: true | false
- notes:

## Phase 2: PLAN

- status: NOT_STARTED | IN_PROGRESS | COMPLETED | SKIPPED
- started_at:
- completed_at:
- plan_doc_path:
- approval_keyword: Plan Approved
- review_matrix_verdict: GO | NO-GO
- checklist_item_count:
- notes:

## Phase 3: CODE

- status: NOT_STARTED | IN_PROGRESS | COMPLETED | SKIPPED
- started_at:
- completed_at:
- build_passed: true | false
- vet_passed: true | false
- checklist_progress: 0/N
- files_created:
- files_modified:
- notes:

## Phase 4: CODE REVIEW

- status: NOT_STARTED | IN_PROGRESS | COMPLETED | SKIPPED | ABORTED
- started_at:
- completed_at:
- review_cycles: 0
- current_cycle_report:
- issue_summary:
  - critical: 0
  - high: 0
  - medium: 0
  - low: 0
  - info: 0
- user_decisions:
  - cycle_1:
  - cycle_2:
- skipped_issues:
- notes:

## Phase 5: UNIT TEST

- status: NOT_STARTED | IN_PROGRESS | COMPLETED | SKIPPED
- started_at:
- completed_at:
- test_cycles: 0
- total_tests: 0
- passed_tests: 0
- failed_tests: 0
- coverage_percent: 0
- test_files_created:
- notes:

## Phase 6: FINAL VERIFICATION

- status: NOT_STARTED | IN_PROGRESS | COMPLETED | SKIPPED
- started_at:
- completed_at:
- build: PASS | FAIL
- vet: PASS | FAIL
- lint: PASS | FAIL | N/A
- tests: PASS | FAIL
- security: PASS | FAIL | N/A
- diff_files_changed: 0
- overall_verdict: READY | NOT READY
- notes:

## Change Log

| 时间 | 阶段 | 事件 | 详情 |
|------|------|------|------|
| YYYY-MM-DD HH:MM | Phase N | <事件类型> | <详情> |

<!--
事件类型枚举:
- STARTED: 阶段开始
- SELF_CHECK_PASSED: 自检通过
- SELF_CHECK_FAILED: 自检失败，附失败项
- USER_CONFIRMED: 用户确认通过
- USER_APPROVED: 用户批准计划
- BUILD_PASSED: 构建通过
- BUILD_FAILED: 构建失败，附错误摘要
- REVIEW_CYCLE_N: 审核第N轮完成
- USER_DECISION_FIX: 用户选择修复
- USER_DECISION_SKIP: 用户选择跳过
- USER_DECISION_ABORT: 用户选择中止
- TEST_PASSED: 测试通过
- TEST_FAILED: 测试失败，附失败测试名
- COVERAGE_MET: 覆盖率达标
- COVERAGE_BELOW: 覆盖率不足，附当前值
- VERIFICATION_DONE: 验证完成
- COMPLETED: 阶段完成
- ABORTED: 工作流中止
-->
