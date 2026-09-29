# E1–E3 实现候选状态

## 2026-09-29 当前接续

**固定本地来源补证L1–L6限定任务已完成。** 最新89c725ef rerun3完整回执为`OBSERVED_PARTIAL / final_local_recheck`：11项均匹配且各自读前后元数据稳定，四份控制原文已返回；收件及静态依赖复核完成。见[限定完成复核](Q2_LOCAL_SOURCE_EVIDENCE_COMPLETION_REVIEW.md)。

随后已完成原 H1/H4 内的[有限 wrapper profile 兼容修复](Q2_WRAPPER_PROFILE_IMPLEMENTATION_REVIEW.md)，准确 D `22efa42ab362ab3ea4b811fc1c1519ddc2ef2bb3`，143 个不同定向测试通过。新 profile 显式选入；旧默认和全部现场门保持。原件仅静态匹配，未执行或采用为执行来源。

普通操作者的[显式 v2 记录组件及纯账单绑定](Q2_ORDINARY_WRITER_IMPLEMENTATION_REVIEW.md)随后在原 H1/H2/H4 内完成。旧 v1 仍按 root 合同验证；生产 loader、原内核/FS 资格及 field readiness 拒绝保留。准确 D `c2373313` 的原生 CI 3/3 成功，Linux 新增 99 项均通过，包含 20 项真实普通身份操作；组件验证与原机资格分开登记。

本轮[首次父目录增量计费组件](Q2_PARENT_ALLOCATION_IMPLEMENTATION_REVIEW.md)已在 H2/H3/H4 内完成，准确 D `530a2a45` 的 CI 3/3 成功，Linux 新增 84 项通过（含 2 项真实普通身份用例）。已有首次 metadata 与 marker snapshot 固定绑定，显式 bill/v2 将 G 从同一原池 future 转入 actual，总预留保持；父旧基数 UNPROVEN、完整账单/FS/现场门不放行。具体后续见[现场资格复核](Q2_FIELD_QUALIFICATION_NEXT_REVIEW.md)。

旧四份BLOCKED、11文件/8目录盘点和六文件维护各自保留。无需再采集同一11项或改权限。下一步按[执行准入差额](Q2_POST_SOURCE_ADMISSION_PLAN.md)处理来源与环境绑定、H07、完整账单、普通身份现场装配及FS资格；当前Q2仍未验收，共享依赖仍UNKNOWN。

K4 的准确实现 D 为 `e15c633adbdfbf1e29cb12b2410975fe4911458d`，完整回执复核见
[Q2_KERNEL_FACT_READ_FULL_RETURN_REVIEW.md](Q2_KERNEL_FACT_READ_FULL_RETURN_REVIEW.md)。
回执仍为 `OBSERVED_PARTIAL` / `final_local_recheck`，不证明完整 Q2 准入。

| 范围 | 当前授权与执行状态 |
| --- | --- |
| 单次监督器启动重试 | A `47b351b2b943bf1d6f1c71cfeb031157a2eb70cc` 已由 [Owner 决定](../governance/Q2_SUPERVISOR_STARTUP_RETRY_OWNER_DECISION.md)关闭；独立 C 为 `d4a925c883672fadc7d1b10a8dfe58df18b922cd`。该新批次仍 NOT ISSUED，单次授权尚未消费。 |
| 安装预留对账 | A `c65ff4e25ea6373aabf8db25d304ee7614b96eb5` 的 P1–P6 已 CLOSED；保留历史来源、准确义务和原累计上界。 |
| host 窗口消费 | A `8402f0cc82d8a0ac0b9a56716bf276f41cafea37` 的 H1–H6 已 CLOSED；完整现场派发仍因证据缺口 NOT READY。 |
| 固定内核事实读取 | A `887b640b394f9983f37dfe97c58ba35aaa099359` 的 K0–K4 已 CLOSED；K1–K4 各自限定任务已完成，含完整回执接收及核验。 |
| 固定本地来源补证 | A `b8b9ec3da3de43b72e4e17416ea6633494d50c1d` 的 L0–L6 已 CLOSED；独立 C `8e7545199bde66583e1d643656dece867ab1dbda` 后完成实现与交付。最新诊断 D `89c725efd61dad11b0cc9ae11c3c08a941e3111a` 的 [rerun3](Q2_LOCAL_SOURCE_EVIDENCE_COMPLETION_REVIEW.md)为11 MATCHED / 4 raw，L5收件与L6限定静态复核完成；不是完整Q2准入。 |

