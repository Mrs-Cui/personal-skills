---
name: golang-unittest-coverage
description: 分析 Golang 单元测试覆盖率，识别未覆盖的代码分支，判断是否达标并生成报告。由 golang-unittest 主控调度，也可独立调用。Use when 需要分析测试覆盖率或定位未覆盖代码。
---

# Golang 单元测试 Coverage Analyzer

## 职责

分析单元测试的代码覆盖率，识别未覆盖的代码分支，判断是否达标。

## 分析流程

### Step 0: Build tag（通常已由主控完成）

> 主控 Agent 在调度前已统一执行 `check_build_tags.sh` + `add_build_tags.sh`（详见主控 SKILL 的 Step 0）。
> 如果你是被独立调用（非主控调度），需要自行执行主控 skill 的脚本（脚本统一维护在 `golang-unittest/scripts/` 下）：
> ```bash
> bash {golang_unittest_skill_path}/scripts/check_build_tags.sh <目录...>
> bash {golang_unittest_skill_path}/scripts/add_build_tags.sh <目录...>
> ```

### Step 1: 生成覆盖率数据

```bash
go test -v -tags "{build_tags}" -gcflags='all=-N -l' -coverprofile=coverage.out -run "TestPattern" ./path/to/package/...
```

### Step 2: 查看覆盖率摘要

```bash
go tool cover -func=coverage.out
```

输出示例：
```
package/file.go:42:     FunctionA       85.7%
package/file.go:78:     FunctionB       100.0%
package/file.go:120:    FunctionC       60.0%
total:                  (statements)    78.5%
```

### Step 3: 分析未覆盖代码

```bash
go tool cover -html=coverage.out -o coverage.html
```

或直接查看覆盖率文件：

```bash
go tool cover -func=coverage.out | grep -v "100.0%"
```

### Step 4: 判断是否达标

| 覆盖率 | 状态 | 操作 |
|-------|------|------|
| >= 目标 | 达标 ✓ | 完成，输出报告 |
| < 目标 | 不达标 ✗ | 识别未覆盖分支，返回 Writer |

## 覆盖率分析命令

### 针对特定文件

```bash
# 只看某个文件的覆盖率
go tool cover -func=coverage.out | grep "target_file.go"
```

### 针对特定函数

```bash
# 只看某个函数的覆盖率
go tool cover -func=coverage.out | grep "FunctionName"
```

### 生成 HTML 报告

```bash
go tool cover -html=coverage.out -o coverage.html
```

### 运行测试时的 tag 说明

所有 `go test` 命令必须使用 `-tags "{build_tags}"`。`{build_tags}` 由主控 Agent 在 Step 0 自动确定：

- 简单项目（无 `scripts/build/utils.sh`）：`build_tags` = `ai_test`
- 有 `utils.sh` 的项目：`build_tags` = `$SITE,$BRANCH_BUILD_TAG,ai_test`（如 `primary,local,ai_test`）

如果你是被独立调用（非主控调度），需要自行确定 `{build_tags}` 的值。

HTML 报告中：
- **绿色**：已覆盖的代码
- **红色**：未覆盖的代码
- **灰色**：不可执行代码（如注释、声明）

## 未覆盖代码分析

### 常见未覆盖场景

| 场景 | 原因 | 解决方案 |
|------|------|---------|
| 错误处理分支 | 未 mock 错误返回 | 添加错误场景测试用例 |
| 边界条件 | 未测试边界值 | 添加边界值测试用例 |
| switch/case | 未覆盖所有 case | 为每个 case 添加测试 |
| if/else 分支 | 未触发某个分支 | 调整输入使其触发该分支 |
| panic/recover | 未测试异常路径 | 添加异常场景测试 |

### 识别关键未覆盖分支

优先补充以下类型的未覆盖代码：

1. **错误处理路径**：`if err != nil { return err }`
2. **业务逻辑分支**：`if condition { ... } else { ... }`
3. **空值检查**：`if x == nil { return }`
4. **循环边界**：循环体内的 break/continue

## 输出报告格式

### 达标报告

```
## 覆盖率分析：达标 ✓

### 目标
- 源文件：xxx.go
- 覆盖率目标：80%

### 结果
- 实际覆盖率：85.7%
- 状态：达标

### 函数覆盖详情
| 函数 | 覆盖率 |
|------|--------|
| FuncA | 100% |
| FuncB | 85% |
| FuncC | 75% |

### 结论
测试覆盖率达标，任务完成。
```

### 不达标报告

```
## 覆盖率分析：不达标 ✗

### 目标
- 源文件：xxx.go
- 覆盖率目标：80%

### 结果
- 实际覆盖率：65.3%
- 差距：14.7%

### 未覆盖分支分析

#### 函数：ProcessData (覆盖率 45%)

未覆盖代码位置：
- 第 42-45 行：错误处理分支
  ```go
  if err != nil {
      log.Error("process failed", err)
      return nil, err
  }
  ```
  建议：mock 依赖返回错误

- 第 58-60 行：空值检查
  ```go
  if data == nil {
      return defaultValue, nil
  }
  ```
  建议：添加 data=nil 的测试用例

#### 函数：ValidateInput (覆盖率 70%)

未覆盖代码位置：
- 第 85 行：switch case
  ```go
  case TypeC:
      return handleTypeC(input)
  ```
  建议：添加 TypeC 输入的测试用例

### 需要 Writer 补充
- 总共需补充：3 个测试用例
- 预计可提升覆盖率至：82%
```

