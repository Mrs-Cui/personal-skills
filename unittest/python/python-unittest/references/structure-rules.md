# 单元测试结构和组织规则

## 概述

本文档规定了在 `test_auto_generate` 目录中生成和组织单元测试的标准结构和命名规范，确保测试代码的一致性、可维护性和可发现性。

## 目录结构规范

### 1. 顶层目录结构

```
test_auto_generate/
├── __init__.py                    # 包初始化文件
├── conftest.py                    # 全局 pytest 配置和 fixtures
├── README.md                      # 测试目录说明文档
│
├── unit/                          # 单元测试（主要测试目录）
├── integration/                   # 集成测试
├── fixtures/                      # 测试数据和 Mock 对象
├── common/                        # 通用测试工具和基类
├── templates/                     # 测试代码模板
├── tools/                         # 测试辅助工具
└── examples/                      # 测试示例和用法演示
```

### 2. 单元测试目录结构 (`unit/`)

**规则**: 单元测试目录结构必须与 `message/` 源代码目录结构保持一致

```
test_auto_generate/unit/
├── __init__.py
├── common/                        # 对应 message/common/
│   ├── __init__.py
│   ├── test_config.py            # 测试 message/common/config.py
│   ├── test_connection.py        # 测试 message/common/connection.py
│   └── test_util_*.py            # 测试 message/common/util*.py
│
├── model/                         # 对应 message/model/
│   ├── __init__.py
│   ├── test_base.py              # 测试 message/model/base.py
│   ├── test_user.py              # 测试 message/model/user.py
│   └── test_template.py          # 测试 message/model/template.py
│
├── handler/                       # 对应 message/handler/
│   ├── __init__.py
│   ├── test_base.py              # 测试 message/handler/base.py
│   └── streamHandler/            # 对应 message/handler/streamHandler/
│       ├── __init__.py
│       └── send_data_producer/   # 对应具体的生产者目录
│           ├── __init__.py
│           ├── api_msg_producer/
│           │   ├── __init__.py
│           │   └── test_api_msg_whatsapp_producer.py
│           └── send_box_producer/
│               ├── __init__.py
│               ├── test_send_box_whatsapp_producer.py
│               └── test_send_box_whatsapp_producer_simple.py
│
├── interface/                     # 对应 message/interface/
│   ├── __init__.py
│   ├── test_public.py            # 测试 message/interface/public.py
│   └── test_internal.py          # 测试 message/interface/internal.py
│
├── service/                       # 对应 message/service/
│   ├── __init__.py
│   └── test_*.py                 # 各种服务测试
│
└── stream/                        # 对应 message/stream/
    ├── __init__.py
    ├── test_base.py              # 测试 message/stream/base.py
    └── test_*.py                 # 各种流处理器测试
```

## 文件命名规范

### 1. 测试文件命名

**规则**: 测试文件名必须以 `test_` 开头，后跟被测试的源文件名

```python
# 源文件: message/handler/email_handler.py
# 测试文件: test_auto_generate/unit/handler/test_email_handler.py

# 源文件: message/model/user.py  
# 测试文件: test_auto_generate/unit/model/test_user.py

# 源文件: message/common/config.py
# 测试文件: test_auto_generate/unit/common/test_config.py
```

### 2. 特殊情况命名

**多版本文件**:
```python
# 源文件: message/handler/email_handler_v2.py
# 测试文件: test_auto_generate/unit/handler/test_email_handler_v2.py
```

**复杂模块的多测试文件**:
```python
# 主测试文件
test_send_box_whatsapp_producer.py

# 简化版本测试文件  
test_send_box_whatsapp_producer_simple.py

# 特定场景测试文件
test_send_box_whatsapp_producer_error_handling.py
```

### 3. 测试类命名

**规则**: 测试类名必须以 `Test` 开头，后跟被测试的类名

```python
# 被测试类: WhatsAppSendBoxDataProducer
# 测试类: TestWhatsAppSendBoxDataProducer

# 被测试类: EmailHandler
# 测试类: TestEmailHandler

# 被测试类: UserModel
# 测试类: TestUserModel
```

