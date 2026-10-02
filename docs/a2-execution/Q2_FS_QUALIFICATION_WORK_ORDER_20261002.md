# Q2 双 parent 文件系统资格：2026-10-02 最小离线工作单

2026-10-02 +08:00；代码审阅起点 `6cce996d17ccde1aa4fe48feaaa4cec226d834c0`；
本轮 FILETYPE 实际修复 D `38a9e15697469f6590e54ddd89754a5d3344f23e`。
本文将已批准范围内可继续的离线工作固定为输入、检查、产物与退出条件。
它是审查工单，不是新的三文档 A、Owner B、C 或现场执行指令。

适用范围为 `LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1`：R
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，准确 A
`68424df2ddbf812b9479ffa7a64dcaa59a2a9f76`，独立 C
`179652cb9487163d83c004d358e4d4b49409694c`；
[需求](q2-old-producer-admission-retry/REQUIREMENTS.md)、
[架构](q2-old-producer-admission-retry/ARCHITECTURE.md)、
[实施计划](q2-old-producer-admission-retry/IMPLEMENTATION_PLAN.md)的字节和历史状态保持。
既有 S1、E1–E3、Ledger A2 及其他独立 CLOSED 记录不因本工单重新申请批准。

**本轮最小路径是重用已有原件、逐项证明适用性并重算条件账单；实际 FS qualification
仍为 BLOCKED。** 不读取新的 host/guest 现场状态，不创建消费对象，不连接 guest，
不试写、provision、修改 flags/权限/配置、扩展 profile 或退休任何设施。
原 `20261001e` 保持 `FAILED_RETAINED`，`20261002a` 未发行；
`field_ready=false`、`allow_run=false`、`guest_executed=false`。

## 本工单采用的固定合同

| 对象 | 当前 A 的准确约束 |
| --- | --- |
| consumption parent、evidence parent | 两者分别来自 package-bound locator/context；已存在，固定普通 UID/GID、mode、device/inode及无 symlink/未知 ACL 的保护祖先链；不得现场新建或改变 parent |
| FS profile | 真实 rw ext4 与受保护实际 block-device source/rdev/superblock 绑定；block/cluster 4 KiB；parent 仅 EXTENTS，size/allocated 各 4 KiB；保留 journal/filetype 及不支持 features 的原拒绝 |
| host record | 文件逻辑 ≤12 KiB、目录与文件总逻辑 ≤16 KiB；完整创建/部分写入/同步峰值 ≤64 KiB / 4 inode |
| evidence | 一个原始 archive inode；四个独立 `evidence_*` 上限均在准确 manifest 中固定；最终文件、partial 状态、parent 增长及未覆盖 metadata/sync 均受预留约束 |
| 共享 capture | **20 MiB / 384 inode**，只有一份；64 KiB/4 inode record 是其中的子预留；两个实际设备分别准入，同一物理设备聚合 |
| 容量算法 | statvfs free 已扣除实际分配；保留全部未释放历史完整承诺，再加入新未物化义务/峰值；actual 不作为第三个容量加数，也不从承诺退款 |

上述值来自当前 A 的“固定 host 尝试记录”“不变预算”部分。
[旧 FS1–FS6 工单](Q2_FS_BILLING_SOURCE_CONTRACT.md)的证明义务可以重用，但其旧 capture
64 MiB / 4096 inode **不能作为本范围 ceiling**。旧 H 中允许研究更宽 profile 的文字也
不能改写当前 A 明确固定的 EXTENTS-only/4 KiB 双 parent 谓词。

## 已有来源索引与适用边界

| 来源 | 已保留的准确材料 | 本工单可以直接使用的事实与边界 |
| --- | --- | --- |
| K4 | [完整回传复核](evidence/q2-kernel-field-20260928/full-return-review.json)；[原件引用记录](evidence/q2-cost-source-review-20260929/retained-input-check.json)登记 34,013 bytes，SHA-256 `281ff17ffd7bb83f7afd0bcae7488f5fa5b9bf551852f63494ceb8d84cc5cab9` | 某时点固定来源/局部 kernel 和文件观察；B 的所选原字段为 4,096 bytes；不是未来创建峰值、当前 freshness 或完整共同账单 |
| R3 | [独立回执复核](evidence/q2-local-source-field-20260928/diagnostic-rerun3-independent-validation.json)；32,439 bytes，SHA-256 `700a17989fec4271973a0620e87dccee64ce30ef4f7082a97ab42e5b6648f119` | 11 项 MATCHED、四份控制原文；某时点 parent size/allocated 为 12,288 bytes、EXTENTS+INDEX。该旧观察若适用于待准入 parent，当前窄 profile 必拒绝；不得假定当前仍是该几何，也不得从 K4→R3 的差推导本次 G |
| 历史归档 | [回传 manifest](evidence/q2-readonly-return-20260927/manifest.json)、[保留说明](evidence/q2-readonly-return-20260927/README.md)；[准确 D 来源复验](evidence/q2-reconciliation-implementation-20260927/exact-D-source-check.json) | 十份 reservation 原件已在归档并集可用；12 历史树、15 旧文件锚、47 分类来源、610 前瞻比较基线及五项 post-read 起点已保留。该复验不证明当前树或对账后的实际账单；历史来源标签按各自后续准确 adoption 决定解释 |
| 普通 writer | [实现复核](Q2_ORDINARY_WRITER_IMPLEMENTATION_REVIEW.md)、[验证记录](evidence/q2-ordinary-writer-20260929/verification.json)；D `c2373313eb78aa55373cb0318d08d5f60424dafd` | 普通身份、保护链、真实创建/ACL/O_NOATIME/fsync/读回/竞争有组件证据；测试替代 readiness、boot、FS 三项前提，不能作原设备 qualification |
| 首次 parent 增量 | [实现复核](Q2_PARENT_ALLOCATION_IMPLEMENTATION_REVIEW.md)、[验证记录](evidence/q2-parent-allocation-20260929/verification.json)；D `530a2a45bc6e96270771ccf266793e471d8408ee` | 首次 M/G 与原记录绑定；actual=M+G、future=C−M−G，C=65,536 不变。G 是顺序端点净差，不是同时快照、独占因果、峰值或持久性证明；B 仍未证明 |
| 当前前驱和离线模型 | [原实现复核](Q2_OLD_PRODUCER_ADMISSION_RETRY_IMPLEMENTATION_REVIEW.md)；[固定 predecessor](../../tests/e3_host/q2_old_producer_admission_retry_contract.py)、[accounting](../../tests/e3_host/q2_old_producer_admission_retry_accounting.py)、[完整离线 fixture](../../tests/e3_host/q2_old_producer_admission_retry_offline.py) | 前驱 bytes/摘要与 pre-provision-failure 类型固定；纯模型验证全额承诺、去重、时点峰值与未知拒绝。`SYNTHETIC_BOUND`、`SYNTHETIC_COMPLETE` 只描述合成输入，不能成为来源采用或现场证明 |

