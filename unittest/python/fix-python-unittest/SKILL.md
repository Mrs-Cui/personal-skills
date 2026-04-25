---
name: fix-python-unittest
description: 批量修复 AI 生成的 Python 单元测试中的运行错误。执行 pytest 收集所有失败，按错误类型分类（环境依赖/Mock 缺失/断言不匹配/属性不存在/签名变更等），然后逐一修复测试代码（不修改源码）。Use when 用户要求修复 Python 单测错误、pytest 执行失败需要修复、或提到 fix-python-unittest。
---

# 修复 Python 单元测试错误

## 概述

本 skill 专注于**修复已有的 AI 单元测试代码中的运行错误**，核心原则是**只修改测试文件，不修改业务源码**。

适用场景：
- `pytest` 执行后存在 FAILED 或 ERROR
- AI 生成的 `test_auto_generate/` 目录下的测试文件存在 import 错误、运行时错误
- 用户指定某个模块或目录下的测试需要修复

## 核心约束

1. **绝对不修改业务源码**（`message/` 下的非测试文件）
2. **只修改 `test_auto_generate/` 下的测试文件**
3. 修复后必须验证通过
4. 保留测试的原始意图，修复方式应尽量小幅度

---

## 错误分类体系

所有错误分为 **2 个阶段 8 大类**，每类有明确的标识特征、优先级和修复策略。

### 阶段划分

| 阶段 | 说明 | pytest 表现 |
|------|------|------------|
| **收集阶段** | import 或 fixture 初始化失败，测试根本无法运行 | `ERROR collecting ...` / `121 errors during collection` |
| **执行阶段** | 测试能运行但结果不符合预期或运行时崩溃 | `FAILED ...` / `ERROR ...` |

> 收集阶段的错误必须**最先修复**，因为它们会阻塞对应文件中的所有测试用例。

### 一级分类总览

| 大类 | 代号 | 优先级 | 阶段 | 说明 |
|------|------|--------|------|------|
| **环境依赖缺失** | `ENV` | P0 | 收集 | 缺少 Python 模块、系统依赖 |
| **Import 链路错误** | `IMP` | P0 | 收集 | 模块入口导入触发连锁 import 失败 |
| **Fixture 错误** | `FIX` | P1 | 收集/执行 | fixture setup 抛出异常（NotImplementedError 等） |
| **Mock 属性/配置缺失** | `MK` | P2 | 执行 | Mock 对象缺少源码依赖的属性或配置 |
| **断言值不匹配** | `AF` | P2 | 执行 | 测试期望值与源码实际行为不一致 |
| **Patch 目标不存在** | `PT` | P2 | 执行 | patch 了源码中不存在的函数/属性 |
| **函数签名变更** | `SIG` | P2 | 执行 | 源码新增/删除了参数，测试调用不匹配 |
| **运行时异常** | `RT` | P3 | 执行 | RecursionError、TypeError 等运行时崩溃 |

### 二级分类详情

#### ENV — 环境依赖缺失

| 子类 | 代号 | 标识特征 | 典型修复 |
|------|------|---------|---------|
| 模块缺失 | `ENV-MOD` | `ModuleNotFoundError: No module named 'xxx'` | `pip install xxx` |
| 系统库缺失 | `ENV-SYS` | `ImportError: cannot import name 'xxx'` + 系统库 | 安装系统依赖 |

#### IMP — Import 链路错误

| 子类 | 代号 | 标识特征 | 典型修复 |
|------|------|---------|---------|
| 连锁导入 | `IMP-CHAIN` | 入口 `__init__.py` 顶层 import 触发链式失败 | 修复入口 import 或安装缺失依赖 |
| 导入名变更 | `IMP-NAME` | `ImportError: cannot import name 'OldName'` | 更新测试中的 import 语句 |
| 循环导入 | `IMP-CIRC` | `ImportError: cannot import name ... (most likely due to circular import)` | 延迟导入或重构 |

#### FIX — Fixture 错误

