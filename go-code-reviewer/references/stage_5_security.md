# 阶段5：安全漏洞审核

## 目标
识别代码中的安全漏洞，包括资源安全、输入安全、数据安全和权限安全，防止注入攻击、信息泄露、越权访问等安全风险。

## 输入
- 阶段1的上下文摘要（项目类型、对外暴露的接口、依赖的外部服务）
- 阶段3的发现（资源泄漏等，本阶段进一步评估安全影响）
- 待审核代码

## 与阶段3的协作
阶段3发现"资源未释放"，阶段5进一步判断"该泄漏能否被外部攻击者利用来打垮服务"。阶段5可引用阶段3的发现做深入安全分析。

例如：阶段3报告 `bug/resource-leak`（goroutine未退出），阶段5进一步分析该goroutine是否由外部请求触发，若是则升级为 `security/goroutine-dos`。

## 严格度适配

| 严格度 | 范围 |
|--------|------|
| **strict** | 所有安全检查，包括低风险项（CORS、日志泄露、弱加密等） |
| **normal** | 常见安全问题和中高风险项 |
| **relaxed** | 仅检查高危项（注入、硬编码密钥、缺少鉴权） |

---

## 检查项

---

### 资源安全

---

#### security/goroutine-dos — goroutine泄漏导致DoS

- **严重程度**：🔴严重
- **描述**：goroutine泄漏可被外部触发，每个请求创建goroutine但无上限，攻击者可发送大量请求耗尽内存

**检查要点**：
1. 每个请求创建goroutine但无并发上限
2. 缺少semaphore或worker pool限制
3. goroutine无退出条件，外部可持续触发创建

**反例**：

```go
// BAD: 每个请求无限制创建goroutine，攻击者可发送大量请求耗尽内存
func handleRequest(w http.ResponseWriter, r *http.Request) {
    go func() { // 无上限，无退出控制
        result := heavyComputation(r.URL.Query().Get("input"))
        storeResult(result)
    }()
    w.WriteHeader(http.StatusAccepted)
}
```

**修复建议**：

```go
// GOOD: 使用semaphore限制并发goroutine数量
var sem = make(chan struct{}, 100) // 最多100个并发

func handleRequest(w http.ResponseWriter, r *http.Request) {
    select {
    case sem <- struct{}{}:
        go func() {
            defer func() { <-sem }()
            result := heavyComputation(r.URL.Query().Get("input"))
            storeResult(result)
        }()
        w.WriteHeader(http.StatusAccepted)
    default:
        http.Error(w, "too many requests", http.StatusTooManyRequests)
    }
}
```

---

#### security/resource-exhaustion — 资源耗尽

- **严重程度**：🔴严重
- **描述**：文件/连接未释放可导致fd耗尽；缺少请求体大小限制，大payload可导致OOM

**检查要点**：
1. 文件句柄、网络连接未及时关闭导致fd耗尽
2. 缺少请求体大小限制（`http.MaxBytesReader`）
3. 无限制读取外部输入到内存

**反例**：

```go
// BAD: 未限制请求体大小，攻击者可发送超大payload导致OOM
func uploadHandler(w http.ResponseWriter, r *http.Request) {
    body, err := io.ReadAll(r.Body) // 可能读取数GB数据
    if err != nil {
        http.Error(w, err.Error(), 500)
        return
    }
    processBody(body)
}
```

**修复建议**：

```go
// GOOD: 限制请求体大小
func uploadHandler(w http.ResponseWriter, r *http.Request) {
    r.Body = http.MaxBytesReader(w, r.Body, 10<<20) // 限制10MB
    body, err := io.ReadAll(r.Body)
    if err != nil {
        http.Error(w, "request too large", http.StatusRequestEntityTooLarge)
        return
    }
    processBody(body)
}
```

---

#### security/missing-timeout — 缺少超时控制

- **严重程度**：🟡警告
- **描述**：context无deadline、HTTP client无超时、数据库查询无超时，请求可能永远挂起，被攻击者利用进行慢速攻击

**检查要点**：
1. context无deadline或timeout（请求可能永远挂起）
2. HTTP client使用 `http.DefaultClient`（无超时设置）
3. 数据库查询未传入带超时的context

**反例**：

