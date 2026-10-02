# Q2 旧生产者准入解析失败后的单次替代批次：需求

- Authority：Owner；状态：**PROPOSED / Gate OPEN**。
- Scope：`LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1`，实施阶段 P1–P4。
- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；直接来源 SHA-256
  `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`；
  采用、完整性、Owner-only authority 和变更规则继承根 `AGENTS.md`。
- 本文、[架构](ARCHITECTURE.md)和[实施计划](IMPLEMENTATION_PLAN.md)构成待批准的准确文档基线 A。没有本范围的 Owner B 与独立 CLOSED C，不生成可现场执行的替代包，也不接触 guest。

## 已发生事实与问题边界

已获准的 `LH-Q2-SYSTEM-MANAGER-REPAIR-v1` M4 包以批次 `20261001e`
调用过原 guest。其独占 `consumed.json` 和 `staged.json` 已持久化，候选
`1a900e4a38e9567655f21cbf3c3f17941de1a8d5` 已并排安装到该批次 CODE；
外层 unit 已产生一次失败 invocation。该调用在 `old_producer_admission`
停止，`normal_chain_executions=0`，没有进入资源 provision 或正常链。

首错是私有交付帮助程序把 `systemctl show` 省略的空数组属性当作必然存在，
读取 `ExecStartPre` 时触发 `KeyError`。当时取得的 `systemctl show` 输出包含
加载/活动状态、PID、cgroup、fragment、`ExecStart` 等配置字段；流程尚未进入
实际 argv、可执行文件和进程身份读取，也没有取得 Environment。systemd 可在空值时
省略的 `ExecStartPre`、`ExecStartPost`、`ExecStop`、`ExecStopPost` 均未形成映射键。
该事实只定位交付解析器，不证明旧生产者准入、资源准备或 Q2 通过。

`20261001e` 已消费且状态为 `FAILED_RETAINED`。本提案不是它的续跑或自动重试；
旧 BASE、CODE、unit、InvocationID、截止时间、日志、回执和全部更早 UNKNOWN、
lease、quota 与历史结论均不可重写、清理或复用。原 CLOSED scope 只批准一次
现场包执行，因此第二次现场批次必须由本独立范围明确批准。

## 范围与可验证要求

