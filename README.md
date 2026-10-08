# infra-local-hand

跨平台受控本地执行器，为 AI 与自动化系统提供统一的任务、结果和证据接口。

**当前阶段（2026-10-08）：核心现场链尚未跑通，journal 扩容未完成。**
最新 GS2 单次维护 `lhqjgrow-20261008d` 已消费且失败；GS3 与 H01/Q4/H11 均未执行。
见[准确冻结及现场返回](docs/a2-execution/Q2_CORE_GUEST_STARTUP_CONTINUATION_FIELD_20261008.md)。

Owner 批准准确 A `7ea9aed` 的 GS1–GS3，并确认 guest 管理前提和间接启动覆盖缩减。
准确 B、独立 C 已先行登记；执行候选 `3417965` 已发布、验证并冻结，首次 CI 3/3 通过。
Linux 7133 项通过、89 项跳过，独立安装 94 项检查通过；早期 Windows 导入失败及修复
记录保留。两处通用间接启动类别阻断已删除，报告明确 NOT_PERFORMED，其余目标保护保持。

本次普通预检通过，同窗 execute 在 `PRE_QUIESCENCE / GROWTH_UNDECLARED_BUSINESS_UNIT`
停止，已有诊断指向 system manager 的一个未声明业务单元检查；不据此断言存在实际写入。
动作列表为空，没有关机令牌、备份、扩容或重启。仅保留已产生原件，未追加查询、重试、
补采、清理或恢复。私有 gate 已终止，条件核心包未生成或发送。

后续已补齐同次拒绝诊断：命中属性、业务根摘要/序号、内容摘要及字节位置；模板另记
物理行号。复用已读取内容，不改变拒绝条件。相关本地回归 1374 passed / 5 skipped。
诊断提交 `fd6f2a6` 的准确 CI 已 3/3 通过，本地定向 48 项通过。
[本地原件离线核对](docs/a2-execution/Q2_CORE_GUEST_REFERENCE_OFFLINE_REVIEW_20261008.md)已完成：
清单可从原输入复现；该轮检查材料缺少命中单元的当时属性和历史启动绑定，当时尚不能
区分漏声明与相似路径误匹配。后续当前读取和 C10 核对结果如下，现场仍未修复。

[单单元当前读取已完成](docs/a2-execution/Q2_CORE_UNIT_CURRENT_REVIEW_20261008.md)：一次 SSH
完整返回，当前 ExecStart 命中保护根下真实的 Q1 worker/runtime 路径，不是相似子串。
该准确单元未声明；原路径判断保持，未再次执行维护。当前观察不回填 08d 历史。

[C10 离线核对已完成](docs/a2-execution/Q2_CORE_UNIT_CURRENT_REVIEW_20261008.md)：本地原件
匹配历史 pin，runtime 唯一匹配同条配置，七项身份重算与准确单元名相同。对应父域
也未声明，私有候选差额为一个服务及其 system slice / cgroup，数量 18/6/6 → 19/7/7。
准确来源和差额已留存；原冻结输入未改，当前 cgroup、完整 Manifest 校验和维护准入
仍未完成。该[离线交接](docs/a2-execution/CORE_UNIT_CURRENT_TASK_20261008.txt)无需重做。

已将唯一下一步合为[准确方案 A `e66b1b5`](docs/governance/Q2_CORE_Q1_BINDING_CONTINUATION_BASELINE.md)：
采用已核对来源，补齐准确服务及父域，维护/核心两侧一次接齐；新 08e 维护成功后直接
接原 07a 的 H01→Q4→H11。当前为 PROPOSED/OPEN，尚未批准、实现或执行；保留所有
原校验，不增加扫描/诊断支线，不再次搜证。按仓库既有 R，需要 Owner 对该准确批次
及来源采用作一次决定；方案内不逐子步骤重复审批。

六旧维护窗口与本次消费、原件、完整费用和 UNKNOWN 保留。[获准旧 08c 五件最小索引](docs/a2-execution/Q2_CORE_EXEC_ORIGINALS_INDEX_20261008.md)
已公开；新 08d 原文及索引保持私有。所有旧交接均不重放，不自动申请下一窗口。
Owner 要求只推进任务执行、运行中取消、同一任务恢复查询和结果收回；全宿主扫描扩展、
额外诊断平台及其它支线停止新增。生产 E3、E4–E6 与 NAS 不在本轮范围。

