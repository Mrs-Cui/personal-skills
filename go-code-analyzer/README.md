# Go Code Analyzer Skill

分析 Go 代码库，提取业务逻辑、生成 Mermaid 流程图、构建函数调用层次和服务依赖关系文档。

## 功能

- **函数调用分析**: 从入口点构建完整调用树，覆盖所有层级（Handler → Service → DAO → Client）
- **服务依赖映射**: 识别所有外部服务调用（HTTP、gRPC、Kafka、Redis、MySQL），含接口、超时、失败处理
- **流程图生成**: 生成 Mermaid 流程图，展示所有执行路径、分支和错误处理
- **多入口点支持**: 分析 HTTP 端点、MQ 消费者、定时任务、gRPC 方法

## 使用方式

```
# 分析指定目录
分析 internal/app/campaign 的代码，生成调用链和依赖图

# 分析 git 变更
分析最近一次提交的代码变更，生成服务依赖文档

# 分析指定函数
从 OrderHandler.CreateOrder 开始，追踪完整调用链

# 聚焦依赖
列出 payment 模块的所有外部服务依赖
```

## 输出模式

| 模式 | 适用场景 | 输出内容 |
|------|----------|----------|
| 快速 | 单个函数 | 调用链列表 + 直接依赖 |
| 标准 | 模块/目录 | 调用层次图 + 依赖图 + 入口点 |
| 完整 | 服务级/PR | 完整文档（12 节） |

## 文件结构

```
go-code-analyzer/
├── SKILL.md              # 核心 Skill 定义（工作流、工具策略、约束）
├── README.md             # 本文件
└── references/
    └── EXAMPLES.md       # 输出模板和完整示例
```

## 工具策略

Skill 指导 AI 使用语义分析工具（Serena 的 `find_symbol`、`get_symbols_overview`、`find_referencing_symbols`、LSP 调用层次等），而非手工解析代码文件，确保分析结果的准确性。

## 示例

完整输出示例见 [references/EXAMPLES.md](references/EXAMPLES.md)。
