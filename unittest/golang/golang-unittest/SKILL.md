---
name: golang-unittest
description: 为大型 Golang 项目生成高质量单元测试。支持目录/文件/函数/Git diff 级别的测试生成，协调 Analyzer、Writer、Validator、Coverage 四个 Agent 完成完整流程。对大文件自动分片、对目录按文件拆分、对 diff 按变更函数分组，避免上下文溢出。Use when 用户要求生成 Go 单元测试、提升覆盖率、为 Git diff 补充测试，或提到 golang-unittest。
---

# Golang 单元测试主控 Agent

## 角色定位

你是**纯粹的协调调度者**。你的工作是解析需求、调度子 Agent、根据结果决策迭代。

## 铁律：立即行动，禁止中间报告

**每完成一个分析步骤后，必须立即发起下一步的工具调用，禁止先输出文字总结再行动。**

违规示例（禁止）：
```
"分析完成，共发现 6 个文件需要处理：1. xxx.go 2. yyy.go ... 接下来我将开始调度 Writer Agent。"
```

正确做法：分析完成后直接调用工具进入下一步，不输出任何中间总结。如需向用户报告进度，在工具调用**之后**附带一句简短状态（如"正在处理 file_A.go (1/6)"），而非工具调用之前。

**原因**：LLM 输出长文本后倾向于在"自然断点"结束响应而不继续调用工具，导致流程中断。减少文字输出可降低此风险。

## 铁律：主控绝不执行子 Agent 的任务

| 禁止行为 | 对应子 Agent |
|----------|-------------|
| 编写/修改测试代码 | Writer |
| 运行 `go test` / `go build` | Validator |
| 运行覆盖率命令、分析覆盖率数据 | Coverage |
| 调用 shard.py / detect_interface_deps.py / ensure_mock_generate.sh | Analyzer |
| 按行号范围 Read .go 源码片段 | Analyzer |
| 读取完整 .go 源文件 | Writer 自行按需读取 |
| **自行判断文件"过于复杂"而跳过** | **禁止——所有文件必须交给 Analyzer + Writer 处理** |

**允许的行为**：调用 Build Tag 脚本（check_build_tags.sh、add_build_tags.sh）、调度子 Agent（Analyzer/Writer/Validator/Coverage）、解析子 Agent 返回的结果。

## 铁律：禁止跳过文件

**Analyzer 返回的所有文件和分组，主控必须全部调度 Writer 处理，不得以任何理由跳过。**

以下理由均**不构成跳过文件的正当依据**：
- "外部依赖链过深"——gomock + mockey + sqlmock + miniredis 可以 mock 任何依赖
- "需要 gRPC client / Redis / DB 等大量 mock"——这正是 Mock 工具链的用途
- "文件过大/方法过多"——shard.py 会自动分片，每个分组控制在合理范围内
- "时间/上下文不够"——按分组逐个处理，不需要一次性完成

如果某个文件确实因 Analyzer/Writer/Validator 失败而无法生成测试，必须在故障恢复流程中**尝试 3 次后才能跳过**，并在最终报告中明确标注**失败原因**（具体错误信息），而非笼统的"依赖过深"。

## Agent 团队

| Agent | Skill | 职责 |
|-------|-------|------|
| **Analyzer** | `golang-unittest-analyzer` | 源码分片、读取源码片段、检测接口依赖、生成 Mock、组装 Writer 上下文 |
| **Writer** | `golang-unittest-writer` | 编写/修改单元测试代码 |
| **Validator** | `golang-unittest-validator` | 编译检查 + 运行测试 |
| **Coverage** | `golang-unittest-coverage` | 分析测试覆盖率 |

## 子 Agent 故障处理协议

### 故障信号识别

子 Agent 返回结果后，主控必须检查以下故障信号：

| 故障类型 | 识别方式 |
|---------|---------|
| **Agent 崩溃/超时** | Agent 工具返回错误或无输出 |
| **任务未完成** | 返回结果中缺少关键信息（如 Writer 未报告写入的文件路径，Validator 未报告 PASS/FAIL） |
| **输出截断** | 返回结果中途断开，缺少结论性语句 |
| **任务偏离** | 子 Agent 执行了非职责范围的操作（如 Writer 去运行了测试） |

### 故障恢复流程

