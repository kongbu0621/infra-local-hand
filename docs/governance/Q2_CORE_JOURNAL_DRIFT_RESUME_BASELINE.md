# Journal 一致性诊断后单次维护接续：准确待决基线

2026-10-07（Asia/Shanghai）。**OPEN / NOT APPROVED**；尚无本范围 Owner B 或独立 C。
本记录只登记可审阅方案，不授权现场调用、替代交接或新实现。

- Scope：`LH-Q2-CORE-JOURNAL-DRIFT-RESUME-v1`，仅 DR1–DR2。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，来源 `kongbu0621/engineering-sop`。
- 已直接读取[固定规则](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)，
  沿用登记的源 SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- Mandate / Authority：Owner；exceptions：none；原采用、准确批准及实质变更重审规则不变。
- 准确 A：`4f2a6a37ad5afd027dbde0f1656a3552750cb3b2`，tree
  `49c38eafe07f2a8f31febbc510e34ccbe79e3d46`，parent
  `d8c079302717452711251a83d642e5b9ed9fb21e`。A 只含以下三文档，没有源码、测试或配置。
- [需求](../a2-execution/q2-core-journal-drift-resume/REQUIREMENTS.md)、
  [架构](../a2-execution/q2-core-journal-drift-resume/ARCHITECTURE.md)、
  [计划](../a2-execution/q2-core-journal-drift-resume/IMPLEMENTATION_PLAN.md)。

| A 文档 | SHA-256 |
| --- | --- |
| REQUIREMENTS.md | `1b176e044cfb4bf4dc4d7e6d7cee01e1480e3acf67825c9eda78980bf71d577f` |
| ARCHITECTURE.md | `473ace5e05c300f1e6751d97727b04e69f7f53628f3220d06bfdb1483e77551a` |
| IMPLEMENTATION_PLAN.md | `aec1a315f47fb05b5ccdc2a0855f5de479489d13c5e80f3d2e294a3563c920be` |

## 已有证据与本次差异

诊断修复 `711932aae3370c7f2ed5c1a51ac82d3b0f67a6e5` 的
[准确 CI 37569620992](https://github.com/kongbu0621/infra-local-hand/actions/runs/37569620992)
attempt 1 的三个 job 已独立核实全部 completed/success。本地 663 项、原八静态输入及十二
源成员核验已完成；证据见 [完整记录](../a2-execution/Q2_CORE_JOURNAL_DRIFT_DIAGNOSTICS_REVIEW_20261007.md)。
本次不再要求重复开发诊断或无差异重做已完成核验；新候选绑定和准确 CI 仍独立验证。

唯一新增现场权限为：准确批准链及最终绑定/验证/发布/CI/冻结完成后，沿用原 session 和
对象的一次替代预检；全门通过便同窗完成未消费的原 journal 维护。不另设诊断试跑。
当前 v2/progress、FD stat 2097152、maps 512 MiB、两源 98304 B 和其它全部原界不变。
接受/拒绝集合不变，不保证本次现场通过；历史精确分支保持 UNKNOWN。

两项独立只读审阅核对了新旧批准链、原源码/窗口顺序、现行预算和维护/核心边界。
冻结前已明确 execute 仍执行原 checkpoint 2、再次准入与本地 SSH 配置检查，复用首次
窗口和 checkpoint 1 报告；没有删除复核、重放 checkpoint 1 或另开窗口。
缺失合法 child 报告不补造 progress，合法 request 的报告缺失 progress 仍拒绝。
文档链接、引用提交、摘要与差异检查通过，远端 A tree 与本地审阅树相同。
没有修改源实现、执行新测试、扫描原现场、发送 SSH 或启动维护。

扩容后的新 boot consumer、05c 第四旧 profile 和新核心批仍是真实后续接线缺口。
本 A 不包含其实现/执行，不承诺维护成功即能用旧包进入 H01/Q4/H11；支线继续暂停。

## 请求 Owner 的准确决定

以下是待决文本，不是已收到的批准：

> 按原 R，批准 A `4f2a6a37ad5afd027dbde0f1656a3552750cb3b2` 的
> `LH-Q2-CORE-JOURNAL-DRIFT-RESUME-v1`，关闭 DR1–DR2 范围 Gate。
> 先记录准确 B 和独立 C，再按方案完成新候选绑定、验证、发布、准确 CI 和冻结；
> 允许原 session 一次替代预检，全门通过同窗完成原 journal 维护。
> 原检查、预算、期限和旧窗口消耗保持，不重试、补采、清理或扩展支线；
> 不执行新 boot 核心采用或 H01/Q4/H11。

收到准确决定前，不生成替代现场命令或执行新窗口。既有未受影响 CLOSED 工作继续；
不得把本文件、普通“继续”、发布或旧 CI 成功当作 Owner B。
