# Q2 历史未来安装承诺对账：架构

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。
- Scope：`LH-Q2-INSTALLATION-RESERVATION-RECONCILIATION-v1`；R 与[需求](REQUIREMENTS.md)一致。
- 本文定义待批准合同；实现顺序见[实施方案](IMPLEMENTATION_PLAN.md)。不改变既有 startup A 的字节或旧 v1 解释器。

## 责任边界与选择

| 组件 | 责任与依赖方向 |
| --- | --- |
| 来源校验器 | 读取准确 manifest、历史证明与 B/C，输出带来源类别的不可变输入；不作费用或执行决定 |
| 现场鉴证 backend | 受保护只读取得完整实时事实，输出有界观察；不修改旧对象或自行修复环境 |
| 义务账单器 | 从已验证输入和观察计算 C/A/U、全部费用与拟 after；不写记录、不解释未验证 raw |
| 追加记录器 | 仅在前置全部通过时 create-only 写入固定材料、fsync/seal；不运行候选 |
| amendment driver | 管理唯一窗口/状态顺序，验证 sealed 记录和再次准入后调用原 startup；原 runtime/owner/stop 合同不变 |

选择独立 amendment 与追加记录，是为了使旧解释器仍严格拒绝并保留历史原件。
不采用原位 `released` 字段、修改 quota 或清理旧目录；它们会破坏原证据或扩大
范围。失败恢复限于保留材料及只读确认，同值 seal 不重新执行；没有删除重做、
自动迁移旧 schema 或以旧 v1 回退运行的路径。实机可行性由有界联合鉴证证明，
若方案假设被实现或现场证据推翻，先改文档并重新取得受影响范围的准确决定。

## 输入与来源采纳

独立 amendment 输入模型有六组：准确 R/A/B/C/D 与既有 startup A/C；唯一未发行
计划和固定候选；十条历史 reservation 的原始值与互相引用；旧树/单文件证明；
仅两条新的 Owner 提供原始值；现场联合观察与完整费用对象清单。

`evidence-adoption` manifest 逐条保存逻辑 ID、来源类别、raw SHA-256/长度、
私有定位、证明摘要及适用范围。允许来源类别只有 `HISTORICAL_PIN`、
`HISTORICAL_TREE_MEMBER` 和 `CURRENT_OWNER_SUPPLIED_RAW`。前两种必须复算
原锚及其全部必要字段；完整树证明必须覆盖原算法的所有条目，不能只给根 hash。
第三种恰好为需求中的两条摘要，绑定本次回传包、准确 B/C 与 `prospective_only=true`；
不得覆盖或降低任何已经存在的历史 pin，也不为旧时间、旧动态观察或旧结果背书。

另设一个 `CURRENT_PRESERVATION_BASELINE`，只表示“第二 bootstrap staging 根
及相邻 intent”的当前完整树/文件，不能用作义务 raw 的替代来源。范围由准确
第二 bootstrap intent 与私有定位映射确定，共 610 条目（staging 树 609 项加
准确相邻 intent 1 项）、239944 bytes，准确
`forward-baseline-index.json` SHA-256 为
`9b5b5ec8dd1516cb8807bf26f657c652079843a3669783db215a4f9c5dd5852e`；
其中 `proposed_only=true`、`historical_identity_claim=false` 均保留，采用权威
须由独立 B/C 提供，不原位改该证据索引。它同时绑定 guest manifest
`82c8c13e250ac0be0957b766e84827514dd50cc5cc53d461c126d6dd0523f735`
及需求指定的外层包。逐项保留根/相对路径、类型、dev/inode、mode/uid/gid/nlink、
size/blocks、atime/mtime/ctime 纳秒值、regular raw 摘要或 symlink 目标文本，
采用初次无保护 hash 探测后、guest-inventory 记录时点，不声称具有全部归档
读取后完整二次 stat。该范围准确成员数及内容必须完整匹配；Git index
采用包内实际字节，不能把 stat 缓存变化解释成历史整文件相等。该当前比较起点
不能覆盖任何既有旧 pin，也不能扩展到其他根、动态 runtime 或新执行结果。

元数据采纳另用恰好五项 `POST_READ_METADATA_BASELINE`，每项绑定 raw 摘要、
既有元数据说明与 guest manifest 中的准确记录。后续比较从固定的 post-read 值
开始，必须明确记载 `historical_atime_preservation_proven=false`。缺项、加项、
把原准备 intent/preflight 加入例外、自动接受更新基线、遗漏偏差声明均拒绝。
采集前 stat 转录缺失这一限制永久保留，不依据说明文字补造旧元数据。

