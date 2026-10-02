# Q2 旧生产者准入解析失败后的单次替代批次：架构

- Authority：Owner；状态：**PROPOSED / Gate OPEN**；scope：`LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1`。
- [需求](REQUIREMENTS.md)定义新增的一次替代现场批次；原系统管理器修复 A/B/C/D 和已消费 `20261001e` 保持不变。

## 职责与信任边界

| 组件 | 职责 | 不可推导的事实 |
| --- | --- | --- |
| 本地包所有者 | 固定准确 ZIP/SHA/字节、required CI、单次 SSH stdin 与双流；现场前排他绑定新批次 | 本地验证不能证明 guest 状态或授权重放旧批次 |
| 前驱鉴证器 | 读取并摘要核验 `20261001e` 的 consumed/staged、code intent/receipt、plan/preflight/failure 和 failed invocation | `normal_chain_executions=0` 不等于旧包未消费，也不产生退款 |
| 旧生产者准入器 | 有界读取固定 unit/进程/路径；严格解析 systemd 输出并拒绝可影响新资源的旧生产者 | 空父 cgroup、缺单个日志或“当前没进程”不能替代完整准入 |
| 固定内核视图 reader | 在普通身份下只读取 boot_id 与本进程 mountinfo，供 host boot 和双 parent 文件系统准入 | 不能读取任意 proc/PID/路径，不能证明 namespace 对齐、H07 或现场 readiness |
| 容量与 quota 准入器 | 按设备累计全部历史完整承诺与新授权；旧实际分配只标记为已体现在 statvfs free，确认新 ID/路径未占用 | statvfs 已扣实际占用，不等于未释放承诺可忽略 |
| 新代码与装配器 | 复用原解释器/工具，把同一已验证产品候选安装到新 CODE，创建独立 plan/authority/ledger 和资源 | 同一产品 commit 不允许复用旧 CODE、receipt、身份或 deadline |
| 既有 Broker/Runner/systemd 链 | 在新 system slice 中以普通 UID/GID、零 capabilities 和 NNP 运行唯一正常链 | exit 0 不自动成为 Q2/Q3/production 验收 |

host 侧另设一个不可变消费器，但不增加任意本机路径接口。父路径只从准确私有成员
`host-locator.json` 取得；其专用严格 schema 只允许规范绝对 parent 和预期
类型/UID/GID/精确 mode/device/inode，拒绝重复 key、多余字段、尾随数据或执行行为。
`host-context.json` 以专用严格 schema 另行固定 locator 摘要、预期 host boot、完整
普通操作者与 SSH/guest 身份摘要，以及规范绝对 evidence parent 的 type/UID/GID/精确
mode/device/inode；manifest 还固定唯一 evidence basename、`evidence_max_frame_bytes`、
`evidence_max_archive_logical_bytes`、`evidence_max_archive_allocated_bytes`、
`evidence_archive_inode_count=1`，并绑定两个固定 member name、bytes、SHA-256 和 parser
version，最终 ZIP 再绑定 manifest。CLI、环境变量、`TASK.txt`、
输出目录或 manifest 自报的自由路径不能覆盖这些值。

新 consumer 明确窄采用 CLOSED K 链 A
`887b640b394f9983f37dfe97c58ba35aaa099359`、C
`f7f8b503470725ca1ba18d1cb8d8b39e09a15ea8`、D
`e15c633adbdfbf1e29cb12b2410975fe4911458d` 的专用 reader，但旧 K 授权本身只覆盖 local
preflight，不能自动传递到消费入口；本 A 才是该有限集成的待批 authority。reader 只接受
内部 `boot` 或 `mountinfo` 枚举，目标固定为 `/proc/sys/kernel/random/boot_id` 与
`/proc/<os.getpid()>/mountinfo`，内容上限分别为 64 bytes 与 1 MiB；逐段持有
`O_PATH|O_NOFOLLOW|O_DIRECTORY|O_CLOEXEC` 祖先/父 fd，核验 procfs magic、同一 device/
mount ID、名称到 fd、普通叶/单链接/保护属性，并仅以
`O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK` 打开内容，明确不加 `O_NOATIME`。读取前后复核
身份/挂载/名称，使用有界分块读取与 EOF 检查，并保留准确操作标签/errno；不允许任意路径/
PID、先失败再降级、generic fallback、sudo、capability、remount 或新增扫描。原 host 终端与
proc/PID namespace 对齐仍是披露的外部环境前提，不由 boot、数字 PID 或 mount ID 单独证明。

