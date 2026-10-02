# Q2 实机条件：本轮修复后的准确缺口

2026-10-02 +08:00。接续[离线修复复核](Q2_OFFLINE_EXECUTION_CONTRACT_REPAIR_REVIEW.md)。
本记录完成当前路线的只读资格审查与源码/验证映射，不是新三文档 A、Owner B、
CLOSED C、现场发行或现场运行。没有读取 host/guest 新事实、修改系统配置或创建消费对象。

## 已提交的修复与验证

| 项目 | 准确身份 |
| --- | --- |
| 本轮源码 D | `661e96772c64433d1cd0eebf122e165781d8c11c` |
| D tree | `2e977e9887f9e6e1a97b86082d1664772c0f7e3b` |
| D 直接父提交 | `50c5590995fc75ca68e2970730b9384a5b816302` |
| 原 R / A / C | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` / `68424df2ddbf812b9479ffa7a64dcaa59a2a9f76` / `179652cb9487163d83c004d358e4d4b49409694c` |
| 验证 | Python 3.12.14，3713 PASS / 89 SKIP / 0 FAIL |

D 是原 C 的后继，保留原 closure 和实现的独立历史。13 个变更源码的 Git blob
大小/SHA-256 均与[验证快照](evidence/q2-offline-contract-repair-20261002/validation.json)
匹配；三份批准文档仍与 A 字节相同。快照中的 `new_implementation_commit=null`
和 `working_tree_uncommitted=true` 描述验证创建时点，此表补充其提交映射，不改写快照。
机器原件、私有 helper、连接/凭据和 `.codex` 均未进入 D。

## 三项门槛的具体缺口

| 门槛 | 已有能力 | 尚缺的实现或证据 | 完成判据 |
| --- | --- | --- | --- |
| H07 | 原 stage 身份、deadline、stop ACK、Job 终态、空 parent、原 client exit 和双 EOF；HELLO/BIND 的保守算术 | 首次远端前已生效的监督；全运行期 host/guest rate/pause 边界；丢回复/排队/迟激活的服务端禁入；全域独立停止与端点退出 | 所有原域既已终止，原代际将来也不能迟激活，原绝对窗口和完整费用均成立 |
| 两个 parent 的文件系统 | 普通 writer 的真实隔离 IO 测试、held fd/name 绑定、首次 M/G 观察及合成峰值账本 | 两个固定 parent 的当前适用 FS 来源、全过程分配/属性/metadata/sync 峰值、持久性及历史/原生审计覆盖 | mkdir 前完整证据满足准确 profile、逐设备 available 和唯一 capture ceiling；未知项保留未知 |
| namespace 对齐 | 固定 boot/mountinfo 的 procfs magic、挂载身份和 fd/name 资格 | proc 所属 PID namespace 与实际进程关系，以及同一时段原宿主终端的独立可信对照 | 固定来源、普通身份和原窗口内的 namespace 关系证据；仅 self 观察不能自证原宿主 |

### H07：当前 system-manager 域图

当前协议明确为三 phase（preflight/business/evidence）各三 stage
（bootstrap/helper/result_reader），见[协议](../../tools/local_hand_jobs/system_manager_protocol.py)。
不能把旧模型的 owner→supervisor、supervisor→target 两条 modeled edge 当作完整域图。

| 域/边 | 当前源码能核验什么 | 准确剩余项 |
| --- | --- | --- |
| host 入口→首个 SSH/session/shell/权限调用/loader | 原双钟与有界合同；没有实际 prearm 资格 | 保护必须在首项远端工作前生效；不能由首次未受保护探测追溯建立 |
| host→outer / collector | 旧 H07 模型显式列为 unmodeled edges | 分别绑定原 request、准确实例与停止域；collector 必须在同一窗口和同一通道内 |
| owner→supervisor→target | 既有模型覆盖两条边，保留原身份 | 模型与实际实例/独立停止端点/退出事实的映射未齐 |
| target→各 phase query/listener/admission | 旧模型显式列九条缺失边 | 每项 issued request、原 Job/Invocation、父域、截止、独立 stop/EOF 与费用 |
| 各 phase × bootstrap/helper/result_reader | 当前 lifecycle 核验原 stage 终态、空 parent、stop、client exit 和双 EOF | 该 stage 的 `future_start_blocked` 不能扩大为所有未决请求已禁入 |
| gateway→manager，回执丢失或仍排队 | intent 与 delivery-consumed 防止本地重发；失联保留 IO_UNCERTAIN | manager 已受理请求的有界终结/服务端迟激活禁入证明 |
| stop/seal/最终观察端点 | 原管道与实例可核验后才 seal；close 只关 fd | seal 后实际自退、独立外部观察与原双 EOF，不能由端点自封退出 |

源码依据：[旧域模型](../../tests/e3_host/q2_host_window_h07.py)、
[stage lifecycle](../../tools/local_hand_jobs/quota_lifecycle.py)、
[gateway](../../tools/admin/local_hand_system_manager/server.py)及
[失联处理](../../tools/local_hand_jobs/system_manager.py)。这些是静态源码结论，
没有将其写成原机部署或当前实机状态。

下一项既有 CLOSED 范围内工作是把上述域图逐边绑定准确来源、request/intent、
manager Job/Invocation、绝对截止、stop、exit/EOF、排队终态和预算。
负例至少包括丢回复后迟激活、stop 后仍排队、controller 退出但 sibling 存活、
seal 后端点未退出。缺项始终 UNPROVEN，现有观察和原代际禁入分别成立。

新增首次远端前监督设施、timer/fence、服务端控制点、权限/配置/持久对象或
时钟权威来源须先形成准确受影响补充 A/B/C；不预选未经证明的接口。
[native spike 的退休决定](SYSTEMD_CANCELLATION_REPAIR.md)仍有效，
不继续 helper/generation fixture，也不派发第三轮。完整验收保持
[当前 A 的全运行期约束](q2-old-producer-admission-retry/REQUIREMENTS.md)。

### 文件系统：profile、来源和账单同时闭合

当前 A 明确要求消费与 evidence 两个 parent 都满足 EXTENTS-only、size/allocated
各 4 KiB、block/cluster 4 KiB、受保护 block-device/superblock 与 feature 拒绝规则，
见[准确 requirements](q2-old-producer-admission-retry/REQUIREMENTS.md)。
旧回传 indexed/12 KiB 只是该历史观察时点的事实，不证明两个新固定 parent 当前几何，
也不能被改写为符合窄 profile。[历史来源工单](Q2_FS_BILLING_SOURCE_CONTRACT.md)
所述旧 capture 额度不能移植到本批次；本批次仍是 20 MiB / 384 inode，
其中 record 子预留为 64 KiB / 4 inode。

需要逐 parent 补齐以下来源关系：

1. 同一 boot/普通身份、祖先保护、device/inode、mount/source/rdev、superblock 摘要、
   适用内核构建及 ext4 features。
2. mkdir/create/write/file/dir/parent fsync 及部分失败的峰值；parent 正增长、
   extent/allocator、创建属性和隐式 inode，并发假设与费用去重。共享 parent 需联合上界。
3. 原 B、M、首次 G、历史 actual/future、诊断留存及原生 SSH/sudo/systemd/journal
   的事件数、分配取整、轮转与失败收尾上界；不能跨时点拼成实时完整清单或填零。
4. 准确 fsync 链、错误传播和底层存储适用事实，在已有可信存储前提内论证持久性。
   摘要/端点净增/CI 成功不能补成全过程或掉电证明。

[普通 writer 测试](Q2_ORDINARY_WRITER_IMPLEMENTATION_REVIEW.md)替代了 readiness/boot/FS
先决条件；[首次分配组件](Q2_PARENT_ALLOCATION_IMPLEMENTATION_REVIEW.md)只绑定局部 M/G。
两者不提供上述完整资格。已保留的十二历史树、十五旧文件锚及相关 reservation 不需
再次向 Owner 索取；后续离线工作先复用[准确来源索引](Q2_RECONCILIATION_IMPLEMENTATION_REVIEW.md)。

旧 H 范围曾允许更宽 profile 的离线研究；本次准确 A 明确固定窄 profile，扩大其
profile/source/permission 要回到 R。接受 INDEX/多块、增加来源或权威用途、改变 parent
定位或创建/chmod/chown parent、试写和新增设施都不能当作现有 A 自动允许的现场修复。
先证明具体候选机制，再形成最小受影响三文档；不改 flags、不搬目录、不扩额度。

### namespace：只读候选先固定来源与采用边界

[K reader](../../tests/e3_host/q2_host_kernel_facts.py)只允许固定 boot 与自身 mountinfo。
[K4 完整回执](Q2_KERNEL_FACT_READ_FULL_RETURN_REVIEW.md)已经核对，不需重复收集。
[准确 K 架构](q2-kernel-fact-read/ARCHITECTURE.md)明确将 proc/PID 与原终端对应保留为
环境假设，并禁止因此增加其它 proc 读取。

可以先在文档中研究 qualified proc 下的固定 self status、PID/mount namespace fd，
并与独立可信、同一时段的原终端参考绑定。Linux 的 NStgid/NSpid 反映从挂载 proc 的
PID namespace 向内的身份序列；namespace 对象可用类型查询区分。这些接口含义见
[proc_pid_status(5)](https://man7.org/linux/man-pages/man5/proc_pid_status.5.html)和
[ioctl_nsfs(2)](https://man7.org/linux/man-pages/man2/ioctl_nsfs.2.html)。据此作出的候选
推论是：self 观察可研究当前 proc/process 的关系，但仍缺独立原终端来源，不能自证原宿主。

候选必须先固定真实来源和参考身份/有效期、PID 重用防护、proc magic-link 与 nsfs
例外、held fd/name 验证、字节/fd/时间/审计预算及变化/失联负例。
新增 collector/source adoption 要先有补充准确 A → Owner B → 独立 C，再实施 D。
权限不足、参考缺失或关系未知保持 BLOCKED；无需 sudo、setns、remount 或 sysctl。
本文只研究候选，不新增 collector 或运行该读取。

## 后续顺序与保留状态

先完成已有材料的 H07 全域来源映射和 FS1–FS6/费用工单；再为已经确定的 material
变化形成可审批的最小补充三文档，不请求“任选机制”的空白授权。
namespace 的最小只读候选必须包含可信原终端参考，不能只加 self 检查就写 PASS。

全部实际硬门闭合且准确包完成后，仍需独立 stable P4 event 绑定 scope/batch/A/C/D、
包 basename/bytes/SHA-256、evidence limits、仅一次和失败不重试。
`field_ready=false`、`allow_run=false`、`guest_executed=false`、真实正常链计数 0
保持；代码提交、推送或 CI 都不能发行这项运行权。本记录不声明 Local Hand 已可用。
