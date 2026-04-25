# Mockey 使用规范

> 本项目使用 `github.com/bytedance/mockey` 作为函数/方法级 Mock 工具。

## 基本模式

### Mock 结构体方法（指针接收者）

```go
import (
    "github.com/bytedance/mockey"
)

// 指针接收者方法
mocker := mockey.Mock((*TargetStruct).MethodName).To(
    func(_ *TargetStruct, args...) (returns...) {
        return mockValues...
    },
).Build()
defer mocker.UnPatch()
```

### Mock 结构体方法（值接收者）

```go
mocker := mockey.Mock(TargetStruct.MethodName).To(
    func(_ TargetStruct, args...) (returns...) {
        return mockValues...
    },
).Build()
defer mocker.UnPatch()
```

### 简单返回值（无需写 hook 函数）

```go
mocker := mockey.Mock((*TargetStruct).MethodName).Return(mockValue1, nil).Build()
defer mocker.UnPatch()
```

## Mock 全局函数

```go
mocker := mockey.Mock(time.Now).To(func() time.Time {
    return time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
}).Build()
defer mocker.UnPatch()

// 简单返回值
mocker := mockey.Mock(time.Now).Return(time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)).Build()
defer mocker.UnPatch()
```

## Mock 全局变量

```go
mocker := mockey.MockValue(&global.DB).To(gormDB)
defer mocker.UnPatch()
```

## 多个 Mock（链式）

```go
// 每个 Mock 独立创建，统一用 PatchConvey 或手动 UnPatch
mocker1 := mockey.Mock((*A).Method1).Return(result1, nil).Build()
defer mocker1.UnPatch()

mocker2 := mockey.Mock((*B).Method2).Return(result2, nil).Build()
defer mocker2.UnPatch()

mocker3 := mockey.Mock(SomeFunc).Return(result3).Build()
defer mocker3.UnPatch()
```

## 使用 GetMethod 处理特殊情况

当无法直接引用方法时（如未导出类型、嵌套 struct 方法），使用 `GetMethod`：

```go
// 通过实例 mock 方法（包括接口类型实例）
instance := &SomeStruct{}
mocker := mockey.Mock(mockey.GetMethod(instance, "MethodName")).Return(result).Build()
defer mocker.UnPatch()

// mock 未导出类型的方法
mocker := mockey.Mock(mockey.GetMethod(someFactory(), "MethodName")).Return(result).Build()
defer mocker.UnPatch()
```

## 注意事项

1. **必须禁用内联**：测试运行需要 `-gcflags='all=-N -l'`
2. **必须 UnPatch**：每个 mocker 必须在测试结束时 UnPatch（或使用 PatchConvey/PatchRun 自动管理）
3. **不支持并行**：不要使用 `t.Parallel()`
4. **签名匹配**：使用 `To` 时 hook 函数签名必须完全匹配原函数（receiver 可省略）
5. **私有方法**：可通过 `GetMethod` mock 未导出方法

## 私有方法处理策略

mockey 的 `GetMethod` 支持 mock 未导出方法，但推荐优先 mock 其调用的公开依赖：

```go
// 方式 1（推荐）：mock 私有方法内部调用的公开依赖
mocker := mockey.Mock((*Repo).Save).Return(nil).Build()
defer mocker.UnPatch()

// 方式 2：直接 mock 未导出方法（mockey 支持）
mocker := mockey.Mock(mockey.GetMethod(&Service{}, "privateMethod")).Return(nil).Build()
defer mocker.UnPatch()
```

### Mock 层级图示

```
┌──────────────────────────────────────────────────────┐
│  业务逻辑层（测试目标）                                │
│  PublicMethod() → privateHelper()                    │
│                   (私有方法，推荐 mock 其公开依赖)      │
└──────────────────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────┐
│  数据访问层                                           │
│  Repo.PublicMethod()  ← mockey mock 这里              │
└──────────────────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────┐
│  基础设施层（⚠️ 禁止 mockey mock 方法）                │
│  *gorm.DB / *sql.DB / *xdb.XDB   ← 必须用 sqlmock     │
│  *redis.Client                   ← 必须用 miniredis   │
│  *http.Client                    ← 必须用 httptest    │
└──────────────────────────────────────────────────────┘
```

### Mock 策略总结

| 方法类型 | Mock 策略 |
|---------|----------|
| 公开方法（首字母大写） | `mockey.Mock((*Struct).Method).To(hook).Build()` 直接 mock |
| 私有方法（首字母小写） | 推荐 mock 其调用的公开依赖，或用 `GetMethod` 直接 mock |
| 接口方法 | 使用 gomock 生成 mock 实现 |
| `*gorm.DB` / `*sql.DB` 方法 | ❌ **禁止 mockey**，必须用 sqlmock |
| `*redis.Client` 方法 | ❌ **禁止 mockey**，必须用 miniredis |
| `*http.Client` / HTTP 调用 | ❌ **禁止 mockey**，必须用 httptest |

## 与 gomock 混合使用

同一测试中可同时使用 mockey（具体类型）和 gomock（接口）：

```go
func TestCombinedMock(t *testing.T) {
    // gomock 用于接口（必须使用 go.uber.org/mock，禁止 github.com/golang/mock）
    // import "go.uber.org/mock/gomock"
    ctrl := gomock.NewController(t)
    defer ctrl.Finish()
    mockUserSrv := mockutils.NewMockIUserUtilSrv(ctrl)
    mockUserSrv.EXPECT().
        GetUserDetailByUserIds(gomock.Any(), gomock.Any()).
        Return([]*auth.User{{Uuid: 1001}}, nil)

    // mockey 用于具体类型
    mocker := mockey.Mock((*esrepo.SearchES).DistinctUuidArray).To(
        func(_ *esrepo.SearchES, ctx context.Context, indices []string, filter *xes.EsSearch) ([]string, int, error) {
            return []string{"1001"}, 1, nil
        },
    ).Build()
    defer mocker.UnPatch()

    // 注入所有 mock
    s := &TaskSrv{
        IUserUtilSrv: mockUserSrv,
        SearchES:     &esrepo.SearchES{},
    }
    // 执行测试...
}
```

## 常见错误速查表

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `function is too short to patch` | 目标函数太短被内联 | 添加 `-gcflags='all=-N -l'` |
| mock 不生效 | 未禁用内联优化 | 添加 `-gcflags='all=-N -l'` |
| mock 不生效 | 未调用 Build() | 确保链式调用以 `.Build()` 结尾 |
| 测试间相互影响 | 未调用 UnPatch() | `defer mocker.UnPatch()` |
| 并行测试失败 | mockey 修改全局函数指令，非并发安全 | 移除 `t.Parallel()` |
| 方法签名不匹配 | To() 的 hook 函数参数/返回值类型错误 | 使用 Return() 简化，或确保签名完全匹配 |
| `signal SIGBUS: bus error` | M 系列 Mac 内存权限问题 | 升级 mockey 到最新版本 |

## 安装

```bash
go get github.com/bytedance/mockey@latest
```
