# Q2 首次父目录增量与账单绑定实现复核

2026-09-29 +08。接续[普通操作者 v2 组件](Q2_ORDINARY_WRITER_IMPLEMENTATION_REVIEW.md)，
在既有 CLOSED H2/H3/H4 内完成首次分配观察与显式计费组件。
完整 Q2 仍未验收，原 startup batch 仍 NOT ISSUED。

## 准确实现和范围

| 项目 | 准确值 |
| --- | --- |
| 实现 D | `530a2a45bc6e96270771ccf266793e471d8408ee` |
| D tree | `ce3ac229ed0a083875fb49ddcfa2f086fd0833f5` |
| Parent | `bd3f5e038f9517b702590aa0ef6fdda99757562d` |

原 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 的直接原件已复读，
SHA-256 为 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
H A `8402f0cc82d8a0ac0b9a56716bf276f41cafea37`、独立 C
`271c07cd16140aa5942dcf3fad468003c58b6b0e` 及准确三文档不变。
独立范围复核确认：留存已有首次 fstat、原池内费用重分类和纯跨输入验证属于
H2/H3/H4；没有扩大额度、读取范围、持久对象、来源采用、时钟或现场动作。

修改 `q2_host_window_record.py`、`q2_host_window_billing.py`、
`q2_reconciliation_bootstrap.py`，新增两份独立测试。
冻结 runtime `b49d3df3d1e76813faf08e59ab4975e25279c2fc`、旧准确交付包、
现场 loader、内核/文件系统资格及原拒绝门保持。

## 修复的准确问题

旧 writer 已验证 marker 子树分配 M 与首次父目录正向增量 G 满足 M+G≤65,536，
但旧 bill/v1 只把 M 记入 marker 池 actual。旧 future 为 C−M，C=65,536，
所以旧 actual+future 仍为 C；本轮证据不支持“旧总预算已经少算 G”。
修复对象是 G 的证据绑定和同一池内 actual/future 分类。

| marker 池 | 旧 bill/v1 | 显式 bill/v2 |
| --- | --- | --- |
| actual bytes | M | M+G |
| future bytes | C−M | C−M−G |
| actual+future bytes | C | C |
| G 新增 inode | 无独立表达 | 0 |

G 只承接首次端点观察的非负净增长，不证明变化由本次创建独自产生、没有并发兄弟写入，
也不证明中途分配峰值、allocator/属性 inode、同步或持久性。
父目录原有费用 B 的分类与既有覆盖仍为 UNPROVEN；新接口不将 B 填零或归入 capture。
它仅验证这一有限费用分摊，不能证明完整 host 清单或完整共同账单。

## 首次观察的固定绑定

普通 writer 在原 `_budget` 已有 fstat 处保存完整首次 parent metadata；
后续 verify/evidence 不替换它。`first_allocation_observation()` 只从仍持有的成功记录
复制 RAM 缓存，没有新文件访问、重新采样、时钟刷新或当前有效性声明。
失败/已关闭记录、旧 v1 记录及历史只读回执不能倒填这个首次事实。
已有 consumption v1/v2 字段保持，新观察使用独立
`local-hand-q2-host-window-parent-allocation/v1`。

观察严格绑定原 intent bytes、binding、precheck、window、固定 parent before/after 和
首次 marker snapshot 摘要；span 固定为 `precheck-parent-to-first-marker-budget`。
marker snapshot 与 parent fstat 是顺序观察，不是同时全局快照。
新纯计费接口从完整 metadata 计算 G；负差拒绝，不能借旧 `max(0)` 变成合格零增长。
身份/保护字段漂移、跨 intent/window/snapshot 调包及超过原上界也拒绝。
G=0 仍不能证明期间无增长，或解除任何未证明项。

## 显式计费与入口隔离

`quote_host_parent_allocation`、`validate_host_bill_parent_allocation` 与
`validate_marker_transition_parent_allocation` 使用显式 consumed bill/v2，
precheck 仍绑定原 bill/v1。完整 observation 被纳入 inventory 摘要。
新 summary 将子树 M 与父增长 G 分列，并同步调整 actual、future、capture 与实际设备项；
只抵扣原 marker 池一次，保持原 64 KiB / 4 inode、旧义务、旧扫描和共享池。

窄 profile 拒绝旧 scan 的 parent/祖先根、同 parent 路径或相同 device/inode 别名，
并拒绝任意 kind 义务已覆盖 parent/祖先的情况。它不靠删除旧义务、放松双重抵扣检查，
或把整个混合用途父目录改成 capture 来迁就接口。广义父基数分摊仍待准确来源与覆盖关系。

