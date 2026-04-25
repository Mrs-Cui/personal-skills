# 单元测试 - 流处理器规则

## 概述

本文档基于老虎证券消息系统的技术实现详细说明和项目设计架构文档，针对 `message/handler/streamHandler` 模块的单元测试生成规则。该模块实现了基于Kafka的流处理架构，包含5阶段处理管道、FA用户合规检查、多牌照管理等核心功能。

## 流处理架构理解

### 1. Kafka流处理架构

#### 1.1 多Topic消费者架构
```
业务系统 → API Gateway → Message Service API → Kafka Message Bus
                                                        ↓
                    ┌─────────────────────────────────────┼─────────────────────────────────────┐
                    │                                     │                                     │
            ┌───────┴────────┐                   ┌───────┴────────┐                   ┌───────┴────────┐
            │ Realtime Node  │                   │ Backend Node   │                   │ Batch Node     │
            │ (验证码/紧急)   │                   │ (通知类消息)    │                   │ (营销/批量)     │
            │ ≤10秒投递      │                   │ ≤1分钟投递     │                   │ 可接受延迟      │
            └───────┬────────┘                   └───────┬────────┘                   └───────┬────────┘
                    │                                     │                                     │
            MESSAGE_TP_REALTIME=1              MESSAGE_TP_BACKEND_BUSINESS=1           MESSAGE_TP_BATCH=1
```

### 2. 发件箱5阶段处理管道

#### 2.1 完整处理流程
```
原始数据 → 数据预处理 → 数据加工 → 数据存储 → 数据过滤 → 数据交付
   ↓           ↓           ↓          ↓          ↓          ↓
 Raw Data → Preprocess → Produce → Store → Filter → Delivery
```

#### 2.2 各阶段职责
```python
async def send_control_center(*, send_id: str, delivery_type: str,
                              target_to_list: List[str], target_to_type: TargetToType, **kwargs):
    # 阶段1: 数据预处理 - 获取配置内容和用户信息
    preprocessed_send_data = await send_data_preprocess(...)
    
    # 阶段2: 数据加工 - 完善内容，补充变量
    produced_data_list = await send_data_produce(...)
    
    # 阶段3: 数据存储 - 持久化加工后的数据
    await produced_data_store(produced_data_list)
    
    # 阶段4: 数据过滤 - FA用户检查、黑名单过滤等
    passed_produced_data = await produced_data_filter(...)
    
    # 阶段5: 数据交付 - 调用第三方接口发送
    await produced_data_delivery(passed_produced_data)
```

### 3. 核心组件层次

#### 3.1 消息路由和优先级
```python
class CrmMessagePriority(str, Enum):
    EXTREMELY_HIGH = "extremely_high"  # 极高优先级 - 验证码
    HIGH = "high"                      # 高优先级 - API消息
    MEDIUM = "medium"                  # 中等优先级
    LOW = "low"                        # 低优先级 - 发件箱
    MATERIAL = 'material'              # 实时物料
    POPUP = 'popup'                    # 物料禁用

class CrmMessageSendScene(str, Enum):
    PRE_POST = "prepost"               # 预发布
    CALLBACK = "callback"              # 回调
    EMERGENCY = "emergency"            # 紧急
    API_MESSAGE = "apiMessage"         # API消息
    SEND_BOX = "sendBox"               # 发件箱
```

#### 3.2 多渠道处理器
```
BaseHandler (基础处理器)
├── SmsV2Handler (短信处理器)
├── EmailV2Handler (邮件处理器)  
├── PushV2Handler (推送处理器)
└── WhatsAppHandler (WhatsApp处理器)
```

#### 3.3 多牌照管理
```python
class AccountLicense(Enum):
    TBNZ = auto()      # 新西兰
    TBSG = auto()      # 新加坡  
    TBHK = auto()      # 香港
    TBMS = auto()      # 马来西亚
    TBAU = auto()      # 澳大利亚
    TBKIWI = auto()    # 新西兰KIWI
    USTS = auto()      # 美国
    Marsco = auto()    # Marsco
    TBNZ_AFSL = auto() # 新西兰AFSL
    UNKNOWN = auto()   # 未知牌照
```

## 流处理测试规范

### 1. Kafka流处理测试规范

**规则**: 测试Kafka消息的完整处理流程，包括消息路由、优先级处理、并发执行等

