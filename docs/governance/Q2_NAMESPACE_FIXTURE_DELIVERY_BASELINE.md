# Q2 namespace fixture delivery：待批准文档基线

2026-10-03 +08:00；Authority：Owner；状态 **PROPOSED / Gate OPEN / AWAITING OWNER**。
本件只登记已经提交并通过独立只读终审的准确候选，不是 Owner B、CLOSED C、implementation D
或现场发行。四文件中“尚无准确 A commit”是提交前的历史状态；本登记给出准确 A，原文件字节不改。

- Scope：`LH-Q2-NAMESPACE-FIXTURE-DELIVERY-v1`，拟关闭 **F0–F4 only**。
- Gate R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- Direct pinned source：[program-repository-documentation-gate.md](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)。
- Direct source SHA-256：`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`；本轮 executor 已直接读取并核对。
- Documentation A：`ad5abaee642cba02d997149badf75a08c219a35c`。
- A tree：`871dc54f4caa2284b39f83bfacac6a6f8c75a1b5`。
- A parent：`fd23308bb0e018894b02e49f8b9f5e9c43cfd286`。
- Owner mandate、Owner-only decision authority、no exceptions 和禁止自动改变采用规则继续采用根
  [AGENTS.md](../../AGENTS.md) 的声明。

| Candidate document at A | SHA-256 |
| --- | --- |
| [需求](../a2-execution/q2-namespace-fixture-delivery/REQUIREMENTS.md) | `e05a3f6e6d2717fddbb74412fecdb1c99b61624a2be4c896ce5f6b3f594c664c` |
| [架构](../a2-execution/q2-namespace-fixture-delivery/ARCHITECTURE.md) | `6c297bc507495c875d9e0a62a1c1b3156b75e487027268fa8444c34132d34fa9` |
| [实施计划](../a2-execution/q2-namespace-fixture-delivery/IMPLEMENTATION_PLAN.md) | `e6d7baedb61fca1726d3e37df9d3060dee052b61038c20cfe842aaa2553914d1` |
| [设计复核](../a2-execution/Q2_NAMESPACE_FIXTURE_DELIVERY_DESIGN_20261002.md) | `4b2978866c0f7861d9604198e594c8aa7f425832b2e0d9875456fa4e9d421386` |

三份权威候选文档和设计复核共同固定完整 conditional route：F0 只从保留原件离线绑定唯一 target、
carrier、root anchor、既有 sealed native watchdog W、runtime、来源和全量费用；F1 在独立 C 后实现
standalone G/R/O、RAM bootstrap/guardian、root supervisor、收件和 synthetic validation；F2 冻结并
验证准确 D、bundle/context/runtime；F3 在全部门通过后只发一个 carrier request、最多一个
`BATCH_RELEASE`，顺序执行最多十二个唯一 native case；F4 保留 wait/stop、空树、三层 EOF、费用和
outer seal。缺准确身份、退出、EOF、计数或账目时不产生成功结论。

候选要求 W 在目标上已经存在且字节、loader、source relation、权限、资源和状态映射全部可由固定
来源资格化；本范围不安装、上传、现场编译或替换 W，不补建账户、manager、unit、mount、系统依赖或
内核配置。若这些静态输入缺失，F0 必须保持 `NOT_ISSUED`；若只在已发连接后发现不成立，则按完整
状态/EOF/账目证据进入 BLOCKED 或 UNKNOWN。登记 A 不证明这些输入已准备，也不证明 field readiness。

旧 scope `LH-Q2-NAMESPACE-REFERENCE-v1` 的 proposed A
`dfdd653dd48388d8ab1a2554d16bf5b610edba10` 现登记为
`SUPERSEDED_PROPOSAL_NOT_APPROVED`。其[原基线](Q2_NAMESPACE_REFERENCE_BASELINE.md)、三文档和
[只读 readiness 复核](../a2-execution/Q2_NAMESPACE_FIXTURE_READINESS_REVIEW_20261002.md)保持历史原件；
旧候选从未取得 Owner B 或 CLOSED C，新 A 不追认、修改或继承旧候选的实施权限。

当前没有本范围 Owner B、独立 bookkeeping-only CLOSED C、implementation D、private delivery、guest
连接或 native run。后续必须保持 **R → exact A → exact Owner B → independent C → D**；A、C 与实现
不得 squash。任何 material target/source/premise/property/cap/budget/use 变化继续触发 R 的 reopen
规则。当前 `field_ready=false`、`allow_run=false`、`guest_executed=false`，真实正常链计数为 0。
