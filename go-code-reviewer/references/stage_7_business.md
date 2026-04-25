# 阶段7：业务逻辑审核

## 输入

- 阶段1的上下文摘要（架构上下文、服务间调用关系）
- 阶段2-6的发现（可能暗示业务问题）
- 待审核代码

## 与代码实现审核的区别

阶段3关注"代码会不会崩"，阶段7关注"业务会不会错"。

例如一个扣款函数：
- 阶段3检查：是否有 nil panic、error 是否正确返回
- 阶段7检查：是否存在超扣、重复扣款、并发扣款竞态的可能

## 严格度适配

| 严格度 | 检查范围 |
|--------|----------|
| strict | 所有业务检查项，核心业务路径（支付、订单、用户数据）最严格 |
| normal | 常见业务问题 |
| relaxed | 仅检查高危业务问题（数据一致性、重复操作） |

## 特殊处理

- 依赖阶段1的架构上下文理解服务间调用关系
- 依赖代码注释和命名推断业务意图
- 如果代码缺少业务注释，标记为 `[业务意图不明确]` 而非强行猜测
- 核心业务路径（支付、订单、用户数据）严格审核，辅助功能（日志、监控、通知）放宽

---

## 检查项

### 7.1 业务规则正确性

#### `business/incorrect-condition` — 条件判断与业务规则不一致

严重程度：🔴严重

检查要点：
- 状态机转换是否覆盖所有合法路径（是否有非法状态转换）
- 条件判断逻辑是否与业务规则匹配

```go
// ❌ 状态机转换遗漏合法路径，且允许非法转换
func (o *Order) UpdateStatus(newStatus OrderStatus) error {
    switch o.Status {
    case StatusPending:
        if newStatus == StatusPaid {
            o.Status = newStatus
            return nil
        }
    case StatusPaid:
        if newStatus == StatusShipped {
            o.Status = newStatus
            return nil
        }
    }
    // 问题1: StatusPending -> StatusCancelled 是合法的，但未处理
    // 问题2: 没有 default 返回错误，静默忽略非法转换
    return nil
}
```

```go
// ✅ 完整的状态机，明确拒绝非法转换
var validTransitions = map[OrderStatus][]OrderStatus{
    StatusPending:   {StatusPaid, StatusCancelled},
    StatusPaid:      {StatusShipped, StatusRefunding},
    StatusShipped:   {StatusDelivered, StatusReturning},
    StatusRefunding: {StatusRefunded},
    StatusReturning: {StatusReturned},
    // StatusDelivered, StatusRefunded, StatusReturned 是终态，无合法转换
}

func (o *Order) UpdateStatus(newStatus OrderStatus) error {
    allowed, ok := validTransitions[o.Status]
    if !ok {
        return fmt.Errorf("当前状态 %s 为终态，不允许变更", o.Status)
    }
    for _, s := range allowed {
        if s == newStatus {
            o.Status = newStatus
            return nil
        }
    }
    return fmt.Errorf("不允许从 %s 转换到 %s", o.Status, newStatus)
}
```

---

#### `business/calculation-error` — 计算逻辑错误

严重程度：🔴严重

检查要点：
- 金额用整数分而非浮点元（避免精度丢失）
- 比例计算精度（百分比、折扣）
- 时区处理（UTC vs 本地时间）

```go
// ❌ 浮点数计算金额，精度丢失
func CalculateDiscount(priceYuan float64, discountRate float64) float64 {
    return priceYuan * discountRate // 0.1 + 0.2 != 0.3
}

// ❌ 时区问题：用本地时间判断活动是否生效
func IsPromotionActive(start, end time.Time) bool {
    now := time.Now() // 服务器时区可能不同
    return now.After(start) && now.Before(end)
}
```

```go
// ✅ 用整数分计算金额，避免浮点精度问题
func CalculateDiscount(priceCents int64, discountBasisPoints int64) int64 {
    // discountBasisPoints: 8500 表示 85% (万分比)
    return priceCents * discountBasisPoints / 10000
}

// ✅ 统一使用 UTC 时间
func IsPromotionActive(start, end time.Time) bool {
    now := time.Now().UTC()
    return now.After(start.UTC()) && now.Before(end.UTC())
}
```

---

#### `business/incomplete-enum` — 枚举未覆盖所有场景

严重程度：🟡警告

检查要点：
- switch 语句是否有 default 兜底
- 新增枚举值时是否所有相关 switch 都已更新