该 reader 的 outer consumer 不能依赖 K helper 自身的 owner 检查来证明普通身份。双钟锚定后，
consumer 先只读解析 package-bound context，并在任何 proc 内容读取前取得
`getresuid/getresgid/getgroups`：real/effective/saved UID 与 GID 三元须各自全等且非 0，完整
groups 经稳定排序并保留重复项后须与 context 相同。该 guard 通过后才可调用 boot reader，
再次通过后才可调用 mountinfo reader；每项读取期间、读后以及后续创建/复读阶段继续重复采样。
root、混合身份、任何观测到的变化或 context 不符均在内容读取或下一动作前 fail closed。

完成上述普通身份及两项固定内核读取后，held directory fd/no-follow 分别比较消费 parent、evidence parent 与固定
context，要求两个现存目录都属于固定普通 UID/GID、精确 mode 未漂移且
`mode & 06022 == 0`，并核验 ACL、设备/inode 和两条祖先保护链。被准确固定的 0755
可接受；0700 只强制用于新消费目录。现场不能 mkdir、chown 或 chmod parent。

消费 parent 与 evidence parent 在任何 mkdir 前都须通过 CLOSED ordinary writer 的准确文件
系统谓词；boot 和受限 mountinfo 内容须经上述专用 reader 取得，不能经过通用
`O_NOATIME` 普通文件路径。mountinfo 指向真实 rw ext4 与实际 block device；设备 rdev、root-owned/
单链接/保护位、superblock 摘要、4 KiB block/cluster、journal/filetype 和全部已拒绝 ext4
feature 逐项匹配；parent 只有 EXTENTS flag，size/allocated blocks 均为 4 KiB；`fstatvfs`
的 block/fragment 为 4 KiB。消费 parent 的 available bytes/inodes 覆盖 64 KiB/4 inode；
evidence parent 覆盖预先固定的 archive 最大实际分配、1 inode 与经验证的 parent-growth/
部分写入/sync 峰值；同一设备聚合一次，不同设备分别准入。未知即 fail closed，不试写或
动态换 parent。后继 `530a2a45` 只证明首次端点非负净增长 G 的有限账单绑定，不证明中途
峰值、allocator/属性 inode、sync、持久性或 parent 原有基数；这些未闭合时
`field_ready=false`。

消费器排他创建
`q2-old-producer-admission-retry-cf8319dc8c8bed098a6917c5777d60b00ac0efcb5fecd813d14fec4e64af6bf3/host-intent.json`。
目录名由 UTF-8 无换行的 scope+batch 域分离字符串复算，不能由参数、PID、时间或输出目录
选择。新目录与固定普通操作者同 UID/GID、0700；intent 与其同 UID/GID、单链接普通文件、
最终 0400。mkdir 成功即消费，随后依次 fsync 目录/父目录，以
`O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW|O_NOATIME|O_CLOEXEC` 排他创建、held-fd `fchmod(0400)`
并完整写入 intent、fsync 文件/目录/父目录，再以 held file fd/O_NOATIME 复读核验准确 bytes/SHA、身份、唯一成员
和分配。任一步失败保留 `CONSUMED_PARTIAL`，不能清理后重来。联合准入前主动创建白名单
只有这一个目录和一个文件；intent 文件逻辑 12 KiB、目录与文件总逻辑 16 KiB、实际
64 KiB、4 inode 均从原共享 capture 类
扣除，并按真实设备纳入同一完整账单，不能给 host/guest 重复额度。