以上准确 R/A、Owner 决定和独立 C 以根 [AGENTS.md](../../AGENTS.md)及其引用记录为准。
冻结设计文件的历史 OPEN 标签保留，不覆盖后续有效关闭记录；本状态更新不产生新授权或新批次。

当前继续离线核对完整账单、H07 首次远端截止与停止覆盖、wrapper 来源与执行绑定、文件系统分配及持久资格。
此前[来源差额核对](Q2_OFFLINE_SOURCE_GAP_REVIEW.md)确认旧 anchor 缺历史 host 字段；wrapper 原件已恢复，旧默认不支持其语法，后续显式 profile 已完成限定兼容验证；实际来源与环境绑定仍未闭合。
此前写入器的 root-only 条件与 K4 当次报告的普通身份／父目录不匹配。后续显式 v2 组件补齐普通身份支持，旧 v1 不放宽；这不证明当前 FS 或完整现场准入。
随后[v1 跨层绑定修复](Q2_HOST_RECORD_BINDING_REPAIR_REVIEW.md)已在实现
`14d19f1f52d687afa360353aadecd6ea17725310` 完成：记录／预检／账单身份一致性与写入时身份检查加强，
相关 Q2 回归 942 PASS / 5 SKIP。当时普通身份 writer 尚未实现（后续组件结果见页首）；新增[固定本地补证基线](../governance/Q2_LOCAL_SOURCE_EVIDENCE_BASELINE.md)
准确 A 为 `b8b9ec3da3de43b72e4e17416ea6633494d50c1d`，已获[准确 Owner 决定](../governance/Q2_LOCAL_SOURCE_EVIDENCE_OWNER_DECISION.md)
关闭该范围 Gate 并授权 L1–L6；随后已完成[固定来源采集器与准确 RAM 交付](Q2_LOCAL_SOURCE_EVIDENCE_IMPLEMENTATION_REVIEW.md)，
相关开发回归 211 PASS / 3 SKIP及原准确交付保持。诊断修复`89c725ef`的六组236 PASS / 3 SKIP和准确离线包验证保持。首次调用及其后三份诊断的BLOCKED详见[历史收件记录](Q2_LOCAL_SOURCE_EVIDENCE_FIELD_REVIEW.md)。本次rerun3在六文件维护后完成11项读取和最终parent/marker/boot复检；每文件稳定不等于全体同刻稳定，当前分配量不等于完整账单。准确结果和后续支持差额见页首新复核。
现有本地观察不能补齐这些事实；`allow_run`、`allow_consume`、Q2/Q3 验收与 production supported 均仍为 false。
新作业生产入口继续保留 `E3_SUPERVISION_UNVERIFIED`；E1–E3 未全部完成，E4–E6 及 S2 未因此启动。

既有内核读取定向验证为 331 PASS / 3 SKIP；通用 CI 保留 Linux 21 FAILED / 2140 PASS / 31 SKIP、
Windows 6 项收集错误 / 7 SKIP，详见[实现复核](Q2_KERNEL_FACT_READ_IMPLEMENTATION_REVIEW.md)。
这些是各自准确版本的历史结果；后续 [2026-09-28 CI 修复](CI_REPAIR_20260928.md)记录
`3d9b9ff306bc6c4cfc48bafbeaaad4f114a5dafe` 的测试装配、平台边界及准确验证结果。
不把局部成功改写为全仓 PASS，也不把 CI 修复解释为原机 Q2 验收。

## 历史批次与实现沿革

2026-09-27 CPUQuota retry 历史状态：一次已批准的批次已真实执行并回收原始证据，
准备达到 `RETRY_PREPARED`，监督器返回 `BLOCKED / PermissionError`，外层保持
`INCOMPLETE / SUPERVISOR_DELIVERY_UNCERTAIN`。旧记录、未消费账本及七个空根的既有保留检查通过，
但这些检查未证明全部 atime 不变；原始独立停止与 seal 也未形成，后续观察不补判该尝试成功。
准确执行、启动排队/受限身份检查修复及验证边界见
[监督器启动修复记录](Q2_SUPERVISOR_STARTUP_REPAIR_VERIFICATION.md)。
本次代码修复不重放已消费的 300 秒窗口，不替换原实机安装；Q2、Q3/Q4、E3 和生产仍未验收。
修复候选 `b49d3df3d1e76813faf08e59ab4975e25279c2fc` 已完成本地完整源码与隔离安装验证，原生 Linux/Windows CI 均通过。
新一次运行的准确三文档 A 为 `47b351b2b943bf1d6f1c71cfeb031157a2eb70cc`，
形成时为 OPEN，见[新批次提案登记](../governance/Q2_SUPERVISOR_STARTUP_RETRY_BASELINE.md)；
后续准确 Owner 决定已关闭该范围，当前授权和剩余执行阻塞见页首。