| 子类 | 代号 | 标识特征 | 典型修复 |
|------|------|---------|---------|
| NotImplementedError | `FIX-NOTIMPL` | fixture 中实例化抽象类触发 `NotImplementedError` | 提供具体子类或 mock 抽象方法 |
| RecursionError | `FIX-RECUR` | fixture 中出现无限递归 | 检查 fixture 的 mock 是否导致循环调用 |
| 其他 fixture 异常 | `FIX-OTHER` | `ERROR ... - XxxError` | 根据具体异常分析 |

#### MK — Mock 属性/配置缺失

| 子类 | 代号 | 标识特征 | 典型修复 |
|------|------|---------|---------|
| 属性缺失 | `MK-ATTR` | `AttributeError: Mock object has no attribute 'xxx'` | 为 Mock 补充缺失属性 |
| 配置不完整 | `MK-CONF` | `KeyError: 'xxx'`（Mock 的配置字典缺少 key） | 补充 Mock 配置项 |
| 异步 Mock 错误 | `MK-ASYNC` | `object MagicMock can't be used in 'await'` | 改用 `AsyncMock` |
| Mock 路径错误 | `MK-PATH` | Mock 配置了但实际代码仍调用真实对象 | Mock 路径指向使用位置而非定义位置 |

#### AF — 断言值不匹配

| 子类 | 代号 | 标识特征 | 典型修复 |
|------|------|---------|---------|
| 值不匹配 | `AF-VALUE` | `assert X == Y`、`AssertionError: assert ... == ...` | 根据源码逻辑修正期望值 |
| 字符串不匹配 | `AF-STR` | `assert 'expected' in 'actual_message'` | 更新断言中的文案字符串 |
| 调用参数顺序 | `AF-ORDER` | `expected call not found`、参数列表顺序不同 | 修正期望的调用参数顺序 |
| 调用计数 | `AF-COUNT` | `assert X == Y` 其中 X/Y 是调用次数 | 修正期望的调用次数 |

#### PT — Patch 目标不存在

| 子类 | 代号 | 标识特征 | 典型修复 |
|------|------|---------|---------|
| 函数不存在 | `PT-FUNC` | `does not have the attribute 'xxx'`（patch 模块级函数） | 查找实际函数名并更正 patch 目标 |
| 方法不存在 | `PT-METHOD` | `does not have the attribute 'xxx'`（patch 类方法） | 查找实际方法名并更正 patch 目标 |
| 模块路径错误 | `PT-MOD` | `ModuleNotFoundError` 在 `@patch()` 中 | 更正 patch 的模块路径 |

#### SIG — 函数签名变更

| 子类 | 代号 | 标识特征 | 典型修复 |
|------|------|---------|---------|
| 缺少参数 | `SIG-MISS` | `missing N required positional argument: 'xxx'` | 补充缺失的参数 |
| 多余参数 | `SIG-EXTRA` | `takes N positional arguments but M were given` | 移除多余参数 |
| 关键字参数变更 | `SIG-KW` | `unexpected keyword argument 'xxx'` | 更新关键字参数名 |

#### RT — 运行时异常

| 子类 | 代号 | 标识特征 | 典型修复 |
|------|------|---------|---------|
| 递归溢出 | `RT-RECUR` | `RecursionError: maximum recursion depth exceeded` | 检查 mock 是否导致循环调用 |
| 类型错误 | `RT-TYPE` | `TypeError: ...` | 修正参数类型或 mock 返回值类型 |
| 其他异常 | `RT-OTHER` | 其他非预期异常 | 根据具体异常分析 |

---

## 工作流程

### Step 0: 确定测试范围和运行命令

```bash
# 默认全量运行（带覆盖率）
pytest --cov=message --cov-report=xml:coverage.xml --cov-report=html:htmlcov --cov-report=term-missing -v 2>&1

# 指定文件/目录
pytest {目标路径} -v 2>&1

# 指定测试类/函数
pytest {文件路径}::{TestClass}::{test_method} -v 2>&1
```

### Step 1: 运行测试并收集错误

运行 pytest 并将完整输出保存到临时文件：

```bash
python3 -m pytest --cov=message --cov-report=xml:coverage.xml --cov-report=term-missing -v 2>&1 > /tmp/pytest_output.txt
echo "Exit code: $?"
```

**要求**：完整捕获 stdout + stderr，不要截断输出。

### Step 2: 解析、分类并展示错误

从测试输出中提取所有失败信息，按分类体系进行归类。