host intent 使用专用 schema/run permission，旧 v1/v2 decoder 与新 decoder 双向拒绝
错版本。规范 JSON 固定批准链（含 Owner B stable event/ref 与独立 Owner P4 stable
event/ref）、新范围 D 与旧产品 D、
批次、ZIP/帮助程序/bootstrap/固定 SSH argv、固定 evidence basename 与四个独立
`evidence_*` 上限/计数字段、locator/context/
evidence parent/目标身份、完整普通操作者
real/effective/saved UID 三元全等且非 0、real/effective/saved GID 三元全等且非 0，以及
稳定排序并保留重复项的完整 groups；再固定 host boot、MONOTONIC/BOOTTIME 双原点、outer/
preparation 双截止、预算、`window_consumed=true`、`owner_issued=false`。它不记录秘密，
也不包含自身摘要；外部 SHA 只在完整字节固定后计算并供握手/guest marker/seal 引用。
任何既存对象、路径/祖先替换、链接、owner/mode/ACL/设备漂移或无法证明 file/directory/
parent fsync 都在 SSH 前 fail closed。普通 issuer 在创建前、创建期间和复读后重复采样
getresuid/getresgid/getgroups；UID 三元和 GID 三元必须各自全等且非 0，完整 groups 经稳定
排序并保留重复项后必须相同。不接受 root、混合身份、任何观测到的变化、caller UID/GID
override 或 chown；parent/目录/文件 UID/GID 逐项相等。重复采样不声称排除采样间
change-and-revert。规范 intent（含完整 groups）在 mkdir 前超过 12 KiB，或连同 4 KiB
目录使总逻辑量超过 16 KiB，就拒绝且不截断。
该记录不证明 fsuid/fsgid、capabilities 或 user namespace；这些不在本身份结论内，也不是
本 A 新增硬门，若以后需要则须固定新来源并回到 R。

消费器继承 CLOSED host-window A/C/D 的机制，但 ordinary v2 writer 另准确固定为
`c2373313eb78aa55373cb0318d08d5f60424dafd`，首次 parent 增量有限计费后继固定为
`530a2a45bc6e96270771ccf266793e471d8408ee`，固定内核视图 reader 另固定上述 K A/C/D。
它们只提供各自已验证的组件边界；旧 K D 也没有自行把 reader 接入 consumer。本范围 D
必须完成并验证该窄集成，但这些前驱均不证明
field readiness、峰值/持久性、H07 或现场权。新消费器使用本范围新路径；旧 marker 及其
批次不能作为本次记录，也不因本范围而获得 replay 权限。

私有交付帮助程序不是产品 wheel 的一部分。它只能在新 CLOSED C 之后进入准确
可执行 ZIP；产品 `source.bundle`、wheel、commit/tree/payload 保持原字节。
私有原始证据、连接信息和 guest 路径快照不进入公开仓库。

## 精确解析修复

准入器保持既有参数数组和由 caller 决定的 manager；`20261001e` 失败路径经原
setpriv 边界调用 `systemctl --user show ... --all --property=...`，其它既有 caller
仍可查询 system manager。`_show()` 按原逻辑将输出解码为 UTF-8，并把含 `=` 的行
在第一个 `=` 处分隔后构造映射；本修复不新增 ASCII、重复键或畸形行策略。构造映射后：

1. 仅对 `ExecStartPre`、`ExecStartPost`、`ExecStop`、`ExecStopPost` 使用
   `setdefault(key, "")`，兼容 systemd 对空数组属性的省略；
2. 下游仍要求上述四项全部为空，任一非空 hook 立即拒绝；
3. 各既有 caller 对 Id 完整性/重复 Id、`LoadState`、`ActiveState`、`SubState`、
   `Job`、`ControlGroup`、PID、fragment、InvocationID、deadline，以及后续实际
   argv、可执行文件和进程身份等原检查不补默认值、不降级；
4. 缺失其它要求字段、字段冲突、unit/进程/路径变化、输出截断或命令失败均保留首错并停止。

该兼容层只表达“已请求的四个数组为空且被 systemd 省略”，不把任意缺失字段
解释为空。离线测试必须覆盖四字段分别/共同缺失、显式空、非空 hook、关键标量
缺失，以及完整 caller 的既有 fail-closed 行为；不得把未实现的解析硬化宣称为通过。

## 前驱绑定与状态模型

