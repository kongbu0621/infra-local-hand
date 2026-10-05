# 核心 host 容量边界修订登记

状态：**OPEN / NOT APPROVED**。Authority：Owner。
Scope：`LH-Q2-CORE-HOST-CAPACITY-BOUNDARY-v1`，B1–B3 only。

R 保持 `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；直接固定来源
`kongbu0621/engineering-sop/docs/workflow/program-repository-documentation-gate.md`，原 SHA-256
`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
Owner mandate、Authority、无例外及变更规则保持；本登记不是新的 Owner 决定。

准确三文档 A：**`f491b15514ed0e05f7e1924785a3f7d162dae90f`**；tree `318a7ddb656c9256ab4348379dcb12848ef82351`。
事实/源码基线：`26421d723499dde013964aab89c37da839613cff`，实际核心 D 仍为
`27928b35e4406f7cfbbd360bccf0e0a8c4d7ea03`。本轮未修改运行或测试源码。

| docs/a2-execution/q2-core-host-capacity-boundary 下的权威文件 | SHA-256 |
| --- | --- |
| ARCHITECTURE.md | `fbe274526b6058c683103256ecb6b57dee8fd360321972f3bef0acd601687353` |
| IMPLEMENTATION_PLAN.md | `5851022f390b2b21a06a9d8fef60dae2aaa4c24fe242ce2bb81f769de36b8704` |
| REQUIREMENTS.md | `88e0b216a238eab35dd8e04f82ac194f49a9e587739d0d1cae29182b599c9924` |

[需求](../a2-execution/q2-core-host-capacity-boundary/REQUIREMENTS.md) ·
[架构](../a2-execution/q2-core-host-capacity-boundary/ARCHITECTURE.md) ·
[实施方案](../a2-execution/q2-core-host-capacity-boundary/IMPLEMENTATION_PLAN.md)

## 阻塞与最小修订

44 份历史 host 原件已找到且匹配；“继续定位原件即可接线”的旧判断不足，完整 host 承诺的覆盖、
金额和共享池映射并未因此得到证明。原 guest source horizon 不可扩大为 host 完整集合。
这不是可在 N1 内补一个推导公式或把 null 填零的代码缺陷。

本 A 明确请求降低这一项 host 历史容量证明保证：只对原未消费 `lhqcore-20261005a`，
保留旧新 core 的固定 `134217728 B / 32 inodes` 当前可用量条件；更早 host 仍 UNKNOWN，
不退款、不释放、不宣称不存在，也不作为该次 capture 的独立阻断项。
未知共享增长可能造成任务失败和证据不完整；当前观察不预留空间。
原实际写入/观测限额、当前身份与凭据、guest 完整历史计费、旧 scope 双观察及停止规则全保留。
本修订不增加机会、不重建存储，也不新增 host 配额/内核证明支线。

## 独立复核与可实施性

两路只读审查核对原 next A §4/§6、binding amendment 的 guest-only 前提及准确 26421d 记录，
确认现有原件不能推导完整 host 历史金额。独立三文档复核未发现阻断冲突；字段/窗口与现有代码对应。
`verify_prior_originals` 当前调用 `observe_capture_floor` 后丢弃返回；批准后在原点保留该条件、
沿原栈验证并放入同一 live 返回，即可明确区分本次条件与未证明的完整历史准入。
原 capture_accounting 五键、wire、field 三文件与六个持久文件保持不变。
这项审查不冒充实现、源测试、实机或成功验收；本轮只有提案与登记，原 release 仍为空。

## 准确决定建议，尚未收到

> 按原 R，批准 A `f491b15514ed0e05f7e1924785a3f7d162dae90f` 的 `LH-Q2-CORE-HOST-CAPACITY-BOUNDARY-v1`，关闭该范围 Gate，执行 B1–B3；先独立 C 再实现。接受更早 host 历史承诺保持 UNKNOWN，不单独阻断这一次 capture；当前可用量检查不构成排他预留，空间竞争可能导致任务或证据回收失败。沿用已批准且未消费的 `lhqcore-20261005a` 一次机会，保留旧账不退款；原身份、凭据、guest 计费、限额和停止条件不变，支线暂停。

只有收到准确 B 并作独立 bookkeeping-only CLOSED C 后，才实施本新增保证边界。
已批准 next N1–N3 无需重复决定，仍按原未改变的边界有效；不能用其既有 B 代替本次变化的决定。
后续 B1/B2 完成必要实现和准确验证后，由本地 Codex 复用既有入口执行原单次 H01→Q4→H11。
本登记未创建 marker、发出 carrier、连接 guest、改系统、清理或重试。真实核心验收尚未完成。
