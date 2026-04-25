# 阶段3：潜在bug与边界条件审核

## 输入
- 阶段1的上下文摘要（代码类型、依赖关系、关键路径）
- 待审核代码

## 严格度适配

| 严格度 | 检查范围 |
|--------|----------|
| strict | 所有检查项，包括低概率边界条件 |
| normal | 常见bug模式和高风险边界条件 |
| relaxed | 仅检查高危项（nil panic、资源泄漏、错误处理） |

---

## 检查项

### bug/nil-pointer — 空值/nil检查

- **严重程度**：🔴严重
- **描述**：未对nil进行防御性检查即直接使用，导致运行时panic

**检查要点**：
1. 指针解引用前未检查nil
2. map访问前未检查nil（nil map读取返回零值，写入panic）
3. slice长度未检查就访问索引
4. interface类型断言未使用comma-ok模式
5. 函数返回指针+error时，error非nil但仍使用指针

**反例**：
```go
// 问题1：指针解引用前未检查nil
func getName(u *User) string {
    return u.Name // panic: nil pointer dereference
}

// 问题2：nil map写入
func addTag(tags map[string]string, k, v string) {
    tags[k] = v // panic: assignment to entry in nil map
}

// 问题3：类型断言未使用comma-ok
func process(v interface{}) {
    s := v.(string) // panic: interface conversion
    fmt.Println(s)
}

// 问题4：error非nil时仍使用返回的指针
user, err := findUser(id)
if err != nil {
    log.Println(err)
}
fmt.Println(user.Name) // user可能为nil
```

**修复建议**：
```go
// 修复1：检查nil
func getName(u *User) string {
    if u == nil {
        return ""
    }
    return u.Name
}

// 修复2：初始化map
func addTag(tags map[string]string, k, v string) map[string]string {
    if tags == nil {
        tags = make(map[string]string)
    }
    tags[k] = v
    return tags
}

// 修复3：使用comma-ok模式
func process(v interface{}) {
    s, ok := v.(string)
    if !ok {
        return
    }
    fmt.Println(s)
}

// 修复4：error非nil时立即返回
user, err := findUser(id)
if err != nil {
    return fmt.Errorf("find user: %w", err)
}
fmt.Println(user.Name)
```

---

### bug/zero-value — 零值陷阱

- **严重程度**：🟡警告
- **描述**：Go的零值机制在某些场景下会导致隐蔽的逻辑错误

**检查要点**：
1. 未初始化的map直接写入（panic）
2. bool零值false导致逻辑错误（如 `if !config.Enabled` 当config未设置时）
3. string零值""的语义歧义（空字符串 vs 未设置）
4. time.Time零值（0001-01-01）被当作有效时间

**反例**：
```go
// 问题1：bool零值导致逻辑错误
type Config struct {
    Enabled bool
}
cfg := Config{} // Enabled == false
if !cfg.Enabled {
    shutdown() // 未设置 ≠ 主动禁用，但行为相同
}

// 问题2：string零值语义歧义
type Filter struct {
    Status string
}
f := Filter{}
if f.Status == "" {
    // 这是"查全部"还是"未设置"？语义不清
}

// 问题3：time.Time零值被当作有效时间
type Event struct {
    CreatedAt time.Time
}
e := Event{}
fmt.Println(e.CreatedAt) // 0001-01-01 00:00:00 — 不是有效时间
```

**修复建议**：
```go
// 修复1：使用*bool区分"未设置"和"false"
type Config struct {
    Enabled *bool
}
if cfg.Enabled == nil {
    // 未设置，使用默认值
} else if !*cfg.Enabled {
    shutdown() // 明确禁用
}

// 修复2：使用指针或自定义类型区分
type Filter struct {
    Status *string // nil=未设置, ""=空字符串
}

// 修复3：检查零值时间
if e.CreatedAt.IsZero() {
    return errors.New("created_at is required")
}
```

---

### bug/index-out-of-range — 数组/slice越界

- **严重程度**：🔴严重
- **描述**：未检查长度即访问slice/array索引，导致运行时panic

**检查要点**：
1. 索引访问前未检查长度
2. sub-slice边界 `s[a:b]` 中 a > b 或 b > len(s)

