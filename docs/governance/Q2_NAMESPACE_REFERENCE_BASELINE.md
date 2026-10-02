# Q2 namespace reference：待批准文档基线

2026-10-02 +08:00；Authority：Owner；状态 **PROPOSED / Gate OPEN**。
本件仅登记已经提交、经独立读审修正的准确候选，不是 Owner B 或 CLOSED C。
三文档内“尚无准确 A commit”是提交前的历史草拟状态；现在的准确 A 由本登记定位，
三文档原字节保持，不据此补写 Owner 决定。

- Scope：`LH-Q2-NAMESPACE-REFERENCE-v1`，拟闭合 **NS1–NS2 only**。
- Gate R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- Direct pinned source：[program-repository-documentation-gate.md](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)。
- Direct source SHA-256：`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`；本轮 executor 直接读取并核对，无 Private SOP 内容进入 Public。
- Documentation A：`dfdd653dd48388d8ab1a2554d16bf5b610edba10`。
- A tree：`763bec60189e801913c66186c9f83543c1083452`。
- A parent：`38a9e15697469f6590e54ddd89754a5d3344f23e`。
- Owner mandate、Owner-only decision authority、no exceptions 与禁止自动改变采用规则继续采用根 [AGENTS.md](../../AGENTS.md) 的声明。

| Authoritative document at A | SHA-256 |
| --- | --- |
| [需求](../a2-execution/q2-namespace-reference/REQUIREMENTS.md) | `e00c6ceae866d1ca6d8111b5440220d327f70701eb6e72d840ecc88b513bf5db` |
| [架构](../a2-execution/q2-namespace-reference/ARCHITECTURE.md) | `7d1a9fa9dac7ab17e0de351bcde4be381ead708b091a23d9e645d31510fbf564` |
| [实施计划](../a2-execution/q2-namespace-reference/IMPLEMENTATION_PLAN.md) | `24698ea512ed510bde894771b316b44343c1c7a1ecbb09a7f91ad240c24c6ea0` |

[设计说明](../a2-execution/Q2_NAMESPACE_REFERENCE_DESIGN_20261002.md)与三文档同在 A；
没有新 collector/test/prototype、依赖、配置或现场采集。已 CLOSED 的 FILETYPE/H07
修复属于独立既有范围，不能作为本 namespace 范围已开始实现的证据。

拟批准 NS1 的固定 standalone collector/source/IPC 合同及 NS2 的 synthetic 和明确 supplied
isolated native fixture 资格：固定普通身份的 G/R/O 三进程，限 own 与两个内部 fork PID 的
status/pid/mnt FD 来源；固定 proc→nsfs 两叶例外、pidfd、16 帧、两 nonce、全部资源和原
30s 双钟界。只有已经存在并准确绑定的普通监督和原生审计/收件来源适用；缺失即 BLOCKED，
不 provision、提权、改系统配置或重启退休设施。

原终端 provenance 与 endpoint execution integrity 是三文档明示的候选设计前提；尚无
Owner 接受决定，不从旧 storage premise 推出。NS1–NS2 的 fixture 不能充当原 host 来源，
不产生 `OWNER_DESIGNATED_TERMINAL_MATCHED` 或 consumer readiness。
NS3 原 host local-only 采集、NS4 consumer 集成及 P4 包发行/实际消费均排除；将来须各自
准确来源、artifact、费用/停止证据、scope 及 Owner 决定。

当前没有本范围 Owner B、独立 CLOSED C 或新 implementation D。只有准确 Owner 决定
被保留并由独立 bookkeeping-only C 登记后，才能从其后实施 NS1–NS2；不能将 A、C 和
实现 squash。Material scope/source/premise/permission/caps/用途变更保留 R 的 reopen 规则。
当前 `field_ready=false`、`allow_run=false`、`guest_executed=false`，真实正常链计数为 0。
