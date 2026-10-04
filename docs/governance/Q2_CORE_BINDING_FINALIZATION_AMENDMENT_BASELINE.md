# Local Hand 核心输入绑定与结果收回：最小修订基线

2026-10-04 +08:00；Authority：Owner；状态 **PROPOSED / Gate OPEN / AWAITING EXACT OWNER DECISION**。
这份登记固定可审阅的最小方案 A；不是 Owner B、CLOSED C、实现 D 或现场执行记录。

- Scope：`LH-Q2-CORE-BINDING-FINALIZATION-AMENDMENT-v1`。
- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- [直接固定规则](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)；
  已读取，SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- Documentation A：`0bdb49cae5586be60a7ba31d4a8e8367854d1e8c`。
- A tree：`ee15aa4fa26fd2e87b40f6fad72828265e5cf9bc`；direct parent：`c83dad17040e9f8cec148303083c47311f8b7fb9`。
- 取代未批准 `4009e1b560dd873bc3d9b937be539f329b93371a` 和更早 proposal；其历史保留，不补造 B。
- Owner-only authority、mandate、no exceptions 与变更规则沿用根 [AGENTS.md](../../AGENTS.md)。

| 准确文件 | Bytes | SHA-256 |
| --- | ---: | --- |
| [REQUIREMENTS.md](../a2-execution/q2-core-binding-finalization-amendment/REQUIREMENTS.md) | 72756 | `e6b29c45c550f2ae8b3eaa91baad8d1382851dec6a69e2f807cce9233b14cdb1` |
| [ARCHITECTURE.md](../a2-execution/q2-core-binding-finalization-amendment/ARCHITECTURE.md) | 11458 | `7782e2fb89a28052978d3ce205278906b92752e3ba1add9cd634c0e7c0f92c96` |
| [IMPLEMENTATION_PLAN.md](../a2-execution/q2-core-binding-finalization-amendment/IMPLEMENTATION_PLAN.md) | 13336 | `52faaf002d9b5b9d88aef0b6f568e8ed56d2aa49eb0ea41e7eeb85d2d0b64cce` |

## 已完成的收敛与复核

[本地回传](../a2-execution/Q2_CORE_LOCAL_HANDOFF_RESULT_20261004.md)已经收到并保留；准确 anchor
是历史 4 KiB control parent，与另一个 12 KiB parent 不同；它与 VM 镜像共用 ext4。
没有找到已证明的专属 host hard-limit 机制，不能推断机制不存在或历史观察等于当前资格。
不再重复索取 R3/K4、探测内核或读 VM 镜像。

本 A 撤回第七个 attestation 文件、local restart COMPLETE、loaded-ext4/IKCONFIG 测量、
raw-device/superblock 资格化、内核 Git proof archive 与完整 allocator 模型。
恢复六文件、receipt/capture v1、原 live caller 完成最终 fsync/回读/时限检查的路线。
保留 approved-input §3 的逐字原文、已修正的 sudo predicate、完整 source horizon 和 package/HELLO JIT 绑定。

**这不是原资源保证完全不变：**host capture 采用应用写入限制与实际六文件分配的多点观测验收；
64 MiB/16 不是共享宿主文件系统包含 metadata/journal/未观测瞬时分配的全程物理硬限额。
两流合计 52 MiB；六角色逻辑上限合计最多 55132160 B；固定最多六文件；
每次 write/fsync 后真实 `st_blocks*512` 的合计与最大观测值都检查，超限停止，但不谎称从未超限。
live 返回明确 `full_filesystem_peak_proven=false`。原 guest 资源限额与安全/身份校验不变。

两路交叉复核已处理：frame 58716144 B 与 carrier 62914560 B 分开、后续失败不抹掉 H01 已证实真值、
absence 在最终 release 检查之后、正值 short-write 可继续但无法完成的写入保留残留。
方案不再要求新的内核/存储研究。本轮只变更文档；没有修改 runtime/test 或把审阅写成现场 PASS。

## 必须明确的决定

Owner B 须对本准确 A 接受：

1. 唯一 carrier 内 post-entry JIT 自观察及其不能追溯证明原 entry/loaded image 的限制。
2. §3 source-horizon 完整性及本批次终结前不另签发 Q2 batch。
3. 受限 management anchor/六文件的可信单写者窗口及无法排除 change-and-revert 的剩余信任。
4. 上述 host capture **资源保证变化**；不宣称全宿主文件系统的全过程物理硬上限。

凭据、PID/UID/GID、路径/摘要、O_EXCL、单次 carrier、真实 wait/双 EOF、fsync/同 inode 回读、
原 deadline、失败保留、无清理和无自动重试均不放宽。禁止修改命名或诊断去隐藏真实功能。

准确决定可表述为：

> 按原 R，批准 A `0bdb49cae5586be60a7ba31d4a8e8367854d1e8c` 的核心最小修订，接受其中三项治理前提及 host capture 改为应用限额和文件分配观测验收、不再承诺共享文件系统全过程物理硬上限；关闭该范围 Gate，先独立提交 C，再执行 D1–D4 和条件单次 F1。只推进核心，暂停支线。

上段只是待 Owner 决定的文本，不是已发生的 B。当前仍 OPEN。
需要这次决定的来源是仓库 AGENTS.md 与固定 R 对 material contract 变化的准确 A/B/C 顺序要求，
不是平台自动检查或网络安全资格要求。

## 下一步直接交付核心

准确 B 后保留原文与 event/reference，独立提交仅 bookkeeping 的 C；首个 D 以 C 为 direct parent。
按[实施计划](../a2-execution/q2-core-binding-finalization-amendment/IMPLEMENTATION_PLAN.md)补齐：
输入/JIT 准入，dispatcher 八组真实效果，六文件 finalizer，必要验证与完整 package/release freeze。
云端完成可做的仓库实现和测试；本地只负责私有源/host binding/独立 package 复算和唯一现场运行。
本批 create-only candidate placement 按原 A 执行；复用现有 SSH/机器准备，不重跑历史安装或覆盖旧现场。
现场严格 H01 正常执行/结果收回 → Q4 运行中取消 → H11 自己原任务恢复；前项不 PASS 不进入后项。

原核心 A `74366b3fe41e675b1aa2d677228714a5606c275c`、B event
`LH-Q2-CORE-ACCEPTANCE-DELIVERY-CLOSURE-20261003-01`、C
`a8dd077392ebb656770c8f94ca3b051e93fc296d` 保持历史准确；部分 D
`520f77f578b90d31870517e33e29bee42918f3c0` 仍不可 release。
本批 package=null / NOT_ISSUED；marker/carrier/H01/Q4/H11/真实任务/退出确认/结果收回仍未发生。
18 项既有 core-entry 回归及 1e1ecff 的 CI 成功不代替这些功能事实。

namespace/watchdog、旧版扩建、专用存储建设、生产/E4–E6/NAS 支线继续暂停；
production `E3_SUPERVISION_UNVERIFIED` 不变。不得重放旧批次、重连重试、host sudo/系统变更或公开私有 raw。
