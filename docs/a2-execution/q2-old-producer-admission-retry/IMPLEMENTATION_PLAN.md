# Q2 旧生产者准入解析失败后的单次替代批次：实施计划

- Authority：Owner；状态：**PROPOSED / Gate OPEN**；scope：`LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1`。
- [需求](REQUIREMENTS.md) → [架构](ARCHITECTURE.md) → 本计划。
- OPEN 期间仅允许形成准确 A，并只读审阅既有失败与既有离线修补证据；采用修补和
  离线实现必须等待 Owner B 和独立 CLOSED C。生成可现场执行的 ZIP 还必须先闭合 H07、
  双 parent 文件系统与证据峰值/持久资格；任何 guest 操作另须准确包生成后的独立 Owner
  P4 stable event/ref。

## 固定输入和不变项

前驱是唯一已消费 `20261001e` 调用；其状态保持 `FAILED_RETAINED`，外层退出 1，
首错为 old-producer admission 中缺失 `ExecStartPre` 的 `KeyError`，正常链计数为 0。
原修正版交付 ZIP、现场 evidence ZIP 及其中 consumed/staged、code intent/receipt、
plan/preflight/failure、systemd show/journal 都是私有固定输入；公开仓库只记录
脱敏结论与合同，不复制原始现场字节。

固定私有输入为：修正版交付 ZIP，3,887,651 字节，SHA-256
`5805dcd2a45f150f0e5b7062a17b46137d53e889e1ea160601d7c75fb529e886`；现场
evidence ZIP，129,584 字节，SHA-256
`f352d1d8bc70d3d4c419c21de493efca2c51a3453dc90d04fba3ec654e7e33b6`。
其中 intent/receipt/plan/preflight/failure/consumed/staged/client-result 的 SHA-256
依次为 `c4e45fc7fa217722fe57f7576d85c72181ad93a9cdf422e0a3919b77a1493a48`、
`1bc8d61538d0c48f604e3bf2fb7002b481bb62e7f0c3c7ffc433c0818ef5b1f5`、
`85633b837718282ba6590b7a6679d51aa60addfb0f5be39ea929af83de4a45c1`、
`eabe18b207e68967e65b9dc9d114466aad7284063cff6e90814938a0ae9fb086`、
`79ccccf1745bcad29089c381e692ca777c7fc2165cd31cc1f54ed825db545b85`、
`ba29f6c3dcfab18708f1d67de58a5bb8bff1918b4d01c3fd49b67ee1c70156ee`、
`63fd8aa4b3f8cc406b47b94109d547d4ecdc85d147034e45b068e65e222a08ae`、
`ef898352c22ffc601f2617327918a0f0baa45d45def99e487bde45e41e1878cd`。

既有离线修补件固定为
`local-hand-system-manager-1a900e4-old-producer-parser-fix-20261002.zip`，
12,864 字节，SHA-256
`2ddb55db15f73738116377de6fb8fa8fba9c5cc2cf23f1f59e2dc112ce63be70`；其中
`old_producers.py` 修改前/后 SHA-256 分别为
`4014a80998469607f8a279a4fc7b7abbeff61e349657b7d8224429d142dfa8db` /
`3e6521f6065a3bb61e12b0f2cdcbf1c7f2d40e138269bf85d386aeb2741ab21a`。
该件不含 `TASK.txt`，只作为待采纳的离线 evidence。

产品候选保持：commit `1a900e4a38e9567655f21cbf3c3f17941de1a8d5`，tree
`ffffce7258036a974d44f6dc8b3ed022d4127aac`，payload
`fbd773a9a669440ad015dfe0967b3d505d3cabc91b11fee7ddb4015d90aae118`。
`source.bundle`、wheel 和 `code-manifest.json` 必须逐字复用并重新核验；不提交
私有 helper，不改变产品源码。required CI 必须在现场消费前对该准确 commit 读取成功。
三者 SHA-256 分别为
`36fddae6dd57b2d80b90b4eff5d5bf40cb2f6a29d91d946c1bbefabdb5ae2fc0`、
`76a2573f9b5f0a1e9e260bf215f57d6cd011f49736653e0939ebd1b2ba034d9a`、
`c764a4f6a05d2b6aaa6f8c1d35617a520dba1c1e91fad54b0e93e02ba856fe86`。

