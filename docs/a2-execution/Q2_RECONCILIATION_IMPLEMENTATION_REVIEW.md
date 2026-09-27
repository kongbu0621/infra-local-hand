# Q2 对账实现与受限验证

2026-09-27。范围为 `LH-Q2-INSTALLATION-RESERVATION-RECONCILIATION-v1`。
本提交是已批准范围的受限实现，不是可发行交付包或现场验收结果。

## 授权与保留基线

R 为 `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；准确已批准 A 为
`c65ff4e25ea6373aabf8db25d304ee7614b96eb5`。Owner 原话、稳定仓库副本及事件
见 [决定记录](../governance/Q2_INSTALLATION_RESERVATION_RECONCILIATION_OWNER_DECISION.md)。
独立关闭 C 为 `1491765c64c60a63d6bddf10a049308e404885ca`，仅登记授权。
本实现以 C 为祖先，原 A 的三份文档字节保持不变。

冻结 runtime commit `b49d3df3d1e76813faf08e59ab4975e25279c2fc`、tree
`2d957ccf1d9cbdf5e538189c6b68d56f34590a42`、wheel SHA-256
`c077a8f8aa2f0c3147228602746fd459a6d13267df299a84835331ad35ef158b`
保持不变。旧 startup v1 源码和合同未改；未重建替换 wheel。

## 已实现的独立组件

| 组件 | 行为与边界 |
| --- | --- |
| contract / sources | 严格新 schema；固定 R/A/B/C、外部准确 D 与全部新旧工具闭包；12 历史树、15 单文件锚、47 分类来源、610 当前基线和五项 post-read 起点；两项当前 raw 不冒充历史 pin |
| billing | allocated blocks 与唯一 inode；仅两准确安装目标的 C/A/U 可终止 future；其它义务、实际对象和 owner 共池保持；四设备和真实 project 0 库存分别处理 |
| IO / records | 逐段保护路径和 held fd、O_NOATIME、全量元数据/内容比较；五固定文件的 create-only、fsync、seal；部分状态拒绝恢复，同值 sealed 只读 |
| backend / bootstrap / driver | 新 authority 与 source classes；完整现场观察、写前及发行前重新准入；原五文件 state 子预算和 stage 元数据预算；复用原 owner 装配而不制造旧 v1 许可 |
| delivery / HostStore | 内存双向有界传输、原双时钟及共同输出池；落盘对象的 fd/name/元数据/内容与目录精确成员验证 |
| collector | 原窗口内的只读来源、五文件 seal、保留性与 owner 实物链核对；不准备、不安装、不启动，不倒补原 caller EOF 或独立停止证明 |

本地真实来源 fixture 使用复原原件与准确旧证明，而早期测试中的 D/source 身份
是明确标记的合成占位，仅用于结构和来源算法。准确 Git D/tree/工具 blob 与
冻结 wheel 的核验必须在 D 提交后另行绑定；纯 decode 通过不证明 Git 成员关系。

## 复核发现和处置

已经修复：源码闭包遗漏新模块；live scan 未知字段及汇总伪造；普通账户文件
的准确 owner allowlist；四设备布局；project 0/零 hard 背景配额；总 allocated
扫描上限；clock-anchor stage 文件及预算；host 落盘对象与实际封存输入不一致。

另发现的跨进程一次性问题触发受影响范围重新 OPEN：A 的 I06、架构现场联合
鉴证及 P5.2 要求首次新持久写入前完成全量现场准入，但提前失败时没有 durable
消费事实，进程内 set 不能阻止下一进程重新计时。旧 startup 文档也没有该例外；
旧实现的早期 host intent 不能倒推授权。

已移除不安全的 host runner 初稿，公开 `run_host` 和 CLI 均在任何 window、
wrapper、现场历史读取或写入之前固定返回 `HOST_WINDOW_CONSUMPTION_DESIGN_OPEN`。
初稿及其当时合成验证仅作为私有被否决证据保留，不作为可运行交付。
拟议准入前 host 消费记录尚未实现。依固定 R 的 Document evolution 和 Traceability，
受影响顺序须先形成准确三文档及 Owner 决定；不把这项变化混入原批准。

wrapper 的严格 atime 保护、剩余绝对 deadline 对外层硬监督的绑定，以及 host
终端结果与实际 owner seal 的完整匹配，仍是恢复 host 路径时必须满足的原合同
检查；静态 BLOCKED 避免这些未接通路径产生现场副作用。

## 验证与可观察结果

具体工具版本、命令、准确文件摘要、通过和跳过数见同目录
`evidence/q2-reconciliation-implementation-20260927/validation.json`。
验证使用仓库准确 requirements-build.txt 的隔离 Python 3.12 环境。
检查范围是新增组件与实际复用的旧 startup/contract 入口，不冒称全仓测试。

真实本地文件、fsync 故障、路径替换、hardlink、双向 subprocess 管道、输出
溢出和 EOF 边界均有定向测试；现场观察/配额/cgroup 组合仍是合成输入。
当前命名空间无法映射普通 UID 的真实 chown，numeric /proc 枚举能力也不足，
相应测试保留 SKIP。当前挂载的 relatime symlink 在 readlink 前拒绝，未把
noatime 挂载下允许分支称为实测通过。

本轮未连接 guest、未进行现场 probe、未创建现场消费记录、未开始 300 秒窗口、
未发行 owner。现场 after 账单仍未知，旧 INCOMPLETE 保留，Q2/Q3 未验收，
production support 不变。P1–P4 组件进度不等于 P5/P6 完成；新 host 顺序准确
决定后，还须完成对应实现与验证，才可能在原唯一批次中条件执行。

## 准确实现提交之后的复验

实际实现 D 为 `8fd84521cdd25b455ff148e0c0fed6b5d8e39fe1`，tree
`5fb64e578d06e2954c1eedbc1b15e00069dc32a4`，已证明 C 是其祖先。复验从 D 的
实际 Git blob 导出 42 个工具文件（包含全部 11 个新模块），加载准确 D 的
校验器并使用 48 个真实输入 blob、5,686,734 bytes：47 分类来源、12 历史树、
610 当前条目、五项 metadata 起点与七项归并义务全部通过。冻结 wheel 原件
266,010 bytes，摘要与原候选相符，并与 b49d 的准确源码进行验证。

[准确 D 复验记录](evidence/q2-reconciliation-implementation-20260927/exact-D-source-check.json)
保留完整工具摘要、离线 manifest 摘要及真实结果。调用准确 D 的受控 host 入口
验证其在调用 guest builder 以前返回 BLOCKED；这次检查没有创建现场窗口。
该复验只证明准确代码/来源关系与入口阻断，仍不是可执行交付或现场准入。
