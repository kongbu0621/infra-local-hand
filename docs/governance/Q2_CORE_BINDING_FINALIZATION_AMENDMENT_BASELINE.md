# Local Hand 核心输入绑定与终结证明修订：待批准文档基线

2026-10-04 +08:00；Authority：Owner；状态 **PROPOSED / Gate OPEN / REVISION REQUIRED**。
本件登记复核后已修正明确矛盾、但 capture 路线仍待收敛的准确方案 A；它不是 Owner B、bookkeeping-only CLOSED C、
implementation D、field package、marker、carrier request 或现场验收。

- Scope：`LH-Q2-CORE-BINDING-FINALIZATION-AMENDMENT-v1`。
- Gate R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- Direct pinned source：[program-repository-documentation-gate.md](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)。
- Direct source SHA-256：`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`；
  本轮 executor 已直接读取并核对。
- Documentation A：`4009e1b560dd873bc3d9b937be539f329b93371a`。
- A tree：`1739c8aabc1627c42555f95d7e0173ceb0ed4ff4`。
- A direct parent：`6a93e9d2c6bb03b860fa07139648e4feb3146b76`。
- Supersedes 未获批准的 proposal A `0a843218a1614b62c62e7dad8578748f911dad27`；原 proposal 和
  OPEN 登记保留在 Git history。本次只修正文档与复核结论，不补造 Owner 决定。
- Owner mandate、Owner-only decision authority、no exceptions 和禁止自动改变采用规则继续采用根
  [AGENTS.md](../../AGENTS.md) 的声明。

| A 中的准确文件 | Bytes | SHA-256 |
| --- | ---: | --- |
| [需求](../a2-execution/q2-core-binding-finalization-amendment/REQUIREMENTS.md) | 103363 | `1b504035aa62058c14a85083e61c1aeca3581512fcceeca503a42996cd636cae` |
| [架构](../a2-execution/q2-core-binding-finalization-amendment/ARCHITECTURE.md) | 24181 | `71f123a7f3add387a287bd0bd0d09350a68172c9c4707d27cfdd23ea055f0468` |
| [实施计划](../a2-execution/q2-core-binding-finalization-amendment/IMPLEMENTATION_PLAN.md) | 22655 | `3639e789b6c78543f782dcaa5238c87e4746bd9b4374f47daa6f859ba1e26707` |

终审覆盖 source-horizon 与 placement、package/HELLO/admission digest、receipt/attestation 状态机、
H01/Q4/H11 顺序、capture 全过程资源账、loaded ext4 与 source-tree 机械绑定、held parent/mount/device
交叉绑定、filesystem-static projection 和失败残留。后续三路复核发现两个确定 P1 文档矛盾及
未成立的宿主技术依赖，撤回先前“zero P0/P1、等待整体批准”的就绪表述。两个确定矛盾已修正并经
定向复核；宿主路线仍未闭合。本次没有新增 runtime/test 实现或执行现场任务。

## 本轮复核结论与最小后续工作

| 项目 | 结论及处置 |
| --- | --- |
| sudo predicate | 已修正：原配置是 `(ALL)`，并非 `(ALL:ALL)`；helper 无显式 RunAsGroups 归一化为 `[]`，`!authenticate` 归一化为 NOPASSWD。host ALL 来自已绑定配置，不能从已按 host 筛选的 `-ll` 输出反推。没有修改 guest 权限。 |
| STOP receipt | 已修正：create 前被截止则不创建；O_EXCL 后失败或晚返保留 partial/full，不补写、删除或创建 attestation。partial/invalid 不生成 derived，strict-valid STOP 只能是 STOP；deadline 未放宽。 |
| 历史行来源 | 已统一：固定 accounting producer 只验证 projection，修订 transform 生成 enriched rows。 |
| finite attestation | 方案可保持有限、无自摘要循环；但原 A 已采用调用端终结观察，未要求 receipt 自证未来或 restart COMPLETE，不能把此新增设计描述成 H01 的必然前置阻塞。 |
| host capture 路线 | **未解决**：强制 runtime IKCONFIG、loaded-ext4 可信测量、raw-device 读取和完整分配模型，但没有实际宿主具备这些能力的证据；批准本 A 不能使它们成立。 |

