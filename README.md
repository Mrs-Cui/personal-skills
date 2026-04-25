# Personal Skills Collection

个人 Claude Code / Agent Skill 合集，涵盖开发工作流、多语言编程模式、文档创作、AI 编排、需求分析等场景。

---

## 快速安装

```bash
# 安装指定 skill（示例）
npx skills add <skill-name>

# 或让 Agent 自动安装
# "帮我安装这个 skill：<GitHub URL>"
```

---

## Skill 目录

### Agent 编排与工作流

| Skill | 描述 |
|---|---|
| [using-superpowers](./using-superpowers) | 对话开始时调用，建立如何发现和使用 skills 的基础框架 |
| [dispatching-parallel-agents](./dispatching-parallel-agents) | 2+ 个独立任务时并行分发 Agent，提升执行效率 |
| [executing-plans](./executing-plans) | 在独立 session 中执行已写好的实现计划 |
| [writing-plans](./writing-plans) | 多步骤任务开始前，将需求写成结构化实现计划 |
| [iterative-retrieval](./iterative-retrieval) | 渐进式精化上下文检索，解决 subagent 上下文丢失问题 |
| [subagent-driven-development](./subagent-driven-development) | 用独立 subagent 并行执行实现计划中的各任务 |
| [strategic-compact](./strategic-compact) | 在逻辑节点建议手动 compaction，保留关键上下文 |
| [brainstorming](./brainstorming) | 任何创意工作（新功能、新组件）前必须调用的头脑风暴框架 |
| [continuous-learning](./continuous-learning) | 自动从 Claude Code session 提取可复用模式并保存 |
| [continuous-learning-v2](./continuous-learning-v2) | 基于直觉的学习系统，通过 hooks 观察 session 并创建 instincts |
| [eval-harness](./eval-harness) | 为 Claude Code session 实现 eval 驱动开发的正式评估框架 |

### 代码开发工作流

| Skill | 描述 |
|---|---|
| [test-driven-development](./test-driven-development) | 实现功能或修 bug 前的 TDD 工作流（先写测试再实现） |
| [tdd-workflow](./tdd-workflow) | 新功能、bug 修复、重构时强制执行 TDD 方法论 |
| [systematic-debugging](./systematic-debugging) | 遇到 bug、测试失败、非预期行为时的系统化调试流程 |
| [verification-loop](./verification-loop) | Claude Code session 的全面验证系统 |
| [verification-before-completion](./verification-before-completion) | 声明工作完成、已修复或通过之前的验证检查 |
| [finishing-a-development-branch](./finishing-a-development-branch) | 实现完成且测试通过后，完成开发分支的收尾流程 |
| [using-git-worktrees](./using-git-worktrees) | 需要与当前工作区隔离的功能开发时使用 git worktree |
| [requesting-code-review](./requesting-code-review) | 完成任务、实现重要功能或合并前请求 Code Review |
| [receiving-code-review](./receiving-code-review) | 收到 Code Review 反馈后、实施建议前的处理流程 |
| [ai-code-review](./ai-code-review) | 基于 git diff 和 CLAUDE.md 业务上下文进行结构化 Code Review |
| [ai-regression-testing](./ai-regression-testing) | AI 辅助开发的回归测试策略，沙盒模式 API 验证 |

### Skill 管理

| Skill | 描述 |
|---|---|
| [skill-creator](./skill-creator) | 创建有效 skill 的指南，包含结构、触发词、最佳实践 |
| [skill-reviewer](./skill-reviewer) | 对照官方最佳实践审查和改进 Claude Code skills |
| [skill-stocktake](./skill-stocktake) | 审计 Claude skills 和命令的质量（快速扫描 / 全量审计） |
| [writing-skills](./writing-skills) | 创建新 skill、编辑现有 skill 或验证 skill 是否有效时使用 |
| [find-skills](./find-skills) | 帮助用户发现并安装所需 agent skills |
| [sync-skills](./sync-skills) | 从本地目录、GitHub URL 或 skillsmp.com 同步 skills |
| [configure-ecc](./configure-ecc) | Everything Claude Code 的交互式安装器 |
| [template](./template) | Skill 模板，创建新 skill 的起点 |
| [project-guidelines-example](./project-guidelines-example) | 基于真实生产应用的项目级 skill 模板示例 |

### 文档与内容创作