2026-09-25 第六批历史进展：Q2 第六批已补常驻 broker test-only composition、原预算管理装配和
首个 preflight 的一次 fixture 入口，并修复启动/readiness/有限轮询问题，见
[第六批实现与准确剩余缺口](E3_QUOTA_Q2_RESIDENT.md)。完整 business/evidence 跨阶段账本装配、
外层 controller 生命周期及真实 Q3/Q4 尚待完成；生产仍固定封堵。
本批固定回归 872 项：857 通过、15 环境跳过、零失败；准确源码与发布映射见
[第六批验证](E3_QUOTA_Q2_RESIDENT_VERIFICATION.md)。

第五批历史进展：Q2 第五批新增认证常驻桥接、已准备单阶段驱动、管理员先关闭的双账本顺序及外层采集，
见 [第五批实现和准确剩余缺口](E3_QUOTA_Q2_BRIDGE.md)。常驻 broker 的 test-only composition、
原预算管理配置装配及完整 fixture 启动器尚待完成；未执行真实 Q3/Q4，生产仍封堵。
本批固定回归 822 项：807 通过、15 环境跳过，见 [第五批验证](E3_QUOTA_Q2_BRIDGE_VERIFICATION.md)。

第四批历史进展：Q2 第四批已实现六单元关闭合同、原普通客户端双流采集、独立管理监督组件、
broker 阶段关闭检查及一次组合预检，见 [第四批实现与固定 fixture 交接](E3_QUOTA_Q2_PHASE_CLOSURE.md)。
真实双向管理桥接和整链 fixture 驱动尚待完成；Q2 整体、Q3/Q4 和生产 E3 仍未完成。
下文各批历史范围和结果保留，不将组件验证等同于实机验收。
本批准确源码两组回归共 802 项：787 通过、15 环境跳过、零失败，见
[第四批验证与发布映射](E3_QUOTA_Q2_PHASE_CLOSURE_VERIFICATION.md)。

前三批进展：私有隔离 guest 的 Q1 查询/权限/真实 EDQUOT/完整退出及原容量范围已复核，
见 [Q1 限定范围结论](E3_QUOTA_Q1_GUEST_CAPACITY_REVIEW.md)。Q2 首批协议、完整根绑定和有界客户端
已实现：31 项逻辑通过，11 项实际 IPC 因执行器策略未验证，见
[Q2 客户端验证](E3_QUOTA_Q2_CLIENT_VERIFICATION.md)。第二批已补固定准入、持久防重、永久管理预算
和 bootstrap 新版回执消费，107 项定向测试通过，见
[Q2 持久核心验证](E3_QUOTA_Q2_DURABLE_VERIFICATION.md)。第三批已实现保护配置、认证 listener、
多根受监督运行适配、broker 持久绑定及 bootstrap 回执管道，见
[本批实现与剩余工作](E3_QUOTA_Q2_RUNTIME_BINDING.md)。完整 phase-close/harness 装配和真实整链验收
尚未闭合；Q2 整体、Q3/Q4 和生产 E3 仍未完成。下文的逐次历史结果不因新结果被改写。
本批固定源码回归为 780 项：765 通过、15 环境跳过；准确提交、发布映射、CI 状态和下一批接续点见
[第三批验证记录](E3_QUOTA_Q2_RUNTIME_VERIFICATION.md)。

