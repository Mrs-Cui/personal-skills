---
name: fix-ai-unittest
description: 批量修复 AI 生成的 Golang 单元测试中的运行错误。运行测试脚本收集所有失败，按错误类型分类（编译错误/nil pointer/断言失败/mock 问题等），然后逐一修复测试代码（不修改源码）。遇到 gomonkey 无法 mock 的情况自动切换为 mockey 方案。Use when 用户要求修复 AI 单测错误、执行 test_ai.sh 失败需要修复、或提到 fix-ai-unittest。
---

# 修复 AI 单元测试错误

## 概述

本 skill 专注于**修复已有的 AI 单元测试代码中的运行错误**，核心原则是**只修改测试文件，不修改业务源码**。

适用场景：
- `scripts/build/test_ai.sh` 执行失败
- AI 生成的 `_ai_test.go` 文件存在编译或运行时错误
- 用户指定某个包或目录下的 AI 测试需要修复

## 核心约束

1. **绝对不修改业务源码**（非 `_ai_test.go` 的 `.go` 文件）
2. **只修改 `_ai_test.go` 测试文件**
3. 修复后必须验证通过
4. 保留测试的原始意图，修复方式应尽量小幅度

---

## 错误分类体系

所有错误分为 **5 大类 14 子类**，每类有明确的标识特征、优先级和修复策略。

### 一级分类总览

| 大类 | 代号 | 优先级 | 说明 |
|------|------|--------|------|
| **编译错误** | `CE` | P0 | 阻塞整个包的测试运行，必须最先修复 |
| **运行时 Panic** | `RT` | P1 | 测试能编译但运行时崩溃 |
| **断言/逻辑失败** | `AF` | P2 | 测试能运行但结果不符合预期 |
| **Mock 问题** | `MK` | P2 | Mock 框架相关的各类问题 |
| **环境/超时** | `ENV` | P3 | 非代码本身的运行环境问题 |

### 二级分类详情

#### CE — 编译错误

| 子类 | 代号 | 标识特征 | 典型修复 |
|------|------|---------|---------|
| 未定义标识符 | `CE-UNDEF` | `undefined: Xxx` | 补充导入或修正拼写 |
| 类型不匹配 | `CE-TYPE` | `cannot use X as type Y` | 修正类型转换或参数类型 |
| 参数数量错误 | `CE-ARGS` | `too many/few arguments` | 根据源码签名修正调用 |
| 未使用导入 | `CE-IMPORT` | `imported and not used` | 删除未使用的导入 |

#### RT — 运行时 Panic

| 子类 | 代号 | 标识特征 | 典型修复 |
|------|------|---------|---------|
| 空指针解引用 | `RT-NIL` | `invalid memory address or nil pointer dereference` | 提供非 nil 值或补充 mock 返回 |
| 数组越界 | `RT-BOUND` | `index out of range` | 修正测试数据或断言前检查长度 |
| 其他 panic | `RT-OTHER` | `panic:` + 其他信息 | 根据具体 panic 类型分析 |

#### AF — 断言/逻辑失败

| 子类 | 代号 | 标识特征 | 典型修复 |
|------|------|---------|---------|
| 期望值不匹配 | `AF-VALUE` | `got = X, want = Y`、`Not equal`、`assert` 失败 | 根据源码逻辑修正期望值 |
| 错误预期不符 | `AF-ERR` | 期望 error 但得到 nil 或反之 | 修正 `wantErr` 或错误断言 |

#### MK — Mock 问题

| 子类 | 代号 | 标识特征 | 典型修复 |
|------|------|---------|---------|
| gomonkey 失效 | `MK-MONKEY` | mock 未拦截、调用了真实方法、`permission denied` | **改用 mockey**（见下方决策树） |
| sqlmock 不匹配 | `MK-SQL` | `was not expected`、`expectations were not met` | 修正 SQL 正则或补充期望 |
| gomock 调用问题 | `MK-GOMOCK` | `missing call(s)`、`unexpected call` | 补充或移除 `.EXPECT()` |

#### ENV — 环境/超时

