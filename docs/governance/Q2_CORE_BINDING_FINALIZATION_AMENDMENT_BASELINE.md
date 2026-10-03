# Local Hand 核心输入绑定与终结证明修订：待批准文档基线

2026-10-04 +08:00；Authority：Owner；状态 **PROPOSED / Gate OPEN / AWAITING OWNER**。
本件只登记已提交并通过三路只读终审的准确方案 A；它不是 Owner B、bookkeeping-only CLOSED C、
implementation D、field package、marker、carrier request 或现场验收。

- Scope：`LH-Q2-CORE-BINDING-FINALIZATION-AMENDMENT-v1`。
- Gate R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- Direct pinned source：[program-repository-documentation-gate.md](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)。
- Direct source SHA-256：`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`；
  本轮 executor 已直接读取并核对。
- Documentation A：`0a843218a1614b62c62e7dad8578748f911dad27`。
- A tree：`58e1503d0c2f3cdfa8a44cf75b48c9f626f3c9a2`。
- A direct parent：最新已同步主线 `bd02fbd094a76767c21fbc8a96502c5b894df3c2`。
- Owner mandate、Owner-only decision authority、no exceptions 和禁止自动改变采用规则继续采用根
  [AGENTS.md](../../AGENTS.md) 的声明。

| A 中的准确文件 | Bytes | SHA-256 |
| --- | ---: | --- |
| [需求](../a2-execution/q2-core-binding-finalization-amendment/REQUIREMENTS.md) | 101928 | `1b9e18b3745add8535ccf39a75513164d20ac6d5fa1fe8ee6acc76cd15ecf1d6` |
| [架构](../a2-execution/q2-core-binding-finalization-amendment/ARCHITECTURE.md) | 23847 | `3f1745815e6f9982fff764a244ec8e08b198f6ed4e50b6c8c8222f135aa00cb9` |
| [实施计划](../a2-execution/q2-core-binding-finalization-amendment/IMPLEMENTATION_PLAN.md) | 21909 | `e797576a337b2ab5c0c1939905b0fe38a6b9b44f4f9ee4772399696f4813fc40` |

终审覆盖 source-horizon 与 placement、package/HELLO/admission digest、receipt/attestation 状态机、
H01/Q4/H11 顺序、capture 全过程资源账、loaded ext4 与 source-tree 机械绑定、held parent/mount/device
交叉绑定、filesystem-static projection 和失败残留。三路最终结论均为 zero P0/P1；这只是 A 的
文档一致性结果，不是实现或现场 PASS。

## 与原 core closure 的关系

原 `LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1` 在 A
`74366b3fe41e675b1aa2d677228714a5606c275c`、Owner B event
`LH-Q2-CORE-ACCEPTANCE-DELIVERY-CLOSURE-20261003-01` 和独立 C
`a8dd077392ebb656770c8f94ca3b051e93fc296d` 下仍是历史准确 CLOSED 记录。其部分 D
`520f77f578b90d31870517e33e29bee42918f3c0` 已准确记录为不可 release；最新主线
`bd02fbd094a76767c21fbc8a96502c5b894df3c2` 修复 Linux-only collection 与 quota receipt race，
但没有生成 field package、解除 dispatcher release gate 或消费现场批次。

本修订不改写原 A/B/C，不追认部分 D，也不以主线 CI 成功代替现场验收。它只处理部分 D 后暴露的
material package/current-guest binding 冲突、receipt 自证循环、source-horizon 缺口，以及未证明的
host capture filesystem/全过程 allocation bound。因为这些是 material contract changes，原 core B/C
不能自动覆盖；必须保持 R → 本准确 A → 新 Owner B → 独立 bookkeeping-only CLOSED C → 新集成 D。

## 三项且仅三项新增治理前提

Owner B 必须逐项接受，不能由实现或测试推定：

1. **post-entry JIT guest self-observation**：唯一 carrier 已进入后才允许以固定 HELLO 和各至多一次的
   `sudo -n -ll -U q1admin` / `sshd -T` helper 观察 current guest；它们不能回溯证明 entry 时 inode、
   loaded image、配置或无 change-and-revert，也不是第二 request/connection/unit。
