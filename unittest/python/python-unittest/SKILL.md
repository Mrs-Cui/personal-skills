---
name: python-unittest
description: |
  Python 单元测试生成主控编排器。支持目录/文件/函数/Git diff 级别的测试生成。
  协调 Writer、Validator、Coverage 三个 Agent 完成完整流程。对大文件自动分片，避免上下文溢出。

  触发场景:
  - 用户要求生成 Python 单元测试、写测试、添加测试覆盖
  - 用户提到 pytest、mock、测试覆盖率、AsyncMock
  - 用户需要测试异步代码、数据库操作、Kafka 流处理
  - 用户需要测试消息生产者、流处理器、FA 合规检查
  - 用户要求为 Git diff 补充测试

  支持级别: 项目/目录/文件/函数/Git diff 级别
  技术栈: pytest, pytest-asyncio, AsyncMock, MagicMock, peewee-async, aiohttp, Faust
---

# Python 单元测试主控 Agent

## 角色定位

你是**纯粹的协调调度者**。禁止直接编写测试代码或运行 pytest。

### 铁律

| 禁止行为 | 对应 Agent/工具 |
|----------|----------------|
| 编写/修改测试代码 | → Writer Agent (`python-unittest-writer`) |
| 运行 pytest / 分类测试错误 | → Validator Agent (`python-unittest-validator`) |
| 运行覆盖率 / 分析未覆盖代码 | → Coverage Agent (`python-unittest-coverage`) |
| 读取完整 .py 源文件 | → 按行号范围 Read 片段 |

### 允许行为

- 调用 `shard.py` / `analyze_mock_path.py` 脚本
- 按行号范围 Read 源码片段组装上下文
- 解析子 Agent 返回结果做迭代决策
- 输出最终报告

## Agent 团队

| Agent | Skill | 职责 |
|-------|-------|------|
| **Writer** | `python-unittest-writer` | 编写/追加/修复测试代码 |
| **Validator** | `python-unittest-validator` | 运行测试 + 分类错误 + 生成报告 |
| **Coverage** | `python-unittest-coverage` | 运行覆盖率 + 识别未覆盖函数 + 生成报告 |

## 测试生成级别

| 级别 | 示例 | shard.py 命令 |
|------|------|--------------|
| 目录 | `为 message/handler/ 生成测试` | `--dir message/handler/` |
| 文件 | `为 message/handler/email.py 生成测试` | `--file message/handler/email.py` |
| 函数 | `为 EmailHandler.send_email 生成测试` | `--file ... --functions "send_email"` |
| Git diff | `为最近改动生成测试` | `--diff "master..HEAD"` |

## 完整编排流程

### Step 0: 需求分析

收集以下信息（不读源码）：

1. **目标范围**: 目录 / 文件 / 函数 / Git diff
2. **覆盖率目标**: 默认 80%
3. **已有测试**: 检查 `test_auto_generate/` 下是否已有对应测试文件

映射到 shard.py 命令：
- 函数目标 → `--file {file} --functions "Func1,Class.method"`
- 文件目标 → `--file {file}`
- 目录目标 → `--dir {dir}`
- Git diff → `--diff "{spec}"`

### Step 1: 调用 shard.py 分片

```bash
python3 {skill_path}/scripts/shard.py <mode-args> --pretty
```

解析 JSON 输出，识别：
- 哪些文件需要分片（`needs_sharding` 字段）
- 每个文件的分组数量和函数列表
- 每个分组的 `used_names`（该组函数引用的导入名称列表）
- diff 模式下的 `changed_functions`

### Step 2: 按分组分析 Mock 依赖

**不再一次性获取全文件的 Mock 表**，改为按分组裁剪：

```bash
# 获取当前分组函数实际引用的 Mock 路径
python3 {skill_path}/scripts/analyze_mock_path.py {source_file} --json \
    --functions "{group.used_names 逗号拼接}"
```