| 编号 | 要求 | 可验证结果 |
| --- | --- | --- |
| R01 | 精确绑定旧失败 | 固定旧包、消费/暂存、代码安装、外层 invocation、原 boot、完整退出/双流和首错摘要；新包只接受私有 manifest 预先固定的该 boot，变化时在消费前停止，不动态采纳；任一字节或身份不符即停止 |
| R02 | 仅修四个空数组属性 | 按既有 `key=value` 映射规则解析后，只为 `ExecStartPre`、`ExecStartPost`、`ExecStop`、`ExecStopPost` 补空字符串；不得合成其它字段或改变解析规则 |
| R03 | 原准入保持 fail-closed | 各既有 caller 对 Id 完整性/重复 Id、LoadState/ActiveState/SubState、PID/cgroup、InvocationID/Job/Restart/NRestarts、activation links、ExecStart、fragment/drop-ins、argv、期限、实际进程身份和旧路径的原检查全部保留；不得把它们改成统一默认值；任一 hook 非空仍拒绝 |
| R04 | 全量保留旧现场 | `20261001e` BASE/CODE/failed unit/日志/回执保持；旧批次、UNKNOWN、lease、数据库、配额及成本不退款、不清理、不追认成功 |
| R05 | 独立 create-only 新批次 | 使用 `20261002a` 新 BASE、CODE、outer/supervisor/target/ordinary slice、新状态/证据目录和 project `12061..12067`；任何对象已存在即停止 |
| R06 | 候选与运行合同不变 | 产品 commit/tree/source.bundle/wheel/payload 保持 `1a900e4` 已验证值；仅复用原 SSH、sudo 及 `/opt/local-hand-5ca9753-20260930a` 的基础 runtime/Python/native 工具。`20261001e` CODE/receipt 只读绑定，不得作为新 CODE 或安装结果复用；不改产品源码或系统策略 |
| R07 | 累计容量完整计费 | 当前 statvfs free 已扣除旧实际分配；仍须在该 free 上另加全部未释放的完整承诺。实际分配只记录其已反映在 free 中，不再显式作为第三项加数；不得由此扣减承诺或从 `20261001e`/更早失败获得退款 |
| R08 | 一个新窗口、一次正常链 | host launcher 在任何 P4 本机现场读取前先采 BOOTTIME、紧邻采 MONOTONIC（或使用等价保守 bracket），并从该双原点建立 outer 300 秒与 preparation 150 秒截止；本地预检、host intent、唯一 SSH、传输及消费前 boot/旧对象检查均计入 preparation，owner 最多 120 秒且不得超过当时 outer 剩余量。mkdir 前失败结束本次调用且不自动重试；固定目录一旦出现即持久消费授权，之后任何失败都不得重放。正常链最多一次，失败停止、保留现场、不换名续跑、不自动重试 |
| R09 | 如实验收 | 分开报告解析准入、provision、正常链、退出/EOF、停止和有限 systemd/journal 补采；缺证据保持 BLOCKED/UNKNOWN，不把离线测试当实机通过 |
| R10 | 保持治理先后 | Owner B 后先以独立 bookkeeping-only C 关闭本范围，再从 C 的后继提交形成本范围实现 D；C 不混入实现，旧产品提交 `1a900e4` 不冒充本范围 D |
| R11 | 现场执行另行发行 | B 只批准准确 A、P1–P3 与 P4 合同/资格，不发行现场运行；准确包完成后，Owner 必须用独立稳定 P4 event/ref 逐项绑定 scope、batch、A、C、D、ZIP basename/bytes/SHA-256、固定 evidence basename、`evidence_max_frame_bytes`、`evidence_max_archive_logical_bytes`、`evidence_max_archive_allocated_bytes`、`evidence_archive_inode_count=1`、仅一次及失败不重试 |
| R12 | 固定内核视图仅窄采用 | 本范围 D 须把已 CLOSED K 链的专用 reader 明确集成到新 host consumer，且只在双钟后、任何 proc 内容读取前已按固定 context 核验非 root 且 real/effective/saved UID/GID 各自全等、完整 groups 匹配的普通身份下，读取 `/proc/sys/kernel/random/boot_id` 和本进程 `/proc/<自身 PID>/mountinfo`；读取过程中继续身份 guard。不得把旧 K 授权自动扩张为通用 `/proc`、任意 PID/路径、PermissionError fallback、提权或 consumer 现场权 |

## 固定 host 尝试记录与跨机期限

现场 P4 复用已 CLOSED 的 `LH-Q2-HOST-WINDOW-CONSUMPTION-v1` 的原子消费语义：
准确 A `8402f0cc82d8a0ac0b9a56716bf276f41cafea37`、C
`271c07cd16140aa5942dcf3fad468003c58b6b0e`、组件 D
`f1814b27adbc1bcdb6d6ac14875e9d2ec6a795ff` 及只读预检后继
`0a456a909821fd1fc6a4fdec43b9e16bc88679f2`。普通身份 v2 writer 另固定为组件 D
`c2373313eb78aa55373cb0318d08d5f60424dafd` 及其[实现复核](../Q2_ORDINARY_WRITER_IMPLEMENTATION_REVIEW.md)，
首次父目录增量计费组件固定为 D `530a2a45bc6e96270771ccf266793e471d8408ee` 及其
[实现复核](../Q2_PARENT_ALLOCATION_IMPLEMENTATION_REVIEW.md)。这些提交只提供各自已验证的
原子记录、普通身份与计费机制，不复用消费路径、批次、marker 或运行授权，也不证明
field readiness、H07 或本范围现场资格。

固定内核视图 reader 的准确前驱另为 A
`887b640b394f9983f37dfe97c58ba35aaa099359`、C
`f7f8b503470725ca1ba18d1cb8d8b39e09a15ea8`、D
`e15c633adbdfbf1e29cb12b2410975fe4911458d` 及其
[实现复核](../Q2_KERNEL_FACT_READ_IMPLEMENTATION_REVIEW.md)。旧 K 范围只把该 reader 接到
local preflight，并没有授权 consumer 使用；本准确 A 请求的仅是把同一受限机制集成到本范围
新 consumer 的上述两个固定视图。它不采用旧 K 的现场批次、包、marker 或运行授权，也不
证明原 host 的 proc/PID namespace 对齐、H07、文件系统资格或本范围现场 readiness。

