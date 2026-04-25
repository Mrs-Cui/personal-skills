---
name: golang-unittest-writer
description: 编写或修改 Golang 单元测试代码，使用表驱动测试模式和 gomock/mockey Mock 技术。由 golang-unittest 主控调度，也可独立调用。Use when 需要生成测试代码或修复测试编译错误。
---

# Golang 单元测试 Writer

## 职责

编写高质量的 Golang 单元测试代码，使用表驱动测试模式和适当的 Mock 技术。

## 工作流程

### Step 0: Build tag（通常已由主控完成）

> 主控 Agent 在调度前已统一执行 `check_build_tags.sh` + `add_build_tags.sh`（详见主控 SKILL 的 Step 0）。
> 如果你是被独立调用（非主控调度），需要自行执行主控 skill 的脚本（脚本统一维护在 `golang-unittest/scripts/` 下）：
> ```bash
> bash {golang_unittest_skill_path}/scripts/check_build_tags.sh <目录...>
> bash {golang_unittest_skill_path}/scripts/add_build_tags.sh <目录...>
> ```

### Step 1: 分析源码

1. 读取目标源文件
2. 识别所有公开函数/方法
3. 分析每个函数的：
   - 输入参数和返回值
   - 内部依赖（数据库、HTTP、gRPC 等）
   - 分支逻辑和边界条件

### Step 2: 确定 Mock 策略

| 依赖类型 | Mock 方式 | 参考 |
|---------|----------|------|
| 接口类型 | **使用主控预生成的 gomock Mock**（见下方说明） | `references/mock-patterns.md` |
| 结构体方法（公开） | mockey.Mock((*Struct).Method) | `references/mockey-patterns.md` |
| 结构体方法（私有） | mock 其调用的公开依赖，或 mockey.GetMethod | `references/mockey-patterns.md` |
| 全局函数 | mockey.Mock(Func) | `references/mockey-patterns.md` |
| HTTP 调用 | httptest.NewServer | `references/mock-patterns.md` |
| gRPC 调用 | mockey mock client 方法 | `references/mockey-patterns.md` |
| 数据库 | sqlmock(**优先使用**) 或 mock repo 层 | `references/mock-patterns.md` |
| Redis | miniredis(**优先使用**) 或 mock client | `references/mock-patterns.md` |
| ES 操作 | httptest + mockey | `references/es-testing.md` |

#### ⚠️ 接口 Mock 强制规则

**禁止在测试文件中手写 `type mockXxx struct { ... }` 来实现接口。**

主控 Agent 在调用 Writer 之前，已通过 `detect_interface_deps.py` + `ensure_mock_generate.sh` 自动检测并生成了所有外部接口的 gomock Mock。主控会在 prompt 中提供 **"已生成的 gomock Mock 信息"** 表格，包含：

| 信息 | 说明 |
|------|------|
| Mock 导入路径 | 如 `"project/testmocks/services/userv2"` |
| Mock 类型名 | 如 `mock_userv2.MockUserService` |
| 构造函数 | 如 `mock_userv2.NewMockUserService(ctrl)` |

**Writer 必须**：
1. import gomock 时使用 `"go.uber.org/mock/gomock"`，禁止使用已废弃的 `"github.com/golang/mock/gomock"`
2. 在 import 块中导入主控提供的 Mock 包路径
3. 使用 `gomock.NewController(t)` 创建 controller
4. 使用 `NewMockXxx(ctrl)` 构造 Mock 实例
5. 使用 `.EXPECT().Method(args).Return(values)` 设置期望

**示例**：

```go
import (
    "go.uber.org/mock/gomock"
    mock_userv2 "github.com/yourorg/yourproject/testmocks/services/userv2"
    mock_member "github.com/yourorg/yourproject/testmocks/services/member"
)

func TestCoreService_SomeMethod(t *testing.T) {
    ctrl := gomock.NewController(t)
    defer ctrl.Finish()

    mockUserSvc := mock_userv2.NewMockUserService(ctrl)
    mockMemberSrv := mock_member.NewMockIMemberSRV(ctrl)

    // 设置期望
    mockUserSvc.EXPECT().
        GetNormalUserByUserID(gomock.Any(), gomock.Eq(123)).
        Return(mockUser, nil)

    // 构造被测 struct，注入 mock
    srv := CoreService{
        UserService: mockUserSvc,
        IMemberSRV:  mockMemberSrv,
    }

    // 执行测试...
}
```

**如果 prompt 中没有 Mock 信息**（例如被测函数是包级别函数，不依赖接口字段），则按其他 Mock 方式处理（mockey 等）。

#### ⚠️ mockey 回退接口处理