| 子类 | 代号 | 标识特征 | 典型修复 |
|------|------|---------|---------|
| 超时 | `ENV-TIMEOUT` | `test timed out` | 增加 timeout 或检查死循环/死锁 |

---

## gomonkey 失效 → mockey 回退机制

### 何时判定 gomonkey 失效

出现以下任一情况，判定当前 gomonkey mock 失效（`MK-MONKEY`）：

| 场景 | 表现 |
|------|------|
| **即使加了 `-gcflags=all=-l` 仍未拦截** | 测试调用了真实方法，触发了真实的 DB/HTTP/外部调用 |
| **ApplyMethod 对接口/泛型 panic** | `reflect.TypeOf` 返回 nil 或 panic，泛型值接收者无法 patch |
| **私有方法或闭包无法 patch** | gomonkey 无法拦截未导出方法 |
| **ApplyFunc 对某些内联函数无效** | 即使禁用优化，编译器仍在链接期内联的函数 |
| **运行时 permission denied** | macOS ARM 架构下 gomonkey 写内存被拒 |

### 回退决策树

```
gomonkey mock 失效？
│
├─ 是结构体方法 mock？
│   │
│   ├─ 接口字段 → 优先用 gomock（如已有生成的 mock）
│   │
│   └─ 非接口（具体 struct 方法）→ 改用 mockey.Mock((*Struct).Method)
│
├─ 是包级别函数 mock？
│   │
│   └─ 改用 mockey.Mock(pkgFunc)
│
└─ 是全局变量替换？
    │
    └─ 改用 mockey.Mock + mockey.PatchConvey（自动回滚）
```

### mockey 改写规则

#### 规则 1：整个测试函数改用 PatchConvey 包裹

mockey 要求所有 `mockey.Mock` 必须在 `mockey.PatchConvey` 内部调用，PatchConvey 结束后自动回滚所有 patch。

```go
// gomonkey 原写法 ❌（失效时改写）
func TestXxx(t *testing.T) {
    patches := gomonkey.ApplyMethod(reflect.TypeOf(&SomeStruct{}), "Method",
        func(_ *SomeStruct, ctx context.Context) error {
            return nil
        })
    defer patches.Reset()
    // ... test logic
}

// mockey 改写 ✅
func TestXxx(t *testing.T) {
    mockey.PatchConvey("TestXxx", t, func() {
        mockey.Mock((*SomeStruct).Method).To(
            func(_ *SomeStruct, ctx context.Context) error {
                return nil
            }).Build()
        // ... test logic（断言用 convey 的 So 或标准 t.Error 均可）
    })
}
```

#### 规则 2：Mock 函数签名必须与原函数完全一致

```go
// 源码：func (s *ScoreV2Srv) CheckSignIn(ctx context.Context, req *Req) (*Resp, *Rule, error)

// mockey mock ✅ — 第一个参数是 receiver
mockey.Mock((*ScoreV2Srv).CheckSignIn).To(
    func(_ *ScoreV2Srv, _ context.Context, req *Req) (*Resp, *Rule, error) {
        return mockResp, mockRule, nil
    }).Build()
```

#### 规则 3：包级别函数直接 Mock

```go
// 源码：func xlog.S(ctx context.Context) *zap.SugaredLogger

mockey.Mock(xlog.S).To(func(_ context.Context) *zap.SugaredLogger {
    return zap.NewNop().Sugar()
}).Build()
```

#### 规则 4：表驱动测试 + PatchConvey 的组合模式

```go
func TestXxx(t *testing.T) {
    tests := []struct {
        name    string
        // ... fields
    }{ /* ... cases ... */ }

    for _, tt := range tests {
        mockey.PatchConvey(tt.name, t, func() {
            // setup mocks
            mockey.Mock((*Dep).Method).To(func(...) ... { ... }).Build()

            // execute
            got, err := svc.TargetMethod(ctx, tt.input)

            // assert（在 PatchConvey 内用标准 testing 断言即可）
            if (err != nil) != tt.wantErr {
                t.Errorf("error = %v, wantErr %v", err, tt.wantErr)
            }
        })
    }
}
```

#### 规则 5：导入替换

