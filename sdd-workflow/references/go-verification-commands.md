# Go 验证命令集

Go 项目专用的构建、测试、安全扫描命令。其他语言扩展时，在 `references/` 下新增对应文件即可。

## Phase 3: CODE 阶段验证

### 基础构建验证（必须）

```bash
# 编译检查 — 确保所有包可编译
go build ./...

# 静态分析 — 检测常见错误
go vet ./...
```

### 快速格式检查（建议）

```bash
# 检查格式是否符合标准（不修改文件，仅报告）
gofmt -l .

# 自动格式化（如需修复）
gofmt -w .
```

## Phase 4: CODE REVIEW 阶段

Code Review 由 `go-code-reviewer` skill 全权负责，验证命令内嵌在其 8 阶段管道中。此处仅列出前置条件检查：

```bash
# 确认代码可编译（Review 前置条件）
go build ./...

# 获取当前分支名（用于报告文件命名）
git rev-parse --abbrev-ref HEAD
```

## Phase 5: UNIT TEST 阶段

### 运行测试

```bash
# 运行所有测试（详细输出）
go test ./... -v

# 运行测试并生成覆盖率报告
go test ./... -coverprofile=coverage.out

# 查看覆盖率概览
go tool cover -func=coverage.out

# 查看按包汇总的覆盖率
go tool cover -func=coverage.out | grep total:

# 生成 HTML 覆盖率报告（可选，方便可视化）
go tool cover -html=coverage.out -o coverage.html
```

### Race 检测

```bash
# 运行测试时启用竞态检测
go test ./... -race
```

### Mock 生成

```bash
# 使用 mockgen 为接口生成 mock（示例）
# mockgen -source=<interface_file>.go -destination=<mock_dir>/mock_<name>.go -package=mock
mockgen -source=internal/service/interface.go -destination=internal/service/mock/mock_service.go -package=mock
```

## Phase 6: FINAL VERIFICATION 阶段

### Step 1: Build Verification

```bash
go build ./...
```

**判定**：exit code = 0 → PASS，否则 FAIL

### Step 2: Vet Check

```bash
go vet ./...
```

**判定**：exit code = 0 → PASS，否则 FAIL

### Step 3: Lint Check

```bash
# 检查 golangci-lint 是否可用
which golangci-lint 2>/dev/null

# 如果可用，运行完整 lint
golangci-lint run ./...

# 如果不可用，标记为 N/A
```

**判定**：工具可用且 exit code = 0 → PASS；工具可用但有问题 → FAIL；工具不可用 → N/A

### Step 4: Test Suite with Coverage

```bash
# 运行全部测试，启用竞态检测和覆盖率
go test ./... -race -coverprofile=coverage.out -count=1

# 提取总覆盖率
go tool cover -func=coverage.out | grep total: | awk '{print $3}'
```

**判定**：全部通过且覆盖率 >= 80% → PASS，否则 FAIL

### Step 5: Security Scan

```bash
# 检查 govulncheck 是否可用
which govulncheck 2>/dev/null

# 如果可用，运行漏洞扫描
govulncheck ./...

# 硬编码密钥扫描（始终执行）
grep -rn "sk-" --include="*.go" . 2>/dev/null | head -10
grep -rn "api_key\s*=" --include="*.go" . 2>/dev/null | head -10
grep -rn "password\s*=" --include="*.go" . 2>/dev/null | grep -v "_test.go" | head -10
grep -rn "secret\s*=" --include="*.go" . 2>/dev/null | grep -v "_test.go" | head -10
```

**判定**：无已知漏洞且无硬编码密钥 → PASS；有问题 → FAIL；govulncheck 不可用但密钥扫描通过 → N/A（govulncheck）+ PASS（密钥）

### Step 6: Diff Review

```bash
# 查看变更统计
git diff --stat

# 查看变更文件列表
git diff --name-only

# 查看详细 diff（用于逐文件审查）
git diff
```

**判定**：所有变更文件均为预期变更 → PASS；发现非预期变更 → WARN

## 工具安装指南

如果缺少可选工具，可通过以下命令安装：

```bash
# golangci-lint（推荐版本 v1.55+）
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest

# govulncheck
go install golang.org/x/vuln/cmd/govulncheck@latest

# mockgen
go install go.uber.org/mock/mockgen@latest
```

## 报告输出模板

```
═══════════════════════════════
SDD WORKFLOW FINAL VERIFICATION
═══════════════════════════════
Topic:     <topic>
Time:      YYYY-MM-DD HH:MM
Branch:    <branch_name>

Build:     [PASS/FAIL]
Vet:       [PASS/FAIL]
Lint:      [PASS/FAIL/N/A] (<details>)
Tests:     [PASS/FAIL] (<X>/<Y> passed, <Z>% coverage)
Security:  [PASS/FAIL/N/A] (<details>)
Diff:      [<N> files changed]

Overall:   [READY / NOT READY]

Issues to Fix:
1. <issue description>
2. <issue description>

Warnings (non-blocking):
1. <warning description>

N/A Items:
1. <tool> — <reason not available>
═══════════════════════════════
```