host 消费机制的固定前驱为 CLOSED host-window A
`8402f0cc82d8a0ac0b9a56716bf276f41cafea37`、C
`271c07cd16140aa5942dcf3fad468003c58b6b0e`、组件 D
`f1814b27adbc1bcdb6d6ac14875e9d2ec6a795ff` 和只读预检后继
`0a456a909821fd1fc6a4fdec43b9e16bc88679f2`。普通身份 v2 writer 另固定为组件 D
`c2373313eb78aa55373cb0318d08d5f60424dafd` 及其
[实现复核](../Q2_ORDINARY_WRITER_IMPLEMENTATION_REVIEW.md)；首次 parent 增量有限计费后继固定为
组件 D `530a2a45bc6e96270771ccf266793e471d8408ee` 及其
[实现复核](../Q2_PARENT_ALLOCATION_IMPLEMENTATION_REVIEW.md)。它们只提供各自已批准的原子记录、
普通身份和有限首次端点账单机制，不证明中途峰值、allocator/属性 inode、sync、持久性、
field readiness 或 H07；本范围使用新固定路径、新 intent 和新的单次现场授权，不复用旧消费对象。

固定内核视图 reader 的准确前驱为 A
`887b640b394f9983f37dfe97c58ba35aaa099359`、C
`f7f8b503470725ca1ba18d1cb8d8b39e09a15ea8`、D
`e15c633adbdfbf1e29cb12b2410975fe4911458d` 及其
[实现复核](../Q2_KERNEL_FACT_READ_IMPLEMENTATION_REVIEW.md)。该旧范围只授权 local preflight；
本范围必须经自己的 B/C/D 才能把同一 reader 窄接入新 consumer，不能把旧授权或包当作现场权。

## P1：C 后准确实现、验证并固定 D

现有无 `TASK.txt` 的 repair artifact 是原 CLOSED scope 下形成的既有离线 evidence，
不是本范围的 D，也不提供现场权限。仅在本范围 Owner B 与独立 CLOSED C 之后，
采纳并复核私有 `old_producers.py::_show()` 的四字段兼容变化：按原 UTF-8 与既有
`key=value` 映射规则解析后，只对四个允许被 systemd 省略的空 Exec 数组字段使用
空字符串默认值。保持 caller 选择的 manager、全部下游检查、命令、超时、读取范围、
错误码和其它字段不变。

同一 D 还须把上述 K D 的专用 reader 明确接到新 consumer 的 host boot 与 mountinfo
读取点；这是本 A 请求的第二项隔离变化，不是旧 K scope 的隐式传递。reader 只允许固定
boot_id 和本进程 mountinfo，分别限制 64 bytes / 1 MiB，并保持 K 的逐段 no-follow held fd、
procfs magic、device/mount ID、叶身份、读前/读后名称重绑定、有界分块/EOF、准确 errno 和
原双钟 guard；内容 fd 精确使用 `O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK`，不得加入
`O_NOATIME`。不得接受任意 proc 路径/PID、PermissionError 后降级、通用 fallback、sudo、
capability、remount 或额外扫描；其它普通文件仍走原 `O_NOATIME` 保护路径。outer consumer
必须在任何 proc 内容读取前先按固定 context 核验 real/effective/saved UID/GID 三元各自全等
且非 0，并核验稳定排序、保留重复项的完整 groups；在每项读取期间及读后重复该 guard，不能
把 K helper 自身允许 root/当前 euid 的叶 owner 检查冒充 ordinary consumer 身份证明。

