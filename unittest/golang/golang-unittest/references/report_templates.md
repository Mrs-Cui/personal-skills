# 输出报告模板

完成后根据输入类型输出以下信息。

## 文件模式报告

```
## 测试生成报告

### 目标
- 源文件：xxx.go
- 测试文件：xxx_ai_test.go

### 分片信息（仅大文件显示）
- 触发原因：文件超过 1000 行（实际 {n} 行）
- 分组数量：{m} 组
- Group 1 (_pkg_): NewOrderSrv, getAdminName, getAssetLevel (341 行)
- Group 2 (OrderSrv_group1): GetConfig, GetBelongQuery, ToFilter, Search ... (792 行)
- Group 3 (OrderSrv_group2): QueryRemarkInfo, AllocateUsers ... (794 行)
- ...

### 覆盖率
- 目标：80%
- 实际：85%
- 状态：达标

### 测试用例
| 函数 | 测试数 | 覆盖分支 |
|------|--------|----------|
| FuncA | 5 | 正常流程、边界条件、错误处理 |
| FuncB | 3 | 空输入、正常输入、大数据 |

### 迭代历史
- Group 1: 第1轮通过
- Group 2: 第1轮编译错误，第2轮通过
- Group 3: 第1轮通过
- Coverage 第1轮: 72% → 补充 Group 2 的 AllocateUsers
- Coverage 第2轮: 85% 达标
```

## 目录模式报告

```
## 测试生成报告（目录模式）

### 目标
- 源目录：internal/services/order/
- 文件数量：12 个 .go 文件

### 文件处理明细
| 文件 | 行数 | 是否分片 | 分组数 | 函数数 | 状态 |
|------|------|---------|--------|--------|------|
| order.go | 4053 | 是 | 6 | 65 | 完成 |
| common_srv.go | 520 | 否 | - | 12 | 完成 |
| helper.go | 180 | 否 | - | 5 | 完成 |
| ... | ... | ... | ... | ... | ... |

### 覆盖率
- 目标：80%
- 实际（整体）：78%
- 未达标文件：common_srv.go (65%)
- 状态：部分达标

### 迭代历史
- order.go: 6 组全部通过，Coverage 第1轮 82% 达标
- common_srv.go: 第1轮通过，Coverage 65% → 补充后 81% 达标
- ...
```

## Git diff 模式报告

```
## 测试生成报告（Git diff 模式）

### 目标
- diff 基准：main..HEAD
- 涉及文件：3 个
- 涉及函数：8 个

### 变更函数明细
| 文件 | 函数 | 变更类型 | 行数 | 是否分片 |
|------|------|---------|------|---------|
| order.go | GetConfig | 修改 | 77 | 否（总计 320 行） |
| order.go | Search | 修改 | 145 | 否 |
| order.go | NewSearch | 新增 | 98 | 否 |
| payment.go | CreateOrder | 新增 | 850 | 是（2 组） |
| payment.go | ValidateOrder | 新增 | 120 | 是 |
| ... | ... | ... | ... | ... |

### 增量覆盖率
- 目标：80%
- 增量覆盖率：85.0%（272/320 可执行新增行）
- 状态：达标

### 增量覆盖率文件明细
| 文件 | 新增行 | 可执行行 | 已覆盖 | 未覆盖 | 覆盖率 |
|------|--------|---------|--------|--------|--------|
| order.go | 320 | 200 | 180 | 20 | 90.0% |
| payment.go | 130 | 120 | 92 | 28 | 76.7% |

### 迭代历史
- order.go (3 函数): 第1轮通过
- payment.go (Group 1): 第1轮编译错误，第2轮通过
- payment.go (Group 2): 第1轮通过
- 增量覆盖率第1轮: 85.0% 达标
```
