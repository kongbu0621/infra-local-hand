# 核心下一次验收：需求

- Authority：Owner；状态 **PROPOSED / Gate OPEN / NOT APPROVED**。
- Scope：`LH-Q2-CORE-NEXT-ACCEPTANCE-v1`，仅 N1–N3。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；直接规则路径及完整性沿用根 AGENTS。
- 本文与 [架构](ARCHITECTURE.md)、[实施方案](IMPLEMENTATION_PLAN.md)构成准确 A。
  未获准确 A 的 Owner B 与独立 CLOSED C 前，不实施本次新转换、对象或现场动作。

## 1. 目标与已发生事实

唯一目标仍是：真实执行 H01，收回业务结果和证据，再验证 Q4 运行中取消、H11 原 ledger 恢复。
代码、CI、包或 HELLO 通过均不能替代这三个实际语义结果。

源基线 `40f0f989cc1d76f35a17bb1551ea6a1c68da0441` 在 `3902ce5` 上提前拒绝 guest 不接受的包名；
既有 writer 修复为 `a6638424c5de2ea59f39cf6e24f07b06040d0884`，其 CI 37220038272 已全部通过。
[原 F1 记录](../Q2_CORE_SINGLE_F1_RESULT_20261005.md)固定了已消费批次：
发行 D `605a2a38d1db5ef85c961b4d357cafa157bdd7d5`、有效 HELLO、BIND/package 零字节、
SSH wait status 255、远端退出/EOF/完整 usage UNKNOWN。原五个文件保留；原单次授权已消耗。
此处对私有现场的陈述来自 `3902ce51d33c736a44a26013d239e6f5cbe996bc` 的上述记录；新实现必须读取并核验私有原件，不能以公开摘要代替 raw。

原 scope 固定 `LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1`，原 session 固定 `lhqcore-20261003a`。
原 D tree 固定 `ced38519fe6e3b86973de5ccf0dff60fc62322e4`；原 package SHA-256 固定
`a8ca34f3fba3fd370485b522f3c009fa41de70fab1441224b56232885b77380e`，manifest SHA-256 固定
`9c05d55ed52dc1e0c04ad340549de6e584a4296b392d84abd07428f179a1989f`。
以下为本 A 自包含的旧原件固定值，不随后来同路径报告或文件改变：

| 原 basename（均以前缀 `.lhqcore-20261003a` 开始） | bytes | SHA-256 |
| --- | ---: | --- |
| `.lhqcore-20261003a.carrier-consumed.json` | 3577 | `5d85f8d5c51329bf46eba91d0106a41d449389e16b018bbb30ddbc667e69d502` |
| `.lhqcore-20261003a.stdout` | 2852 | `bd042a224271b03eadaddb99868e3f0c4cef4f71365482f112577005d8be5e1d` |
| `.lhqcore-20261003a.stderr` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `.lhqcore-20261003a.capture-manifest.json` | 1637 | `5ab260b4062404991151dd917fd636d4f1cd4ba5dd0ffa45a1578f5cf6bb3db3` |
| `.lhqcore-20261003a.acceptance-receipt.json` | 1252 | `dd1d4f5c607572fa9eb1527ddb94e2eb839f5ae5e59509042b6d03313cf74700` |

本 A 请求新增**仅一次**固定管理请求，不重用旧请求或旧身份。原 CLOSED 开发授权不因此作废。
旧错误修复无需再次批准；新增批次、当前旧 scope 核对和新增资源承诺才是本次请求决定的范围。

## 2. 明确请求 Owner 接受的有限边界

保留该准确旧批次的 historical remote exit、deadline closure、EOF、usage 为 UNKNOWN。
只有在新请求同一 carrier 的原准入窗口内证明**当前旧固定 scope 不活跃**，并全额保留旧资源承诺后，
允许这个特定历史 UNKNOWN 不单独阻断新批次。它不变成历史 PASS，不产生退款或旧义务释放。
新批次自身的 UNKNOWN、超时、当前身份/权限/容量不完整仍立即停止；不能推广为一般忽略 UNKNOWN。

当前核对须同旧 HELLO boot。旧 unit 若仍 loaded，必须与原 InvocationID 一致、MainPID=0、
处于 inactive/dead 或 failed/failed，且原精确 cgroup 当前不存在或完整无任务。
若已被原 --collect 卸载，只有两次固定 unit 查询均 not-found、原精确 cgroup 两次确实不存在、
held no-follow 父身份及 boot 前后一致，才可记录 CURRENT_SCOPE_QUIESCENT。
这证明当前固定 scope 的状态，不补造历史退出证明。旧 PID 缺少 starttime，不用 PID 单独认领进程。
同名新 InvocationID、active、populated、alias、漂移或取证不完整均 STOP_AND_RETAIN。

不等待旧进程自然结束，不轮询，不 stop/kill/reset-failed，不删除旧 unit/cgroup/文件。
核对在唯一新 carrier 收到已验证包后的 dispatcher 准入中完成，早于安装目录、quota、ledger 或业务创建；
不增加独立 SSH probe、辅助现场轮次或第二管理请求。

## 3. 新批次的唯一对象