新计划把 `20261001e` 记录为不可变 `FAILED_RETAINED` 前驱，至少固定：

- 原交付 ZIP 摘要与字节、consumed/staged 摘要；
- code-update intent 与 installation receipt，候选 commit/tree/payload；
- plan、preflight 和 old-producer-admission failure 摘要；
- outer unit、boot、InvocationID、exit status、双流 EOF 和失败阶段；
- provisioning 未到达、normal chain 计数为 0，以及未创建对象的有界证明。

该前驱使用独立的 pre-provision-failure 历史类型，不能塞进既有
`prior_normals`：后者要求 provision 后的 `observed.roots`，而本次失败没有该事实。
现场仍须逐项 `lstat` 旧计划的 12 个目录、7 个 root 和 ordinary slice fragment，
并核对 `12051..12057` 未配置/未使用；证据 collector 的短 missing 清单不能替代
这次完整准入。任何对象实际存在或状态不明都停止并另行盘点，不按「未创建」强行计账。

前驱事实只允许读取和核验。旧 BASE/CODE/failed unit 不清理、不 reset-failed、
不续期；已存在、缺失或变化与计划不一致均拒绝新运行，不能靠改写设置绕过。

host 成功路径为 `OFFLINE_VERIFIED → WINDOW_ANCHORED → LOCAL_PREFLIGHT →`
`HOST_RECORD_ADMITTED → HOST_WINDOW_CONSUMED → HOST_INTENT_DURABLE → SSH_STARTED →`
`HELLO_VALIDATED → GUEST_DEADLINE_BOUND → PAYLOAD_SENT → GUEST_CONSUMED`；双钟在任何
P4 本机现场读取前采样，LOCAL_PREFLIGHT 与后续阶段均不能刷新。之后 guest 才进入
`DECLARED → CONSUMED → STAGED → CODE_INSTALLED → PREFLIGHTED → ADMITTED →`
`PROVISIONED → ISSUED → RECORDED`。`SSH_STARTED` 只表示 remote-exec channel 已启动，
不能冒充 owner 业务发行。

mkdir 前失败为 `LOCAL_BLOCKED_UNCONSUMED`：无 guest、无新持久对象，本次调用终止且
不自动重试；未来调用需另行准确现场确认。mkdir 后、intent durable 前为
`CONSUMED_PARTIAL/BLOCKED_RETAINED`；durable 后、SSH 前或握手失败为
`CONSUMED/BLOCKED_RETAINED`；SSH 后缺实际 exit、双 EOF 或远端 stop 为
`REMOTE_UNKNOWN/CONSUMED`。host 固定目录与 guest BASE 各自排他且都没有回退边；host
目录已存在而 guest 未消费仍是已用掉的现场授权。每个副作用前记录适用 intent；任一
阶段失败保留当时全部对象和首错，不回滚、不换 suffix、不重新调用入口。只读证据收集
不改变状态机，也不能补写缺失的成功状态。

## 对象、隔离与旧生产者

`20261002a` 的 BASE、CODE、outer/supervisor/target/ordinary slice、状态、证据和
七个 quota 根均 create-only，且与所有保留路径做 no-follow/祖先/设备/重叠检查。
旧 `20261001e` 的 BASE/CODE 和 failed outer unit 加入旧生产者与保留路径集合；
其 12 个计划目录、7 个 root、ordinary slice 以及未创建的 supervisor/target 名称
也进入精确前驱检查。code-update intent/receipt 作为独立历史代码池读取，不从
当前候选实际占用推断释放。

旧生产者准入仍须绑定全部固定旧服务的 unit 文件、argv、实际 PID/UID/GID、
cgroup、期限及保留输出，并证明它们不能影响新资源。旧失败 outer unit 可以保持
failed，但不得有活动 PID/job 或未知子进程；不得通过 reset/restart 改造现场。
若旧进程、未知 EOF/stop、路径别名或可写共享对象无法排除，结果为 BLOCKED。

新 normal 链仍在原 controller 下的独立 system ordinary slice 中运行，target 与
ordinary 为兄弟；业务进程保持私有 manifest 固定的原 ordinary identity、清空 supplementary groups、五组
capability 为零、NNP=1 和原 namespace/路径/quota 检查。修复不引入 root broker、
sudo/polkit 权限、通用 systemd API 或任意命令通道。

