# Q2 原终端 namespace 独立参考：需求

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。
- Scope：`LH-Q2-NAMESPACE-REFERENCE-v1`；拟批准阶段仅 **NS1–NS2**。
- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；直接来源 SHA-256
  `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
  readable direct source、Owner-only authority、mandate、无例外及变更规则继承根 `AGENTS.md`。
- 本文、[架构](ARCHITECTURE.md)、[实施计划](IMPLEMENTATION_PLAN.md)构成候选补充 A。
  尚无本范围准确 A commit、Owner B 或独立 CLOSED C；本次只形成文档，不生成源码或执行采集。

## 问题与既有边界

已 CLOSED 的 K reader 与旧生产者替代批次 consumer 只读取固定 boot_id 和本进程
mountinfo。它们能验证普通身份、procfs 类型、held fd 与挂载身份，但不证明原终端来源，
也不证明当前 PID namespace 与该 procfs 所属 PID namespace 相同。既有 K4 回传不缺件，
无需重交同一材料；该来源没有独立原终端参考、namespace fd 或当前活体交换。

本提案增加固定的 standalone 本地 collector。Owner 在未来 NS3 指定的原本机终端
直接启动其固定 coordinator G，G 只 fork 两个单线程直系子进程：参考 R 与观察 O。
G/R/O 使用 held procfs、pidfd、pid/mnt namespace fd 和本地匿名 IPC 相互核验。
O 是本提案的 standalone observer，**不是实际待准入 consumer**；通过也只覆盖
这三个准确活体进程在该次交换的观察，不转给另一个 PID 或未来窗口。

## 候选信任前提与充分性

以下两项是待 Owner 明确接受的新前提，不能由此前 trusted-storage / no-same-UID-storage-tamper
接受记录推出，本文也不是 Owner 决定：

1. **原终端 provenance 前提**：Owner 直接选择既有原 host 的 native 本机终端，
   在固定普通身份下直接启动准确摘要绑定的 G；该启动不经过容器、namespace launcher、
   远端终端、中继或以另一个进程的 FD/回执代替。Owner 将这一准确启动指定为该次
   session 的原终端参考来源。程序不接受“原终端 PID”或输入路径来代替此决定。
2. **endpoint execution integrity 前提**：准确绑定的 interpreter/runtime、collector
   字节和固定启动环境按所审代码执行；在这次 session 内，没有 root、kernel 或同 UID
   runtime/ptrace/FD 注入者替换或修改 G/R/O。该前提只限此次端点执行诚信，既有
   存储前提保持其原范围，不能声称本机制技术排除了这些干预。

在这两项前提、准确内核接口语义及 NS2 资格均成立时，G 自身来源、直接 fork 关系、
两端由 kernel credentials 绑定的消息、G 独立取得的子进程 namespace fd 与两端实际
交付的 held fd 可共同证明：该次 O 与所指定原终端参考 G/R 的 pid/mnt namespace 相同，
且所用 procfs 的 PID 视图与这三个进程各自 PID namespace 对齐。不能证明全局 initial
namespace、physical host 身份、boot 相等、user/time/net namespace、capability 或未来
状态。若不接受 provenance 前提，结果最多为 `LIVE_PROCESS_VIEWS_MATCHED`，不得改记
`OWNER_DESIGNATED_TERMINAL_MATCHED`；若执行诚信前提不能采用，参考独立性仍为 UNKNOWN。

## 阶段和权限

| 阶段 | 本 A 候选范围 | 必要边界 |
| --- | --- | --- |
| NS1 | 独立固定 collector 合同、纯解析/状态模型及源码实现 | 仅独立 B/C 后开始；不接入 consumer 或生成现场 P4 包 |
| NS2 | synthetic 负例和明确 supplied isolated fixture 上的 native qualification | 只限 manifest 绑定的 fixture、普通身份和既有监督；不新建 namespace、账户、manager、mount、cgroup 或系统策略 |
| NS3 | 原 host 终端 local-only 取证 | **不在本拟闭合范围**；须另有准确私有 artifact、固定 runtime/context、资源与原生审计计费、Owner 独立稳定 event/ref 及完整停止/EOF；不消费 P4、无 SSH |
| NS4 | 实际 consumer/P4 用途 | **不在本拟闭合范围**；须准确受影响补充 A/B/C/D，将 O 明确改为实际 consumer，并绑定其同一 live session、原双钟/预算/费用；P4 仍需自己的准确发行 event/ref |

NS2 的 fixture 启动者可以指定 synthetic/native fixture reference，但不得把它标为原
host 终端。NS3 的将来 artifact/event 不是本 A 下的自动执行权。NS4 不能以 NS3 的历史
报告作跨 PID 准入或重采样来刷新旧 preparation / outer deadline。

## 固定来源与要求

| 编号 | 要求 | 验证/拒绝规则 |
| --- | --- | --- |
| NR01 | 没有 caller-selected PID、路径、命令或环境覆盖 | 唯一私有输入为固定 schema 的 fixture/context 与 artifact 摘要；只从 G 的两个 fork 返回值派生子进程数字路径 |
| NR02 | 所有内容读取前 ordinary guard | G/R/O 的 real/effective/saved UID 三元各自全等且非 0、GID 同理，完整 groups 稳定排序且保留重复项后逐项匹配固定 context；各操作前后继续 guard |
| NR03 | 固定 procfs 来源 | G/R/O 各自 `/proc/self/status`、`/proc/self/ns/pid`、`/proc/self/ns/mnt`；另仅 G 可读其两个内部直接 child PID 对应的同三项。没有 boot_id、mountinfo、stat、readlink、祖先进程或其它 proc 内容 |
| NR04 | 精确 magiclink 例外 | 固定 procfs 下 `self` 为唯一进程目录 magiclink 例外；该目录下 `ns/pid`、`ns/mnt` 为唯二 namespace FD magiclink 例外。其它段逐段 no-follow，不跟随任意 link，不以失败 fallback 扩展 |
| NR05 | proc PID 视图对齐 | 单线程进程 status 的 `Threads=1`，唯一 `NStgid` 与 `NSpid` 都为单级正整数；self 值等于该进程 getpid，G 读 child 的值等于原 fork PID。缺项、重复项、多级、格式/关系不符全部 BLOCKED |
| NR06 | held namespace 对象资格 | proc ancestor/process/ns directory先有fd级procfs/mount资格；仅固定两ns leaf允许从procfs magiclink转为nsfs handle，不要求target仍是procfs；对指定nsfd查询NSFS_MAGIC、对象身份和`NS_GET_NSTYPE`。缺ABI/权限、替换、proc链子挂载或未知结果拒绝 |
| NR07 | PID reuse 和活性 | G 设置正常 SIGCHLD/reap 语义，从自己的两个 fork 取得并保持原 pidfd，在交换前/后核验活性；任何 exit 即停止成功判断；最终确认/收尾前不 reap。数字 PID 不能单独证明原进程 |
| NR08 | 独立 FD 对照 | G 从 held procfs 独立打开两 child 的 pid/mnt nsfd；将其与 child 交付的 fd 逐项比对，并与 G 自身参考比对。R/O 对交换得到的实际 fd 与 own held fd 比对；不接受 JSON inode 或 caller FD 自证 |
| NR09 | 固定 IPC 与活体挑战 | 三个匿名 UNIX SOCK_SEQPACKET socketpair，只连接 G↔R、G↔O、R↔O；逐消息核验 kernel SCM_CREDENTIALS 与原 direct-child 身份。两个独立 32-byte getrandom nonce、固定 role/counter/session/pins，拒绝截断、重复、乱序、旧 session、unexpected FD/ancillary 或不能绑定到实际 child 对象的 relay FD |
| NR10 | 不变双钟与资源界 | 任何 proc/身份观察前先采 BOOTTIME、紧邻 MONOTONIC；30s/20s/5s/5s 按原双原点形成绝对 deadline，取较早剩余量，不刷新；每次 syscall/帧前后 guard |
| NR11 | 真实收尾与只观察输出 | G 只向自己持有的 R/O pidfd 发固定 TERM/KILL，直接取得两 child 原 wait status 和两 G-control IPC EOF；R↔O交叉EOF由固定child代码先观察后正常退出，来源单列。fixture supervisor另观察G原退出与stdout/stderr EOF。缺退出/EOF、失联或超期为UNKNOWN，不补写成功 |
| NR12 | scope 隔离 | 无消费 marker、host/evidence 文件创建、guest、SSH、业务 job、产品候选替换或 consumer readiness。没有 sudo/setns/unshare/nsenter/remount/sysctl，也不复活退休的 H07 native spike |

`status` 读取只严格解释上述 namespace/单线程字段；ordinary 身份结论来自固定系统调用，
不把 status 未解释字段或动态 metadata 当成新的身份/adoption 证明。`self` 与 child
process directory 必须在读前/后从同一 held procfs 重新绑定；子挂载或普通替代文件不接受。
本范围不能更改既有 K reader 的两来源和 no-follow 行为，新增例外只在独立 collector 内。
另一个进程交付同一 namespace 对象的 FD，技术上不能区分其最初打开者；此时对象关系
仍相符，按固定代码取得 own FD 的来源诚信属于已明示 endpoint 前提，不声称挑战排除了
任意同对象 FD relay。不同对象的替代则必须由 G 的独立 child FD 对照拒绝。

## 一次 collector session 的固定 ceilings

以下是待实现/资格的准确上限，不是已测值，也不借此保证内核不可中断调用必能停止。
一个正常或失败 session 共用一份额度；无自动重试或新 session 抵扣失败成本。

| 资源 | 固定 ceiling |
| --- | --- |
| 新任务 | G/R/O 合计 3 个单线程进程；只允许 G fork 两次，无 exec/额外 child/thread |
| held/open FD | 每进程 24，三进程同时合计 72，含 stdio、临时叶 fd、pidfd、IPC 及 SCM_RIGHTS duplicate；fixture 的准确 launcher 必须只继承 stdio，G/R/O 按固定表继承/关闭；不接管 unknown FD |
| artifact/context | artifact 全部逻辑 bytes ≤256 KiB；固定 context/manifest ≤16 KiB，计入 256 KiB；无外部 dependency/runtime 安装 |
| status 内容 | 单次实际读取 ≤16 KiB，接受 payload 必须在额度内取得 EOF；最多 12 次，合计 ≤192 KiB；不超额补读 |
| namespace opens | 总计 ≤40 次指定 nsfd 打开/重绑定；同一 held 对象的 metadata/ioctl 查询也只按固定两轮表执行，失败不循环探测 |
| 随机挑战 | R、O 各一次 32-byte getrandom，总计 64 bytes；短读或失败拒绝，不换 nonce 重启 |
| IPC | 总计 ≤16 帧，每帧 payload ≤4 KiB、总 payload ≤64 KiB；SOURCE/首次 peer exchange 每帧最多 2 个 nsfd，其他帧无 FD；每帧恰好一个 credentials |
| 报告/诊断 | G stdout ≤32 KiB、stderr ≤8 KiB，合计 ≤40 KiB；R/O 不向外输出，所有失败也受同界；不截断成成功 |
| 内存/CPU | aggregate RAM ≤128 MiB、CPU ≤5s，包含三端峰值与收尾；必须由明确 fixture 的已有普通监督给出适用 enforcement/账单证据，未知则 native qualification BLOCKED |
| 时间 | 原双钟 total ≤30s；观察/两轮交换 ≤20s；stop ≤5s；退出/EOF/report ≤5s，四段无滚动刷新 |
| 新持久对象/网络 | collector 为 0 bytes / 0 inode 新文件、0 网络连接、0 远端调用；匿名 IPC 的内核资源仍计 RAM/CPU，不当作零成本 |

正常路径的观察/stop/report 最晚截止分别为原 issued+20s/+25s/+30s。提前失败或结束
观察时，stop deadline 取“原 stop 阶段最晚截止”与“该 stop 起点+5s”较早值；report/EOF
同理取原+30s与实际收尾起点+5s较早值。双钟分别计算再取较早剩余量，提前结束只能
缩短后续截止，不能把早期失败变成25秒stop或刷新30秒outer。

fixture 已有 supervisor 及原生审计的增量成本须独立登记，不能由 stdout=0 或“不创建
文件”推导无 journal/audit 成本。NS2 不 provision supervisor；如现有 fixture 不能对
RAM、CPU、原 process stop/EOF 与 deadline 给出准确界，保留 BLOCKED，不用 root 或新配置补齐。
stdio-only 初始继承由准确 fixture launcher 的封闭启动合同和 NS2 资格负责；collector
不新增 `/proc/self/fd` 扫描或无限 FD probe。不能确认该启动合同就 BLOCKED，不声称
collector 技术上已检查所有可能 descriptor。G 收到 SOURCE 的 namespace duplicates
串行比较后立即关闭，只有其独立取得的原 namespace/pidfd 留到活体复查结束。

## 结果与未证项

合成结果只标 `SYNTHETIC_CONTRACT_VERIFIED`。isolated native 完整结果只标
`FIXTURE_LIVE_REFERENCE_MATCHED`；provenance 前提不成立时最多
`LIVE_PROCESS_VIEWS_MATCHED`。将来的 NS3 在其准确前提和批准下可标
`OWNER_DESIGNATED_TERMINAL_MATCHED`，但该枚举在 NS1–NS2 禁止产生。
任一失败保留准确操作/errno/阶段和最后观察；退出、停止或 EOF 缺失为
`UNKNOWN_RETAINED`，其余拒绝为 `BLOCKED_RETAINED`；都不自动重试。

所有结果保持 `field_ready=false`、`allow_run=false`、`guest_executed=false`、
`window_consumed=false`、`consumer_namespace_admitted=false`、`normal_chain_executions=0`。
nsfd 和 pidfd 关闭/进程退出后，报告只是该交换的历史事实；不得延长 namespace reference
有效期。H07、双 parent FS、physical origin、同 boot、user namespace/fsuid/capabilities
与未来 consumer 集成各自仍未证明。