原件继续在各索引所列的私有 Git 归档保留；公开产物只用逻辑角色、摘要、字段关系和结论。
不要求 Owner 再寻找或重新采集上述已经 retained 的文件。

已有公开字段可以先完成如下引用表，无需新采集：

| 准确字段位置（JSON pointer） | 已有值/结论 | 本次处理 |
| --- | --- | --- |
| `retained-input-check.json#/selected_reference_arithmetic/B_K4`、`/B_R3` | 4,096、12,288 bytes | 两项分别保留；`/same_epoch_or_current_inventory_proven=false`，不相减为G、不作为当前资格 |
| 同件 `/source_group_subtotals/0`、`/source_group_subtotals/1`、`/unknown_identity_count`、`/unknown_commitment_count` | null、null、13、2 | 引用检查已完成，身份/承诺依旧未证；不重跑相同13项后记为全账PASS |
| `q2-readonly-return-20260927/manifest.json#/historical_verification/all_ten_reservation_raw_inputs_available_across_archive_union` | true | 原件定位工作已有材料；缺口是适用分类、义务和当前联合账单，不是请Owner补同一批raw |
| 同件 `/ledger_snapshots/0/empty_consumption_tables`、`/ledger_snapshots/1/empty_consumption_tables` | true | 两个历史RAM副本检查通过；不推导当前表仍空或实际可重新消费 |
| `exact-D-source-check.json#/live_admission_proven`、`/runtime_authorization_consumed` | false、false | 42工具/48blob的来源复验与现场准入分开；文档/原件引用不消费运行权 |

以上简称分别指本节链接的准确源文件；字段算术不赋予原件新的权威用途。

## 按顺序执行的最小离线工单

每项产物都须给出准确源 commit/tree、原件 bytes/SHA-256、字段位置、角色/类别依据、
观察边界及明确未证项。允许使用已经持有的 bytes；禁止执行来源载荷或跟随其机器路径。
“离线完成”只表示该产物完整且诚实；表内 qualification PASS 条件必须另有适用证据全部满足。