```go
// ❌ 新增了 PayMethodCrypto，但 switch 未更新
type PayMethod int

const (
    PayMethodCard   PayMethod = iota
    PayMethodAlipay
    PayMethodWechat
    PayMethodCrypto // 新增
)

func GetPayChannel(method PayMethod) string {
    switch method {
    case PayMethodCard:
        return "bank_gateway"
    case PayMethodAlipay:
        return "alipay_gateway"
    case PayMethodWechat:
        return "wechat_gateway"
    // PayMethodCrypto 未处理，走不到任何分支，返回空字符串
    }
    return ""
}
```

```go
// ✅ 有 default 兜底，且新增枚举值时编译期可发现
func GetPayChannel(method PayMethod) (string, error) {
    switch method {
    case PayMethodCard:
        return "bank_gateway", nil
    case PayMethodAlipay:
        return "alipay_gateway", nil
    case PayMethodWechat:
        return "wechat_gateway", nil
    case PayMethodCrypto:
        return "crypto_gateway", nil
    default:
        return "", fmt.Errorf("未知支付方式: %d", method)
    }
}
```

---

### 7.2 业务边界条件

#### `business/missing-exception-handling` — 业务异常场景未处理

严重程度：🟡警告

检查要点：
- 库存不足、余额不够、重复操作等异常场景

```go
// ❌ 未处理库存不足的业务异常
func PlaceOrder(ctx context.Context, userID int64, productID int64, qty int) error {
    product, err := repo.GetProduct(ctx, productID)
    if err != nil {
        return err
    }
    // 直接扣减，未检查库存是否充足
    err = repo.DeductStock(ctx, productID, qty)
    if err != nil {
        return err
    }
    return repo.CreateOrder(ctx, userID, productID, qty, product.Price*int64(qty))
}
```

```go
// ✅ 处理库存不足等业务异常
func PlaceOrder(ctx context.Context, userID int64, productID int64, qty int) error {
    product, err := repo.GetProduct(ctx, productID)
    if err != nil {
        return err
    }

    if product.Status != ProductStatusOnSale {
        return ErrProductNotOnSale
    }

    if product.Stock < qty {
        return ErrInsufficientStock
    }

    affected, err := repo.DeductStockWithCheck(ctx, productID, qty)
    if err != nil {
        return err
    }
    if affected == 0 {
        return ErrInsufficientStock // 并发场景下库存已被扣完
    }

    return repo.CreateOrder(ctx, userID, productID, qty, product.Price*int64(qty))
}
```

---

#### `business/missing-idempotency` — 缺少幂等性保护

严重程度：🔴严重

检查要点：
- 并发业务冲突：重复下单、重复支付
- 关键操作缺少幂等键或去重机制

```go
// ❌ 无幂等保护，网络重试会导致重复支付
func Pay(ctx context.Context, orderID int64, amount int64) error {
    order, err := repo.GetOrder(ctx, orderID)
    if err != nil {
        return err
    }
    // 没有检查订单是否已支付
    err = gateway.Charge(ctx, order.UserID, amount)
    if err != nil {
        return err
    }
    return repo.UpdateOrderStatus(ctx, orderID, StatusPaid)
}
```

```go
// ✅ 幂等键 + 状态检查，防止重复支付
func Pay(ctx context.Context, idempotencyKey string, orderID int64, amount int64) error {
    // 1. 幂等键去重
    exists, err := repo.CheckIdempotencyKey(ctx, idempotencyKey)
    if err != nil {
        return err
    }
    if exists {
        return nil // 重复请求，直接返回成功
    }

    // 2. 状态检查
    order, err := repo.GetOrder(ctx, orderID)
    if err != nil {
        return err
    }
    if order.Status != StatusPending {
        return ErrOrderNotPayable
    }

    // 3. 执行扣款
    err = gateway.Charge(ctx, order.UserID, amount)
    if err != nil {
        return err
    }

    // 4. 更新状态 + 记录幂等键（同一事务）
    return repo.InTx(ctx, func(tx *sql.Tx) error {
        if err := repo.UpdateOrderStatusTx(tx, orderID, StatusPaid); err != nil {
            return err
        }
        return repo.SaveIdempotencyKeyTx(tx, idempotencyKey)
    })
}
```

---

#### `business/missing-limit` — 缺少业务数据上下限校验

严重程度：🟡警告

检查要点：
- 金额上限、数量限制、频率限制