```go
// BAD: 使用默认HTTP client（无超时），外部服务无响应时goroutine永远阻塞
func fetchData(url string) ([]byte, error) {
    resp, err := http.Get(url) // http.DefaultClient 无超时
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    return io.ReadAll(resp.Body)
}
```

**修复建议**：

```go
// GOOD: 设置超时的HTTP client + context控制
var httpClient = &http.Client{Timeout: 10 * time.Second}

func fetchData(ctx context.Context, url string) ([]byte, error) {
    req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
    if err != nil {
        return nil, err
    }
    resp, err := httpClient.Do(req)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    return io.ReadAll(resp.Body)
}
```

---

### 输入安全

---

#### security/sql-injection — SQL注入

- **严重程度**：🔴严重
- **描述**：字符串拼接SQL语句，攻击者可注入恶意SQL，导致数据泄露或破坏

**检查要点**：
1. `fmt.Sprintf` 或 `+` 拼接SQL语句
2. 未使用参数化查询或ORM的安全查询方法

**反例**：

```go
// BAD: 字符串拼接SQL，存在注入风险
func getUser(db *sql.DB, name string) (*User, error) {
    query := fmt.Sprintf("SELECT * FROM users WHERE name = '%s'", name)
    // name = "'; DROP TABLE users; --" → 灾难
    row := db.QueryRow(query)
    var u User
    err := row.Scan(&u.ID, &u.Name)
    return &u, err
}
```

**修复建议**：

```go
// GOOD: 使用参数化查询，数据库驱动自动转义
func getUser(db *sql.DB, name string) (*User, error) {
    query := "SELECT * FROM users WHERE name = ?"
    row := db.QueryRow(query, name) // 参数化，安全
    var u User
    err := row.Scan(&u.ID, &u.Name)
    return &u, err
}
```

---

#### security/command-injection — 命令注入

- **严重程度**：🔴严重
- **描述**：`os/exec` 拼接用户输入，攻击者可注入任意系统命令

**检查要点**：
1. `exec.Command` 的参数包含未校验的用户输入
2. 使用 `sh -c` 执行拼接的命令字符串

**反例**：

```go
// BAD: 用户输入直接拼接到shell命令中
func compress(filename string) error {
    cmd := exec.Command("sh", "-c", "tar czf archive.tar.gz "+filename)
    // filename = "; rm -rf /" → 灾难
    return cmd.Run()
}
```

**修复建议**：