```go
// 移除 gomonkey 导入
// - "reflect"
// - "github.com/agiledragon/gomonkey/v2"

// 添加 mockey 导入
import "github.com/bytedance/mockey"
```

项目 `go.mod` 中已包含 `github.com/bytedance/mockey v1.4.5`，无需额外安装。

### 局部回退 vs 整体回退

| 场景 | 策略 |
|------|------|
| 测试文件中只有 1~2 处 gomonkey 失效 | **局部回退**：仅将失效的 patch 改为 mockey，其他 gomonkey 不动 |
| 测试文件中 gomonkey 大面积失效 | **整体回退**：整个文件统一改为 mockey 风格（PatchConvey 包裹） |
| 同一个测试函数内混合使用 | **不允许**：一个测试函数内不能同时用 gomonkey 和 mockey，必须选一种 |

**判断标准**：同一个测试函数中如果有任何一处需要回退 mockey，则该函数整体改为 mockey。不同测试函数之间可以各自使用不同方案。

---

## 工作流程

### Step 0: 确定 Build Tags

```bash
BUILD_TAGS="ai_test"

if [ -f scripts/build/utils.sh ]; then
    source scripts/build/utils.sh
    SITE=${SITE:-primary}
    BUILD_TAGS="$SITE,$BRANCH_BUILD_TAG,ai_test"
fi

echo "Build tags: $BUILD_TAGS"
```

### Step 1: 运行测试并收集错误

根据用户指定的范围选择运行方式：

#### 全量运行（默认）

```bash
bash scripts/build/test_ai.sh 2>&1
```

#### 指定目录/包

```bash
go test -tags="{build_tags}" -gcflags=all=-l -vet=off -timeout 120s ./{target}/... 2>&1
```

**要求**：完整捕获 stdout + stderr，不要截断输出。

### Step 2: 解析、分类并展示错误

从测试输出中提取所有失败信息，按分类体系进行归类。

#### 展示格式：分类报告

向用户展示结构化的分类报告，帮助快速了解问题全貌：

```
## 错误分类报告

### 总览看板

| 指标 | 值 |
|------|---|
| 失败包数 | 3 |
| 总错误数 | 7 |
| 阻塞性错误（P0 编译） | 2 |
| 崩溃性错误（P1 Panic） | 1 |
| 逻辑性错误（P2 断言/Mock） | 3 |
| 环境性错误（P3 超时） | 1 |

### 按大类分布

| 大类 | 数量 | 子类分布 |
|------|------|---------|
| CE 编译错误 | 2 | CE-UNDEF(1), CE-ARGS(1) |
| RT 运行时 Panic | 1 | RT-NIL(1) |
| AF 断言失败 | 2 | AF-VALUE(1), AF-ERR(1) |
| MK Mock 问题 | 1 | MK-MONKEY(1) |
| ENV 环境 | 1 | ENV-TIMEOUT(1) |

### 按包详情

#### internal/app/meetup/service/admin （3 个错误）

| # | 代号 | 测试函数 | 错误摘要 | 修复方案 |
|---|------|---------|---------|---------|
| 1 | RT-NIL | TestCollectionService_xxx | collection.go:480 解引用 nil current | 传入非 nil 参数 |
| 2 | AF-VALUE | TestValidate_地址超长 | got="", want="错误信息" | 修正期望值 |
| 3 | MK-MONKEY | TestMeetup_Create | gomonkey 未拦截 RewardService 方法 | 改用 mockey |

#### internal/services/score （2 个错误）

| # | 代号 | 测试函数 | 错误摘要 | 修复方案 |
|---|------|---------|---------|---------|
| 1 | CE-UNDEF | - | undefined: NewScoreFunc | 补充导入 |
| 2 | CE-ARGS | - | too many arguments in call to svc.Get | 修正参数数量 |
```

### Step 3: 按优先级逐个修复

修复顺序：**P0 → P1 → P2 → P3**。在同一优先级内，编译错误优先（解除包级阻塞），可能暴露出隐藏错误。

#### 3.1 分析根因

1. **读取测试文件**：定位出错的测试函数
2. **读取源码文件**：理解被测函数的签名、参数要求和行为逻辑（只读不改）
3. **比对**：判断测试代码与源码的不一致之处

