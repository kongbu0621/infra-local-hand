# Local Hand 核心验收交付：待批准文档基线

2026-10-03 +08:00；Authority：Owner；状态 **PROPOSED / Gate OPEN / AWAITING OWNER**。
本件只登记已提交并通过只读终审的准确方案 A；它不是 Owner B、bookkeeping-only CLOSED C、
implementation D、package、carrier request 或现场验收。

- Scope：`LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1`。
- Gate R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- Direct pinned source：[program-repository-documentation-gate.md](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)。
- Direct source SHA-256：`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`；
  本轮 executor 已直接读取并核对。
- Documentation A：`74366b3fe41e675b1aa2d677228714a5606c275c`。
- A tree：`7df4fd0c876df13af4ec73c6f910272a72d7ea4d`。
- A direct parent：核心 candidate `4b6e4a7c403362358192086b88679e1326dcb2e1`。
- Owner mandate、Owner-only decision authority、no exceptions 和禁止自动改变采用规则继续采用根
  [AGENTS.md](../../AGENTS.md) 的声明。

| A 中的准确文件 | Bytes | SHA-256 |
| --- | ---: | --- |
| [现场输入只读复核](../a2-execution/Q2_CORE_LIVE_INPUT_REVIEW_20261003.md) | 6203 | `39853b72755e4737b5329856691e1f616cfd2ffdf403d1c06cbeccff89686f1c` |
| [需求](../a2-execution/q2-core-acceptance-delivery/REQUIREMENTS.md) | 111223 | `8ef192452302ae2c2c55c38dd6889a0a62265404f4baa823be097f0a2524ce76` |
| [架构](../a2-execution/q2-core-acceptance-delivery/ARCHITECTURE.md) | 30956 | `7599870a39f04a68a84992dbc2f3035ba202963fc1cc688914f9b5fa596b54ab` |
| [实施计划](../a2-execution/q2-core-acceptance-delivery/IMPLEMENTATION_PLAN.md) | 26931 | `dd128597f90cfdf38d4a9f716fa53fd12acbb12cbc86c261f3f9c760477938c1` |
| [source projection](../a2-execution/artifacts/q2-core-acceptance-20261003/.local-hand-source-projection.json) | 11811 | `55f555fc225edca943b8c86cee8119c4878f5ec1e9503a084ba7a560cf2c991d` |
| [artifact receipt](../a2-execution/artifacts/q2-core-acceptance-20261003/artifact-receipt.json) | 1294 | `f34baa40ceb3bbce99d02cfef1c8748990d9e405df7fe56d14c15cc8e49f3e5e` |

## 候选与已完成的离线证据

A 固定产品 candidate `4b6e4a7c403362358192086b88679e1326dcb2e1`、tree
`4d4349580c9f4b67cc26f601126849c2bc8d76a4`、direct parent
`607100a57206f7dc7cfcbd6cae8507cfa599b813`。它包含正常链、取消和 H11 same-ledger recovery
入口；production `tools/local_hand_jobs/runner.py` 的 `E3_SUPERVISION_UNVERIFIED` 限制保持。

唯一 wheel 是 `infra_local_hand-0.2.0a1-py3-none-any.whl`，288375 bytes，SHA-256
`ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9`，canonical payload
digest `b4d094a9f70c308c63870c9fbf273b6b0646ad211d6f61a79901f52e67cf2e23`，62 members；两次
独立 build byte-identical。wheel 保留在 workspace 的 ignored/untracked `dist/`，不属于 A 的 Git
bytes；C 后 D/package 只能 exact-hash reuse 或重建出相同 bytes，缺失或不等即 `NOT_ISSUED`，不得替代。
projection 的 89 个 path/blob/mode 已逐项对照 candidate，且不含 namespace/watchdog 路径。