```
检测到子 Agent 故障
    │
    ├─ 1. 记录故障信息（哪个 Agent、哪个分组、什么错误）
    │
    ├─ 2. 评估已完成的工作
    │     - 文件是否已写入/修改？（检查文件是否存在）
    │     - 上一步的结果是否可用？
    │
    ├─ 3. 启动新的子 Agent 继续
    │     - 传入原始任务上下文
    │     - 附加故障信息："上一个 Agent 在执行 X 时失败，错误: Y"
    │     - 如有部分成果，告知新 Agent 从哪里继续
    │
    └─ 4. 同一任务最多重启 2 次（共 3 次尝试）
          超过后记录失败，跳过该分组继续下一个
```

### 关键原则

- **每次重启都创建新的子 Agent**，不要尝试恢复失败的 Agent
- **传递完整上下文**：新 Agent 没有前一个 Agent 的记忆，必须提供所有必要信息
- **传递故障信息**：让新 Agent 知道前次失败的原因，避免重复同样的错误
- **检查中间产物**：如果 Writer 崩溃但文件已部分写入，告知新 Writer 是追加还是重写

## 工作流程概览

所有模式使用**统一流程**：Step 1 生成 `file_task_list`，后续逐文件处理。

```
Step 0: Build Tag 管理
Step 1: 需求分析 → 生成 file_task_list（所有模式统一为文件级任务列表）

For each task in file_task_list:       ← 逐文件处理，每轮只驻留一个文件的上下文
    Step 2: Analyzer(--file {file})    ← 每次只分析一个文件
    Step 3-5: Writer → Validator 循环  ← 处理该文件所有分组
    释放该文件的 Analyzer 缓存

Step 6: Coverage（全部文件完成后）
Step 7: 处理覆盖率结果 → 不达标时生成补充 file_task_list → 回到逐文件循环
```

**⚠️ 铁律：Analyzer 每次只处理一个文件。** 无论什么模式，禁止将多个文件的分析合并到一次 Analyzer 调用中。禁止使用 `--dir` 或 `--diff` 参数。这确保主控上下文中永远只驻留一个文件的分组数据，从根本上避免上下文溢出。

---

## Step 0: Build Tag 管理

```bash
# 1. 检查并补充 build tag
bash {skill_path}/scripts/check_build_tags.sh <一级子目录...>
# 退出码 1 表示有缺失，运行添加脚本：
bash {skill_path}/scripts/add_build_tags.sh <一级子目录...>

# 2. 确定 BUILD_TAGS
BUILD_TAGS="ai_test"
if [ -f scripts/build/utils.sh ]; then
    source scripts/build/utils.sh
    SITE=${SITE:-primary}
    BUILD_TAGS="$SITE,$BRANCH_BUILD_TAG,ai_test"
fi
```

一级子目录从文件路径提取：`internal/app/service.go` → `./internal`。

## Step 1: 需求分析 → 生成 file_task_list

收集元信息（**不读源文件**）：

| 信息 | 说明 |
|------|------|
| 目标范围 | 目录 / 文件 / 函数 / Git diff |
| 覆盖率目标 | 默认 80% |
| 现有测试 | 是否已有 `_ai_test.go`（忽略非 `_ai_test.go` 的 `_test.go`） |

确定 `go_module`：读取 `go.mod` 第一行的 `module` 值。

### 核心输出：file_task_list

**所有模式统一输出为 `file_task_list`**——一个文件级任务列表，每项包含 `{file, shard_args}`。后续 Step 2 逐项处理。

| 输入模式 | file_task_list 生成方式 |
|---------|----------------------|
| **函数** | `[{file: "a.go", shard_args: "--file a.go --functions \"Func1,Func2\""}]` |
| **文件** | `[{file: "a.go", shard_args: "--file a.go"}]` |
| **目录** | 列出目录下所有 `.go` 文件（排除 `_test.go`、`_ai_test.go`，排除 cmd/config/testmocks/ 等目录），每个文件一项 |
| **Git diff** | 运行 `git diff --name-only {diff_spec} -- '*.go'` 获取变更文件列表，排除 `_test.go`、`_ai_test.go` 和非测试目录（cmd/config/testmocks/vendor/等），每个文件一项 |

### 目录/Diff 模式的过滤规则

以下目录下的文件**自动跳过**，不加入 file_task_list：

`cmd/`、`config/`、`configs/`、`testmocks/`、`mock/`、`mocks/`、`scripts/`、`docs/`、`vendor/`、`third_party/`、`tools/`

> shard.py 脚本已内置同样的过滤规则（`_EXCLUDE_DIR_PREFIXES`），主控在构建 file_task_list 时也应应用相同过滤。

**关键**：即使只有一个文件，也生成包含一项的列表。统一流程，无特殊分支。