#### 解析步骤

1. **提取收集阶段错误**：查找 `errors during collection` 和 `ERROR collecting` 行
2. **提取执行阶段 FAILED**：查找 `FAILED ...` 行，提取测试函数名和错误摘要
3. **提取执行阶段 ERROR**：查找 `ERROR ...` 行（非 collecting），提取错误类型
4. **按错误特征归入分类代号**（对照上方分类表）
5. **按目录层级聚合统计**

#### 解析命令参考

```bash
# 统计错误根因（收集阶段）
grep -E "^E " /tmp/pytest_output.txt | sort | uniq -c | sort -rn

# 列出所有 FAILED 测试
grep "^FAILED" /tmp/pytest_output.txt

# 列出所有 ERROR 测试
grep "^ERROR" /tmp/pytest_output.txt

# 按目录分类统计
grep "^FAILED\|^ERROR" /tmp/pytest_output.txt | awk -F'/' '{...}' | sort | uniq -c | sort -rn
```

#### 展示格式：分类报告

```
## 错误分类报告

### 总览看板

| 指标 | 值 |
|------|---|
| 总测试数 | N |
| 通过 | X |
| 失败 (FAILED) | Y |
| 错误 (ERROR) | Z |
| 跳过 (SKIPPED) | S |

### 按大类分布

| 大类 | 代号 | 数量 | 优先级 | 子类分布 |
|------|------|------|--------|---------|
| 环境依赖缺失 | ENV | 121 | P0 | ENV-MOD(121) |
| Mock 属性缺失 | MK | 17 | P2 | MK-ATTR(17) |
| 断言值不匹配 | AF | 13 | P2 | AF-VALUE(10), AF-STR(3) |
| ... | ... | ... | ... | ... |

### 按目录详情

#### test_auto_generate/unit/handler/ （N 个错误）

| # | 代号 | 测试函数 | 错误摘要 | 修复方案 |
|---|------|---------|---------|---------|
| 1 | MK-ATTR | test_xxx | Mock 缺少 tiger_profile 属性 | 补充属性 |
| 2 | PT-FUNC | test_yyy | 模块无 simple_query_xxx | 更正 patch 目标 |
```

### Step 3: 按优先级逐个修复

修复顺序：**P0 → P1 → P2 → P3**。

在同一优先级内：
- **ENV** 最优先（解除大批量阻塞）
- **IMP** 其次（修复 import 链路）
- **FIX** 再次（修复 fixture 解除 ERROR）
- **MK/AF/PT/SIG** 按文件聚合修复（减少文件切换）

#### 3.1 分析根因

1. **读取测试文件**：定位出错的测试函数
2. **读取源码文件**：理解被测函数的签名、参数要求和行为逻辑（只读不改）
3. **比对**：判断测试代码与源码的不一致之处

#### 3.2 确定修复策略

##### ENV — 环境依赖缺失

```bash
# 安装缺失的 Python 模块
pip install {module_name}
```

> 如果缺失模块是项目私有或不适合在测试环境安装，考虑在测试文件中 mock 掉该 import。

##### IMP — Import 链路错误

```python
# 场景：__init__.py 顶层 import 触发连锁失败
# 分析 import 链路，找到根因模块
# 方案 1：安装缺失依赖
# 方案 2：测试文件中 mock.patch 相关 import
# 方案 3：修改测试文件的 import 方式
```

##### FIX — Fixture 错误

```python
# ❌ fixture 实例化了抽象类
@pytest.fixture
def producer():
    return WhatsAppApiMsgDataProducer()  # 抽象方法未实现

# ✅ mock 掉抽象方法
@pytest.fixture
def producer():
    with patch.multiple(WhatsAppApiMsgDataProducer,
                        __abstractmethods__=set()):
        return WhatsAppApiMsgDataProducer()
```

##### MK — Mock 属性缺失

```python
# ❌ Mock 对象缺少源码依赖的属性
mock_user = MagicMock()
result = handler.process(mock_user)  # AttributeError: 'Mock' has no attribute 'tiger_profile'

# ✅ 补充所有必需属性
mock_user = MagicMock()
mock_user.tiger_profile = MagicMock()
mock_user.tiger_profile.language = 'CHS'
```