sudo 语义依据为上游 [display.c](https://github.com/sudo-project/sudo/blob/main/plugins/sudoers/display.c)
的 `display_cmndspec_long`。普通管理进程对 root 所有模块使用 `O_NOATIME` 也不能由“可读”推出可用：
[Linux open(2)](https://man7.org/linux/man-pages/man2/open.2.html)要求所有者身份或相应 `CAP_FOWNER`。
这里没有断言真实宿主必然缺少权限；准确状态是未证实。

已复用而无需重采的历史材料：

- [旧 host/control parent 观察](../a2-execution/evidence/q2-local-source-field-20260928/diagnostic-rerun2-independent-validation.json)：
  两者当时为 ext4/rw,relatime，但 `allocation_peak_proven=false`。
- [既有文件系统复核](../a2-execution/Q2_POST_SOURCE_ADMISSION_PLAN.md)：旧 parent 为 12 KiB、EXTENTS+INDEX，
  不是当前 core anchor 的全过程容量证明。
- [FS work order](../a2-execution/Q2_FS_QUALIFICATION_WORK_ORDER_20261002.md)：普通身份 raw-device read/
  O_NOATIME 能力仍 UNKNOWN。
- [core 部分实现复核](../a2-execution/Q2_CORE_ACCEPTANCE_DELIVERY_IMPLEMENTATION_REVIEW.md)：本地 anchor
  的文件、key、依赖和 cwd 绑定已复核，但没有 host capture 硬配额或固定容量存储证明。

下一步仅需能访问真实管理机既有材料的执行端补齐三个事实：准确 core capture anchor 对应哪个宿主
mount；该目录是否已有硬配额或固定容量存储及其真实权限/限额；该机制对七对象、parent 增长与额外
inode/瞬时分配的计费范围。没有记录就报告 UNKNOWN，不以 guest project quota、云端容器或假数据代替。
本轮不增加 SSH、marker、任务、安装、清理或自动重试，也不要求重采已有 K4/R3。
在这些事实基础上选择可执行的 capture 路线，保持 64 MiB/16 inode 与 52 MiB 流上限；不得只删除
物理分配约束，也不把未成立的完整内核证明项目默认为核心交付工作。

## 与原 core closure 的关系

原 `LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1` 在 A
`74366b3fe41e675b1aa2d677228714a5606c275c`、Owner B event
`LH-Q2-CORE-ACCEPTANCE-DELIVERY-CLOSURE-20261003-01` 和独立 C
`a8dd077392ebb656770c8f94ca3b051e93fc296d` 下仍是历史准确 CLOSED 记录。其部分 D
`520f77f578b90d31870517e33e29bee42918f3c0` 已准确记录为不可 release；最新主线
`bd02fbd094a76767c21fbc8a96502c5b894df3c2` 修复 Linux-only collection 与 quota receipt race，
但没有生成 field package、解除 dispatcher release gate 或消费现场批次。

本修订不改写原 A/B/C，不追认部分 D，也不以主线 CI 成功代替现场验收。它只处理部分 D 后暴露的
material package/current-guest binding 冲突、有限终结/restart 合同选择、source-horizon 缺口，以及未证明的
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

capture 路线收敛且文档复核闭合后，才提出可 review 的准确 A。若 Owner 批准该准确 A，先保留准确 B，
再独立提交 bookkeeping-only CLOSED C。新 D 必须以 C
为 direct parent，完成 source/test、independent review、proof/model、双 package build/parse 与 release
digest。origin 前 offline source/model/package-template 门及 origin 后 current host kernel/ext4/capture、
package/release 与其它 pre-marker local 门全 PASS 后，才可创建 marker、发唯一 carrier request；随后同一
carrier 内的 HELLO/package/policy/capacity/live admission 全 PASS 后，才可创建首个 guest mutation/H01
intent，并依次条件执行 H01→Q4→H11。任何前项非 semantic PASS 都不创建下一 intent。

namespace/watchdog 继续暂停并排除；production `E3_SUPERVISION_UNVERIFIED` 保持。不授权 production
enable/cutover、E4–E6、host sudo/配置改变、第二 request、旧批次重放、UNKNOWN 提升成功或公开 raw
machine evidence。

## 当前决定状态

本轮不请求 Owner 批准尚未落地的 capture 路线；原批准建议已撤回，Gate 保持 OPEN。
仓库 AGENTS.md 与固定 R 要求 material contract 变化先有准确 A/B/C，再推进受影响实现；
它们不允许以“已推送”推定 Owner B。只有 Owner 的准确回复及稳定 event/reference 可以形成 B；
之后还须单独提交只含关闭登记的 C，且不得与 D squash。任何 material premise、candidate、artifact、
object、budget、deadline、management entry、capture model 或 execution rule 变化继续触发 R 的 reopen
规则。