host 父路径不能由同一 manifest 自报。P2 必须生成固定成员 `host-locator.json`，使用
专用严格 schema `local-hand-q2-old-producer-admission-retry-host-locator/v1`，只包含规范
绝对 parent 及其预期 type、UID/GID、精确 mode、device/inode；严格 UTF-8/JSON、拒绝重复
key/多余字段/尾随数据，不能执行。另一个固定私有成员 `host-context.json` 以专用严格
schema 固定 locator 摘要、预期 host boot、完整普通操作者身份、SSH/guest 身份摘要，以及
规范绝对 evidence parent 与其预期 type、UID/GID、精确 mode、device/inode；package
manifest 还固定唯一 evidence basename、`evidence_max_frame_bytes`、
`evidence_max_archive_logical_bytes`、`evidence_max_archive_allocated_bytes` 和
`evidence_archive_inode_count=1`，并逐项绑定两个成员的 member name、bytes、SHA-256 和解析版本，最终
私有 ZIP 再绑定 manifest。执行器只能读取这些固定值，不能接受
CLI、环境变量、`TASK.txt`、输出目录或同一 manifest 中的自由路径覆盖。公开仓库不披露
真实路径或身份。

P4 在双钟采样后先只读解析并核验 package-bound locator/context；在任何 K reader 内容读取前，
先取得 `getresuid/getresgid/getgroups`，核验 UID/GID 三元各自全等且非 0、完整 groups 经稳定
排序并保留重复项后与固定 context 相同。只有该普通身份 guard 通过，才依次读取固定 boot 与
本进程 mountinfo；每项读取期间及读后继续重复同一身份 guard，任一漂移立即停止。随后才核验
现存消费 parent、evidence parent 及两者全部祖先，并分别保持 held no-follow directory fd。
两个 parent 都必须已经存在且与固定
type/UID/GID/mode/device/inode 逐项相同，owner/GID 与固定普通操作者相同，并满足
`mode & 06022 == 0`；0755 可在被准确固定且其它保护条件满足时接受，0700 不是既有
parent 的硬编码前提。两条祖先链须无 symlink、未知 ACL 或保护链漂移，不允许现场新建、
chown 或 chmod parent。

任何 mkdir 前，消费 parent 与 evidence parent 都必须逐项复现 CLOSED ordinary writer 的
写前文件系统资格谓词；boot 与受限 mountinfo 内容必须由 R12 的专用 reader 读取，不能走
通用 `O_NOATIME` 普通文件 reader。从该 mountinfo 绑定真实 rw ext4 mount 与实际 block-device source，
核对设备 rdev、root-owned 单链接且受保护的 block device、准确 superblock 摘要、4 KiB
block/cluster、journal/filetype 要求及 bigalloc、EA_INODE、dir_index、inline-data、encrypt、
casefold 等不支持特性的拒绝；parent 只允许既有 EXTENTS flag，size 与 allocated blocks 均为
4 KiB；`fstatvfs` 的 block/fragment 为 4 KiB。消费 parent 的 available bytes/inodes 至少覆盖
64 KiB/4 inode；evidence parent 至少覆盖 manifest 固定的 archive 最大实际分配、1 inode以及
经独立验证的 parent-growth/部分写入/sync 峰值。两者位于同一实际设备时必须聚合后只计一次，
位于不同设备时分别准入。任一读取、来源、几何、容量或持久性未知都在消费目录 mkdir 前
BLOCKED，不试写、不切换 parent、不采用调用者 fallback。组件 `530a2a45` 只绑定首次端点的
非负净增长 G，不证明中途峰值、allocator/属性 inode、sync、持久性或 parent 原有基数；当前
固定输入也未闭合这两条落盘路径的现场事实，因此必须保持 `field_ready=false`。若本范围 D
不能给出准确、独立验证的峰值/持久资格，或需扩展 profile、来源或权限，须回到 R 形成新的
受影响 A，不能把组件隔离测试冒充现场证明。

