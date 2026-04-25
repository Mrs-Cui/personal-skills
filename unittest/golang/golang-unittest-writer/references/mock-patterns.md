# Mock 模式速查

> ⚠️ **强制规则：统一使用 `go.uber.org/mock`（gomock + mockgen）。`github.com/golang/mock` 已停止维护，禁止使用。**
> - import 路径：`"go.uber.org/mock/gomock"`（禁止 `"github.com/golang/mock/gomock"`）
> - 安装 mockgen：`go install go.uber.org/mock/mockgen@latest`
> - `ensure_mock_generate.sh` 会自动检查 mockgen 版本并在 go.mod 中添加依赖

## gomock 生成流程

### mockgen 命令

```bash
# 方式 1: 从源文件生成（-source 模式，脚本默认优先使用）
mockgen -source=internal/repo/user_repository.go \
    -destination=testmocks/repo/mock_user_repository.go \
    -package=repo

# 方式 2: 从包生成（reflect 模式，接口引用未导出符号时自动回退）
mockgen -destination=testmocks/services/mock_service.go \
    -package=services \
    github.com/yourproject/internal/services UserService,OrderService
```

### go:generate 自动化（强制）

**⚠️ 强制规则：涉及已定义接口的 Mock 时，必须通过脚本自动生成，禁止手动编写任何 Mock 代码。**

#### 使用脚本生成 Mock

脚本 `scripts/ensure_mock_generate.sh` 会自动完成：检查/添加 `go:generate` 注释 → 计算正确的 `-destination` 路径（含 `internal/` 去除逻辑）→ 执行 `go generate` 生成 Mock 文件 → 验证编译 → 失败时自动回退到 reflect 模式。

```bash
# 用法: ./scripts/ensure_mock_generate.sh <项目根目录> [--tags "tag1,tag2"] <接口文件1> [接口文件2] ...
# 接口文件路径相对于项目根目录

# 单个文件
./scripts/ensure_mock_generate.sh /path/to/project internal/repo/user_repository.go

# 多个文件，带 build tags
./scripts/ensure_mock_generate.sh /path/to/project \
    --tags "primary,local,ai_test" \
    internal/repo/user_repository.go \
    internal/services/channel/channel_service.go \
    infra/database/connection.go
```

#### --tags 参数说明

`--tags` 用于编译验证阶段。脚本生成 Mock 后会执行 `go build -tags "..." ./testmocks/...` 验证 Mock 文件能否编译。如果项目依赖 build tags（如 `primary`、`local`），不传 `--tags` 可能导致验证误判。

#### 自动回退机制

脚本默认使用 `-source` 模式生成 Mock。如果生成的 Mock 编译失败（通常因为接口方法签名引用了未导出的类型或变量），脚本会自动：

1. 检测编译错误（`undefined:` 关键字）
2. 提取源文件中的所有接口名
3. 用 reflect 模式重新生成 Mock
4. 再次验证编译
5. 更新源文件中的 `//go:generate` 注释为 reflect 模式

两种模式的区别：
- **-source 模式**：解析源文件 AST，原样复制类型引用 → 跨包时未导出符号会编译失败
- **reflect 模式**：编译后通过反射获取接口信息 → 类型安全，不会引用未导出符号

#### 禁止事项

- ❌ 禁止手动编写 Mock struct 和方法实现
- ❌ 禁止复制粘贴其他 Mock 文件后修改
- ❌ 禁止在测试文件中内联定义 Mock 实现来替代 mockgen 生成的 Mock

## ⚠️ Mock 目录路径规则（强制）

> 路径计算已内置于 `scripts/ensure_mock_generate.sh`，以下规则供理解和审查使用。

**核心规则：Mock 输出路径中禁止出现 `testmocks/internal/`**，否则 Go 编译器会因 `internal` 包可见性约束导致导入失败。

**判定逻辑：**
1. 源码路径包含 `internal/` → Mock 路径 = `testmocks/` + 去掉 `internal/` 后的剩余路径
2. 源码路径不包含 `internal/` → Mock 路径 = `testmocks/` + 完整源码路径
3. `-package` = 目标目录最后一级目录名

**快速对照：**

| 源码路径 | Mock 输出路径 | `-package` |
|---------|-------------|-----------|
| `internal/repo/user.go` | `testmocks/repo/mock_user.go` | `repo` |
| `internal/services/channel/svc.go` | `testmocks/services/channel/mock_svc.go` | `channel` |
| `infra/database/conn.go` | `testmocks/infra/database/mock_conn.go` | `database` |

