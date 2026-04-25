# 阶段2：代码规范审核

## 目标

基于阶段1的上下文摘要，对待审核代码进行 Go 语言代码规范检查。重点关注命名、惯用写法、错误处理约定、注释、包组织和格式化等方面。

## 输入

- 阶段1输出的上下文摘要（项目结构、模块职责、依赖关系等）
- 待审核的代码变更（diff 或完整文件）

## 严格度适配

根据用户指定的严格度级别调整检查范围：

| 严格度 | 检查范围 | 报告级别 |
|--------|---------|---------|
| **strict** | 所有规则均检查 | 🔵建议 及以上全部报告 |
| **normal**（默认） | 所有规则均检查 | 仅报告 🟡警告 及以上 |
| **relaxed** | 仅检查关键规则（命名、错误处理） | 仅报告 🟡警告 及以上 |

---

## 检查项

### `style/naming` — 命名规范

**严重度：** 🟡警告（导出符号）/ 🔵建议（未导出符号）

Go 命名遵循 MixedCaps / mixedCaps 风格，不使用下划线分隔单词。

#### 规则

1. **驼峰命名**：使用 MixedCaps（导出）或 mixedCaps（未导出），禁止 snake_case
2. **缩写词全大写**：常见缩写保持全大写或全小写，不混合大小写
3. **导出 vs 未导出**：导出命名首字母大写，未导出首字母小写
4. **receiver 命名**：短小一致，通常 1-2 个字母，基于类型名缩写；禁止使用 `this`、`self`

#### 正例

```go
// 驼峰命名
type UserService struct{}
func getUserByID(id int) {}

// 缩写词全大写
type HTTPClient struct{}
var userID string
var xmlHTTPRequest *Request
func ServeHTTP(w http.ResponseWriter, r *http.Request) {}

// receiver 命名：短小一致
func (s *UserService) FindByID(id int) (*User, error) {}
func (c *HTTPClient) Do(req *Request) (*Response, error) {}
```

#### 反例

```go
// ✗ snake_case 命名
type user_service struct{}
func get_user_by_id(id int) {}

// ✗ 缩写词大小写混合
type HttpClient struct{}   // 应为 HTTPClient
var UserId string          // 应为 UserID
var xmlHttpRequest *Request // 应为 xmlHTTPRequest

// ✗ receiver 使用 this/self 或过长命名
func (this *UserService) FindByID(id int) (*User, error) {}
func (self *HTTPClient) Do(req *Request) (*Response, error) {}
func (userService *UserService) Delete(id int) error {}
```

---

### `style/idiomatic-go` — Go 惯用写法

**严重度：** 🔵建议

遵循 Go 社区公认的惯用模式，写出地道的 Go 代码。

#### 规则

1. **error 处理扁平化**：使用 `if err != nil { return err }` 提前返回，避免深层嵌套
2. **nil slice 声明**：空 slice 用 `var s []T`（nil slice），除非明确需要非 nil 空 slice 才用 `make`
3. **接口命名用 -er 后缀**：单方法接口以方法名 + er 命名（Reader, Writer, Closer）
4. **单方法接口优先**：接口应尽量小，优先定义单方法接口
5. **标准 error 创建**：使用 `errors.New` 和 `fmt.Errorf`，不要为简单错误自定义类型

#### 正例

```go
// error 处理：提前返回，保持主逻辑在左侧
func processUser(id int) error {
    user, err := findUser(id)
    if err != nil {
        return fmt.Errorf("find user: %w", err)
    }

    if err := validate(user); err != nil {
        return fmt.Errorf("validate user: %w", err)
    }

    return save(user)
}

// nil slice 声明
var users []User // nil slice，json.Marshal 输出 null
// 需要非 nil 空 slice 时（如 JSON 输出 []）：
users := make([]User, 0)

// 单方法接口 + -er 后缀
type Reader interface {
    Read(p []byte) (n int, err error)
}

type Validator interface {
    Validate() error
}

// 标准 error 创建
var ErrNotFound = errors.New("user not found")
return fmt.Errorf("query user %d: %w", id, err)
```

#### 反例