公开文档只保留逻辑身份、合同和摘要；私有输入承载实际路径、账户、unit/
InvocationID、原 raw、树条目和元数据。公开[回传索引](../evidence/q2-readonly-return-20260927/README.md)
是定位入口，不代替准确私有材料的验证。

## 现场联合鉴证

管理员使用受保护的逐段 no-follow 路径与 held fd，实际枚举和读取使用 O_NOATIME；
不能调用普通读取、时间戳恢复或保护降级重试。regular 文件单链接；原合同允许的
符号链接仅核验链接本身及已固定目标文本，不追随以读取其他对象。所有对象在
读取前后比较身份、权限、大小、内容及要求的元数据，五项偏差只改变准确起点。
SQLite 从固定 fd 读有界 bytes，在 RAM 副本核验固定 schema、身份、generation
及空表；不让 SQLite 打开旧路径、创建 sidecar 或恢复原库。

首次持久写入前，联合核验同 guest/boot/namespace、四个已知历史失败实例及其
准确 InvocationID/退出来源、所有相关父 cgroup 的完整后代成员与状态、无 job/PID、
账户/能力/manager/slice、两 ledger、两批次所有计费树、Q1 保留树及七根实测
UUID/project/inherit/限额/usage。未创建过的 target/监督器也按原失败阶段核验，
不把“不存在”和“本次已停止”合并。本包摘要不能代替实时 ioctl/quota 与完整树查询。

鉴证通过后持有受保护来源并写有界追加材料；在发行前再核验所有可能漂移的
来源/身份/空树/账本/根/配置/容量与剩余期限。两次 boot 必须一致，不能通过记录
外观相同、同名新对象或重新打开未受保护路径绕过。任何漂移/权限不足/截断/
无法覆盖全部成员即 BLOCKED，已写材料保留，不进入安装或发行的后续阶段。

## 义务图与账单

义务主键由原尝试、准确目标、费用类别、原授权与来源摘要共同决定；不是当前
目录名或新 epoch。原目标 192 MiB / 8192 inodes 与恢复声明是一笔；第二目标
64 MiB / 4096 inodes 是另一笔。第二 bootstrap 中 113274880 的旧 actual 基数
46166016 仅用于解释原累计数，不能重复变成独立 future 或作为当前实际量。

每个实际对象以 `(device,inode)` 去重，并有唯一费用归属。每笔承诺的覆盖集合
明确列出；原安装目标、第二安装目标、各 staging 与 owner 共池不得相互借用
actual。两 owner 的 capture/declarations/journal 是各自共池，不是三个完整池。
无法证明归属/嵌套/覆盖时拒绝，不以最大值、目录小或余额为零自行推断。

对每个维度 `d∈{bytes,inodes}`：

- `A_i[d]` 为目标完整树的现场实际分配；bytes 用分配块，不用 logical size。
- `U_i[d]=max(0,C_i[d]−A_i[d])`；仅两项目标的 `U_i` 可以在有效 seal 后终止。
- `bill_before[d]=unique_actual[d]+全部旧未消费独立义务[d]+尚未被本次同义务 actual 覆盖的新峰值余额[d]+未被上述池覆盖的封存余量[d]`。
- `bill_after[d]=bill_before[d]−U_1[d]−U_2[d]`；不得减任何 actual 或其他 future。

before/after 必须取同一观察时点、同一新费用覆盖基准；不能把安装增长后的
actual 再叠加完整新 64 MiB，或把已含 seal 的 1 MiB 子预算重复加一次 seal。
写记录导致实际增加后必须重新测量并重新计算剩余峰值，不能沿用写前 actual。

公式按费用类别和唯一设备分别展开；before/after 需给出每一项实际、覆盖、
未用承诺、新增峰值与去重关系，不只给一个净数。对其他义务仍计算其未消费
余额并保留，即使已终止服务也不自动终止 future。实际大于承诺时全额保留实际。
配额硬限制和设备剩余容量照原算法计一次，物理空间足够不等于承诺准入通过。

本包不含第二安装和部分第二 capture/state 当前完整树，因此当前只能确定旧
严格规则的超限下界。只有未来现场全量取证才能形成准确 after；未知绝不记零。
写入对账记录之前先验证拟采用的 after 及全量新费用；在 seal 成立之前计费语义
尚未改变，不可安装/发行。有效 seal 之后仍执行原 startup 完整准入，不自动放行。

## 独立记录合同与字段上限

