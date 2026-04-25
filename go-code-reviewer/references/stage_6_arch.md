# 阶段6：架构设计审核

> **重要依赖**：本阶段严重依赖阶段1中 go-code-analyzer 的输出结果，特别是函数调用链（call chain）和包依赖图（dependency graph）。审核前务必确认已获取这些信息，否则架构层面的判断将缺乏全局视角。

## 输入
- 阶段1的上下文摘要（特别是 go-code-analyzer 的调用链和依赖图）
- 待审核代码

## 严格度适配

| 严格度 | 检查范围 |
|--------|----------|
| strict | 所有架构检查，包括建议级别的优化（如包拆分建议、接口精简） |
| normal | 常见架构问题（分层违规、依赖方向、职责不清） |
| relaxed | 仅检查严重架构问题（循环依赖、明显的分层违规） |

---

## 检查项

### arch/package-structure — 包结构合理性

- **严重程度**：🟡警告
- **描述**：包应按业务职责划分，而非按技术类型划分；包命名应清晰简短，避免出现"万能包"

**检查要点**：
1. 包是否按职责划分（而非按类型：不要 `models/`, `controllers/`, `utils/`）
2. 是否存在过大的"万能包"（一个包超过20个文件需关注）
3. 包命名是否清晰简短（避免 `common`, `base`, `misc`, `helper`, `util`）
4. 包内文件是否围绕同一主题（而非杂乱堆放不相关功能）

> **提示**：利用阶段1的依赖图判断包之间的耦合程度，高扇入/扇出的包需要重点关注。

**反例**：
```go
// 问题1：按类型划分包 — 导致修改一个功能需要跨多个包
project/
├── models/
│   ├── user.go
│   ├── order.go
│   └── product.go
├── controllers/
│   ├── user.go
│   ├── order.go
│   └── product.go
├── services/
│   ├── user.go
│   ├── order.go
│   └── product.go
└── utils/
    ├── string.go
    ├── time.go
    ├── http.go
    └── ... (20+ 不相关的工具函数)

// 问题2：万能包 — common包被所有人依赖，改动影响面巨大
package common

func FormatTime(t time.Time) string { ... }
func ParseJSON(data []byte) (map[string]interface{}, error) { ... }
func SendEmail(to, subject, body string) error { ... }
func ValidatePhone(phone string) bool { ... }
// 完全不相关的功能堆在一起

// 问题3：含糊的包名
package base   // base是什么？
package misc   // 杂项？
package helper // 帮助什么？
```

**正确做法**：
```go
// 修复1：按业务领域划分包
project/
├── user/
│   ├── handler.go
│   ├── service.go
│   ├── repository.go
│   └── user.go        // 领域模型
├── order/
│   ├── handler.go
│   ├── service.go
│   ├── repository.go
│   └── order.go
└── pkg/
    ├── timeutil/       // 明确的工具包，职责单一
    │   └── format.go
    └── httputil/
        └── response.go

// 修复2：拆分万能包为职责明确的小包
package timeutil  // 只做时间相关
func Format(t time.Time) string { ... }

package jsonutil  // 只做JSON相关
func Parse(data []byte) (map[string]interface{}, error) { ... }

package notify    // 通知相关
func SendEmail(to, subject, body string) error { ... }
```

---

### arch/interface-design — 接口抽象

- **严重程度**：🟡警告
- **描述**：接口设计应遵循Go惯例——小接口、消费方定义、避免过度抽象或抽象不足

**检查要点**：
1. 过度抽象：只有一个实现的interface（除非用于测试mock或跨包边界）
2. 抽象不足：直接依赖具体实现而非interface（导致难以测试和替换）
3. 接口应在消费方定义（Go惯例），而非在提供方
4. 接口过大：超过5个方法的接口考虑拆分（接口隔离原则）

