# 单元测试问题索引

按错误关键字快速定位解决方案。

## 快速索引

| 错误关键字 | 问题 | 跳转 |
|-----------|------|------|
| `patch`, `mock not working` | Mock 路径不生效 | [T001](#t001) |
| `can't be used in 'await'` | 异步 await 错误 | [T002](#t002) |
| `coroutine was never awaited` | 协程未等待 | [T003](#t003) |
| `has no attribute` | Mock 属性缺失 | [T004](#t004) |
| `can't set attribute` | 只读属性错误 | [T005](#t005) |
| `reified property` | aiohttp reified 错误 | [T006](#t006) |
| `database are different` | 数据库连接错误 | [T007](#t007) |
| `could not get source code` | Fixture 源码错误 | [T008](#t008) |
| `redis_cache`, `decorator` | 装饰器 Mock 失败 | [T009](#t009) |
| `ConfigManager`, `class level` | 类级别配置 | [T010](#t010) |

---

## T001

**Mock 路径不生效**

```
Mock 配置了但实际代码仍然调用真实对象
```

**修复**: Mock 路径指向使用位置，不是定义位置

```python
# ❌ @patch('message.common.config.ConfigManager')
# ✅ @patch('message.handler.email.ConfigManager')
```

---

## T002

**异步 await 错误**

```
TypeError: object MagicMock can't be used in 'await' expression
```

**修复**: 异步方法使用 AsyncMock

```python
# ❌ mock_method = MagicMock(return_value=data)
# ✅ mock_method = AsyncMock(return_value=data)

# 或
with patch.object(Handler, 'method', new_callable=AsyncMock) as mock:
    mock.return_value = data
```

---

## T003

**协程未等待**

```
RuntimeWarning: coroutine 'xxx' was never awaited
```

**修复**: 添加 await 关键字

```python
# ❌ result = handler.async_method()
# ✅ result = await handler.async_method()
```

---

## T004

**Mock 属性缺失**

```
AttributeError: Mock object has no attribute 'xxx'
```

**修复**: 为 Mock 对象添加所有必需属性

```python
mock_obj = MagicMock()
mock_obj.required_attr1 = "value1"
mock_obj.required_attr2 = "value2"
mock_obj.nested.attr = "nested_value"
```

---

## T005

**只读属性错误**

```
AttributeError: can't set attribute
```

**原因**: 尝试直接设置只读属性（property）

**修复方案 1**: 使用 patch.object 和 property

```python
# ❌ interface.request = mock_request

# ✅
with patch.object(type(interface), 'request', 
                  new=property(lambda self: mock_request)):
    result = await interface.get()
```

**修复方案 2**: 使用 pytest fixture（复杂场景）

```python
@pytest.fixture
def mock_limiter():
    limiter = MagicMock()
    limiter.enable = True
    limiter.check_rate_limit = AsyncMock(return_value=(True, ""))
    return limiter
```

**要点**: 只读属性必须在类级别 mock：`patch.object(type(instance), 'attr', ...)`

---

## T006

**aiohttp reified 错误**

```
AttributeError: reified property is read-only
```

**原因**: aiohttp 的 `reified` 装饰器使属性在首次访问后变为只读

**修复**: 使用 MagicMock 替代 make_mocked_request

```python
# ❌
mocked_request = make_mocked_request('POST', '/path')
mocked_request.query = {}  # 报错

# ✅
mocked_request = MagicMock()
mocked_request.method = 'POST'
mocked_request.path = '/path'
mocked_request.query = {}
mocked_request.json = AsyncMock(return_value={})
```

**选择指南**:

| 场景 | 推荐方案 |
|------|---------|
| 只读取 request 属性 | `make_mocked_request` |
| 需要设置 query/json | `MagicMock` |
| 复杂 request 行为 | `MagicMock` |

---

## T007

**数据库连接错误**

```
AssertionError: Error, query's database and manager's database are different
```

**修复**: 直接 Mock 模型方法，避免底层连接 Mock

```python
# ✅
with patch.object(MyModel, 'get_records', new_callable=AsyncMock) as mock:
    mock.return_value = [{"id": 1}]
    result = await MyModel.get_records(params)
```

---

## T008

**Fixture 源码错误**

```
OSError: could not get source code
```

**修复**: 使用 setup_method 替代 @pytest.fixture(autouse=True)

```python
# ❌
class TestMyClass:
    @pytest.fixture(autouse=True)
    def setup_test(self):
        yield

# ✅
class TestMyClass:
    def setup_method(self):
        pass
    
    def teardown_method(self):
        pass
```

---

## T009

**装饰器 Mock 失败**

```
装饰器（如 redis_cache）Mock 后函数行为异常
```

**修复**: 返回装饰器工厂函数

```python
def mock_redis_cache(key_pattern, ttl, value_serializer=None):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator

@patch('target_module.redis_cache', side_effect=mock_redis_cache)
async def test_method(self, mock_cache):
    pass
```

---

## T010

**类级别配置**

```
类定义时读取配置，方法级 Mock 无效
```

**修复**: 使用模块级 Mock（类装饰器）

```python
# ❌
class TestMyClass:
    @patch('module.ConfigManager')
    def test_method(self, mock_config):
        pass

# ✅
@patch('module.ConfigManager')
class TestMyClass:
    def test_method(self, mock_config):
        mock_config.api_config.get.side_effect = lambda key, default=None: {
            'service': {'host': 'http://test'}
        }.get(key, default)
```

---

## 新问题记录

遇到新问题时按此格式添加：

```markdown
## TXXX

**问题标题**

```
错误信息
```

**修复**: 解决方案描述

```python
# 代码示例
```
```