## 覆盖率目标建议

| 代码类型 | 建议覆盖率 |
|---------|----------|
| 核心业务逻辑 | >= 80% |
| 工具函数 | >= 90% |
| 错误处理 | >= 70% |
| 第三方集成 | >= 60% |

## 提升覆盖率策略

### 快速提升

1. **补充错误路径**：每个 `if err != nil` 都需要测试
2. **补充边界值**：空值、零值、最大值、最小值
3. **补充所有分支**：switch 的每个 case，if 的每个分支

### 高价值优先

优先覆盖：
1. 高频调用的函数
2. 复杂业务逻辑
3. 涉及金钱/权限的代码
4. 容易出错的边界处理

## 增量覆盖率模式

### 适用场景

增量覆盖率模式专用于 **diff 模式**（`shard.py --diff`），由主控 Agent 在 Step 7 通过 Task 调用 Coverage Agent 时传入 `diff-spec` 参数触发。

当 Coverage Agent 收到包含 `diff-spec` 的调用时，走增量覆盖率流程而非整体覆盖率流程。

与整体覆盖率的区别：
- **整体覆盖率**（文件/目录模式）：统计整个包或文件的所有可执行行覆盖情况，通过 `go tool cover -func` 分析
- **增量覆盖率**（diff 模式）：仅统计 diff 新增的可执行行覆盖情况，避免被存量代码的覆盖率稀释

| 维度 | 整体覆盖率 | 增量覆盖率 |
|------|-----------|-----------|
| 适用模式 | 文件模式、目录模式 | diff 模式 |
| 统计范围 | 包/文件的所有可执行行 | 仅 diff 新增的可执行行 |
| 触发条件 | 调用时无 diff-spec | 调用时有 diff-spec |
| 工具 | `go tool cover -func` | `incremental_coverage.py` |
| 优势 | 全面反映代码质量 | 精准反馈新增代码质量 |

### 增量覆盖率流程

当收到包含 `diff-spec` 的调用时，执行以下步骤：

#### Step 1: 生成覆盖率数据

```bash
go test -v -tags "{build_tags}" -gcflags='all=-N -l' -coverprofile=coverage.out -run "TestPattern" ./path/to/package/...
```

#### Step 2: 调用增量覆盖率脚本

```bash
python3 {incremental_coverage_script_path} \
    --diff-spec "{diff_spec}" \
    --coverage-file coverage.out \
    --target {coverage_target} \
    --project-root .
```

`{incremental_coverage_script_path}` 由主控在调用时提供。

#### Step 3: 返回结果

将脚本的完整 JSON 输出返回给主控。主控根据 `pass` 字段决定后续流程。

### JSON 输出格式

```json
{
  "diff_spec": "master...HEAD",
  "target": 80,
  "pass": true,
  "summary": {
    "total_added_lines": 450,
    "total_executable_lines": 320,
    "total_covered_lines": 272,
    "total_uncovered_lines": 48,
    "coverage_percent": 85.0
  },
  "files": [
    {
      "file": "internal/app/meetup/service/admin/collection.go",
      "added_lines": 120,
      "executable_lines": 85,
      "covered_lines": 70,
      "uncovered_lines": 15,
      "coverage_percent": 82.35
    }
  ],
  "uncovered_functions": [
    {
      "file": "internal/app/meetup/service/admin/collection.go",
      "function": "CreateCollection",
      "uncovered_incremental_lines": 5
    }
  ]
}
```

字段说明：
- `pass`：是否达标（`coverage_percent >= target`）
- `summary.total_added_lines`：diff 新增总行数（含非可执行行如注释、空行）
- `summary.total_executable_lines`：diff 新增行中被 coverage.out 标记为可执行的行数
- `summary.total_covered_lines`：可执行行中被测试覆盖的行数
- `files`：按文件维度的覆盖率明细
- `uncovered_functions`：未覆盖行所属的函数列表，按未覆盖行数降序

### 排除规则

脚本自动排除以下文件的 diff 行：
- `*_test.go`：测试文件
- `wire_gen.go`：Wire 自动生成文件
- `testmocks/` 目录下的文件：Mock 文件
- `mock_*` 前缀的文件：Mock 文件

### uncovered_functions 反馈 Writer

当 `pass=false` 时，主控从 `uncovered_functions` 提取未覆盖函数名，按文件分组后调用 `shard.py --file {file} --functions "func1,func2"` 获取分组信息，再传给 Writer 补充测试用例。这形成了精准的反馈闭环：

```
增量覆盖率不达标
  → uncovered_functions 定位到具体函数
  → shard.py 获取函数分组上下文
  → Writer 补充测试
  → Validator 验证
  → 重新计算增量覆盖率
```