本文件记录实现事实，不替代已批准的三层文档。整体状态为 **受监督启动准备和结果读取已有隔离实现、E1 整体未完成、E3 实机验收 BLOCKED、候选不可部署**；
NAS 已有固定只读查询与响应校验，但实际查询、写入身份和限定网络尚未准入。结果读取已迁入独立受监督进程，真实阻塞 I/O、恢复和取消仍待 E3 实测；本轮未达到 E1–E3 全部出口。
实现边界见 [受监督启动与结果读取](SUPERVISED_BOOTSTRAP.md)和 [NAS 配额准入](NAS_QUOTA_ADMISSION.md)。上一检查点准确源码 `4be98b8`、运行结果、保留的本地安装失败和产物身份见 [启动准备验证报告](E1_BOOTSTRAP_VERIFICATION.md)，不转记为新增实现的验证。
当前结果读取与 NAS 查询合同的准确源码、测试和证据摘要见 [本轮验证报告](E1_RESULT_READER_VERIFICATION.md)。
后续 E3 准备核查确认了两项实现缺口：真实宿主测试仍为占位，且当前 project-quota 查询与固定 upstream 隔离权限模型冲突；不能仅换到 systemd 主机就完成验收。事实、来源和待验证范围见 [E3 实现缺口](E3_IMPLEMENTATION_GAPS.md)，当前可执行的只读盘点及后续场景见 [宿主验收准备](E3_HOST_ACCEPTANCE_RUNBOOK.md)。
只读准备检查点的准确源码 `287f6b9`、18 项定向验证、准确 main CI 及私有证据摘要见 [准备验证报告](E3_PREPARATION_VERIFICATION.md)；云端 BLOCKED 不转记为目标宿主验收。
随后修复了只读探针对合法 nsfs root 的解析误判；准确源码 `88b78b6`、22 项探针验证、准确 main CI 与重测交接见 [nsfs 修复验证](E3_NSFS_REPAIR_VERIFICATION.md)。两份原始宿主 ZIP 已独立核验，固定源码的现场解析修复通过，详见 [GX10 重测证据核验](GX10_E3_NSFS_RETEST_VERIFICATION.md)；整体 readiness 仍为 INCOMPLETE。
最新一次性输入确认包已独立核验：六项专用 E3 输入为 **NOT_PREPARED**，原 13 组命令和 5 个非零退出码均保留，详见 [输入确认核验](GX10_E3_INPUT_CONFIRMATION_VERIFICATION.md)。现场盘点在此结束，不重复无目标探针。
下一步的 [quota/harness 三层变更方案](e3-quota-harness/REQUIREMENTS.md) 已获 Owner 批准，scope `LH-E3-QUOTA-HARNESS-v1` 在 A `415327ebdcc251bb055da9931a7a88990f750b7a` 下仅对隔离开发 CLOSED，见 [开工决定](../governance/E3_QUOTA_HARNESS_OWNER_DECISION.md)。独立 C 为 `5a4ea852091db06549a876e42bbd5f95d5869d3b`。随后完成了 [Q1 原生查询原语](../../tools/admin/local_hand_quota_observer/README.md)：准确 FD 查询、原 rc/errno 和前后身份事实；9 项定向测试、33 个 UBSan 模拟场景通过，真实 quota syscall 执行数为 0。管理服务/准入/监督装配和 Q1 实机验证尚未完成，未进入 Q2/Q3。
历史准确提交与结果见 [首轮验证](E1_E3_VERIFICATION.md)、[后续复查](E1_E3_RECHECK.md)、[第二轮复核](E1_E3_RECHECK_2.md)、[第三轮复核](E1_E3_RECHECK_3.md)、[第四轮复核](E1_E3_RECHECK_4.md)、[第五轮复核](E1_E3_RECHECK_5.md)、[第六轮复核](E1_E3_RECHECK_6.md)、[第七轮复核](E1_E3_RECHECK_7.md)、[第八轮复核](E1_E3_RECHECK_8.md)、[第九轮复核](E1_E3_RECHECK_9.md)、[第十轮复核](E1_E3_RECHECK_10.md)及 [fd55 中断交付恢复](E1_E3_RECOVERY_FD55C07.md)。批准基线 A 为
`79f73faedcd9cde4164b0d1625782dae27db6c2f`，规则 R 为
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，独立开工记录 C 为
`367632126c1930983a06b1854f63789448633148`。三份权威文档保留批准时原文。
Owner 决定及准确范围见 [开工决定](../governance/A2_EXEC_E1_E3_OWNER_DECISION.md)。

