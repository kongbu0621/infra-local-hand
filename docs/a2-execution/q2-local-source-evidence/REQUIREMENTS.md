# Q2 固定本地来源补证：需求

- Authority：Owner；状态：**PROPOSED / Gate OPEN / 尚无本 scope 的 A/B/C/D**。
- Scope：`LH-Q2-LOCAL-SOURCE-EVIDENCE-v1`，仅本地只读取证。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，直接来源为 `engineering-sop/docs/workflow/program-repository-documentation-gate.md`；其 SHA-256 为 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- Owner mandate、Owner-only Authority、无规则例外及禁止自动改变采用/范围的规则沿用根 `AGENTS.md`。本提案不修订 R。
- 本文与[架构](ARCHITECTURE.md)、[实施方案](IMPLEMENTATION_PLAN.md)共同组成待审三文档；只有包含这些确定字节的真实提交才成为 A，不预写未来 SHA。

## 问题与目标

准确 K4 完整回执已于 2026-09-28 收到并完成限定核对；状态仍为
`OBSERVED_PARTIAL / final_local_recheck`。五树42对象已观察，七个已知相邻普通文件
仍未观察；wrapper 的准确 raw 未在现有私有归档中恢复。现有 attestation 只有四份
固定控制文件的路径、stat、长度与 SHA，没有原文。

目标是给后续离线账目与执行来源审查提供最小缺失事实：**七个相邻对象的当前有界
metadata/hash、四份固定控制文件的匹配原文、两个固定父目录的既有 FS 观察**。
使用原普通身份、已有 Python 和 RAM 回传；不要求重做已完成 K4。

旧 host A 的一般本地核验目标不等于允许任意扩展已交付 K 包。K A
`887b640b394f9983f37dfe97c58ba35aaa099359` 明确保留五组目标及原 pin，专用读者
初始只供原 local preflight。故本 scope 明示新增7+4目标，以及两固定内核视图在
这个新 local-only 分支的有限复用，不将其自动传递到消费入口。

## 精确输入与来源角色

| 代号 | 固定原件 | 长度 bytes / SHA-256 | 本 scope 采用用途 |
| --- | --- | --- | --- |
| P | 原 `q2-cpuquota-retry-20260927.py` carrier | 5,426,689 / `5eef22e497e9e0a867470c6c490336dc80fadd0e506e3419847e6c37b687918b` | 仅 AST 解析唯一 HOST_RESULT/HOST_OLD，按原合同派生相同父目录和消费定位；不执行 |
| M | 旧 host manifest | 50,266 / `7672ac050609fc7e05481443c9239df0d36f25b4ec9860c2bb833024b962647a` | 仅解析固定49条中的七个直接相邻普通文件；保留 locator-only 角色，不作为历史身份或费用类别 |
| T | `host-current-attestation.json` | 5,913 / `76cc2c698dbe882ed246509746bc7088ba55df4199f550af8bad42c9f925dd65` | 保留原 boot_id 用途；新增仅采用 vm_control_files 中下述四项的路径/长度/SHA，固定本次目标和原文匹配基准 |

四项新采用不包括 T 的其它字段、整个 VM 目录、控制脚本引用的其它文件或任何执行权。
匹配 raw 只作为静态来源材料，不证明历史执行采用了这些 bytes，不自动取得完整Q2准入。

七个 M 定位目标与有界内容读取长度：

七项按完整 `source_path` 字典序排序后分配以下逻辑ID；公开表不含真实诊断路径组成部分。

| 逻辑ID | bytes |
| --- | ---: |
| M01 | 9,844 |
| M02 | 5,426,689 |
| M03 | 4,564 |
| M04 | 4,779,775 |
| M05 | 5,353 |
| M06 | 258,348 |
| M07 | 4,095 |

M 的完整摘要固定每项原 SHA；架构另按其规范字段逐项解析，不由调用者覆盖。
这些内容只求 hash，不回传 raw。合计上限10,488,668 bytes。

本scope只新读上述七文件、下述四文件和必要父目录/固定内核视图。**不重扫K4五树的
42对象**；七份旧pin仅在既有原件中离线保留/校验，不再现场读取其文件，除非该文件
本来就是本11项allowlist的一项。K4旧42对象只作历史观察，不能与本次七项拼成同一
时点49对象当前完整清单，完整账单及未释放future继续unknown。

四份 T 固定原件：

| 文件名 | bytes | SHA-256 |
| --- | ---: | --- |
| ssh.sh | 328 | `aed91e80483d4df103f95c1d4cd5bf9bd18720f4dc51720702c329c937f93c63` |
| start.sh | 1,162 | `1acc8c4cb09bc5b14c32adc35e87d8500098cbf3968d53f406269e96df30f96a` |
| known_hosts | 99 | `d1025c074e532f29534fcab1d10ec1bc2f38d2137173c74d0bc921bbab420bbd` |
| id_ed25519.pub | 95 | `e67e15549d3e8586af936108f666612841d31612705236dd8ce265a3da18b25c` |

