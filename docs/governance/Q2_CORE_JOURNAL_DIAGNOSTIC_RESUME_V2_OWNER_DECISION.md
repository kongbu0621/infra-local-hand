# Journal proc 诊断替代窗口 v2：Owner 决定

本记录关闭准确 A 的 `LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-v2`，仅 DR1–DR2。
它不证明现场准入、窗口已启动、journal 扩容或核心验收成功。

- Authority：当前本地 Codex 对话中的本仓库 Owner。
- Event：`LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-V2-CLOSURE-20261006-01`；登记日期
  2026-10-06，Asia/Shanghai。不补造消息时间。
- 稳定来源：本对话中，执行者核对截图、准确 A 与修复 CI 后发出的下列请求，以及紧随其后的
  Owner 回复；本提交逐字保存请求的决定文本和准确批准，供 Owner 核实。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本执行者已直接完整读取固定规则，
  源 SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- A：`4341487c9be9ef64cf6fccbd973ed438a66e7483`，tree
  `bc3d2b3fdfb14359404796941c2639c00004b440`；其三文档摘要见
  [准确基线登记](Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_V2_BASELINE.md)。
- 原有离线诊断修复：`03cfb183d05c55258bb2da01e8c3cf77ea06fe63`；准确 CI
  `37475992159` attempt 1 completed/success，三个 job 成功。这不替代新 D 的验证或现场准入。

## 紧邻的准确请求

执行者说明修复未放宽原阈值、覆盖与预算，现场超限仍未确定，journal 尚未扩容；随后请求：

> 按原 R，批准 A `4341487c9be9ef64cf6fccbd973ed438a66e7483` 的 `LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-v2`，关闭 DR1–DR2 范围 Gate，按该方案执行一次替代预检窗口。全门通过后仅完成既有 journal 维护，不执行 H01/Q4/H11 或扩展支线。

请求同时说明旧 v1 窗口已消耗，v2 必须另有准确 Owner B 和独立 C；截图本身不是批准。

## Owner 准确批准

> 按原 R，批准 A `4341487c9be9ef64cf6fccbd973ed438a66e7483` 的 `LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-v2`，关闭 DR1–DR2 范围 Gate，按该方案执行一次替代预检窗口。全门通过后仅完成既有 journal 维护，不执行 H01/Q4/H11 或扩展支线。

## 独立关闭与边界

本提交仅包含本决定与 AGENTS.md 的 CLOSED 登记，作为独立 bookkeeping-only C。
没有源码、测试、可执行原型、依赖、配置、release digest 或现场操作；A 三文档、历史 OPEN
标签和全部旧批准/失败记录不变。后续 D 必须承接本 C，不得 squash 合并。

批准按准确 A 执行：先完成 DR1 的 v2 A/C 绑定、验证、发布、最终相关 CI 与准确候选冻结，
随后只允许一次 DR2 替代预检。沿用 `lhqjgrow-20261006a`、原对象、原输入、原真实本机前台
终端与固定 writer 的 sudo 认证。旧窗口继续消耗；无 marker 不返还窗口。密码只交给 sudo
的控制终端，不进入程序、文件、环境、管道、日志或 Codex。

全部原检查、proc 上限与覆盖、15s/900s/780s、最多八检查点、原预算和跨历次累计维护上限
保持。不得提高上限、跳过任务、裁剪扫描、增预算、增权限/helper/探测或预热。
失败、未知、超时或漂移即停，不自动重试、重连、补采、强杀、清理或回滚。
只有全门通过才在同窗完成尚未消费的原 journal 维护；不执行 H01/Q4/H11、新 boot 核心采用
或扩展支线。诊断修复不追认历史 UNKNOWN，也不证明实际超限已解决。