**反例**：
```go
// 问题1：过度抽象 — 只有一个实现，且不用于测试
// animal.go
type Animal interface {
    Speak() string
}

// dog.go
type Dog struct{}
func (d Dog) Speak() string { return "woof" }

// 整个项目只有Dog实现了Animal，且没有mock需求

// 问题2：抽象不足 — 直接依赖具体实现，无法替换和测试
type OrderService struct {
    repo *MySQLOrderRepo // 直接依赖具体MySQL实现
}

func (s *OrderService) Create(order Order) error {
    return s.repo.Insert(order) // 测试时必须连真实数据库
}

// 问题3：接口在提供方定义（Java风格，非Go惯例）
// repo/interfaces.go — 提供方定义了接口
package repo

type UserRepository interface {
    FindByID(id int) (*User, error)
    Save(user *User) error
    Delete(id int) error
    List(filter Filter) ([]*User, error)
    Count(filter Filter) (int, error)
    // ... 更多方法
}

type mysqlUserRepo struct{ db *sql.DB }
// 实现所有方法...

// 问题4：接口过大 — 消费方被迫依赖不需要的方法
type DataStore interface {
    GetUser(id int) (*User, error)
    SaveUser(u *User) error
    DeleteUser(id int) error
    GetOrder(id int) (*Order, error)
    SaveOrder(o *Order) error
    DeleteOrder(id int) error
    GetProduct(id int) (*Product, error)
    SaveProduct(p *Product) error
    // 8个方法，混合了多个领域
}
```

**正确做法**：
```go
// 修复1：去掉不必要的接口，直接使用具体类型
type Dog struct{}
func (d Dog) Speak() string { return "woof" }
// 直接使用Dog，不需要Animal接口

// 修复2：通过接口解耦，便于测试
type OrderRepository interface {
    Insert(order Order) error
}

type OrderService struct {
    repo OrderRepository // 依赖接口
}

func (s *OrderService) Create(order Order) error {
    return s.repo.Insert(order) // 测试时可注入mock
}

// 修复3：接口在消费方定义（Go惯例）
// service/user.go — 消费方只定义自己需要的方法
package service

type UserFinder interface {
    FindByID(id int) (*User, error)
}

type UserService struct {
    finder UserFinder // 只依赖需要的能力
}

// 修复4：拆分大接口为小接口
type UserReader interface {
    GetUser(id int) (*User, error)
}

type UserWriter interface {
    SaveUser(u *User) error
    DeleteUser(id int) error
}

// 消费方只依赖需要的接口
type UserProfileService struct {
    reader UserReader // 只需要读
}
```

---

### arch/dependency-direction — 依赖方向

- **严重程度**：🔴严重（循环依赖）/ 🟡警告（其他）
- **描述**：依赖应单向流动，高层依赖低层，禁止循环依赖和反向调用

**检查要点**：
1. 循环依赖（package A imports B, B imports A）
2. 下层调用上层（DAO层调用Service层）
3. 违反依赖倒置原则（高层模块依赖低层模块的具体实现）

> **提示**：利用阶段1的依赖图直接检测循环依赖路径。如果 go-code-analyzer 已标记循环依赖，此处直接引用其结果。

**反例**：
```go
// 问题1：循环依赖 — A imports B, B imports A
// package user
package user

import "myapp/order" // user -> order

type User struct{ ID int }

func (u *User) Orders() []order.Order {
    return order.FindByUserID(u.ID)
}

// package order
package order

import "myapp/user" // order -> user — 循环！

type Order struct{ UserID int }

func FindByUserID(uid int) []Order { ... }
func (o *Order) Owner() *user.User {
    return user.FindByID(o.UserID)
}

// 问题2：DAO层调用Service层
// repo/user_repo.go
package repo

import "myapp/service" // DAO层反向依赖Service层

func (r *UserRepo) SaveWithNotify(u *User) error {
    if err := r.db.Save(u); err != nil {
        return err
    }
    service.NotifyUserCreated(u.ID) // DAO不应调用Service
    return nil
}

// 问题3：高层直接依赖低层具体实现
// service/order_service.go
package service

import "myapp/repo" // 直接import具体的repo包

type OrderService struct {
    repo *repo.MySQLOrderRepo // 依赖具体MySQL实现
}
```