四者合计1,684 bytes；只在长度、摘要和前后完整性核查吻合后回传单份 base64 raw。
不匹配时不返回替代原文、不改 pin。不读取原私钥 `id_ed25519` 或额外凭据文件。脚本原文尚未恢复，文件名与摘要不证明其中没有敏感内容；四份 raw 只进入私有回执与证据，不公开或日志散出。

## 要求与验收

| 编号 | 要求 | 通过条件 |
| --- | --- | --- |
| L01 | 固定离线来源与准确链 | P/M/T 原字节先校验；新R/A/B/C/D和旧链可验证；任何未知字段覆盖、额外目标或更换来源均在现场读以前拒绝 |
| L02 | 7+4有限目标 | 精确11文件与两个父目录；七个相邻文件只metadata/hash，四控制文件只匹配raw；不执行carrier或脚本，不递归/扩读依赖 |
| L03 | 普通证据保全 | held/no-follow/O_NOATIME、单链接/保护及读前后名称与fd绑定保持；权限不足、别名、替换或变化准确报告，不能回写时间戳 |
| L04 | 内核例外只属本地 | 仅沿用固定boot与自身mountinfo专用资格合同；boot→mountinfo→boot各有上限；不接受任意PID、路径或降级开关，不能接到writer/full execution |
| L05 | 原身份、原boot | 原本机普通身份及namespace假设；当前身份稳定且与held父目录owner关系匹配；固定boot不变，无sudo/账户/能力/挂载/权限变更 |
| L06 | 有界RAM回传 | 有效内容合计上限10,490,352 bytes，含每文件最多1 byte超长检测的实际读取总上限10,490,363 bytes；接收/校验/读取/输出受140/300秒双钟与16MiB输入、2MiB双流约束；无主动持久结果 |
| L07 | 完整性与差异分开 | 七对象长度不同则metadata-only并报告变化；等长才hash，摘要差异明确保留；四原件不符则不返回raw；每项缺失保留原因，不补零 |
| L08 | 当前FS事实不越权 | 两个固定父目录fstat、statvfs、GETFLAGS和已有mountinfo匹配；无raw device、试写、fsync试验或配置变更；分配峰值/持久资格仍unknown |
| L09 | 不产生业务权限 | 0 wrapper/remote/owner/marker/批次消费；消费名既存或状态不明立即停止；allow_run/consume、Q2/Q3/production始终false |
| L10 | 结果可复核且历史保留 | 精确D与目标来源、实际范围、双钟、错误和原文绑定；保留K4及旧失败原件；不把异时观察合并成同刻完整账单 |

## 资源、停止与非目标

完整启动、输入与framing合计≤16 MiB；stdout+stderr合计≤2 MiB（结果预留原16KiB
协议/错误余量）；普通文件有效内容≤10,490,352 bytes；每项超长检测最多额外读1 byte，实际读取合计≤10,490,363 bytes。boot每次有效内容≤64 bytes、mountinfo≤1MiB；各视图超长检测最多额外读1 byte。
仅一次mountinfo和两次boot；内核实际取回字节合计最多1,048,707。父目录及必要祖先只读metadata，不枚举。
计时包括最早载荷接收和全部校验，准备≤140秒、总≤300秒；不继承K4时钟，不刷新
原Q2唯一批次起点。无自动重试、备用目标或自动续跑。L5先交付一次有界原host调用；返回后只收件复核。如确需同范围再次观察，由Owner明确发起，沿同一固定来源/对象/上限从新的本地双钟开始；不接管旧原点、不改变或消费原Q2批次。

全局环境/保护或离线来源不符即停止，报告已实际完成的范围。单项缺失、长度变化或稳定摘要差异仅按架构的固定错误分类处理。纯本地观察不消费原Q2批次；读取可能
引发内核动态metadata/既有系统审计，不声称整机零写入，不把未知原生日志费用补零。
本范围不提供full-run选项；不采集guest时钟/版本/管理域，不新增监督设施，不更改预算
或旧义务，不批准普通writer使用内核例外，不批准H07监督准备、Q2/Q3、GX10、真实NAS。

原预算、冻结runtime、旧批准链及无关CLOSED范围保持。完成本scope仅说明限定来源
事实已取得或阻断明确；完整账单、费用采用、H07和FS分配峰值/持久性仍各自待证。
原文/真实路径/boot/机器身份只私有保留，公共披露另按已有准确授权边界判断。