```go
// ❌ 无上下限校验，可能出现异常数据
func Transfer(ctx context.Context, from, to int64, amount int64) error {
    // amount 可以是 0、负数、或超大金额
    return repo.InTx(ctx, func(tx *sql.Tx) error {
        if err := repo.DeductBalanceTx(tx, from, amount); err != nil {
            return err
        }
        return repo.AddBalanceTx(tx, to, amount)
    })
}
```

```go
// ✅ 业务上下限校验
const (
    MinTransferAmount = 1        // 最小转账 1 分
    MaxTransferAmount = 50000000 // 最大转账 50 万元 = 50000000 分
)

func Transfer(ctx context.Context, from, to int64, amount int64) error {
    if amount < MinTransferAmount {
        return fmt.Errorf("转账金额不能小于 %d 分", MinTransferAmount)
    }
    if amount > MaxTransferAmount {
        return fmt.Errorf("转账金额不能超过 %d 分", MaxTransferAmount)
    }
    if from == to {
        return errors.New("不能给自己转账")
    }

    // 频率限制检查
    count, err := repo.GetTransferCountToday(ctx, from)
    if err != nil {
        return err
    }
    if count >= MaxDailyTransferCount {
        return ErrDailyTransferLimitExceeded
    }

    return repo.InTx(ctx, func(tx *sql.Tx) error {
        if err := repo.DeductBalanceTx(tx, from, amount); err != nil {
            return err
        }
        return repo.AddBalanceTx(tx, to, amount)
    })
}
```

---

### 7.3 业务流程完整性

#### `business/missing-step` — 关键步骤遗漏

严重程度：🟡警告

检查要点：
- 缺少审批环节、缺少通知、缺少日志记录

```go
// ❌ 退款流程缺少关键步骤
func Refund(ctx context.Context, orderID int64) error {
    order, err := repo.GetOrder(ctx, orderID)
    if err != nil {
        return err
    }
    // 直接退款，缺少：审批、通知用户、记录操作日志
    return gateway.Refund(ctx, order.PaymentID, order.Amount)
}
```

```go
// ✅ 完整的退款流程
func Refund(ctx context.Context, orderID int64, operatorID int64, reason string) error {
    order, err := repo.GetOrder(ctx, orderID)
    if err != nil {
        return err
    }

    // 1. 业务校验
    if order.Status != StatusPaid && order.Status != StatusShipped {
        return ErrOrderNotRefundable
    }

    // 2. 记录退款申请（审计日志）
    refundID, err := repo.CreateRefundRecord(ctx, orderID, operatorID, reason, order.Amount)
    if err != nil {
        return err
    }

    // 3. 执行退款
    err = gateway.Refund(ctx, order.PaymentID, order.Amount)
    if err != nil {
        repo.UpdateRefundStatus(ctx, refundID, RefundFailed, err.Error())
        return fmt.Errorf("退款失败: %w", err)
    }

    // 4. 更新订单状态
    if err := repo.UpdateOrderStatus(ctx, orderID, StatusRefunded); err != nil {
        return err
    }

    // 5. 通知用户
    _ = notifier.SendRefundNotification(ctx, order.UserID, orderID, order.Amount)

    return nil
}
```

---

#### `business/transaction-inconsistency` — 事务一致性问题

严重程度：🔴严重

检查要点：
- 跨表操作是否在同一事务
- 跨服务操作是否有 saga/补偿机制

```go
// ❌ 跨表操作不在同一事务，可能部分成功
func CreateOrderAndDeductStock(ctx context.Context, req *CreateOrderReq) error {
    // 操作1: 扣库存
    err := repo.DeductStock(ctx, req.ProductID, req.Qty)
    if err != nil {
        return err
    }
    // 操作2: 创建订单 —— 如果这里失败，库存已扣但订单未创建
    err = repo.CreateOrder(ctx, req)
    if err != nil {
        return err // 库存已扣，数据不一致！
    }
    return nil
}
```

```go
// ✅ 同一事务保证原子性
func CreateOrderAndDeductStock(ctx context.Context, req *CreateOrderReq) error {
    return repo.InTx(ctx, func(tx *sql.Tx) error {
        // 同一事务内扣库存
        affected, err := repo.DeductStockTx(tx, req.ProductID, req.Qty)
        if err != nil {
            return err
        }
        if affected == 0 {
            return ErrInsufficientStock
        }
        // 同一事务内建订单
        return repo.CreateOrderTx(tx, req)
    })
}
```

---

#### `business/missing-rollback` — 补偿/回滚机制缺失

