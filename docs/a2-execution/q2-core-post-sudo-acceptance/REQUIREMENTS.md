# sudo 修复后核心单次验收：需求

- Authority：Owner；状态 **PROPOSED / Gate OPEN / NOT APPROVED**。
- Scope：`LH-Q2-CORE-POST-SUDO-ACCEPTANCE-v1`，仅 S1–S3。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；规则、直接来源及 SHA-256、Owner mandate、无例外和 change control 沿用根 AGENTS。
- 本文、[架构](ARCHITECTURE.md)、[实施方案](IMPLEMENTATION_PLAN.md)共同形成新准确 A。未有 Owner B 和独立 CLOSED C，不实施新批次。

## 1. 唯一目标与已有进展

继续同一核心功能：H01 真实任务、结果和证据收回 → Q4 运行中取消 → H11 自身原 ledger 恢复。
不增加功能、现场探针或资格项目。修复基线是 `432f3f4c5a36735d38869261968fc44583f14023`。
其 sudo 正式输出兼容修复和详细错误码已完成，相关 248 项测试通过；准确
[CI 37270712716](https://github.com/kongbu0621/infra-local-hand/actions/runs/37270712716) 3/3 success：
Linux 5157 passed / 88 skipped、installed 94 checks / 292 commands；Windows 1808 passed / 1327 skipped、installed 10/10。
Owner 提供的 2026-10-05 14:32 +08 截图报告本地 321 passed / 10 skipped、两次私料内存构包一致，未发现场包。
截图是本地报告，不替代原件；新批次身份改变后仍须核验准确 D 和新包。

旧 `lhqcore-20261003a` 和 `lhqcore-20261005a` 均已消费。前者收到 HELLO 后、发送 BIND 前失败；
后者已发 BIND/package，在 sudo 输出解析处停止。两个批次没有完整业务结果，历史业务真值、远端监督退出和 usage 保持 UNKNOWN。
本 A 请求的只有**一次新增固定请求**，不重用、改名重放或重置任何旧 marker/窗口。

## 2. 精确固定的旧来源

第一批五原件及身份逐字采用旧 next A
`0b0f445a36232f6bcd32c395b642f9a6b259d2db` 的
[固定表](https://github.com/kongbu0621/infra-local-hand/blob/0b0f445a36232f6bcd32c395b642f9a6b259d2db/docs/a2-execution/q2-core-next-acceptance/REQUIREMENTS.md)。
原 D `605a2a38d1db5ef85c961b4d357cafa157bdd7d5`，tree `ced38519fe6e3b86973de5ccf0dff60fc62322e4`，五件合计 9318 B；原逐项长度、摘要、包/manifest 和零 BIND 事实不变。

第二批来自固定 `d846c72afbdc1c46441cac133621b26c87e1730d` 的
[现场记录](https://github.com/kongbu0621/infra-local-hand/blob/d846c72afbdc1c46441cac133621b26c87e1730d/docs/a2-execution/Q2_CORE_HOST_CAPACITY_BOUNDARY_REVIEW_20261005.md)。
准确发行 D `59d7c32bbe10d580603b8e5e62dd49ad6a538e56`，tree `15bfe2192ced5aad0acf5c74a58b6e865afe34d1`；
dispatcher SHA-256 `30d8e9fe9a9bbf39dc5261d0eb0d47c7349fe7e8229132f394a31aa934216eb4`。
包 18149835 B / 860 members，SHA-256 `da72c862bbcbe4ae43df681f91576d38586eec1eeb550b46e378d3398e07008b`；
manifest SHA-256 `09e7b8ef0df3b3103f0ba87113dfcf2d3470b861ad14f84c83c144a0f6b3c6fb`；
approved-input 325117 B，SHA-256 `5bcbf535f6c8d0d2c974756af6815ba95a03da7fadc31c97a0622cdeeaf4846e`。

| 第二批固定 basename | SHA-256 |
| --- | --- |
| `.lhqcore-20261005a.carrier-consumed.json` | `126a3fc0c40085c360e6392d06ec286e42f05edc93823fd01f36c0869103d2a6` |
| `.lhqcore-20261005a.stdout` | `3cf4a279a36daeb3348d52544c92bdfeba3f295e0650f2bf49bd204d3e0bd3b9` |
| `.lhqcore-20261005a.stderr` | `ef5aad9b8e8b977441ad9ab1e58cd1dc8ad994798f5802d2f6768c241afb8ece` |
| `.lhqcore-20261005a.capture-manifest.json` | `081019f289a561839ddf13da0c5bf55150879e998a6b52241864f3813b132d1b` |
| `.lhqcore-20261005a.acceptance-receipt.json` | `541198e61811e4b6f2df3d17eb4ade8f91ef567ae4c00e89e7023f5709040f35` |

第二批五件总长度恰 9072 B，stderr 恰 23 B、原文 `CORE_ADMIT_SUDO_OUTPUT\n`。
其余逐项长度由上述散列匹配的原 bytes 得出，再验证原角色上限及文件/记录中的长度关联；不猜测或公开机器原文。
原 HELLO 必须恰一个完整 frame；BIND/package 已写、stdin 18150763 B/EOF、wait 3、双 EOF true、host deadline met true。
无 output-package/remote-result，原 receipt 两项业务真值 UNKNOWN。云端摘要不能代替本地严格读取十件原件。

## 3. 本次唯一新身份

| 对象 | 固定值 |
| --- | --- |
| session / carrier | `lhqcore-20261005b` / `lhqcore20261005b-carrier.service` |
| install / staging | `local-hand-core-acceptance-20261005b` / `.local-hand-core-acceptance-20261005b.staging` |
| package / marker | `lhqcore-20261005b.lhfp` / `.lhqcore-20261005b.carrier-consumed.json` |
| 另外五个输出 | `.lhqcore-20261005b` 加 `.stdout`、`.stderr`、`.remote-result.json`、`.capture-manifest.json`、`.acceptance-receipt.json` |
| install UUID | `4648df9b-a917-408d-9dba-763db663dd9c` |

| case | preparation ID | operation UUID | controller prefix | projects |
| --- | --- | --- | --- | --- |
| H01_NORMAL | `lhqc05b01h01normal` | `eb627e0e-88f7-48f9-929a-61ee0976bba7` | `lhqcore20261005b-c01` | 12301..12307 |
| Q4_HELPER_RUNNING_CANCEL_SUBSET | `lhqc05b02q4cancel` | `31aedc12-6ac1-4d63-82db-2d0cef0d5905` | `lhqcore20261005b-c02` | 12308..12314 |
| H11_SAME_LEDGER_RECOVERY | `lhqc05b03h11recovery` | `26019ce4-bacf-4352-90aa-1db003366649` | `lhqcore20261005b-c03` | 12315..12321 |

UUID 沿用 SHA-256 前16 B、UUIDv4/variant 位设置；seed 为 ASCII `urn:local-hand:LH-Q2-CORE-POST-SUDO-ACCEPTANCE-v1:<完整 case name 或 installation>`。
case basename、五个 parent locator 和12-role映射不变；identity/authority/profile/principal/ledger/node/epoch/slot 和所有派生 unit 使用新 session/operation。
发现任何新固定对象存在、别名、保护不符或 project 被占用即停止，不能换名找空位。两旧批的所有对象和原安装保持。

## 4. 请求接受的有限边界和资源

只有两个旧固定 carrier 在同一新请求内分别通过当前静止核验、完整保留旧承诺后，允许这两批的特定历史 UNKNOWN 不单独阻断。
第一批依据零 BIND/包与原 bootstrap；第二批依据固定发行代码的准入前置调用顺序及严格绑定的失败原件，不能冒用零包证明。
它不是完整历史执行证明，也不把本地 wait/EOF 当作远端监督闭合。若静态路径或原件不能支持“业务安装/独立业务 unit 前停止”，停止发行；不能扩大扫描范围补证。
每旧批各两次有界 SHOW/cgroup 观察，当前 boot 必须与两个旧 HELLO 一致；同名新 InvocationID、active、populated、身份漂移、缺项或超时立即停止。

| 保留承诺/边界 | 本次固定值 |
| --- | --- |
| 两旧 guest 逻辑承诺 + 新一次 | 各 289406976 B / 16512 inodes；同设备合 868220928 B（828 MiB）/ 49536，另加全部更早 guest 义务 |
| CPU 承诺 | 各 2090 CPU-s；三批合6270，旧不退款，新一次仍最多2090 |
| 三批 host capture 当前可用条件 | 各67108864 B / 16；合201326592 B（192 MiB）/ 48，全部另计、不减旧文件占用 |
| 两旧静止核验完成前的跨批 carrier 上界 | 三个carrier合3072 MiB / 384 pids；每个原1 GiB / 128不变；此阶段新批不得安装或启动case |
| 两旧全部静止后的新批原峰值上界 | 2624 MiB / 1160 pids，非整机其它负载保证 |

前置跨批上界明确从旧方案两carrier的2048 MiB增加到三carrier的3072 MiB；不声称新批自身2624 MiB能覆盖此初始跨批阶段。
无法核验原单unit限制或上界前提不成立即停止，不能提高单unit限额；不新增整机可用内存探针或排他预留保证。四次SHOW合计最多20s wall/8 CPU-s/131072 B输出，全部计入新原750s/2090CPU-s预算，无新unit、宽限或额外连接。
原guest 24+12历史行、46 quota 来源、32池逐device保守重复不变；每旧承诺独立计入，不以目前小文件或前置失败退款。

更早 host 覆盖、金额、共享池关系仍 UNKNOWN/null；本 A 重新明确请求 Owner 接受其不单独阻断本固定 capture。
仅在同一原900s caller内held anchor的当前 `f_bavail*f_frsize >= 201326592`、`f_favail >= 48` 后继续。
这不证明历史完整或排他预留：`complete_host_admission_proven=false`、`exclusive_reservation_proven=false`、两种 full-filesystem-peak 标志保持false。
空间争用仍可能导致任务和证据写入失败；失败不保证完整receipt。旧host边界批准只覆盖旧批，本A不假定其自动授权新批。

新批原180MiB/13440应用/观察、276MiB/16512逻辑准入、32MiB输入、60MiB输出、64MiB/16 host capture、六文件、82输出成员、900/800/750s和原reserve保持。
runtime candidate `4b6e4a7c403362358192086b88679e1326dcb2e1`、tree `4d4349580c9f4b67cc26f601126849c2bc8d76a4`，wheel SHA-256 `ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9`，projection SHA-256 `55f555fc225edca943b8c86cee8119c4878f5ec1e9503a084ba7a560cf2c991d` 不变。
仅新批create-only安装；不重装、覆盖或清理历史安装。身份、凭据、sudo授权、whole-file/no-follow/no-atime与原停止标准不放宽。

## 5. 完成及终点

S1：双旧来源、新身份、非退款承诺与准入/返回消费接齐。S2：准确D完整source、installed、CI和真实双构包验证。S3：最多一次新marker/request，H01→Q4→H11及原证据收回。
任一步失败、断开、UNKNOWN即停止保留；不自动重试、重连、延期、另起名字、退款或补采。新失败不授权第四批。
生产E3仍未获启用；namespace/watchdog、E4–E6、NAS及其它支线暂停。准确A批准前只继续既有不受影响的CLOSED开发范围。