其下唯一允许的新目录名由 UTF-8 无换行字符串
`LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1:20261002a` 的 SHA-256 域分离派生，固定为
`q2-old-producer-admission-retry-cf8319dc8c8bed098a6917c5777d60b00ac0efcb5fecd813d14fec4e64af6bf3`，
模式 0700；唯一文件固定为 `host-intent.json`，与目录同 UID/GID、单链接普通文件、
最终模式 0400。该定位不含尚未知的 A/C/D/ZIP，避免自引用；这些身份由 intent 内容
绑定。固定目录的排他创建就是本次现场授权的持久消费边界；空目录、部分文件、同值
完整文件、symlink、类型/owner/mode/nlink/ACL/设备不符均为 replay barrier，停止且
不接触 guest，不删除、接管、覆盖、改名或重试。完整既存记录只能只读核验并返回
`allow_run=false`，不能接管或再次派发。mkdir 前本地预检失败为
`LOCAL_BLOCKED_UNCONSUMED`：没有 guest、没有新持久对象，本次调用立即结束且不自动重试；
由于没有持久消费证明，未来任何再次调用仍必须取得针对准确包的另行单次现场确认，不能
从本次确认推导。

host launcher 在任何 P4 本机现场读取前先采样本机 `CLOCK_BOOTTIME`，再紧邻采样
`CLOCK_MONOTONIC`（或使用能覆盖两次读取间 suspend 的等价保守 bracket），从该双原点形成 outer `issued + 300s` 与 preparation
`issued + 150s` 两组双钟硬截止。本地预检和目录创建沿用同一对原点，不能重采样；
preparation 完成前每个 guard 同时取适用预算内两钟较早剩余量。预检通过后，固定写入
顺序为：沿 held no-follow 父 fd 排他 `mkdirat` 创建同 UID/GID 的 0700 目录；目录出现
即消费；fsync 新目录和必要父目录；以
`O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW|O_NOATIME|O_CLOEXEC` 创建文件，随后在
held file fd 上 `fchmod(0400)`；规范 JSON 完整写入，短写即失败；fsync 文件、目录和必要
父目录；最后从 held file fd 以
O_NOATIME 复读，核验准确 bytes/SHA、owner/gid/mode/nlink、设备/inode、唯一成员和分配。
任一步失败保留空或部分对象，不能删除、改名、接管或重试。

intent 使用本范围专用 schema
`local-hand-q2-old-producer-admission-retry-host-intent/v1` 和专用 run permission
`old_producer_admission_retry_20261002a_once`；旧 v1/v2 decoder 必须拒绝它，新 decoder
也必须拒绝旧记录。intent 严格绑定 scope/batch、R/A/Owner B stable event/ref/C/本范围 D、
独立 Owner P4 stable event/ref、旧产品
commit、最终 ZIP basename/bytes/SHA-256、固定 evidence basename 与上述四个 `evidence_*`
上限/计数字段、helper/bootstrap/固定 SSH argv 摘要、locator 与私有 context
摘要、evidence parent 身份、host/SSH 目标与
预期 guest 身份摘要、host boot、完整普通操作者
real/effective/saved UID 三元全部相等且非 0、real/effective/saved GID 三元全部相等且非 0，
以及稳定排序并保留重复项的全部 supplementary groups；再绑定 MONOTONIC/BOOTTIME
issued 值、outer/preparation 四个 deadline、所有预算、`window_consumed=true`、
`owner_issued=false` 和协议版本。intent 不包含自身 SHA；完整字节固定后才在外部计算
SHA-256，并由握手、guest marker 与最终 seal 引用。

host launcher/issuer 必须在创建前、创建过程中及复读后重复取得
`getresuid/getresgid/getgroups`：UID 三元和 GID 三元各自全等且非 0，完整 groups 列表经
稳定排序并保留重复项后逐次相同；parent/目录/文件的 UID/GID 也须逐项相等。root、混合
real/effective/saved 身份、任何观测到的变化、caller 身份 override 或 chown 均拒绝；重复
采样不声称排除两次采样间的 change-and-revert，该风险属于下述诚信前提。包含完整 groups
后的规范 intent 必须在 mkdir 前算出；当前窄 profile 下文件逻辑长度不超过 12 KiB，连同
已核验为 4 KiB 的新目录后总逻辑量不超过 16 KiB，超限即
`LOCAL_BLOCKED_UNCONSUMED`，不得截断。fsuid/fsgid、capabilities 与 user namespace 不在
本 host intent 身份结论内，也不是本 A 新增的准入硬门；不得声称已证明，若以后要求它们
成为硬门，须固定新的读取机制/来源并回到 R。