独立测试至少包含：

1. 四字段全缺、分别缺失、显式空均可继续到原下游校验；
2. 任一字段非空时拒绝；
3. Id/LoadState/MainPID/ControlGroup/FragmentPath 等关键字段缺失仍拒绝；
4. 命令非零、超限和 UTF-8 解码错误保持原失败行为；
5. 完整 old-producer caller 在旧 unit 固定输入上保持既有 Id 完整性/重复 Id 与
   其它关键字段的 fail-closed 行为；
6. 普通身份下原 proc `O_NOATIME` 对照可返回 EPERM，而两项固定 reader 仍按 K 合同成功；
   任意路径/PID、非 procfs/子挂载、mount ID 或名称变化、超长/无 EOF、缺 ABI 能力均拒绝；
7. 静态与动态检查证明 consumer 的 boot/mountinfo 只调用专用 reader，且不存在
   `O_NOATIME`、失败降级或第二读取路径；原 host 终端与 proc/PID namespace 对齐只标作
   外部环境假设，不冒充已证明事实；
8. 在任何 proc 内容读取前，root、混合 UID/GID 三元、context/groups 不符均拒绝且 reader
   未调用；合法普通身份在 boot 前、两项读取之间和读后漂移也拒绝，后续无创建或 SSH。

修补文件独立记录 before/after SHA；非现场 repair artifact 不含 `TASK.txt`，不能执行。
先把公开安全的实现、测试、封包器合同和验证记录提交为本范围独立实现 D；D 必须以
本范围 bookkeeping-only C 为祖先，且不得与 C squash。D 固定 helper before/after
摘要和将生成的私有包/manifest 合同，但不提交私有 helper、连接资料或原始现场证据。
旧产品实现 `1a900e4` 与本范围 D 是两个不同身份。

## P2：H07/文件系统资格硬门与条件式准确封包

Owner B、独立 C 和本范围 D 是必要条件，不是现场充分条件。当前固定输入没有证明整个
运行期间的 host/guest 时钟速率、VM pause 上界或独立远端停止，也没有闭合消费/evidence
两条 parent 的准确文件系统资格、evidence 上限及 parent-growth/部分写入/sync 峰值与持久性；
除 P1 明确批准的两项固定内核视图 reader 窄集成外，本 A 没有批准新的机制、来源或权限来补足
上述 H07 与双 parent 峰值/持久资格证明。因此当前范围只允许形成 `field_ready=false`、
`allow_run=false`、无 `TASK.txt` 的非执行原型、合同 fixture 和离线验证材料，不得生成
可现场执行的 P4 交付。若后续按 R 形成准确受影响补充 A/B/C/D 并闭合全部硬门，才可从
干净仓库和准确实现组装唯一 `20261002a` 运行包。所有固定常量和合同必须显式更新，不做
未经审阅的全局替换：

- 新 BASE/CODE、prefix、identity、outer/supervisor/target/ordinary slice、全部
  normal 目录和 project scope 改为 `20261002a` / `12061..12067`；
- `20261001e` 作为前驱保留，加入历史 code-update intent/receipt、失败计划和
  现场绑定；用独立 pre-provision-failure 类型表示，不加入 `prior_normals`；
  old-producer 与 protected-path 集合显式覆盖其 BASE/CODE、12 个计划目录、
  7 个 root、ordinary slice 和 outer/supervisor/target 名称；
- 容量实现增加该前驱的代码池、state/journal/capture/quota 全额未释放义务；当前
  statvfs free 已含实际分配影响，实际只记录、不显式加为第三项，也不得从承诺扣除；
  所有更早 prior normals/code updates 不变；