```
✅ testmocks/repo/mock_user.go                    — 正确
❌ testmocks/internal/repo/mock_user.go            — 编译报错，禁止
```

## gomock 使用模板

### 基本用法

```go
ctrl := gomock.NewController(t)
defer ctrl.Finish()

mockRepo := repo.NewMockUserRepository(ctrl)
mockRepo.EXPECT().
    GetUser(gomock.Any(), int64(123)).
    Return(&User{ID: 123, Name: "张三"}, nil)

svc := NewService(mockRepo)
user, err := svc.GetUser(context.Background(), 123)
```

### 调用次数验证

```go
mockRepo.EXPECT().GetUser(gomock.Any(), int64(123)).Return(&User{}, nil).Times(1)
mockRepo.EXPECT().DeleteUser(gomock.Any(), gomock.Any()).Times(0)       // 期望不被调用
mockRepo.EXPECT().LogEvent(gomock.Any(), gomock.Any()).MinTimes(1)      // 至少一次
```

### 调用顺序验证

```go
gomock.InOrder(
    mockRepo.EXPECT().BeginTx(gomock.Any()).Return(nil),
    mockRepo.EXPECT().CreateUser(gomock.Any(), gomock.Any()).Return(nil),
    mockRepo.EXPECT().Commit(gomock.Any()).Return(nil),
)
```

### DoAndReturn 动态返回

```go
mockRepo.EXPECT().
    GetUser(gomock.Any(), gomock.Any()).
    DoAndReturn(func(ctx context.Context, id int64) (*User, error) {
        if id == 123 {
            return &User{ID: 123, Name: "张三"}, nil
        }
        return nil, errors.New("user not found")
    })
```

### 自定义匹配器

```go
type userMatcher struct{ expectedName string }

func (m *userMatcher) Matches(x interface{}) bool {
    user, ok := x.(*User)
    return ok && user.Name == m.expectedName
}
func (m *userMatcher) String() string {
    return fmt.Sprintf("user with name %s", m.expectedName)
}

mockRepo.EXPECT().CreateUser(gomock.Any(), &userMatcher{expectedName: "张三"}).Return(nil)
```

## 专用 Mock 工具

### sqlmock — 数据库（强制用于 *gorm.DB / *sql.DB / *sqlx.DB）

> ⚠️ **强制规则：当被测 struct 持有 `*gorm.DB` / `*sql.DB` / `*sqlx.DB` 字段时，必须使用 sqlmock，禁止对这些类型使用 mockey.Mock。特别注意：*xdb.XDB底层仍然是`*gorm.DB`、`*sql.DB`、`*sqlx.DB`的一种**

#### GORM + sqlmock 初始化（项目标准模式）

```go
import (
    "github.com/DATA-DOG/go-sqlmock"
    "gorm.io/driver/mysql"
    "gorm.io/gorm"
)

// 推荐抽取为 helper 函数，多个测试复用
func setupGormMock(t *testing.T) (*gorm.DB, sqlmock.Sqlmock, func()) {
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
    cleanup := func() { db.Close() }
    return gormDB, mock, cleanup
}
```

#### 查询场景

```go
func TestOrderSrv_GetOrder(t *testing.T) {
    gormDB, mock, cleanup := setupGormMock(t)
    defer cleanup()

    rows := sqlmock.NewRows([]string{"id", "name", "status"}).
        AddRow(1, "订单A", "paid")
    mock.ExpectQuery("SELECT \\* FROM `orders` WHERE `orders`.`id` = \\?").
        WithArgs(1).
        WillReturnRows(rows)

    srv := &OrderSrv{DB: gormDB}
    order, err := srv.GetOrder(context.Background(), 1)

    assert.NoError(t, err)
    assert.Equal(t, "订单A", order.Name)
    assert.NoError(t, mock.ExpectationsWereMet())
}
```

#### 事务场景（Begin / Commit / Rollback）

```go
func TestOrderSrv_CreateOrder(t *testing.T) {
    gormDB, mock, cleanup := setupGormMock(t)
    defer cleanup()

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

// 事务回滚场景
func TestOrderSrv_CreateOrder_Rollback(t *testing.T) {
    gormDB, mock, cleanup := setupGormMock(t)
    defer cleanup()

    mock.ExpectBegin()
    mock.ExpectExec("INSERT INTO `orders`").
        WithArgs(sqlmock.AnyArg(), sqlmock.AnyArg(), sqlmock.AnyArg()).
        WillReturnError(errors.New("duplicate key"))
    mock.ExpectRollback()

    srv := &OrderSrv{DB: gormDB}
    err := srv.CreateOrder(context.Background(), &Order{Name: "test"})

    assert.Error(t, err)
    assert.NoError(t, mock.ExpectationsWereMet())
}
```

