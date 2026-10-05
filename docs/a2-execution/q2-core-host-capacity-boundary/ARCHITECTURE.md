# 核心 host 当前容量边界：架构

- Authority：Owner；状态 **PROPOSED / Gate OPEN / NOT APPROVED**。
- Scope：`LH-Q2-CORE-HOST-CAPACITY-BOUNDARY-v1`，仅 B1–B3；准确 R/A/B/C 顺序见[需求](REQUIREMENTS.md)。
- 本文与[需求](REQUIREMENTS.md)、[实施方案](IMPLEMENTATION_PLAN.md)组成准确 A；批准及独立 CLOSED C 前不实施。
- 仅调整已批准 `LH-Q2-CORE-NEXT-ACCEPTANCE-v1` 的 host 历史容量准入保证，沿用未消费的 `lhqcore-20261005a`。
  不新增 marker、carrier、SSH 请求次数、现场 probe、执行机会或失败后的重试权。

## 1. 固定事实与保证变化

采用 `26421d723499dde013964aab89c37da839613cff` 的
[保存来源核验与实现报告](../Q2_CORE_NEXT_ACCEPTANCE_IMPLEMENTATION_REVIEW.md)：固定归档的 44 份原件均匹配，
但归档成员不证明完整 host 义务集合；更早 host 的覆盖、保留金额和与 guest 的共享池关系仍 UNKNOWN。
不得用归档大小、2 MiB 传输上限、guest 配额、当前小文件、空闲空间或历史批次数推导缺失承诺。
原批准 next A 的 `128 MiB/32 + 全部更早 host 义务` 不能凭这些材料证明，原失败和判断保留。

本 A 明确请求 Owner 接受：仅本次 host capture 可在下述当前可用量条件通过后继续；更早历史 UNKNOWN
不单独阻断该动作。它们不变成零、已释放或已完整计入；不宣称已完成原完整 host admission。
共享文件系统、VM 镜像以及其它历史写入可能并发消耗空间；观察不构成预留，不能保证写入不遭遇 ENOSPC、
inode 用尽或 I/O 失败。停止时失败证据也可能不完整；不得因此新增日志文件、补采、重试或退款。

## 2. 唯一数字集合与停止条件

| 固定行（按此顺序） | session | bytes | inodes |
| --- | --- | ---: | ---: |
| 原 core 未释放 capture 承诺 | `lhqcore-20261003a` | 67108864 | 16 |
| 本次 core capture 承诺 | `lhqcore-20261005a` | 67108864 | 16 |

旧行来源为 next A 已固定的原五件与旧预算；新行来源为既有本次 64 MiB/16 限额。
两行全部另计于当前可用量，不减去旧文件已分配空间，合计固定 `134217728 B / 32 inodes`。
现有 prior-originals reader 仍须证明旧五件与本次 held anchor 同设备；不接受 caller 自选 rows、
额外虚构旧 grant、按批次猜金额或以其它设备剩余空间补足本设备。
更早 host 及后续记录整体保留 UNKNOWN，不声明此二行是全部历史集合；所有 guest 历史计费完全维持。
若已有材料或正常既有校验发现明确的新 host 预算来源、来源冲突、先前未知金额的可靠证明或同设备前提矛盾，
本固定口径不再足够，停止受影响范围按 R 处理；不得忽略已知矛盾，也不为此增加通用扫描或现场取证轮次。

## 3. 原窗口内的唯一当前观察

继续由 `verify_prior_originals` 的原 pre-marker 验证点调用一次受 deadline 包裹的 `fstatvfs(directory_fd)`。
该动作位于原 management requalification、prior raw 绑定之后，原六名 absence 和 O_EXCL marker 之前。
不在 origin 前取得当前值后沿用，不另起观察窗口、不刷新原 900 秒时限，不循环、重试或增加后台监视器。