2. **governed source-horizon completeness**：A 列出的 2026-09-27 source、五个 normal batch、
   `20261001e` 与三项 later-nonissuance 是既有 Q2 obligation/field batch 的完整治理集合，且本批次
   终结前不另发 Q2 batch；反证在 marker 前为 `NOT_ISSUED`、marker 后为 `STOP_AND_RETAIN`。
3. **local trusted single-writer and stable capture-kernel window**：从 origin 前最后 offline gate 到 live
   final sample，没有同 credential/equivalent DAC writer 或不可回溯 change-and-revert；kernel/module、
   mount/ext4 allocator、ACL/xattr/project/quota/LSM 和 model inputs 保持 A 规定的稳定性。这不授予 host
   sudo、系统变更、服务锁或第二 writer。

除这三项外没有新增治理前提。A 另设 fail-closed 技术门，不把它们冒充技术消除上述剩余信任。

## 固定候选、对象、预算与收紧项

- 产品 candidate 固定 `4b6e4a7c403362358192086b88679e1326dcb2e1`、tree
  `4d4349580c9f4b67cc26f601126849c2bc8d76a4`、direct parent
  `607100a57206f7dc7cfcbd6cae8507cfa599b813`。
- wheel 仍是 `infra_local_hand-0.2.0a1-py3-none-any.whl`，288375 bytes，SHA-256
  `ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9`，canonical payload
  digest `b4d094a9f70c308c63870c9fbf273b6b0646ad211d6f61a79901f52e67cf2e23`；原 harness、logical
  namespace、installation/staging、三个 case、21 roots、units 与 H01→Q4→H11 顺序不变。
- 原总预算保持：physical 188743680 B/13440、admission 289406976 B/16512、2090 CPU-s、peak
  2751463424 B/1160 pids、32 MiB carrier input、60 MiB outer output refusal、64 MiB/16-inode host
  capture；host/remote/guest 外层时限仍为 900/800/750 秒，所有 reserve/gate 更早 deadline 不刷新。
- 60 MiB 只保留 outer refusal；本修订把实际 stdout+stderr logical capture 收紧到 52 MiB
  （54525952 B）。七个固定 local basename 的 conservative peak 为 66363390 B/14 inodes，距
  67108864 B/16 尚余 745474 B/2；未用 role cap 不转移。
- 最多一次 create-only `O_EXCL` marker、最多一次 carrier request、一次 BIND/package/EOF；不 reconnect、
  retry、refund、rename bypass 或复用旧批次。marker 完整持久化前不得接触 current guest。
- H01 保留 empty-ledger gate。Q4 只在 helper 已真实 RUNNING 后 cancel 恰一次。H11 只用原 ledger、
  request/execution/unit/grant/deadline恢复 observation/control，不 submit/start、重启业务、重读结果、
  新建 grant/unit 或延长 deadline。

## 新的 fail-closed 技术闭包

- host 在 origin 前离线验证一个 D-pinned、host-only、read-only、最多 32 MiB 的 canonical Git SHA-1
  object-proof archive；它机械证明 kernel source commit→root tree→manifest path→blob/raw SHA-256，
  不进入 field package、guest 或 capture，也不扩大 carrier/field/capture预算。
- origin 后从 held current source 验证 runtime kernel config、磁盘 ext4 image，以及能证明 kernel 实际
  admit image SHA 的 trusted loaded-module measurement；缺 measurement、built-in、disk/loaded/source-row
  不一致或 UNKNOWN 均为 `NOT_ISSUED`，不得请求 sudo 或改配置补齐。
- held parent `STATX_MNT_ID`、mountinfo、fstatfs、block-device rdev、UUID/superblock、完整 reviewed model
  必须闭合。完整 initial superblock raw SHA 只作初始 qualification；每阶段重建 exact
  filesystem-static geometry/feature-mask projection，并保留 statx mask/attributes。正常可变 counters、
  wtime/journal/checksum 只有在 D review 证明不影响 profile allocation bound 时才可排除。
- receipt v2 只持久化 `COMPLETE_PENDING_ATTESTATION`；同 deadline 内再持久化并回读 attestation，最后
  live sample/resource closure 才能生成非持久 `COMPLETE`。restart 最多
  `RECEIPT_COMPLETE_ATTESTED` / timing-resource `UNPROVEN`，不得提升成功。
