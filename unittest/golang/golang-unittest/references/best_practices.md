# Golang 单元测试最佳实践

## mockey 使用指南

> 本项目使用 `github.com/bytedance/mockey` 作为函数/方法级 Mock 工具。

### 基本用法

```go
import (
    "github.com/bytedance/mockey"
)

// Mock 结构体方法（指针接收者）
mocker := mockey.Mock((*TargetStruct).MethodName).To(
    func(_ *TargetStruct, ctx context.Context, args ...interface{}) (Result, error) {
        return mockResult, nil
    },
).Build()
defer mocker.UnPatch()

// Mock 全局函数
mocker := mockey.Mock(targetFunc).To(
    func(args ...interface{}) Result {
        return mockResult
    },
).Build()
defer mocker.UnPatch()

// 简单返回值（无需写 hook 函数）
mocker := mockey.Mock((*TargetStruct).MethodName).Return(mockResult, nil).Build()
defer mocker.UnPatch()
```

### 关键注意事项

1. **必须禁用内联**
   ```bash
   go test -gcflags='all=-N -l' ./...
   ```

2. **必须调用 UnPatch**
   ```go
   mocker := mockey.Mock(...).Return(...).Build()
   defer mocker.UnPatch()  // 必须！
   ```

3. **不支持并行测试**
   ```go
   // 不要使用
   t.Parallel()
   ```

4. **私有方法可通过 GetMethod mock**
   ```go
   // 推荐：mock 私有方法调用的公开依赖
   mocker := mockey.Mock((*Dependency).PublicMethod).Return(nil).Build()
   defer mocker.UnPatch()

   // 也可以直接 mock 私有方法（mockey 支持）
   mocker := mockey.Mock(mockey.GetMethod(&Service{}, "privateMethod")).Return(nil).Build()
   defer mocker.UnPatch()
   ```

### 多个 Mock

```go
mocker1 := mockey.Mock((*A).Method1).Return(result1).Build()
defer mocker1.UnPatch()

mocker2 := mockey.Mock((*B).Method2).Return(result2).Build()
defer mocker2.UnPatch()

mocker3 := mockey.Mock(GlobalFunc).Return(result3).Build()
defer mocker3.UnPatch()
```

## 常见问题解决

### 问题：function is too short to patch

**原因**：目标函数太短被编译器内联

**解决**：确保添加了 `-gcflags='all=-N -l'`

### 问题：私有方法需要 mock

**推荐**：mock 私有方法内部调用的公开方法

```go
// 私有方法
func (s *Service) processData(data []byte) error {
    return s.repo.Save(data)  // 调用公开方法
}

// Mock 公开方法
mocker := mockey.Mock((*Repo).Save).To(
    func(_ *Repo, data []byte) error {
        return nil
    },
).Build()
defer mocker.UnPatch()
```

### 问题：ES 客户端返回错误时 panic

**原因**：httptest mock HTTP 500 时 ES 客户端会 panic

**解决**：直接 mock ES 方法层，不 mock HTTP 层

```go
// 不要这样
server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(500)
}))

// 应该这样
mocker := mockey.Mock((*CustomES).Query).To(
    func(_ *CustomES, ctx context.Context, query interface{}) ([]Result, error) {
        return nil, errors.New("ES error")
    },
).Build()
defer mocker.UnPatch()
```

### 问题：期望值与实际值不匹配

**原因**：未仔细阅读源码逻辑

**解决**：分析源码确定各种情况下的实际返回值

```go
// 源码
if len(results) == 0 {
    isFilter = true  // 空结果时返回 true
    return
}

// 测试期望应该匹配源码逻辑
{
    name:       "空结果返回isFilter=true",
    mockReturn: []string{},
    wantFilter: true,  // 不是 false！
}
```

## Mock 层级选择

```
场景 A: 被测代码 → repo/service 接口 → DB/Redis
  → mock 接口层（gomock 生成的 Mock）
  → 这是最干净的方式，推荐架构设计时使用接口隔离

场景 B: 被测代码 → 直接操作 *gorm.DB / *sql.DB / *xdb.XDB
  → 必须用 sqlmock 创建 mock DB 实例，注入到被测 struct
  → ❌ 禁止对 *gorm.DB / *sql.DB / *xdb.XDB 使用 mockey

场景 C: 被测代码 → 直接操作 *redis.Client
  → 必须用 miniredis 创建 mock server，注入到被测 struct
  → ❌ 禁止对 *redis.Client 使用 mockey

场景 D: 被测代码 → 全局变量 global.DB / global.Redis
  → mockey.MockValue 替换全局变量为 sqlmock/miniredis 实例
  → 本质上仍然是用专用工具，只是注入方式不同

场景 E: 被测代码 → 具体 struct 方法（如 *esrepo.SearchES）
  → mockey.Mock((*Struct).Method) mock 该 struct 的公开方法
```

**判断顺序**：先看字段类型 → 接口用 gomock，基础设施具体类型用专用工具，其他具体类型用 mockey。

## 表驱动测试模板

> **原则：快速生成、快速提高覆盖率。每个代码分支只需 1 个 case，不追求用例完整性。**

```go
func TestXxx(t *testing.T) {
    tests := []struct {
        name      string
        input     InputType
        mockSetup func()
        want      OutputType
        wantErr   bool
    }{
        {
            name:  "正常流程",
            input: validInput,
            mockSetup: func() {
                mockey.Mock((*Dep).Method).Return(expectedResult, nil).Build()
            },
            want:    expectedResult,
            wantErr: false,
        },
        {
            name:  "依赖返回错误",
            input: validInput,
            mockSetup: func() {
                mockey.Mock((*Dep).Method).Return(nil, errors.New("error")).Build()
            },
            wantErr: true,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            mockey.PatchConvey(tt.name, t, func() {
                if tt.mockSetup != nil {
                    tt.mockSetup()
                }

                got, err := FunctionUnderTest(tt.input)

                if (err != nil) != tt.wantErr {
                    t.Errorf("error = %v, wantErr %v", err, tt.wantErr)
                    return
                }
                if !reflect.DeepEqual(got, tt.want) {
                    t.Errorf("got = %v, want %v", got, tt.want)
                }
            })
        })
    }
}
```

## 测试命名规范

```
Test{结构体}_{方法名}
```

子测试命名：
```
{场景}_{条件}_{预期结果}
```

示例：
- `TestUserService_GetUser`
  - `正常情况_用户存在_返回用户信息`
  - `边界条件_用户ID为0_返回错误`
  - `错误处理_数据库连接失败_返回错误`
