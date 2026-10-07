# Journal 漂移诊断后单次维护接续：Owner 决定

本记录关闭准确 A 的 `LH-Q2-CORE-JOURNAL-DRIFT-RESUME-v1` / DR1–DR2，
不证明新候选、现场准入或 journal 维护已完成。

- Authority：当前本地 Codex 对话中的本仓库 Owner。
- Event：`LH-Q2-CORE-JOURNAL-DRIFT-RESUME-CLOSURE-20261007-01`；登记日期
  2026-10-07，Asia/Shanghai，不补造消息时间。
- 稳定来源：当前对话中执行者核对提案后的紧邻请求及 Owner 的明确回复；
  下文逐字保留决定作为可核验副本，截图内的待决文字没有被视为批准。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。本执行者已在本会话完整读取
  直接固定规则，源 SHA-256
  `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5` 匹配。
- A：`4f2a6a37ad5afd027dbde0f1656a3552750cb3b2`，tree
  `49c38eafe07f2a8f31febbc510e34ccbe79e3d46`。三文档摘要见
  [基线登记](Q2_CORE_JOURNAL_DRIFT_RESUME_BASELINE.md)，已逐一核对准确 A 和当前发布版本。
- 本提交只包含本决定及 AGENTS.md 的 CLOSED 登记，为独立 bookkeeping-only C；
  不含实现、配置、发行摘要或现场动作，D 必须承接本 C，不合并 C/D。

## 紧邻请求

执行者确认已同步 `33c04c4`，准确 A 三文档摘要匹配，原 663 项验证及修复 CI 继续有效，
请求 Owner 回复以下文字：

> 按原 R，批准 A `4f2a6a37ad5afd027dbde0f1656a3552750cb3b2` 的 `LH-Q2-CORE-JOURNAL-DRIFT-RESUME-v1`，关闭 DR1–DR2 Gate。先记录准确 B 和独立 C，再完成新候选绑定、验证、发布、准确 CI 和冻结；允许原 session 一次替代预检，全门通过后同窗完成原 journal 维护。原检查、预算、期限及旧窗口消耗不变；不重试、补采、清理、扩展，不执行新 boot 核心采用或 H01/Q4/H11。

请求同时解释 AGENTS.md 中本范围 OPEN / NOT APPROVED、旧 W2 已消耗，以及截图的
待决文字尚不能登记为 Owner B。

## Owner 准确批准

> 按原 R，批准 A `4f2a6a37ad5afd027dbde0f1656a3552750cb3b2` 的 `LH-Q2-CORE-JOURNAL-DRIFT-RESUME-v1`，关闭 DR1–DR2 Gate。先记录准确 B 和独立 C，再完成新候选绑定、验证、发布、准确 CI 和冻结；允许原 session 一次替代预检，全门通过后同窗完成原 journal 维护。原检查、预算、期限及旧窗口消耗不变；不重试、补采、清理、扩展，不执行新 boot 核心采用或 H01/Q4/H11。

## 授权边界

A 的三文档及其历史 OPEN 标签保持原字节；R、Owner authority/mandate、无例外及
实质变化重审规则保持。旧批准、冻结源码/交接、原失败、全部窗口消费和 UNKNOWN 保留。

DR1 只新增本范围准确 A/C、诊断修复身份和文档 pins 的来源及 manifest 绑定，并完成
必要隔离验证、发布、准确候选 CI、原静态资料离线核对和新私有交接冻结。
`711932aae3370c7f2ed5c1a51ac82d3b0f67a6e5` 的 scanner、生成函数及固定入口保持原字节；
已有核验继续有效，新增差异与候选身份单独核对。

DR1 全门通过后，DR2 沿用 `lhqjgrow-20261006a`、原对象/八输入、普通 coordinator
身份及 Owner 已有真实本机前台终端执行一次替代预检。固定 writer 使用原 sudo 认证，
密码只交控制终端；不增加权限、helper、探测或预热。预检全门通过即复用同 D、manifest、
nonce、窗口、TTY 和 writer handoff，在同窗完成未消费的原 journal 维护，无需逐步骤再批。
保留原 execute 再次准入、checkpoint 2 和本地 SSH 配置检查，不重放 checkpoint 1。

扫描覆盖、身份/集合判据、v2 progress、固定 2097152 FD stat、512 MiB maps、两源 98304 B、
其它所有预算、15s/900s/780s、八检查点及累计维护次数保持。没有通过保证。
窗口开始即消费；失败、未知、超时、漂移即停，不重试、重连、补采、提额、停宿主应用、
强杀、清理、恢复或回滚。合格原 receipt 才证明维护成功。
不执行新 boot 核心采用、H01/Q4/H11、生产部署或扩展支线。