采用独立 schema `local-hand-q2-installation-reconciliation/v1`；旧 schema 不新增
`released` 字段或免检开关。所有对象严格字段集合，拒绝重复 JSON key、未知字段、
非整数/负数/布尔冒充整数、非有限值、超长字符串与溢出；整数上限为 `2^63−1`，
SHA-256 为准确 64 位小写十六进制，commit/tree 为准确 40 位小写十六进制。
逻辑 ID ≤128 UTF-8 bytes；私有路径 ≤4096 bytes 且不能路径别名或目录穿越；
引用项合计≤128；每项 reservation JSON≤1 MiB，完整输入 manifest 单份≤8 MiB、
≤32768 条目，全部受解析输入合计≤16 MiB。本次 guest manifest 为 3419814
bytes，包含在该输入界限中；其引用不要求把全文重复写入 256 KiB 的 adoption
记录。原完整树扫描上限 512 MiB / 32768 条目及原命令/输出更小限额继续适用，
输入传输/暂存另计入原额度，解析界限不授予额外 IO/输出或 staging 空间。

| state 新文件 | 逻辑字节上限 | 固定内容 |
| --- | ---: | --- |
| `evidence-adoption.json` | 256 KiB | 十条 reservation、旧证明引用、两条新来源、五条偏差的准确 manifest |
| `reconciliation-intent.json` | 16 KiB | 独立操作 ID、R/A/B/C/D、startup A/C、唯一计划、候选、输入摘要、绝对 deadline |
| `live-attestation.json` | 512 KiB | 有界现场观察、完整扫描的摘要和覆盖数、计费集合引用及 before/after 元数据关系 |
| `reconciliation-record.json` | 64 KiB | 两项 C/A/U、全部分类账单前后值、其他义务不变、被引用观察与意图摘要 |
| `reconciliation-seal.json` | 4 KiB | 前四文件摘要/长度、记录身份、完成状态与落盘关系 |

adoption 还引用上述唯一第二 staging 当前树基线的完整私有 manifest，不把
整包采纳写成通用信任。现场观察可以引用已固定的完整基线及可复核比较摘要，
但必须完成全量扫描、所有字段比较和覆盖数核对；不能只保存 `true` 或缺项摘要。
512 KiB 无法承载完整的必要证明时即 BLOCKED，不截断观察后 seal。

五文件逻辑总上限 852 KiB；五文件加一个新目录，实际分配与 inode 峰值必须在
**1 MiB / 16 inodes** 内。该 state 子预算在首次写前显式计入原 32 MiB / 4096
类别；按实际文件系统核验分配块，不假设 4096 字节粒度；目录、所有部分写入
与 fsync/seal 开销也在内，压缩/稀疏不放宽逻辑上限。不能把既有 2 MiB 外部输出池
或已有日志余量重复当作它的抵扣。准备日志、管理 journal、外部 capture 的新增
成本按各自原类别另行计入。上限不够就失败保留，不切分额外文件或增加第二目录。

intent 和 record 均显式携带两个目标的私有映射、来源类别、`future_only=true`、
实际不变断言、其他承诺不变断言、`historical_results_unchanged=true`、
`run_permission=existing_startup_once`。断言必须由已核验对象导出；不能仅相信布尔值。
记录与 seal 不把 `Q2 accepted`、历史停止或原 EOF 当作成功字段。

## 追加协议与独立状态

创建使用固定身份与 create-only 排他路径；先完整写入并 fsync adoption/intent/
attestation/record，再建立 seal 并 fsync 文件与父目录。只有完整 seal 引用的
准确记录才允许该唯一计划采用新账单；写入出错、截断、缺 seal、并发 loser、
既存异值均阻塞，不能删除、覆盖、换身份或自动重试另一笔。既存同值 sealed
记录只允许只读验证，不产生第二次释放或第二次启动。

输入状态为 `REVIEWABLE` 或 `INPUTS_BLOCKED`；Gate 独立为 OPEN/CLOSED。
准确 B/C 后，执行状态依次为 `UNSTARTED → LIVE_ATTESTED → INTENT_DURABLE →
RECORD_DURABLE → RECONCILIATION_SEALED`，其后才可能进入原 startup 的
`PREPARED → ISSUED → CAPTURED/STOPPED/SEALED` 各独立证据状态。任一阶段
失败进入 `BLOCKED_RETAINED`；缺 stop、EOF 或 seal 各自保留，不能由别层成功补齐。
对账 seal 只证明受限新计费记录成立。原 startup 发行状态未证实就不能称已运行，
新批次成功也不能把旧 INCOMPLETE 改成成功。