candidate 已有 targeted `269 passed / 1 skipped` 和 full source `3910 passed / 91 skipped / 0 failed`
结果；installed verification 为 `PASS`、94 checks/292 commands，但准确标记
`fixture_only=true`、`physical_node_tested=false`。其 raw report 为 364843 bytes、SHA-256
`54ec1ec834511623b3817dc28c11ae365cef8c322125c3978a897a3611f7d479`，未纳入 A artifact set，
也不能替代本范围真实 guest 运行。

## 实际 guest、唯一新前提与固定对象

2026-10-03 的只读管理入口复核确认目标是实际 QEMU guest：PID 1 为 systemd 255、cgroup v2，
`q2job` 为 UID/GID 1100，ordinary user manager active，固定 parent slices 存在，目标 ext4 启用
project quota。当前工具容器 PID 1 非 systemd 只描述工具环境，不能用于判定宿主或 guest 不支持监督。
管理入口脚本、启动脚本、known-hosts、public identity 和 cloud-init user-data 的 SHA-256 依次为
`aed91e80483d4df103f95c1d4cd5bf9bd18720f4dc51720702c329c937f93c63`、
`1acc8c4cb09bc5b14c32adc35e87d8500098cbf3968d53f406269e96df30f96a`、
`d1025c074e532f29534fcab1d10ec1bc2f38d2137173c74d0bc921bbab420bbd`、
`e67e15549d3e8586af936108f666612841d31612705236dd8ce265a3da18b25c` 和
`5b81deabefb7bc70aa6ee13b72053d65556fac1e400b5a37919ca1f90e4b6523`；private locator、
private key 和 raw machine evidence 不进入 Public repository。

A 的**唯一新治理前提**是：这个既有隔离 fixture 的 current source/policy 含
`q1admin ALL=(ALL) NOPASSWD:ALL`。A/D 只允许固定 management entry、固定 argv 和一次 request，
但该既有 policy 本身不是 exact-command/one-shot 的技术 containment，不能技术排除另一登录、并发 sudo
或重复调用。Owner 若批准，是接受在这项明确限制下使用当前隔离 fixture；不是授予通用 sudo、系统配置
变更或生产权限。source/policy/隔离事实任一漂移都必须停止且不得重试。

A 固定 logical namespace `lhqcore-20261003a`、installation
`local-hand-core-acceptance-20261003a`、staging `.local-hand-core-acceptance-20261003a.staging`、
install UUID `2ba06c6f-d3e5-4e36-a41f-d5991cdd7232`，以及以下三项且只能按此顺序条件存在：

| 顺序 | Case / basename | Preparation / operation | Controller / projects |
| ---: | --- | --- | --- |
| 1 | `H01_NORMAL` / `c01-h01-normal` | `lhqc01h01normal` / `b6638120-ed28-4ed1-b603-a153fab1c93d` | `lhqcore20261003a-c01` / `12101..12107` |
| 2 | `Q4_HELPER_RUNNING_CANCEL_SUBSET` / `c02-q4-cancel` | `lhqc02q4cancel` / `ade1b42f-f03d-48dc-b690-e588b44289f6` | `lhqcore20261003a-c02` / `12108..12114` |
| 3 | `H11_SAME_LEDGER_RECOVERY` / `c03-h11-recovery` | `lhqc03h11recovery` / `4b035797-229a-4cdc-8eca-8195869b7ac9` | `lhqcore20261003a-c03` / `12115..12121` |

H01 保留正常入口的 empty-ledger gate。H11 只附着原 ledger 和原 request/execution/unit 身份，收回
recovery observation/verdict 与仍持有的外层控制证据；不得重新 submit/start 业务，不得读取、hash、
复制或封装原业务 result bytes，不得重建 unit、生成新 grant 或延长任何 deadline。H01/Q4/H11 的
required member 闭包分别为 32/21/26，phase source-artifact 闭包分别为 5/5/8。

## 一次性现场边界与预算

