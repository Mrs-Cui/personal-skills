# Writer Agent Prompt 模板

主控调度 Writer 时使用以下模板构造 prompt。

## Prompt 精简原则

1. **Mock 表按组裁剪**：使用 `analyze_mock_path.py --functions` 只传当前分组函数引用的依赖
2. **追加模式去重**：第 2+ 分组不重传 header 和 class_def（Writer 可自行读取）
3. **类型摘要替代全文**：dataclass / 枚举等辅助类型只传字段签名，不传完整源码
4. **目标**：每个 Writer 调用的 prompt ≤ 4000 token

## 首次调用模板（生成测试）

```
使用 python-unittest-writer 技能为以下目标生成单元测试。

## 基本信息
- 源文件：{file}
- 测试文件：{test_file}
- 目标函数/方法：{函数名列表}
- 所属类：{class_name}（如果是模块级函数则为"无"）
- 覆盖率目标：{coverage_target}%
- 追加模式：false

## 源码上下文

### 文件头部（imports）
{Read file header.start ~ header.end}

### 类定义
{Read class_def.start ~ min(class_def.start + 30, 第一个方法的 start)}

### 关联类型（摘要）
{如果 related_type 是 dataclass/NamedTuple → 只传字段签名列表}
{如果 related_type 是 Enum → 只传当前分组引用的枚举值}
{如果 related_type < 20 行 → 传完整源码}
{示例: FilterDataInfo(uuid: str, status: int, email: str, tiger_phone: str, ...)}

### 目标函数源码
{Read each functions[i].start ~ functions[i].end}

## Mock 信息（已按当前分组函数裁剪）

| 依赖名 | 来源模块 | Mock 路径 | Mock 类型 | 是否异步 |
|--------|---------|----------|----------|---------|
{从 analyze_mock_path.py --json --functions "{当前组函数名}" 输出填充}

## 项目约束
- 测试目录：test_auto_generate/unit/（镜像 message/ 结构）
- 异步模式：asyncio_mode=auto（无需 @pytest.mark.asyncio）
- 共享 fixtures：mock_config_manager, mock_factory, async_mock
- 禁止参考 tests/ 目录（已废弃）
- Python 3.9，pytest + pytest-asyncio
```

## 追加调用模板（同文件后续分组）

追加模式**不重传**文件头部和类定义，只传目标函数 + 裁剪后的 Mock 表。
Writer 如需参考上下文，可自行 Read 测试文件头部。

```
使用 python-unittest-writer 技能追加测试代码。

## 基本信息
- 源文件：{file}
- 测试文件：{test_file}（已存在）
- 目标函数/方法：{函数名列表}
- 所属类：{class_name}
- 追加模式：true

## 源码上下文

### 目标函数源码
{Read each functions[i].start ~ functions[i].end}

### 关联类型（摘要，仅当本组函数引用了新类型时才传）
{同首次模板的摘要策略}

## Mock 信息（已按当前分组函数裁剪）

| 依赖名 | 来源模块 | Mock 路径 | Mock 类型 | 是否异步 |
|--------|---------|----------|----------|---------|
{从 analyze_mock_path.py --json --functions "{当前组函数名}" 输出填充}

## 追加说明
测试文件已存在，请在文件末尾追加新的测试方法。
如果新方法属于已有的测试类，追加到该类内部。
如果是新的测试类，在文件末尾添加。
检查是否需要补充 import（在文件头部 Edit）。
```

## 修复调用模板（Validator 返回错误报告后）

Validator（python-unittest-validator）只验证和分类错误，不修复代码。
错误修复由 Writer 负责。主控将 Validator 的结构化报告原样传给 Writer。