| Skill | 描述 |
|---|---|
| [doc-coauthoring](./doc-coauthoring) | 引导用户完成结构化文档协作写作工作流 |
| [internal-comms](./internal-comms) | 帮助撰写各类内部沟通文档 |
| [tech-doc](./tech-doc) | 生成高质量技术方案文档并输出到飞书 |
| [docx](./docx) | 全面的 Word 文档创建、编辑与分析（支持修订追踪） |
| [pdf](./pdf) | PDF 操作工具包：提取文本/表格、创建/合并 PDF |
| [pptx](./pptx) | PowerPoint 演示文稿创建、编辑与分析 |
| [xlsx](./xlsx) | 全面的电子表格创建、编辑与分析（公式、格式化、透视表） |
| [frontend-slides](./frontend-slides) | 从大纲或内容创建动画丰富的 HTML 演示文稿 |
| [web-artifacts-builder](./web-artifacts-builder) | 在 claude.ai 中创建精美的多组件 HTML artifacts |
| [canvas-design](./canvas-design) | 用设计哲学创建 PNG/PDF 视觉艺术 |
| [algorithmic-art](./algorithmic-art) | 使用 p5.js 和种子随机性创作算法艺术 |
| [brand-guidelines](./brand-guidelines) | 将 Anthropic 官方品牌色和排版应用到任意 artifact |
| [theme-factory](./theme-factory) | 为 slides、文档、报表等 artifact 设置主题样式 |
| [slack-gif-creator](./slack-gif-creator) | 创建 Slack 优化的动态 GIF 图 |

### 前端开发

| Skill | 描述 |
|---|---|
| [frontend-patterns](./frontend-patterns) | React、Next.js、状态管理、性能优化等前端开发模式 |
| [frontend-design](./frontend-design) | 创建高设计质量的生产级前端界面 |
| [web-access](./web-access) | 给 Agent 装上完整联网能力（搜索、WebFetch、CDP 浏览器操作） |
| [webapp-testing](./webapp-testing) | 用 Playwright 与本地 Web 应用交互和测试 |
| [e2e-testing](./e2e-testing) | Playwright E2E 测试模式、Page Object Model、CI/CD 集成 |

### 后端与通用

| Skill | 描述 |
|---|---|
| [api-design](./api-design) | REST API 设计模式：资源命名、状态码、分页、过滤 |
| [backend-patterns](./backend-patterns) | 后端架构模式、API 设计、数据库优化、服务端最佳实践 |
| [coding-standards](./coding-standards) | 通用编码标准和最佳实践（TypeScript/JS/Python/Go/Java 等） |
| [mcp-server-patterns](./mcp-server-patterns) | 用 Node/TypeScript SDK 构建 MCP servers（tools、resources、prompts） |
| [mcp-builder](./mcp-builder) | 创建高质量 MCP 服务器的完整指南 |

### Go 语言

| Skill | 描述 |
|---|---|
| [golang-patterns](./golang-patterns) | 地道的 Go 模式、最佳实践和惯用法 |
| [golang-testing](./golang-testing) | Go 测试模式：表格驱动测试、subtests、benchmarks、fuzzing |
| [go-code-analyzer](./go-code-analyzer) | 分析 Go 代码库，生成 Mermaid 流程图、调用层次和服务依赖文档 |
| [go-code-reviewer](./go-code-reviewer) | 管道式 Go 代码审核：PR 增量审核 + 全量代码审计（七维度） |
| [go-unit-test-expert](./go-unit-test-expert) | 专家级 Go 单元测试生成器，自动 mock 接口和依赖 |

### Python

| Skill | 描述 |
|---|---|
| [python-patterns](./python-patterns) | Pythonic 惯用法、PEP 8、类型注解、最佳实践 |
| [python-testing](./python-testing) | Python 测试策略：pytest、TDD、fixtures、mocking、参数化 |
| [django-patterns](./django-patterns) | Django 架构模式、DRF REST API、ORM 最佳实践、缓存 |
| [django-tdd](./django-tdd) | Django TDD：pytest-django、factory_boy、mocking、覆盖率 |
| [django-verification](./django-verification) | Django 项目验证循环：migrations、linting、测试覆盖率 |

### Java / Kotlin / Android

| Skill | 描述 |
|---|---|
| [java-coding-standards](./java-coding-standards) | Spring Boot 服务的 Java 编码标准：命名、不可变性、Optional |
| [kotlin-patterns](./kotlin-patterns) | 地道的 Kotlin 模式、最佳实践和惯用法 |
| [kotlin-testing](./kotlin-testing) | Kotlin 测试：Kotest、MockK、协程测试、属性测试 |
| [kotlin-coroutines-flows](./kotlin-coroutines-flows) | Android/KMP 的 Kotlin Coroutines 和 Flow 模式 |
| [kotlin-exposed-patterns](./kotlin-exposed-patterns) | JetBrains Exposed ORM 模式：DSL 查询、DAO、事务 |
| [kotlin-ktor-patterns](./kotlin-ktor-patterns) | Ktor 服务端模式：路由 DSL、插件、认证、Koin DI |
| [springboot-patterns](./springboot-patterns) | Spring Boot 架构模式、REST API、分层服务、数据访问 |
| [springboot-tdd](./springboot-tdd) | Spring Boot TDD：JUnit 5、Mockito、MockMvc、Testcontainers |
| [springboot-verification](./springboot-verification) | Spring Boot 验证循环：构建、静态分析、测试覆盖率 |
| [android-clean-architecture](./android-clean-architecture) | Android 和 KMP 的 Clean Architecture 模式 |
| [compose-multiplatform-patterns](./compose-multiplatform-patterns) | Compose Multiplatform 和 Jetpack Compose 的 KMP 模式 |