`validate_ordinary_host_window_parent_allocation` 进一步绑定准确 raw、precheck bill、
consumed bill、原 window、plan 和机器关系，成功仅为 `INPUT_CONSISTENT`。
显式 `joint_quote_parent_allocation` 返回联合账单 v2 的局部计算结果；
旧 `require_joint_admissible` 及旧生产 loader 不接受这份新版本。
`baseline_parent_cost_proven`、`full_bill_proven`、`filesystem_proven`、`field_ready`
固定为 false，父基数状态固定 UNPROVEN；算术/容量通过不成为来源采用或执行许可。

## 验证与复核

本地 Python 3.12.14、pytest 8.4.2，十四文件定向回归 **388 PASS / 22 SKIP**，
共 410 个不同用例。新增 84 项中，82 个纯验证通过；2 个真实普通身份用例在云端 root 下跳过，
加上既有 20 个普通身份跳过，共 22 项，不能记为通过。
独立新增输入组 75 PASS 属于上述回归，不重复累加。

新增反例覆盖跨 raw/binding/window/snapshot、metadata 类型/漂移/缩小/溢出、原池上界、
父覆盖/别名、重复抵扣、汇总篡改、plan/机器重封及旧版本拒绝。真实普通身份用例还覆盖
producer→bill/v2→transition 对接、getter 无新 I/O、深拷贝、后续 sibling 变化不覆写首次观察。
这些 syscall 用例仍明确模拟 readiness、boot 与 FS 资格，不能证明原主机持久性。

独立审查发现 standalone 新报价还需将 host/guest 与 raw-bound precheck 摘要逐项绑定；
已修复并加入两种直接换机和重新封装后与 plan 不符的反例。最终五件字节与准确 D 匹配，
必须修正项清零。独立 24 项 AST/字节边界检查全部通过；另核验 16 件冻结文件、9 个
关键函数 AST、H C 祖先关系、Python 3.10 语法和 diff whitespace。
两件冻结 supervisor/launcher 另与准确 runtime 基线逐字相同。

准确 D 的原生 CI [36536347779](https://github.com/kongbu0621/infra-local-hand/actions/runs/36536347779)
已完成，整体 **SUCCESS，3/3 jobs 成功**。

| 原生 CI | 准确结果 |
| --- | --- |
| Linux job `109301215664` | 源码 **2584 PASS / 51 SKIP**；独立 root collector **16 PASS / 0 SKIP**；wheel **94 checks / 292 commands PASS**；Plugin、smoke、重复 smoke 与归档成功 |
| Windows job `109301215728` | 源码 **636 PASS / 994 SKIP**；wheel **10 checks / 10 commands PASS**；平台 smoke 与归档成功 |

Linux 比前一准确源码 D 增加 84 项 PASS，SKIP 不变；完整 `-rs` 没有新增两文件条目。
结合准确源的 75+9 项计数及强制真实普通身份 fixture，确认新增 2 项真实普通身份用例通过；
不冒称取得逐节点 JUnit。Windows 新增 76 项平台跳过，由 75 项输入测试和观察测试整模块 1 项构成。
日志长度/摘要、准确源码和步骤结果保存在 native-ci.json。

准确机器记录见 [verification.json](evidence/q2-parent-allocation-20260929/verification.json)、
[independent-review.json](evidence/q2-parent-allocation-20260929/independent-review.json)、
[frozen-boundary-checks.json](evidence/q2-parent-allocation-20260929/frozen-boundary-checks.json) 和
[native-ci.json](evidence/q2-parent-allocation-20260929/native-ci.json)。
原生结果只属于准确 D；后继纯文档提交不冒领 D 的测试，历史失败 SHA 的红叉保留。

## 当前阶段与下一步

固定来源 L1–L6、wrapper 有限 profile、普通身份组件及本轮首次增量计费组件各自保留完成证据。
当前处于完整 Q2 执行前的资格与共同账单闭合阶段。
现场 indexed/12 KiB parent 尚无写前峰值与持久资格；完整历史/future/原生审计费用、
准确工具/环境来源以及首次远端前截止和完整停止关系仍未证明。

后续具体工作与准确边界见[现场资格下一阶段复核](Q2_FIELD_QUALIFICATION_NEXT_REVIEW.md)及
[准入计划](Q2_POST_SOURCE_ADMISSION_PLAN.md)。先完成按固定计划派生的监督域清单、
pending/queued/已绑定实例状态合同及 FS 谓词与来源映射；实际新增来源采用或监督准备
只有在方案确定后才形成受影响范围的准确 A，不要求重批整个 H。
本轮没有原机操作请求，没有 guest 连接、wrapper 运行、原机 marker 或批次消费。