```
使用 python-unittest-writer 技能修复测试代码。

## 基本信息
- 测试文件：{test_file}
- 源文件：{file}
- 迭代轮次：{第 N 次 Writer→Validator 循环}

## Validator 错误报告
{原样粘贴 Validator 返回的完整错误报告，包含：}
{- 错误码（如 MK-ASYNC, PT-FUNC, AF-VAL）}
{- 测试函数名}
{- 错误信息}
{- 错误位置（文件:行号）}
{- 分类和修复建议}

## 源码上下文（仅错误相关函数）
{只传 Validator 报告中涉及的函数源码，不传整个分组}

## Mock 信息（已按错误涉及函数裁剪）

| 依赖名 | 来源模块 | Mock 路径 | Mock 类型 | 是否异步 |
|--------|---------|----------|----------|---------|
{从 analyze_mock_path.py --json --functions "{错误涉及的函数名}" 输出填充}

## 修复指引
根据 Validator 的错误报告修复测试代码。只修改测试文件，不修改源码。

错误码与 troubleshooting 对照：
- PT-FUNC / PT-MOD → T001（Mock 路径）
- MK-ASYNC → T002 / T003（异步 Mock）
- MK-ATTR → T004 / T005（Mock 属性）
- MK-CTX → T006（上下文管理器）
- MK-CONF → T010（配置 Mock）

按优先级修复：P0（ENV/IMP）→ P1（FIX）→ P2（MK/AF/PT/SIG）→ P3（RT）
```

## 覆盖率补充调用模板（Coverage 不达标时）

```
使用 python-unittest-writer 技能补充测试用例。

## 基本信息
- 源文件：{file}
- 测试文件：{test_file}（已存在）
- 追加模式：true
- 覆盖率目标：{coverage_target}%
- 当前覆盖率：{current_coverage}%

## 未覆盖的函数
{从 run_test_with_coverage.py --json --uncovered-functions 输出}

## 源码上下文（仅未覆盖函数）
{只传 uncovered_functions 的源码}

## Mock 信息（已按未覆盖函数裁剪）

| 依赖名 | 来源模块 | Mock 路径 | Mock 类型 | 是否异步 |
|--------|---------|----------|----------|---------|
{从 analyze_mock_path.py --json --functions "{未覆盖的函数名}" 输出填充}

## 补充说明
当前覆盖率未达标。请为上述未覆盖的函数补充测试用例。
重点覆盖：
1. 未覆盖的分支（if/else, try/except）
2. 边界条件
3. 异常路径
```

## 主控组装规则

### 上下文选择

主控根据源文件特征选择性引用规则文档：

| 源文件路径 | 额外引用 |
|-----------|---------|
| `handler/streamHandler/` | stream-handler-rules.md |
| `handler/streamHandler/send_data_producer/` | message-producer-rules.md |
| 含 `async def` 的文件 | async-mock-rules.md（强调） |
| 其他 | 仅 general-rules.md + templates.md |

### 分组调度顺序

1. 同一文件的分组按序号调度（group1 → group2 → ...）
2. 第一个分组 `append=false`，后续 `append=true`
3. 每个分组调度 Writer 后，立即调度 Validator
4. 目录模式下，完成一个文件所有分组后再处理下一个文件

### 关联类型摘要策略

| related_type 特征 | 传递方式 | 示例 |
|-------------------|---------|------|
| dataclass / NamedTuple | 字段签名列表 | `FilterDataInfo(uuid: str, status: int, email: str, ...)` |
| Enum | 仅当前分组引用的枚举值 | `FilterStrategyName: STATUS_VALID, PHONE_VALID` |
| 普通类 < 20 行 | 完整源码 | 原样传 |
| 普通类 ≥ 20 行 | 类签名 + 公开方法签名 | `class Helper: def validate(self, data: dict) -> bool` |

### Mock 表裁剪流程

```
shard.py 输出 → 每个 group 包含 used_names 列表
                     ↓
analyze_mock_path.py --functions "{group.used_names 逗号拼接}"
                     ↓
只包含该组实际引用的 Mock 路径 → 填入 Writer prompt
```
