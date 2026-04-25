# 异步测试 Mock 配置规范

## 目录

- [Mock 类型选择](#mock-类型选择)
- [项目特定异步模式](#项目特定异步模式)
- [数据库操作 Mock](#数据库操作-mock)
- [HTTP 请求 Mock](#http-请求-mock)
- [常见错误修复](#常见错误修复)

---

## Mock 类型选择

### 快速判断

```python
# async def → AsyncMock  |  def → MagicMock
async def get_data(self): ...   # → AsyncMock
def validate(self): ...         # → MagicMock
```

### 类方法 vs 实例方法

```python
# 类方法调用: ClassName.method()
with patch.object(MyModel, 'get_records', new_callable=AsyncMock) as mock:
    mock.return_value = data
    result = await MyModel.get_records(params)

# 实例方法调用: instance.method()
with patch('module.ClassName') as MockClass:
    mock_instance = MockClass.return_value
    mock_instance.method = AsyncMock(return_value=data)
    result = await ClassName().method()
```

### 异步属性 Mock

```python
# 异步属性需要 new_callable=AsyncMock
@patch.object(ConnectionManager, 'message_db_peewee', new_callable=AsyncMock)
async def test_db_operation(self, mock_db):
    mock_db.execute.return_value = [{"id": 1}]
```

---

## 项目特定异步模式

### 必须用 AsyncMock

| 模式 | 示例 |
|------|------|
| Handler 查询 | `*Handler.get_*()` |
| 数据库操作 | `*Model.save_*()`, `*Model.get_*()` |
| 网络请求 | `*Client.request_*()` |
| Redis 操作 | `RedisHelper.*()` |
| Kafka 流处理 | `*Stream.*()` |

### 通常用 MagicMock

| 模式 | 示例 |
|------|------|
| 配置验证 | `*Client.check_*()`, `*Client.validate_*()` |
| 工具函数 | `*Util.*()` (除非明确异步) |
| 配置读取 | `*Config.*()` |
| 枚举常量 | `*Enum.*` |

---

## 数据库操作 Mock

**推荐方式**：直接 Mock 模型方法，避免底层 ORM Mock

```python
# ✅ 推荐：Mock 模型方法
with patch.object(MyModel, 'get_records', new_callable=AsyncMock) as mock:
    mock.return_value = [{"id": 1}]

# ❌ 避免：底层 ORM Mock（容易导致协程泄漏）
with patch('peewee_async.Manager') as mock_manager:
    ...
```

> 完整的查询/插入/更新模板见 `templates.md` 的"数据库操作测试模板"

---

## HTTP 请求 Mock

### aiohttp ClientSession

```python
@pytest.mark.asyncio
async def test_http_get(self):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"data": "test"})
    
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_response
    mock_context.__aexit__.return_value = None
    
    with patch('aiohttp.ClientSession.get', return_value=mock_context):
        # 测试代码...
```

---

## 常见错误修复

### TypeError: object X can't be used in 'await' expression

**原因**：异步方法使用了 MagicMock

**修复**：
```python
# ❌ 错误
with patch.object(Handler, 'async_method', return_value=data):
    result = await Handler.async_method()  # TypeError!

# ✅ 正确
with patch.object(Handler, 'async_method', new_callable=AsyncMock) as mock:
    mock.return_value = data
    result = await Handler.async_method()
```

### RuntimeWarning: coroutine was never awaited

**原因**：缺少 await 关键字

**修复**：
```python
# ❌ 错误
result = handler.async_method()

# ✅ 正确
result = await handler.async_method()
```

---

## 必需导入

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
```
