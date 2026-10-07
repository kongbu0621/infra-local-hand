# 最小核心接续：Owner 决定

本记录关闭 `LH-Q2-CORE-MINIMAL-CONTINUATION-v1` 的 K1–K3，明确接受三文档所述
维护访问前提与观察覆盖变化；不证明实现、维护或核心现场验证已经通过。

- Authority：当前本地 Codex 对话中的本仓库 Owner。
- Event：`LH-Q2-CORE-MINIMAL-CONTINUATION-CLOSURE-20261007-01`；登记日期
  2026-10-07，Asia/Shanghai，不补造消息时间。
- 稳定来源：当前对话内执行者完成准确三文档审阅后的紧邻请求及 Owner 明确回复。
  下文逐字保留可核验副本，先前截图的待决文本没有被当作批准。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。本执行者已在本会话完整读取
  直接固定规则，源 SHA-256
  `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5` 匹配。
- A：`5d6cefa602e9146f02887ebfaa4b0cad4e376ff2`，tree
  `72262d27c2caef48db0965989508b1f193f3b527`，parent
  `b531d448741eda69463ed6c31b81976672caab58`。
- 本提交仅含本决定和 AGENTS.md 的 CLOSED 登记，为独立 bookkeeping-only C。
  新实现 D 必须承接 C，不合并 C/D；三份 A 文档及其历史 OPEN 标签保持原字节。

## 准确三文档

| 文档 | 字节 | SHA-256 |
| --- | ---: | --- |
| [需求](../a2-execution/q2-core-minimal-continuation/REQUIREMENTS.md) | 7009 | `f132068c02f6a49332e991525591c409d38690bb1cbff51d0f17de1e68e28769` |
| [架构](../a2-execution/q2-core-minimal-continuation/ARCHITECTURE.md) | 6253 | `121f67c11bbc85e18aed7635f3541cdb581fdb52aceba25fb12aca18aecf760b` |
| [计划](../a2-execution/q2-core-minimal-continuation/IMPLEMENTATION_PLAN.md) | 4701 | `093e0daac0f85cc78a48fcf58386d3133cfc796e9faba416b622dd0e072b8c58` |

已逐项核对准确 A 与发布登记 `3d6227ca2dcdeaa61b00b0c7d8dc2b5bc69b4820`，没有源码变化。

## 紧邻请求

执行者确认已同步 `3d6227c`，准确文档匹配、源码未改，方案覆盖维护删减、扩容和新 boot
核心接续；随后请求以下决定：

> 按原 R，批准 A `5d6cefa602e9146f02887ebfaa4b0cad4e376ff2` 的 `LH-Q2-CORE-MINIMAL-CONTINUATION-v1`，关闭 K1–K3 Gate；接受可信单管理员维护前提及取消全宿主 writer 扫描覆盖。先记录准确 B 和独立 C，按三文档完成实现、验证、发布和冻结；允许一次维护窗口，完整验证通过后执行一次 H01→Q4→H11。旧窗口继续消耗，不重试、补采、清理或扩展支线。

请求明确说明 AGENTS 中范围尚 OPEN，本次会保留目标/数据检查，但取消未知宿主 writer
检测，依赖维护期间没有其它任务直接操作五个镜像的可信单管理员前提。

## Owner 准确批准

> 按原 R，批准 A `5d6cefa602e9146f02887ebfaa4b0cad4e376ff2` 的 `LH-Q2-CORE-MINIMAL-CONTINUATION-v1`，关闭 K1–K3 Gate；接受可信单管理员维护前提及取消全宿主 writer 扫描覆盖。先记录准确 B 和独立 C，按三文档完成实现、验证、发布和冻结；允许一次维护窗口，完整验证通过后执行一次 H01→Q4→H11。旧窗口继续消耗，不重试、补采、清理或扩展支线。

## 范围与顺序

K1 一次接齐维护扫描删减、普通预检累计计量交接、严格新 manifest/receipt、完整维护原件
验证及 transition、新 boot 核心采用、05c 第四旧 profile 和固定 07a 新批。
保留目标 VM/五镜像、guest 静止、正常锁/停机、备份、增长、内容/容量及原核心策略。
取消的是维护全宿主 writer 观察及其专属 root/TTY/15s/八报告依赖，其预算不转给其它动作。
未执行观察必须明确为 NOT_PERFORMED；不声称等价安全或全程排他，不增加替代扫描器/helper。

两段实现均完成相关源码/独立安装验证、准确 CI、发布和冻结后，且可信单管理员前提成立，
K2 才可沿原 session、对象/输入和管理环境执行一次维护窗口。保留原维护期限及累计动作
次数，所有旧窗口保持消耗；失败即停止，K3 为 NOT_RUN。

只有 K2 的完整合格原件验证通过后，K3 才能用同一准确实现完成真实 transition 绑定、
原双构包及独立解析/发行检查，按 A 的固定 `lhqcore-20261007a` 身份在一个独立原期限
核心窗口内执行一次 H01→Q4→H11。前项未完整通过，后项 NOT_RUN；H11 恢复同一任务，
不重放任务或借别的 case 的 ledger/unit。不直接运行旧包，不通过猜测 boot 替代原件。

准确身份、容量/CPU/inode 预算、四旧批/两诊断/全部维护历史及 UNKNOWN 按 A 保留。
范围内已列明子步骤无需分别再批；不重试、补采、重连、改名绕过已存在对象、强杀、
清理、自动恢复或回滚。生产 E3、E4–E6、NAS、namespace/watchdog 和其它支线不在范围。
R、Owner-only authority/mandate、无例外及实质变化重审规则不变。