- package manifest 写入 Rule R、准确 A、Owner B stable event/ref、独立 C、本范围实现 D、
  任何闭合 H07 与文件系统/峰值资格的准确补充批准链，并另行写入旧产品实现 commit
  `1a900e4` 以及固定 K A/C/D 与本范围 consumer 集成版本；同时写入新
  scope/批次/purpose、前驱摘要、helper 新 SHA、`guest_executed=false`、
  `normal_chain_executions=0`、`q2/q3/production=false`；
- 固定成员 `host-locator.json` 使用专用严格 schema，只含规范绝对 parent 与预期
  type/UID/GID/精确 mode/device/inode；`host-context.json` 绑定 locator 摘要、host boot、
  完整普通操作者与 SSH/guest 身份，以及规范绝对 evidence parent；manifest 固定唯一
  evidence basename、`evidence_max_frame_bytes`、`evidence_max_archive_logical_bytes`、
  `evidence_max_archive_allocated_bytes`、`evidence_archive_inode_count=1`，并绑定两者的 member
  name、bytes、SHA-256、parser version，以及 scope+batch 复算的固定派生目录、0400 intent、
  12 KiB 文件/16 KiB 总逻辑/64 KiB 实际/4 inode 子预留、双钟双截止、host-intent schema
  和跨机握手版本；CLI、环境变量、`TASK.txt`、
  输出目录和同一 manifest 中的自由路径均不能覆盖它们；公开仓库不披露真实值；
- host intent 使用专用 schema 与 `old_producer_admission_retry_20261002a_once` 权限；它绑定
  scope/batch/R/A、Owner B stable event/ref、C/D、闭合全部硬门的补充链、准确 ZIP/helper/
  bootstrap/固定 SSH argv、locator/context/host/guest/固定 evidence parent/basename/四个
  独立 `evidence_*` 上限/计数字段、
  操作者 real/effective/saved UID
  三元全等且非 0、real/effective/saved GID 三元全等且非 0、稳定排序且保留重复项的完整
  groups、host boot、双原点/双截止/预算和消费状态，但不自包含摘要；旧版本 decoder
  与新 decoder 双向拒绝；
- 固定 in-memory bootstrap 必须能在 ZIP 到达前通过同一 SSH 完成 HELLO/BIND/READY，且不能
  接收任意命令或依赖未收到的 ZIP。只有最终可执行包才含 `TASK.txt`；它只声明独立 Owner P4
  stable record 的必需字段与外部核验规则，不内嵌尚未发行的具体 event/ref。准确包完成后
  才能发行的 P4 stable record 由 host 在任何现场读取前独立核验，并仅写入本次 live host
  intent。`TASK.txt` 另声明唯一入口、准确包 SHA/字节外部核验、单 SSH 有界双向帧、全新对象、
  完整期限/预算、失败保留和禁止清理/重试，不得声称旧失败已修复或现场已通过。

旧 `20261001e` 的任何文件、unit、项目 ID、marker、身份和期限都不能成为新包写入目标。

## P3：离线验收与 H07/文件系统资格硬门

对非执行原型以及将来满足资格时的最终包执行并保存：

- ZIP CRC、平铺成员/名称/模式/大小、`SHA256SUMS` 和 manifest 双向一致；
- 所有 Python 语法、AST/常量与固定调用边界检查；
- P1 解析负例、host/guest stage/consume replay 拒绝、BASE/CODE/路径/project 预存在拒绝；
- 两项固定内核视图 reader 的 K A/C/D 固定值与 consumer 调用边界；普通身份 EPERM 对照、
  固定 boot/mountinfo 成功路径、64-byte/1-MiB 上限、procfs/device/mount ID/名称/叶身份读前后
  复核，以及任意路径/PID、子挂载、`O_NOATIME`、fallback、提权和额外扫描拒绝；