#### 3.2 确定修复策略

##### CE — 编译错误

| 子类 | 修复方式 |
|------|---------|
| `CE-UNDEF` | 检查导入是否缺失，标识符是否拼写错误/已重命名 |
| `CE-TYPE` | 修正测试中的类型转换或参数类型 |
| `CE-ARGS` | 根据源码函数签名修正调用参数 |
| `CE-IMPORT` | 删除未使用的导入 |

##### RT — 运行时 Panic

| 子类 | 修复方式 |
|------|---------|
| `RT-NIL` | 提供合理的非 nil 值，或修正 mock 返回非 nil 对象 |
| `RT-BOUND` | 修正测试数据使切片长度满足访问要求，或在断言前加长度检查 |
| `RT-OTHER` | 根据具体 panic 信息针对性修复 |

##### AF — 断言/逻辑失败

| 子类 | 修复方式 |
|------|---------|
| `AF-VALUE` | 阅读源码逻辑，修正期望值或调整测试输入 |
| `AF-ERR` | 根据源码的错误返回行为修正 `wantErr` 和错误断言 |

##### MK — Mock 问题

| 子类 | 修复方式 |
|------|---------|
| `MK-MONKEY` | **回退 mockey**（见上方回退机制） |
| `MK-SQL` | 根据源码实际 SQL 修正 sqlmock 期望的正则 |
| `MK-GOMOCK` | 补充缺失或移除多余的 `.EXPECT()` |

##### ENV — 环境/超时

| 子类 | 修复方式 |
|------|---------|
| `ENV-TIMEOUT` | 检查死循环/死锁，或放大 timeout（`-timeout 300s`） |

#### 3.3 执行修复

使用 Edit 工具修改测试文件。修改时遵循：

- **最小修改原则**：只改必须改的部分
- **保留测试意图**：修复方式不应改变测试的验证目标
- **保持代码风格**：与原测试文件的风格一致
- **同函数不混用**：一个测试函数内 gomonkey 和 mockey 不能混用

#### 3.4 增量验证

每修完一个包（或一批相关错误）后，立即运行验证：

```bash
go test -tags="{build_tags}" -gcflags=all=-l -vet=off -timeout 120s -run "{修复的测试函数}" ./{package}/... 2>&1
```

- **通过** → 继续下一个错误
- **仍失败** → 重新分析，最多重试 3 次
- **3 次后仍失败** → 记录为"未解决"，继续修复其他错误

**重要**：修复编译错误（P0）后，需要重新运行整个包的测试，因为编译错误修复后可能暴露之前被掩盖的运行时错误。新出现的错误需要归类后加入待修复列表。Panic（P1）同理——一个 panic 会终止整个包，修复后可能暴露更多错误。

### Step 4: 全量验证

所有错误修复完成后，重新运行完整测试：

```bash
# 全量
bash scripts/build/test_ai.sh 2>&1

# 指定范围
go test -tags="{build_tags}" -gcflags=all=-l -vet=off -timeout 120s ./{target}/... 2>&1
```

### Step 5: 输出修复报告

```
## 修复报告

### 总览

| 指标 | 值 |
|------|---|
| 原始错误数 | M |
| 已修复 | X |
| 其中 gomonkey→mockey 回退 | N |
| 未解决 | Y |

### 修复详情

| # | 包 | 测试函数 | 错误代号 | 修复方式 | 状态 |
|---|---|---------|---------|---------|------|
| 1 | meetup/admin | TestCollectionService_xxx | RT-NIL | 传入非 nil current 对象 | ✅ |
| 2 | meetup/admin | TestMeetup_Create | MK-MONKEY | gomonkey→mockey 回退 | ✅ |
| 3 | services/score | - | CE-UNDEF | 补充缺失导入 | ✅ |
| 4 | services/xxx | TestYyy | AF-VALUE | 未解决（源码逻辑不明） | ❌ |

### Mock 回退记录

| 文件 | 回退范围 | 原因 | 涉及函数 |
|------|---------|------|---------|
| meetup_ai_test.go | 局部（1个函数） | ApplyMethod 未拦截 RewardService | TestMeetup_Create |
| task_ai_test.go | 整体 | macOS ARM gomonkey 权限问题 | 全部 3 个测试函数 |

### 未解决的问题

{对每个未解决的问题，说明代号、原因和建议}
```