```python
class TestKafkaStreamProcessing:
    """Kafka流处理测试"""
    
    @pytest.fixture
    def kafka_message(self):
        """Kafka消息fixture"""
        message = MagicMock(spec=KafkaMessage)
        message.topic = "message_realtime"
        message.platform = "test_platform"
        message.delivery_id = "test_delivery_123"
        message.delivery_type = "sms"
        message.target_uuid = "test_uuid_123"
        message.target_content = "测试消息内容"
        message.target_channel = "captcha"
        return message
    
    @pytest.mark.asyncio
    async def test_stream_base_process_success(self, kafka_message):
        """测试StreamBase消息处理成功流程"""
        with patch('message.stream.base.JobManager.HANDLER') as mock_handlers, \
             patch('message.stream.base.StreamBase.wait_for_job_completion') as mock_wait:
            
            mock_job_detail = MagicMock()
            mock_job_detail.message_function = AsyncMock(return_value="success")
            mock_job_detail.topic_set = {"message_realtime"}
            mock_handlers = [mock_job_detail]
            
            mock_wait.return_value = None
            
            await StreamBase.process(kafka_message)
            
            mock_wait.assert_called_once()
            mock_job_detail.message_function.assert_called_once()
```

### 2. 5阶段处理管道测试规范

**规则**: 测试发件箱控制中心的完整5阶段处理流程

```python
class TestSendControlCenter:
    """发件箱控制中心测试"""
    
    @pytest.fixture
    def send_control_params(self):
        """发件箱控制参数"""
        return {
            "send_id": "test_send_123",
            "delivery_type": "email",
            "target_to_list": ["uuid1", "uuid2", "uuid3"],
            "target_to_type": TargetToType.UUID,
            "template_id": "EMAIL_001",
            "create_time": "2024-01-01 10:00:00"
        }
    
    @pytest.mark.asyncio
    async def test_complete_5_stage_pipeline(self, send_control_params):
        """测试完整的5阶段处理管道"""
        with patch('message.handler.streamHandler.send_data_preprocess') as mock_preprocess, \
             patch('message.handler.streamHandler.send_data_produce') as mock_produce, \
             patch('message.handler.streamHandler.produced_data_store') as mock_store, \
             patch('message.handler.streamHandler.produced_data_filter') as mock_filter, \
             patch('message.handler.streamHandler.produced_data_delivery') as mock_delivery:
            
            mock_preprocessed_data = MagicMock(spec=PreprocessedSendData)
            mock_produced_data_list = [MagicMock(spec=ProducedData)]
            mock_filtered_data_list = [MagicMock(spec=ProducedData)]
            
            mock_preprocess.return_value = mock_preprocessed_data
            mock_produce.return_value = mock_produced_data_list
            mock_store.return_value = None
            mock_filter.return_value = mock_filtered_data_list
            mock_delivery.return_value = None
            
            await send_control_center(**send_control_params)
            
            mock_preprocess.assert_called_once()
            mock_produce.assert_called_once()
            mock_store.assert_called_once()
            mock_filter.assert_called_once()
            mock_delivery.assert_called_once()
```

### 3. FA用户合规检查测试规范

**规则**: 测试FA用户识别和合规检查逻辑

```python
class TestFAComplianceCheck:
    """FA用户合规检查测试"""
    
    @pytest.fixture
    def fa_user_info(self):
        """FA用户信息"""
        return {
            "uuid": "fa_user_123",
            "account_id": "fa_account_456",
            "customer_id": "fa_customer_789",
            "is_fa_related": True,
            "fa_marketing_opt_out": False,
            "license": "TBHK"
        }
    
    @pytest.mark.asyncio
    async def test_fa_user_identification(self, fa_user_info):
        """测试FA用户识别"""
        with patch.object(FaAdvisorModel, 'get_user_advisor') as mock_get_advisor:
            mock_advisor = MagicMock(spec=FaAdvisorModel)
            mock_advisor.account_id = fa_user_info["account_id"]
            mock_advisor.advisor_email = "advisor@example.com"
            mock_get_advisor.return_value = mock_advisor
            
            advisor = await FaAdvisorModel.get_user_advisor(
                account_id=fa_user_info["account_id"],
                customer_id=fa_user_info["customer_id"],
                user_license="TBHK"
            )
            
            assert advisor is not None
            assert advisor.account_id == fa_user_info["account_id"]
            mock_get_advisor.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fa_user_message_filtering(self, fa_user_info):
        """测试FA用户消息过滤"""
        uuid_list = ["fa_user_123", "regular_user_456", "fa_user_789"]
        
        with patch('message.handler.streamHandler.UserMarketableInfoModel.filter_uuids') as mock_filter:
            filtered_uuids = ["regular_user_456"]  # FA用户被过滤
            mock_filter.return_value = filtered_uuids
            
            result = await filter_unmarketable_uuids("test_send_123", "1", uuid_list)
            
            assert result == filtered_uuids
            assert "fa_user_123" not in result
            mock_filter.assert_called_once()
```