quota/harness 变更的首个源码检查点为 `eb7ca61d109f00a699de8591fcf0e0f92717019b`；
准确测试、原始编译失败及私有证据摘要见 [Q1 原语验证报告](E3_QUOTA_Q1_VERIFICATION.md)。
后续 Q1 检查点新增固定对象配置校验与独立退出判定核心：有界不可变 manifest、严格原语事实匹配、
非阻塞管道采集，以及启动/排队/cgroup/采集器均结束后才接受结果的判定。
25 项定向测试通过，包括真实匿名管道和 native emitter 联合验证；OS 观察仍为逻辑 fixture，
真实 quota syscall 为 0。该历史检查点尚未连接真实 manager、持久请求账本、保护配置读取和权限过滤，
因此没有完成管理服务装配或实机准入；未进入 Q2/Q3。准确源码 `ec2fac0`、分类验证和证据摘要见
[Q1 固定对象与监督判定验证](E3_QUOTA_Q1_MONITOR_VERIFICATION.md)，详细接口边界见 [管理侧 README](../../tools/admin/local_hand_quota_observer/README.md)。

当前检查点进一步完成 Q1 单次 systemd 查询装配源码、受保护 worker、参数级 syscall 过滤及永久启动意图。
启动竞态、失败停止、原身份恢复及有界采集已有定向验证；systemd/quota 成功链仍为 LOGIC_ONLY，
未启动真实单元或执行真实 quota。详细边界见 [管理侧 README](../../tools/admin/local_hand_quota_observer/README.md)。
完整 observer 服务和 Q2 账本/通信未完成，Q1 实机仍 BLOCKED。准确源码 `39e7bcb`、106 项定向测试
及仓库内原始日志见 [Q1 运行装配验证](E3_QUOTA_Q1_RUNTIME_VERIFICATION.md)。后续 `d117cbe` 修复 Windows
收集时 Linux 测试默认参数的常量导入；保留首次 CI 失败与 14 项定向重测日志。修复后的准确 main
`4148527` 两平台 CI/独立安装均通过，平台跳过与 E3 未验收边界在报告中分别记录。普通开发不逐次生成 ZIP。

随后补充 Q1 离线配置检查入口 `tools/validate_q1_fixture.py`：两份字节快照及外部摘要、源码和安装绑定，
全部 slot 与固定输入/journal 的路径交叠检查；运行装配同步采用同一检查，修复只检查选中 slot 的缺口。
输出仅为 `CONFIG_CONSISTENT/OFFLINE_ONLY`，无宿主观察、ticket 或资源保留。
准确输入及后续实测步骤见 [Q1 fixture 交接](E3_QUOTA_Q1_FIXTURE_HANDOFF.md)。
准确源码 `c0b817b`、130 项定向验证及仓库内日志见 [离线配置验证记录](E3_QUOTA_Q1_FIXTURE_VERIFICATION.md)。
发布后准确 `fbae913` 的 Linux/Windows CI 均通过；源码分别 1017/222 项通过、1/277 项跳过，
默认 wheel 安装分别 94/10 项检查通过；真实 E3 跳过和管理侧安装未覆盖在报告中保留。
实际输入仍 NOT_PREPARED；Q1 实机与 E3 仍 BLOCKED，未进入 Q2。

随后补充[单次管理实验入口](E3_QUOTA_Q1_EXPERIMENT_HANDOFF.md)：在接触 journal 前核验
控制器的实际 systemd/cgroup/进程限制及匿名管道，再使用原票据进行一次运行或恢复；
输出有限私有诊断，保留原字节及独立错误，输出失败不重投。入口不创建监督器，外层受信启动器
需在 unit 启动后固定自身 InvocationID/cgroup 身份并保留 PID 地进入入口；该装配及真实 fixture
尚未交付。完整 observer/Q2/三单元验收仍待完成，生产封堵保持。
准确源码 `e9b21b3`、194 项定向回归及仓库内原始日志见
[单次管理实验入口验证](E3_QUOTA_Q1_EXPERIMENT_VERIFICATION.md)。
首轮 Windows CI 暴露合成 Linux 报告测试未明确模拟 `O_PATH`；测试修复 `273eb0a`
仅固定测试模型，10 项局部回归通过。准确候选 `4dcf46c` 的 CI 已完整 success：
Linux 1081 passed/1 skipped、安装 94 checks/292 commands；Windows 255 passed/308 skipped、安装 10/10。
首轮失败、修复和最终准确结果均在同一验证记录及入库 CI 摘录中保留。