严重程度：🔴严重

检查要点：
- 部分成功时如何回滚已完成的步骤

```go
// ❌ 跨服务调用无补偿，部分成功无法回滚
func ProcessOrder(ctx context.Context, order *Order) error {
    // 步骤1: 扣库存（库存服务）
    err := inventorySvc.Deduct(ctx, order.ProductID, order.Qty)
    if err != nil {
        return err
    }
    // 步骤2: 扣款（支付服务）—— 失败时库存已扣，无法回滚
    err = paymentSvc.Charge(ctx, order.UserID, order.Amount)
    if err != nil {
        return err // 库存已扣但未付款，数据不一致！
    }
    // 步骤3: 发货（物流服务）—— 失败时库存已扣、款已付
    err = shippingSvc.CreateShipment(ctx, order.ID)
    if err != nil {
        return err // 更严重的不一致！
    }
    return nil
}
```

```go
// ✅ 带补偿机制的跨服务调用
func ProcessOrder(ctx context.Context, order *Order) error {
    // 步骤1: 扣库存
    err := inventorySvc.Deduct(ctx, order.ProductID, order.Qty)
    if err != nil {
        return fmt.Errorf("扣库存失败: %w", err)
    }

    // 步骤2: 扣款，失败则补偿库存
    err = paymentSvc.Charge(ctx, order.UserID, order.Amount)
    if err != nil {
        // 补偿：回滚库存
        if rollbackErr := inventorySvc.Restore(ctx, order.ProductID, order.Qty); rollbackErr != nil {
            // 补偿也失败，记录告警，人工介入
            log.Error("库存补偿失败",
                zap.Int64("orderID", order.ID),
                zap.Error(rollbackErr),
            )
            alertSvc.Send(ctx, AlertCritical, "库存补偿失败，需人工处理", order.ID)
        }
        return fmt.Errorf("扣款失败: %w", err)
    }

    // 步骤3: 发货，失败则补偿扣款和库存
    err = shippingSvc.CreateShipment(ctx, order.ID)
    if err != nil {
        // 补偿：退款
        if refundErr := paymentSvc.Refund(ctx, order.UserID, order.Amount); refundErr != nil {
            log.Error("退款补偿失败", zap.Int64("orderID", order.ID), zap.Error(refundErr))
            alertSvc.Send(ctx, AlertCritical, "退款补偿失败，需人工处理", order.ID)
        }
        // 补偿：回滚库存
        if restoreErr := inventorySvc.Restore(ctx, order.ProductID, order.Qty); restoreErr != nil {
            log.Error("库存补偿失败", zap.Int64("orderID", order.ID), zap.Error(restoreErr))
            alertSvc.Send(ctx, AlertCritical, "库存补偿失败，需人工处理", order.ID)
        }
        return fmt.Errorf("创建物流单失败: %w", err)
    }

    return nil
}
```

---

### 7.4 数据一致性

#### `business/dirty-data` — 读写顺序导致脏数据

严重程度：🟡警告

检查要点：
- 先读后写无锁（并发覆盖）

```go
// ❌ 先读后写无锁，并发场景下余额可能被覆盖
func AddBalance(ctx context.Context, userID int64, amount int64) error {
    user, err := repo.GetUser(ctx, userID)
    if err != nil {
        return err
    }
    // 并发时两个请求同时读到 balance=100
    // 都写入 balance=100+50=150，实际应该是 200
    user.Balance += amount
    return repo.UpdateUser(ctx, user)
}
```

```go
// ✅ 方案1: 使用原子更新（推荐）
func AddBalance(ctx context.Context, userID int64, amount int64) error {
    // UPDATE users SET balance = balance + ? WHERE id = ?
    return repo.IncrBalance(ctx, userID, amount)
}

// ✅ 方案2: 使用乐观锁
func AddBalance(ctx context.Context, userID int64, amount int64) error {
    for retries := 0; retries < 3; retries++ {
        user, err := repo.GetUser(ctx, userID)
        if err != nil {
            return err
        }
        user.Balance += amount
        // UPDATE users SET balance=?, version=version+1
        // WHERE id=? AND version=?
        affected, err := repo.UpdateUserWithVersion(ctx, user)
        if err != nil {
            return err
        }
        if affected > 0 {
            return nil
        }
        // version 不匹配，重试
    }
    return ErrOptimisticLockConflict
}
```

---

#### `business/cache-inconsistency` — 缓存与数据库不一致

