# Q2 历史未来安装承诺对账：需求提案

- Authority：Owner；状态：**PROPOSED / Gate OPEN / BLOCKED ON HISTORICAL INPUTS**。
- Scope：`LH-Q2-INSTALLATION-RESERVATION-RECONCILIATION-v1`。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；采用、可读来源、完整性和变更规则沿用根 `AGENTS.md`。
- 本文、[架构](ARCHITECTURE.md)、[实施方案](IMPLEMENTATION_PLAN.md)仅提出一个受限变更。尚无本范围的准确 A/B/C；不实现对账行为，不请求在缺少历史来源时立即关闭。

## 已确认阻断与授权状态

`LH-Q2-SUPERVISOR-STARTUP-RETRY-v1` 在 A
`47b351b2b943bf1d6f1c71cfeb031157a2eb70cc`、C
`d4a925c883672fadc7d1b10a8dfe58df18b922cd` 下已批准一次新批次；工具实施和
验证不等于发行。该新批次尚未运行，原一次运行授权没有消费，没有开始新 guest
窗口。两次更早的已发行失败及其 INCOMPLETE 结论保留。

现有 S02/S06 保留全部未释放承诺。历史交付源码和已返回记录表明：最初安装未来
承诺为 192 MiB，账户恢复阶段的 192 MiB 是同一旧候选的嵌套承诺，不能再加一次；
随后独立 CPUQuota retry 的新增安装承诺为 64 MiB。本次工具所需安装峰值另为
64 MiB。因此当前规则下的保留量下界为 **192 + 64 + 64 = 320 MiB > 256 MiB**，
尚未加其他暂存、元数据和最终证据费用。历史承诺自身已占满原 256 MiB 上界。
这个下界足以阻止发行；不能假设旧服务退出、目录小或安装完成就自动取消承诺。

上述下界来自可核查的源码和部分回传证据，不代表所有原 reservation raw 已取得。
当前十条历史 reservation 中，七条缺回传原始 bytes，六条尚缺可锚定的单文件
摘要。输入缺口是另一个独立阻断，不能靠额度对账掩盖。

## 受限变更

本提案只请求在全部历史来源及当前终止状态得到联合鉴证后，通过**新的追加式
对账记录**，终止两次已终止历史尝试中尚未消费的未来安装义务。旧 reservation、
计划、期限、安装/source/wheel、日志、失败与原始流均不改写、不删除、不重新
计时；实际分配的全部 bytes/inodes 继续计费。对账不改变历史成功或失败结论。

| 编号 | 要求 | 可验证结果 |
| --- | --- | --- |
| I01 | 历史输入先完整、来源先成立 | 原 raw 或历史已锚定树的完整展开证明与原计划/回执对应；缺 pin 或当前自算 hash 不得成为历史依据 |
| I02 | 只处理准确已终止的两次安装义务 | 同 guest/boot、全部已知历史 FAILED 实例、准确 InvocationID/退出状态、无 job/PID、空树、双 ledger/七根和旧来源共同通过；未知即阻塞 |
| I03 | 仅终止未消费的未来安装部分 | 每项原承诺的来源、用途、实际覆盖、嵌套关系与未来剩余量可核查；恢复的 192 MiB 只映射原同一义务 |
| I04 | 新记录追加，旧证据不变 | create-only 对账记录绑定原摘要、前后账单、权限和现场鉴证；不修改旧 reservation，不清理或退款任何实际存量 |
| I05 | 不改变其他承诺或上限 | 不终止 capture、runtime、journal、ordinary state 承诺，不改 quota；安装总上界仍 256 MiB/原 16384 inode，其余原 ceilings 原样保持 |
| I06 | 服务原唯一未发行新批次 | 对账只绑定准确 startup scope/C 和同一个尚未发行计划；不新增第二次运行，不刷新已开始的窗口，不默认为可以发行 |
| I07 | 对账后仍完整准入 | 旧实际占用、所有剩余承诺、新峰值和最终封存同时符合 byte/inode 及设备容量；不足仍 BLOCKED |

当前 startup A 的 S02/S06 禁止释放旧承诺，本提案会改变该受影响的计费语义，必须
单独形成准确三文档 A、Owner B 和独立 C 后才能实现；既有 C 不能代替本次关闭。
不受影响的已批准工具和验证可保留，现有严格计费路径必须继续拒绝不满足的计划。

## 固定运行边界

运行候选保持 commit `b49d3df3d1e76813faf08e59ab4975e25279c2fc`、tree
`2d957ccf1d9cbdf5e538189c6b68d56f34590a42`，wheel SHA-256
`c077a8f8aa2f0c3147228602746fd459a6d13267df299a84835331ad35ef158b`。
不改候选、能力集合、账户、设备、挂载、project 或配额，不增加依赖、硬件或权限。
既有 startup 批次的一次 300 秒以及 guest/owner/准备/stop、CPU/memory/tasks/输出
限额均保持；现场对账及其证据写入也消费该唯一窗口及现有预算，不能增加准备窗口。
只执行原 `host.inspect`、空 inputs、固定三阶段；不含 Q3、H06–H13、production、
GX10、真实 NAS 或 E4–E6。

## 关闭前尚缺的输入

| 原始材料 | 当前缺口与要求 |
| --- | --- |
| 原 transfer/bootstrap intent | 未取得回传 raw 或单文件 pin；需原留存输入，或可验证的历史锚定树展开 |
| 原 preparation intent | 已知原计划摘要，缺对应 raw；原样 bytes 须匹配，不用重构值替代原输入 |
| 原 preflight | raw/单文件 pin 未完整取得；须展开原已锚定保留树或提供真实原记录 |
| recovery-intent 与 recovery stage | raw/单文件 pin 未完整取得；stage 须回到已固定恢复 source、原计划及原准备回执 |
| 第二 bootstrap intent 与 bootstrap-attestation | 缺 raw 和历史单文件 pin；第二 staging 目前也没有可用历史树 hash，不能只读取现状后自行设锚 |
| 全部历史失败实例身份 | 每个允许保留实例须有可绑定的历史 InvocationID/退出证据；缺项不以当前 failed 状态代替 |

应先取得 Owner 提供的真实留存材料，或把已有可信历史树摘要展开成可验证的完整
条目清单。展开必须复现历史树摘要；当前新 hash、文件名相同、内容看似合理或
Owner 只批准计费原则，都不能追认缺失的历史来源。
在这些阻断解决、准确金额及 inode 归属可审阅前，只保留 PROPOSED，不请求立即
批准执行，不生成 READY 的实机入口。