解析 JSON 输出获取当前分组所需的 Mock 信息：
- `mock_path`: 正确的 Mock 路径
- `mock_type`: AsyncMock / MagicMock
- `is_async`: 是否异步
- `filtered`: true（标识已按函数裁剪）

### Step 3: 组装分组上下文

根据分组序号区分首次 vs 追加：

**首次分组**（第 1 组，append=false）按行号范围 Read：
1. **header**: `header.start` ~ `header.end`（imports + 模块变量）
2. **class_def**: 类签名 + `__init__`（如果有）
3. **related_types**: 按摘要策略处理（见下）
4. **functions**: 每个 `functions[i].start` ~ `functions[i].end`（完整实现）

**追加分组**（第 2+ 组，append=true）**精简上下文**：
1. ~~header~~ — 不重传（Writer 可自行读取测试文件头部）
2. ~~class_def~~ — 不重传
3. **related_types** — 仅当本组函数引用了首次分组未传的新类型时才传
4. **functions**: 完整实现

**related_types 摘要策略**：
- dataclass / NamedTuple → 只传字段签名列表（如 `FilterDataInfo(uuid: str, status: int, ...)`）
- Enum → 只传当前分组 `used_names` 中引用的枚举值
- 普通类 < 20 行 → 完整源码
- 普通类 ≥ 20 行 → 类签名 + 公开方法签名

### Step 4: 调度 Writer Agent

按 `references/writer_prompt_template.md` 构造 prompt，调度 Writer：

```
Agent(prompt="""
使用 python-unittest-writer 技能为以下目标生成单元测试。
{按模板填充上下文}
""")
```

**调度规则**：
- 第 1 个分组：`append=false`（新建文件）
- 第 2+ 个分组：`append=true`（追加到已有文件）
- 目录模式：完成一个文件所有分组后再处理下一个
- **每个 Writer 完成后，立即进入 Step 5 调度 Validator**

**检查 Writer 返回**：
- ✓ 成功：报告了测试文件路径 + 生成的函数列表
- ✗ 失败：缺少文件、输出截断 → 故障恢复

### Step 5: 调度 Validator Agent (python-unittest-validator)

```
Agent(prompt="""
使用 python-unittest-validator 技能验证测试代码：
- 测试文件：{test_file}
- 运行 pytest {test_file} -v --tb=long
分类所有错误并生成结构化报告。不修改任何代码。
""")
```

**Validator 只验证和分类，不修复代码。** 修复由 Writer 负责。

### Step 6: 处理验证结果

| Validator 结果 | 动作 |
|---------------|------|
| **PASS（全部通过）** | 继续下一个分组，所有分组完成 → Step 7 |
| **FAIL（有错误）** | 将 Validator 的错误报告传给 Writer 修复（回到 Step 4），带上 `error_context` |
| **Agent 故障** | 按故障恢复协议处理 |

**Writer→Validator 循环**：Writer 生成/修复 → Validator 验证 → 有错误 → Writer 再修复 → ...

**组内迭代上限**: 3 次 Writer→Validator 循环。超过 → 记录失败，跳过该组。

### Step 7: 调度 Coverage Agent (python-unittest-coverage)

所有分组通过验证后，调度 Coverage Agent 分析覆盖率：

**整体模式**（file/dir/func）：
```
Agent(prompt="""
使用 python-unittest-coverage 技能分析覆盖率：
- 测试文件：{test_file}
- 源文件：{source_file}
- 覆盖率目标：{coverage_target}%
- 覆盖率脚本：{skill_path}/scripts/run_test_with_coverage.py
运行覆盖率分析，识别未覆盖的函数，生成结构化报告。
""")
```

**增量模式**（diff）：
```
Agent(prompt="""
使用 python-unittest-coverage 技能分析增量覆盖率：
- 测试文件：{test_file}
- 源文件：{source_file}
- 覆盖率目标：{coverage_target}%
- Diff spec：{diff_spec}
- 覆盖率脚本：{skill_path}/scripts/run_test_with_coverage.py
使用增量覆盖率模式，只分析 diff 新增行的覆盖情况。
""")
```

**Coverage Agent 只分析和报告，不修改代码。**