**正确做法**：
```go
// 修复1：通过接口打破循环依赖
// package user
package user

type OrderFinder interface {
    FindByUserID(uid int) ([]Order, error)
}

type User struct{ ID int }
type Service struct {
    orders OrderFinder // 通过接口依赖，不直接import order包
}

// package order
package order

type Order struct{ UserID int }

func (r *Repo) FindByUserID(uid int) ([]Order, error) { ... }
// order包不再import user包

// 修复2：DAO层只做数据访问，通知逻辑上移到Service层
// repo/user_repo.go
package repo

func (r *UserRepo) Save(u *User) error {
    return r.db.Save(u) // 只做数据操作
}

// service/user_service.go
package service

func (s *UserService) CreateUser(u *User) error {
    if err := s.repo.Save(u); err != nil {
        return err
    }
    s.notifier.NotifyUserCreated(u.ID) // 通知逻辑在Service层
    return nil
}

// 修复3：通过接口实现依赖倒置
// service/order_service.go
package service

type OrderRepository interface { // 在Service层定义接口
    Insert(order Order) error
    FindByID(id int) (*Order, error)
}

type OrderService struct {
    repo OrderRepository // 依赖抽象，不依赖具体实现
}
```

---

### arch/single-responsibility — 职责划分

- **严重程度**：🟡警告
- **描述**：每个struct/函数应只承担单一职责，避免God Object和过长函数

**检查要点**：
1. 单一职责原则：一个struct/函数只做一件事
2. 函数过长（>100行需关注，>200行必须拆分）
3. God Object：一个struct承担过多职责（字段过多、方法过多）
4. 一个函数内混合多个抽象层次（如同时处理HTTP解析和业务逻辑）

**反例**：
```go
// 问题1：God Object — 一个struct做了所有事情
type AppManager struct {
    db        *sql.DB
    cache     *redis.Client
    mailer    *smtp.Client
    logger    *log.Logger
    config    *Config
    templates *template.Template
    // ... 20+ 字段
}

func (m *AppManager) CreateUser(w http.ResponseWriter, r *http.Request) { ... }
func (m *AppManager) SendEmail(to, subject string) error { ... }
func (m *AppManager) ClearCache(key string) error { ... }
func (m *AppManager) RenderTemplate(name string, data interface{}) error { ... }
func (m *AppManager) HandleWebhook(w http.ResponseWriter, r *http.Request) { ... }
// ... 50+ 方法，涵盖用户管理、邮件、缓存、模板、webhook等

// 问题2：函数过长，混合多个抽象层次
func ProcessOrder(w http.ResponseWriter, r *http.Request) {
    // 1. HTTP解析（20行）
    var req OrderRequest
    body, err := io.ReadAll(r.Body)
    if err != nil { ... }
    if err := json.Unmarshal(body, &req); err != nil { ... }
    // 参数校验...

    // 2. 业务逻辑（80行）
    user, err := db.Query("SELECT * FROM users WHERE id = ?", req.UserID)
    // 库存检查...
    // 价格计算...
    // 优惠券核销...

    // 3. 数据持久化（30行）
    tx, _ := db.Begin()
    tx.Exec("INSERT INTO orders ...")
    tx.Exec("UPDATE inventory ...")
    tx.Commit()

    // 4. 发送通知（20行）
    smtp.SendMail(...)

    // 5. 响应（10行）
    w.WriteHeader(200)
    json.NewEncoder(w).Encode(resp)
    // 总计 160+ 行，混合了5个不同层次的逻辑
}
```

**正确做法**：
```go
// 修复1：拆分God Object为职责明确的组件
type UserService struct {
    repo     UserRepository
    notifier Notifier
}

type CacheService struct {
    client *redis.Client
}

type TemplateRenderer struct {
    templates *template.Template
}

// 每个struct只关注自己的领域

// 修复2：按抽象层次拆分函数
// Handler层：只做HTTP相关
func (h *OrderHandler) Create(w http.ResponseWriter, r *http.Request) {
    var req OrderRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, "invalid request", http.StatusBadRequest)
        return
    }

    order, err := h.service.CreateOrder(r.Context(), req)
    if err != nil {
        handleError(w, err)
        return
    }

    json.NewEncoder(w).Encode(order)
}

// Service层：业务逻辑
func (s *OrderService) CreateOrder(ctx context.Context, req OrderRequest) (*Order, error) {
    if err := s.validateOrder(req); err != nil {
        return nil, err
    }
    order, err := s.repo.Insert(ctx, req.ToOrder())
    if err != nil {
        return nil, fmt.Errorf("insert order: %w", err)
    }
    s.notifier.OrderCreated(ctx, order)
    return order, nil
}
```