#### 批量查询 / Count 场景

```go
// Count
mock.ExpectQuery("SELECT count\\(\\*\\) FROM `orders`").
    WillReturnRows(sqlmock.NewRows([]string{"count(*)"}).AddRow(42))

// 多行结果
rows := sqlmock.NewRows([]string{"id", "name"}).
    AddRow(1, "订单A").
    AddRow(2, "订单B").
    AddRow(3, "订单C")
mock.ExpectQuery("SELECT \\* FROM `orders` WHERE status = \\?").
    WithArgs("paid").
    WillReturnRows(rows)
```

#### 全局 DB 变量场景

当被测函数通过全局变量（如 `global.DB`）访问数据库时，用 mockey.MockValue 替换全局变量为 sqlmock 实例：

```go
func TestCreateOrder_GlobalDB(t *testing.T) {
    gormDB, mock, cleanup := setupGormMock(t)
    defer cleanup()

    // 替换全局变量为 sqlmock 实例
    mockerDB := mockey.MockValue(&global.DB).To(gormDB)
    defer mockerDB.UnPatch()

    mock.ExpectBegin()
    mock.ExpectExec("INSERT INTO `orders`").
        WillReturnResult(sqlmock.NewResult(1, 1))
    mock.ExpectCommit()

    err := CreateOrder(context.Background(), &Order{Name: "test"})
    assert.NoError(t, err)
    assert.NoError(t, mock.ExpectationsWereMet())
}
```

#### Repo/DAO 层 struct 场景

当被测 struct 的字段是 `*repo.XxxRepo` 类型，且该 repo 嵌入了 `common.Repo[T]` 或内部持有 `*gorm.DB` / `*xdb.XDB` 时，必须通过构造函数注入 sqlmock 实例，禁止使用 mockey.Mock（泛型值接收者方法 mock 不稳定）。

**识别规则：**
- 被测 struct 字段类型为 `*repo.XxxRepo`、`*dao.XxxDao` 等
- 查看该 repo/dao struct 定义，若嵌入了 `common.Repo[T]` 或字段中含 `*gorm.DB` / `*xdb.XDB`，即命中此规则

**注入方式：** 通过 `repo.NewXxxRepo(mockDB)` 构造函数注入 sqlmock 实例

```go
import (
    "testing"
    "github.com/DATA-DOG/go-sqlmock"
    "github.com/stretchr/testify/assert"
    "gorm.io/driver/mysql"
    "gorm.io/gorm"
    "git.tigerbrokers.net/astro/campaign/internal/app/meetup/repo"
    "git.tigerbrokers.net/astro/campaign/internal/conn"
    "git.tigerbrokers.net/astro/campaign/pkg/xdb"
)

// 构造 mock xdb.XDB
func newTestXDB(t *testing.T) (*xdb.XDB, sqlmock.Sqlmock) {
    db, mock, err := sqlmock.New()
    assert.NoError(t, err)
    gormDB, err := gorm.Open(mysql.New(mysql.Config{
        Conn:                      db,
        SkipInitializeWithVersion: true,
    }), &gorm.Config{})
    assert.NoError(t, err)
    return &xdb.XDB{DB: gormDB}, mock
}

// 通过构造函数注入 mock DB 到 repo，再注入到 service
func newTestCollectionService(t *testing.T) (*CollectionService, sqlmock.Sqlmock) {
    mockDB, mock := newTestXDB(t)
    return &CollectionService{
        MeetupRepo:     repo.NewMeetupRepo(conn.ActivityDB(mockDB), conn.ActivitySlaveDB(mockDB)),
        CollectionRepo: repo.NewCollectionRepo(conn.ActivityDB(mockDB), conn.ActivitySlaveDB(mockDB)),
    }, mock
}

// 在测试中使用
func TestCollectionService_GetList(t *testing.T) {
    s, mock := newTestCollectionService(t)

    mock.ExpectQuery("SELECT \\* FROM `meetup`").
        WillReturnRows(sqlmock.NewRows([]string{"id", "number", "status"}).
            AddRow(1, "M001", 1))

    // 执行被测方法...
    assert.NoError(t, mock.ExpectationsWereMet())
}
```