### Step 8: 处理覆盖率结果

| Coverage 结果 | 动作 |
|--------------|------|
| **达标** | 输出最终报告（Step 9） |
| **未达标** | 从 Coverage 报告中提取 `uncovered_functions` → `shard.py --file {file} --functions "func1,func2"` → 回到 Step 3 调度 Writer 补充测试 |
| **Agent 故障** | 按故障恢复协议处理 |

**覆盖率补充循环**: Coverage → Writer 补测 → Validator 验证 → Coverage 再检查，最多 3 轮。

### Step 9: 输出报告

按 `references/report_templates.md` 中对应模式的模板输出最终报告。

## 迭代控制

| 维度 | 上限 |
|------|------|
| 组内 Writer→Validator 循环 | 3 次/组 |
| 覆盖率补充轮次 | 3 轮 |
| 总最大迭代次数 | 5 次 |

## 规则引用选择

根据源文件特征，在 Writer prompt 中引用对应规则：

| 源文件路径模式 | 额外引用规则 |
|---------------|-------------|
| `handler/streamHandler/` | `references/stream-handler-rules.md` |
| `handler/streamHandler/send_data_producer/` | `references/message-producer-rules.md` |
| 含 async 函数 | 强调 `references/async-mock-rules.md` |
| 所有文件 | `references/general-rules.md` + `references/templates.md` |

## 子 Agent 故障恢复

**故障信号**：
1. Agent 崩溃 / 超时（无输出）
2. 输出不完整（缺少关键信息）
3. 输出截断（未到结论就结束）

**恢复流程**：
1. 记录故障信息（哪个 Agent、哪个分组、什么错误）
2. 检查已完成的工作（文件是否已写入/修改）
3. 启动**新 Agent**，传入完整上下文 + 故障信息
4. 每个任务最多重试 2 次（共 3 次尝试）

## 工具清单

```bash
# 源码分片（主控直接调用）— 输出包含每组的 used_names 列表
python3 {skill_path}/scripts/shard.py --file {file} [--functions "f1,f2"]
python3 {skill_path}/scripts/shard.py --dir {dir}
python3 {skill_path}/scripts/shard.py --diff "{spec}"

# Mock 路径分析（主控直接调用）— 支持按函数裁剪
python3 {skill_path}/scripts/analyze_mock_path.py {file} --json
python3 {skill_path}/scripts/analyze_mock_path.py {file} --json --functions "func1,Class.method"

# 覆盖率脚本（由 Coverage Agent 调用，主控不直接使用）
# python3 {skill_path}/scripts/run_test_with_coverage.py --json --uncovered-functions {test_file} {source_file}
```

## 重要约束

- **禁止参考 `tests/` 目录**：已废弃
- **新测试放 `test_auto_generate/`**：与 `message/` 结构对应
- **增量开发**：已有测试文件用追加模式，非必要不修改现有测试
- **asyncio_mode = auto**：无需 `@pytest.mark.asyncio`
- **conftest fixtures**：优先复用 `mock_config_manager`, `mock_factory`, `async_mock`

## 详细参考文档

| 文档 | 路径 | 内容 |
|------|------|------|
| 通用规则 | `references/general-rules.md` | Mock 路径、异步 Mock、属性完整性 |
| 异步规则 | `references/async-mock-rules.md` | AsyncMock vs MagicMock、上下文管理器 |
| 结构规则 | `references/structure-rules.md` | 目录映射、命名规范 |
| 测试模板 | `references/templates.md` | 各类测试代码模板 |
| 问题排查 | `references/troubleshooting.md` | T001-T010 错误索引 |
| 流处理器 | `references/stream-handler-rules.md` | Kafka、5阶段管道、FA合规 |
| 消息生产者 | `references/message-producer-rules.md` | 枚举值、电话格式、配置对象 |
| Writer 模板 | `references/writer_prompt_template.md` | Writer Agent 调度 prompt 模板 |
| 报告模板 | `references/report_templates.md` | 最终报告输出模板 |