- 三 case 串行；只有 H01 semantic PASS 才可形成 Q4 intent，只有 Q4 semantic PASS 才可形成 H11
  intent。任何 STOP/BLOCKED/UNKNOWN/缺证据都不越过当前门。
- 每 case physical 为 36 MiB/2944 inodes，三项 108 MiB/8832；shared physical 为
  64 MiB/4096，carrier/audit 为 8 MiB/512，总 physical 为 **180 MiB/13440 inodes**。
- 每 case admission 为 68 MiB/3968，三项 204 MiB/11904；加相同 shared/audit 后总 admission 为
  **276 MiB（289406976 B）/16512 inodes**。management headroom 只用于准入，不是可写额度。
- 三 case CPU 为 1290 CPU-s，carrier 为 800 CPU-s，总计 **2090 CPU-s**；串行 peak 为
  **2624 MiB（2751463424 B）/1160 pids**。
- carrier input 最多 32 MiB，stdout+stderr 最多 60 MiB；本地 capture 最多 64 MiB/16 inodes。
  固定上界另含 15 job units、6 controllers、5 quota-query units、15 dynamic quota units 和
  16 native children。
- host carrier deadline 900 s、remote unit 800 s、guest cap 750 s；clock margin 2 s、local final
  reserve 15 s、remote final reserve 45 s、case gate 315 s、preparation 150 s、owner 120 s，
  所有层只取既有更早 deadline，未用时间不转移也不刷新。
- 最多一次 held-anchor `O_EXCL` consumption marker、最多一次 carrier request。marker 创建即消费；
  不删除、不退款、不 reconnect、不 retry，也不改名绕过。2026-10-03 的只读观察不是 request；历史
  `20261001e` 已消费批次不得重放。

当前计数准确为 marker 0、carrier request 0、H01/Q4/H11 run 0；没有 Local Hand 任务被受理或受监督
执行，没有退出确认、业务结果或真实证据被收回。A 和本登记不改变这些计数。C 后须先实现 D、完成
静态和现场 admission、冻结准确 package basename/bytes/SHA/member manifest，之后才可能条件发出唯一
request。namespace/watchdog 继续暂停；不授权其实现/fixture/预算，不授权移除 production
`E3_SUPERVISION_UNVERIFIED`、生产 cutover、E4–E6、系统配置变更、旧批次重放或第二 request。

## 待 Owner 决定的准确文本

若 Owner 决定批准，可准确回复：

> 按原 R 10d2a5c827964989f41ca6e8eeac3d44de6d0f04，批准 A 74366b3fe41e675b1aa2d677228714a5606c275c 的 LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1；接受 A 中披露的唯一新治理前提、固定 candidate/wheel/harness/对象、physical 180 MiB/13440、admission 276 MiB/16512、2090 CPU-s、peak 2624 MiB/1160 pids、32 MiB input/60 MiB output/64 MiB/16-inode capture 预算及 900/800/750 秒外层时限；授权最多一次 O_EXCL marker、最多一次 carrier request、不重连不重试，并继续建立独立 bookkeeping-only CLOSED C，再按 A 实施 D、验证、冻结 package，且仅在全部门通过后条件执行 H01_NORMAL→Q4_HELPER_RUNNING_CANCEL_SUBSET→H11_SAME_LEDGER_RECOVERY。H11 只使用原 ledger 和原 unit 身份，不重启业务、不延长 deadline；namespace/watchdog 保持暂停，production E3_SUPERVISION_UNVERIFIED 保持。不授权复用旧批次、第二 request、系统配置变更、生产启用或把 UNKNOWN 提升为成功。

上句是待决定文本，**不是已经发生的 Owner B**。必须先保留准确 B 及其稳定 event/ref，再独立提交
只含关闭登记的 C；D 必须直接 descend from C，且不得与 C squash。任何 material premise、candidate、
artifact、object、budget、deadline、management entry 或 execution rule 变化继续触发 R 的 reopen 规则。
