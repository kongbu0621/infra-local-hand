# H07 第二轮续验：批准登记与纯数据组件

2026-09-30 +08。**V1–V4 已获批准；本次实现仅为纯数据组件，整体仍 PARTIAL。**
原生 helper 实现被执行环境的自动安全检查拒绝，实际生成方和第三轮准入未闭合。
没有第三轮派发；额度仍 2/3，原 Q2 startup 仍 NOT_ISSUED。

## 准确链与不变历史

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，完整规则摘要已再次核对。
- A：`eac5e65449e3a4b7083bc91b9123a253e0cb8320`，三文档及历史OPEN标签原字节保留。
- Owner B：2026-09-30 12:35:14 +08，准确决定见[原文登记](../governance/Q2_H07_R2_CONTINUATION_OWNER_DECISION.md)。
- 独立 C：`eb96b87343bfa8b74994265d03417e52430a6efd`，只修改AGENTS并新增Owner记录；独立复核无阻断。
- 此后才编写本次纯数据组件。C不包含新实现，当前实现提交以C为祖先。

本次历史接受只改变准确第二轮事件是否单独阻断最后一轮；它不改变原件状态、不免除修复和准入。
首轮UNKNOWN/cleanup=false，第二轮UNKNOWN/本轮登记清理true/整份收件错误REJECTED分别保留。
两轮验证索引和九份准确权威文档不改；原实验fixture、native helper、workflow及旧continuation执行入口未改。

## 执行环境阻断与本次缩小的交付

开始原生helper实现的子任务被平台自动检查拒绝，原提示为“flagged for possible cybersecurity risk”（可能涉及网络安全风险），
未提供具体命中项。该子任务未交付修改；没有通过改述、转交其他代理或改用另一执行通道重试。
已暂停实际fixture/native实现与派发，只继续可独立完成的无主机副作用数据校验。
这不是实验运行失败，也不消费H07轮次；Owner批准继续有效，但不等于平台已允许被拒绝操作。

| 部分 | 本次实际交付 | 未完成的连接 |
| --- | --- | --- |
| V1 历史数据 | 显式continuation v2，绑定原两套A/C、新A/C、准确两轮脱敏索引、原件摘要、boot比较摘要、固定round3/attempt1 | 真正producer的Git祖先/准确工作树/当前环境/全局run盘点准入未实现 |
| V2 对象生命周期 | 仅静态接口审查 | 固定七代创建/退休、原helper捕获与FD/对象实际证据均未实现 |
| V3 收件数据 | 显式新版离线收件组件和合成输入负例；旧版本保持独立 | 新native/helper/fixture不产生新版报告，真实生成→收件链路不可达 |
| V4 最后一轮 | 保持NOT_DISPATCHED并留证 | 不能由本次纯数据测试或普通CI代替完整准入 |

新continuation模块没有dispatch/运行准入入口，只检查调用者提供的数据并可只读两个固定索引。
通过仅证明给定输入与冻结事实的语义一致，不能证明Git祖先、全局不存在别的run、真实新VM、
当前内核能力或执行权限。新版收件的合成输入不作为现场报告发布，也不构成真实fixture资格。
新版派生结果显式标注`evidence_basis=INPUT_CONSISTENCY_ONLY`。单一`primary_failure`字段与
独立有界`validation_errors`可以检查、输入可以保持不变，但纯收件器不能证明生产端曾经
保留首个失败且没有覆盖；该生成方行为仍待实现与验证。

## 兼容、验证和后续

旧原件由原schema分支处理；不把原报告迁移到v3，不向旧native1校验器偷加新事件，也不放宽旧第三轮准入。
合成数据测试明确标注，没有执行真实账户操作、cgroup操作、helper probe/case或主机配置。
PRO6000/GX10/guest未被调用。

本次最终H07目录回归为 **438 passed**，命令为`python -B -m pytest -q -p no:cacheprovider tests/e3_host/spikes/q2_cgroup_fence`，临时产物置于仓库外。
其中新增continuation v2有47项、新增receipt v3有73项；旧范围318项全部保持通过。
完整正例使用明确标注的人工合成字典，经JSON编码、原bounded loader、显式schema3分派，
真实调用六病例/probe、世代、账户和continuation判据，没有mock决定性校验函数。
负例覆盖历史字节与批准/额度、早退身份三态、首次失败与后续校验错误分列、
并发身份别名及跨代inode重用、创建/退休/账户清理双钟顺序、共享阶段账单、
原helper退出/双EOF/FD关闭、诊断事件归属、版本及输出上限。

独立复核分别检查历史组件、纯数据收件与状态/批准记录；发现的输入健壮性、
创建与退休因果关系、阶段耗时、清理事件重复引用、拒绝诊断原身份及账户清理先后问题已修复。
独立的520个字段类型变异未导致原生数据或整份报告入口崩溃。`git diff --check`通过。
再次读取第二轮原始报告，SHA-256仍为`99d6def38ae46a417a1cfc25b0e6588028813bc0d3b27cee60b083929ad99a54`，
仍由schema2分支派生`REJECTED`、错误`C1: launcher/account binding missing`；
原报告的`UNKNOWN_RETAINED`未改。九份权威文档、两轮索引及固定R完整性均再次核对一致。

发布前GitHub全部76项运行盘点仍只有两轮H07实验，均attempt1，没有第三轮。
本实现提交尚未在本记录中取得准确D普通CI结果；随后自动普通CI即使通过，也只补充
此纯数据提交的回归证据，不建立实际fixture或最后一轮资格。当前不是V1–V4完成声明。

此前独立测试修复`824f4be40fc02a68fe64df4934966471e146b222`的普通CI
[36666922354](https://github.com/kongbu0621/infra-local-hand/actions/runs/36666922354)
已经3/3 SUCCESS；它是旧范围修复证据，不能转记成本次新增组件或完整生命周期通过。

后续须在执行环境允许相关工作后，完成准确A内原生与fixture实现、完整非stub收件链、独立验证、
准确D普通CI以及全部实际准入。不得为绕过本次平台阻断改用PRO6000/GX10或其他执行通道。
现有Owner决定不需重复请求；若实际方案发生实质改变，仍按原R处理受影响范围。
