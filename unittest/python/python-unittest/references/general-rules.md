# 单元测试通用规则

## 概述

本文档包含适用于所有单元测试的通用规则和最佳实践，这些规则与具体的测试域无关，是测试代码质量的基础保障。


## 核心通用原则

### 0. 测试生成范围选择
**规则**: 支持基于 Git diff 的智能范围选择

**交互选项**: 
1. 当前暂存区 vs master (推荐日常开发)
2. 工作区 vs master (代码审查时使用)
3. 两个提交之间 (版本发布时使用)
4. 最近 N 次提交 (重构清理时使用)
5. 指定文件或目录 (特定模块测试)
6. 全量生成 (项目初始化时使用)

**详细交互流程**: 参考 `unit-test-interactive-rules.md`

### 1. 测试生成范围（基于 .coveragerc）
**规则**: 单元测试生成范围与 `.coveragerc` 配置完全一致
**使用场景**: 确定哪些文件/代码需要生成测试，哪些文件/代码应该排除
**核心原则**: 
- 测试生成范围 = 覆盖率统计范围
- 单一配置源：`.coveragerc` 文件

### 2. Mock 路径规则（最重要）

**核心原则**: Mock 路径 = 目标文件模块路径 + 在该文件中的使用名称

#### 根据 import 方式确定路径

| import 方式 | Mock 路径 |
|------------|----------|
| `from message.common import ConfigManager` | `目标模块.ConfigManager` |
| `from message.common.config import ConfigManager` | `目标模块.ConfigManager` |
| `import message.common.config` 后用 `config.ConfigManager` | `目标模块.config.ConfigManager` |

#### 验证步骤

1. 打开目标文件，查看 import 语句
2. 确定类/函数在该文件中的使用名称
3. Mock 路径 = `目标文件的模块路径.使用名称`

#### 辅助工具

```bash
# 分析文件并生成正确的 Mock 路径
python test_auto_generate/tools/mock_path_helper.py path/to/target_file.py

# 检查 Mock 路径是否正确
python test_auto_generate/tools/mock_path_helper.py path/to/target_file.py "your.mock.path"
```

### 3. 异步 Mock 配置规则

**规则**: 所有异步方法和属性必须使用 `AsyncMock`，详细用法见 `async-mock-rules.md`

```python
# 异步属性 Mock（general-rules 独有补充）
@patch.object(ConnectionManager, 'message_db_peewee', new_callable=AsyncMock)
```

### 4. Mock 对象属性完整性规则
**规则**: Mock 对象必须包含所有被访问的属性

```python
# ✅ 检查基础类的 __init__ 方法，添加所有必需属性
mock_object.required_attribute_1 = default_value
mock_object.required_attribute_2 = default_value
# ... 添加所有被访问的属性
```

### 5. 异步上下文管理器 Mock 规则
**规则**: 异步上下文管理器需要特殊配置

```python
# ✅ 正确：异步上下文管理器 Mock
async_context_manager = AsyncMock()
async_context_manager.__aenter__.return_value = mock_object
async_context_manager.__aexit__.return_value = None
```

### 6. 装饰器 Mock 规则
**规则**: 缓存装饰器需要返回装饰器工厂函数

