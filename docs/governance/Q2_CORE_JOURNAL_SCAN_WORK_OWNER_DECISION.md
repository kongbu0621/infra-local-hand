# Journal 扫描工作量修正：Owner 决定

本记录关闭 `LH-Q2-CORE-JOURNAL-SCAN-WORK-v1` 在准确 A 下的 W1–W2，
不证明实现、现场准入、journal 维护或核心验收成功。

- Authority：当前本地 Codex 对话中的本仓库 Owner。
- Event：`LH-Q2-CORE-JOURNAL-SCAN-WORK-CLOSURE-20261007-01`；登记日期
  2026-10-07，Asia/Shanghai。不补造消息时间。
- 稳定来源：当前对话中执行者核对新方案后的紧邻请求与 Owner 回复；本提交逐字保留决定，
  供 Owner 核实。截图中的提案没有被当作批准。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本执行者已在本会话完整读取直接固定规则，
  源 SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5` 匹配。
- A：`42a66be98c45e817e866d3fb86a1c184c2ce55f9`，tree
  `30f3be0a4f2e145095bb4ccaa0b40087f8f99e81`；三文档摘要由
  [基线登记](Q2_CORE_JOURNAL_SCAN_WORK_BASELINE.md)固定，并已与准确 A 及发布版本逐一核对。
- 本提交仅登记准确 B 与 CLOSED C，不含本范围实现、配置、发行摘要或现场动作。

## 紧邻请求

执行者确认 main `fe24919` 及三文档摘要匹配，新方案尚未实现或启动窗口，且不保证现场通过。
随后请求：

> 按原 R，批准 A `42a66be98c45e817e866d3fb86a1c184c2ce55f9` 的 `LH-Q2-CORE-JOURNAL-SCAN-WORK-v1`，关闭 W1–W2 Gate。按三文档实施固定 2097152 次 FD stat 预算、v2 进度及两维护源长度调整。先记录准确 B 和独立 C，再完成实现、验证、发布、准确候选 CI 与冻结，以及一次替代预检窗口。全门通过后仅完成原 journal 维护；旧窗口继续消耗，不重试、补采或扩展，不执行新 boot 核心采用及 H01/Q4/H11。

请求同时解释 AGENTS.md 的 OPEN 状态，以及新增预算、协议和源码界超出此前 maps 批准。

## Owner 准确批准

> 按原 R，批准 A `42a66be98c45e817e866d3fb86a1c184c2ce55f9` 的 `LH-Q2-CORE-JOURNAL-SCAN-WORK-v1`，关闭 W1–W2 Gate。按三文档实施固定 2097152 次 FD stat 预算、v2 进度及两维护源长度调整。先记录准确 B 和独立 C，再完成实现、验证、发布、准确候选 CI 与冻结，以及一次替代预检窗口。全门通过后仅完成原 journal 维护；旧窗口继续消耗，不重试、补采或扩展，不执行新 boot 核心采用及 H01/Q4/H11。

## 独立 C 与边界

本提交只含本决定及 AGENTS.md；准确 A 三文档和历史 OPEN 标签保持原字节。新实现 D 必须
承接本独立 C，不合并 C/D。旧批准、失败、窗口消费与 UNKNOWN 保持。

每 writer 调用固定 2097152 次 FD stat 尝试预算，初始 snapshot、复核 snapshot 与匹配对象
额外 stat 在调用前共享计费，异常不退款；替代旧事后 FD_TOTAL 门，不取消其它检查。
新增严格 `lhq-journal-writer-result/v2` progress，仅记录已有操作和成功时钟样本。
仅 host/guest 两维护源上限改为 98304 B，guest bundle 中只扩大 guest 源项；payload、argv、
reader、descriptor、压缩/解压及其它限额保持。准确细节由 A 三文档共同约束。

完整逐 task 扫描、身份/集合/writer 校验、maps 512 MiB/单文件 1 MiB、原认证和权限、
15s/900s/780s、AS/RSS/FD、存储/capture 及累计维护次数保持。工程预算不冒充宿主需求或成功保证。

W1 必须完成实现、相关隔离验证、发布、准确 D 的相关 CI 与冻结，之后才允许 W2 一次替代预检。
沿用 `lhqjgrow-20261006a`、原输入/对象、普通 coordinator 身份与 Owner 已有真实本机前台终端。
只有固定 writer 使用既有 sudo，密码只交给控制终端；不新增 helper、权限、探测或认证预热。

旧窗口全保持消耗，新窗口开始即消耗；失败、未知、漂移、超时即停，不重试、补采、重连、
自动调额、强杀、清理、恢复或回滚。全门通过才在同窗完成尚未消费的原 journal 维护，
合格原 receipt 才证明维护成功；不执行新 boot 核心采用、H01/Q4/H11、生产部署或扩展支线。