```go
// ✗ 深层嵌套的 error 处理
func processUser(id int) error {
    user, err := findUser(id)
    if err == nil {
        err = validate(user)
        if err == nil {
            err = save(user)
            if err != nil {
                return fmt.Errorf("save: %w", err)
            }
        } else {
            return fmt.Errorf("validate: %w", err)
        }
    } else {
        return fmt.Errorf("find: %w", err)
    }
    return nil
}

// ✗ 不必要的 make 初始化空 slice
s := make([]string, 0) // 如果不需要非 nil，应使用 var s []string

// ✗ 过大的接口
type UserManager interface {
    Create(user User) error
    Update(user User) error
    Delete(id int) error
    Find(id int) (*User, error)
    List() ([]User, error)
}

// ✗ 为简单错误自定义类型
type SimpleError struct {
    Message string
}
func (e *SimpleError) Error() string { return e.Message }
// 应直接使用：errors.New("something failed")
```

---

### `style/error-naming` — 错误命名约定

**严重度：** 🟡警告

Go 社区对错误变量和错误类型有明确的命名约定。

#### 规则

1. **错误变量**：以 `Err` 为前缀，如 `ErrNotFound`、`ErrTimeout`
2. **错误类型**：以 `Error` 为后缀，如 `ValidationError`、`NotFoundError`
3. **错误字符串**：小写开头，不以标点结尾（因为常被包装拼接）

#### 正例

```go
// 错误变量：Err 前缀
var (
    ErrNotFound   = errors.New("not found")
    ErrTimeout    = errors.New("operation timed out")
    ErrPermission = errors.New("permission denied")
)

// 错误类型：Error 后缀
type ValidationError struct {
    Field   string
    Message string
}

func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation failed on field %s: %s", e.Field, e.Message)
}

// 错误字符串：小写开头，无结尾标点
return fmt.Errorf("connect to database: %w", err)
```

#### 反例

```go
// ✗ 错误变量命名不规范
var NotFoundErr = errors.New("not found")       // 应为 ErrNotFound
var TimeoutError = errors.New("timeout")         // 变量应为 ErrTimeout（Error 后缀用于类型）
var ERROR_PERMISSION = errors.New("no permission") // 不要用全大写 snake_case

// ✗ 错误类型命名不规范
type ErrValidation struct { // 类型应为 ValidationError，Err 前缀用于变量
    Field string
}

// ✗ 错误字符串格式不规范
return fmt.Errorf("Connect to database: %w", err)  // 不要大写开头
return fmt.Errorf("connection failed.") // 不要以标点结尾
```

---

### `style/comments` — 注释规范

**严重度：** 🟡警告（导出符号缺少注释）/ 🔵建议（注释格式）

Go 的文档注释是代码的一等公民，godoc 工具直接从注释生成文档。

#### 规则

1. **导出符号必须有注释**：所有导出的类型、函数、常量、变量都应有 doc comment
2. **注释以符号名开头**：`// SymbolName does something.` 格式
3. **完整句子**：注释应为完整的英文/中文句子，以句号结尾
4. **包注释**：每个包应在 package 声明前有包级别的 doc comment（或独立 `doc.go` 文件）

#### 正例

```go
// Package user provides user management functionality including
// creation, authentication, and profile management.
package user

// MaxRetries is the maximum number of retry attempts for failed operations.
const MaxRetries = 3

// ErrNotFound is returned when a requested user does not exist.
var ErrNotFound = errors.New("user not found")

// User represents a registered user in the system.
type User struct {
    ID    int
    Name  string
    Email string
}

// UserService handles user-related business logic.
type UserService struct {
    repo UserRepository
}

// FindByID retrieves a user by their unique identifier.
// It returns ErrNotFound if no user exists with the given ID.
func (s *UserService) FindByID(id int) (*User, error) {
    // ...
}
```

#### 反例

```go
// ✗ 缺少包注释
package user

// ✗ 注释未以符号名开头
// this service handles users
type UserService struct{}

// ✗ 注释不是完整句子
// find user by id
func (s *UserService) FindByID(id int) (*User, error) {}

// ✗ 导出常量缺少注释
const MaxRetries = 3

// ✗ 注释与符号名不匹配
// Service is the main handler.
type UserService struct{}
```

---

### `style/imports` — 包导入组织

**严重度：** 🔵建议