##### AF — 断言值不匹配

```python
# ❌ 期望值与源码行为不一致
assert result == UserLanguageEnum.CHS  # 源码实际返回 ENG

# ✅ 阅读源码逻辑，修正期望值
assert result == UserLanguageEnum.ENG
```

```python
# ❌ 字符串断言不匹配（源码错误提示语已变更）
assert '发件箱渠道配置错误' in error_msg

# ✅ 更新为实际的错误信息
assert '发件箱渠道与delivery_info渠道不符' in error_msg
```

##### PT — Patch 目标不存在

```python
# ❌ patch 了不存在的函数名
@patch('message.handler.post_search.simple_query_delivery_target_index')
def test_xxx(self, mock_query):
    pass

# ✅ 查找实际函数名
@patch('message.handler.post_search.query_delivery_target_index')
def test_xxx(self, mock_query):
    pass
```

##### SIG — 函数签名变更

```python
# ❌ 源码新增了必需参数
result = fa_handler._request_fa_advisor_api(url, headers)

# ✅ 补充缺失的参数
result = fa_handler._request_fa_advisor_api(url, headers, params={})
```

##### RT — 运行时异常

```python
# ❌ mock 导致无限递归
@patch('module.func')
def test_xxx(self, mock_func):
    mock_func.side_effect = lambda *args: module.func(*args)  # 循环调用

# ✅ 提供具体返回值
@patch('module.func')
def test_xxx(self, mock_func):
    mock_func.return_value = expected_result
```

#### 3.3 执行修复

使用 Edit 工具修改测试文件。修改时遵循：

- **最小修改原则**：只改必须改的部分
- **保留测试意图**：修复方式不应改变测试的验证目标
- **保持代码风格**：与原测试文件的风格一致
- **Mock 路径准确**：Mock 路径指向使用位置，不是定义位置

#### 3.4 增量验证

每修完一个文件（或一批相关错误）后，立即运行验证：

```bash
pytest {修复的测试文件} -v 2>&1
```

- **通过** → 继续下一个错误
- **仍失败** → 重新分析，最多重试 3 次
- **3 次后仍失败** → 记录为"未解决"，继续修复其他错误

**重要**：
- 修复 ENV/IMP 错误（P0）后，需要重新运行整个测试集，因为大量之前被阻塞的测试会首次执行，可能暴露新的错误
- 新出现的错误需要归类后加入待修复列表

### Step 4: 全量验证

所有错误修复完成后，重新运行完整测试：

```bash
# 全量运行（带覆盖率）
python3 -m pytest --cov=message --cov-report=xml:coverage.xml --cov-report=term-missing -v 2>&1

# 指定范围
pytest {目标路径} -v 2>&1
```

### Step 5: 输出修复报告

```
## 修复报告

### 总览

| 指标 | 值 |
|------|---|
| 原始错误数 | M |
| 已修复 | X |
| 未解决 | Y |

### 修复前 → 修复后对比

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| PASSED | 2855 | 2901 |
| FAILED | 46 | 0 |
| ERROR | 7 | 0 |

### 修复详情

| # | 文件 | 测试函数 | 错误代号 | 修复方式 | 状态 |
|---|------|---------|---------|---------|------|
| 1 | test_language.py | test_default_chs | MK-ATTR | 补充 tiger_profile 属性 | ✅ |
| 2 | test_post_search.py | test_time_limit | PT-FUNC | 更正 patch 函数名 | ✅ |
| 3 | test_xxx.py | test_yyy | AF-VALUE | 未解决（源码逻辑不明） | ❌ |

### 未解决的问题

{对每个未解决的问题，说明代号、原因和建议}
```

---

## 常见修复模式速查

### 模式 1：Mock 对象属性缺失（MK-ATTR）

```python
# ❌ Mock 缺少嵌套属性
mock_obj = MagicMock()
# source code accesses: obj.tiger_profile.language

# ✅ 补充完整属性链
mock_obj = MagicMock()
mock_obj.tiger_profile = MagicMock()
mock_obj.tiger_profile.language = 'CHS'

# 或使用 spec 自动约束
mock_obj = MagicMock(spec=RealClass)
```

### 模式 2：Mock 配置字典缺少 Key（MK-CONF）