```python
# ✅ 正确：缓存装饰器 Mock
def mock_redis_cache(key_pattern, ttl, value_serializer=None):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

### 7. 继承链属性检查规则
**规则**: 检查整个继承链的 `__init__` 方法，确保所有基类属性都被包含

```python
# 检查顺序：目标类 → 直接父类 → 间接父类
# 例如：WhatsAppProducer → BaseProducer → object
# 需要包含所有层级的必需属性
```

## 单元测试增量开发规范

### 核心原则

在新增单元测试时，必须遵循**最小变更原则**，保护现有测试代码的稳定性和完整性。

### 具体规范

#### 1. 现有测试代码保护
- **严禁随意修改**现有的测试文件和测试用例
- 新增测试时优先**创建新的测试文件**或在现有文件中**添加新的测试方法**
- 保持现有测试的**命名约定**和**代码结构**不变

#### 2. 允许修改的情况
仅在以下情况下可以修改现有测试代码：

- **被测试代码已修改**：源代码接口、行为或实现发生变化
- **语法错误**：现有测试存在 Python 语法错误导致无法运行
- **逻辑错误**：现有测试的断言或测试逻辑明显错误
- **依赖更新**：第三方库升级导致的兼容性问题

#### 3. 修改时的注意事项
- 修改前**备份原有测试逻辑**，在注释中说明修改原因
- 确保修改后的测试**覆盖原有功能**，不降低测试覆盖率
- 优先使用**向后兼容**的方式进行修改
- 修改后运行**完整测试套件**确保无回归问题

#### 4. 新增测试的最佳实践
- 在 `test_auto_generate/` 目录下创建新测试文件
- 遵循现有的**文件命名规范**：`test_<module_name>.py`
- 保持与现有测试相同的**代码风格**和**Mock 策略**


## 常见错误和解决方案

> 详细的错误索引和解决方案请参考 `troubleshooting.md`，支持按错误关键字快速定位。

常见错误类型：
- Mock 路径不生效 → T001
- 异步 await 错误 → T002
- 协程未等待 → T003
- Mock 属性缺失 → T004
- 只读属性错误 → T005、T006
- 数据库连接错误 → T007
- Fixture 源码错误 → T008
- 装饰器 Mock 失败 → T009
- 类级别配置问题 → T010


## 测试失败处理原则


### 运行

单元测试生成之后，统一执行一遍`python -m pytest test_auto_generate/unit -v`


### 自动修复的测试代码问题

如果测试失败是由于以下测试框架问题导致的，AI 应该自动修复：

- ❌ `RuntimeWarning: coroutine was never awaited` - 缺少 `await` 关键字
- ❌ `TypeError: object AsyncMock can't be used in 'await' expression` - Mock 配置错误
- ❌ `AssertionError: Error, query's database and manager's database are different` - 数据库连接 Mock 问题
- ❌ Mock 路径错误、参数不匹配等测试框架问题
- ❌ 缺少 `@pytest.mark.asyncio` 装饰器
- ❌ 使用 `Mock` 而不是 `AsyncMock` 处理异步方法

**修复策略**: 简化 Mock 策略，使用直接的方法级 Mock，确保异步调用正确

### 仅报告的业务逻辑问题

如果测试失败是由于以下业务逻辑问题导致的，AI 只需指出问题，不应修复：

- ✅ 业务方法返回值与预期不符
- ✅ 业务逻辑分支覆盖不完整
- ✅ 数据验证规则不正确
- ✅ 异常处理逻辑缺失
- ✅ 业务流程逻辑错误

**处理方式**: 报告问题位置和原因，建议开发者检查业务代码


## 通用检查清单

### 生成前检查
- [ ] 分析目标文件的导入语句
- [ ] 检查基础类的 `__init__` 方法
- [ ] 检查整个继承链的属性要求
- [ ] 识别所有异步方法和属性
- [ ] 识别异步上下文管理器
- [ ] 识别装饰器依赖
- [ ] 识别类级别配置读取

### 生成后检查
- [ ] 所有 Mock 路径指向使用位置
- [ ] 所有异步方法使用 `AsyncMock`
- [ ] 异步上下文管理器正确配置
- [ ] Mock 对象包含所有必需属性（包括继承链）
- [ ] 装饰器 Mock 返回正确的函数结构
- [ ] 类级别配置使用模块级 Mock
- [ ] 嵌套配置结构使用 `side_effect`

### 运行前检查
- [ ] 导入语句正确
- [ ] 没有语法错误
- [ ] Mock 配置完整
- [ ] 测试数据格式正确
- [ ] 异步测试标记正确（@pytest.mark.asyncio）
- [ ] Fixture 依赖关系正确
- [ ] conftest.py 无重复定义
- [ ] 事件循环配置正确

## 总结

这些通用规则适用于所有单元测试，遵循这些规则可以避免 90% 的常见错误：

1. **Mock 路径必须指向使用位置**
2. **异步方法必须使用 AsyncMock**
3. **异步上下文管理器需要特殊配置**
4. **Mock 对象必须包含所有必需属性（包括继承链）**
5. **装饰器 Mock 必须返回正确的函数结构**
6. **复杂依赖关系需要按优先级配置**
7. **类级别配置必须使用模块级 Mock**
8. **避免在测试类中使用 @pytest.fixture(autouse=True)**
9. **嵌套配置结构使用 side_effect 模拟**
10. **新增单元单测试时，需要考虑到现有的单元测试逻辑，非必要不要修改原有的测试代码，除非涉及的相关被测试的代码已经被修改或者出现语法/逻辑错误**

记住：**一次性生成正确的测试比反复修改更高效**。

## 版本历史

- v1.0 (2024-12-25): 从综合规则中提取通用规则，建立独立的通用规则文档
- v1.1 (2025-01-15): 优化错误 7（can't set attribute），新增错误 8（reified property is read-only）
