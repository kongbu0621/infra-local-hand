# GX10 S2 需求：现役迁移与可核对回退

- Authority：Owner；状态：DRAFT / **S2 Documentation Gate OPEN**。
- 已复核产品前身：`e6412a1a38e91906355fbd9ec21974993449d743`；最终构建输入在新作业候选验收后固定。
- 规则 R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，采用来源与限制见根 `AGENTS.md`。
- 本组文档不改变 S1 文档基线、既有 closure 或八动作权限。
- Owner 本轮同意方案和只读准备；尚未对本组三文档既有 commit 作 S2 closure。

## 目标与范围

Local Hand 为 `infra-artifact-ledger` 的 GX10 A2 验收提供受控执行能力。
路径是公开独立仓库、GX10 可用闭环、A2 项目接纳；S2 不是通用 Agent 平台扩展。
S1 证明候选在隔离环境中的行为；S2 要证明实际部署、任务账本、来源和恢复均可核对。
现役服务切换不能仅以 `active`、源码测试通过或 controller 收到结果作为完成依据。

本轮可交付三层方案、现有动作范围内的只读盘点和缺口记录。
后续 S2 实施范围为独立安装、成对 controller/Worker 迁移、单 writer 切换及回退验收。
实施须有准确文档基线和独立 closure 记录；本文件不授权生成新运行配置或迁移状态。
真实切换另须准确私有部署 manifest、前置验收及对应操作授权。

## 需求与成功条件

| ID | 用户可观察要求 | 成功条件与失败信号 |
| --- | --- | --- |
| S2-R01 | 只使用已核对的真实输入 | 实际旧部署、拟部署 source/wheel/profile/controller 身份可追溯；未知不能填作默认值 |
| S2-R02 | 保留现役环境和历史证据 | 独立 checkout、build/runtime venv、安装目录、state 与 mailbox clone；旧目录不被覆盖或删除 |
| S2-R03 | 同一目标只有一个执行者 | 新实例启动前旧 Worker、子进程和自动重启来源均已停；全部任务生产者处于冻结状态 |
| S2-R04 | 升级不丢失防重放证据 | Task、receipt、Result、conflict、outbox、quarantine 按任务身份全量核对；不明任务不重执行 |
| S2-R05 | 切换前后来源明确 | controller 与 Worker 配置成对更新；新 Task 的来源预期为实际新部署，历史结果保留原来源 |
| S2-R06 | 部署失败可以核对地回退 | 区分新实例未执行与已执行／状态不明；回退保留新证据并验证旧版不会重放 |
| S2-R07 | 服务健康反映真实业务闭环 | 固定只读健康任务成功、来源匹配、无非预期重启、outbox 真正清空、观察期无轮询错误 |
| S2-R08 | 操作和结果可独立验收 | 完整命令、退出状态、日志摘要、文件类型与内容清单、前后身份和恢复记录可交叉核对 |
| S2-R09 | 权限受既有范围约束 | 不通过 CAS 写脚本或借 validation 执行未准入主机／NAS 操作；缺能力记作阻塞 |
| S2-R10 | S2 对 A2 有明确出口 | 真实切换前明确 A2 后续执行与证据交付路径；仅升级现有八动作不能声称 A2 已可执行 |

## 必须冻结的私有部署字段

以下字段的准确值只进入私有 deployment manifest；公开方案保存字段定义和脱敏结论。
manifest 必须具有版本、摘要、采集时间、证据引用和审查状态，不得以模板代替已冻结输入。

| 字段组 | 必需内容 |
| --- | --- |
| 旧部署 | 节点、运行账户与组、unit/别名/drop-ins、enabled/restart 配置、解释器、代码和安装来源 |
| 新部署 | 固定 source、wheel 摘要、完整 payload、Python 与包位置、install UUID、独立安装根 |
| 配置 | profile 原始字节摘要、精确项目 allowlist、各 validation argv/timeout/replay_safe、传输策略 |
| 运行绑定 | state、mailbox、projects、安装记录、Git/SSH 可执行文件、key/known_hosts 引用及权限 |
| 任务生产者 | 所有 controller、自动化入口、各 clone/policy/来源预期、冻结及恢复负责人和方法 |
| 迁移账本 | Task/receipt/Result/conflict/quarantine 对应关系、未决项、冻结时 mailbox 提交、文件清单 |
| 操作约束 | 停机窗口、排空和停止期限、检查点、失败条件、回退路径、私有证据归档位置 |

凭据内容不进入报告；运行路径、账户、mailbox 和机器身份不进入公共仓库。
当前已知与未知逐项见 [READINESS.md](READINESS.md)，不能将 S1 历史快照当成当前现场。

## 不可接受后果

- 新旧实例或多个入口对同一目标并行产生副作用。
- 因等待超时、缺 Result、空 outbox 或回退旧快照而重新执行结果不明任务。
- 改写历史 receipt/Result 的来源、覆盖冲突、删除失败现场或未跟踪控制文件。
- 以完整 payload 未变为由伪造新 wheel 的 source commit，或跳过安装绑定校验。
- 对权限错误、链接、无法枚举、无法确认进程退出等状态报告不存在或 PASS。
- 将现有只读成功、MCP server 启动或服务 active 写成 S2／A2 完成。

## A2 与接口选择

A2 的准确输入和既有 closure 见 [A2_CAPABILITY_MAP.md](A2_CAPABILITY_MAP.md)。
保留 Ledger 本体 `A2-snapshot-nas-restore-v0.1` S1–S5 已有 CLOSED，不重复要求其开工批准。
Local Hand 项目接纳、主机操作、NAS 副作用和私有二进制证据交付仍须独立限定。
现有 GitHub Connector/mailbox 继续支持旧准入操作；Owner 要求将 Connector、MCP、Plugin
都纳入有用的设计。具体路线见 [新作业需求](../a2-execution/REQUIREMENTS.md)：复用 Connector，
新 MCP 接入唯一作业后端，Plugin 打包流程；首版不把新作业桥接进旧 mailbox。
新 scope `LH-A2-EXEC-MCP-v1` 仍为 OPEN，不自动增加动作、账户权限或豁免恢复账本。

S2 出口是可证明的新部署和回退能力，加上明确的 A2 后续路径。
实际 A2 作业执行、NAS 配置、生产数据、Windows 和 Git Authority 均不由本 S2 方案批准。
主机入口、状态兼容和单 writer 的未决项不阻塞方案审查，但阻塞真实切换。
A2 方面，切换前须冻结足以覆盖能力缺口的接纳、作业和证据交付路径及对应授权计划；
缺少这条具体路径阻塞切换。其实现和部署验收可在独立 scope 中分阶段进行，
不要求先把全部 A2 实机验收完成才能完成 S2，也不把规划写成已具备能力。
部署选择为新作业 E1–E3 验证后的准确候选，并先通过 E4 当前客户端接入；
不先对 e6412a1 单独切换一次，再为新 jobs 重复切换。新增源码不继承 S1 的测试结论。