后续补充[Q1 单元内启动适配与有限采集](E3_QUOTA_Q1_LAUNCH_HANDOFF.md)：
在已存在的受监督控制器单元中取得当前身份，固定管理侧安装字节，create-only/fsync
交付原票据绑定的实验输入，再保留 PID 地 exec 进入已有入口。新增外部采集组件
保留原匿名管道的有限字节、EOF、客户端退出和关闭错误；管理采集可覆盖原查询超时后的
有限收尾，但不延长查询期限或判定业务成功。原始票据恢复不补投，失败不覆盖输入。
这只是单元内启动适配和采集组件；真实 fixture 的监督单元、独立停止入口、有限存储
以及实际 systemd/quota/三单元验证仍未交付。Q1/E3 仍 BLOCKED，未进入 Q2。
源码本地检查点 `c1c37dd31763726eeca3084c0db690836b0d43fa` 的 235 项 Q1 回归通过、
0 跳过，独立源码复核收口。用户明确发布授权后，同一文件树已发布为
`07807d62b49f07d31e9e41d4f2fd25c3cefe8f83`；验证记录为
`8cc2b2b8255502d1407f8b820be86b47cc813559`，准确候选 CI `35956624107` 已 success：
Linux 1122 passed/1 skipped、独立安装 94 checks/292 commands；
Windows 261 passed/343 skipped、独立安装 10 checks/10 commands。
详见[本轮验证记录](E3_QUOTA_Q1_LAUNCH_VERIFICATION.md)。

后续隔离 fixture 调试定位并修正了 systemd 255 显式 `User=0` 留下继承能力的启动冲突。
worker 严格权限检查未放宽，235 项 Q1 开发回归通过、0 跳过。私有候选参数只读检查由用户
截图反馈通过，未据此宣称 quota enforcement 或 Q1/E3 通过；原 UNKNOWN 及预留继续保留。
修正源码已发布为 `45ebc2f`；准确候选 `97e12d8` 的 CI `35975888188` 全部通过，
Linux 1122 passed/1 skipped、安装 94 checks/292 commands；Windows 261 passed/343 skipped、
安装 10 checks/10 commands。准确源码与验证边界见 [默认 root 启动修正](E3_QUOTA_Q1_DEFAULT_ROOT_VERIFICATION.md)。

## 已实现的代码

| 边界 | 实现与可观察行为 |
| --- | --- |
| 协议与准入 | `local_hand_jobs.contract/policy/registry`；六类固定作业、七接口、严格原始 JSON、规范摘要、主体/目标/资源准入、有限预算及固定 Ledger 输入 |
| 持久后端 | `state/resources/broker`；单一 authority 锚、SQLite 意图和事件、资源屏障、稳定业务/核对 ID、精确取消、撤权和重启后原身份观察 |
| 启动根分配 | `bootstrap_roots`；私有有限预建 slot 池、准确目录身份、与执行意图同事务的永久消费；preflight/business 仅在同一操作内共享原分配，其他阶段消费独立 slot，不开放 profile 父目录写权 |
| 进程监督 | `runner/bootstrap/result_reader/ledger_jobs`；新阶段依次使用 bootstrap、helper、result_reader 三个固定 unit，每次交付有独立持久意图和启动围栏；启动根身份、硬配额和计划发布在 bootstrap 内进行，helper 写入前再验根身份。结果文件由只读 reader 读取，observer 只收有界非阻塞管道；生产入口仍固定拒绝启用 |
| Q1 内部 quota ABI | 独立管理侧开发目录中的原生 FD 查询原语，固定观察调用、errno/前后身份和有界 JSON；不接受路径或修改动作，未安装、未提权、未接入 broker，不在默认 wheel/Plugin 中。模拟成功不是宿主准入，完整 observer 仍待实现 |
| Q1 固定对象与结果判定 | `admin/local_hand_quota_observer/admission.py`、`supervision.py`；不可变配置映射、原执行/截止时间绑定、有限非阻塞采集、独立进程退出事实与原语回包分别核对。内部判定核心；实际 adapter 由独立 Q1 runtime 源码连接，未授予作业执行 |
| Q1 单次运行装配 | 保护配置/安装及 worker、固定 systemd query unit、准确能力集和 native 参数级过滤、永久意图 journal、启动竞态/原身份停止与有界采集；真实启动已取得失败现场及候选参数 pre-exec 反馈，原生 quota 尚未成功；恢复丢失原采集归属保持 UNKNOWN；不替代 Q2 服务 |
| Q1 离线输入校验 | 严格快照摘要/源码/安装绑定及全部 slot 路径检查；计费域去重，声明额度不冒充实际预留；CLI 无宿主执行，真实权限/配额/监督仍待实测 |
| Q1 管理实验入口 | 原票据 run/recover 单次连接、执行前实际监督核验、有界私有诊断及失败不重投；Outcome 未携带的 EOF 事实不补造，不提供完整 Q1 出口证明 |
| Q1 单元内启动与外部采集 | 固定安装清单、当前身份绑定、保护输入 create-only 交付、同 PID exec；独立有限管理采集保留原字节/EOF/客户端退出/关闭错误，输出已知停止身份但不执行停止；真实 fixture、外层监督/停止和实机验收尚缺 |
| 证据交付 | `evidence/evidence_client`；真实事件和停止证明、成员摘要、create-only ZIP/manifest/外 seal、fsync 后 DB 登记、有界读取和宿主直接文件续传 |
| MCP | `local_hand_mcp`；官方 SDK Streamable HTTP、成熟 JWT 验签、逐次权限检查、OAuth 发现和挑战；复用同一个 broker |
| 维护 CLI | `local-hand-jobs` 经私有 Unix socket 与 OS peer 映射调用同 broker；没有另一套直接执行路径 |
| Plugin | 独立 `plugins/local-hand-a2` 分发，四个工作流程与稳定 ID 客户端；公开 `mcpServers` 为空，等待 E4 私有配置 |

