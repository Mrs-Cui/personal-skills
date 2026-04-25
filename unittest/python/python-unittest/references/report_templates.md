# 输出报告模板

主控在完成所有测试生成和验证后，按以下模板输出最终报告。

## 文件模式报告

```markdown
## 单元测试生成报告

### 目标
- 源文件：{source_file}
- 测试文件：{test_file}
- 覆盖率目标：{coverage_target}%

### 分片信息
- 文件总行数：{total_lines}
- 需要分片：{yes/no}
- 分组数量：{group_count}
{foreach group}
  - {group.name}: {func_count} 个函数, {total_func_lines} 行
{endfor}

### 执行结果

| 分组 | Writer | Validator | 迭代次数 | 状态 |
|------|--------|-----------|---------|------|
| {group.name} | ✅ | ✅ | {iterations} | 通过 |
| {group.name} | ✅ | ❌→✅ | {iterations} | 修复后通过 |
| {group.name} | ✅ | ❌ | 3 | 失败（已达重试上限）|

### 覆盖率
- 目标：{coverage_target}%
- 实际：{actual_coverage}%
- 状态：{达标/未达标}
- 补充轮次：{supplement_rounds}

### 生成的测试用例

| 函数/方法 | 测试数 | 覆盖场景 |
|-----------|--------|----------|
| {func_name} | {count} | {scenarios} |

### 未解决问题
{如果有 Validator 无法修复的错误，列在这里}
```

## 目录模式报告

```markdown
## 单元测试生成报告（目录模式）

### 目标
- 源目录：{source_dir}
- 覆盖率目标：{coverage_target}%

### 文件处理汇总

| 源文件 | 测试文件 | 分组数 | 状态 | 覆盖率 |
|--------|---------|--------|------|--------|
| {source_file} | {test_file} | {groups} | ✅/❌ | {cov}% |

### 整体统计
- 处理文件数：{file_count}
- 成功：{success_count}
- 失败：{fail_count}
- 平均覆盖率：{avg_coverage}%

### 未解决问题
{列出所有文件中未修复的错误}
```

## Diff 模式报告

```markdown
## 单元测试生成报告（Diff 模式）

### Diff 范围
- Diff spec：{diff_spec}
- 变更文件数：{changed_file_count}
- 变更函数数：{changed_func_count}

### 变更函数处理

| 源文件 | 变更函数 | 测试文件 | 状态 | 覆盖率 |
|--------|---------|---------|------|--------|
| {file} | {func} | {test_file} | ✅/❌ | {cov}% |

### 增量覆盖率
- 新增可执行行：{added_executable_lines}
- 已覆盖行：{covered_lines}
- 增量覆盖率：{incremental_coverage}%
```

## 函数模式报告

```markdown
## 单元测试生成报告（函数模式）

### 目标
- 源文件：{source_file}
- 目标函数：{function_list}
- 测试文件：{test_file}
- 覆盖率目标：{coverage_target}%

### 执行结果
{与文件模式相同的表格}

### 覆盖率
{与文件模式相同}

### 生成的测试用例
{与文件模式相同}
```

## 状态图标约定

| 图标 | 含义 |
|------|------|
| ✅ | 通过/成功 |
| ❌ | 失败 |
| ❌→✅ | 初次失败，修复后通过 |
| ⚠️ | 部分成功/警告 |
| ⏭️ | 跳过（达到重试上限） |