### 4. 多牌照管理测试规范

**规则**: 测试多牌照环境下的数据库连接和配置管理

```python
class TestMultiLicenseManagement:
    """多牌照管理测试"""
    
    @pytest.mark.parametrize("license_type,expected_db", [
        (AccountLicense.TBNZ, "customer_db_tbnz"),
        (AccountLicense.TBSG, "customer_db_tbsg"),
        (AccountLicense.TBHK, "customer_db_tbhk"),
        (AccountLicense.TBMS, "customer_db_tbms"),
        (AccountLicense.TBAU, "customer_db_tbau"),
        (AccountLicense.USTS, "customer_db_usts"),
    ])
    @pytest.mark.asyncio
    async def test_license_database_routing(self, license_type, expected_db):
        """测试牌照对应的数据库路由"""
        with patch.object(ConnectionManager, 'customer_db') as mock_customer_db:
            mock_customer_db.return_value = MagicMock()
            
            db_pool = await license_type.customer_database_pool
            
            mock_customer_db.assert_called_once_with(license_type.name)
            assert db_pool is not None
```

### 5. UUID缓存管理测试规范

**规则**: 测试大批量UUID列表的Redis缓存管理

```python
class TestUuidCacheManagement:
    """UUID缓存管理测试"""
    
    @pytest.fixture
    def large_uuid_list(self):
        """大批量UUID列表"""
        return [f"uuid_{i:06d}" for i in range(10000)]
    
    @pytest.mark.asyncio
    async def test_get_send_box_uuid_list_success(self, large_uuid_list):
        """测试获取发件箱UUID列表成功"""
        send_id = "test_send_123"
        redis_key_number = 1
        
        with patch.object(UuidCache, 'get_uuid_by_key_number') as mock_get_uuid, \
             patch.object(UuidCache, 'clear_saved_uuid_cache') as mock_clear_cache:
            
            cached_bytes = [uuid.encode() for uuid in large_uuid_list[:5000]]
            mock_get_uuid.return_value = cached_bytes
            mock_clear_cache.return_value = None
            
            result = await get_send_box_uuid_list(send_id, redis_key_number)
            
            assert len(result) == 5000
            assert all(isinstance(uuid, str) for uuid in result)
            mock_get_uuid.assert_called_once_with(send_id, redis_key_number)
            mock_clear_cache.assert_called_once_with(send_id, redis_key_number)
```

## 流处理特定 Mock 规范

### 1. KafkaMessage Mock 模式

**规则**: Mock Kafka消息时需要包含完整的消息结构

```python
@pytest.fixture
def kafka_message_fixture(self):
    """标准Kafka消息Mock"""
    message = MagicMock(spec=KafkaMessage)
    
    # 基础信息
    message.topic = "message_realtime"
    message.platform = "test_platform"
    message.ldap = "test_user"
    
    # 投递信息
    message.delivery_id = "test_delivery_123"
    message.delivery_type = "sms"
    message.delivery_timestamp = int(time.time())
    message.task_id = "test_task_456"
    
    # 目标信息
    message.target_id = "target_123"
    message.target_type = "SMS_TEXT"
    message.target_uuid = "uuid_123"
    message.target_account_id = "account_456"
    message.target_customer_id = "customer_789"
    
    # 内容信息
    message.content_original = "您的验证码是{code}"
    message.target_content = "您的验证码是123456"
    message.target_multi_lang_content = {
        "zh_CN": "您的验证码是123456",
        "en_US": "Your verification code is 123456"
    }
    
    # 配置信息
    message.target_channel = "captcha"
    message.target_api_platform = "eps"
    message.target_template_type = "SI"
    
    return message
```

### 2. 5阶段处理管道 Mock 模式

**规则**: Mock 5阶段处理时需要保持数据类型的一致性

