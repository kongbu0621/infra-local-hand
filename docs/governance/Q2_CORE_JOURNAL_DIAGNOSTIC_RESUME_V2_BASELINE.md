# Journal proc 诊断修复：一次替代预检待决方案

2026-10-06。状态 **OPEN / NOT APPROVED**；没有本范围 Owner B 或 CLOSED C。
本文仅登记可审阅提案，不批准或执行新窗口、sudo、writer、SSH、marker 或维护。

- Scope：`LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-v2`，仅 DR1–DR2。
- Gate 来源：`kongbu0621/engineering-sop`；原 R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- [固定直接规则](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)；
  既有源 SHA-256：`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- Mandate / decision authority：Owner；exceptions：none；采用及实质变化重审规则不变。
- 准确 A：`4341487c9be9ef64cf6fccbd973ed438a66e7483`，tree
  `bc3d2b3fdfb14359404796941c2639c00004b440`，parent
  `03cfb183d05c55258bb2da01e8c3cf77ea06fe63`。
- 已发布诊断修复：`03cfb183d05c55258bb2da01e8c3cf77ea06fe63`，tree
  `539b4ab98d0494bf7058b2054ae9a84f3b759c09`；与本地已验证树一致。
- 三文档：[需求](../a2-execution/q2-core-journal-diagnostic-resume-v2/REQUIREMENTS.md)、
  [架构](../a2-execution/q2-core-journal-diagnostic-resume-v2/ARCHITECTURE.md)、
  [计划](../a2-execution/q2-core-journal-diagnostic-resume-v2/IMPLEMENTATION_PLAN.md)。

| A 的三文档 | SHA-256 |
| --- | --- |
| `REQUIREMENTS.md` | `a4a7891c01d32abf7a3283a39a0bf701cd47d023bab14808bf25f84ef98eca5b` |
| `ARCHITECTURE.md` | `a17ef97537748d03b0d48bc9e6945785fbda6d707875ad925df773fa9c511bbb` |
| `IMPLEMENTATION_PLAN.md` | `13f2ae38d9637c3e3d96cd59216037da7569132fa73bb4187e30a49763967c67` |

[离线修复记录](../a2-execution/Q2_CORE_JOURNAL_PROC_LIMIT_DIAGNOSTICS_REVIEW_20261006.md)：
十四文件相关回归 **598 passed、3 skipped**，新增 163 项隔离测试。原阈值、读取与覆盖不变。
准确修复提交的 [CI 37475992159](https://github.com/kongbu0621/infra-local-hand/actions/runs/37475992159)
attempt 1 已完成，conclusion `success`；classify-change、Linux 与 Windows 三个 job 均通过，
包括源码测试及独立安装 wheel 验证。没有重跑；该结果不计现场成功。

## 精确范围与旧窗口

[DR2 现场记录](../a2-execution/Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_FIELD_20261006.md)已登记
`deab8acdabf0d35294f55fa87f2bc86d542fdf2e` 在 checkpoint 1 以 `GROWTH_PROC_LIMIT` 失败。
marker、SSH、维护均为 0；窗口仍已消耗。截图未记录具体分支/计数，准确原因保持 UNKNOWN。
诊断修复仅使未来同一个拒绝点保留固定 kind、首次拒绝值、原 cap、适用 PID/TID，
不增加读取、不放宽校验/覆盖/上限，不改五字段 schema，不宣称实际阈值问题已解决。

唯一新增现场权限是：修复验证、发布、最终相关 CI 及准确 A/B/C/D 绑定通过后，沿用原 session
明确再开一次替代预检窗口；全门通过才同窗完成原维护。所有旧失败/消耗、原认证、检查、
15s/900s/780s、预算及累计维护次数不变。旧 A 文档字节不改；源码或 CI PASS 不返还窗口。

## 建议 Owner 决定文本

以下是对已登记准确 A 的请求，不是已收到的批准：

> 按原 R，批准 A `4341487c9be9ef64cf6fccbd973ed438a66e7483` 的 `LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-v2`，关闭 DR1–DR2 范围 Gate。proc 诊断修复完成验证、发布和准确绑定，且最终相关 CI 通过后，允许沿用 `lhqjgrow-20261006a` 再一次替代预检窗口；先记录准确 B 和独立 C，再由承接 C 的准确候选执行。旧窗口维持消耗，原认证、全部检查、15s/900s/780s、预算及累计维护次数不变；不提高 proc 上限、不跳过任务、不改覆盖、不增预算，不增加权限、helper 或探测，不自动重试、补采、清理或回滚。全门通过后仅同窗完成既有 journal 维护，不执行 H01/Q4/H11 或扩展支线。

收到准确 B 前，仅继续已有开发授权与提案准备；不得执行任何新现场观察或维护。
范围、R/A 或继承边界实质变化仍须重审；本方案没有当前批准。