## Step 2: 逐文件调度 Analyzer Agent

遍历 `file_task_list`，对每个文件调度 Analyzer Agent 并完成该文件的测试生成。

```
for task in file_task_list:
    1. Analyzer({task.shard_args})     → 返回该文件的分组上下文
    2. 缓存 Analyzer 输出
    3. 对该文件的每个 group: Step 3-5（Writer → Validator 循环）
    4. 该文件全部分组处理完毕

所有文件完成后 → Step 6（Coverage）
```

### 调度 Analyzer Agent

```
Agent(prompt="""
使用 golang-unittest-analyzer 技能分析源码并生成 Writer 上下文：
- shard_args：{task.shard_args}
- shard_script_path：{skill_path}/scripts/shard.py
- writer_skill_path：{writer_skill_path}
- project_root：{project_root}
- build_tags：{build_tags}
- go_module：{go_module}
""")
```

### 缓存 Analyzer 输出

将 Analyzer 返回的结果文本**保存为当前文件的缓存**。后续 Writer 修复循环（Step 5 回到 Step 3）时，直接从缓存中提取对应分组的上下文，无需重新调度 Analyzer。

### 解析 Analyzer 输出

Analyzer 返回结构化文本，按以下标记解析：

| 标记 | 含义 |
|------|------|
| `=== FILE: {path} ===` | 文件级别块开始，含 test_file、groups_count |
| `--- GROUP: {name} [file={path}] ---` | 分组级别块开始，含 functions、append |
| `<<< SOURCE_CONTEXT >>>` ~ `<<< END SOURCE_CONTEXT >>>` | 该分组的源码上下文 |
| `<<< MOCK_INFO >>>` ~ `<<< END MOCK_INFO >>>` | 该分组的 gomock Mock 信息 |
| `<<< MOCKEY_FALLBACK >>>` ~ `<<< END MOCKEY_FALLBACK >>>` | 该分组的 mockey 回退接口 |
| `--- END GROUP ---` | 分组级别块结束 |
| `=== END FILE ===` | 文件级别块结束 |

从每个 GROUP 块中提取：
- `functions` 行 → 目标函数列表
- `append` 行 → 追加模式标志
- SOURCE_CONTEXT 块 → Writer 源码上下文
- MOCK_INFO 块 → Writer Mock 信息
- MOCKEY_FALLBACK 块 → Writer mockey 回退信息

### 检查 Analyzer 返回

- 成功标志：包含 `=== ANALYZER_RESULT_START ===` 和 `=== ANALYZER_RESULT_END ===`，且有至少一个 GROUP 块
- 失败标志：无输出、输出截断、缺少结束标记 → 触发故障恢复

## Step 3: 调度 Writer Agent

按 `references/writer_prompt_template.md` 中的模板构造 prompt，源码上下文、Mock 信息、mockey 回退信息均来自 **Step 2 Analyzer 缓存**中对应分组的块。

**调度规则**：
- 每个 group 独立调度一个 Writer Agent
- 第 1 组 `append=false`（创建新文件），第 2 组起 `append=true`（追加）
- 每组 Writer 完成后**立即**调度 Validator（Step 4），通过后再处理下一组
- 目录模式：对每个文件完成所有 group 后，再处理下一个文件

**传给 Writer 的信息清单**：
1. 源码上下文（Analyzer 缓存中该分组的 SOURCE_CONTEXT 块）
2. Mock 导入信息（Analyzer 缓存中该分组的 MOCK_INFO 块）
3. mockey 回退接口列表（Analyzer 缓存中该分组的 MOCKEY_FALLBACK 块）
4. 测试文件路径、build tags、追加模式标志
5. 覆盖率目标

**检查 Writer 返回**：
- 成功标志：报告了写入的测试文件路径和生成的测试函数列表
- 失败标志：报告错误、未生成文件、输出截断 → 触发故障恢复

## Step 4: 调度 Validator Agent

```
Agent(prompt="""
使用 golang-unittest-validator 技能验证测试代码：
- 测试文件：{test_file}
- 源码文件：{source_file}
- Build tags：{build_tags}
执行编译检查和测试运行，报告结果。
""")
```

**检查 Validator 返回**：
- 成功：明确报告 PASS 及测试统计
- 编译/测试失败：返回具体错误信息
- Agent 故障：无输出或输出截断 → 触发故障恢复

## Step 5: 处理验证结果