```python
@pytest.fixture
def mock_5_stage_pipeline(self):
    """Mock 5阶段处理管道"""
    mocks = {}
    
    # 阶段1: 数据预处理
    mock_preprocessed_data = MagicMock(spec=PreprocessedSendData)
    mock_preprocessed_data.send_id = "test_send_123"
    mock_preprocessed_data.delivery_type = "email"
    mock_preprocessed_data.target_users = [{"uuid": "user1"}, {"uuid": "user2"}]
    mock_preprocessed_data.template_content = {"subject": "测试邮件", "body": "邮件内容"}
    
    mocks['preprocess'] = patch(
        'message.handler.streamHandler.send_data_preprocess',
        new_callable=AsyncMock,
        return_value=mock_preprocessed_data
    )
    
    # 阶段2: 数据加工
    mock_produced_data = MagicMock(spec=ProducedData)
    mock_produced_data.uuid = "user1"
    mock_produced_data.content = "个性化邮件内容"
    mock_produced_data.status = "ready"
    mock_produced_data_list = [mock_produced_data]
    
    mocks['produce'] = patch(
        'message.handler.streamHandler.send_data_produce',
        new_callable=AsyncMock,
        return_value=mock_produced_data_list
    )
    
    # 阶段3: 数据存储
    mocks['store'] = patch(
        'message.handler.streamHandler.produced_data_store',
        new_callable=AsyncMock
    )
    
    # 阶段4: 数据过滤
    mock_filtered_data = MagicMock(spec=ProducedData)
    mock_filtered_data.uuid = "user1"
    mock_filtered_data.status = "filtered"
    mock_filtered_data_list = [mock_filtered_data]
    
    mocks['filter'] = patch(
        'message.handler.streamHandler.produced_data_filter',
        new_callable=AsyncMock,
        return_value=mock_filtered_data_list
    )
    
    # 阶段5: 数据交付
    mocks['delivery'] = patch(
        'message.handler.streamHandler.produced_data_delivery',
        new_callable=AsyncMock
    )
    
    return mocks
```

### 3. FA用户合规 Mock 模式

**规则**: Mock FA用户检查时需要模拟完整的合规检查流程

```python
@pytest.fixture
def mock_fa_compliance_check(self):
    """Mock FA用户合规检查"""
    mocks = {}
    
    # Mock FA顾问查询
    mock_fa_advisor = MagicMock(spec=FaAdvisorModel)
    mock_fa_advisor.account_id = "fa_account_123"
    mock_fa_advisor.customer_id = "fa_customer_456"
    mock_fa_advisor.advisor_email = "advisor@example.com"
    mock_fa_advisor.advisor_emails = ["advisor@example.com", "backup@example.com"]
    
    mocks['get_advisor'] = patch.object(
        FaAdvisorModel, 'get_user_advisor',
        new_callable=AsyncMock,
        return_value=mock_fa_advisor
    )
    
    # Mock用户分组信息查询
    mock_segment_info = {
        "logic_id": "segment_123",
        "segment_name": "高净值用户",
        "allow_fa_users": False,
        "marketing_restrictions": ["email", "sms"]
    }
    
    mocks['get_segment'] = patch(
        'message.handler.streamHandler.RequestUserProfileHandler.get_segment_info_by_logic_id',
        new_callable=AsyncMock,
        return_value=mock_segment_info
    )
    
    # Mock用户可营销性过滤
    mocks['filter_marketable'] = patch.object(
        UserMarketableInfoModel, 'filter_uuids',
        new_callable=AsyncMock,
        return_value=["regular_user_1", "regular_user_2"]  # FA用户被过滤
    )
    
    return mocks
```

### 4. 多牌照管理 Mock 模式

**规则**: Mock多牌照环境时需要模拟不同牌照的数据库连接和配置

```python
@pytest.fixture
def mock_multi_license_environment(self):
    """Mock多牌照环境"""
    mocks = {}
    
    # Mock不同牌照的数据库连接
    license_db_mapping = {
        "TBNZ": MagicMock(name="tbnz_db"),
        "TBSG": MagicMock(name="tbsg_db"),
        "TBHK": MagicMock(name="tbhk_db"),
        "TBMS": MagicMock(name="tbms_db"),
        "TBAU": MagicMock(name="tbau_db"),
        "USTS": MagicMock(name="usts_db"),
    }
    
    async def mock_customer_db(license_name):
        return license_db_mapping.get(license_name, MagicMock())
    
    mocks['customer_db'] = patch.object(
        ConnectionManager, 'customer_db',
        side_effect=mock_customer_db
    )
    
    # Mock牌照特定配置
    license_configs = {
        AccountLicense.TBHK: {
            "email_sender": "noreply@tigerbrokers.com.hk",
            "sms_signature": "【老虎证券】",
            "timezone": "Asia/Hong_Kong",
            "currency": "HKD"
        },
        AccountLicense.USTS: {
            "email_sender": "noreply@tigerbrokers.com",
            "sms_signature": "[Tiger Brokers]", 
            "timezone": "America/New_York",
            "currency": "USD"
        }
    }
    
    mocks['license_config'] = patch(
        'message.handler.streamHandler.get_license_config',
        side_effect=lambda license: license_configs.get(license, {})
    )
    
    return mocks
```

