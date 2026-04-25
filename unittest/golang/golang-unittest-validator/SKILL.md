---
name: golang-unittest-validator
description: 验证 Golang 单元测试代码能否正确编译和运行，分析失败原因并分类（编译错误/测试失败/panic）。由 golang-unittest 主控调度，也可独立调用。Use when 需要验证测试代码的编译和运行结果。
---

# Golang 单元测试 Validator

## 职责

验证生成的单元测试代码能够正确编译和运行，识别并报告任何错误。

## 验证流程

### Step 0: Build tag（通常已由主控完成）

> 主控 Agent 在调度前已统一执行 `check_build_tags.sh` + `add_build_tags.sh`（详见主控 SKILL 的 Step 0）。
> 如果你是被独立调用（非主控调度），需要自行执行主控 skill 的脚本（脚本统一维护在 `golang-unittest/scripts/` 下）：
> ```bash
> bash {golang_unittest_skill_path}/scripts/check_build_tags.sh <目录...>
> bash {golang_unittest_skill_path}/scripts/add_build_tags.sh <目录...>
> ```

### Step 1: 编译检查

```bash
go build -tags "{build_tags}" ./path/to/package/...
```

检查是否有编译错误：
- 语法错误
- 类型不匹配
- 未定义的变量/函数
- 导入错误

### Step 2: 运行测试

```bash
go test -v -tags "{build_tags}" -gcflags='all=-N -l'-run "TestFunctionName" ./path/to/package/...
```

**重要**：必须加 `-gcflags='all=-N -l'` 禁用内联，否则 mockey 不生效。必须加 `-tags "{build_tags}"`（由主控传入），否则 `_ai_test.go` 文件不会被编译。

### Step 3: 分析结果

根据测试输出判断结果类型：

| 结果类型 | 特征 | 处理方式 |
|---------|------|---------|
| **PASS** | 所有测试通过 | 返回成功，进入覆盖率分析 |
| **编译错误** | `cannot...`、`undefined...` | 返回错误详情给 Writer 修复 |
| **测试失败** | `FAIL`、`got... want...` | 分析是测试问题还是源码 Bug |
| **Panic** | `panic:`、`runtime error` | 分析 panic 原因 |

## 错误分类与处理

### 编译错误

常见编译错误及修复建议：

```
# 未定义错误
undefined: SomeFunc
→ 检查导入是否正确，函数名是否拼写正确

# 类型不匹配
cannot use x (type A) as type B
→ 检查 mock 函数返回值类型

# 导入冲突
imported and not used
→ 删除未使用的导入

# 循环导入
import cycle not allowed
→ 检查测试文件的包声明和导入
```

### 测试失败

分析失败原因：

```
# 期望值不匹配
got = X, want = Y
→ 检查测试期望值是否正确，或源码逻辑是否有 Bug

# Mock 未生效
actual method was called instead of mock
→ 检查是否禁用了内联优化

# Nil pointer
panic: runtime error: invalid memory address
→ 检查 mock 设置是否完整
```

### 测试失败分析决策树

```
测试失败
    │
    ├─ 期望值与实际值不符？
    │      │
    │      ├─ 期望值设置错误 → 修改测试代码
    │      │
    │      └─ 源码逻辑有 Bug → 报告源码问题
    │
    ├─ Mock 未生效？
    │      │
    │      ├─ 未禁用内联 → 添加 -gcflags='all=-N -l'
    │      │
    │      └─ 方法签名不匹配 → 修正 mock 函数签名
    │
    └─ Panic？
           │
           ├─ nil pointer → 补充必要的 mock
           │
           └─ 其他 panic → 分析具体原因
```

## 输出报告格式

### 验证通过

```
## 验证结果：通过 ✓

### 测试运行
- 测试文件：xxx_ai_test.go
- 运行命令：go test -v -gcflags='all=-N -l' -run "TestXxx" ./...
- 测试数量：10
- 通过：10
- 失败：0
- 耗时：1.23s

### 下一步
进入覆盖率分析阶段
```

### 编译失败

```
## 验证结果：编译失败 ✗

### 错误详情
文件：xxx_ai_test.go
行号：42
错误：undefined: mockClient

### 修复建议
1. 检查 mockClient 是否正确声明
2. 检查导入是否包含 mock 包

### 需要 Writer 处理
- 类型：编译错误
- 错误代码：E001_UNDEFINED
- 错误位置：xxx_ai_test.go:42
```

### 测试失败

```
## 验证结果：测试失败 ✗

### 失败详情
测试：TestXxx/边界条件_空输入
错误：got = nil, want = []string{}

### 分析
- 失败类型：期望值不匹配
- 可能原因：测试期望值设置错误
- 建议：检查空输入时源码的实际返回值

### 需要 Writer 处理
- 类型：测试失败
- 错误代码：F001_ASSERTION
- 失败测试：TestXxx/边界条件_空输入
```

## 运行命令参考

### 运行特定测试

```bash
# 运行单个测试函数
go test -v -tags "{build_tags}" -gcflags='all=-N -l' -run "TestFunctionName" ./path/to/package/...

# 运行匹配模式的测试
go test -v -tags "{build_tags}" -gcflags='all=-N -l' -run "TestCommon.*" ./path/to/package/...

# 运行特定子测试
go test -v -tags "{build_tags}" -gcflags='all=-N -l' -run "TestFunction/子测试名" ./path/to/package/...
```

### 超时设置

```bash
# 设置超时时间（默认 10 分钟）
go test -v -tags "{build_tags}" -gcflags='all=-N -l' -timeout 30s ./path/to/package/...
```

### 详细输出

```bash
# 显示所有日志输出
go test -v -tags "{build_tags}" -gcflags='all=-N -l' ./path/to/package/... 2>&1
```

### tag 说明

所有 `go test` / `go build` 命令必须使用 `-tags "{build_tags}"`。`{build_tags}` 由主控 Agent 在 Step 0 自动确定：

- 简单项目（无 `scripts/build/utils.sh`）：`build_tags` = `ai_test`
- 有 `utils.sh` 的项目：`build_tags` = `$SITE,$BRANCH_BUILD_TAG,ai_test`（如 `primary,local,ai_test`）

如果你是被独立调用（非主控调度），需要自行确定 `{build_tags}` 的值。