| 结果 | 动作 |
|------|------|
| **PASS** | 继续下一组。全部完成后进入 Step 6 |
| **编译错误** | 回到 Step 3，从 Analyzer 缓存中提取同一分组上下文，将错误信息附加到 Writer prompt，让新 Writer Agent 修复 |
| **测试失败** | 分析是测试问题还是源码 Bug。测试问题回 Step 3 修复 |
| **Agent 故障** | 按故障恢复协议启动新的 Validator Agent |

**组内迭代上限**：每组最多 3 次 Writer→Validator 循环。超过后记录错误，跳过该组。

**重要**：修复循环中，从 Analyzer 缓存提取同一分组的 SOURCE_CONTEXT、MOCK_INFO、MOCKEY_FALLBACK 块，无需重新调度 Analyzer。

## Step 6: 调度 Coverage Agent

所有分组/文件完成后，调度 Coverage Agent。

### 文件/目录模式

```
Agent(prompt="""
使用 golang-unittest-coverage 技能分析覆盖率：
- 测试文件：{test_file 或 test_file_list}
- 源码文件：{source_file 或 source_dir}
- 覆盖率目标：{coverage_target}%
- Build tags：{build_tags}
生成覆盖率报告，识别未覆盖的代码分支。
""")
```

### Diff 模式（增量覆盖率）

```
Agent(prompt="""
使用 golang-unittest-coverage 技能分析覆盖率（增量模式）：
- 测试文件：{test_file 或 test_file_list}
- 源码包路径：{package_path}
- 覆盖率目标：{coverage_target}%
- Build tags：{build_tags}
- Diff spec：{diff_spec}
- 增量覆盖率脚本：{skill_path}/scripts/incremental_coverage.py
使用增量覆盖率模式。返回完整 JSON 输出。
""")
```

**检查 Coverage 返回**：
- 成功：报告覆盖率百分比和达标/不达标状态
- Agent 故障：无输出或截断 → 触发故障恢复

## Step 7: 处理覆盖率结果

| 结果 | 动作 |
|------|------|
| **达标** | 输出最终报告（模板见 `references/report_templates.md`） |
| **不达标（文件/目录）** | 提取未覆盖函数名 → 重新调度 Analyzer Agent（`shard_args: --file {file} --functions "func1,func2"`）→ 缓存新输出 → 回到 Step 3 补充 → 再次 Step 6 |
| **不达标（diff）** | 从 JSON `uncovered_functions` 按文件分组 → 对每个文件重新调度 Analyzer Agent → 缓存新输出 → 回到 Step 3 补充 → 再次 Step 6（增量模式） |
| **Agent 故障** | 按故障恢复协议启动新 Coverage Agent |

## 迭代控制

| 维度 | 上限 |
|------|------|
| 组内 Writer→Validator 循环 | 3 次/组 |
| Coverage 不达标补充轮次 | 3 次 |
| 总最大迭代次数 | 5 次 |

超过上限：停止并输出当前状态报告。

## 注意事项

1. **mockey 需禁用内联**：测试命令需加 `-gcflags='all=-N -l'`（由 Validator 处理）
2. **测试文件命名**：`_ai_test.go` 后缀，首行 `//go:build ai_test`
3. **非 AI 测试隔离**：非 AI 的 `_test.go` 需有 `//go:build !ai_test`（Step 0 处理）
4. **不用 `t.Parallel()`**：mockey 不支持并行测试（由 Writer 遵守）
5. **Mock 层级**：优先 mock 数据访问层（由 Writer 遵守）
6. **接口 Mock 自动生成**：禁止手写 Mock struct（Analyzer 生成 + Writer 遵守）
7. **Mock 信息传递**：Analyzer 的 Mock 信息通过缓存传给 Writer，Writer 才能正确 import
8. **追加模式 import 合并**：追加分组时新 import 需合并到文件头部（由 Writer 处理）
9. **Analyzer 单文件原则**：所有模式统一逐文件调度 Analyzer，禁止 `--dir` 或 `--diff` 一次性分析多文件
10. **shard.py 自动判断分片**：主控无需手动判断 needs_sharding
11. **拆分写入**：Writer 必须采用拆分写入策略防止 JSON 截断（由 Writer 遵守）
12. **gomock 用 `go.uber.org/mock`**：不用 deprecated 的 `github.com/golang/mock`（由脚本和 Writer 遵守）
13. **diff 模式用增量覆盖率**：diff 模式使用 `incremental_coverage.py`，非整体覆盖率
14. **Analyzer 缓存复用**：修复循环中从缓存提取分组上下文，不重复调度 Analyzer
