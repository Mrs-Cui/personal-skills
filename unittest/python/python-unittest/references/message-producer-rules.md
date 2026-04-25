# 单元测试 - 消息生产者规则

## 概述

本文档包含消息生产者（Message Producer）相关的单元测试规则，主要基于 WhatsApp 生产者重构过程中的实际经验总结。这些规则专门针对消息生产者的业务逻辑、数据预处理、Mock 配置等特定需求。

## 适用范围

- **消息生产者类**: `message/handler/streamHandler/send_data_producer/` 下的所有生产者
- **数据预处理**: 预处理数据模型和相关逻辑
- **消息渠道**: WhatsApp、邮件、短信、推送等各种消息渠道的生产者
- **配置管理**: 生产者相关的配置对象和映射关系

## 消息系统特定规范

### 1. 枚举值规范
**必须使用项目实际定义的枚举值**

```python
# ✅ 正确的枚举值
UserLanguageEnum.CHS      # 中文简体
UserLanguageEnum.CHT      # 中文繁体  
UserLanguageEnum.ENG      # 英文
TemplateCategoryEnum.WN   # WhatsApp 通知类
TemplateCategoryEnum.WM   # WhatsApp 营销类

# ❌ 错误的枚举值（不存在）
UserLanguageEnum.ZH_CN    # 不存在
UserLanguageEnum.EN_US    # 不存在
TemplateTypeEnum.EMAIL_TEMPLATE  # 不存在
```

### 2. 电话号码格式规范
**三种格式有不同用途，不能混淆**

```python
# 国家代码（用于映射查找）- 不带加号
tiger_phone.country_calling_code = "86"

# 完整电话号码（用于实际发送）- 带加号
whatsapp_send_phone = "+8613900139000"

# 纯数字格式（存储格式）- 无前缀
phone_number = "13900139000"
```

### 3. 配置对象区分规范
**API 消息和发送箱使用不同的配置对象**

```python
# API 消息配置
preprocessed_data.send_config.send_id = "test_send_id"

# 发送箱配置（注意：不是 send_config）
preprocessed_data.send_box_config.send_id = "test_send_id"
preprocessed_data.send_box_config.platform_id = "sendBox"
```

### 4. 时间和 ID 格式规范

```python
# 时间格式
created_at = "2024-01-01 00:00:00"  # 字符串格式

# ID 格式
user_id = 1                         # 整数类型
uuid = "test-uuid-123"              # 字符串类型
send_id = "test_send_id"            # 字符串类型
```

## 消息系统 Mock 配置模式

### 1. 预处理数据 Mock 模式
**针对消息生产者的预处理数据对象**

```python
# ✅ 必须包含的基础生产者属性
mock_preprocessed_data.target_to_list = []
mock_preprocessed_data.target_id_list = []
mock_preprocessed_data.uuid_to_account_id_dic = {}
mock_preprocessed_data.uuid_to_customer_id_dic = {}
mock_preprocessed_data.target_user_info_dict = {}
mock_preprocessed_data.user_license = "TBHK"
mock_preprocessed_data.template_id = "test_template_id"
mock_preprocessed_data.prefer_language = "CHS"
mock_preprocessed_data.variable_kwargs = {}
mock_preprocessed_data.channel = "api"

# WhatsApp 特定属性
mock_preprocessed_data.template_multi_lang_content = {}
mock_preprocessed_data.whatsapp_multi_lang_content = {}
```

### 2. 国家代码映射 Mock 模式
**配置管理器的国家代码映射**

```python
mock_config_manager.country_code_to_region_mapping = {
    "86": "CHN",    # 中国
    "852": "HKG",   # 香港
    "65": "SGP",    # 新加坡
    "1": "USA",     # 美国
    "44": "GBR",    # 英国
    "853": "MAC",   # 澳门
    "886": "TWN",   # 台湾
}
```

### 3. TigerPhone Mock 模式
**电话号码对象的标准 Mock 配置**

```python
mock_tiger_phone = MagicMock(spec=TigerPhone)
mock_tiger_phone.country_calling_code = "86"      # 不带加号
mock_tiger_phone.phone_number = "13900139000"     # 纯数字
mock_tiger_phone.full_phone_number = "+8613900139000"  # 带加号
mock_tiger_phone.phone_mask = "(+86)139***9000"   # 掩码格式
```

### 4. 模板内容 Mock 模式
**模板记录内容的标准配置**

```python
mock_template_content = MagicMock()
mock_template_content.language_type = "zh-CN"
mock_template_content.review_state = TemplateStatusEnum.RECORD.value
mock_template_content.special_serial_no = 0
mock_template_content.fa_switch = True
mock_template_content.is_send_broker = True
mock_template_content.is_send_eam = True
```

## 消息系统测试模板

### WhatsApp 生产者测试模板