现有 Task v1 的八动作和 GitHub mailbox 保持原协议。新 job 不通过旧 v1 自动桥接或故障回退。
Connector 继续用于获准的 GitHub 访问，仓库文件中不存在实际客户端连接、凭据或实机运行配置。

## 当前不能宣称完成的门槛

| 项目 | 准确状态 |
| --- | --- |
| E1 受监督执行 | 已有私有 root allocation、三个固定单元、受监督配额／计划发布与结果读取、三次 durable guard 和不重放恢复代码；真实 OS 约束、阻塞 I/O 及完整取消链尚未验收，不据此声明 E1 整体完成 |
| E3 真实独立进程监督 | `SystemdManager.support()` 固定包含 `E3_SUPERVISION_UNVERIFIED`，即使其他主机条件齐备也拒绝生产启动；没有配置布尔值可解除。现有实机用例仍为 SKIP/FAIL 占位，尚缺完整 host fixture/harness；委派、namespace、子孙进程、延迟启动、broker 崩溃、配额和阻塞 I/O 的真实验收未完成 |
| 本地 project quota | 用户专用 guest 已取得 Q1 查询和 PrivateUsers 下真实 EDQUOT/完整退出结果，限定范围复核见页首；旧 UNKNOWN/INCOMPLETE 保留。Q2 已接保护配置、认证通信、原预算与 bootstrap 回执，完整关闭装配及真实整链仍待验收；GX10 生产能力和 E3 支持仍未验收 |
| E3 只读准备 | 独立探针的 nsfs 修复已完成现场重测；原始 mountinfo 未归档，不声称云端重放。随后一次性输入确认的 44 成员 ZIP 已独立核验，六项专用账户/manager/slice/cgroup/隔离/委派输入为 NOT_PREPARED；slots/quota/store 仍 UNVERIFIED。只读库存阶段结束，整体 E3 仍未验收 |
| helper 结果读取 | 新 v3 将文件读取迁入独立只读 reader unit，父端仅处理有界匿名管道；旧布局不补授 reader 预算、不回退直接读盘。重启丢失管道不重读，结果保留 UNKNOWN；原三 unit 退出可独立记录，允许新显式 reconcile，旧 local CLI 停止仍不冒充已证明。真实 E3 尚未验收 |
| 真实 Unix maintenance transport | 宿主限制和各准确候选结果按对应验证报告分别记账；独立 TCP/SDK 测试不替代 Unix socket |
| NAS 运行时 | `nas_quota` 已有固定 CIFS 只读请求、准确响应与身份／时间校验，结果始终 LOGIC_ONLY；实际 collector、写入身份、凭据及限定网络未准入。`ledger.nas.roundtrip` 和真实查询仍明确 UNSUPPORTED，Plugin 不提交该类型。现场事实按 [私有输入工作表](NAS_PRIVATE_INPUT_WORKSHEET.md) 收集，填写不启用查询 |
| E4 | 真实当前客户端 OAuth、私有 MCP 连接及工具结果到可下载文件的宿主桥接未执行。16 MiB 合成证据下载属于 E2 客户端组件验证 |
| E5 / S2 | 未安装到 GX10、未停止或切换旧服务；S2 仍按独立 OPEN 基线管理 |
| E6 | 未执行真实 GX10 → NAS → GX10 A2，不把 Linux 合成文件或逻辑测试当 NAS 证据 |