联合准入前主动创建的 host 白名单仅此一个目录和一个文件。intent 文件逻辑内容最多
12 KiB、目录与文件总逻辑量最多 16 KiB、实际分配最多 64 KiB、inode 最多 4，作为既有
共享 capture 20 MiB / 384 inode 的子预留，
不增加总额度；父目录增长、部分写入和同步峰值也计费。每个实际设备仍按既有完整承诺
计费，host 已用量与未用子预留只计一次，不能让 guest 扣减或重复扩张 capture 总额。
最终 0600 evidence ZIP 是联合准入后的既有封存输出，不属于此前主动创建白名单。
它的 evidence parent 身份由 context 固定，basename 由 manifest、intent 与独立 Owner P4
event/ref 共同绑定。manifest/context/intent 同时固定单个原始 ZIP（host 不展开）的四个
独立字段：`evidence_max_frame_bytes` 约束固定 header 与 ZIP payload 的整个 wire frame；
`evidence_max_archive_logical_bytes` 约束 frame header 的 archive length 与最终 `st_size`；
`evidence_max_archive_allocated_bytes` 约束任一部分或完整文件的 `st_blocks*512`；
`evidence_archive_inode_count=1`。frame 上限还受 management-output 上限约束，archive
logical/allocated/inode 则受 capture 上限约束，不能用其中一个字段替代另一个。

写前账单固定为两个不重叠的峰值：`record_peak` 是创建/写入/fsync 各时点中 marker 子树
实际分配、消费 parent 正增长与其它未覆盖 record metadata/sync 的最大和，须保持在
64 KiB / 4 inode 内；`evidence_peak` 是部分或最终 evidence 文件实际分配、evidence parent
正增长与其它未覆盖 evidence metadata/sync 的最大和，其中 partial/final 是同一个文件的
状态峰值，不与完整文件上限双加。共享 capture 账单以物理身份去重，固定为“既有 capture
actual + 未释放且不含已划拨子预留的 future + record_peak + evidence_peak”，不得超过
20 MiB / 384 inode；同一设备聚合，不同设备分别以各自子集对 available 准入，但全局 ceiling
只存在一份。statvfs 采样前已存在的 actual 只通过当前 free 扣除，不再作为容量加数；未来
义务与尚未物化的峰值仍须叠加。parent 原有基数 B 不得填零；其分类/覆盖或任何峰值未知时
保持 `field_ready=false`。全部预留须在消费目录 mkdir 前完成，不能等最终帧到达再补做。
P4 在消费目录 mkdir 前须经
held no-follow fd 核验 evidence parent 及祖先，并确认固定 basename 不存在且不是 symlink；不符即
`LOCAL_BLOCKED_UNCONSUMED`。guest 最后证据帧声明 archive bytes/SHA-256/length，host
先按预先固定上限核验；超限即停止且不创建 host evidence 文件。合格后才对 held evidence
parent 使用 `openat(O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW|O_NOATIME|O_CLOEXEC, 0600)`；持续
持有返回的 file fd，先 `fchmod(0600)` 以消除 umask 差异，再以完整写循环写入并依次 fsync
file/held parent。最终报告前须从同一 file fd `pread` 复读长度和 SHA-256，并经 held dirfd
用 no-follow stat 把固定名称重绑定到同一 device/inode，核验普通文件、准确普通 UID/GID、
精确 0600、`nlink=1`、无 ACL、`st_size` 等于 archive length，且 `st_blocks*512` 不超过
`evidence_max_archive_allocated_bytes`。既存/链接/parent
漂移禁止覆盖；短写、fchmod/fsync、重绑定或复读失败保留固定名称的部分文件并停止，不改名、
不清理、不重试。
evidence parent 增长、部分文件与同步峰值均计入既有封存/capture 预算。

durable intent 后只允许一条固定 remote-exec SSH channel；禁止另用 scp、第二 SSH 或
失败后补连 journal。准确包必须绑定固定 remote argv 和内存 bootstrap 的 bytes/SHA；
bootstrap 由已有 `/usr/bin/python3` 通过固定 argv/受限 stdin 前导直接启动，不依赖尚未
传到 guest 的 ZIP，不写文件、不接受任意命令。它在同一 stdin/stdout 内按固定长度、顺序
和总量的帧协议完成握手，READY 后才接收已绑定 ZIP；有限 systemd/journal 补采也只能在
同一 SSH、同一截止内完成。

