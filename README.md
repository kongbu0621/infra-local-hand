# infra-local-hand

跨平台受控本地执行器，为 AI 与自动化系统提供统一的任务、结果和证据接口。

**当前状态：原始 S1 候选 `b763bd6` 已公开，GX10 隔离验收后的修复候选 `1e2f9dc` 也已发布主干。** 后续修复、验证结果及其平台范围见 [S1 后续复核](docs/S1_FOLLOWUP_REVIEW.md)。Windows 延后；新版现役服务切换和 artifact-ledger A2 尚未完成。暂不添加许可证，实机原始证据保留本地。准确发布范围见 [首次公开决定](docs/governance/PUBLICATION_OWNER_DECISION.md)、[GX10 修复发布决定](docs/governance/Q6_MAIN_PUBLICATION_OWNER_DECISION.md) 和 [发布复核](docs/PUBLICATION_VERIFICATION.md)。

**GX10 首轮复现入口：** [原始 S1 任务书](docs/GX10_S1_RUNBOOK.md) 固定到 `b763bd6`，保留原始输入身份。验证后续修复时使用 [复核记录](docs/S1_FOLLOWUP_REVIEW.md) 指定的新候选，仍须新 checkout、独立 build/runtime venv；不同候选的结果分别记录。

安装和接口变化见 [使用说明](docs/USAGE.md)，抽取、恢复修复和验收边界见 [S1 实现说明](docs/S1_IMPLEMENTATION_NOTES.md)。

Local Hand 接收有限、结构化的任务，在本机授权的仓库和验证配置内执行，并返回与任务及运行版本绑定的结果。首阶段保持可信单控制端、scratch／非敏感数据范围，支持 Linux 和 Windows 的共同语义。现有系统已有运行证据，抽取和参数化后的新版本需要重新验证。

| 文档 | 回答的问题 |
| --- | --- |
| [需求](docs/REQUIREMENTS.md) | 为谁解决什么问题、范围和成功条件 |
| [架构](docs/ARCHITECTURE.md) | 职责、接口、信任边界和一致性 |
| [当前实施方案](docs/IMPLEMENTATION_PLAN.md) | S1 如何抽取、参数化、打包和验证 |
| [拆仓与迁移](docs/FORMATION_AND_MIGRATION.md) | 来源、保留项、排除项和后续部署入口 |
| [执行约束](AGENTS.md) | 当前授权、固定规则来源和开工状态 |
| [公开规则摘录候选](docs/governance/PUBLIC_GATE_CANDIDATE.md) | 已批准披露、待批准等价采用的方案 |

当前可执行规则来源是固定版本的 Private companion source，见 AGENTS.md。治理摘录已获准公开，尚未获得等价采用批准，不替代该来源。公开决定暂不添加许可证；固定候选已完成无需私有实现依赖的云端安装验证。

S1 的交付对象是可安装、可验证的通用候选包。S2 才切换真实节点；S3 才接入 artifact-ledger 的 A2 验收。各阶段的证据和授权独立记录。

面向 A2 的后续设计已补齐：复用 GitHub Connector，新 MCP 接入受限作业后端，Plugin 打包操作流程。
见 [需求](docs/a2-execution/REQUIREMENTS.md)、[架构与接口](docs/a2-execution/ARCHITECTURE.md)、
[实施与验收](docs/a2-execution/IMPLEMENTATION_PLAN.md)。Owner 已批准准确基线的 **E1–E3 隔离实现**，
独立开工记录为 `367632126c1930983a06b1854f63789448633148`。
`0.2.0a1` 增加受限作业后端、可选 MCP adapter 和独立 Plugin；
[当前实现状态](docs/a2-execution/IMPLEMENTATION_STATUS.md) 和 [首轮验证记录](docs/a2-execution/E1_E3_VERIFICATION.md)
分别记录 NAS provider 代码缺口、真实 cgroup 等环境阻塞及准确测试结果。
**这不是可部署或 A2 实机验收完成声明。** 真实连接、GX10 [S2 切换](docs/s2/REQUIREMENTS.md) 和 NAS 验收仍分别满足后续门槛。