- locator/context 的严格 schema、重复 key/多余字段/尾随数据拒绝，两个 parent、固定 evidence
  basename/上限及派生名不可由参数改变；准确固定且受保护的 0755 parent 可接受，
  `mode & 06022 != 0` 必拒绝；消费与 evidence parent 均覆盖真实 rw ext4、实际 block device、
  rdev/保护位/superblock/4 KiB 几何、feature/flag、fstatvfs 和逐设备峰值准入；旧 indexed/
  12 KiB parent 等不合格输入必须拒绝且无动态 fallback。真实本地竞争、空/部分/同值/symlink/
  类型/owner/mode/nlink/ACL/设备异常、短写及 file/directory/parent fsync 失败均在 SSH 前阻断，
  且不得现场 mkdir/chown/chmod parent；`530a2a45` 的首次端点 G 不冒充中途/同步峰值证明；
- host intent 的专用 schema/权限/规范字段、12 KiB 文件/16 KiB 总逻辑/64 KiB 实际/4 inode
  计费与复读；完整 groups 导致规范 intent 超过文件上限时必须在 mkdir 前拒绝、不得截断；普通 issuer
  在创建前/中/复读后取得的 getresuid/getresgid 三元各自全等且非 0，完整 getgroups 经稳定
  排序并保留重复项后逐次相同，parent/目录/文件 UID/GID 逐项相等；root、混合或任何观测到的
  身份变化、caller identity override、chown、旧 schema/permission 均拒绝；采样不能排除
  change-and-revert，fsuid/fsgid、capabilities 与 user namespace 在身份结论之外且不是本 A
  新增硬门，不能声称已证明；
- fixtures 明确证明 0700/0400 只阻挡其它 UID，不把它们当作同 UID 防回滚保证；覆盖同 UID
  chmod/unlink/rename/目录替换竞态并拒绝，但不得由竞态测试推导跨调用不可回滚。可信存储
  与 no-same-UID-tamper 是由 Owner B 绑定准确 A 才接受的外部治理输入，不是技术证明；该前提
  未接受、未知/不成立或观察到回滚/替换时保持 BLOCKED/UNKNOWN。
  若要求技术性抵抗同 UID，须改用不同保护主体或另行批准机制并回到 R；
- 初始 host anchor 覆盖 BOOTTIME-first/紧邻 MONOTONIC-second（或等价保守 bracket）；HELLO
  receive 与后续 guard 覆盖 MONOTONIC-first/BOOTTIME-second。两读间 suspend 由两钟较早
  剩余量保守计入，并在到限或余量不足时拒绝。outer/preparation 分别按
  `floor(min(截止M-样本M, 截止B-样本B)/1ms)*1ms-2s` 计算并绑定两个 raw、floor、margin、
  duration；任一非正、nonce/digest/boot/顺序错误均拒绝，禁止直接比较跨机原点；
- 前驱摘要篡改、旧完整承诺漏算、实际分配被显式第三次计入、quota ID 冲突、容量不足拒绝；
- 以 fixtures/静态检查证明 collector 完整覆盖旧计划 12 个目录、7 个 root、slice
  fragment 与 `12051..12057`，并在缺项/未知时 fail-closed；真实 `lstat`/inventory
  只允许在 P4 执行；
- 产品 source bundle、Git commit/tree、wheel 逐文件/payload 与 code manifest 一致；
- 固定 evidence parent/basename 与单个原始 ZIP 的 `evidence_max_frame_bytes`、
  `evidence_max_archive_logical_bytes`、`evidence_max_archive_allocated_bytes`、
  `evidence_archive_inode_count=1` 在消费 mkdir 前进入逐设备账单；fixture 分别验证 frame
  header+payload、archive length/`st_size` 与任一 partial/final 的 `st_blocks*512`。`record_peak`
  与 `evidence_peak` 按 marker/archive、各自 parent 正增长和未覆盖 metadata/sync 的时点最大和
  计算，partial/final 不双加；共享 capture 以物理身份去重，使用“既有 actual + 未释放且不含
  已划拨子预留的 future + 两个 peak <= 20 MiB / 384 inode”，同设备聚合、异设备分桶而全局
  ceiling 只一份。statvfs free 不重复加入既有 actual，parent 基数 B 未知不得填零；
  超限帧不创建 host evidence 文件。覆盖既存/symlink/短写/fsync/复读失败的固定名称保留、
  `O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW|O_NOATIME|O_CLOEXEC` 0600、持续 held file fd、
  `fchmod(0600)`、完整写循环/fsync/pread，以及经
  held dirfd 的固定名称↔device/inode 重绑定、普通文件/准确普通 UID/GID/精确 mode/
  `nlink=1`/无 ACL/实际分配上限核验；失败不改名/清理/重试；