### 4. 测试方法命名

**规则**: 测试方法名必须以 `test_` 开头，使用描述性命名

```python
# 格式: test_{method_name}_{scenario}_{expected_result}
def test_get_target_send_phone_success_with_country_mapping(self):
    """测试根据国家代码成功获取目标发送手机号"""

def test_send_email_failure_invalid_address(self):
    """测试发送邮件失败 - 无效邮箱地址"""

def test_create_user_success_with_valid_data(self):
    """测试创建用户成功 - 有效数据"""
```

## 目录创建规则

### 1. 自动目录创建

**规则**: 生成测试文件时，必须自动创建对应的目录结构

```python
# 示例：为 message/handler/email/email_sender.py 生成测试
# 需要创建的目录结构：
test_auto_generate/unit/handler/email/
├── __init__.py
└── test_email_sender.py
```

### 2. __init__.py 文件

**规则**: 每个测试目录都必须包含 `__init__.py` 文件

```python
# test_auto_generate/unit/handler/email/__init__.py
"""
邮件处理器测试模块

包含邮件相关的所有测试用例：
- 邮件发送测试
- 邮件模板测试  
- 邮件配置测试
"""
```

### 3. 目录级别限制

**规则**: 测试目录层级不应超过源代码目录层级

```python
# ✅ 正确：层级对应
# 源码: message/handler/streamHandler/send_data_producer/api_msg_producer/
# 测试: test_auto_generate/unit/handler/streamHandler/send_data_producer/api_msg_producer/

# ❌ 错误：测试目录层级过深
# 测试: test_auto_generate/unit/handler/streamHandler/send_data_producer/api_msg_producer/whatsapp/specific/
```

## 测试发现和运行规范

### 1. 测试发现模式

**规则**: 使用标准的 pytest 发现模式

```bash
# 运行所有单元测试
pytest test_auto_generate/unit/

# 运行特定模块的测试
pytest test_auto_generate/unit/handler/

# 运行特定文件的测试
pytest test_auto_generate/unit/handler/test_email_handler.py

# 运行特定测试类
pytest test_auto_generate/unit/handler/test_email_handler.py::TestEmailHandler

# 运行特定测试方法
pytest test_auto_generate/unit/handler/test_email_handler.py::TestEmailHandler::test_send_email_success
```

### 2. 测试标记规范

**规则**: 使用 pytest 标记对测试进行分类

```python
import pytest

class TestEmailHandler:
    
    @pytest.mark.unit
    def test_send_email_success(self):
        """单元测试标记"""
        pass
    
    @pytest.mark.integration  
    def test_email_service_integration(self):
        """集成测试标记"""
        pass
    
    @pytest.mark.slow
    def test_bulk_email_sending(self):
        """慢速测试标记"""
        pass
    
    @pytest.mark.external
    def test_external_email_api(self):
        """外部依赖测试标记"""
        pass
```

## 质量控制规范

### 1. 测试文件质量检查

**规则**: 每个生成的测试文件必须通过以下检查

```python
QUALITY_CHECKLIST = [
    "文件路径符合目录结构规范",
    "文件名符合命名规范", 
    "测试类名符合命名规范",
    "测试方法名符合命名规范",
    "包含必要的导入语句",
    "包含测试类文档字符串",
    "包含测试方法文档字符串",
    "至少包含一个测试方法",
    "能够通过语法检查",
    "能够被 pytest 发现和运行",
    "Mock 配置正确，避免读取真实配置文件",
]
```

## 总结

遵循这些结构和组织规则可以确保：

1. **一致性**: 所有测试文件都遵循统一的结构和命名规范
2. **可发现性**: 测试文件易于查找和定位
3. **可维护性**: 清晰的目录结构便于维护和扩展
4. **可运行性**: 符合 pytest 的发现和运行机制
5. **可扩展性**: 支持新的测试类型和测试域的添加

---

**文档版本**: v1.0  
**创建时间**: 2024-12-25  
**适用范围**: test_auto_generate 目录中的所有测试代码生成