- package、marker、session、capture manifest、receipt/attestation 和 derived state 全部使用 A 的 exact
  version/key/digest chain。缺失、old-v1、partial、extra key、identity drift 或晚返都 fail closed 并保留。

这些要求尚无实现 D、proof archive、trusted loaded measurement、完整 reviewed model、冻结 package 或
field qualification 结果。它们是当前准确准备缺项，不得被 source test、fake harness、CI 或批准文字替代。

## 当前事实与后续门

截至本登记：package 为 `null` / issuance `NOT_ISSUED`；marker 0、carrier request 0、H01/Q4/H11 run 0、
真实任务 0、退出确认 0、结果 0、现场证据 0。没有 Local Hand 任务被受理或受监督执行，没有结果与证据
被收回。A 与本 OPEN 登记不改变这些计数，也不消费原未签发的一次性批次。

若 Owner 批准准确 A，下一步只能先保留准确 B，再独立提交 bookkeeping-only CLOSED C。新 D 必须以 C
为 direct parent，完成 source/test、independent review、proof/model、双 package build/parse 与 release
digest。origin 前 offline source/model/package-template 门及 origin 后 current host kernel/ext4/capture、
package/release 与其它 pre-marker local 门全 PASS 后，才可创建 marker、发唯一 carrier request；随后同一
carrier 内的 HELLO/package/policy/capacity/live admission 全 PASS 后，才可创建首个 guest mutation/H01
intent，并依次条件执行 H01→Q4→H11。任何前项非 semantic PASS 都不创建下一 intent。

namespace/watchdog 继续暂停并排除；production `E3_SUPERVISION_UNVERIFIED` 保持。不授权 production
enable/cutover、E4–E6、host sudo/配置改变、第二 request、旧批次重放、UNKNOWN 提升成功或公开 raw
machine evidence。

## 待 Owner 决定的准确文本

若 Owner 决定批准，可准确回复：

> 按原 R 10d2a5c827964989f41ca6e8eeac3d44de6d0f04，批准 A 0a843218a1614b62c62e7dad8578748f911dad27 的 LH-Q2-CORE-BINDING-FINALIZATION-AMENDMENT-v1；接受 A 披露的三项且仅三项新增治理前提（post-entry JIT guest self-observation、governed source-horizon completeness、local trusted single-writer and stable capture-kernel window），接受原固定 candidate/wheel/harness/对象、physical 180 MiB/13440、admission 276 MiB/16512、2090 CPU-s、peak 2624 MiB/1160 pids、32 MiB input/60 MiB outer output/64 MiB/16-inode capture 预算及 900/800/750 秒外层时限，并接受本修订收紧的 52 MiB 实际 stdout+stderr capture、host-only且不进入carrier/physical/admission/capture预算的最多32 MiB kernel-source object-proof dependency、trusted loaded-ext4 measurement、filesystem-static allocation 与 receipt-v2/attestation/restart 降级合同；继续建立独立 bookkeeping-only CLOSED C，并仅按 A 实施、验证和冻结新的集成 D/package。origin 前 offline source/model/package-template 门及 origin 后 current host kernel/ext4/capture、package/release 和其它 pre-marker local 门全 PASS 后，才允许消费原未签发批次的最多一次 O_EXCL marker 并发一次 carrier request；随后同一 carrier 内的 HELLO/package/policy/capacity/live admission 全 PASS 后，才允许首个 guest mutation/H01 intent，并按 H01_NORMAL→Q4_HELPER_RUNNING_CANCEL_SUBSET→H11_SAME_LEDGER_RECOVERY 条件执行。H11 只使用原 ledger/request/execution/unit/grant/deadline，不重启业务、不重读结果、不新建 grant/unit、不延长 deadline。namespace/watchdog 保持暂停，production E3_SUPERVISION_UNVERIFIED 保持。不授权旧批次复用、第二 request、重连重试、host sudo/系统配置变更、生产启用或把 UNKNOWN/restart attestation 提升为成功。

上句是待决定文本，**不是已经发生的 Owner B**。只有 Owner 的准确回复及稳定 event/reference 可以形成
B；之后还须单独提交只含关闭登记的 C，且不得与 D squash。任何 material premise、candidate、artifact、
object、budget、deadline、management entry、capture model 或 execution rule 变化继续触发 R 的 reopen
规则。