### Rust

| Skill | 描述 |
|---|---|
| [rust-patterns](./rust-patterns) | 地道的 Rust 模式：所有权、错误处理、traits、并发 |
| [rust-testing](./rust-testing) | Rust 测试模式：单元测试、集成测试、异步测试 |

### C++

| Skill | 描述 |
|---|---|
| [cpp-coding-standards](./cpp-coding-standards) | 基于 C++ Core Guidelines 的 C++ 编码标准 |
| [cpp-testing](./cpp-testing) | C++ 测试：GoogleTest/CTest 编写、配置、诊断 |

### Perl

| Skill | 描述 |
|---|---|
| [perl-patterns](./perl-patterns) | 现代 Perl 5.36+ 惯用法、最佳实践和惯用法 |
| [perl-testing](./perl-testing) | Perl 测试：Test2::V0、Test::More、prove、mocking、覆盖率 |

### PHP / Laravel

| Skill | 描述 |
|---|---|
| [laravel-patterns](./laravel-patterns) | Laravel 架构模式、路由/控制器、Eloquent ORM、服务层 |
| [laravel-tdd](./laravel-tdd) | Laravel TDD：PHPUnit 和 Pest、factories、数据库测试 |
| [laravel-verification](./laravel-verification) | Laravel 项目验证循环：env 检查、linting、静态分析 |

### SDD / 规格驱动开发

| Skill | 描述 |
|---|---|
| [sdd-riper-one](./sdd-riper-one) | 将 SDD-RIPER 方法论落地为严格可执行流程（CodeMap + Spec 驱动研发） |
| [sdd-riper-one-light](./sdd-riper-one-light) | 面向强模型（GPT-5.4 等）的轻量 spec-driven / checkpoint-driven coding skill |
| [sdd-workflow](./sdd-workflow) | 端到端 SDD 管线：Design → Plan → Code → Code Review → Unit Test |
| [spec-kit-skill](./spec-kit-skill) | GitHub Spec-Kit 集成，基于 constitution 的规格驱动开发（7 阶段流程） |

### 需求与产品

| Skill | 描述 |
|---|---|
| [requirement-breakdown](./requirement-breakdown) | 根据需求文档进行功能点拆解，面向产品同学，支持飞书链接 |
| [req-to-design](./req-to-design) | 从 PRD 或简要描述生成技术设计文档，利用项目知识库 |
| [okr-coach](./okr-coach) | OKR 写作教练，面向一线开发者，交互式对话写 OKR |

### 工具与质量

| Skill | 描述 |
|---|---|
| [plankton-code-quality](./plankton-code-quality) | 使用 Plankton 在写代码时自动执行格式化、linting、类型检查 |
| [pre-release-check](./pre-release-check) | 基于 git diff 自动生成上线检查清单（DB 变更、配置依赖等） |
| [prompt-optimizer](./prompt-optimizer) | 提示词工程专家，运用 57 种优化技术帮你打磨 prompt |
| [claude-context](./claude-context) | 为代码模块生成或更新 CLAUDE.md 上下文文件 |
| [opencode-kiro-gateway](./opencode-kiro-gateway) | 在 macOS 安装 OpenCode 并配置 Kiro Gateway |

### Campaign 项目专用

| Skill | 描述 |
|---|---|
| [campaign-apidoc](./campaign-apidoc) | 为 campaign 项目 Gin Handler 自动生成 OpenAPI 3.0 接口文档 |
| [campaign-kb](./campaign-kb) | Campaign 项目技术知识库查询（服务、方法、模块等） |
| [check-apidoc](./check-apidoc) | 校验 OpenAPI 3.0 接口文档的结构合法性与接口完整性 |
| [generate-test-doc](./generate-test-doc) | 根据需求文档和 MR 变更自动生成飞书提测文档 |
| [report-unittest-issues](./report-unittest-issues) | 汇总 AI 单元测试遇到的问题，提交到 GitLab issue |

---

## Skill 数量统计

| 类别 | 数量 |
|---|---|
| Agent 编排与工作流 | 11 |
| 代码开发工作流 | 11 |
| Skill 管理 | 9 |
| 文档与内容创作 | 14 |
| 前端开发 | 5 |
| 后端与通用 | 5 |
| Go 语言 | 5 |
| Python | 5 |
| Java / Kotlin / Android | 11 |
| Rust | 2 |
| C++ | 2 |
| Perl | 2 |
| PHP / Laravel | 3 |
| SDD / 规格驱动开发 | 4 |
| 需求与产品 | 3 |
| 工具与质量 | 5 |
| Campaign 项目专用 | 5 |
| **总计** | **102** |

---

## License

各 skill 许可证见各自目录内的 SKILL.md 文件。