- 同一 SSH fixture 覆盖 HELLO→BIND→READY→ZIP→运行/日志→最后 evidence archive 帧→双 EOF，
  以及各阶段首错/超时/EOF/stop 不明；禁止 scp、第二 SSH/SFTP 或失败后补连 journal，均
  仅一次且保留证据；
- 私有包 0600，生成新的 SHA-256；本地验证明确标记 `guest_executed=false`。

模型 fixture、一次 anchor、heartbeat、EOF、`RuntimeMaxSec` 或 client kill 都不能证明整个
运行期间的跨机 rate/pause 上界和独立远端 stop。不得因测试方便访问 guest、复制旧 marker、
清理前驱或临时放宽检查。当前 A 下 H07 保持 OPEN，故 P1–P3 只能产出非执行材料，不能把
测试通过写成 `READY` 或生成可执行交付；双 parent 文件系统/证据上限与峰值/持久资格同样
保持 OPEN。若闭合任一硬门需要新增机制、来源或权限，回到 R 形成新的受影响 A，而不是在
实现或包内偷偷扩大范围。

## P4：一个替代现场批次（当前 BLOCKED）

当前 A 的 H07 与双 parent 文件系统/证据峰值资格均未闭合，因此本节只是将来现场执行的
验收合同：不得据此生成可执行 ZIP、
创建 host 消费对象或连接 guest。只有准确受影响补充 A/B/C/D 以本范围允许的独立机制证明
整个运行期的跨机 rate/pause 边界和远端 stop，闭合双 parent 文件系统/证据峰值资格并完成
最终包完整核验后，Owner 才可另发独立稳定
P4 event/ref；它必须逐项绑定 scope、batch、准确 A/C/D、任何 H07/文件系统资格补充批准链、
ZIP basename/bytes/SHA-256、固定 evidence basename、四个独立 `evidence_*` 上限/计数字段、
仅一次及失败不重试。B/C/D、CI/READY、
产品 commit、ZIP、
`TASK.txt` 和裸“继续/授权继续”均不能替代。资格闭合后，本地 Codex 才可严格执行：

1. 先离线核验 event/ref、准确 commit 的远端 required CI 和本地 ZIP/manifest；这些确定输入
   不读取新的 host 现场状态。任一不符在 mkdir 前以 `LOCAL_BLOCKED_UNCONSUMED` 结束本次
   调用，不接触 guest、不自动重试；未来再调用仍需新的准确单次 P4 event/ref；
2. 在任何 P4 本机现场读取前先采 host BOOTTIME、紧邻采 MONOTONIC（或等价保守 bracket），
   建立 outer 300 秒和 preparation 150 秒两组绝对截止；随后先只读解析 package-bound
   locator/context，在任何 proc 内容读取前以 `getresuid/getresgid/getgroups` 核验非 root、
   UID/GID 三元各自全等且完整 groups 匹配的固定普通操作者。只有该 guard 通过，才通过固定
   K reader 的本范围集成读取 host boot 与本进程 mountinfo，并在两项之间及读后重复身份 guard；
   再核验现存消费/evidence parent 与祖先的 type/UID/GID/精确
   mode/device/inode/ACL/保护链、准确文件系统谓词与逐设备峰值预算，并确认固定 evidence
   basename 不存在。父目录不得创建或修改；任何漂移在创建新对象前停止；