```go
// GOOD: 将用户输入作为独立参数传递，不经过shell解析
func compress(filename string) error {
    // 校验文件名，拒绝特殊字符
    if strings.ContainsAny(filename, ";&|`$") {
        return fmt.Errorf("invalid filename: %s", filename)
    }
    cmd := exec.Command("tar", "czf", "archive.tar.gz", filename)
    return cmd.Run()
}
```

---

#### security/path-traversal — 路径遍历

- **严重程度**：🔴严重
- **描述**：`filepath.Join` 未校验相对路径，攻击者可通过 `../` 访问任意文件

**检查要点**：
1. 用户输入直接拼接文件路径
2. 未校验路径是否在预期目录内
3. 未使用 `filepath.Clean` + 前缀检查

**反例**：

```go
// BAD: 用户可通过 ../../../etc/passwd 读取任意文件
func serveFile(w http.ResponseWriter, r *http.Request) {
    name := r.URL.Query().Get("file")
    path := filepath.Join("/data/uploads", name) // name = "../../etc/passwd"
    http.ServeFile(w, r, path)
}
```

**修复建议**：

```go
// GOOD: 清理路径并校验是否在允许的目录内
func serveFile(w http.ResponseWriter, r *http.Request) {
    name := r.URL.Query().Get("file")
    path := filepath.Join("/data/uploads", filepath.Clean("/"+name))
    if !strings.HasPrefix(path, "/data/uploads/") {
        http.Error(w, "forbidden", http.StatusForbidden)
        return
    }
    http.ServeFile(w, r, path)
}
```

---

#### security/unsanitized-input — 未清洗的外部输入

- **严重程度**：🟡警告
- **描述**：HTTP参数、MQ消息等外部输入未校验直接使用，可能导致非预期行为

**检查要点**：
1. HTTP query/body 参数未做长度、格式校验
2. MQ消息反序列化后未校验字段合法性
3. 外部输入直接用于业务逻辑判断

**反例**：

```go
// BAD: 外部输入未校验直接使用
func updateAge(w http.ResponseWriter, r *http.Request) {
    ageStr := r.FormValue("age")
    age, _ := strconv.Atoi(ageStr) // 忽略错误，age可能为0
    db.Exec("UPDATE users SET age = ? WHERE id = ?", age, getUserID(r))
}
```

**修复建议**：

```go
// GOOD: 校验输入合法性
func updateAge(w http.ResponseWriter, r *http.Request) {
    ageStr := r.FormValue("age")
    age, err := strconv.Atoi(ageStr)
    if err != nil || age < 0 || age > 200 {
        http.Error(w, "invalid age", http.StatusBadRequest)
        return
    }
    db.Exec("UPDATE users SET age = ? WHERE id = ?", age, getUserID(r))
}
```

---

#### security/ssrf — SSRF

- **严重程度**：🔴严重
- **描述**：用户可控URL未做白名单校验，攻击者可利用服务端发起内网请求，探测或攻击内部服务

**检查要点**：
1. 用户提供的URL直接用于HTTP请求
2. 未校验URL的host是否在白名单内
3. 未阻止对内网地址（127.0.0.1、10.x、172.16.x等）的访问

**反例**：

```go
// BAD: 用户可控URL，可访问内网服务
func proxyHandler(w http.ResponseWriter, r *http.Request) {
    targetURL := r.URL.Query().Get("url")
    // targetURL = "http://169.254.169.254/latest/meta-data/" → 云元数据泄露
    resp, err := http.Get(targetURL)
    if err != nil {
        http.Error(w, err.Error(), 500)
        return
    }
    defer resp.Body.Close()
    io.Copy(w, resp.Body)
}
```

**修复建议**：

```go
// GOOD: 白名单校验URL host
var allowedHosts = map[string]bool{
    "api.example.com": true,
    "cdn.example.com": true,
}

func proxyHandler(w http.ResponseWriter, r *http.Request) {
    targetURL := r.URL.Query().Get("url")
    u, err := url.Parse(targetURL)
    if err != nil || !allowedHosts[u.Hostname()] {
        http.Error(w, "forbidden host", http.StatusForbidden)
        return
    }
    resp, err := http.Get(targetURL)
    if err != nil {
        http.Error(w, err.Error(), 500)
        return
    }
    defer resp.Body.Close()
    io.Copy(w, resp.Body)
}
```

---

### 数据安全

---

#### security/hardcoded-secret — 硬编码密钥

- **严重程度**：🔴严重
- **描述**：代码中硬编码密码、API key、token，一旦代码泄露（如推送到公开仓库），所有密钥暴露

**检查要点**：
1. 字符串常量包含密码、API key、token、secret
2. 配置结构体中有默认密钥值
3. 未使用环境变量或密钥管理服务（如 Vault、AWS Secrets Manager）

**反例**：

```go
// BAD: 硬编码API密钥和数据库密码
const apiKey = "sk-1234567890abcdef"

