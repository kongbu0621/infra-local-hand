# locale 修复后单次核心验收需求

- Authority：Owner；状态 **PROPOSED / Gate OPEN / NOT APPROVED**。
- Scope：`LH-Q2-CORE-POST-LOCALE-ACCEPTANCE-v1`，仅 L1–L3。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；直接规则、完整性、Owner mandate、无例外及 change control 沿用根 AGENTS。
- 本文、[架构](ARCHITECTURE.md)、[实施方案](IMPLEMENTATION_PLAN.md)组成待批准 A。截图要求准备方案，不是 Owner B；须先独立 bookkeeping-only CLOSED C，再实现。

## 目标和已验证事实

只推进原核心链：H01 受理真实任务 → 受监督执行 → 确认退出 → 收回结果和证据；H01 语义 PASS 后才 Q4 运行中取消，Q4 完整 PASS 后才 H11 自身原 ledger / 原 unit 恢复。
不增加新功能、探针或 namespace/watchdog 专项。

准备时 main 为 `3f5775fb0a70b9c8394590eeda455225268b2c27`。
修复源码基线固定为 **`d0c8749e47647264c14c406cd85c8c68006689a0`**，tree `290605f62741206d95e6d7f6e9741025de6b488f`。
[离线交付](../Q2_CORE_SSHD_LOCALE_GRAMMAR_REVIEW_20261005.md)记录 359 passed / 2 skipped、准确 D 的 CI 37305140260 三 job success，
完整已保存三文件的一次纯解析为 `SOURCE_GRAMMAR_ACCEPTED`，139.679 ms。
该离线机会已用完；本 A 不要求也不授权重复解析该快照。新源码须逐字保留已验证文法函数及其纯依赖。
有效 sshd 策略、当前 guest 状态和 H01/Q4/H11 仍未实测通过；不能用上述结果替代现场准入。

03a、05a、05b 三次核心请求及 `lhqsshd-20261005a` 诊断均已消费。本 A 只提出一次独立新核心请求，绝不恢复旧窗口、重放旧 marker 或将旧 UNKNOWN 提升为成功。

## 固定版本和历史来源

原核心 runtime 与执行 harness 保持不变：

| 对象 | 固定身份 |
| --- | --- |
| runtime candidate | `4b6e4a7c403362358192086b88679e1326dcb2e1`，tree `4d4349580c9f4b67cc26f601126849c2bc8d76a4` |
| wheel | `infra_local_hand-0.2.0a1-py3-none-any.whl`，288375 B，SHA-256 `ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9` |
| harness projection | 原 89 文件 `.local-hand-source-projection.json`，11811 B，SHA-256 `55f555fc225edca943b8c86cee8119c4878f5ec1e9503a084ba7a560cf2c991d` |
| dispatcher 修复基线 | 449522 B，SHA-256 `8a597dcd8b4ba1cd63d7b8dfc6b8f4a562960faf47afa7190ff876357205f871` |

新批绑定实现会改变 dispatcher 其它部分的摘要，因此该修复基线不是尚未形成的新发行 D。
只允许 L1 指定的三旧来源、新身份、诊断保留及资源/返回接线增量；C 后冻结准确 D/tree/三个 field blob/包，L2 验证通过后才条件发行。
不采用随时移动的 main、不以新测试 wheel 替换原 wheel、不将离线修复 D 直接加入发行表。