guest bootstrap 首先无持久副作用地读取 actual boot、采样 guest
`hello_boottime_ns`，返回严格有界 HELLO 与 nonce；host 必须把 actual boot 与私有预期值
比较。host 收到 HELLO 后先采 `host_hello_received_monotonic_ns`、再紧邻采
`host_hello_received_boottime_ns`；后续每个 guard 也固定按 MONOTONIC→BOOTTIME，发出
BIND 前再执行一次 guard。对 `X ∈ {outer, preparation}`，固定公式为：
`raw_X_ns = min(X_monotonic_deadline_ns - host_hello_received_monotonic_ns,
X_boottime_deadline_ns - host_hello_received_boottime_ns)`；
`duration_X_ns = floor(raw_X_ns / 1_000_000) * 1_000_000 - 2_000_000_000`。
任一 duration 不为正就拒绝。BIND 帧回送两次 host 样本、两个 raw 值、固定
`floor_unit_ns=1_000_000`、`sampling_margin_ns=2_000_000_000`、两个 duration、nonce、
intent digest 和 ZIP digest。guest 以同一 `hello_boottime_ns + duration_X_ns` 形成两个
本地绝对截止，收到 BIND 后以当前 BOOTTIME 再确认均未过期并返回 READY；host 验证 READY
后才发送 ZIP。guest consumed marker 与最终 seal 必须绑定 HELLO、BIND 全字段和两个
截止，使公式可复算。ACK、READY 及每个后续阶段都检查适用截止；两台机器不比较或复制
时钟原点，也不能刷新期限。target、supervisor 和 management 的既有停止余量仍分别独立
保留，不由 2 秒裕量替代。owner 阶段开始时的截止只能取 `当前 BOOTTIME + 120s`、guest
outer 截止扣除既有 stop/EOF/fsync/seal 余量及其它更小既有截止中的最早者。握手、boot
或消费前旧对象检查失败时，guest 不写 consumed marker，但既存 host 目录已经终结本次
授权；host 仍强制原双钟截止，关闭或杀死 SSH 只证明本地 client 状态，不冒充远端停止证明。

上述公式只证明 HELLO 时刻的保守算术映射；一次 anchor、heartbeat、EOF 或模型 fixture
都不能自行证明后续 host/guest clock rate、VM pause 关系或远端停止。当前固定输入尚未
闭合 H07；上述双 parent 文件系统、证据上限与峰值/持久资格也尚未闭合。P1–P3 必须先以
本范围允许且准确固定的机制证明整个运行期间的最大速率/暂停关系和独立 stop，并闭合两条
落盘路径的资格与预算，或者保持 `field_ready=false`、不生成可现场执行的 P4 包；若所需机制、
来源或权限超出本 A，必须回到 R 形成新的受影响 A。不能以杀 client、SSH heartbeat、
RuntimeMaxSec 或 guest 本地截止单独替代该证明。

跨进程 replay 拒绝不是 0700/0400 权限位提供的技术性防回滚证明：同一普通 UID 的进程
仍可 chmod/unlink/rename 自己的文件，并可删除或替换自己父目录中的消费目录。本合同明确
依赖 CLOSED 合同的可信存储及程序/操作者诚信外部前提：同一 host boot 内，范围外管理者
和任何同 UID 进程都不删除、替换或整体回滚受保护 parent、消费目录、intent 或 evidence。
Owner B 只有绑定准确 A 才表示接受这一治理输入；这不把它转化为技术证明。launcher 只
核验可观察状态，不承担证明全局否定事实的任务；若该前提未被接受、被标记为未知/不成立，
或观察到回滚、替换、boot 改变或持久性异常，只能 `BLOCKED/UNKNOWN`，不能重新创建并
声称未消费。若必须技术性抵抗同 UID 回滚，当前 ordinary-owned parent + 0700/0400 设计
不足，须由不同保护主体持有不可删除父级或采用另行批准的机制，并回到 R 形成新的受影响 A。

ZIP 输入/展开计入既有 64 MiB / 4096 项代码交付池；协议帧与双流计入既有管理输出上限；
SSH/systemd/journal 自然审计记录计入既有 journal/capture 上限。派发前必须为这些实际与
峰值保留完整费用；未知时在 SSH 前停止，不借审计名义新增日志设施或额度。

