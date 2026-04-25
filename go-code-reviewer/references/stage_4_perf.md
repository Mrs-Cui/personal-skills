# 阶段4：性能问题审核

## 目标
识别代码中的性能瓶颈和优化机会，包括内存分配、算法效率、并发原语使用和 I/O 模式。

## 输入
- 阶段1的上下文摘要（代码规模、项目类型、热路径标注）
- 阶段3的发现（资源泄漏等可能影响性能的问题）
- 待审核代码

## 严格度适配

| 严格度 | 范围 |
|--------|------|
| **strict** | 所有性能检查，包括微优化（逃逸分析、sync.Pool、预分配等） |
| **normal** | 常见性能问题和中等影响的优化（不必要分配、大对象拷贝、锁竞争等） |
| **relaxed** | 仅检查严重性能问题（N+1查询、goroutine泄漏、明显的O(n²)） |

---

## 检查项

---

### perf/unnecessary-allocation — 不必要的内存分配

**严重程度：🟡警告**

检查要点：
- 循环内创建对象应提到循环外
- 字符串拼接用 `strings.Builder` 而非 `+` 或 `fmt.Sprintf`（循环场景）
- 避免不必要的 `[]byte` ↔ `string` 转换

**错误示例：**

```go
// BAD: 循环内反复分配，每次迭代都产生新的字符串分配
func buildNames(users []User) string {
    result := ""
    for _, u := range users {
        result += u.Name + ","  // 每次 += 都分配新字符串
    }
    return result
}
```

**优化示例：**

```go
// GOOD: 使用 strings.Builder，预分配容量，单次分配
func buildNames(users []User) string {
    var b strings.Builder
    b.Grow(len(users) * 20) // 预估容量
    for i, u := range users {
        if i > 0 {
            b.WriteByte(',')
        }
        b.WriteString(u.Name)
    }
    return b.String()
}
```

---

### perf/missing-prealloc — 缺少预分配

**严重程度：🔵建议**

检查要点：
- `make([]T, 0)` 在已知容量时应 `make([]T, 0, cap)`
- `make(map[K]V)` 在已知大小时应 `make(map[K]V, size)`

**错误示例：**

```go
// BAD: 未预分配，append 触发多次扩容和拷贝
func collectIDs(users []User) []int64 {
    var ids []int64 // len=0, cap=0
    for _, u := range users {
        ids = append(ids, u.ID) // 多次扩容：1→2→4→8→...
    }
    return ids
}
```

**优化示例：**

```go
// GOOD: 已知长度，预分配切片容量
func collectIDs(users []User) []int64 {
    ids := make([]int64, 0, len(users))
    for _, u := range users {
        ids = append(ids, u.ID) // 无扩容
    }
    return ids
}
```

---

### perf/large-struct-copy — 大对象值传递

**严重程度：🟡警告**

检查要点：
- 大 struct 作为值传递（应用指针）
- 循环中 range 大 struct 产生拷贝：`for _, v := range largeStructSlice` 应用 index

**错误示例：**

```go
// BAD: range 每次迭代拷贝整个大 struct（数百字节）
type Record struct {
    ID   int
    Data [4096]byte
}

func process(records []Record) {
    for _, r := range records { // r 是 Record 的完整拷贝
        fmt.Println(r.ID)
    }
}
```

**优化示例：**

```go
// GOOD: 使用 index 访问，避免拷贝
func process(records []Record) {
    for i := range records {
        fmt.Println(records[i].ID) // 零拷贝，直接引用
    }
}
```

---

### perf/sync-pool — 高频临时对象

**严重程度：🔵建议**

检查要点：
- 高频创建销毁的临时对象可用 `sync.Pool` 复用
- 如 `bytes.Buffer`、临时 slice 等

**错误示例：**

```go
// BAD: 每次请求都分配新 buffer，给 GC 带来压力
func handleRequest(data []byte) []byte {
    buf := new(bytes.Buffer) // 每次分配
    buf.Write(data)
    // ... 处理逻辑
    return buf.Bytes()
}
```

**优化示例：**

```go
// GOOD: 使用 sync.Pool 复用 buffer
var bufPool = sync.Pool{
    New: func() any { return new(bytes.Buffer) },
}

func handleRequest(data []byte) []byte {
    buf := bufPool.Get().(*bytes.Buffer)
    defer func() {
        buf.Reset()
        bufPool.Put(buf)
    }()
    buf.Write(data)
    // ... 处理逻辑
    return bytes.Clone(buf.Bytes()) // 返回独立副本
}
```

---

### perf/inefficient-algorithm — 低效算法

**严重程度：🟡警告（明显 O(n²) 为 🔴严重）**

检查要点：
- O(n²) 可优化为 O(n) 的场景（如嵌套循环查找可用 map）
- 不必要的排序
- 重复计算可缓存

**错误示例：**

```go
// BAD: O(n²) 嵌套循环查找
func findCommon(a, b []string) []string {
    var result []string
    for _, x := range a {
        for _, y := range b { // 对每个 a 元素遍历整个 b
            if x == y {
                result = append(result, x)
            }
        }
    }
    return result
}
```

**优化示例：**

```go
// GOOD: O(n) 使用 map 做查找
func findCommon(a, b []string) []string {
    set := make(map[string]struct{}, len(b))
    for _, s := range b {
        set[s] = struct{}{}
    }
    result := make([]string, 0, min(len(a), len(b)))
    for _, s := range a {
        if _, ok := set[s]; ok {
            result = append(result, s)
        }
    }
    return result
}
```

---

### perf/lock-contention — 不必要的锁竞争

**严重程度：🟡警告**

