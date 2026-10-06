# Journal 诊断修复：一次替代预检的待决方案

2026-10-06。状态 **OPEN / NOT APPROVED**；没有本范围的 Owner B 或 CLOSED C。
本记录仅准备准确可审阅方案，不批准或执行任何新现场窗口、sudo、SSH、marker 或维护。

- Scope：`LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-v1`，仅 DR1–DR2。
- Gate 来源：`kongbu0621/engineering-sop`；原 R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- [固定直接规则](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)；
  既有源 SHA-256：`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- Mandate / decision authority：Owner；exceptions：none；原采用及实质变化重审规则保持。
- 准确 A：`ef46ac169fd9084875cb5c5148a9c4985ace680c`。
- A tree：`c4390249aa98c2e99cb2f39ab1a25669b6eb63c2`；parent：
  `aba18e33f79295f3df1964606e389297d1a8a26a`。
- 三文档：[需求](../a2-execution/q2-core-journal-diagnostic-resume/REQUIREMENTS.md)、
  [架构](../a2-execution/q2-core-journal-diagnostic-resume/ARCHITECTURE.md)、
  [计划](../a2-execution/q2-core-journal-diagnostic-resume/IMPLEMENTATION_PLAN.md)。

| A 的三文档 | SHA-256 |
| --- | --- |
| `REQUIREMENTS.md` | `bccfd1d244bcd250a4c9c5c1fdb4aad4401d5398f0e9c3939d5b7ab0257d27d6` |
| `ARCHITECTURE.md` | `72cee2ad2ce82fa47bd8a40dc8e3e74da5de1ea9e8674d22c3c82df8cd04b543` |
| `IMPLEMENTATION_PLAN.md` | `74eb2b9c8c45b159131af785ce14976b104923411b307b8f3d4f7269124d6692` |

## 新决定仅覆盖哪里

[原 T3 现场记录](../a2-execution/Q2_CORE_JOURNAL_TERMINAL_AUTH_FIELD_20261006.md)已明确关闭唯一
替代窗口。没有 marker 不返还窗口；648 B stdout 只留长度/摘要，历史具体原因及 root payload
是否执行不可恢复。已有 `ac08b51` 和后续隔离诊断修复均不能变成重跑依据。

当前新修复 `aba18e33f79295f3df1964606e389297d1a8a26a` 已推送，tree
`628ec75bd3b34615d4896607942d9cbdd2bb85d4`；本地验证 **428 passed、3 skipped**，
[CI 37450280680](https://github.com/kongbu0621/infra-local-hand/actions/runs/37450280680)
已完成，结论 success，三个 job 全部通过。准确 A 冻结时的 pending 文字保留为历史状态；
本条登记后续 CI 结果，不修改 A 的三文档，也不等于 DR2 现场准入。
唯一新增授权是：修复验证、发布及准确绑定通过后，允许原 session 再使用一次明确替代的预检窗口。
不是重新批准整个维护，也不增加 helper、权限、探测、超时、预算池或累计维护次数。
原检查及失败即停边界完整保留；未知原因不能预先宣称已修复。

## 建议 Owner 决定文本

以下只是对已登记准确 A 的请求，不是 Owner 已作决定：

> 按原 R，批准 A `ef46ac169fd9084875cb5c5148a9c4985ace680c` 的 `LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-v1`，关闭 DR1–DR2 范围 Gate。诊断修复完成验证、发布并冻结准确候选后，允许沿用 `lhqjgrow-20261006a` 再替代一次已失败的预检窗口；先记录准确 B 和独立 C，再由承接 C 的准确候选执行。旧窗口维持消耗，原认证、全部检查、15s/900s/780s、预算及累计维护次数不变；不增加权限、helper、探测，不自动重试、补采或清理。全门通过后仅完成既有 journal 维护，不执行 H01/Q4/H11 或扩展支线。

普通推进指令不是上述精确批准。收到准确 B 前，仅继续已授权开发及本提案文档准备；
不得开启新窗口或用独立 sudo/writer 调用试探现场。方案范围、R/A 或继承边界实质变化必须重审。