**反例**：
```go
// 问题1：未检查长度
func first(items []string) string {
    return items[0] // panic: index out of range
}

// 问题2：sub-slice越界
func truncate(s string, n int) string {
    return s[:n] // 当 n > len(s) 时 panic
}
```

**修复建议**：
```go
// 修复1：检查长度
func first(items []string) (string, bool) {
    if len(items) == 0 {
        return "", false
    }
    return items[0], true
}

// 修复2：边界保护
func truncate(s string, n int) string {
    if n > len(s) {
        n = len(s)
    }
    return s[:n]
}
```

---

### bug/integer-overflow — 整数溢出

- **严重程度**：🟡警告
- **描述**：整数类型转换或运算时超出范围，导致静默错误

**检查要点**：
1. int32/int64转换时值超出范围
2. uint减法下溢（结果为负时变成极大正数）
3. 大数乘法溢出

**反例**：
```go
// 问题1：int64转int32溢出
var big int64 = math.MaxInt32 + 1
small := int32(big) // 静默溢出，值变为负数

// 问题2：uint减法下溢
var a, b uint = 1, 2
diff := a - b // 结果为 18446744073709551615
```

**修复建议**：
```go
// 修复1：转换前检查范围
var big int64 = getSomeValue()
if big > math.MaxInt32 || big < math.MinInt32 {
    return fmt.Errorf("value %d overflows int32", big)
}
small := int32(big)

// 修复2：使用有符号类型或先比较
var a, b uint = 1, 2
if a < b {
    return fmt.Errorf("underflow: %d - %d", a, b)
}
diff := a - b
```

---

### bug/race-condition — 竞态条件

- **严重程度**：🔴严重
- **描述**：多goroutine并发访问共享状态时缺少同步机制

**检查要点**：
1. 共享变量无锁访问（多goroutine读写同一变量）
2. map并发读写（fatal error: concurrent map read and map write）
3. slice并发append（数据丢失或panic）

**反例**：
```go
// 问题1：map并发读写
m := make(map[string]int)
for i := 0; i < 10; i++ {
    go func(i int) {
        m[fmt.Sprint(i)] = i // fatal error
    }(i)
}

// 问题2：共享变量无锁
var count int
for i := 0; i < 100; i++ {
    go func() { count++ }() // data race
}
```

**修复建议**：
```go
// 修复1：使用sync.Map或加锁
var mu sync.Mutex
m := make(map[string]int)
for i := 0; i < 10; i++ {
    go func(i int) {
        mu.Lock()
        m[fmt.Sprint(i)] = i
        mu.Unlock()
    }(i)
}

// 修复2：使用atomic
var count int64
for i := 0; i < 100; i++ {
    go func() { atomic.AddInt64(&count, 1) }()
}
```

---

### bug/resource-leak — 资源泄漏

- **严重程度**：🔴严重
- **描述**：打开的资源未正确关闭，导致文件描述符耗尽、内存泄漏或死锁

**检查要点**：
1. 文件打开后未defer Close()
2. 获取锁后未defer Unlock()
3. HTTP response body未关闭
4. goroutine无退出条件（永远运行）
5. context未cancel（context.WithCancel/WithTimeout后未defer cancel()）
6. 数据库连接/事务未关闭

**反例**：
```go
// 问题1：HTTP response body未关闭
resp, err := http.Get(url)
if err != nil {
    return err
}
// 缺少 resp.Body.Close() — 连接无法复用

// 问题2：context未cancel
ctx, cancel := context.WithTimeout(parentCtx, 5*time.Second)
// 缺少 defer cancel() — 资源直到超时才释放

// 问题3：goroutine泄漏
func watch(ch <-chan Event) {
    go func() {
        for e := range ch { // 如果ch永远不关闭，goroutine永远不退出
            process(e)
        }
    }()
}
```