```python
# ❌ 配置 mock 不完整
mock_config = {'timeout': 30}
# source code accesses: config['host']  →  KeyError

# ✅ 补充所有必需 key
mock_config = {'timeout': 30, 'host': 'http://test-host'}
```

### 模式 3：异步方法用 MagicMock（MK-ASYNC）

```python
# ❌
mock_handler.get_data = MagicMock(return_value=data)
await mock_handler.get_data()  # TypeError: can't be used in 'await'

# ✅
mock_handler.get_data = AsyncMock(return_value=data)
```

### 模式 4：patch 目标函数名不存在（PT-FUNC）

```python
# ❌ 函数已重命名或不存在
@patch('message.handler.post_search.simple_query_delivery_target_index')

# ✅ 查找实际函数名
# 1. 读取 message/handler/post_search.py
# 2. 搜索相关函数定义
# 3. 更正 patch 目标
@patch('message.handler.post_search.query_delivery_target_index')
```

### 模式 5：断言字符串过时（AF-STR）

```python
# ❌ 源码错误信息已变更
assert '发件箱渠道配置错误' in response['msg']

# ✅ 读取源码找到实际错误信息
assert '发件箱渠道与delivery_info渠道不符' in response['msg']
```

### 模式 6：函数新增必需参数（SIG-MISS）

```python
# ❌ 源码新增了 params 参数
result = handler._request_api(url, headers)
# TypeError: missing 1 required positional argument: 'params'

# ✅ 阅读源码确认新参数的含义并补充
result = handler._request_api(url, headers, params={})
```

### 模式 7：参数调用顺序不匹配（AF-ORDER）

```python
# ❌ 断言期望的参数顺序与实际不同
mock_func.assert_called_once_with(['123', '456', '789'])
# actual: mock_func(['123', '789', '456'])

# ✅ 方案 1: 使用 assert_called_once()  + 手动检查（忽略顺序）
mock_func.assert_called_once()
actual_args = mock_func.call_args[0][0]
assert set(actual_args) == {'123', '456', '789'}

# ✅ 方案 2: 修正期望顺序
mock_func.assert_called_once_with(['123', '789', '456'])
```

### 模式 8：Fixture 实例化抽象类（FIX-NOTIMPL）

```python
# ❌ 直接实例化含抽象方法的类
@pytest.fixture
def producer():
    return WhatsAppProducer()  # NotImplementedError

# ✅ 方案 1: 使用 patch.multiple 清除抽象方法集
@pytest.fixture
def producer():
    with patch.multiple(WhatsAppProducer, __abstractmethods__=set()):
        instance = WhatsAppProducer()
        return instance

# ✅ 方案 2: 创建测试用子类
class ConcreteProducer(WhatsAppProducer):
    def abstract_method(self):
        return None

@pytest.fixture
def producer():
    return ConcreteProducer()
```

### 模式 9：递归溢出（RT-RECUR）

```python
# ❌ mock side_effect 导致循环
@patch('module.func')
def test_xxx(self, mock_func):
    mock_func.side_effect = lambda x: module.func(x)  # 无限递归

# ✅ 直接返回期望值
@patch('module.func')
def test_xxx(self, mock_func):
    mock_func.return_value = expected_result
```

---

## 注意事项

1. **不修改源码**：最核心约束。即使源码有明显 bug，也只修改测试代码绕过问题，并在报告中标注
2. **理解测试意图**：修复前务必理解原测试想验证什么，修复后的测试应保持相同的验证目标
3. **Mock 路径准确**：Mock 路径必须指向**使用位置**，不是定义位置。查看目标文件的 import 语句确定正确路径
4. **异步方法用 AsyncMock**：所有 `async def` 方法必须用 `AsyncMock`，普通方法用 `MagicMock`
5. **增量修复**：优先修复 P0 错误（ENV/IMP），因为它们会阻塞大批量测试的运行
6. **连锁暴露效应**：修复 P0 后可能暴露大量之前被掩盖的 P2/P3 错误，需要多轮迭代
7. **并行修复**：不同文件的错误互不影响，可以使用多个 Agent 并行修复不同文件
8. **保持幂等**：修复后的测试应在任何环境下都能通过，不依赖外部服务或特定网络环境