调用前后仍检查同一 held fd/name 的完整目录身份、权限、UID/GID、nlink 和实际 writer 绑定；
身份必须等于本次 local-management-binding 的 anchor，不能只比较 dev/ino 或沿用历史资格。
所有阻塞调用沿用原双钟前后检查；BOOTTIME-first、MONOTONIC-second，晚返回即失败。
保存紧邻本次资源观察的 before/after 双钟，满足原 origin ≤ before ≤ after < 原 deadline。
`f_bavail`、`f_favail` 必须为非负整数，`f_frsize` 为正整数；不完整、调用失败或不可信值均停止。
恰计算 `bytes_available = f_bavail * f_frsize`，要求 `bytes_available >= 134217728` 且 `f_favail >= 32`。
通过只表示该时点普通 writer 可用量满足固定条件，不证明历史完整性、quota 剩余量或未来排他占有。
pre-marker 失败不消费；marker 后所有原停止、限额、保留和不可重试语义保持。

## 4. 同一 live 调用保留的条件记录

新增 `host_capacity_condition` 仅作为原 live 返回值的 sibling；原 `capture_accounting` 五键完全不变。
条件记录 schema 为 `local-hand-q2-core-host-capacity-condition/v1`，exact top-level keys 为：
`schema,scope,session_id,implementation,local_management_binding_sha256,prior_attempt_sha256,origins,observation,dev,known_commitments,capacity,earlier_host_obligations,complete_host_admission_proven,exclusive_reservation_proven,released_bytes,released_inodes`。

- `scope` 固定本 scope，`session_id` 固定 `lhqcore-20261005a`；`implementation` exact keys `commit,tree`，
  逐字绑定本次已核验 manifest 的准确 D；不得只写方案 A 或历史 D。
- 两个摘要分别取本次已复核的 local-management-binding 摘要、已验证 prior-attempt canonical/no-LF SHA-256。
- `origins` 恰含原四键 `host_boottime_origin_ns,host_monotonic_origin_ns,host_boottime_deadline_ns,host_monotonic_deadline_ns`，
  与传入原窗口及后续 marker 完全相同；`observation` 恰含 `before,after`，各恰含 `boottime_ns,monotonic_ns`。
- `dev` 等于 held anchor 的当前 dev；`known_commitments` 恰为第 2 节有序二行，每行 exact keys
  `session_id,bytes,inodes`，数值逐字固定，无 caller 可选择的条目。
- `capacity` exact keys `frsize,blocks_available,bytes_available,inodes_available,required_bytes,required_inodes`；
  前四项来自本次观察及上述乘法，后两项固定 `134217728,32`；不可填入历史采样值。
- `earlier_host_obligations` exact keys `coverage,bytes,inodes,shared_pool`，恰为
  `{"coverage":"UNKNOWN","bytes":null,"inodes":null,"shared_pool":"UNKNOWN"}`；null 不是数值零。
- `complete_host_admission_proven=false`、`exclusive_reservation_proven=false`、`released_bytes=0`、`released_inodes=0` 恒定。

实现必须在原调用栈保存该记录，从 prior 检查传到 delivery/finalizer 和最终 live 返回，不可丢弃后合成 PASS。
最终返回再次核对 schema、固定值、摘要、implementation、同一窗口和 identity 关联；不重新采样或刷新旧记录。
若观察失败，不形成成功条件记录；若后续失败，不以已通过的条件记录替代失败，不构造成功结果。
live 报告同时披露上述 UNKNOWN 和非排他语义；盘上 receipt 字面 COMPLETE 仍不是可重启验收证明。

## 5. 发行与核心执行边界

不增持久文件，不改六个固定 basename、receipt/capture manifest、wire schema、三个 field 文件或 guest 准入。
原 prior raw、旧 scope 两次静止检查、guest 历史池/额度、credential、身份、权限和 source validation 全部保留。
本次应用 64 MiB/16、逐角色/两流限额、分配采样、fsync/回读、900/800/750 秒及 final reserve 不变。
N2 必须对准确新 D 完成 source/installed/CI 和新条件负例；原同一 900 秒 caller 再核验私有原件、双构包、
当前身份及上述条件，满足准确 release 规则后才允许原一次 marker/request。不能只打开 dispatcher allowlist。
N3 仍为原 H01 真任务及结果收回 → Q4 RUNNING 后取消 → H11 原 ledger 恢复，不跳过原语义验收。
本 A 不提供 quota、整盘监控、通用历史账平台、新 runner、存储迁移或生产启用；其它支线继续暂停。