| 工单 | 已有 source 和精确不可替代缺项 | 当前允许的离线检查及固定产物 | Qualification PASS 条件 | 是否 material 补充 |
| --- | --- | --- | --- | --- |
| FS0 来源与两个 parent 分开绑定 | K4/R3、locator/context schema、历史归档可作引用起点；缺两条待准入路径各自的同一 host/boot、parent/祖先/device/mount、观察边界和合法采用依据。一个 parent 的证据不能转给另一个 | 逐字段列出 consumption/evidence 两张来源表；核验 bytes/摘要、schema、固定角色和调用用途；缺失值写 UNKNOWN，不用旧路径名或整数 device/inode 补身份。产物：双 parent 来源与缺项表 | 两条路径与准确 locator/context 及保护链逐项相同；所有观察机器和时点明确，全部准入事实有适用来源 | 整理已持原件不需；将未采用字段/来源升级为执行权威、改 locator/parent 或信任边界才需 |
| FS1 设备与实现适用性 | 现 `_mount`/`_superblock` 固定 ext4/rdev/原件读取关系；缺实际内核构建/config 与所引用 ext4 实现、block-device/存储链的适用绑定。上游代码或 CI 内核不能替代原机版本 | 按当前函数逐条列出读取对象、flags、权限、范围、错误及用途；从已持原件找能绑定的字段，逐项标“已采用/仅观察/缺失”；把算法引用映射到实际构建。产物：版本/设备/读取来源矩阵 | 两 parent 设备与真实挂载一致；所有算法/存储假设适用于准确已采用构建；普通身份具有原保护方式下的读取资格 | 映射不需；新的 raw/等价来源、权限、读取例外或字段用途须逐项按 R 处理，不默认请求 sudo |
| FS2 粒度与 features | 当前 `_geometry`、EA_INODE 拒绝和窄 parent 检查已在源码；缺双路径适用 superblock/config 事实及其权限/采用关系。statvfs=4 KiB、GETFLAGS 和 ACL absence 均不能代替完整 feature/config 事实 | 对照准确函数逐 bit/条件列必需与拒绝 feature，核验常量/测试与 A 一致；将已有源字段指向该清单，缺 cluster/raw 事实明确阻断。产物：窄 profile 谓词/来源清单 | block/cluster、journal/filetype、被拒绝 feature、parent flags/size/allocated、fstatvfs 几何全部满足当前 A，无未证项 | 原窄谓词核对/收紧实质缺陷不需；接纳 INDEX/12 KiB 或扩 feature/profile 必须准确受影响补充 |
| FS3 全过程分配与父增长 | 固定名称、marker 操作顺序、archive bounds、M/G getter 与合成 phase snapshots已有；缺实际适用创建/目录插入/extent/allocator 的全过程上界，包括失败残留。端点 G、一次成功测试和只列正常阶段都不能代替 | 从准确创建路径列 mkdir/create/partial-write/file-sync/directory-sync/parent-sync 及每条首错分支；逐项标物化量、承诺、释放是否确证和 parent 正增长；为每个算法界给出处和适用前提。产物：双路径时序峰值证明表，不填写无证据数值 | 正常和全部失败路径每一时点的无重复分配有适用界；record ≤64 KiB/4；evidence 覆盖固定最大 archive allocation+parent/metadata/sync；partial/final 为同一个 inode的不同状态 | 原源码/已有源的离线推导不需；原机试写、另建实际 fixture/provision 或引入不在既有范围内的机制/来源才需明确边界 |
| FS4 创建属性、metadata 与隐式对象 | ACL 检查、EA_INODE 拒绝、dir scan 已有；缺实际 security/xattr/default-attribute/quota/allocator 路径适用事实及额外块/inode上界。ACL absence不证明所有创建属性为零，目录成员不覆盖隐式 inode | 逐个创建操作列 inode/data/extent metadata、security/xattr、quota和同步所涉资源；与 FS2/FS3 做交叉覆盖索引，区分已存在区域重写和真实新增分配；未知成本保留 UNKNOWN。产物：无重复 metadata/attr/allocator 成本表 | 每个适用创建钩子及 allocator 分支被排除或有独立上界，并且未在已计 st_blocks/其他条目中再收费；额外 inode明确计费 | 分解/去重不需；新增配置/属性读取、权限或新权威来源若超原批准须补充；不能为取得上界改 LSM/xattr/日志策略 |
| FS5 并发、B/G/M 与失败留存 | 历史归档、首次 observation、成本引用组件已有；缺 B 的合法类别/覆盖、同一观察机器边界、并发创建者适用约束和完整失败留存库存。held fd 与前后稳定不是兄弟互斥 | 逐件关联原件字段→物理身份→角色/类别→义务→覆盖；已知“same inode”仅在已证明的同机/观察边界去重；列所有已知 alias/混合 parent/未决覆盖；为共享 parent 的正增长标联合峰值 UNKNOWN。产物：B/G/M/alias/并发责任表 | B 计一次且类别合法，G/M不漏/不双抵；所有可能影响界的并发与失败残留都有依据；无 unknown inventory，亦不靠删旧承诺迁就接口 | 既有引用/冲突检查不需；新增互斥设施、共享分摊规则、类别采用或将旧未知推定已释放须准确补充 |
| FS6 同步与存储适用前提 | writer的真实 syscall组件证据、A规定record/evidence fsync/readback/rebinding顺序及已接受trusted-storage/no-same-UID-tamper前提已有；缺原设备存储链/flush适用事实、对该准确过程的错误/失败终态覆盖。SHA、close、CI success不能代替 | 对源码和离线trace逐次列held fd对象、fsync前后guard、错误传播、部分对象保留、pread与name↔inode重绑定；将存储假设标治理前提或设备事实，不能把前者写成技术回滚证明。产物：持久性论证与错误终态表 | 在准确已接受存储前提和已绑定设备/实现下，所有成功声明均有完整适用同步链，错误/身份漂移保留真实UNKNOWN/BLOCKED；不承诺排除任意掉电/同UID整体回滚 | 源码/已有证据论证不需；扩张诚信/存储假设、新设备来源、掉电实验、改存储设置等才需精确补充 |
| BILL 历史全额承诺与新预留 | 十份reservation、12树/15锚、47来源/610基线、固定`20261001e`intent/receipt/plan/failure及纯accounting已有；缺其全部费用的已采用类别/观察设备映射、当前完整actual/future与原生审计覆盖 | 按原scope/池/目标列每项未释放承诺、actual已反映free及合法终止记录；只对确有准确终止依据的义务采用其已有规则，不把旧实现“允许终止”写成实际已终止。用严格纯API复算原件关系和条件账单。产物：带unknown的完整ledger映射及逐设备条件报价 | 保留所有更早义务、`20261001e`代码64MiB/4096及其state/journal/capture/七根、当前新授权；实际不第三次加收/不退款；record/evidence全部预留在mkdir前；全局20MiB/384及每设备free同时满足 | 映射/严格算术修复不需；新增释放、重分类/采用、改变预算或错误地复用旧对账权才是material变化 |
| AUDIT 原生审计及收尾 | 已有wrapper/control原文与FS费用矩阵可列事件；缺准确工具/服务/config、事件次数、每条记录/块取整、目的设备、轮转和并发背景上界。业务stdout上限或stderr空不能替代磁盘审计成本 | 从固定一次SSH/manager/owner/collector/stop/seal路径列成功及每个失败阶段事件；给每个事件关联source、次数界、记录界、分配/轮转和已覆盖池；源缺失保留UNKNOWN。产物：事件→记录→物理分配→原journal/capture池矩阵 | 所有实际/未来SSH、sudo、systemd/journald和收尾副作用都有适用界且与已有池去重；原16MiB management-output等流量限制分别核验，不当作磁盘界 | 既有材料静态映射不需；新审计来源/信任用途、日志设置修改、专用设施或新增维护动作须按实际material差异补充 |

