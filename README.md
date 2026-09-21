# infra-local-hand

跨平台受控本地执行器，为 AI 与自动化系统提供统一的任务、结果和证据接口。

**当前状态：独立仓库文档候选，Documentation Gate OPEN。** 本目录尚不包含新产品实现；Public 仓库已创建，源码发布、GX10 新版部署及 artifact-ledger A2 验收尚未完成。

Local Hand 接收有限、结构化的任务，在本机授权的仓库和验证配置内执行，并返回与任务及运行版本绑定的结果。首阶段保持可信单控制端、scratch／非敏感数据范围，支持 Linux 和 Windows 的共同语义。现有系统已有运行证据，抽取和参数化后的新版本需要重新验证。

| 文档 | 回答的问题 |
| --- | --- |
| [需求](docs/REQUIREMENTS.md) | 为谁解决什么问题、范围和成功条件 |
| [架构](docs/ARCHITECTURE.md) | 职责、接口、信任边界和一致性 |
| [当前实施方案](docs/IMPLEMENTATION_PLAN.md) | S1 如何抽取、参数化、打包和验证 |
| [拆仓与迁移](docs/FORMATION_AND_MIGRATION.md) | 来源、保留项、排除项和后续部署入口 |
| [执行约束](AGENTS.md) | 当前授权、固定规则来源和开工状态 |
| [公开规则摘录候选](docs/governance/PUBLIC_GATE_CANDIDATE.md) | 待 Owner 批准的公开采用方案 |

当前可执行规则来源是固定版本的 Private companion source，见 AGENTS.md。公开摘录尚未获批，也尚未替代该来源。最终发布前须完成公开材料审查、许可证决定以及无需私有实现依赖的安装验证。

S1 的交付对象是可安装、可验证的通用候选包。S2 才切换真实节点；S3 才接入 artifact-ledger 的 A2 验收。各阶段的证据和授权独立记录。