本范围不提供任意命令、任意 unit/路径、通用 rerun、清理或 release 接口。
不启动/重启旧 user manager，不修改 AppArmor、sysctl、capabilities、挂载、
系统包或任何既有 unit、数据库、quota；只允许在 CLOSED 后 create-only 创建本范围
明确列出的新数据库与新 quota。不开放生产 backend、Q3、GX10、NAS 或 E4–E6。

## 新对象与保留义务

新批次固定使用：

- BASE `/opt/local-hand-resume-5ca9753-20261002a`；
- CODE `/opt/local-hand-code-20261002a`；
- outer unit `local-hand-resume-5ca9753-20261002a.service`；
- ordinary slice `lhqq2controller-ordinary20261002a.slice`；
- supervisor/target unit `lhqnormal20261002a-supervisor.service`、
  `lhqnormal20261002a-target.service`；
- 所有 normal setup/state/session/control/authority/declarations/capture/journal/quota
  路径均使用唯一后缀 `20261002a`；
- 七个新 project ID 为 `12061..12067`，各 1 MiB / 128 inode，现场创建前仍须确认未占用。

固定映射为 `12061 work-a`、`12062 evidence-a`、`12063 temporary-a`、
`12064 work-b`、`12065 evidence-b`、`12066 temporary-b`、
`12067 retained_store`；不允许调换角色或部分复用。

即使某些 `20261001e` 计划对象尚未创建，也不得复用该批次绑定的名称或
`12051..12057`。容量检查至少保存并核验旧 BASE/CODE 的实际分配、该批次
64 MiB / 4096 项代码池承诺，以及已批准但未释放的 state、journal、capture
和七 quota 域承诺；它们与全部更早义务、当前新批次授权共同按物理文件系统计费。
不得以“未 provision”推导退款。实际占用只通过现场 statvfs free 体现，不再显式
加成第三项；仍须在该 free 上叠加同一范围未释放的完整承诺，这不是退款或残额算法。

## 不变预算与 Owner 决策

新批次沿用原系统管理器批准的上限，不增加单项预算：

- outer 300 秒与 preparation 150 秒从 host launcher 在任何 P4 本机现场读取前按
  BOOTTIME-first、MONOTONIC-second 取得的保守双原点开始；本地预检、host intent、唯一 SSH、传输及消费前
  检查均计入 preparation。owner 120 秒只取开始时的 outer 剩余量并扣除既有停止/封存
  余量；原 operation 72 秒、30 CPU 秒、98,304 字节输出，内部 phase/stage、停止和证据
  余量保持；
- controller 512 MiB / 64 tasks / 100% CPU；target 256 MiB / 32 tasks /
  85+1 秒；新 ordinary 256 MiB / 32 tasks / 100% CPU；它们保持兄弟/父级几何；
- supervisor 64 MiB / 32 tasks / 100+1 秒；management 三阶段仍各
  64 MiB / 8 pids / 2 CPU 秒 / 32 KiB，admission/collector/query 时限分别为
  7/8/5 秒；
- 管理总量 400 CPU 秒、1536 MiB、1024 pids、16 MiB output、
  32 MiB / 1024 inode；state 8 MiB / 1536 inode、journal 1 MiB / 128、
  capture 20 MiB / 384；七根各 1 MiB / 128；
- 新 BASE/CODE、输入 ZIP、展开峰值、受限日志与私有包内受限帮助程序合计
  64 MiB / 4096 项。

Owner B 只针对准确 A 明确批准：保留已消费且失败的 `20261001e`，采用上述四字段解析
修复及 R12 的两项固定内核视图 reader 集成，并允许 P1–P3 实施及 P4 合同/资格验证；B 不创建 `20261002a` 现场运行权，也不改变
旧 M4 结论。准确私有包生成且 H07 等全部资格闭合后，Owner 还须另作 P4 决定，以稳定
事件/引用逐字绑定 scope `LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1`、batch `20261002a`、
准确 A/C/D、ZIP basename/bytes/SHA-256、固定 evidence basename、上述四个 `evidence_*`
字段、仅一次和失败不重试。
B 对准确 A 的绑定也明确接受本文披露的 trusted-storage/no-same-UID-tamper 治理前提，但
不构成技术性防回滚证明。B/C/D、CI/READY、产品 commit、ZIP 或 `TASK.txt` 的存在以及
裸“继续/授权继续”均不能替代该 P4 event；它不授权第二次 `20261002a`，也不降低任何
安全或验收条件。