func connectDB() (*sql.DB, error) {
    dsn := "root:P@ssw0rd123@tcp(db.example.com:3306)/mydb"
    return sql.Open("mysql", dsn)
}
```

**修复建议**：

```go
// GOOD: 从环境变量读取敏感配置
func connectDB() (*sql.DB, error) {
    dsn := os.Getenv("DATABASE_DSN")
    if dsn == "" {
        return nil, fmt.Errorf("DATABASE_DSN not set")
    }
    return sql.Open("mysql", dsn)
}
```

---

#### security/log-leak — 敏感信息日志泄露

- **严重程度**：🟡警告
- **描述**：密码、token、身份证号、手机号等敏感信息出现在日志中，可能被日志收集系统采集后扩散

**检查要点**：
1. 日志中打印完整的请求体（可能含密码）
2. 日志中打印token、session ID
3. 日志中打印用户PII（身份证号、手机号、银行卡号）

**反例**：

```go
// BAD: 日志中打印敏感信息
func login(w http.ResponseWriter, r *http.Request) {
    var req LoginRequest
    json.NewDecoder(r.Body).Decode(&req)
    log.Printf("login attempt: user=%s password=%s", req.Username, req.Password)
    token, err := authenticate(req.Username, req.Password)
    if err != nil {
        log.Printf("auth failed: %v", err)
        return
    }
    log.Printf("issued token: %s", token) // token泄露到日志
}
```

**修复建议**：

```go
// GOOD: 日志中脱敏处理
func login(w http.ResponseWriter, r *http.Request) {
    var req LoginRequest
    json.NewDecoder(r.Body).Decode(&req)
    log.Printf("login attempt: user=%s", req.Username) // 不打印密码
    token, err := authenticate(req.Username, req.Password)
    if err != nil {
        log.Printf("auth failed for user=%s: %v", req.Username, err)
        return
    }
    log.Printf("token issued for user=%s", req.Username) // 不打印token
}
```

---

#### security/weak-crypto — 不安全的加密

- **严重程度**：🔴严重
- **描述**：使用MD5/SHA1用于安全场景（如密码哈希、签名），或使用ECB模式、固定IV等不安全的加密方式

**检查要点**：
1. MD5/SHA1用于密码存储或安全签名
2. AES使用ECB模式（相同明文产生相同密文）
3. 固定IV或nonce（破坏加密安全性）
4. 使用 `math/rand` 而非 `crypto/rand` 生成安全相关随机数

**反例**：

```go
// BAD: 使用MD5存储密码，极易被彩虹表破解
func hashPassword(password string) string {
    h := md5.Sum([]byte(password))
    return hex.EncodeToString(h[:])
}
```

**修复建议**：

```go
// GOOD: 使用bcrypt存储密码，自带盐值和自适应开销
func hashPassword(password string) (string, error) {
    hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
    if err != nil {
        return "", err
    }
    return string(hash), nil
}
```

---

#### security/sensitive-response — 敏感数据未脱敏

- **严重程度**：🟡警告
- **描述**：敏感数据未脱敏直接返回给前端，可能导致用户隐私泄露

**检查要点**：
1. API返回完整的用户手机号、身份证号、银行卡号
2. 返回的用户对象包含密码哈希字段
3. 错误信息中包含内部实现细节（数据库表名、内部IP等）

**反例**：

```go
// BAD: 直接返回完整用户对象，包含敏感字段
type User struct {
    ID       int64  `json:"id"`
    Name     string `json:"name"`
    Phone    string `json:"phone"`     // 完整手机号
    IDCard   string `json:"id_card"`   // 完整身份证号
    Password string `json:"password"`  // 密码哈希也不应返回
}

func getUser(w http.ResponseWriter, r *http.Request) {
    user, _ := findUser(getUserID(r))
    json.NewEncoder(w).Encode(user) // 所有字段暴露
}
```

**修复建议**：

```go
// GOOD: 使用独立的响应结构体，敏感字段脱敏
type UserResponse struct {
    ID    int64  `json:"id"`
    Name  string `json:"name"`
    Phone string `json:"phone"`   // 脱敏后的手机号
}

func maskPhone(phone string) string {
    if len(phone) <= 7 { return "***" }
    return phone[:3] + "****" + phone[len(phone)-4:]
}

func getUser(w http.ResponseWriter, r *http.Request) {
    user, _ := findUser(getUserID(r))
    resp := UserResponse{
        ID: user.ID, Name: user.Name,
        Phone: maskPhone(user.Phone),
    }
    json.NewEncoder(w).Encode(resp)
}
```

---

### 权限安全

---

#### security/missing-auth — 缺少鉴权

- **严重程度**：🔴严重
- **描述**：API未校验token/session，任何人可直接访问

**检查要点**：
1. HTTP handler未检查Authorization header
2. 缺少认证中间件
3. 内部接口暴露到公网但无鉴权

**反例**：

```go
// BAD: 管理接口无任何鉴权
func deleteUser(w http.ResponseWriter, r *http.Request) {
    userID := r.URL.Query().Get("id")
    db.Exec("DELETE FROM users WHERE id = ?", userID) // 任何人可删除任何用户
    w.WriteHeader(http.StatusOK)
}