FS3 在本范围首先证明被准许的非 indexed 窄路径，不把旧 FS 工单的 HTree 研究要求变成
默认允许 INDEX。仅当明确选择扩 profile 方案时，才在新的受影响 A 中写入那条算法、来源、
预算和验证合同；当前不能只删除 `FS_INDEX_FL` 拒绝或放宽 size。

## 可直接执行的离线检查与产物格式

按 FS0 → FS1/FS2 → FS3/FS4/FS5 → FS6 → BILL/AUDIT 的依赖顺序处理。
FS1/FS2 缺适用字段时，后续可以继续完成条件论证，不能把条件论证改记为 qualification PASS。

1. 从上述公开索引定位已经 retained 的私有 blob；核对 bytes/SHA及准确 adoption引用，
   不读取原机器路径。对每个条目登记 `source_sha256`、JSON pointer或准确源码行、
   `observed_value`、机器/观察关系依据、合法类别/用途依据和缺项；未知保持 null/UNKNOWN。
2. 重用 `q2_cost_source_review.review_cost_sources(manifest_raw, sources)`检查已有bytes的引用、
   物理别名和覆盖/抵扣冲突；该API的source_adoption/observation_completion/full_bill/FS
   false字段保持。K4/R3已应用的13项原引用不重新声称完整身份、当前epoch或跨源总账。
3. 对照准确源码、当前A与离线fixture生成双路径操作/首错表，并逐项标实现、仅模型或未接线。
   record覆盖目录出现即消费、0400 held-fd fchmod、
   短写、所有必要fsync及O_NOATIME复读；evidence覆盖超限不创建、0600独占open/fchmod、
   完整写循环、file/parent fsync、同fd pread及名称/metadata重绑定；每次失败固定名称保留。
4. 已有数值和合成反例分别送入 `calculate_peak`、`evaluate_accounting` 与
   `verify_offline_case`。后者已有完整record64KiB/4及manifest最大archive allocation预留，
   不用实际小archive缩减预留；人工填入的bound和identity仍是fixture事实。
5. 出具本表九项产物的汇总：每项分别标 `OFFLINE_COMPLETE`、`CONDITIONAL_PROOF` 或
   `BLOCKED_MISSING_APPLICABLE_FACT`，附确切缺项和已有source引用。整套qualification
   只有在所有适用证据、峰值、持久性及全量账单均通过时才可PASS；离线产物齐全不自动改状态。

纯源码实质缺陷可以在其已有 CLOSED 开发范围内修复并添加有意义反例；验证采用项目支持的
Python版本与准确CI身份。合成测试通过不记为实机资格，旧失败记录和未消费状态保持。
初始工单仅固定材料、顺序和验收条件；下节另登记本轮已完成的 FS2/FS3 源码核对及
FILETYPE 窄修复。没有新增机器观察。

## 本轮已固定的结果与下一决定点

本工单已把现有材料映射到九项明确工作，并界定了当前A与旧FS工单的预算/profile差异。
以下事实不能由现有公开来源索引替代，仍保留未知：两parent实际适用资格、内核/设备/存储
绑定、完整创建/失败/同步峰值、隐式属性/allocator费用、B分类/并发、当前完整ledger和原生审计界。
没有编造峰值块数、当前设备free或实际after账单；没有重用历史4KiB/12KiB观察作当前资格。

先完成上述原件映射和条件证明，优先利用已批准的来源、读取保护、定位和预算。
确有必要的material补充只列准确缺项、选定机制/来源/实际对象、原池费用、截止及失败终态，
形成最小三文档A后再走R→A→Owner B→独立C→D；不请求任意新来源或任选设施的空白许可。
当前窄K reader consumer集成已由本A明确批准，不能再次当作未获准用途；新增任意proc/raw
读取或PermissionError fallback则不随该窄批准传递。

即使FS工单将来满足，H07与准确独立P4 event/ref仍各自是硬门；
本文件不产生可执行ZIP/`TASK.txt`，不发行现场包、不消费窗口，也不授权live cutover、S2或E4–E6。

## 本轮实际完成：FS2 源码谓词矩阵