## 容量、期限和证据

历史计费区分“实际分配已从当前 free 中扣除”和“未释放的完整承诺”。对
`20261001e`：读取并绑定新加入的 code intent/receipt，将 64 MiB / 4096 项代码池
作为历史完整承诺，在当前 statvfs free 上另行计入；BASE/CODE 实际块和 inode
仅记录其已从 free 扣除，不再显式加成第三项。该批次已授权但未释放的
state/journal/capture/七 quota 域
也保守计入；quota 尚未配置时以受保护的实际父挂载为覆盖设备，不伪造根已存在。
再加全部更早承诺与 `20261002a` 新授权，按设备验证 bytes/inodes 均不超过现场 free。

新 project `12061..12067` 在任何创建前须同时满足：inventory 中不存在、project
未使用、路径不存在、限额工具与挂载身份未变。旧 `12051..12057` 不复用，即使
inventory 中未出现。容量不足、别名或读数不完整均在 provision 前停止。

host 在任何 P4 本机现场读取前先采 `CLOCK_BOOTTIME`、紧邻采 `CLOCK_MONOTONIC`
（或等价保守 bracket），由该双原点建立 outer 300 秒和 preparation 150 秒两组绝对截止；本地预检、intent 写入/
fsync、SSH 建连、握手、传输和消费前 boot/旧对象读取都计入 preparation。所有 host
检查取适用预算中两钟较早剩余量，暂停不能刷新窗口。

durable intent 后只启动一条固定 remote-exec SSH。准确摘要绑定的内存 bootstrap 由
已有 Python 通过固定 argv/受限 stdin 前导启动，不依赖尚未收到的 ZIP、不写文件、不接收
任意命令；禁止 scp、第二 SSH 或失败后补连 journal。guest 无副作用地返回 actual boot、
`hello_boottime_ns` 和 nonce，host 先对预期 boot，再按 MONOTONIC-first/BOOTTIME-second
取得两个 HELLO-received 样本；后续 guard 使用同序并在 BIND 前再检查。对 outer/preparation 分别计算双钟较小原始剩余纳秒，
向下取整到 1 ms 后扣固定 2 s；任一非正即拒绝。BIND 固定两次 host 样本、两个 raw 值、
floor/margin、两个 duration、nonce、intent 与 ZIP digest。guest 从原 HELLO 样本形成
两个本地截止，以当前 BOOTTIME 复核后回 READY；host 验证 READY 才在同一有界帧通道发送
固定 ZIP。两台机器的时钟数值不直接比较，不能从握手获得新的 300/150 秒。consumed
marker 和最终 seal 绑定完整 HELLO/BIND 与两个 guest 截止，使公式可复算。

展开、代码安装、前驱鉴证、旧生产者准入、provision、正常链、停止和有限 systemd/
journal 收集均留在同一 SSH。host 始终执行自己的 outer 双截止；guest 执行映射后的
outer/preparation 截止，preparation 必须在其 preparation 截止前结束。算术映射本身不
证明 guest 截止在 VM pause/clock drift 下始终不晚于 host。owner 截止为开始时
`guest BOOTTIME + 120s`、outer 截止扣原 stop/EOF/fsync/seal 余量及其它更小既有截止的
最早者；外层 unit 只取真实剩余时间，不得在换阶段/unit 后刷新。当前固定输入尚未证明
整个运行期的 host/guest rate/pause 上界或独立远端 stop，故 H07 保持 OPEN；双 parent
文件系统、证据上限及峰值/持久资格也未闭合。P1–P3 若不能用本 A 范围内准确固定并独立验证
的机制闭合这些门，就必须保持 `field_ready=false` 且不生成
可执行 P4 包；若需要新增来源、权限或机制则回到 R 形成新 A。一次 anchor、heartbeat、
EOF、RuntimeMaxSec、client kill 或模型 fixture 均不能单独补证。消费前失败即使没有
guest consumed marker，host 固定目录也终结本次授权，不得再次进入。到限后不能确认
进程停止则记录 UNKNOWN 并结束；SSH 退出、关闭或被杀不构成远端停止证明。

