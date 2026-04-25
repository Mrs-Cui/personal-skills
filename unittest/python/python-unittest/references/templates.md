# 测试模板

## 基础测试类模板

```python
"""
{模块名}的单元测试

测试目标：确保业务逻辑代码被真实执行，Mock 所有外部依赖
自动生成时间：{日期}
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from {目标模块路径} import {目标类名}


class Test{目标类名}:
    """{目标类名}测试类"""
    
    def setup_method(self):
        """测试方法设置"""
        pass
    
    @pytest.mark.asyncio
    async def test_method_success(self):
        """测试方法成功场景"""
        with patch('{Mock路径}', new_callable=AsyncMock) as mock_dep:
            mock_dep.return_value = expected_result
            
            result = await target_instance.method_name()
            
            assert result is not None
            mock_dep.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_method_failure(self):
        """测试方法失败场景"""
        with patch('{Mock路径}', new_callable=AsyncMock) as mock_dep:
            mock_dep.side_effect = Exception("错误")
            
            with pytest.raises(Exception):
                await target_instance.method_name()
```

## 数据库操作测试模板

```python
@pytest.mark.asyncio
async def test_database_query(self):
    """测试数据库查询"""
    expected = [{"id": 1, "name": "test"}]
    
    with patch.object(Model, 'get_records', new_callable=AsyncMock) as mock:
        mock.return_value = expected
        
        result = await Model.get_records({"status": "active"})
        
        assert result == expected
        mock.assert_called_once_with({"status": "active"})


@pytest.mark.asyncio
async def test_database_insert(self):
    """测试数据库插入"""
    with patch.object(Model, 'create_record', new_callable=AsyncMock) as mock:
        mock.return_value = 12345
        
        result = await Model.create_record({"name": "test"})
        
        assert result == 12345


@pytest.mark.asyncio
async def test_database_update(self):
    """测试数据库更新"""
    with patch.object(Model, 'update_by_fields', new_callable=AsyncMock) as mock:
        mock.return_value = 3  # 影响行数
        
        result = await Model.update_by_fields(
            where={"status": "pending"},
            update_fields={"status": "completed"}
        )
        
        assert result == 3
```

## HTTP 请求测试模板

```python
@pytest.mark.asyncio
async def test_http_request(self):
    """测试 HTTP 请求"""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"data": "test"})
    
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_response
    mock_context.__aexit__.return_value = None
    
    with patch('aiohttp.ClientSession.get', return_value=mock_context):
        async with aiohttp.ClientSession() as session:
            async with session.get('http://test.com') as resp:
                data = await resp.json()
                assert data == {"data": "test"}
```

## 异步上下文管理器测试模板

```python
@pytest.mark.asyncio
async def test_async_context_manager(self):
    """测试异步上下文管理器"""
    mock_resource = MagicMock()
    mock_resource.data = "test_data"
    
    async_cm = AsyncMock()
    async_cm.__aenter__.return_value = mock_resource
    async_cm.__aexit__.return_value = None
    
    with patch('module.get_resource', return_value=async_cm):
        async with get_resource() as resource:
            assert resource.data == "test_data"
```

## 装饰器测试模板

```python
def mock_redis_cache(key_pattern, ttl, value_serializer=None):
    """Mock redis_cache 装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator


@patch('target_module.redis_cache', side_effect=mock_redis_cache)
@pytest.mark.asyncio
async def test_cached_method(self, mock_cache):
    """测试带缓存装饰器的方法"""
    result = await target_object.cached_method()
    assert result is not None
```

## aiohttp Interface 测试模板

```python
@pytest.mark.asyncio
async def test_interface_get(self):
    """测试 GET 接口"""
    interface = MyInterface()
    
    mock_request = MagicMock()
    mock_request.method = 'GET'
    mock_request.path = '/api/test'
    mock_request.query = {"id": "123"}
    
    with patch.object(type(interface), 'request', 
                      new=property(lambda self: mock_request)):
        with patch.object(Handler, 'get_data', new_callable=AsyncMock) as mock:
            mock.return_value = {"data": "test"}
            
            result = await interface.get()
            
            assert result.status == 200


@pytest.mark.asyncio
async def test_interface_post(self):
    """测试 POST 接口"""
    interface = MyInterface()
    
    mock_request = MagicMock()
    mock_request.method = 'POST'
    mock_request.path = '/api/test'
    mock_request.json = AsyncMock(return_value={"name": "test"})
    
    with patch.object(type(interface), 'request',
                      new=property(lambda self: mock_request)):
        with patch.object(Handler, 'create_data', new_callable=AsyncMock) as mock:
            mock.return_value = {"id": 1}
            
            result = await interface.post()
            
            assert result.status == 200
```

## 多层 Mock 测试模板

```python
@patch.object(ConnectionManager, 'message_db_peewee', new_callable=AsyncMock)
@patch('target_module.ConfigManager')
@patch('target_module.redis_cache', side_effect=mock_redis_cache)
@patch('target_module.ExternalClient')
@pytest.mark.asyncio
async def test_complex_dependencies(self, mock_client, mock_cache, 
                                     mock_config, mock_db):
    """测试复杂依赖关系"""
    # 配置 Mock
    mock_db.execute.return_value = [{"id": 1}]
    mock_config.get_setting.return_value = "test_value"
    mock_client.call_api = AsyncMock(return_value={"status": "success"})
    
    # 执行测试
    result = await target_object.complex_method()
    
    # 验证
    assert result is not None
    mock_db.execute.assert_called_once()
    mock_client.call_api.assert_called_once()
```

## 异常测试模板

```python
@pytest.mark.asyncio
async def test_exception_handling(self):
    """测试异常处理"""
    with patch.object(Service, 'call_api', new_callable=AsyncMock) as mock:
        mock.side_effect = ConnectionError("网络错误")
        
        with pytest.raises(ConnectionError) as exc_info:
            await handler.process_request()
        
        assert "网络错误" in str(exc_info.value)


@pytest.mark.asyncio
async def test_retry_on_failure(self):
    """测试失败重试"""
    with patch.object(Service, 'call_api', new_callable=AsyncMock) as mock:
        # 前两次失败，第三次成功
        mock.side_effect = [
            ConnectionError("失败1"),
            ConnectionError("失败2"),
            {"status": "success"}
        ]
        
        result = await handler.process_with_retry()
        
        assert result == {"status": "success"}
        assert mock.call_count == 3
```

## 参数化测试模板

```python
@pytest.mark.parametrize("input_data,expected", [
    ({"status": "active"}, True),
    ({"status": "inactive"}, False),
    ({"status": ""}, False),
    ({}, False),
])
@pytest.mark.asyncio
async def test_validate_status(self, input_data, expected):
    """参数化测试状态验证"""
    result = await validator.validate_status(input_data)
    assert result == expected


@pytest.mark.parametrize("error_type,error_msg