本实现保留硬约束；没有跳过认证、配额、进程树证明或挂载检查的运行时开关。
本地 quota 查询机制与真实 host harness 须先补齐，再完成启动准备、结果读取和真实 cgroup 验收；NAS 配额适配仍单列未完成，不能靠改一个配置布尔值宣称支持。
私有 root slot 由受信部署侧预先创建、绑定账户与硬配额；broker 只消费已声明身份，不能自动扩池、回收或重新分配已用 slot。
Bootstrap、helper 与 result_reader 共享原阶段绝对截止时间；新 v3 的 CPU 三分固定且不退款，旧 v2 原分额不改。不会因排队、切换子阶段或重启而续额。
不能把线程超时当作进程树退出证明，也不能把新增启动准备隔离解释成所有存储观察已具备有限停止保证。
宿主执行的账户、解释器、安装和准入配置须在服务加载前由受信部署侧保护；包摘要是漂移检测，
不能从已被任意篡改的解释器或正在执行的恶意进程中建立信任。

## 构建与安装身份

产品发布版本为 `0.2.0a1`。基础安装仍无第三方运行依赖，四包同版本分发；
MCP 使用独立可选 extra。已冻结 Linux x86_64 / CPython 3.12 的
[完整 wheel 哈希锁](../../requirements-mcp-linux-x86_64-py312.lock)和
[28 项依赖版本、wheel 摘要与许可记录](MCP_DEPENDENCIES.json)。
其他平台须另行解析、审查并冻结其哈希锁；依赖许可不改变本仓库未添加许可证的决定。

对受信取得的 wheel，基础安装和可选依赖安装分别执行：

```sh
python -m pip install --no-index --no-deps /absolute/path/infra_local_hand-0.2.0a1-py3-none-any.whl
python -m pip install --require-hashes -r requirements-mcp-linux-x86_64-py312.lock
```

以上是独立环境的安装说明，不授予连接或部署权限。基础安装调用 MCP 入口时若缺少 extra，
明确报告缺失。`local-hand-worker`、`local-hand-connect` 的使用仍见 [原使用说明](../USAGE.md)。

准入前可用 `python -m local_hand_jobs.deployment --service broker` 或 `--service mcp`
读取准确 source commit、完整四包 payload digest 和实际服务模块入口。私有 policy 必须固定这些值，
服务启动在创建 authority 锁、线程和监听前重新核验。旧 `core_digest` 保持 v1 含义，
不能替代新完整摘要。生成的 Python 缓存额外与同解释器新编译的源码匹配；缓存不参与稳定源码摘要。
旧 source-staging 仍可服务旧 Worker，不能据此启动新 job 服务。

从干净提交单独生成 Plugin：

```sh
python tools/build_plugin.py --output /absolute/new/output/local-hand-a2-plugin.zip
```

分发包含逐文件摘要、准确来源提交和冻结工具契约；输出 create-only，不能覆盖已有交付物。
Plugin 不隐式安装 Python 包，不创建真实 endpoint，不提供第二套认证或执行器。

## 验证解释

测试覆盖原有行为、严格输入、身份和策略变化、迟到回执、重复 ID、延迟启动、取消与恢复、
未知副作用屏障、事件封存、并发文件、持久化失败、分块撤权和真实文件续传。
真实模块的七接口合成集成只替换 OSManager/固定业务结果，授权、Registry、SQLite、
证据发布和客户端文件校验均使用实现本体。它不能证明真实 Ledger 程序已经受该 OS 监督执行。

CI 保留既有 Windows S1 测试；新 job/Plugin 的当前实现与测试范围为 Linux。
Linux CI 安装冻结 MCP 依赖并构建独立 Plugin。CI 源码/安装测试通过也不自动关闭上述实机门槛。
各验证报告分别绑定准确候选提交、最终测试数量、产物摘要及失败记录，不把旧候选计数沿用给新实现。