func main() {
    http.HandleFunc("/admin/delete-user", deleteUser) // 无中间件保护
    http.ListenAndServe(":8080", nil)
}
```

**修复建议**：

```go
// GOOD: 使用认证中间件保护接口
func authMiddleware(next http.HandlerFunc) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        token := r.Header.Get("Authorization")
        claims, err := validateToken(token)
        if err != nil {
            http.Error(w, "unauthorized", http.StatusUnauthorized)
            return
        }
        ctx := context.WithValue(r.Context(), "claims", claims)
        next(w, r.WithContext(ctx))
    }
}

func main() {
    http.HandleFunc("/admin/delete-user", authMiddleware(requireAdmin(deleteUser)))
    http.ListenAndServe(":8080", nil)
}
```

---

#### security/broken-access — 越权访问

- **严重程度**：🔴严重
- **描述**：水平越权（用户A访问用户B数据）或垂直越权（普通用户访问管理接口），缺少所有权或角色检查

**检查要点**：
1. 水平越权：查询数据时未校验资源属于当前用户（缺少owner检查）
2. 垂直越权：管理接口未校验用户角色
3. 仅依赖前端隐藏按钮来控制权限

**反例**：

```go
// BAD: 水平越权 — 用户可通过修改order_id查看他人订单
func getOrder(w http.ResponseWriter, r *http.Request) {
    orderID := r.URL.Query().Get("order_id")
    var order Order
    db.QueryRow("SELECT * FROM orders WHERE id = ?", orderID).Scan(&order)
    // 未检查 order.UserID == 当前用户ID
    json.NewEncoder(w).Encode(order)
}
```

**修复建议**：

```go
// GOOD: 查询时加入owner条件，确保只能访问自己的数据
func getOrder(w http.ResponseWriter, r *http.Request) {
    orderID := r.URL.Query().Get("order_id")
    currentUserID := getUserIDFromContext(r.Context())
    var order Order
    err := db.QueryRow(
        "SELECT * FROM orders WHERE id = ? AND user_id = ?",
        orderID, currentUserID, // 加入owner条件
    ).Scan(&order)
    if err == sql.ErrNoRows {
        http.Error(w, "not found", http.StatusNotFound)
        return
    }
    json.NewEncoder(w).Encode(order)
}
```

---

#### security/cors-misconfiguration — CORS配置过于宽松

- **严重程度**：🟡警告
- **描述**：在需要认证的API上设置 `Access-Control-Allow-Origin: *`，可能导致跨站请求伪造

**检查要点**：
1. `Allow-Origin: *` 与 `Allow-Credentials: true` 同时使用
2. 动态反射Origin header而不做白名单校验
3. 需要认证的API使用通配符Origin

**反例**：

```go
// BAD: CORS过于宽松，任何网站都可以携带cookie访问API
func corsMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Access-Control-Allow-Origin", "*")
        w.Header().Set("Access-Control-Allow-Credentials", "true") // 危险组合
        next.ServeHTTP(w, r)
    })
}
```

**修复建议**：

```go
// GOOD: 白名单校验Origin
var allowedOrigins = map[string]bool{
    "https://app.example.com":   true,
    "https://admin.example.com": true,
}

func corsMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        origin := r.Header.Get("Origin")
        if allowedOrigins[origin] {
            w.Header().Set("Access-Control-Allow-Origin", origin)
            w.Header().Set("Access-Control-Allow-Credentials", "true")
        }
        next.ServeHTTP(w, r)
    })
}
```

---

## 输出格式

每个发现按以下结构输出：

```
### [check_id] 标题
- **严重程度**：🔴严重 / 🟡警告
- **位置**：`file.go:行号`
- **问题**：描述具体安全漏洞及可能的攻击方式
- **建议**：具体修复方案
- **攻击场景**：简述攻击者如何利用该漏洞
```

## 注意事项

1. **攻击者视角**：始终从攻击者角度评估风险，考虑"这个漏洞能被怎样利用"
2. **与阶段3联动**：阶段3发现的资源泄漏，本阶段进一步评估其安全影响（如能否被外部触发导致DoS），避免重复报告但可交叉引用
3. **严格度过滤**：relaxed模式下仅报告🔴严重级别的发现，避免噪音
4. **误报控制**：内部工具代码的安全要求低于对外API，结合阶段1的上下文判断
5. **修复优先级**：注入类 > 鉴权类 > 数据泄露类 > 配置类