| 项目 | 固定值 |
| --- | --- |
| session / logical namespace | `lhqcore-20261005a` |
| carrier unit | `lhqcore20261005a-carrier.service` |
| install / staging basename | `local-hand-core-acceptance-20261005a` / `.local-hand-core-acceptance-20261005a.staging` |
| package basename | `lhqcore-20261005a.lhfp` |
| marker | `.lhqcore-20261005a.carrier-consumed.json` |
| 五个 output basename | `.lhqcore-20261005a.stdout`、`.stderr`、`.remote-result.json`、`.capture-manifest.json`、`.acceptance-receipt.json`（后四项均使用相同 `.lhqcore-20261005a` 前缀） |
| install UUID | `6fd82898-ae68-4a5c-bce5-65f06e86580c` |

| case（原语义不变） | case basename | preparation ID | operation UUID | controller prefix | project IDs |
| --- | --- | --- | --- | --- | --- |
| H01_NORMAL | c01-h01-normal | lhqc05a01h01normal | `97d5ce56-e176-47c8-88eb-ff81242bfcfd` | lhqcore20261005a-c01 | 12201..12207 |
| Q4_HELPER_RUNNING_CANCEL_SUBSET | c02-q4-cancel | lhqc05a02q4cancel | `bb46ffb2-187e-48a7-8c2d-f548dd576fa6` | lhqcore20261005a-c02 | 12208..12214 |
| H11_SAME_LEDGER_RECOVERY | c03-h11-recovery | lhqc05a03h11recovery | `7fa6d9d2-812f-45a4-8027-4cfb183aa862` | lhqcore20261005a-c03 | 12215..12221 |

UUID 沿用原 SHA-256 前16bytes、版本4/variant位设置算法，URN scope 精确改为本 Scope；
case name 与 installation 后缀不变。不得仅改日期而复用旧 operation/install UUID。
其余 identity/authority/profile/principal/ledger/node/epoch/session 的原派生算法使用上述新 session；
所有 lh-jobs 派生 unit 必须由新 operation/policy 得出。五个既有 parent locator 与12-role映射不变。
新对象或 project ID 已存在/占用即停止，不临时换名找空位。旧 session/project12101..12121及所有旧对象原样保留。

## 4. 固定资源、来源与可接受后果

固定 runtime candidate `4b6e4a7c403362358192086b88679e1326dcb2e1`、tree
`4d4349580c9f4b67cc26f601126849c2bc8d76a4`，wheel SHA-256
`ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9`，projection SHA-256
`55f555fc225edca943b8c86cee8119c4878f5ec1e9503a084ba7a560cf2c991d` 均不变。
只允许新批次 create-only 安装，原安装不重装、不覆盖。生产 E3、namespace/watchdog、E4–E6、NAS 仍暂停/排除。

每新批次维持原上限：应用/观察180MiB/13440；逻辑 admission276MiB/16512及逐设备保守预留；
2090CPU-s、2624MiB/1160pids；input32MiB/output60MiB；host capture64MiB/16inodes。
原旧批次全276MiB/16512和2090CPU-s承诺不退，不能用0输入或9KB capture推定实际guest使用为零。
同设备仅这两个core批次的逻辑承诺为552MiB/33024，CPU承诺4180CPU-s，另加全部更早历史义务。
旧host64MiB/16承诺与新host64MiB/16分别保留，同设备合128MiB/32；不能拿现有小文件自动退款。
当前容量准入须将旧/新和原更早承诺一并计算，各device不能凭总空间充足略过。

旧scope确认前，最多两个carrier暂时并存，各仍1GiB/128pids，其并存上界2GiB/256pids；
新carrier不得开始case，保持原全链峰值上限。核对所用最多两次systemctl helper总wall≤10s、
每次CPU≤2s、combined stdout/stderr≤32KiB，全部计入新carrier原预算，无额外unit/宽限期。
新host900s、carrier800s、guest750s及原子时限/预留不变；新窗口只属于本次新增授权，旧窗口永不重置。

原包版本v3、HELLO/BIND/marker、approved-input顶层v1、remote-result v2、三field文件集合、
82 output members、六host文件保持。旧失败原件内联既有唯一private/approved-inputs.json，仍受1MiB上限；
仅其reconciliation、historical_capacity_obligations组件及admission中的新记录按架构显式演进。
源码上限8192/49152/524288B与原所有身份、credential、sudo和whole-file校验不变。

## 5. 成功、停止与本 A 的终点

N1：旧五原件严格绑定、旧新承诺分开、新身份完整派生、当前旧scope核对与双端消费实现并离线验证。
N2：准确D完整source/installed验证、真实私有输入及两套package build/parse，全部release门闭合。
N3：最多一次新marker和carrier，原序列H01 semantic PASS → Q4 semantic PASS → H11，回收真实结果及证据。
创建marker即保留消费事实；请求发出后失败、断开、UNKNOWN均停止，不重连、重试、改名或补采。
仍存在或部分存在的marker不覆盖、不删除。新批次失败不授权第三批。

最终报告分别给出两个批次的消费、HELLO/BIND、真实任务、结果回收、取消、恢复、退出和资源状态；
旧UNKNOWN不得被新成功改写。修复或新CI通过不等于本A已批准，也不等于现场通过。
本次仅请求以上明确一次核心验收及其必要实现，不开放通用重试器、通用批次平台或生产切换。