跨进程 replay 拒绝依赖可信存储及程序/操作者诚信外部前提，不是 0700/0400 的技术性
防回滚保证。同一普通 UID 仍能 chmod/unlink/rename 自己的文件，并删除或替换自己父目录
中的消费目录；因此准确 A 声明同一 host boot 内范围外管理者和任何同 UID 进程均不删除、
替换或整体回滚受保护 parent、消费目录、intent 或 evidence。Owner B 绑定准确 A 才表示
接受这一治理输入，但不产生技术证明。launcher 只核验可观察状态；该前提未被接受、被标为
未知/不成立，或观察到替换、回滚、boot 改变或持久性异常时只能 BLOCKED/UNKNOWN，不能
重新创建。若要求技术性抵抗同 UID 回滚，须由不同保护主体持有不可删除父级或另行批准新
机制并回到 R。

ZIP/展开、协议帧/双流和自然 SSH/systemd/journal
审计记录分别进入既有代码交付、管理输出、journal/capture 预算；manifest/context/intent
必须在消费 mkdir 前固定单个原始 evidence ZIP（host 不展开）的四个独立字段：
`evidence_max_frame_bytes`（固定 header+payload，受 management output 约束）、
`evidence_max_archive_logical_bytes`（archive length/`st_size`）、
`evidence_max_archive_allocated_bytes`（任一 partial/final 的 `st_blocks*512`）及
`evidence_archive_inode_count=1`（后三者受 capture 约束）。`record_peak` 取 marker 子树实际
分配、消费 parent 正增长和其它未覆盖 record metadata/sync 在创建/写入/fsync 时点的最大和，
不超过 64 KiB / 4 inode；`evidence_peak` 同理取同一个 partial-or-final archive、evidence
parent 正增长和其它未覆盖 metadata/sync 的最大和，不把 partial 与 final 双加。共享 capture
按物理身份去重后的公式为“既有 actual + 未释放且不含已划拨子预留的 future + record_peak +
evidence_peak <= 20 MiB / 384 inode”。同设备聚合、异设备分别按子集检查 available，全局
ceiling 仍只一份；采样前 actual 已反映在 statvfs free，容量式不再加，future/新峰值仍加。
parent 基数 B 的分类/覆盖不得填零；未知就在 SSH 前保持 `field_ready=false`，不新增额度。

回传保留准确退出码、分离 stdout/stderr、EOF、首错、各阶段回执、有限固定 unit
show/journal、资源和数据库状态；guest 证据 archive 必须作为同一 remote-exec SSH 的最后
一个有界输出帧在双 EOF 前返回，并在帧头声明准确 length/SHA-256；frame 总字节、archive
length 和后续实际分配分别受对应 `evidence_*` 字段约束，超过任一上限就停止
且不创建 host evidence 文件。host 从启动前已核验且
持续 held/no-follow 的 evidence parent fd 以 manifest/intent/P4 event 固定 basename 执行
`openat(O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW|O_NOATIME|O_CLOEXEC, 0600)`，持续持有返回的 file
fd，在其上 `fchmod(0600)` 后以完整写循环写入并依次 fsync file/held parent；再用同一 fd
`pread` 复读长度/摘要，并经 held dirfd no-follow stat 把固定名称重绑定到同一 device/inode，
核验普通文件、准确普通 UID/GID、精确 0600、`nlink=1`、无 ACL、`st_size=archive length`、
`st_blocks*512 <= evidence_max_archive_allocated_bytes`。
只在这些核验后把该固定文件报告为 Downloads 私有证据。既存、symlink、parent 漂移禁止
覆盖；短写/fchmod/fsync/重绑定/复读失败保留部分文件并停止，不改名、不清理、不重试。parent
增长、部分文件和同步峰值纳入封存/capture 账单。EOF 后禁止第二 SSH/scp/SFTP 或补 journal。
成功只证明本次实际通过的边界；Q2 接纳仍需原完整验收，Q3 和 production 保持 false。