以下按当前 A 的 R12、R13 和“固定 host 尝试记录”核对，包含本轮已提交的
FILETYPE 窄修复 D `38a9e15697469f6590e54ddd89754a5d3344f23e`；源码摘要及准确
commit/CI 映射由本轮独立实现验证记录绑定。函数为
[record 实现](../../tests/e3_host/q2_host_window_record.py#L174)的 `_mount`、
`_superblock`、`_geometry`、`filesystem`。这里证明的是准确源码检查什么，
不是为两条原机路径填入结果。当前消费器
[observe](../../tests/e3_host/q2_old_producer_admission_retry_consumer.py#L183)
只取得固定 boot/mountinfo、选择两 parent 的 containing mount；结果明确包含
`filesystem_qualified=false`、`peak_and_persistence_qualified=false`，没有调用 raw
block-device reader、保持两个 parent fd 或创建对象。

符号/mask 已对照一手固定版本
[Linux v6.12 ext4.h](https://raw.githubusercontent.com/torvalds/linux/v6.12/fs/ext4/ext4.h)
核验：`FILETYPE` 属于 `s_feature_incompat`，值为 `0x0002`；superblock `DIR_INDEX`
为 compat `0x0020`，inode `INDEX` 为 `0x1000`，两者是不同字段。字段偏移同时对照
[ext4 superblock 文档](https://docs.kernel.org/filesystems/ext4/super.html)。
v6.12 仅是本轮常量对照源，**不是原机内核构建/config、算法适用性或设备资格**。

| 字段/来源 | 准确值或 mask | 当前 A 的约束与源码实际检查 | 已完成的离线结论；原机状态 |
| --- | --- | --- | --- |
| raw superblock 长度；`s_magic` @56 (`0x38`) | 1024 bytes；`0xEF53` | `_geometry` 要求严格 `bytes`、长度和 magic；错误 `HOST_WINDOW_EXT4_SUPERBLOCK` | 源码谓词已核对；两 parent 的适用 raw 摘要/内容仍 UNKNOWN |
| `s_log_block_size` @24 (`0x18`)；`s_log_cluster_size` @28 (`0x1c`) | 二者均 `2`，返回 `(4096,4096)` | `_geometry` 拒绝任何非 2；`fstatvfs` 不代替这两个 raw 字段 | synthetic 2/2 正例和分别变 3 的反例通过；两 parent 原字段 UNKNOWN |
| `s_feature_compat` @92 (`0x5c`)：HAS_JOURNAL | required `0x0004` | `_geometry` 要求置位，保持 A 的 journal 要求 | 源码检查成立；原设备 journal/配置/适用性 UNKNOWN |
| 同字段：DIR_INDEX | forbidden `0x0020` | `_geometry` 要求未置位；禁用的是 filesystem feature，不是只检查这个 parent 当前是否 indexed | 源码检查成立；不能由 parent ioctl 没有 INDEX 推导 superblock 没有 DIR_INDEX |
| `s_feature_incompat` @96 (`0x60`)：FILETYPE | required `0x0002` | 本轮增加 `EXT4_FEATURE_INCOMPAT_FILETYPE=0x2` 与必需谓词；缺位返回 `HOST_WINDOW_EXT4_GEOMETRY` | 修复前 compat=4/incompat=64/rocompat=0 被误接受；修复后缺位拒绝，正确 `0x42` 接受；compat 或 rocompat 的 `0x2` 不能冒充；原字段 UNKNOWN |
| 同字段：EXTENTS | required `0x0040` | `_geometry` 要求置位；与 inode EXTENTS flag 不是同一 mask | 正向 raw fixture 全部改为 `0x42` (`EXTENTS\|FILETYPE`)；原字段 UNKNOWN |
| 同字段：COMPRESSION、JOURNAL_DEV | forbidden `0x0001`、`0x0008` | `_geometry` 保留原拒绝集合 | 源码检查成立；没有据此假定所有其它 journal/config 事实已证明 |
| 同字段：EA_INODE | forbidden `0x0400` | `_geometry` 用该 namespace 拒绝额外 EA inode 路径 | 正反 namespace 控制保留，EA 反例为 `0x442`，不会先因缺 FILETYPE 失败；同数值 compat FAST_COMMIT/rocompat METADATA_CSUM 不是 EA_INODE，也不是完整 metadata qualification |
| 同字段：INLINE_DATA、ENCRYPT、CASEFOLD | forbidden `0x8000`、`0x10000`、`0x20000` | `_geometry` 保留原拒绝集合，合计 incompat 拒绝 mask `0x38409` | inline/encrypt 反例已保留必需 FILETYPE (`0x8042`/`0x10042`)；源码拒绝集合已核对；原字段 UNKNOWN |
| `s_feature_ro_compat` @100 (`0x64`)：BIGALLOC | forbidden `0x0200` | `_geometry` 拒绝置位；block/cluster 相同仍不能替代 BIGALLOC 检查 | synthetic BIGALLOC 反例通过；原字段 UNKNOWN |
| 其余 superblock feature/config | 没有全 feature 白名单；没有从本轮读取扩展字段 | `_geometry` 不拒绝以上集合之外的每个位。它不读完整 xattr/security/quota/allocator/config 事实 | 精确限制已固定；未排除/未计费的路径仍交 FS1/FS4，不能把谓词返回值写成“全部隐式费用为零” |
| parent `FS_IOC_GETFLAGS=0x80086601` | 必须精确 `FS_EXTENTS_FL=0x80000`；`FS_INDEX_FL=0x1000` 必拒绝 | `filesystem` 要求 EXTENTS 置位且没有其它 flag，错误 `HOST_WINDOW_PARENT_FLAGS_UNSUPPORTED` | 源码检查成立；parent INDEX 和 superblock DIR_INDEX 两个检查各自必需；12 KiB/EXTENTS+INDEX 旧 R3 不能作为当前正例 |
| held parent stat | `st_size=4096`、`st_blocks*512=4096`（8 sectors） | `filesystem` 逐项要求，错误 `HOST_WINDOW_PARENT_GEOMETRY` | 严格窄谓词已核对；两个当前 parent 的字段、同机器/时点绑定及 B 类别仍 UNKNOWN |
| held parent `fstatvfs` | `f_bsize=f_frsize=4096` | `filesystem` 检查这两项；record available≥65536、`f_favail≥4`，错误 `HOST_WINDOW_LOCAL_CAPACITY` | legacy record 容量谓词有实代码；evidence 的 manifest 最大分配+父增长/metadata/sync 及同设备聚合尚只有离线账单模型，不能借固定65536检查完成双路径准入 |
| containing mount | parent `st_dev` 的 major:minor；root=`/`、fs=`ext4`、rw；canonical `/dev/` source | `_mount` 选择最深 containing mount；拒绝 ro、`nobarrier`、`barrier=0`、`dax`、`dax=always`、`data=writeback`、`fsync=volatile` | legacy source 检查已核对；当前 consumer 的 K reader/mount parser 只观察，并未调用此 legacy 通用 proc reader；namespace 合法条目不能被忽略以伪造 ext4 |
| block-device raw source | root-owned、单链接、block 类型、`st_rdev==parent.st_dev`、`mode & 06022 == 0`；无 ACL；name↔fd 与读前后 metadata 稳定 | `_superblock` 经 root-owned protected ancestors、`io.flags()` 打开，`pread(fd,1024,1024)`；`io.flags()` 为 `O_RDONLY\|O_CLOEXEC\|O_NOFOLLOW\|O_NONBLOCK\|O_NOATIME`，不弱化/提权回退 | 源码边界已核对；普通操作者对准确原设备的 read 与 O_NOATIME 能力/资格仍 UNKNOWN。测试/CI substituted `filesystem`，不能借 CI 普通身份成功替代 raw 设备读取资格 |

上述改动只收紧已批准 raw 字段的 FILETYPE 缺位判断，没有新 source、profile、权限或
现场读取。修复前精确合成失败案例已私有保留：433 bytes，SHA-256
`77e0bacae893426d1e30e0a490a521f7d990986ad8266866276ce2e56b1722ea`；
它证明旧源码缺谓词，不作为历史机器资格证据。支持 Python 3.12.14 的纯 geometry 组
为 **3 passed**；native 普通身份、仅进程临时 `umask(022)`、既有隔离 test-parent 的
record/ordinary/ordinary-inputs/parent-observation/parent-allocation-inputs/consumer/offline
定向组为 **316 passed, 21 skipped**。21 项均为旧 root-only record 测试，不能计为 PASS；
普通 writer 的真实局部 syscall 组已执行，其 boot、readiness、FS qualification 仍是
明确替代项。此次检查没有访问原机 raw device，不把测试结果写为 qualification=true。

## 本轮实际完成：FS3 操作、首错与峰值覆盖表

记号：**实代码/组件**表示仓库内确有调用该 syscall 的旧 ordinary v2 组件，隔离测试可
执行；**合成**表示当前 retry 的纯数据 fixture，`host_file_created=false`，没有 host I/O；
**UNKNOWN**表示原机或当前 retry 的适用全过程资格未成立。当前
[consumer](../../tests/e3_host/q2_old_producer_admission_retry_consumer.py#L183)是只读 K 集成，
不调用下面的创建流程。旧 record 的 constructor/consume 都有
`require_field_readiness` 阻断，组件正例显式替代此门；旧 `_create` 的名称、schema、
scope、140s preparation 和来源读取也不能自动成为当前 retry 的固定名称、专用 schema、
150s preparation 与窄 K 集成。
下表的 fchmod0400 缺项针对当前 A 已授权但尚未物化的新 retry writer；它不表示旧 v2
已批准合同要求了同一步骤，也不要求为旧 writer 重新审批。

| record 时点/实际函数 | 已有状态与首错路径 | 当时必须覆盖的物理量；当前证明边界 |
| --- | --- | --- |
| mkdir 前：`HeldPrecheck.__init__`/`verify`，ordinary `_before_mkdir`；当前 `validate_trace` 到 `HOST_RECORD_ADMITTED` | 实代码/组件核验身份、held parent/祖先、absence、旧单路径 FS、bill、worst-width intent；任一检查/guard/读取首错立即传播。合成 trace 将 mkdir 前失败记 `LOCAL_BLOCKED_UNCONSUMED` | 当前 A 必须在此完成两个 parent、完整账单、record完整64KiB/4和最大archive+其它峰值预留。旧单 parent 组件和合成 trace 不证明此已发生；实际重采样/设备free/完整义务 UNKNOWN |
| 排他 `mkdirat`：`HeldConsumption._create` | 实代码/组件：`mkdir(固定名,0700,dir_fd)`，成功后立即 `window_consumed=true`；`FileExistsError` 也设 barrier 并首错 `HOST_WINDOW_ALREADY_CONSUMED`。不清理、不重试 | 新目录 inode/data、消费 parent 的插入增长、创建钩子/metadata 初始量。非 EEXIST 的 syscall 错误只传播；若不能证明未出现目录，不能拿旧内存 bool 作“未消费/无对象”证明，结果保留 UNKNOWN |
| 新目录 open/fstat/ACL/name binding；ordinary `_created_directory_check` | 实代码/组件：held no-follow/noatime directory fd；精确0700、普通UID/GID、device、nlink2、name↔fd/祖先检查。open/ACL/guard 错误原样停止；自检错误 `HOST_WINDOW_DIRECTORY_IDENTITY`/`HOST_WINDOW_DIRECTORY_CHANGED`/`HOST_WINDOW_PARENT_CHANGED` 等 | mkdir 已消费；任何空目录和失败残留均留存。成功 metadata 端点不能推导中途创建属性/额外inode为零；目录与parent峰值 UNKNOWN |
| 首次目录/父同步：`_create` | 实代码/组件：guard→`fsync(directory_fd)`→guard→`fsync(parent.fd)`；任一次 OSError/guard 首错传播；随后才生成实际 directory identity 的 intent | 空目录/parent及同步触发的分配和失败终态留存；errno 不被改为成功。隔离 fsync 成功证明调用/返回，不证明原设备 flush/隐式分配峰值 |
| 排他 intent open 与属性确认：`_create`、ordinary `_created_file_check` | 实代码/组件：`O_CREAT\|O_EXCL\|O_RDWR\|O_NOFOLLOW\|O_NOATIME\|O_CLOEXEC`、open mode0400；写前验证 regular/nlink1/size0/精确0400/普通UID/GID/device/name↔fd/ACL。错误 `HOST_WINDOW_INTENT_IDENTITY`/`HOST_WINDOW_INTENT_REPLACED` 或原 OSError | 第二个 inode、空文件、属性/extent/目录插入费用须覆盖。**旧 `_create` 没有 held-fd `fchmod(0400)`**；当前 A 明确要求它，因此当前retry实际 writer仍缺该步骤及对应首错路径，不能用open mode参数代替 |
| intent payload：`_create` | 实代码/组件：单次 `os.write`，必须返回完整长度；短写首错 `HOST_WINDOW_SHORT_WRITE`，不补写/截断/删文件。合成当前 intent decoder只核验 canonical bytes/limits，不执行该步骤 | 全/部分intent同一个inode，文件≤12KiB、目录+文件总逻辑≤16KiB；真实 partial blocks 与metadata/parent/sync峰值仍 UNKNOWN。短写已有真实局部故障保留测试，不能把成功端点当失败路径上界 |
| 文件/目录/父同步：`_create` | 实代码/组件：分别重复guard后按file→directory→parent fsync；任何首错传播，consume只close held fds，不删除目录/文件 | 每个同步前后和首错时点都受record64KiB/4，而不是仅同步完成后检查；实际算法/设备适用性、同步分配和残留量 UNKNOWN |
| bytes与名称复核：`_verify_files` | 实代码/组件：重新parent/boot guard，精确directory/file metadata和name↔fd、唯一成员、0400/nlink1/普通身份/device/无ACL；held fd `io._read`复读准确bytes并decoder核验；漂移/读取失败立即停止 | 保留原路径对象；原K boot集成、原设备O_NOATIME及存储资格仍 UNKNOWN。component操作可用，但旧通用boot读取不是当前retry新的实际writer集成 |
| endpoint `_budget`/`first_allocation_observation`，`verify` | 实代码/组件：snapshot后首次 `G=max(0,after.blocks-before.blocks)*512`，要求marker bytes+G≤65536、inodes≤4、logical≤16384、G≤4096；`HOST_WINDOW_ACTUAL_LIMIT` 首错。首次M/G与metadata固定并在RAM导出；后续使用固定首次G | 这是顺序端点净差与已绑定首次RAM证据，**不是全过程最大值或独占因果**。负delta的原before/after仍保留；新纯accounting拒绝不合法baseline/覆盖，不能用max0填补缺失B、并发正增长或中途峰值 |
| durable声明与后续错误 | 实代码/组件在初次snapshot/budget后设 `durable=true`，再 `verify` 和preparation guard；后续首错仍停止、对象保留。合成trace在目录已出现但durable未到达记 `CONSUMED_PARTIAL`；已durable而SSH未到达记 `BLOCKED_RETAINED` | 应区分“旧组件内存状态已设位”和当前A的完整持久消费资格；未知持久性不能宣布可继续guest或可重来 |

evidence 的实际 syscall writer 尚未接线；下面每行的成功/失败记录来自
[validate_evidence_frame/write](../../tests/e3_host/q2_old_producer_admission_retry_offline.py#L228)
与固定 `WRITE_STEPS`/`WRITE_FAILURE_AT`，它们校验**合成收据**，不是执行写盘。
失序/伪造收据报 `OFFLINE_EVIDENCE_WRITE_ORDER`/`OFFLINE_EVIDENCE_WRITE_FAILURE`；
合法失败收据返回 `BLOCKED_RETAINED`、首错、禁止retry/rename/cleanup，保持所有现场能力false。

| evidence 时点/合成收据 | 准确首错或成功约束 | 实现/峰值与qualification状态 |
| --- | --- | --- |
| mkdir前双parent保护链/固定basename absence、full reserve | 当前context/locator与accounting可纯校验固定角色；不能用name变化、已有文件或symlink作接管理由 | 合成引用/预算已实现；当前retry held evidence parent/祖先/absence实际核验未实现，现场UNKNOWN；此门必须早于recordmkdir，不等frame到达 |
| `FRAME_ACCEPTED` | `validate_evidence_frame` 从canonical header≤4096及archive原bytes重算schema/kind/length/SHA；分别检查frame/logical上限与management output≤16MiB；超限不进下一步骤 | 纯bytes校验实代码；没有SSH或文件创建。wire界不是allocated/metadata界 |
| `OPEN_EXCLUSIVE` | 此前只完成1个step；`EXISTS`/`SYMLINK`在position1失败，不设本模型新partial-file；成功要求随后固定basename、heldfd而不是temp/rename路径 | 实际 `openat(...EXCL/NOFOLLOW/NOATIME...,0600)` 尚未实现；新archive inode和evidence parent插入增长需全额reserve；错误歧义/原已有对象不得忽略 |
| `FD_CHMOD_0600` | 此前2个step；`FCHMOD_FAILED`在position2，模型标partial留存。成功必须在heldfd显式fchmod0600 | 仅合成step；原机属性钩子、inode/data/xattr费用、chmod失败残留量 UNKNOWN |
| `WRITE_COMPLETE` | 此前3个step；`SHORT_WRITE`在position3；实际合同要求完整写循环；失败固定名partial留存，无重命名/清理 | 仅合成step；partial/final必须同一archive inode。未执行循环或证明每个write时点、error路径和最大分配 |
| `FSYNC_FILE` | 此前4个step；`FSYNC_FILE_FAILED`在position4，首错保留 | 仅合成step；file同步所涉allocation/metadata和持久资格 UNKNOWN |
| `FSYNC_PARENT` | 此前5个step；`FSYNC_PARENT_FAILED`在position5，首错保留 | 仅合成step；held evidence parent同步/增长及底层flush事实 UNKNOWN |
| `PREAD_VERIFY` | 此前6个step；`PREAD_FAILED`在position6；成功收据须准确length与SHA对应frame | 纯收据核验；实际same-fd pread循环/错误捕获仍未实现；SHA和读回不能单独证明耐久性 |
| `NAME_REBOUND` | 此前7个step；`NAME_REBOUND_FAILED`在position7；成功要求fixed-name与heldfd identity都true并精确parent device/inode | 纯收据核验；实际held dirfd/no-follow stat/name↔inode重绑定及race控制尚未接线 |
| `FILE_METADATA_VERIFIED` | 此前8个step；`METADATA_FAILED`在position8；成功9个step齐全，regular、普通UID/GID、0600、nlink1、无ACL、同device、inode非parent、logical=frame length、allocated≤manifest上限 | 严格integer/identity/长度收据校验已有；无实际metadata采样。成功仍`host_file_created=false`/`field_ready=false`，不将caller true字段变为qualification |

全过程费用模型的已完成边界也已核对：
[calculate_peak/evaluate_accounting](../../tests/e3_host/q2_old_producer_admission_retry_accounting.py#L128)
按 record `create/write/file_sync/directory_sync/parent_sync`、evidence
`partial/final/file_sync/parent_sync` 的完整顺序synthetic snapshots去重；同一个archive inode在
partial/final只取时点最大和。`metadata_sync` 可计新增块而0新inode；该费用不能漏掉，也不能
把已覆盖的inode/data再计一次。new record/archive/metadata身份不得与**任何** retained actual
物理身份重叠，old-code也不能冒充。parent基数无合法类别/覆盖、缺任一snapshot或实际
qualification未知都阻断；两个路径共享parent且正增长无joint证明同样阻断。
[完整offline绑定](../../tests/e3_host/q2_old_producer_admission_retry_offline.py#L299)
另在每阶段将archive allocation reserve补足manifest固定最大值，record reserve固定65536/4，
然后复核同设备聚合、每设备free及全局20MiB/384，不因实际小archive减少写前预留。

以上证明严格模型的规则与首错分界完整，**不证明人工snapshot就是全部真实时点上界**。
记录文件最多三payload block、子目录/parent各一block的源码注释只能覆盖所列mapped objects的
条件说明；本轮未取得适用ext4构建/创建算法、attr/security/quota/allocator、并发、journal/审计和
sync隐式分配的独立上界，因此不能从“表内有所有step”推出峰值≤64KiB/4或最大archive预留已足够。
FS2源码矩阵、FS3准确操作/首错/模型覆盖表现为 **OFFLINE_COMPLETE**；双parent实际资格及
完整峰值/持久性仍 **BLOCKED_MISSING_APPLICABLE_FACT**。先将已有适用原件字段绑定上述
UNKNOWN；若已有材料无法证明且必须新增source/profile/权限/实际fixture，才列准确受影响
supplement，不把缺事实转为实机试写或CI借证。