import 语句的组织影响代码可读性和一致性。

#### 规则

1. **三段分组**：标准库 / 第三方包 / 项目内部包，各组之间用空行分隔
2. **包命名**：小写、无下划线、简短有意义
3. **禁止 dot import**：不要使用 `. "pkg"` 形式（测试中也应避免）
4. **blank import 限制**：仅在驱动注册等场景使用 `_ "pkg/driver"` 模式，且应加注释说明

#### 正例

```go
import (
    // 标准库
    "context"
    "fmt"
    "net/http"

    // 第三方包
    "github.com/gin-gonic/gin"
    "go.uber.org/zap"

    // 项目内部包
    "myproject/internal/model"
    "myproject/internal/service"
)

// blank import 带注释说明
import (
    "database/sql"

    _ "github.com/go-sql-driver/mysql" // MySQL driver registration
)
```

#### 反例

```go
// ✗ 未分组，混合排列
import (
    "myproject/internal/model"
    "fmt"
    "github.com/gin-gonic/gin"
    "net/http"
    "myproject/internal/service"
    "go.uber.org/zap"
)

// ✗ dot import
import (
    . "github.com/onsi/gomega"
)

// ✗ blank import 无注释
import (
    _ "github.com/go-sql-driver/mysql"
)

// ✗ 包命名不规范
package user_service  // 应为 userservice 或 user
package UserRepo      // 应为 userrepo 或 repo
```

---

### `style/formatting` — 代码格式

**严重度：** 🔵建议

代码格式一致性是 Go 项目的基本要求。

#### 规则

1. **gofmt/goimports 一致性**：所有代码必须通过 `gofmt` 格式化，推荐使用 `goimports`
2. **行长度**：超过 120 字符的行应关注可读性，考虑合理换行
3. **函数长度**：超过 80 行的函数应考虑拆分为更小的函数
4. **空行使用**：函数内用空行分隔逻辑段落，但避免多余空行

#### 正例

```go
// 合理的行长度与换行
func (s *UserService) CreateUser(
    ctx context.Context,
    name string,
    email string,
    role Role,
) (*User, error) {
    // 验证输入
    if name == "" {
        return nil, ErrEmptyName
    }

    // 创建用户
    user := &User{
        Name:  name,
        Email: email,
        Role:  role,
    }

    // 持久化
    if err := s.repo.Save(ctx, user); err != nil {
        return nil, fmt.Errorf("save user: %w", err)
    }

    return user, nil
}

// 函数职责单一，长度适中
func (s *UserService) validate(user *User) error {
    if user.Name == "" {
        return ErrEmptyName
    }
    if !isValidEmail(user.Email) {
        return ErrInvalidEmail
    }
    return nil
}
```

#### 反例

```go
// ✗ 超长行，可读性差
func (s *UserService) CreateUserWithAllDetails(ctx context.Context, name string, email string, role Role, department string, manager string, startDate time.Time) (*User, error) {
    return nil, nil
}

// ✗ 函数过长（此处省略，但超过 80 行的函数应拆分）
func (s *UserService) ProcessEverything() error {
    // ... 100+ 行的业务逻辑 ...
    // 应拆分为 validate(), transform(), persist() 等子函数
}

// ✗ 多余空行
func doSomething() {

    x := 1


    y := 2

}

// ✗ 未经 gofmt 格式化（缩进不一致）
func badFormat() {
  x:=1
    y :=2
  if x==y{
  fmt.Println("equal")
  }
}
```

---

## 输出格式

每个发现的问题按以下格式输出：

```
### [规则ID] 问题简述

**严重度：** 🟡警告 / 🔵建议
**文件：** `path/to/file.go:行号`

**问题描述：**
简要说明违反了什么规则以及为什么需要修改。

**当前代码：**
​```go
// 有问题的代码片段
​```

**建议修改：**
​```go
// 修改后的代码片段
​```
```

## 阶段输出

完成所有检查项后，输出阶段2的汇总：

```
## 阶段2 汇总：代码规范审核

- 检查规则数：N
- 发现问题数：N（🟡警告 x个，🔵建议 x个）
- 严格度：strict / normal / relaxed

### 问题列表
（按严重度排序的问题摘要）
```

将汇总与详细发现一起传递给阶段3。