**关键点：**
1. 不要对 repo struct 使用 mockey.Mock，泛型值接收者方法 mock 不稳定
2. 通过 `repo.NewXxxRepo(mockDB)` 构造函数将 sqlmock 实例注入到 repo 内部
3. sqlmock 会拦截所有通过该 GORM 连接发出的 SQL，正常设置 Expect 即可

#### sqlmock 注意事项

1. **正则匹配**：`ExpectQuery` / `ExpectExec` 的参数是正则表达式，特殊字符需转义（`*` → `\\*`，`(` → `\\(`）
2. **GORM 生成的 SQL**：GORM 会用反引号包裹表名和列名（如 `` `orders` ``），正则中需要匹配
3. **参数顺序**：`WithArgs` 的参数顺序必须与 SQL 中的占位符顺序一致
4. **ExpectationsWereMet**：每个测试结束时必须调用，确保所有预期的 SQL 都被执行
5. **sqlmock.AnyArg()**：当参数值不重要时使用，避免过度约束

### miniredis — Redis（强制用于 *redis.Client / *redis.ClusterClient）

> ⚠️ **强制规则：当被测 struct 持有 `*redis.Client` / `*redis.ClusterClient` 字段时，必须使用 miniredis，禁止对这些类型使用 mockey.Mock。**

#### miniredis + go-redis v8 初始化（项目标准模式）

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
```

#### String 操作

```go
func TestCacheSrv_GetString(t *testing.T) {
    client, mr := setupRedisMock(t)
    defer mr.Close()

    // 预设数据
    mr.Set("user:123", `{"id":123,"name":"张三"}`)
    mr.SetTTL("user:123", 60*time.Second)

    srv := &CacheSrv{Redis: client}
    val, err := srv.GetUserCache(context.Background(), 123)

    assert.NoError(t, err)
    assert.Equal(t, "张三", val.Name)
}
```

#### Hash 操作

```go
func TestCacheSrv_GetHash(t *testing.T) {
    client, mr := setupRedisMock(t)
    defer mr.Close()

    // 预设 Hash 数据
    mr.HSet("order:123", "status", "paid")
    mr.HSet("order:123", "amount", "100.50")

    srv := &CacheSrv{Redis: client}
    status, err := srv.GetOrderStatus(context.Background(), 123)

    assert.NoError(t, err)
    assert.Equal(t, "paid", status)
}
```

#### List / Set / Sorted Set 操作

```go
// List
mr.Lpush("queue:tasks", "task1", "task2", "task3")

// Set
mr.SAdd("online:users", "user1", "user2")
members, _ := mr.SMembers("online:users")

// Sorted Set
mr.ZAdd("leaderboard", 100, "player1")
mr.ZAdd("leaderboard", 200, "player2")
```

#### Key 不存在场景（测试缓存未命中）

```go
{
    name: "缓存未命中_返回空",
    setup: func(mr *miniredis.Miniredis) {
        // 不预设任何数据，模拟 key 不存在
    },
    wantErr: true, // redis.Nil error
},
```

#### 全局 Redis 变量场景

```go
func TestGetCache_GlobalRedis(t *testing.T) {
    client, mr := setupRedisMock(t)
    defer mr.Close()

    mockerRedis := mockey.MockValue(&global.Redis).To(client)
    defer mockerRedis.UnPatch()

    mr.Set("key", "value")

    result, err := GetCache(context.Background(), "key")
    assert.NoError(t, err)
    assert.Equal(t, "value", result)
}
```

#### miniredis 注意事项

1. **必须 defer mr.Close()**：每个测试结束时关闭 miniredis 实例
2. **时间控制**：`mr.FastForward(duration)` 可以模拟时间流逝，测试 TTL 过期
3. **错误模拟**：`mr.SetError("ERR some error")` 可以让所有命令返回错误
4. **并发安全**：miniredis 是并发安全的，但建议每个测试用例创建独立实例
5. **go-redis v8 context**：go-redis v8 的所有方法第一个参数是 `context.Context`

### httptest — HTTP

```go
server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(http.StatusOK)
    w.Write([]byte(`{"id":123,"name":"张三"}`))
}))
defer server.Close()

client := NewClient(server.URL)
```

## 核心原则

1. **所有接口 Mock 必须通过 `scripts/ensure_mock_generate.sh` 脚本生成**，禁止手动编写
2. **EXPECT 明确指定参数**，避免全部用 `gomock.Any()`
3. **必须 `defer ctrl.Finish()`**，验证所有期望被满足
4. **专用工具优先**：数据库用 sqlmock、Redis 用 miniredis、HTTP 用 httptest
5. **Mock 目录禁止 internal 子目录**，路径规则已内置于脚本