**修复建议**：
```go
// 修复1：defer关闭body
resp, err := http.Get(url)
if err != nil {
    return err
}
defer resp.Body.Close()

// 修复2：defer cancel
ctx, cancel := context.WithTimeout(parentCtx, 5*time.Second)
defer cancel()

// 修复3：使用context控制goroutine退出
func watch(ctx context.Context, ch <-chan Event) {
    go func() {
        for {
            select {
            case <-ctx.Done():
                return
            case e, ok := <-ch:
                if !ok {
                    return
                }
                process(e)
            }
        }
    }()
}
```

---

### bug/error-handling — 错误处理不当

- **严重程度**：🟡警告（忽略error为🔴严重）
- **描述**：错误被忽略、丢失或缺少上下文，导致问题难以排查

**检查要点**：
1. error被 `_` 忽略（`_ = doSomething()`）
2. error未向上传播（检查了err但没return）
3. 错误信息缺少上下文（应用 `fmt.Errorf("xxx: %w", err)` 包装）
4. 多个error只返回最后一个（前面的error丢失）

**反例**：
```go
// 问题1：error被忽略
_ = db.Close()
_ = os.Remove(tmpFile)

// 问题2：检查了err但没return
data, err := fetchData()
if err != nil {
    log.Println("fetch failed:", err)
    // 缺少 return — 继续使用可能为nil的data
}
process(data)

// 问题3：错误缺少上下文
func getUser(id int) (*User, error) {
    u, err := db.Query(id)
    if err != nil {
        return nil, err // 调用方不知道是哪一步失败
    }
    return u, nil
}

// 问题4：多个error只保留最后一个
func cleanup(a, b *os.File) error {
    err := a.Close()
    err = b.Close() // a.Close()的error被覆盖
    return err
}
```

**修复建议**：
```go
// 修复1：处理或记录error
if err := db.Close(); err != nil {
    log.Printf("close db: %v", err)
}

// 修复2：检查后立即return
data, err := fetchData()
if err != nil {
    return fmt.Errorf("fetch data: %w", err)
}
process(data)

// 修复3：包装错误上下文
func getUser(id int) (*User, error) {
    u, err := db.Query(id)
    if err != nil {
        return nil, fmt.Errorf("get user %d: %w", id, err)
    }
    return u, nil
}

// 修复4：合并多个error
func cleanup(a, b *os.File) error {
    var errs []error
    if err := a.Close(); err != nil {
        errs = append(errs, fmt.Errorf("close a: %w", err))
    }
    if err := b.Close(); err != nil {
        errs = append(errs, fmt.Errorf("close b: %w", err))
    }
    return errors.Join(errs...)
}
```

---

### bug/channel-misuse — channel误用

- **严重程度**：🔴严重
- **描述**：channel使用不当导致死锁或panic

**检查要点**：
1. 无缓冲channel在同一goroutine中读写（死锁）
2. 关闭后写入（panic: send on closed channel）
3. nil channel永久阻塞
4. 多次关闭同一channel（panic）

**反例**：
```go
// 问题1：同一goroutine中读写无缓冲channel
ch := make(chan int)
ch <- 1    // 永久阻塞，死锁
val := <-ch

// 问题2：关闭后写入
ch := make(chan int, 1)
close(ch)
ch <- 1 // panic: send on closed channel

// 问题3：多次关闭
ch := make(chan int)
close(ch)
close(ch) // panic: close of closed channel

// 问题4：nil channel阻塞
var ch chan int // nil
<-ch // 永久阻塞
```

**修复建议**：
```go
// 修复1：使用缓冲channel或分goroutine
ch := make(chan int, 1)
ch <- 1
val := <-ch

// 修复2：由生产者关闭，消费者只读
func produce(ch chan<- int) {
    defer close(ch) // 只有发送方关闭
    for i := 0; i < 10; i++ {
        ch <- i
    }
}

// 修复3：使用sync.Once防止多次关闭
type SafeChan struct {
    ch   chan int
    once sync.Once
}
func (s *SafeChan) Close() {
    s.once.Do(func() { close(s.ch) })
}

// 修复4：初始化channel
ch := make(chan int)
```

---

## 输出格式

对每个发现的问题，输出：

```
### [check-id] 问题简述
- 严重程度：🔴严重 / 🟡警告
- 位置：`file:line`
- 问题：具体描述
- 修复建议：具体修复方案
```