以下为此前接续沿革，不作为重放历史批次或恢复支线的入口。

固定本地补证 L1–L6 限定任务已完成，结果仍为 `OBSERVED_PARTIAL`。已完成范围内的离线组件，见[费用来源复核](docs/a2-execution/Q2_COST_SOURCE_IMPLEMENTATION_REVIEW.md)。完整账单和 FS 资格仍需闭合；无需重复已有采集或权限维护。

已进入[H07 cgroup 监督原语隔离实验](docs/governance/Q2_H07_CGROUP_FENCE_SPIKE_BASELINE.md)，准确 A `71c7e842`；Owner 已批准 F1–F4，独立 C 为 `8deeed49`。现已完成两轮，第二轮失败后的事实与停止边界见[第二轮结果复核](docs/a2-execution/Q2_H07_ROUND2_RESULT_REVIEW.md)；局部实验不等于原 Q2 已准入。

实验首轮 `36577764454` 在账户 setup 失败，probe 与六案均为 NOT_RUN；首轮当时额度为 **1/3**。
参数修复及其验证已完成，原结果仍为 **UNKNOWN_RETAINED / cleanup.verified=false**。
[首轮历史异常的限定续验 A `a08a5055`](docs/governance/Q2_H07_R1_CONTINUATION_BASELINE.md)
已获 Owner 批准，U1–U4 **CLOSED**，独立 C 为 `7d33c698`；仅该首轮历史未知不再单独阻断剩余限定续验，后续停止条件保持。

