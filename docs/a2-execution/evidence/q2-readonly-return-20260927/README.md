# Q2 原机补证：独立复核与待决边界

2026-09-27。Owner 提供原 PRO6000/既有 Q1 guest 的留存材料回传包。
本记录接续[首轮恢复索引](../q2-history-20260927/README.md)，更正其“六份原始值仍缺”
和“preflight 仅有推导预期值”的当前状态。原件现已收齐；采集与准入分开判断。
新 startup 批次仍 **NOT ISSUED**，没有释放预留或改变原失败结论。

## 独立复核结果

| 检查 | 结果与准确边界 |
| --- | --- |
| 回传总包 | 38,014,204 bytes；SHA-256 与附件和先前终端截图一致 |
| 内部内容 | 全部 SHA256SUMS 条目通过；guest 3,102 条目/2,886 普通文件，host 49 条目/44 普通文件，逐份核对内容摘要和长度 |
| 原历史锚 | 从此前独立留存的 CPUQuota core 取锚，12/12 树快照、15/15 旧文件摘要完全一致；不是仅相信新包的 comparison 结论 |
| 重叠原件与载体 | 旧回传与新包重叠的 628 份文件一致；11 个 host 载体与首轮公开索引的既有 pin 一致 |
| 原件缺口 | 六份 reservation 原件现已收到；preflight 原件同时匹配旧历史树和此前推导值，来源已补齐 |
| 两个前驱 | authority、manifest、receipt、request、issuance、handoff 的既有摘要和引用关系匹配；新包未重复带回的第二 owner 输出和 policy 使用此前已留存原件 |
| 两个 ledger | 从归档 bytes 在 RAM 中独立检查，历史摘要、完整 schema、quick_check、generation=1、五张消费表为空均通过；本次采集未观察到 sidecar |
| 实例与七根 | 回传所记 boot 和四个 FAILED 实例身份匹配原证据，退出 3 有对应来源；七根身份匹配、采集前后元数据相同、成员为空 |

上述最后两项是对回传观察的离线核对，不是本次审阅者连接原 guest 完成实时准入。
没有执行上传的采集器或交付入口，也没有以 SQLite 打开原机数据库。

## 两项来源和五项保存偏差

第二 bootstrap intent 和 bootstrap-attestation 已取得原路径留存字节，但没有早期
独立单文件/全树 pin。旧源码及已锚定 plan/delivery 能核对结构和引用，不能复原
全部原时钟偏移与挂载观测，所以不能宣称这两份文件的历史字节同一性已独立证明。
[manifest.json](manifest.json) 固定两份准确摘要、字节数和本次来源；其前瞻性采纳
仍需在新的准确 A/B/C 中由 Owner 明确决定，原 startup v1 保持原准入规则。

采集说明披露：初始普通 sha256sum 读取使五个文件的 atime 前移。包内保留了所报
初始 atime 与之后的 stat，但没有原始初始 stat/该探测命令的完整捕获。因此：

- 已知保存偏差必须保留，不恢复时间戳，不声称满足了全部 metadata 保全要求。
- 三个受影响文件由历史树证明内容及其纳入的非 atime 字段；历史树算法不含 atime。
- 另外两个即上述无旧锚文件，不能将采集者“其余字段未变”的说明升级成独立历史证明。
- 若 Owner 采纳本次 post-read 基线，仅为此范围的未来比较起点；后续任何新变化仍须拒绝。

第二 staging 的原内嵌归档有 545 份文件，544 份与现留存字节一致；唯一差异为
Git index。独立解析确认 505 个 path/blob OID/mode/flags 及 extensions 相同，
差别在文件时间、设备和 inode 缓存。没有把该 index 字节改写成旧值，也不称该
staging 历史全树未变；本次完整清单仅可按新 A 采用为后续保持性比较起点。
精确范围为第二 staging 根及后代 609 项、旁置 intent 1 项，共 610 项；独立
forward-baseline 索引 SHA-256 为
`9b5b5ec8dd1516cb8807bf26f657c652079843a3669783db215a4f9c5dd5852e`。

归档 manifest 的 `mtime_ns` 浮点投影在多数条目存在纳秒舍入误差。复核使用 PAX
十进制原时间逐项比对 source_metadata，全部一致；后续不得使用浮点投影作精确比较。

## 容量与仍需的现场检查

三项安装峰值的旧下界 320 MiB 仍成立。补上两项旧 staging 和 recovery-stage
后，当前规则的更完整下界为 **365,694,976 bytes（348.75390625 MiB）/17,599 inode**，
超过原 **256 MiB/16,384 inode**，还未加新 staging 等费用。

第二 bootstrap 的 installation_reservation_bytes 实为 113,274,880：包含
46,166,016 的当时已保留安装费用和 67,108,864 的新增峰值，不能把整个字段再当
一笔新增安装额度。原 192 MiB 和恢复阶段同额声明属于同一义务。

拟议对账只处理原 192 MiB/8,192 inode 与第二 64 MiB/4,096 inode 的未用未来
余额；实际文件、两 staging、recovery-stage、owner/journal 共享池及其他承诺
全部保留。新包未收第二安装等完整当前树，不能给出精确对账后账单或保证可以发行。

本次七根的 project_id 是采集器配置值，不能当作实际查询的证据。实际 project/
inherit/UUID/硬限额/usage、父 cgroup 树、ordinary manager、配置/namespace、
全部计费目录与设备容量仍须在原唯一窗口内联合检查。当前材料也不能代替将来的
freshness 检查；预算不足、漂移或未知均停止，不发出新 owner。

## 可供 Owner 审阅的下一步

[需求](../../q2-installation-reservation-reconciliation/REQUIREMENTS.md)、
[架构](../../q2-installation-reservation-reconciliation/ARCHITECTURE.md)和
[实施方案](../../q2-installation-reservation-reconciliation/IMPLEMENTATION_PLAN.md)
将有限来源采纳、五项偏差处理、两项未来义务对账及全部现场前置写为一个明确变更。
Gate 仍 **OPEN / AWAITING OWNER DECISION**；本轮只交付文档和证据，没有实现释放逻辑。
Owner 不必再手工重采本次已收到的材料，也不应修复旧时间戳。

私有 Git 归档追加本次总包、逐文件清单、独立审阅和更新后的输入状态，保留首轮
commit；公开 manifest 只保存摘要、逻辑角色、统计和边界。原机路径和身份不公开。
上游固定 R 在本次云端审阅中已在线读取并核对原摘要；本地采集时的 HTTP 404
另行保留，不能据此宣称该本地环境已满足后续实现的规则可读条件。
