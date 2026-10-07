# Journal 扫描工作量修正：准确待决基线

2026-10-07（Asia/Shanghai）。**OPEN / NOT APPROVED**，没有本范围Owner B或独立C。
Scope `LH-Q2-CORE-JOURNAL-SCAN-WORK-v1`，仅W1–W2；本文不授权实现或现场动作。

- R / source：`kongbu0621/engineering-sop`，`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- 沿用本会话已直接读取的[固定规则](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)，
  既有源SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- Mandate/Authority：Owner；exceptions：none；准确批准、历史顺序和实质变化重审规则不变。
- 准确A：`42a66be98c45e817e866d3fb86a1c184c2ce55f9`，tree
  `30f3be0a4f2e145095bb4ccaa0b40087f8f99e81`，parent
  `8c58f093a3fc923fb078811622fb2691448e81fc`。A只含三文档，没有源码、测试或配置。
- [需求](../a2-execution/q2-core-journal-scan-work/REQUIREMENTS.md)、
  [架构](../a2-execution/q2-core-journal-scan-work/ARCHITECTURE.md)、
  [计划](../a2-execution/q2-core-journal-scan-work/IMPLEMENTATION_PLAN.md)。

| A文档 | SHA-256 |
| --- | --- |
| REQUIREMENTS.md | `632aeecb163ad6e496a917fd73f9230aca1144d1e91050c78c8abff2b4d5ae38` |
| ARCHITECTURE.md | `52d75a0c689ae1ed5321a2b5fde5061084fd05c267cac9cf012924a97eac2e96` |
| IMPLEMENTATION_PLAN.md | `ec8f299e7cd9d9c0fc10eaa34e0ff75b0276fc2c863b753d4f8c109d7fc025b2` |

## 证据和本次审查

[MB2现场记录](../a2-execution/Q2_CORE_JOURNAL_MAPS_BUDGET_FIELD_20261007.md)已明确
`FD_TOTAL=262145>262144`、checkpoint1、marker false、SSH0，维护和业务未启动。
本次Owner截图再次显示该已推送结果；没有新增运行，也没有独立认证原始流。
旧maps失败和当前FD失败仅是首次拒绝值；既不证明只缺一个条目，也不证明512 MiB足够。

本轮三项独立只读审阅分别核对工作预算、结果协议/来源边界、维护及核心接续路线：

- 旧FD_TOTAL未包含全部初始snapshot工作、复核stat和匹配stat；新方案明确计量实际调用。
- 全局PID/task/FD漂移、认证与15s、maps、AS、读取可见性仍可拒绝，不能承诺提额即通过。
- 固定progress记录已观察前缀，严格区分scan_complete和父层writer准入；无额外读取。
- 两维护源当前65494/65453 B，分别只剩42/83 B；方案提前覆盖局部源界及guest传输的
  连带变更，保持root payload/argv/其它输入界，避免实现中再次临时扩大范围。
- 明确现有核心的旧boot等式、仅三旧profile与已消费05c的接线缺口。该后续修订可提前
  设计，但本A没有第五批完整合同，不能当作第五批的实现/发行/执行批准。

审阅指出的maps计数关系、初始PID未完成关系、REPORT失败完成关系、成功maps接受上限、
时钟非null及scan_complete不等于writer准入等歧义，均在冻结A前修正。
文档链接、完整Git引用、长度/hash与差异格式检查通过；远端A tree与本地审阅树相同。
本次无源码/测试/运行配置改动，无新增测试执行或CI成功声明，无sudo/proc/SSH现场调用。

## 请求Owner决定

下面是待决请求，不是收到的批准：

> 按原R，批准A `42a66be98c45e817e866d3fb86a1c184c2ce55f9` 的
> `LH-Q2-CORE-JOURNAL-SCAN-WORK-v1`，关闭W1–W2 Gate。按三文档以固定2097152次
> 实际FD stat预算替代旧FD累计门，加入严格v2进度，并仅调整两维护源及guest源长度界。
> 保留完整扫描、身份/writer校验、其它限额与原期限。先记录准确B和独立C，再完成实现、
> 验证、发布及准确候选CI/冻结，随后允许原session的一次替代预检，全门通过同窗完成
> 原journal维护。旧窗口继续消耗，不重试、补采、自动调额、清理或扩展支线。
> 本范围不执行新boot核心采用及H01/Q4/H11。

批准前只继续提案和既有未受影响CLOSED工作。新预算/协议/源界不属于已完成MB1授权。
本地Codex下一步不得直接重跑旧交接；应先核对准确批准，再执行本方案W1–W2。
