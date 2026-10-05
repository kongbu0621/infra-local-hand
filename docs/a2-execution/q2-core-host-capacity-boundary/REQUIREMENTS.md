# 核心单次验收：host 容量边界修订需求

- Authority：Owner；状态 **PROPOSED / Gate OPEN / NOT APPROVED**。
- Scope：`LH-Q2-CORE-HOST-CAPACITY-BOUNDARY-v1`，仅 B1–B3。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；根 AGENTS 的直接来源、完整性、Owner mandate 与无例外规则保持。
- 本文与 [ARCHITECTURE.md](ARCHITECTURE.md)、[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) 构成待决定的准确 A。未获本 A 的 B 与独立 C 前不实施本修订。

## 1. 目标与事实

目标仍是既有 `lhqcore-20261005a` 的 H01 真实任务及结果回收 → Q4 运行中取消 → H11 自身 ledger 恢复。
本修订不新增一次执行权、不新建批次，不增加核验项目或生产能力。

原批准 A `0b0f445a36232f6bcd32c395b642f9a6b259d2db`、独立 C
`7ac69c0bd4401812b782b75005d8b63936d90a77`、实现 D `27928b35e4406f7cfbbd360bccf0e0a8c4d7ea03` 保留。
最新事实基线 `26421d723499dde013964aab89c37da839613cff` 只更新来源核查，没有执行新 marker/request。

其 `docs/a2-execution/evidence/q2-core-next-host-source-20261005.json` 的原 bytes SHA-256 为
`92b5b4f73ad5990f839edc0d0b08b83b6123b8016212579bea98042412022831`。
44/44 host 原件匹配固定归档，不能据此证明归档覆盖全部历史承诺，也不能把归档字节数当成未释放预留。
六份 guest 归档和原 guest source horizon 不提供 host 完整账；两项 null 也不是两份丢失文件。
目前没有可从这些已查原件推导完整更早 host 未释放 byte/inode 金额及共享池关系的转换。
本 A 采用这份报告作为收窄保证的已知事实，**不把报告变成历史完整性证明**。

## 2. 唯一请求改变的保证

受影响的原条款为 next A 的 REQUIREMENTS §2、§4、§5 及 ARCHITECTURE §6、IMPLEMENTATION_PLAN N1/N2 中，
要求本次 host 启动前把更早 host 历史承诺完整求和并逐设备计入的部分。
原 binding/finalization 及更早约束若有同一 host 完整账准入要求，也仅在下述固定单次范围由本修订替代。
不改变任何 guest 历史账、当前身份、资源限制或执行验收条件。

| 原要求 | 本 A 请求 Owner 接受的替代条件 |
| --- | --- |
| 旧新 core 128 MiB/32 另加全部更早 host 未释放义务，完整性不明即阻断 | 只对本未消费批次核验明确的旧新 core 128 MiB/32 当前可用量；更早 host 集合、金额和共享池关系保留 UNKNOWN，允许这项特定历史未知不单独阻断此次 host capture |
| 需要完整 host 历史准入才能发行 | 只声明当前 capture 容量条件通过；`complete_host_admission_proven=false`，从不声明排他空间预留或历史账完整 |

这是真实降低容量证明范围，不是算法等价优化。它必须经 Owner 明确决定，不能把普通“继续”当成批准。
旧资料、旧承诺和原失败均保留；没有释放、退款、抹零、重分配或认定其它义务不存在。
早于旧 core 的历史合计金额为 null/UNKNOWN，不写成 0；不能用两 core 的已知小集合冒称全部集合。
不授予更早任务再次执行、继续写入或使用本次预算的权利。

## 3. 精确可数条件与保留限制

| 固定承诺 | bytes | inodes | 权威来源 |
| --- | ---: | ---: | --- |
| 旧 `lhqcore-20261003a` host capture | 67108864 | 16 | 原 next A 固定旧承诺及严格绑定的五原件 |
| 本 `lhqcore-20261005a` host capture | 67108864 | 16 | 原 next A 已批准但未消费的新一次 |
| 当前 held anchor 需满足的可用量 | 134217728 | 32 | 上两项相加；不是更早历史合计 |

两行均绑定既有同一个 protected anchor；原五文件实际读取和当前完整 anchor/writer 身份检查继续成立。
当前 `f_bavail * f_frsize >= 134217728` 且 `f_favail >= 32`，输入必须为有效非负整数，`f_frsize>0`；
负值、未知、设备/身份漂移、读取失败、晚返回或原 deadline 失效一律拒绝，不能以本修订放行。
只在原同一 900 秒 live caller、原 pre-marker 位置取得有界观察；不增加探针、连接、挂载、quota 或后台程序。
没有 caller 自选历史行的接口，也不允许填 `2 MiB × 历史次数` 或把 guest pool 移成 host grant。
本固定证据前提若被新的明确 host 预算/共享池证据推翻，应停止受影响范围并按 R 处理，不能隐去矛盾继续发行。

旧新 core 的 128 MiB/32 保留条件不因旧五文件仅 9318 B 而退款。本次实际受控写入仍为 64 MiB/16，
仅原六文件、原角色上限、双流合计 52 MiB、写前累计限制及写后/fsync 后实际分配采样均不放宽。
原 900/800/750 秒窗口及各阶段 reserve、guest 24+12 历史行/46 quota 行/全部旧新计费、
旧 scope 双观察、凭据/UID/GID/PID/权限/no-follow/no-atime/whole-file 与来源校验全部保持。
固定 runtime candidate/wheel、field 三文件、wire/私有输入/82 output members/六持久文件集合及格式保持。
只允许 host 同一 live 返回增加明确容量说明，原 receipt 与 `capture_accounting` 不改义。

## 4. Owner 需要知道的后果

`fstatvfs` 只证明观察时刻的可用空间与 inode，不会占住空间，不覆盖未知旧任务或共享 VM 镜像的后续增长。
同设备可能存在未计入的历史承诺和并发写入；因此不能保证新任务或结果写入一定完成。
ENOSPC、EDQUOT、IO 错误或观测超限仍停止，且可能连完整失败 receipt/证据都写不齐；不得补造 COMPLETE。
保留能够取得的原文件和准确失败事实，不重试、重连、删除、覆盖、扩大预算或补发另一次。
原 `full_filesystem_peak_proven=false`、本修订的完整历史准入 false 和排他预留 false 必须在成功 live 返回中同时可见。

## 5. 完成标准与执行终点

B1：实现并独立验证本固定 host 条件和真实边界报告，原限制及拒绝路径保持；新修订 A/B/C 与准确 D 绑定。
B2：准确 D 的完整 source/installed/CI 及真实私有来源、同窗口双构包校验通过，才登记准确 release digest。
B3：继续使用现有 N1–N3 的唯一未消费机会，旧 scope 准入通过后完成原 H01→Q4→H11，并返回真实结果/失败。
三项并非新的一轮执行配额；marker 已存在或输出冲突仍拒绝，本次失败仍不授权第三批。
本修订不关闭 production E3，也不恢复 namespace/watchdog、内核/硬配额研究、E4–E6 或 NAS 支线。