准确运行 HEAD `9d8328cf742fa130c265de23b1b9085b9e8a0581` 的普通 CI
[36655111148](https://github.com/kongbu0621/infra-local-hand/actions/runs/36655111148) attempt 1 已 **3/3 成功**，见[准确 CI 证据](docs/a2-execution/evidence/q2-h07-cgroup-fence-spike/round-2-ordinary-ci.json)。
同一 HEAD 的第二轮 [36662298613](https://github.com/kongbu0621/infra-local-hand/actions/runs/36662298613) attempt 1 为 **FAILURE**：probe 支持，但 C1 缺 launcher/account binding，原报告保持 **UNKNOWN_RETAINED**；账户创建与删除已完成，`cleanup.verified=true`、`residuals=[]`，C2–C6 为 NOT_RUN。
当前额度 **2/3**，**第三轮 NOT_DISPATCHED**。第二轮结束时新增 UNKNOWN 触发原停止条件；Owner 随后批准下述准确限定续验，但实际实现和准入尚未闭合，仍不能派发。原件、时间线和历史缺口见[第二轮结果复核](docs/a2-execution/Q2_H07_ROUND2_RESULT_REVIEW.md)及[首轮续验实施复核](docs/a2-execution/Q2_H07_R1_CONTINUATION_IMPLEMENTATION_REVIEW.md)。

第二轮后的[准备复核](docs/a2-execution/Q2_H07_R2_PREPARATION_REVIEW.md)确认准确Ubuntu源码包缺少相关内核修复；旧范围测试修复`824f4be4`的普通CI已3/3成功。准确[A `eac5e654`](docs/governance/Q2_H07_R2_CONTINUATION_BASELINE.md)现已获[Owner批准](docs/governance/Q2_H07_R2_CONTINUATION_OWNER_DECISION.md)，**V1–V4 CLOSED**，独立C为`eb96b873`。当前仅完成可分离的纯数据组件；原生实现被平台自动检查阻断，整体 **PARTIAL**，实际fixture与最后一轮未运行。见[准确实现与阻断记录](docs/a2-execution/Q2_H07_R2_PARTIAL_IMPLEMENTATION_REVIEW.md)。

**S1 发布沿革：原始候选 `b763bd6` 已公开，GX10 隔离验收后的修复候选 `1e2f9dc` 也已发布主干。** 后续修复、验证结果及其平台范围见 [S1 后续复核](docs/S1_FOLLOWUP_REVIEW.md)。Windows 延后；新版现役服务切换和 artifact-ledger A2 尚未完成。暂不添加许可证，实机原始证据保留本地。准确发布范围见 [首次公开决定](docs/governance/PUBLICATION_OWNER_DECISION.md)、[GX10 修复发布决定](docs/governance/Q6_MAIN_PUBLICATION_OWNER_DECISION.md) 和 [发布复核](docs/PUBLICATION_VERIFICATION.md)。

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
分别记录受监督启动准备和 NAS provider 代码缺口、真实 cgroup 等环境阻塞及准确测试结果。
随后确认的边界缺陷、修复候选与独立安装/平台验证见[实现复查记录](docs/a2-execution/E1_E3_RECHECK.md)。
新增构建身份、监督恢复与控制/证据边界修复见[第二轮实现复核](docs/a2-execution/E1_E3_RECHECK_2.md)。
未知执行容量、捕获清理、当前密钥准入及最终产物持久化修复见[第三轮实现复核](docs/a2-execution/E1_E3_RECHECK_3.md)。
恢复结果、EOF 预算和证据目录持久化链修复见[第四轮实现复核](docs/a2-execution/E1_E3_RECHECK_4.md)。
业务结果与报告状态、耗尽预算、路径别名及并发封存修复见[第五轮实现复核](docs/a2-execution/E1_E3_RECHECK_5.md)。
资源清理、异常归属、下载恢复及部署入口检查修复见[第六轮实现复核](docs/a2-execution/E1_E3_RECHECK_6.md)。
预检恢复、目录创建及资源清理的进一步修复见[第七轮实现复核](docs/a2-execution/E1_E3_RECHECK_7.md)。
配置绑定、目录替换、资源清理及证据校验的后续修复见[第八轮实现复核](docs/a2-execution/E1_E3_RECHECK_8.md)。
完整字节校验、并发资源绑定及恢复边界的后续修复见[第九轮实现复核](docs/a2-execution/E1_E3_RECHECK_9.md)。
读取完整性、跨阶段执行预算及准入失效的后续修复见[第十轮实现复核](docs/a2-execution/E1_E3_RECHECK_10.md)。
当前新作业生产入口明确拒绝启用；模拟环境测试通过不能解除这个实现阻塞。
历史 CPUQuota retry 批次完成准备并收回证据，监督器启动失败，结果保持 `INCOMPLETE`。
该次启动排队、受限身份检查修复与平台验证见
[监督器启动修复记录](docs/a2-execution/Q2_SUPERVISOR_STARTUP_REPAIR_VERIFICATION.md)；
历史批次与剩余阶段见[当前实现状态](docs/a2-execution/IMPLEMENTATION_STATUS.md)。
后续单次启动重试范围已获[Owner 准确批准](docs/governance/Q2_SUPERVISOR_STARTUP_RETRY_OWNER_DECISION.md)，
按固定 R/A 记录为 CLOSED；该新批次仍为 NOT ISSUED，不能把授权关闭解释为可以跳过现场准入。
后续对账、host 窗口与固定内核读取的独立授权及边界见 [AGENTS.md](AGENTS.md)。
K4 已完成限定的完整回执核验，完整账单、H07 首次远端截止与停止覆盖、wrapper 来源绑定和文件系统资格仍缺证据。
本轮已完成[离线来源差额核对](docs/a2-execution/Q2_OFFLINE_SOURCE_GAP_REVIEW.md)，含写入器身份限制与原观察条件的差异。
后续已完成[v1 记录／账单绑定修复](docs/a2-execution/Q2_HOST_RECORD_BINDING_REPAIR_REVIEW.md)，Q2 相关回归 942 PASS / 5 SKIP；当时普通身份写入尚未实现；现已由后述显式 v2 组件补齐，完整实机准入仍未完成。
随后[固定本地来源补证](docs/governance/Q2_LOCAL_SOURCE_EVIDENCE_BASELINE.md)准确 A `b8b9ec3d` 已获[Owner 关闭决定](docs/governance/Q2_LOCAL_SOURCE_EVIDENCE_OWNER_DECISION.md)，授权 L1–L6；独立 C `8e754519` 后已完成 最终 D `411a9f05` 的 L1–L4 实现、相关回归和准确 RAM 交付，见[实现复核](docs/a2-execution/Q2_LOCAL_SOURCE_EVIDENCE_IMPLEMENTATION_REVIEW.md)。[首次 L5 回执](docs/a2-execution/Q2_LOCAL_SOURCE_EVIDENCE_FIELD_REVIEW.md)已收到并核对：父目录保护阻断，11项均未尝试、4份原文未取得；L6阻断复核完成，Q2仍未验收。
后续89c725ef诊断、rerun1及rerun2的BLOCKED历史均保留。2026-09-29已完成盘点、六文件维护及[rerun3完整回执复核](docs/a2-execution/Q2_LOCAL_SOURCE_EVIDENCE_COMPLETION_REVIEW.md)：11项匹配，四份控制原文返回，结果为`OBSERVED_PARTIAL / final_local_recheck`；固定本地补证L1–L6限定任务完成。随后[显式 wrapper profile 修复](docs/a2-execution/Q2_WRAPPER_PROFILE_IMPLEMENTATION_REVIEW.md)在原 H1/H4 内完成，准确 D `22efa42`、143 个不同定向测试通过；旧默认及现场门保持。普通操作者的[显式 v2 记录组件](docs/a2-execution/Q2_ORDINARY_WRITER_IMPLEMENTATION_REVIEW.md)随后在原 H1/H2/H4 内完成，准确 D `c2373313` 的 CI 3/3 成功，旧 v1 root 合同、内核读取与现场门保持；组件验证不代表原机准入。本轮[首次父目录增量计费修复](docs/a2-execution/Q2_PARENT_ALLOCATION_IMPLEMENTATION_REVIEW.md)在 H2/H3/H4 内完成，准确 D `530a2a45` 的 CI 3/3 成功；同一原预留内准确分配 actual/future，父旧基数与完整现场资格仍未证明。当前按[执行准入差额与方案](docs/a2-execution/Q2_POST_SOURCE_ADMISSION_PLAN.md)处理实际来源/环境绑定、H07、完整账单、普通身份现场装配与FS峰值/持久资格；既有回执中的12KiB索引父目录仍超出writer窄profile。无需重做同一采集或权限维护。
随后完成[H07 固定域与队列一致性组件](docs/a2-execution/Q2_H07_MODEL_IMPLEMENTATION_REVIEW.md)，准确 D `293cb51f` 的 CI 3/3 成功、Linux 新增 84 项通过：分别保留两条请求边的提交/排队/未知状态，模型不能生成现场停止或运行许可；同时补拒 ext4 EA_INODE。当前仍需实际首次远端监督、完整费用和 FS 资格。
现已增加[离线费用来源／覆盖主张组件](docs/a2-execution/Q2_COST_SOURCE_IMPLEMENTATION_REVIEW.md)，初次实现 `7e802685` 的本地相关回归 223 PASS / 0 SKIP；修复 Windows 大输入用例名后，最终 D `24b5536c` 的原生 CI **3/3 成功**，Linux／Windows 各新增 78 项通过。严格引用、别名与重复抵扣核对不产生完整账单。参见[H07 接线边界](docs/a2-execution/Q2_H07_MECHANISM_ROUTE_REVIEW.md)和[FS／费用具体缺项](docs/a2-execution/Q2_FS_BILLING_SOURCE_CONTRACT.md)。
旧提交的通用 CI 失败记录保留；后续[CI 装配与平台边界修复](docs/a2-execution/CI_REPAIR_20260928.md)记录准确修复版本及验证结果。源码／CI 通过与 K4 完成均不构成完整 Q2 验收。

[2026-09-30 全仓红叉核查](docs/a2-execution/CI_FAILURE_AUDIT_20260930.md)逐项核对了发布前全部 80 次运行：25 次普通 CI 历史失败已有修复，2 次失败属于已退休实验；本轮另修复 PR 累计变更、中文路径和移动文件导致的测试漏跑。旧失败记录保留，当前检查以准确提交的 CI 为准。
**这不是可部署或 A2 实机验收完成声明。** 真实连接、GX10 [S2 切换](docs/s2/REQUIREMENTS.md) 和 NAS 验收仍分别满足后续门槛。