03a 和 05a 的原 D/tree、包/manifest、十件原始 bytes 和历史传输/UNKNOWN profile，逐字沿用
[固定旧 A f9ba6fbc 的需求第 2 节](https://github.com/kongbu0621/infra-local-hand/blob/f9ba6fbc2fa983c46322a00f3385af172fed7cb4/docs/a2-execution/q2-core-post-sudo-acceptance/REQUIREMENTS.md)。
03a 五件合 9318 B；05a 五件合 9072 B；原冻结 profile 不因追加第三项而放宽。

05b 原件来自修复基线 Git 树中的[现场记录](https://github.com/kongbu0621/infra-local-hand/blob/d0c8749e47647264c14c406cd85c8c68006689a0/docs/a2-execution/Q2_CORE_POST_SUDO_ACCEPTANCE_REVIEW_20261005.md)。
原发行 D `8704a24b6c3c79ce4a36028ae2182dec2a35843e`，tree `89a5f221883c11838a10a452be2dcb756abb5a17`；
bootstrap SHA-256 `4a58b342ea4fabb95903e9362cc9b0007c6aafda5a5ece3203692c5033982ce3`，
dispatcher SHA-256 `319c651f05998f812ac8faab51a354c7445b584bc6442a26c9800e79ae776e96`；loader 与原两批相同。
正式包 18173610 B / 860 members，SHA-256 `dc30af5fed782615501df61c601461ca3d214d379e8805d86e4f0dc458b6a498`；
manifest SHA-256 `bb7c854f7279a352064de3f9bb260f92d7a0c8456a636cda747b363ac9481d2a`；
approved-input 338750 B，SHA-256 `5d227ecbef0eb0b72a3c5ddee998c1505b88ddf70d3c3c506e262144c25198da`。

| 05b 固定后缀，均接 `.lhqcore-20261005b.` | bytes | SHA-256 |
| --- | ---: | --- |
| carrier-consumed.json | 3577 | `3d38e232e66580d588f03cfd444e5d1729904af801dfeb83af51f87e721d6c20` |
| stdout | 2852 | `cde70ed0b21d2b6cc7c5d9a21652c68f7e0f3b171e7ee03627eb594b56204f3f` |
| stderr | 24 | `7c8bda65cecc5daeba8693865946e37aed794bdb930f1f71e0fe0ddb9c8684de` |
| capture-manifest.json | 1503 | `fd9e85a9b368cfaf58c3138b9860f3d4ba3c4370fa2319e8c992f04d64f23918` |
| acceptance-receipt.json | 1117 | `1274a7522d4f7151f894fbf530618cba12ba8134b1dd162731cb32c72f43929b` |

第三批五件合 9073 B，三批十五件合 27463 B。05b 恰一完整 HELLO；BIND/package 已写、stdin 18174538 B/EOF、wait 3、双 EOF 和原 host deadline met；stderr 恰 `CORE_ADMIT_SSHD_GRAMMAR` 加换行。
无 remote-result/output-package/case verdict，原 STOP_AND_RETAIN/CORE_OUTPUT_MISSING 和两项业务 UNKNOWN 保持。
其准确发行源码在 sudo 校验后、sshd helper 之前拒绝，也先于旧 scope 核对、guest 容量、安装及业务；该有限静态路径前提不是远端退出证明。

诊断四原件使用同一修复基线树中的[固定表](https://github.com/kongbu0621/infra-local-hand/blob/d0c8749e47647264c14c406cd85c8c68006689a0/docs/a2-execution/Q2_CORE_SSHD_SOURCE_CAPTURE_REVIEW_20261005.md#p3-实际单次采集已完成且机会已消费)：
准确 D `bf8d391c3fdb24a5d4fc188b0ec9f2b36d9e5891`、tree `460acde6c11a7b7555bf9992eb65bff16e822cad`，四件长度 495/7028/0/1259 B、合 8782 B，逐项 SHA 不变。
只能在本地核验这四件及 receipt/流关联；不运行旧 reader、snapshot 文法验证或已消费的双解析器/G3。
配置原文仍只留本地，不传入新包、guest、测试 fixture、Git、CI 或聊天；新输入只包含固定摘要与保留边界。

## 本次唯一拟用身份

对象仍为原受保护管理 anchor 绑定的隔离 Q1 guest、原账号/凭据/host key/端口和五个 parent locator；不换机器，不把工具环境当作物理宿主，不运行既有 start.sh。
下列名称仅是提案，不代表已经创建或取得不存在证明。

| 对象 | 固定值 |
| --- | --- |
| session / carrier | `lhqcore-20261005c` / `lhqcore20261005c-carrier.service` |
| install / staging | `local-hand-core-acceptance-20261005c` / `.local-hand-core-acceptance-20261005c.staging` |
| package / marker | `lhqcore-20261005c.lhfp` / `.lhqcore-20261005c.carrier-consumed.json` |
| 另外五输出 | `.lhqcore-20261005c` 加 `.stdout`、`.stderr`、`.remote-result.json`、`.capture-manifest.json`、`.acceptance-receipt.json` |
| installation UUID | `080152e8-883e-4906-a572-506d9534181c` |

| case | preparation ID | operation UUID | controller prefix | projects |
| --- | --- | --- | --- | --- |
| H01_NORMAL | `lhqc05c01h01normal` | `184ac06d-4ad0-405f-8d81-04e2e4474012` | `lhqcore20261005c-c01` | 12401..12407 |
| Q4_HELPER_RUNNING_CANCEL_SUBSET | `lhqc05c02q4cancel` | `041a80a8-ebb0-4611-8958-33076dae3ebc` | `lhqcore20261005c-c02` | 12408..12414 |
| H11_SAME_LEDGER_RECOVERY | `lhqc05c03h11recovery` | `78f91c42-83df-4266-a691-16b51eb5313f` | `lhqcore20261005c-c03` | 12415..12421 |

UUID 为 ASCII `urn:local-hand:LH-Q2-CORE-POST-LOCALE-ACCEPTANCE-v1:<完整 case name 或 installation>` 的 SHA-256 前 16 B，再设 UUIDv4/variant 位。
case basename、12-role 映射及派生 identity/authority/principal/ledger/node/epoch/slot/unit 算法保持，使用本新 session/operation。
任何新固定对象存在、别名、保护不符、project 占用即停止，不换名。只允许新批 create-only 安装；不重装、覆盖、重启或清理旧安装/业务。

## 需接受的有限边界和资源

三旧核心历史退出、usage、业务真值仍 UNKNOWN，各自完整承诺不退款。必须在同一新 carrier 内完成三旧各 A/B 两次静止核验，全部通过才安装或执行 case。
旧 boot 与新 HELLO 不符、InvocationID 改变、active/populated、缺项、漂移或超时均停止。有限静态 pre-business 前提或十五原件绑定不成立时，不发行，不扩大扫描取证。

诊断仅有 reader 报告完成、本地 exit 0/双 EOF；**其远端独立监督闭合和 SSH/sudo/PAM 祖先资源/退出仍未证明**。
本 A 请求接受此特定保留缺口不单独阻断新核心请求，不把诊断的较窄信任当作核心准入证据；所有当前核心校验照常执行。
不新增诊断进程扫描、清理或连接；若已有检查发现活动残留、矛盾或其它当前失败，仍停止，不以此历史接受覆盖失败。

| 预算或保证范围 | 固定值 |
| --- | --- |
| 三旧 guest 逻辑承诺及新一次 | 每批 289406976 B / 16512 inodes；同设备合 1157627904 B（1104 MiB）/ 66048，另加全部更早 guest 义务 |
| 核心 CPU 承诺 | 每批 2090 CPU-s，四批合 8360；旧不退款，新批仍只 2090 |
| 诊断保留 | host 4194304 B / 8 inodes；原已初始化 reader 5 CPU-s / 128 MiB address-space 不退款，不据此给祖先 usage 填 0 或声称整棵树有上界 |
| 当前 host 可用条件 | 四核心各 67108864 B/16，加诊断 4194304 B/8，共 **272629760 B（260 MiB）/72 inodes**；不抵扣旧实际小文件 |
| 三旧静止前的核心 carrier 配置上界 | 四个各 1 GiB/128 pids，合 **4096 MiB/512 pids**；不含诊断残留、管理祖先或其它整机负载，不是整机可用量保证 |
| 三旧全部静止后 | 新批原 2624 MiB/1160 pids；历史 UNKNOWN 不变，不声称整机峰值 |
| 六次固定 SHOW 总上限 | 30s wall / 12 CPU-s / 196608 B 输出，计入新批原窗口、carrier 限额和总预算，不是新增额度 |

每次 SHOW 仍最多 5s/2 CPU-s/32768 B，失败即停止而非继续取得成功样本；所有 helper 归原 carrier，不新增 unit。原 quota `native_children_started` 上限 16 的含义不变。
四核心 carrier 上界以原单 unit 限额和 pre-business 前提可核验为条件；不能核验即停，不新增整机内存探针或放宽限额。
诊断没有业务安装/project 义务，但管理日志/祖先的使用量不能当成零；此未知按上述明确边界保留，不并入虚假的有限整机总数。

更早 host 覆盖/金额/共享池仍 UNKNOWN/null，不单独阻断本固定 capture；当前 fstatvfs 检查不构成排他预留或完整历史准入。
空间竞争可能导致任务和证据回收失败，甚至无法写完整 receipt；完整 host 准入、排他预留及两种 full-filesystem-peak 保证仍为 false。
原 guest 24+12 历史行、46 quota 来源、32 池逐设备保守计账及每批 headroom 不变；三旧承诺逐项独立叠加，不借本 A 清零旧账。

新批应用/观测预算 **180 MiB/13440**、逻辑准入 **276 MiB/16512**、输入 **32 MiB**、输出 **60 MiB**、host capture **64 MiB/16 inode**、六文件、82 输出成员及 **900/800/750s** 外层时限和原各阶段 reserve 全部不变。
同一原 caller 窗口覆盖本地来源核验、构包、容量、marker、连接和收回；新一次不是旧 deadline 延长。

## 精确替换和完成条件

仅对新 05c：旧 post-sudo 合同的两 prior/四 SHOW 改为三 prior/六 SHOW；192 MiB/48 改为含诊断的 260 MiB/72；三 carrier 的 3 GiB/384 改为四核心 carrier 的 4 GiB/512。
增加诊断历史保留记录及其上述未独立监督边界，采用已批准 locale 文法，不扩大 AcceptEnv 模式或有效策略。
其他原核心合同、修订和旧 A 的字节不变；这些变化不回写旧 receipt，也不把旧批准自动转移到新批。

L1 接齐新增一次验收必需绑定；L2 完成准确 D 的 source/installed/CI、真实私料双构包和发行验证；L3 条件执行一次固定请求，交付真实链或准确失败。
仅原 live finalizer 可声明 COMPLETE；H01/Q4/H11 的语义、退出、结果/证据和资源条件缺一不可。
H01 正常入口的空 ledger 检查保持；H11 使用自身 origin 阶段的原 ledger/unit，不借 Q4、不重启业务、不延长 deadline、不读取原业务结果补证。
最多一次 O_EXCL marker 和一次请求；失败、断连、UNKNOWN 即停止保留，不重试、不重连、不补采、不清理、不退款，不自动提出或执行下一批。
生产 `E3_SUPERVISION_UNVERIFIED` 保持；namespace/watchdog、E4–E6、NAS 和其它支线暂停。此批准即使取得，也不授权生产启用。