当主控 prompt 中包含 **"mockey 回退接口"** 表格时，说明这些接口因方法签名引用了未导出类型，gomock 无法生成 Mock。对这些接口，Writer 必须：

1. **不要** import 任何 gomock mock 包（这些接口没有生成 mock 文件）
2. **不要** 手写 `type mockXxx struct` 来实现接口
3. **使用 mockey.Mock + mockey.GetMethod** 对接口方法进行 mock

```go
import (
    "github.com/bytedance/mockey"
    membersrv "github.com/yourorg/yourproject/internal/services/member"
)

func TestSomeMethod(t *testing.T) {
    // 对于 mockey 回退的接口字段，给一个零值或空实现
    srv := &CoreService{
        // gomock 接口正常注入 mock
        UserService: mockUserSvc,
        // mockey 回退接口：使用 nil 或零值，后续用 mockey mock
    }

    // 用 mockey mock 接口方法
    var iMemberSrv membersrv.IMemberSRV
    mocker := mockey.Mock(mockey.GetMethod(iMemberSrv, "GetMember")).To(
        func(ctx context.Context, uid int64) (*membersrv.Member, error) {
            return &membersrv.Member{ID: uid}, nil
        }).Build()
    defer mocker.UnPatch()

    // 执行测试...
}
```

注意：mockey 回退接口和 gomock 接口可以在同一个测试中混合使用。

#### ⚠️ 基础设施依赖 Mock 强制规则

Writer 在分析源码时，**必须检查被测 struct 的字段类型和函数体内的依赖调用**，识别基础设施依赖并使用对应的专用 Mock 工具。

**类型识别与 Mock 工具映射（强制）：**

| 识别到的类型 | 必须使用的 Mock 工具 | 禁止的做法 |
|-------------|---------------------|-----------|
| `*gorm.DB` / `*sql.DB` / `*sqlx.DB` / *xdb.XDB | `go-sqlmock` | ❌ mockey.Mock |
| `*redis.Client` / `*redis.ClusterClient` | `miniredis` | ❌ mockey.Mock |
| `*http.Client` / HTTP 外部调用 | `httptest.NewServer` | ❌ mockey mock http 方法 |

**决策树（按优先级从高到低）：**

```
被测 struct 的某个字段是什么类型？
│
├─ 接口类型（如 IUserSrv）
│   └─ 使用 gomock 生成的 Mock（见上方「接口 Mock 强制规则」）
│
├─ *gorm.DB / *sql.DB / *xdb.XDB
│   └─ 必须用 sqlmock 创建 mock DB，注入到被测 struct
│      示例：db, mock, _ := sqlmock.New()
│            gormDB, _ := gorm.Open(mysql.New(mysql.Config{Conn: db}), &gorm.Config{})
│            srv := &OrderSrv{DB: gormDB}
│
├─ *redis.Client / *redis.ClusterClient
│   └─ 必须用 miniredis 创建 mock server，注入到被测 struct
│      示例：mr, _ := miniredis.Run()
│            client := redis.NewClient(&redis.Options{Addr: mr.Addr()})
│            srv := &OrderSrv{Redis: client}
│
├─ 嵌入/包装了 DB 的 Repo/DAO struct（如 *xxxRepo、*xxxDao，内部嵌入 Repo[T] 或直接持有 *gorm.DB/*xdb.XDB）
│   └─ 必须用 sqlmock 构造 mock DB，通过构造函数注入（如 repo.NewXxxRepo(mockDB)）
│   └─ ❌ 禁止 mockey.Mock（泛型值接收者方法 mock 不稳定）
│   └─ 判断方法：检查 struct 定义，若嵌入了 common.Repo[T] 或字段中含 *gorm.DB/*xdb.XDB，即命中此规则
│      示例：mockDB, mock := newTestXDB(t)
│            repo := repo.NewXxxRepo(conn.ActivityDB(mockDB), conn.ActivitySlaveDB(mockDB))
│            srv := &XxxService{Repo: repo}
│
├─ 具体 struct 类型（如 *esrepo.SearchES）
│   └─ 使用 mockey.Mock((*Struct).Method) mock 其公开方法
│
└─ 包级别全局变量（如 global.DB / global.Redis）
    └─ 使用 mockey.MockValue 替换全局变量
       对于全局 *gorm.DB：优先用 mockey.MockValue 替换全局变量为 sqlmock 实例
       对于全局 *redis.Client：优先用 mockey.MockValue 替换全局变量为 miniredis 实例
```

**禁止事项：**