3. 沿 held fd 排他创建固定 0700 派生目录；目录一出现即持久消费 P4 event。再以
   `O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW|O_NOATIME|O_CLOEXEC` 建立固定 `host-intent.json`，
   held-fd `fchmod(0400)`、规范完整写入、fsync file/directory/parent，并以 held file fd/
   O_NOATIME 复读 bytes/SHA/身份。任一部分失败保留 `CONSUMED_PARTIAL`，不得删除、接管、
   覆盖、改名或重来；
4. 只有 durable intent 后才以固定 argv 和准确摘要绑定的 in-memory bootstrap 发起唯一
   remote-exec SSH。guest 在无副作用状态返回 actual boot、`hello_boottime_ns`、nonce；host
   验证 boot 后按 MONOTONIC-first/BOOTTIME-second 取得 receive 样本，并在 BIND 前同序
   guard。outer/preparation 分别按
   `floor(min(截止M-接收M, 截止B-接收B)/1ms)*1ms-2s` 得到 duration；BIND 绑定两次样本、
   两个 raw、floor=1ms、margin=2s、两个 duration、nonce、intent/ZIP digest。guest 由 HELLO
   样本形成两个更窄截止并回 READY；host 验证 READY 后才在同一有界帧通道传准确 ZIP；
5. 同一 SSH 内完成 guest 消费前 boot/旧 12 目录/7 root/slice fragment/`12051..12057`
   检查、唯一 durable marker、代码装配、前驱/容量/旧生产者准入、create-only system slice/
   目录/quota、一次正常链、停止与有限 systemd/journal 收集。preparation 150 秒包含本地
   预检、intent、SSH、握手、传输及消费前检查；owner 截止取 `guest BOOTTIME+120s`、outer
   扣 stop/EOF/fsync/seal 余量和其它更小截止的最早者，所有阶段不得刷新；
6. 首次失败立即停止，不删除、不修环境、不换 suffix、不自动重试。只有独立远端 stop 证明
   满足后，guest 才把证据 archive 作为同一 SSH 的最后一个有界输出帧发送；host 在双 EOF
   前核验固定最大 length/SHA，并以 held evidence-parent fd 执行
   `openat(O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW|O_NOATIME|O_CLOEXEC, 0600)`、持续 held file fd、
   `fchmod(0600)`、完整写循环/fsync/pread，
   并完成固定名称↔device/inode、普通文件、准确普通 UID/GID、精确 0600、`nlink=1`、无 ACL、
   实际分配上限重绑定核验。超限不创建文件；既存、短写、fchmod/fsync/重绑定或复读失败保留
   固定名称部分文件，不改名、不清理、不重试。禁止 scp、第二
   SSH/SFTP 或失败后补连 journal，保留旧包和旧 evidence。

外层返回 0 也必须继续依据原验收器判断；任何缺失、截断、身份变化、活动进程、无法确认
停止、跨机截止不明或容量不明都如实标记。P4 失败后仅允许只读保留审查；再次运行、
更换候选、复用旧对象或扩大权限均须另有准确范围和新的现场事件。

## 完成定义

在当前 A 下，P1（四字段解析与两项固定内核视图 consumer 集成）和 P2/P3 的离线实现、
合同 fixture 与非执行原型可以完成；这不表示包
`READY`，也不能声明 parser 已在现场通过。只有 H07 与双 parent 文件系统/证据峰值资格经
准确受影响批准链闭合、可执行包
固定且 Owner 另发精确 P4 event 后，才可能进入 P4。届时只有在：

- 前驱与所有历史义务核验；
- 修补后的完整旧生产者准入通过；
- 新资源和固定 system geometry 创建并验证；
- 原正常链、双流、退出/EOF、停止、数据库与证据核验全部满足；

时才可据原合同判断 Q2。否则保留真实终态与唯一下一缺口；Q3 和 production 不随本范围
自动成立。