---

## 常见修复模式速查

### 模式 1：nil 参数传递（RT-NIL）

```go
// ❌ 传 nil 给不接受 nil 的参数
logs := s.calculateReorderPlan(collections, nil, nil)

// ✅ 构造合理的非 nil 值（需阅读源码确定值不影响断言）
current := &model.Collection{ID: 999, PositionSequence: 4}
logs := s.calculateReorderPlan(collections, current, nil)
```

### 模式 2：函数签名变更（CE-ARGS）

```go
// ❌ 源码增加了参数
result, err := svc.Foo(ctx, 123)

// ✅ 补充新增参数
result, err := svc.Foo(ctx, 123, nil)
```

### 模式 3：sqlmock 不匹配（MK-SQL）

```go
// ❌ SQL 变更导致正则不匹配
mock.ExpectQuery("SELECT \\* FROM `users` WHERE id").WillReturnRows(rows)

// ✅ 根据实际 SQL 更新正则
mock.ExpectQuery("SELECT \\* FROM `users` WHERE `users`.`id`").WillReturnRows(rows)
```

### 模式 4：期望值过时（AF-VALUE）

```go
// ❌ 源码逻辑已变更
assert.Equal(t, 3, result)

// ✅ 根据当前源码逻辑修正
assert.Equal(t, 4, result)
```

### 模式 5：gomonkey→mockey 回退（MK-MONKEY）

```go
// ❌ gomonkey 失效
patches := gomonkey.ApplyMethod(reflect.TypeOf(&RewardService{}), "GetAmount",
    func(_ *RewardService, ctx context.Context, id int64) (int64, error) {
        return 100, nil
    })
defer patches.Reset()

result := svc.Calculate(ctx, 1)
assert.Equal(t, 100, result)

// ✅ 改用 mockey
mockey.PatchConvey("TestCalculate", t, func() {
    mockey.Mock((*RewardService).GetAmount).To(
        func(_ *RewardService, ctx context.Context, id int64) (int64, error) {
            return 100, nil
        }).Build()

    result := svc.Calculate(ctx, 1)
    assert.Equal(t, 100, result)
})
```

### 模式 6：struct 字段不完整（RT-NIL）

```go
// ❌ 缺少必需字段导致 nil panic
svc := &Service{RepoA: repoA}

// ✅ 补充新增字段
svc := &Service{RepoA: repoA, RepoB: repoB}
```

### 模式 7：缺少 mock 设置（MK-GOMOCK）

```go
// ❌ 源码新增了外部调用，测试未 mock
// → gomock: missing call(s) to NewMethod

// ✅ 补充缺失的 mock
mockSvc.EXPECT().NewMethod(gomock.Any()).Return(nil, nil)
```

---

## 注意事项

1. **不修改源码**：最核心约束。即使源码有明显 bug（如缺少 nil 检查），也只修改测试代码绕过问题，并在报告中标注
2. **理解测试意图**：修复前务必理解原测试想验证什么，修复后的测试应保持相同的验证目标
3. **build tags**：所有 `go test` / `go build` 命令必须使用 `-tags "{build_tags}"`，否则 `_ai_test.go` 不会被编译
4. **gomonkey 内联**：运行测试时必须加 `-gcflags=all=-l`
5. **增量修复**：优先修复编译错误（P0），因为编译错误会阻塞同包所有测试的运行
6. **Panic 掩盖效应**：一个 panic 会终止整个包的测试运行，修复后可能暴露更多错误，需要多轮迭代
7. **并行修复**：不同包的错误互不影响，可以使用多个 Agent 并行修复不同包
8. **mockey 回退时机**：只在 gomonkey 确实失效时才回退 mockey，不要预防性地全部替换
9. **同函数不混用**：同一个测试函数内 gomonkey 和 mockey 不能共存；不同函数可以各自使用不同方案
10. **mockey 已可用**：项目 `go.mod` 已包含 `github.com/bytedance/mockey v1.4.5`，无需额外安装依赖
