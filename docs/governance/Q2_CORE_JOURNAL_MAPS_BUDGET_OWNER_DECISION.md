# Journal maps 固定预算修正：Owner 决定

本记录关闭 `LH-Q2-CORE-JOURNAL-MAPS-BUDGET-v1` 在准确 A 下的 MB1–MB2，
不证明实现、完整扫描、现场准入、journal 扩容或核心验收成功。

- Authority：当前本地 Codex 对话中的本仓库 Owner。
- Event：`LH-Q2-CORE-JOURNAL-MAPS-BUDGET-CLOSURE-20261007-01`；登记日期
  2026-10-07，Asia/Shanghai。不补造消息时间。
- 稳定来源：当前对话中执行者核对截图、准确 A/三文档和原源码后发出的下列请求，
  及紧随其后的 Owner 回复；本提交逐字保存决定文本，供 Owner 核实。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本执行者已在本会话直接完整读取固定规则，
  源 SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5` 匹配。
- A：`d18b490a7cdb63ee43044a29a89746ef78fccff3`，tree
  `6e3bf87b8e3a62344de0ebf93e1d51e099a56320`；三文档摘要由
  [基线登记](Q2_CORE_JOURNAL_MAPS_BUDGET_BASELINE.md)固定。
- 本提交只登记批准与 CLOSED C；没有本范围实现、现场动作或新成功结果。

## 紧邻请求

执行者先说明新增提交只有文档；累计 maps 预算将从 64 MiB 提高到固定 512 MiB，
完整扫描、单文件上限与原时限保持，仍不保证现场通过。随后请求：

> 按原 R，批准 A `d18b490a7cdb63ee43044a29a89746ef78fccff3` 的 `LH-Q2-CORE-JOURNAL-MAPS-BUDGET-v1`，关闭 MB1–MB2 范围 Gate。允许累计 maps 预算由 64 MiB 改为固定 512 MiB，按方案完成实现、验证、发布、冻结及一次替代预检窗口。全门通过后仅完成既有 journal 维护，不执行 H01/Q4/H11 或扩展支线。

请求同时说明此前批准禁止增加预算且 v2 窗口已消耗，新预算/窗口必须另有准确 B 和独立 C。

## Owner 准确批准

> 按原 R，批准 A `d18b490a7cdb63ee43044a29a89746ef78fccff3` 的 `LH-Q2-CORE-JOURNAL-MAPS-BUDGET-v1`，关闭 MB1–MB2 范围 Gate。允许累计 maps 预算由 64 MiB 改为固定 512 MiB，按方案完成实现、验证、发布、冻结及一次替代预检窗口。全门通过后仅完成既有 journal 维护，不执行 H01/Q4/H11 或扩展支线。

## 独立 C 和准确边界

本提交仅含本决定与 AGENTS.md 的关闭登记，没有源码、测试、可执行原型、依赖、配置、
release digest 或现场操作。A 三文档及历史 OPEN 标签保持原字节；新 D 必须承接本 C，不能 squash。
旧批准、失败与消费记录保持，不追认历史 UNKNOWN。

唯一资源变化是每次扫描累计 maps 文本接受额固定为 512 MiB；仍逐 task 实读、计数与解析，
不去重、缓存、跳过或动态调额。单文件 1 MiB、其它 proc cap、完整可见性、身份/集合复核和
writer 判断不变。原 15s/900s/780s、AS/RSS/FD、输入输出、capture/存储预算与累计维护次数不变。
512 MiB 是被批准的有限工程预算选择，不是已测得的宿主总需求或成功保证。

先完成 MB1 的最小实现、准确授权绑定、隔离验证、发布、最终 D 相关 CI 与冻结，随后只允许
一次 MB2 替代预检。沿用 `lhqjgrow-20261006a`、原对象/输入、普通身份和 Owner 的已有真实
本机前台终端；固定 writer 的密码只交给 sudo 控制终端。不得增加权限、helper、探测或预热。

所有旧窗口继续消耗，新窗口开始即消耗；失败、未知、漂移或超时即停，不重试、重连、补采、
强杀、清理或回滚。只在全门通过后同窗完成尚未消费的原 journal 维护，完整 receipt 才能证明成功。
不执行 H01/Q4/H11、新 boot 核心采用、生产部署或扩展支线。