- ❌ 禁止对 `*gorm.DB`/ `*xdb.XDB` / `*sql.DB` 的方法（如 `TX`、`COMMIT`、`Where`、`Find`、`Create`）使用 mockey.Mock
- ❌ 禁止对 `*redis.Client` 的方法（如 `Get`、`Set`、`HGetAll`）使用 mockey.Mock
- ❌ 禁止用 mockey 直接 mock 数据库驱动层函数
- ❌ 禁止对嵌入了 `Repo[T]` 泛型的 repo struct 使用 mockey.Mock（泛型值接收者方法 mock 不稳定）

**GORM + sqlmock 注入示例：**

```go
import (
    "github.com/DATA-DOG/go-sqlmock"
    "gorm.io/driver/mysql"
    "gorm.io/gorm"
)

func setupGormMock(t *testing.T) (*gorm.DB, sqlmock.Sqlmock) {
    db, mock, err := sqlmock.New()
    if err != nil {
        t.Fatalf("sqlmock.New() error: %v", err)
    }
    gormDB, err := gorm.Open(mysql.New(mysql.Config{
        Conn:                      db,
        SkipInitializeWithVersion: true,
    }), &gorm.Config{})
    if err != nil {
        t.Fatalf("gorm.Open() error: %v", err)
    }
    return gormDB, mock
}

// 在测试中使用
func TestOrderSrv_CreateOrder(t *testing.T) {
    gormDB, mock := setupGormMock(t)

    mock.ExpectBegin()
    mock.ExpectExec("INSERT INTO `orders`").
        WithArgs(sqlmock.AnyArg(), sqlmock.AnyArg(), sqlmock.AnyArg()).
        WillReturnResult(sqlmock.NewResult(1, 1))
    mock.ExpectCommit()

    srv := &OrderSrv{DB: gormDB}
    err := srv.CreateOrder(context.Background(), &Order{Name: "test"})

    assert.NoError(t, err)
    assert.NoError(t, mock.ExpectationsWereMet())
}
```

**miniredis + go-redis 注入示例：**

```go
import (
    "github.com/alicebob/miniredis/v2"
    "github.com/go-redis/redis/v8"
)

func setupRedisMock(t *testing.T) (*redis.Client, *miniredis.Miniredis) {
    mr, err := miniredis.Run()
    if err != nil {
        t.Fatalf("miniredis.Run() error: %v", err)
    }
    client := redis.NewClient(&redis.Options{Addr: mr.Addr()})
    return client, mr
}

// 在测试中使用
func TestOrderSrv_GetCache(t *testing.T) {
    client, mr := setupRedisMock(t)
    defer mr.Close()

    // 预设 Redis 数据
    mr.Set("order:123", `{"id":123,"name":"test"}`)

    srv := &OrderSrv{Redis: client}
    order, err := srv.GetCache(context.Background(), 123)

    assert.NoError(t, err)
    assert.Equal(t, "test", order.Name)
}
```

**注意**：当被测 struct 同时持有接口字段和基础设施字段时，接口用 gomock，基础设施用专用工具，两者可以在同一个测试中混合使用。详细模式参见 `references/mock-patterns.md`。

### Step 3: 生成测试代码

> **核心原则：为目标函数列表中的每一个函数生成测试，每个代码分支只需 1 个 case。**
>
> **铁律：禁止自行筛选或跳过目标函数。** 主控/Analyzer 传入的目标函数列表已经过分组优化，Writer 必须为列表中的**每一个函数**生成测试，不得以"函数过多"、"优先覆盖核心方法"、"时间不够"等理由跳过任何函数。如果单次无法写完所有函数，采用拆分写入策略逐个追加。

使用表驱动测试模式，每个分支 1 个 case：

```go
//go:build ai_test

package xxx

import (...)

func TestXxx(t *testing.T) {
    tests := []struct {
        name      string
        input     InputType
        mockSetup func()
        want      OutputType
        wantErr   bool
    }{
        {
            name: "正常流程",
            // 1 个正常路径 case
        },
        {
            name: "依赖A返回错误",
            // 每个 error return 点 1 个 case
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            if tt.mockSetup != nil {
                tt.mockSetup()
            }
            got, err := FunctionUnderTest(tt.input)
            if (err != nil) != tt.wantErr {
                t.Errorf("error = %v, wantErr %v", err, tt.wantErr)
            }
            if !reflect.DeepEqual(got, tt.want) {
                t.Errorf("got = %v, want %v", got, tt.want)
            }
        })
    }
}
```

## 测试用例设计原则

### 核心原则：全部覆盖、每分支一例

**必须为所有目标函数生成测试**，每个函数用最少的 test case 覆盖所有代码分支（不追求同一分支的多种输入变体）。

### 用例设计策略