```python
"""
WhatsApp 消息生产者单元测试模板
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List

from message.handler.streamHandler.send_data_producer.{producer_type}.{producer_name} import {ProducerClass}
from message.model.template import TemplateCategoryEnum
from message.model.user import UserLanguageEnum


class Test{ProducerClass}:
    """{ProducerClass}测试类"""
    
    @pytest.fixture
    def mock_preprocessed_data(self):
        """模拟 WhatsApp 预处理数据"""
        mock_data = MagicMock()
        
        # 基础属性
        mock_data.target_to_list = []
        mock_data.target_id_list = []
        mock_data.uuid_to_account_id_dic = {}
        mock_data.uuid_to_customer_id_dic = {}
        mock_data.target_user_info_dict = {}
        mock_data.user_license = "TBHK"
        mock_data.template_id = "test_template_id"
        mock_data.prefer_language = "CHS"
        mock_data.variable_kwargs = {}
        mock_data.channel = "api"  # 或 "sendBox"
        
        # WhatsApp 特定属性
        mock_data.template_multi_lang_content = {}
        mock_data.whatsapp_multi_lang_content = {}
        
        # 配置对象（根据生产者类型选择）
        if "api" in "{producer_type}":
            mock_data.send_config = MagicMock()
            mock_data.send_config.send_id = "test_send_id"
        else:
            mock_data.send_box_config = MagicMock()
            mock_data.send_box_config.send_id = "test_send_id"
            mock_data.send_box_config.platform_id = "sendBox"
        
        return mock_data
    
    @pytest.fixture
    def producer(self, mock_preprocessed_data):
        """创建生产者实例"""
        return {ProducerClass}(mock_preprocessed_data)
    
    @pytest.mark.asyncio
    async def test_produce_whatsapp_data_success(self, producer):
        """测试 WhatsApp 数据生产成功场景"""
        # Mock 外部依赖
        with patch('{correct_mock_path}.ConfigManager') as mock_config, \
             patch('{correct_mock_path}.TigerPhone') as mock_tiger_phone_class, \
             patch('{correct_mock_path}.redis_cache', side_effect=self.mock_redis_cache):
            
            # 配置国家代码映射
            mock_config.country_code_to_region_mapping = {
                "86": "CHN",
                "852": "HKG"
            }
            
            # 配置 TigerPhone Mock
            mock_tiger_phone = MagicMock()
            mock_tiger_phone.country_calling_code = "86"
            mock_tiger_phone.full_phone_number = "+8613900139000"
            mock_tiger_phone_class.return_value = mock_tiger_phone
            
            # 执行业务逻辑
            result = await producer.produce_whatsapp_data()
            
            # 验证结果
            assert result is not None
            mock_config.country_code_to_region_mapping.__getitem__.assert_called()
    
    @staticmethod
    def mock_redis_cache(key_pattern, ttl, value_serializer=None):
        """Mock redis_cache 装饰器"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            return wrapper
        return decorator
```

## 消息系统常见错误和解决方案

### 错误 1: 枚举值不存在
**原因**: 使用了不存在的枚举值
**解决**: 检查项目实际定义的枚举值

```python
# 检查 message/model/user.py 和 message/model/template.py
# 使用实际存在的枚举值
UserLanguageEnum.CHS  # 而不是 ZH_CN
```

### 错误 2: 电话号码格式混淆
**原因**: 混淆了三种不同的电话号码格式
**解决**: 根据用途使用正确的格式

```python
# 国家代码查找用途
country_code = "86"  # 不带加号

# 实际发送用途  
send_phone = "+8613900139000"  # 带加号

# 存储用途
store_phone = "13900139000"  # 纯数字
```

### 错误 3: 配置对象混淆
**原因**: 混淆了 send_config 和 send_box_config
**解决**: 根据消息类型选择正确的配置对象

```python
# API 消息使用 send_config
if message_type == "api":
    config = preprocessed_data.send_config

# SendBox 消息使用 send_box_config
if message_type == "sendBox":
    config = preprocessed_data.send_box_config
```

### 错误 4: 预处理数据属性缺失
**原因**: Mock 对象缺少消息系统特定的属性
**解决**: 添加所有必需的预处理数据属性

```python
# 检查 WhatsAppDataProducerMixin 或相关基类
# 添加所有必需属性
mock_data.target_to_list = []
mock_data.uuid_to_customer_id_dic = {}
# ... 其他属性
```

## 消息系统检查清单

### 生成前检查
- [ ] 确认消息类型（API vs SendBox）
- [ ] 检查使用的枚举值是否存在
- [ ] 确认电话号码格式要求
- [ ] 识别 WhatsApp 特定属性需求
- [ ] 检查模板相关依赖

### 生成后检查
- [ ] 使用正确的枚举值（CHS/CHT/ENG）
- [ ] 电话号码格式正确（三种格式区分）
- [ ] 配置对象类型正确（send_config vs send_box_config）
- [ ] 预处理数据属性完整
- [ ] 国家代码映射配置正确
- [ ] 模板内容 Mock 结构正确

---

**文档版本**: v1.0  
**创建时间**: 2024-12-25  
**适用范围**: message/handler/streamHandler/send_data_producer 模块
