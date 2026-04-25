# Writer Agent Prompt 模板

调用 Writer Agent 时，使用以下 prompt 模板。将 `{...}` 占位符替换为实际值。

源码上下文、Mock 信息、mockey 回退信息均来自 **Analyzer Agent 缓存**中对应分组的块，直接嵌入即可。

```
Task(subagent_type="general", prompt="""
使用 golang-unittest-writer 技能为以下目标生成单元测试：
- 源文件：{file}
- 目标函数：{group.functions 中的函数名列表}
- 测试文件：{test_file}
- 覆盖率目标：{coverage_target}%
- Build tags：{build_tags}
- 追加模式：{true/false}（第 1 组为 false，后续组为 true）

以下是源码上下文（由 Analyzer Agent 预组装）：

{Analyzer 缓存中该分组的 SOURCE_CONTEXT 块，即 <<< SOURCE_CONTEXT >>> 到 <<< END SOURCE_CONTEXT >>> 之间的内容}

--- 已生成的 gomock Mock 信息（如有） ---
{Analyzer 缓存中该分组的 MOCK_INFO 块，即 <<< MOCK_INFO >>> 到 <<< END MOCK_INFO >>> 之间的内容}

⚠️ 强制规则：
1. 禁止在测试文件中手写 type mockXxx struct { ... } 来实现接口
2. 必须使用上述 gomock 生成的 Mock 类型
3. 使用 EXPECT() 设置期望行为
--- END Mock 信息 ---

--- mockey 回退接口（如有） ---
{Analyzer 缓存中该分组的 MOCKEY_FALLBACK 块，即 <<< MOCKEY_FALLBACK >>> 到 <<< END MOCKEY_FALLBACK >>> 之间的内容}

注意：需要先给被测 struct 的该字段赋一个真实的零值实例（或 nil interface），再用 mockey mock 方法。
--- END mockey 回退接口 ---

⚠️ Mock 策略检查（强制）：
在生成测试代码之前，你必须先检查源码中被测 struct 的字段类型和函数体内的依赖调用，按以下规则选择 Mock 方式：
1. 字段类型为 *gorm.DB / *sql.DB / *sqlx.DB / *xdb.XDB → 必须用 sqlmock 创建 mock DB 注入，禁止 mockey
2. 字段类型为 *redis.Client / *redis.ClusterClient → 必须用 miniredis 创建 mock server 注入，禁止 mockey
3. 字段类型为接口 → 使用上方提供的 gomock Mock 信息
4. 字段类型为具体 struct → 使用 mockey.Mock((*Struct).Method)
5. 函数体内访问全局 *gorm.DB 变量 → 用 mockey.MockValue 替换全局变量为 sqlmock 实例
6. 函数体内访问全局 *redis.Client 变量 → 用 mockey.MockValue 替换全局变量为 miniredis 实例
详见 golang-unittest-writer 技能的「基础设施依赖 Mock 强制规则」章节。

请基于以上源码上下文，为目标函数列表中的**每一个函数**生成表驱动测试用例。
⚠️ 铁律：必须为目标函数列表中的所有函数生成测试，禁止自行筛选或跳过任何函数。类型定义仅作为理解上下文使用。

重要：写入测试文件时必须采用拆分写入策略（详见 golang-unittest-writer 技能的"拆分写入策略"章节）：
- 先用 Write 写入文件骨架（package + 完整 import + 第1个测试函数）
- 再用 Edit 逐个追加后续测试函数
- 禁止一次性 Write 超过 200 行的测试代码
""")
```

## Writer 修复模板（Validator 返回错误时）

当 Validator 报告编译错误或测试失败，回到 Writer 修复时使用此模板：

```
Agent(prompt="""
使用 golang-unittest-writer 技能修复测试代码中的错误：
- 测试文件：{test_file}
- 源文件：{file}
- Build tags：{build_tags}

--- 错误信息 ---
{Validator 返回的具体错误内容}
--- END 错误信息 ---

--- 源码上下文（当前分组，来自 Analyzer 缓存） ---
{Analyzer 缓存中该分组的 SOURCE_CONTEXT 块}
--- END 源码上下文 ---

--- gomock Mock 信息（来自 Analyzer 缓存，如有） ---
{Analyzer 缓存中该分组的 MOCK_INFO 块}
--- END Mock 信息 ---

请根据错误信息修复测试代码。只修改测试文件，不要修改源码。
""")
```

## Writer 故障重启模板（Agent 崩溃/超时时）

当 Writer Agent 故障（崩溃、超时、输出截断）需要启动新 Agent 继续时：

```
Agent(prompt="""
使用 golang-unittest-writer 技能为以下目标生成单元测试：

⚠️ 注意：上一个 Writer Agent 在处理此任务时失败了。
- 失败原因：{故障描述}
- 测试文件当前状态：{文件是否已存在、已有多少测试函数}
- 需要你：{从头生成 / 继续追加剩余函数}

{后续内容与首次调用模板相同：源文件、目标函数、测试文件、build tags、追加模式、Analyzer 缓存的源码上下文、Mock 信息等}
""")
```

## Validator 故障重启模板

```
Agent(prompt="""
使用 golang-unittest-validator 技能验证测试代码：
- 测试文件：{test_file}
- 源码文件：{source_file}
- Build tags：{build_tags}

⚠️ 注意：上一个 Validator Agent 未能完成验证。
- 失败原因：{故障描述}
- 需要你：重新执行完整的编译检查和测试运行

执行编译检查和测试运行，报告结果。
""")
```

## Coverage 故障重启模板

```
Agent(prompt="""
使用 golang-unittest-coverage 技能分析覆盖率：

⚠️ 注意：上一个 Coverage Agent 未能完成分析。
- 失败原因：{故障描述}
- 需要你：重新执行完整的覆盖率分析

{后续内容与首次调用模板相同：测试文件、源码文件、覆盖率目标、build tags、diff spec 等}
""")
```