1. **每个代码分支只需 1 个 case**：if/else、switch 的每个分支各写一个 case 即可，不需要为同一分支写多个变体
2. **错误路径只覆盖不同的 return**：多个 `if err != nil { return err }` 只需每个 return 点一个 case
3. **跳过纯边界穷举**：不需要为同一逻辑写空值、零值、最大值、最小值等多个 case——选一个能走到目标分支的输入即可
4. **优先覆盖主干逻辑**：1 个正常流程 case + 每个错误 return 各 1 个 case，就够了
5. **不写重复路径的 case**：如果两个输入走的代码路径完全相同，只保留一个

### 速度优先的实践

- 函数只有 1 个 if 分支 → 2 个 case（正常 + 分支）
- 函数有 3 个 error return → 4 个 case（1 正常 + 3 错误）
- 函数有 switch 5 个 case → 5-6 个 case（每个 case 分支 1 个）
- 不需要为每个 case 考虑"边界条件"子集

### 用例命名规范

```
{场景}_{条件}
```

示例：
- `正常流程`
- `参数为空_返回错误`
- `数据库查询失败`

## 输出要求

生成的测试文件应：

1. **文件命名**：`{source}_ai_test.go`
2. **Build tag**：文件首行必须是 `//go:build ai_test`，不得包含其他环境 tag（如 `primary`、`local`、`staging` 等）。环境 tag 仅在 `go test` 命令行通过 `-tags` 传入，不写进文件
3. **包声明**：与源文件相同
4. **导入管理**：只导入必要的包
5. **测试函数命名**：`Test{StructName}_{MethodName}`，**禁止包含任何中文字符**，函数名必须全部使用英文、数字和下划线

## 拆分写入策略（防止 JSON 截断）

**背景**：当测试代码较长时（通常超过 200 行），Write 工具的 JSON 参数可能因内容过大而被截断，导致 `JSON Parse error: Expected '}'` 错误。

**核心原则**：将测试代码拆分为多次写入，每次写入控制在合理大小内。

### 写入流程

#### 第一步：Write 写入文件骨架

使用 Write 工具创建测试文件，只包含 build tag、package 声明、import 块和第一个测试函数：

```go
//go:build ai_test

package custom

import (
    "context"
    "errors"
    "testing"
    // ... 所有需要的 import，一次性写全
)

// 第一个测试函数
func TestXxx_FuncA(t *testing.T) {
    tests := []struct { ... }{ ... }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) { ... })
    }
}
```

**关键**：import 块必须在第一次写入时包含所有测试函数需要的导入，避免后续追加时需要修改 import。

#### 第二步：Edit 逐个追加后续测试函数

对每个后续的测试函数，使用 Edit 工具在文件末尾追加：

```
Edit(
    filePath: "xxx_ai_test.go",
    oldString: "文件最后一个右花括号所在的完整行及上下文",
    newString: "原内容 + 新测试函数"
)
```

具体做法：找到文件末尾最后一个测试函数的结束 `}` 及其上方几行作为 oldString 的定位锚点，在其后追加新的测试函数。

### 拆分粒度

| 场景 | 拆分方式 |
|------|---------|
| 单文件 ≤ 2 个函数 | Write 一次写入全部（通常不超过 200 行） |
| 单文件 > 2 个函数 | Write 骨架 + 第1个函数，Edit 逐个追加其余函数 |
| 分组模式（多 group） | 每个 group 对应一次 Write/Edit |

### 示例

假设需要为 `FuncA`、`FuncB`、`FuncC` 三个函数生成测试：

```
1. Write: package + import + TestFuncA（约 100 行）
2. Edit:  在文件末尾追加 TestFuncB（约 80 行）
3. Edit:  在文件末尾追加 TestFuncC（约 80 行）
```

### 注意事项

1. **import 一次写全**：第一次 Write 时预判所有测试函数需要的 import，全部写入。避免后续 Edit 需要修改 import 块
2. **Edit 定位要精确**：使用文件末尾足够多的上下文行（3-5 行）作为 oldString，确保唯一匹配
3. **每次 Edit 后验证**：如果有多个函数要追加，可以全部追加完再统一验证编译，减少验证次数

## 修复错误模式

当收到 Validator 返回的错误时：

### 编译错误

1. 检查导入是否正确
2. 检查类型是否匹配
3. 检查方法签名是否正确

### 测试失败

1. 检查 mock 返回值是否正确
2. 检查期望值是否与源码逻辑一致
3. 检查是否遗漏了必要的 mock

## 补充覆盖率模式

当收到 Coverage Agent 返回的未覆盖分支时：

1. 分析未覆盖的代码行
2. 确定触发该分支的输入条件
3. 添加新的测试用例覆盖该分支
4. 确保 mock 设置能够触发目标分支

## 执行go命令模式

如果需要执行 go 命令，如`go test`、`go build`，**必须**加上{build_tags} 和 `-gcflags='all=-N -l'`禁用内联和优化