## 流处理测试检查清单

### 生成前检查
- [ ] 识别Kafka消息的主题和优先级路由
- [ ] 确定5阶段处理管道的数据流转
- [ ] 识别FA用户合规检查点
- [ ] 确定多牌照环境的配置差异
- [ ] 识别需要Mock的外部依赖（数据库、Redis、第三方服务）
- [ ] 确定异常处理和重试机制

### 生成后检查
- [ ] Kafka消息处理器有完整的流程测试
- [ ] 5阶段处理管道有端到端测试
- [ ] FA用户合规检查有独立测试
- [ ] 多牌照管理有配置验证测试
- [ ] UUID缓存管理有大批量数据测试
- [ ] 异常路径有相应的测试覆盖
- [ ] Mock配置符合实际架构规范

### 运行前检查
- [ ] 所有Mock路径指向正确的使用位置
- [ ] 异步测试标记正确（@pytest.mark.asyncio）
- [ ] 测试数据格式符合实际业务规范
- [ ] Kafka消息结构完整且正确
- [ ] FA用户和普通用户数据区分明确
- [ ] 多牌照配置数据准确

## 常见错误和解决方案

### Kafka流处理常见错误

| 错误类型 | 错误描述 | 解决方案 |
|---------|---------|---------|
| Mock路径错误 | JobManager.HANDLER Mock不生效 | 使用正确的Mock路径：`message.stream.base.JobManager.HANDLER` |
| 异步Mock错误 | message_function使用MagicMock | 使用AsyncMock：`mock_job_detail.message_function = AsyncMock()` |
| 主题过滤错误 | topic_set配置不正确 | 确保topic_set包含正确的主题名称 |
| 并发处理错误 | asyncio.gather Mock不正确 | Mock coro_log_wrapper函数 |

### 5阶段管道常见错误

| 错误类型 | 错误描述 | 解决方案 |
|---------|---------|---------|
| 数据类型不匹配 | 阶段间数据传递类型错误 | 使用正确的spec参数：`MagicMock(spec=PreprocessedSendData)` |
| 阶段调用顺序 | Mock验证调用顺序错误 | 按实际执行顺序验证：preprocess → produce → store → filter → delivery |
| 异常传播 | 阶段异常处理不正确 | 确保异常在正确的阶段抛出和捕获 |
| 参数传递 | 阶段间参数传递错误 | 验证每个阶段的输入参数是上一阶段的输出 |

### FA合规检查常见错误

| 错误类型 | 错误描述 | 解决方案 |
|---------|---------|---------|
| FA用户识别 | get_user_advisor Mock不正确 | 使用正确的返回值：`MagicMock(spec=FaAdvisorModel)` |
| 合规规则 | 用户过滤逻辑错误 | 确保FA用户在营销消息中被正确过滤 |
| 异常处理 | FA服务异常处理不当 | 实现降级处理，返回None而不是抛出异常 |
| 顾问信息 | advisor_emails格式错误 | 使用列表格式：`["advisor@example.com"]` |

### 多牌照管理常见错误

| 错误类型 | 错误描述 | 解决方案 |
|---------|---------|---------|
| 数据库路由 | 牌照数据库连接错误 | Mock ConnectionManager的customer_db和crm_db方法 |
| 配置差异 | 牌照配置不准确 | 使用实际的牌照配置数据模板 |
| 枚举值错误 | AccountLicense枚举使用错误 | 使用正确的枚举值：AccountLicense.TBHK |
| 异步属性 | database_pool属性Mock错误 | 使用property装饰器Mock异步属性 |

## 总结

基于老虎证券消息系统的实际技术架构，流处理器测试需要关注：

1. **Kafka流处理架构**: 验证多Topic消费者、消息路由、优先级处理等核心功能
2. **5阶段处理管道**: 验证发件箱控制中心的完整处理流程和数据流转
3. **FA用户合规检查**: 验证FA用户识别、合规规则、用户过滤等合规功能
4. **多牌照管理**: 验证不同牌照的数据库路由、配置管理、用户处理等功能
5. **UUID缓存管理**: 验证大批量UUID列表的Redis缓存操作
6. **异常处理机制**: 验证各环节的错误处理、重试机制、降级策略

---

**文档版本**: v2.0  
**更新时间**: 2024-12-26  
**适用范围**: message/handler/streamHandler 模块