---

### arch/layer-violation — 分层规范

- **严重程度**：🟡警告
- **描述**：各层应严格遵守职责边界，不越界操作

**检查要点**：
1. Handler层：只做参数校验、请求解析、响应封装，不含业务逻辑
2. Service层：承载业务逻辑，不直接操作数据库（通过DAO/Repository）
3. DAO层：只做数据访问，不含业务判断
4. 各层是否越界（如Handler直接操作数据库、DAO包含业务逻辑）

> **提示**：结合阶段1的调用链分析，检查是否存在跨层调用（如Handler直接调用DAO跳过Service）。

**反例**：
```go
// 问题1：Handler层包含业务逻辑
func (h *UserHandler) Create(w http.ResponseWriter, r *http.Request) {
    var req CreateUserReq
    json.NewDecoder(r.Body).Decode(&req)

    // 业务逻辑不应在Handler层
    if req.Age < 18 {
        http.Error(w, "must be 18+", 400)
        return
    }
    hashedPwd, _ := bcrypt.GenerateFromPassword([]byte(req.Password), 14)
    user := &User{
        Name:     req.Name,
        Password: string(hashedPwd),
        Role:     "member",
        Credits:  100, // 新用户赠送积分 — 这是业务规则
    }

    // Handler直接操作数据库 — 跳过了Service层
    h.db.Exec("INSERT INTO users (name, password, role, credits) VALUES (?, ?, ?, ?)",
        user.Name, user.Password, user.Role, user.Credits)

    w.WriteHeader(201)
}

// 问题2：Service层直接写SQL
func (s *OrderService) GetPendingOrders(userID int) ([]*Order, error) {
    rows, err := s.db.Query(
        "SELECT * FROM orders WHERE user_id = ? AND status = 'pending' ORDER BY created_at DESC",
        userID,
    ) // Service层不应直接写SQL
    // ...
}

// 问题3：DAO层包含业务判断
func (r *OrderRepo) CreateOrder(order *Order) error {
    // 业务规则不应在DAO层
    if order.Amount > 10000 {
        order.Status = "pending_review" // 大额订单需审核 — 这是业务逻辑
    } else {
        order.Status = "confirmed"
    }
    return r.db.Create(order).Error
}
```

**正确做法**：
```go
// 修复1：Handler只做解析和校验格式，业务逻辑交给Service
func (h *UserHandler) Create(w http.ResponseWriter, r *http.Request) {
    var req CreateUserReq
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, "invalid json", 400)
        return
    }
    if err := req.Validate(); err != nil { // 只做格式校验
        http.Error(w, err.Error(), 400)
        return
    }

    user, err := h.service.CreateUser(r.Context(), req) // 业务逻辑委托给Service
    if err != nil {
        handleError(w, err)
        return
    }

    w.WriteHeader(201)
    json.NewEncoder(w).Encode(user)
}

// 修复2：Service层通过Repository接口访问数据
func (s *OrderService) GetPendingOrders(ctx context.Context, userID int) ([]*Order, error) {
    return s.repo.FindByUserAndStatus(ctx, userID, StatusPending)
}

// 修复3：DAO层只做数据操作，业务判断上移到Service
func (r *OrderRepo) Insert(ctx context.Context, order *Order) error {
    return r.db.WithContext(ctx).Create(order).Error // 只做数据插入
}

// 业务逻辑在Service层
func (s *OrderService) CreateOrder(ctx context.Context, req CreateOrderReq) (*Order, error) {
    order := req.ToOrder()
    if order.Amount > 10000 {
        order.Status = StatusPendingReview // 业务规则在Service层
    } else {
        order.Status = StatusConfirmed
    }
    return order, s.repo.Insert(ctx, order)
}
```

