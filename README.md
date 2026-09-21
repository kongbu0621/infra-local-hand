# infra-local-hand

跨平台受控本地执行器，为 AI 与自动化系统提供统一的任务、结果和证据接口。

**当前状态：Owner 已批准公开 S1 候选 `b763bd6` 及治理摘录，暂不添加许可证。** 云端 Linux 隔离验证已完成；GX10 本机验收待执行，Windows 延后。新版现役服务切换和 artifact-ledger A2 尚未完成。准确发布范围见 [Owner 公开决定](docs/governance/PUBLICATION_OWNER_DECISION.md)。 首轮 GitHub CI：Linux 通过；Windows 为 1 failed、129 passed、9 skipped，留待 Windows 轮处理，详见 [发布复核](docs/PUBLICATION_VERIFICATION.md)。

**GX10 开始入口：** clone 本仓库后，在本地 Codex 中输入“读取 `docs/GX10_S1_RUNBOOK.md`，执行全部 GX10 S1 验收；有问题直接修复复验，保留全部环境和证据，Windows 延后”。任务书固定到完整候选 SHA，并使用新 checkout、独立 build/runtime venv。

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
