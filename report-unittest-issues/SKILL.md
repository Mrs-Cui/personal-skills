---
name: report-unittest-issues
description: 分析当前对话中 AI 单元测试过程遇到的问题，汇总为单个 issue 提交到 GitLab。手动触发，用于在单元测试完成后回顾问题并归档。触发方式：用户明确要求"报告单测问题"、"提交单测 issue"、"report unittest issues"或类似表述时使用。
---

## 运行时上下文

获取当前项目名：

```bash
basename $(git rev-parse --show-toplevel 2>/dev/null || pwd)
```

用户可能提供测试目标参数，若未提供则从对话历史自动推断。

---

## 任务流程

仔细阅读**当前对话的完整历史**，完成以下两个步骤。

---

### Step 1：分析对话历史

#### 1.1 提取测试范围信息

确定测试范围类型（从对话历史推断，四选一）：

| 类型 | scope label | 需记录的具体信息 |
|------|-------------|----------------|
| 目录 | `scope:dir` | 目录路径，如 `internal/services/member/common/` |
| 文件 | `scope:file` | 文件路径，如 `internal/services/member/common/definitions.go` |
| 函数 | `scope:func` | 文件路径 + 函数名列表，如 `definitions.go: GetScoreText, GetProcessMaxScore` |
| diff | `scope:diff` | 分支信息，如 `main..feature/member-refactor` 或 `HEAD~1` |

#### 1.2 提取基本信息

- 使用的 Skill（如 `golang-unittest`、`python-unittest`、`manual`）
- 最终覆盖率（如 `81.3%`，未提及则填 `unknown`）
- 整体状态：`completed` / `partial` / `failed`

#### 1.3 提取问题列表

对每个独立问题，提取：

| 字段 | 说明 |
|------|------|
| 标题 | 简洁描述，如"测试期望值与实际返回不符" |
| 类型 | `compilation` / `mock` / `coverage` / `testing-pattern` / `dependency` |
| 严重程度 | `high`（阻塞）/ `medium`（需手动修复）/ `low`（小问题） |
| 错误信息 | 原始报错关键行，最多3条 |
| 尝试次数 | 同一问题修改了几次才解决 |
| 解决方案 | 最终如何解决 |
| 临时绕过 | 非最优方案则记录，否则填"无" |
| 相关代码 | 见下方规则 |

代码片段贴出规则（仅在有助于理解问题时贴，控制在30行以内）：
- `testing-pattern` → 贴出错的测试函数
- `compilation` → 贴编译失败的代码片段
- `coverage` → 贴未覆盖的源代码分支

如果对话历史中**没有遇到任何问题**（一次通过），输出：

```
✅ 本次单元测试生成过程顺利，无需提交 issue。
```

然后停止，不执行 Step 2。

---

### Step 2：提交单个汇总 Issue

将所有问题汇总为**一个 issue**，使用以下 Python 脚本构造并提交（避免 shell 转义问题）。

将 Step 1 分析结果填入脚本中标注的占位符，然后执行：

使用前需配置环境变量：

```bash
# 在 ~/.zshrc 或 ~/.bashrc 中添加：
# export GITLAB_TOKEN=<your-gitlab-personal-access-token>
# token 需要 api 权限，在 GitLab → Preferences → Access Tokens 中创建
```

```bash
python3 - << 'PYEOF'
import json, subprocess, os

token = os.environ.get("GITLAB_TOKEN", "")
if not token:
    print("❌ 未设置环境变量 GITLAB_TOKEN，请先配置后重试")
    exit(1)
project = "astro%2Fmarket-skills"
api_url = f"https://git.tigerbrokers.net/api/v4/projects/{project}/issues"

# 获取 git 提交人信息
git_user = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True).stdout.strip()
git_email = subprocess.run(["git", "config", "user.email"], capture_output=True, text=True).stdout.strip()
submitter = f"{git_user} <{git_email}>" if git_user and git_email else "unknown"

# ── 以下内容由 AI 根据 Step 1 分析结果填入 ──

title = "{具体范围}-{简单描述}"
# 示例: "internal/services/member/common/ - 测试期望值与实际返回不符等3个问题"

labels = ",".join([
    "AI单测",
    "{skill名}",           # 如 golang-unittest
    "{项目名}",            # 如 campaign
    "{scope label}",       # 如 scope:dir / scope:file / scope:func / scope:diff
    "{整体状态}",          # completed / partial / failed
])

body = """
## 测试范围

- **类型**: {目录 | 文件 | 函数 | diff}
- **{目录/文件/函数/diff}**: `{具体路径或分支}`

## 执行摘要

| 项目 | 值 |
|------|-----|
| 使用 Skill | {skill名} |
| 最终覆盖率 | {覆盖率} |
| 整体状态 | {✅ Completed / ⚠️ Partial / ❌ Failed} |
| 提交人 | """ + submitter + """ |
| 遇到问题数 | {N} 个 |

## 遇到的问题

{对每个问题输出以下格式：}

### 问题 {N}：{问题标题}

- **类型**: {类型} | **严重程度**: {严重程度} | **尝试次数**: {N} 次
- **错误信息**:
  ```
  {原始报错关键行}
  ```
- **解决方案**: {最终解决方案}
- **临时绕过**: {如有，否则省略此行}

{如需贴代码：}
<details>
<summary>相关代码</summary>

```go
{相关测试或源代码片段，≤30行}
```

</details>

---

*由 report-unittest-issues skill 自动生成*
""".strip()

# ── 填入结束 ──

payload = {"title": title, "description": body, "labels": labels}
result = subprocess.run(
    ["curl", "-s", "-X", "POST", api_url,
     "-H", f"PRIVATE-TOKEN: {token}",
     "-H", "Content-Type: application/json",
     "-d", json.dumps(payload)],
    capture_output=True, text=True
)

resp = json.loads(result.stdout)
if "iid" in resp:
    print(f"✅ Issue #{resp['iid']} 已创建：{resp['web_url']}")
else:
    print(f"❌ 提交失败：{resp.get('message') or resp.get('error') or result.stdout}")
PYEOF
```

---

### 最终输出

执行完成后，输出以下汇总：

```
## 📋 汇总报告

- **测试范围**: {类型} → {具体路径/分支}
- **使用 Skill**: {skill名}
- **最终覆盖率**: {覆盖率}
- **整体状态**: {状态}
- **问题数**: {N} 个

✅ Issue #{iid} 已提交：{url}
```