---

### arch/error-propagation — 错误传播

- **严重程度**：🟡警告
- **描述**：错误应在正确的层处理和包装，避免跨层泄露内部实现细节

**检查要点**：
1. 错误是否在正确的层处理（业务错误在Service层、数据错误在DAO层）
2. 是否存在跨层错误泄露（DAO层的SQL错误直接返回给前端）
3. 错误是否正确包装（每层添加上下文信息）
4. 是否区分了业务错误和系统错误（业务错误返回4xx，系统错误返回5xx）

**反例**：
```go
// 问题1：SQL错误直接泄露给前端
func (h *UserHandler) Get(w http.ResponseWriter, r *http.Request) {
    user, err := h.repo.FindByID(id) // 直接调用repo
    if err != nil {
        // SQL错误直接暴露给客户端：
        // "Error 1045 (28000): Access denied for user 'root'@'localhost'"
        http.Error(w, err.Error(), 500)
        return
    }
    json.NewEncoder(w).Encode(user)
}

// 问题2：DAO层的错误未包装，调用链丢失上下文
func (r *UserRepo) FindByID(id int) (*User, error) {
    var user User
    err := r.db.Where("id = ?", id).First(&user).Error
    return &user, err // 直接返回gorm错误，无上下文
}

func (s *UserService) GetUser(id int) (*User, error) {
    return s.repo.FindByID(id) // 继续透传，无上下文
}

// 最终错误信息："record not found" — 不知道是哪个环节、查什么

// 问题3：所有错误都返回500
func (h *OrderHandler) Create(w http.ResponseWriter, r *http.Request) {
    order, err := h.service.CreateOrder(r.Context(), req)
    if err != nil {
        http.Error(w, "internal error", 500) // 库存不足也返回500？
        return
    }
}
```

**正确做法**：
```go
// 修复1+2：每层包装错误，添加上下文
// 定义业务错误类型
var (
    ErrUserNotFound    = errors.New("user not found")
    ErrInsufficientStock = errors.New("insufficient stock")
)

// DAO层：包装数据访问错误，转换为业务语义
func (r *UserRepo) FindByID(ctx context.Context, id int) (*User, error) {
    var user User
    err := r.db.WithContext(ctx).Where("id = ?", id).First(&user).Error
    if err != nil {
        if errors.Is(err, gorm.ErrRecordNotFound) {
            return nil, ErrUserNotFound // 转换为业务错误
        }
        return nil, fmt.Errorf("query user by id %d: %w", id, err) // 包装系统错误
    }
    return &user, nil
}

// Service层：处理业务逻辑错误
func (s *UserService) GetUser(ctx context.Context, id int) (*User, error) {
    user, err := s.repo.FindByID(ctx, id)
    if err != nil {
        return nil, fmt.Errorf("get user: %w", err) // 添加Service层上下文
    }
    return user, nil
}

// 修复3：Handler层区分错误类型，返回合适的HTTP状态码
func (h *OrderHandler) Create(w http.ResponseWriter, r *http.Request) {
    order, err := h.service.CreateOrder(r.Context(), req)
    if err != nil {
        switch {
        case errors.Is(err, ErrUserNotFound):
            http.Error(w, "user not found", 404)
        case errors.Is(err, ErrInsufficientStock):
            http.Error(w, "insufficient stock", 409) // 业务冲突
        default:
            log.Printf("create order: %v", err) // 记录完整错误
            http.Error(w, "internal error", 500) // 不泄露内部细节
        }
        return
    }
    w.WriteHeader(201)
    json.NewEncoder(w).Encode(order)
}
```

---

## 输出格式

对每个发现的问题，输出：

```
### [check-id] 问题简述
- 严重程度：🔴严重 / 🟡警告
- 位置：`file:line`
- 问题：具体描述
- 依赖图参考：（引用阶段1 go-code-analyzer 的相关调用链或依赖关系）
- 修复建议：具体修复方案
```