检查要点：
- 可用 `atomic` 替代 `mutex` 的简单计数器场景
- 锁粒度过大（整个函数加锁 vs 仅保护临界区）
- 读多写少场景应用 `sync.RWMutex` 而非 `sync.Mutex`

**错误示例：**

```go
// BAD: 用 Mutex 保护简单计数器，且锁粒度过大
type Stats struct {
    mu       sync.Mutex
    requests int64
}

func (s *Stats) HandleRequest(req *Request) {
    s.mu.Lock()
    defer s.mu.Unlock()       // 整个函数持锁
    s.requests++
    processRequest(req)        // 耗时操作也在锁内
}
```

**优化示例：**

```go
// GOOD: 简单计数器用 atomic，耗时操作移出锁外
type Stats struct {
    requests atomic.Int64
}

func (s *Stats) HandleRequest(req *Request) {
    s.requests.Add(1)     // 无锁原子操作
    processRequest(req)   // 不需要锁保护
}
```

---

### perf/goroutine-explosion — goroutine 失控

**严重程度：🔴严重**

检查要点：
- 无上限创建 goroutine（应用 worker pool 或 semaphore）
- 缺少退出信号的 goroutine（泄漏）

**错误示例：**

```go
// BAD: 无上限创建 goroutine，可能耗尽内存
func processAll(items []Item) {
    for _, item := range items {
        go func(it Item) { // items 可能有百万条
            handle(it)
        }(item)
    }
}
```

**优化示例：**

```go
// GOOD: 使用 semaphore 限制并发数
func processAll(items []Item) error {
    g, ctx := errgroup.WithContext(context.Background())
    g.SetLimit(runtime.GOMAXPROCS(0)) // 限制并发数
    for _, item := range items {
        item := item
        g.Go(func() error {
            select {
            case <-ctx.Done():
                return ctx.Err()
            default:
                return handle(item)
            }
        })
    }
    return g.Wait()
}
```

---

### perf/io-inefficiency — I/O 效率

**严重程度：🔴严重（N+1）/ 🟡警告（其他）**

检查要点：
- N+1 查询（循环中逐条查询数据库）
- 缺少批量操作（逐条 insert 应改为 batch insert）
- 未使用连接池
- 大文件未流式处理（全部读入内存）

**错误示例：**

```go
// BAD: N+1 查询，循环中逐条查数据库
func getOrderDetails(userIDs []int64) ([]Order, error) {
    var orders []Order
    for _, uid := range userIDs {
        o, err := db.Query("SELECT * FROM orders WHERE user_id = ?", uid)
        if err != nil {
            return nil, err
        }
        orders = append(orders, parseOrders(o)...)
    }
    return orders, nil
}
```

**优化示例：**

```go
// GOOD: 批量查询，单次 SQL
func getOrderDetails(userIDs []int64) ([]Order, error) {
    query, args, err := sqlx.In(
        "SELECT * FROM orders WHERE user_id IN (?)", userIDs,
    )
    if err != nil {
        return nil, err
    }
    var orders []Order
    err = db.Select(&orders, db.Rebind(query), args...)
    return orders, err
}
```

**错误示例（大文件）：**

```go
// BAD: 大文件全部读入内存
func processFile(path string) error {
    data, err := os.ReadFile(path) // 文件可能数GB
    if err != nil {
        return err
    }
    return processData(data)
}
```

**优化示例（大文件）：**

```go
// GOOD: 流式处理，内存占用恒定
func processFile(path string) error {
    f, err := os.Open(path)
    if err != nil {
        return err
    }
    defer f.Close()
    scanner := bufio.NewScanner(f)
    for scanner.Scan() {
        if err := processLine(scanner.Bytes()); err != nil {
            return err
        }
    }
    return scanner.Err()
}
```

---

### perf/escape-analysis — 逃逸分析不友好

**严重程度：🔵建议**

检查要点：
- 不必要的指针使用导致堆分配
- `interface{}` 导致的装箱开销

**错误示例：**

```go
// BAD: 不必要的指针，导致小对象逃逸到堆
func newPoint(x, y int) *Point {
    p := Point{X: x, Y: y} // 因为返回指针，p 逃逸到堆
    return &p
}

func sumPoints(points []*Point) int {
    sum := 0
    for _, p := range points { // 每个 Point 都是堆分配
        sum += p.X + p.Y
    }
    return sum
}
```

**优化示例：**

```go
// GOOD: 值类型，留在栈上，对 GC 友好
func newPoint(x, y int) Point {
    return Point{X: x, Y: y} // 栈分配，调用方决定是否取地址
}

func sumPoints(points []Point) int {
    sum := 0
    for i := range points { // 无指针追踪，无堆分配
        sum += points[i].X + points[i].Y
    }
    return sum
}
```

---

## 输出格式

每个发现按以下结构输出：

```
### [check_id] 标题
- **严重程度**：🔴严重 / 🟡警告 / 🔵建议
- **位置**：`file.go:行号`
- **问题**：描述具体问题及性能影响
- **建议**：具体优化方案
- **预估影响**：定性描述（如"高并发下延迟降低约30%"）
```

## 注意事项

1. **避免过早优化**：仅在热路径或明确瓶颈处建议微优化（strict 模式除外）
2. **结合上下文**：阶段1标注的热路径代码应更严格审查
3. **量化影响**：尽可能给出性能影响的定性或定量估计
4. **与阶段3联动**：阶段3发现的资源泄漏（如未关闭连接）同时也是性能问题，避免重复报告，但可交叉引用
5. **基准测试建议**：对于不确定的性能问题，建议编写 benchmark 验证而非盲目优化
