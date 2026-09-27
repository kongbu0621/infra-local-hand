# Q2 监督器启动失败后单次新批次：提案基线

2026-09-27。Authority：Owner。状态：**PROPOSED / OPEN**。

- Scope：`LH-Q2-SUPERVISOR-STARTUP-RETRY-v1`。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；直接可读来源、完整性、Owner 权限、无例外及变更规则沿用根 `AGENTS.md`。
- 准确三文档 A：`47b351b2b943bf1d6f1c71cfeb031157a2eb70cc`。
- A tree：`2f247c854d9b1553e2b85922897ba5271c244686`。
- 此范围尚无 Owner B 或独立 CLOSED C；本登记不是关闭，不含新批次实现。

| A 中的权威文档 | SHA-256 |
| --- | --- |
| [REQUIREMENTS.md](../a2-execution/q2-supervisor-startup-retry/REQUIREMENTS.md) | `fc6dd6b0c7b7081da61c0c200ea4ebbaf1e6baac4364b70e4f8927e6614c2139` |
| [ARCHITECTURE.md](../a2-execution/q2-supervisor-startup-retry/ARCHITECTURE.md) | `fc4ea078aab64f64ba59dc9f5247e4a91e4d1237ed56488014cb516ae7313773` |
| [IMPLEMENTATION_PLAN.md](../a2-execution/q2-supervisor-startup-retry/IMPLEMENTATION_PLAN.md) | `b3eff564624fae0c4d98bb10d5cd47a1372b0a445f3f4c3bae1f0e863e3b9f6b` |

## 已完成修复与新运行的区别

修复候选为 `b49d3df3d1e76813faf08e59ab4975e25279c2fc`，tree
`2d957ccf1d9cbdf5e538189c6b68d56f34590a42`；准确 wheel SHA-256 为
`c077a8f8aa2f0c3147228602746fd459a6d13267df299a84835331ad35ef158b`。
源码修复、实际验证、保留的中间失败及边界见
[监督器启动修复记录](../a2-execution/Q2_SUPERVISOR_STARTUP_REPAIR_VERIFICATION.md)。
这些源码修复和发布属于已有 CLOSED 开发范围，已获授权，不在此重新请求批准。

旧 `LH-Q2-CPUQUOTA-RETRY-v1` 在 A `d8e49617efecae199b0874f183530794f8c36e6a`
只允许冻结候选的一次 300 秒运行；该次已发行并保留 INCOMPLETE。现在替换 runtime、
建立独立新状态和再开一个窗口是具体的新范围，不能因旧 ledger 空或失败较早而重放。
新方案保留此前 CPUQuota parser 失败及监督器实际执行后的失败、全部来源和未完成证据。
旧三文档、A/B/C、原期限、原安装、authority、账本及结论不被重写。

## 一次完整拟议批次

批准后按 R → A → B → 独立 C → D 顺序，实现并验证专用双前驱鉴证、累计计费和
一次交付工具；固定 D 后，在同一隔离 guest 中执行一次最多 300 秒的管理/捕获批次。
准确复用原普通账户、manager 配置和七个各 1 MiB/128 inode 的根，仅在两个历史
ledger、所有消费材料、现场 quota/成员及历史 FAILED 实例均符合条件时继续。
历史失败服务不 reset、不重启、不删除；新身份与所有前驱去重，新对象均 create-only。

新旧空间累计保留 256/32/64/64 MiB 四类总上界和原 inode ceilings，四个 Q1 域
196 MiB 承诺仍计入。本次新增时间/CPU 显式有界，其他 memory/pids/output 与角色
上限不扩大；一次 300 秒包括首次探测、安装、固定 host.inspect 三阶段、退出/EOF、
独立停止、收集和封存，不按阶段刷新或自动第二次执行。

不新增账户/project、重设 quota、清理旧证据、增加 capability/系统依赖、扩容或
触碰现役服务、GX10、NAS、Q3 接纳、H06–H13、production 或 E4–E6。
原有 S1 与 Ledger A2 不重新开启。Q2 接纳仍需本次实机原始证明；新成功也不能补判旧失败。

三文档经过独立只读复核。Owner 可以一次批准准确 R/A 和完整范围，范围内不逐项询问。
取得该准确 B 后，用独立关闭登记 C 保留决定，再实施 D；本提案不自行构造 Owner 决定。