严重程度：🟡警告

检查要点：
- 缓存更新时机不当
- 缓存穿透/击穿/雪崩风险

```go
// ❌ 先更新数据库再更新缓存，并发时缓存可能是旧值
func UpdateProduct(ctx context.Context, product *Product) error {
    err := repo.UpdateProduct(ctx, product)
    if err != nil {
        return err
    }
    // 问题1: 如果这里失败，缓存是旧数据
    // 问题2: 并发时，请求A更新DB后还没更新缓存，
    //        请求B更新DB并更新了缓存，
    //        然后请求A更新缓存，覆盖了B的新数据
    return cache.Set(ctx, productKey(product.ID), product, time.Hour)
}
```

```go
// ✅ 先更新数据库，再删除缓存（Cache-Aside 模式）
func UpdateProduct(ctx context.Context, product *Product) error {
    err := repo.UpdateProduct(ctx, product)
    if err != nil {
        return err
    }
    // 删除缓存，下次读取时重新加载
    if err := cache.Del(ctx, productKey(product.ID)); err != nil {
        // 缓存删除失败不影响主流程，但需要记录
        log.Warn("缓存删除失败", zap.Int64("productID", product.ID), zap.Error(err))
    }
    return nil
}

// 读取时使用 singleflight 防止缓存击穿
var sfGroup singleflight.Group

func GetProduct(ctx context.Context, id int64) (*Product, error) {
    // 1. 先查缓存
    product, err := cache.Get(ctx, productKey(id))
    if err == nil {
        return product, nil
    }

    // 2. 缓存未命中，singleflight 防止击穿
    val, err, _ := sfGroup.Do(fmt.Sprintf("product:%d", id), func() (interface{}, error) {
        p, err := repo.GetProduct(ctx, id)
        if err != nil {
            return nil, err
        }
        // 随机过期时间，防止雪崩
        ttl := time.Hour + time.Duration(rand.Intn(600))*time.Second
        _ = cache.Set(ctx, productKey(id), p, ttl)
        return p, nil
    })
    if err != nil {
        return nil, err
    }
    return val.(*Product), nil
}
```

---

#### `business/eventual-consistency` — 跨服务数据同步问题

严重程度：🟡警告

检查要点：
- 消息丢失风险
- 消息重复消费未做幂等处理

```go
// ❌ 先操作数据库再发消息，消息可能丢失
func CompleteOrder(ctx context.Context, orderID int64) error {
    err := repo.UpdateOrderStatus(ctx, orderID, StatusCompleted)
    if err != nil {
        return err
    }
    // 如果这里失败（网络抖动、进程崩溃），消息丢失
    // 下游服务（积分、统计）永远收不到通知
    return mq.Publish(ctx, "order.completed", &OrderCompletedEvent{OrderID: orderID})
}

// ❌ 消费者未做幂等，重复消费导致积分多发
func HandleOrderCompleted(ctx context.Context, event *OrderCompletedEvent) error {
    // 消息可能被重复投递，每次都加积分
    return repo.AddPoints(ctx, event.UserID, event.Points)
}
```

```go
// ✅ 使用本地消息表（Transactional Outbox）保证消息不丢
func CompleteOrder(ctx context.Context, orderID int64) error {
    return repo.InTx(ctx, func(tx *sql.Tx) error {
        // 同一事务：更新订单状态 + 写入消息表
        if err := repo.UpdateOrderStatusTx(tx, orderID, StatusCompleted); err != nil {
            return err
        }
        return repo.InsertOutboxMessageTx(tx, &OutboxMessage{
            Topic:   "order.completed",
            Payload: mustMarshal(&OrderCompletedEvent{OrderID: orderID}),
            Status:  OutboxPending,
        })
    })
    // 后台定时任务轮询 outbox 表，发送消息并标记已发送
}

// ✅ 消费者做幂等处理
func HandleOrderCompleted(ctx context.Context, event *OrderCompletedEvent) error {
    // 使用事件ID做幂等键
    processed, err := repo.IsEventProcessed(ctx, event.EventID)
    if err != nil {
        return err
    }
    if processed {
        return nil // 已处理，跳过
    }

    return repo.InTx(ctx, func(tx *sql.Tx) error {
        // 同一事务：加积分 + 标记事件已处理
        if err := repo.AddPointsTx(tx, event.UserID, event.Points); err != nil {
            return err
        }
        return repo.MarkEventProcessedTx(tx, event.EventID)
    })
}
```
