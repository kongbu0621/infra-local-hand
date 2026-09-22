# GX10 S2 实施方案：准备、切换与回退验收

- Authority：Owner；状态：DRAFT / **S2 Documentation Gate OPEN**。
- 规则 R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；S1 的 A/C 和 closure 保留不变。
- 已复核前身：`e6412a1a38e91906355fbd9ec21974993449d743`；最终候选取新作业 E1–E3 验收固定提交 D，不追随可变 main。
- S2 文档基线 A：本组三文档提交后由实际完整 SHA 定位，不预写自身 commit。
- 当前授权：方案与既有能力下的只读准备；S2 实施、runtime 配置、迁移和切换尚未授权。

## S2-P01 本轮准备与可审查输入

1. 阅读根 `AGENTS.md`、固定 R、[需求](REQUIREMENTS.md)、[架构](ARCHITECTURE.md)。
2. 用旧 Local Hand 的现有准入动作采集事实，保留 Task、固定 mailbox commit 与可信 Result。
3. 将实时事实、历史快照、无法取得项分别记入 [READINESS.md](READINESS.md)。
4. 将 A2 需求与现有八动作、主机管理入口、私有证据传输逐项对应，见 [能力映射](A2_CAPABILITY_MAP.md)。
5. 提交三层文档与状态记录供审查；原始配置、路径、账户、mailbox 及 SOP 不进入 Public。

本阶段不调用 bootstrap，不生成新运行配置，不创建迁移器或 MCP 原型。
不使用 CAS 写验证脚本，不把未准入主机／NAS 操作包装为 replay-safe validation。
只有三文档既有 A、准确 Owner closure B、独立 CLOSED 记录 C 均存在，后续实现才从 C 开始。
Owner 本轮“按照建议进行”只支持上述准备，不被补写成尚不存在文档基线的 closure。

## S2-P02 关闭实施范围前的检查点

需取得主机只读管理入口，补齐 unit/drop-ins、解释器、运行包、profile 原始字节、安装绑定、
state 账本、所有生产者和自动重启来源。无法读取项不得填空或由 S1 历史记录代替。
将私有 manifest 字段、旧版兼容验证方法、部署步骤、失败保留和回退操作明确到可执行程度。
新增作业后端、MCP adapter 和 Plugin 的 scope 与文档基线见
[A2 执行实施方案](../a2-execution/IMPLEMENTATION_PLAN.md)，不自动包含在 S2 closure。
该方案 E1–E3 仅隔离实现；E4 验证当前客户端，再在 E5 与本 S2 统一部署验收。
首次主机管理入口仍须实际取得，新 MCP 不负责安装自己。
真实切换前确认 A2 后续路线能够覆盖缺口，避免只升级八动作后仍依赖手工终端完成 A2。
未知项的清单可以随准备文档提交，但仍阻塞对应实施或真实切换。

## S2-P03 独立构建与 staging（对应 scope CLOSED 后）

1. 在唯一新 checkout 固定 E1–E3 已验收的准确候选 D，确认工作区与完整 payload 对应 Git blobs。
2. 使用该提交 `requirements-build.txt` 建立独立 build venv，构建并保留原 wheel。
3. 在新 runtime venv 安装，从源码目录外核对实际 Python、包位置、metadata 和依赖。
4. 记录真实 wheel SHA-256、source commit、完整 payload 与 core digest；不要求 ZIP 容器字节复现。
5. 使用隔离 fixture/mailbox/profile/state 验证新安装，不能启动面向现役 mailbox 的 staging Worker。
6. 既有 S1 安装验收历史为 94 checks / 292 commands；新候选含 jobs/adapter/Plugin，按新矩阵记录实际覆盖与结果，不机械沿用旧计数。
7. 在隔离副本验证真实旧 receipt/result/conflict 的读取兼容及迁移防重放，再验证反向回退兼容。
8. 新 broker 的 staging 使用合成 authority/profile/issuer，与现役根隔离；验证新 job 账本恢复、
   启动/取消围栏和关闭准入状态。E4 测试数据不作为真实 GX10 authority 的初始化输入。

e6412a1 的 S1 等价关系不适用于新增代码；D 的源码和安装证据必须对应 D 的完整发布内容。
复用 E3 对准确 D 的已有充分证据，补齐 GX10 平台、私有绑定和切换差异；不无理由重复云端检查。
本步骤不得就地覆盖旧 venv、依赖、profile、安装记录、unit 或 state。

## S2-P04 冻结投递、排空与切换前封存

在准确切换授权和私有 manifest 具备后执行，按每项命令记录开始/结束/退出和 stdout/stderr。

1. 冻结所有 v1 controller/自动化生产者，并在 broker 后端关闭 MCP/CLI 新 job 准入，
   不只关闭客户端页面；逐入口核对拒绝新执行，记录两种协议已接受/排队/发布不明的原身份。
2. 让旧 Worker 在预定排空期限内完成当前工作；期限依据实际 validation 上界与清理预算冻结。
3. 全量核对任务账本；空 outbox 不替代 receipt/Result/conflict 核对，悬空链接不算不存在。
4. 停止旧服务，核对 cgroup、子进程、手工 Worker 和重启来源；若已有 broker/job，
   还须确认排队启动被撤销、runner/核对 writer 退出和 UNKNOWN 屏障保留。无法确认停止则不启新。
5. 静止窗口内封存旧完整 state、配置、unit、安装绑定、mailbox commit/未跟踪文件及相关目标摘要。
6. 将已验证兼容的防重放证据导入独立新 state；逐项核对文件类型、大小、字节摘要和任务身份。
7. 使用独立新 mailbox clone；对远端冻结基线及新 state 账本再次检查，出现新 Task 或漂移即停止。
8. 生成新安装记录并核对最终绑定，成对准备新 controller 来源预期；历史核对保留旧来源。
9. 单独冻结 broker authority/账本/锁锚点/epoch、job 事件和容量/准入策略。首次创建须证明无历史执行；
   已有真实账本按兼容规则保留，不按 v1 格式迁移。切换窗口和普通健康观察期间保持 job 准入关闭。

意图收据、发布不明、损坏/冲突记录未完成核对时不切换；不得删除证据来获得“空队列”。
保存旧 unit/enabled/配置的准确回退点；锁的持有必须重新证明，不能靠复制锁文件。

## S2-P05 启新、观察与恢复投递

1. 新服务启动前再次证明只有一个被准许的 writer；启动后核对 PID、账户、UUID、完整安装绑定。
2. 普通生产者继续冻结，仅放行 manifest 指定的单一健康检查 controller。
   它使用真实新三元来源预期，依次执行唯一新 ID 的 `node.status`、已准入 `repo.audit`
   和固定非敏感文件 `fs.read_text`；每项等待上界 120 秒，超时进入核对而不换 ID 重投。
3. 观察至少 10 分钟，核对全部轮询日志、非预期重启为零及三项精确结果。
4. 使用严格 `lstat` 与目录枚举确认无 pending outbox、无未解释 conflict/quarantine；读取失败即阻塞。
5. 有 E5 健康 job 准确授权时，仅给 manifest 指定的单一操作者开放固定 host.inspect，
   核对新 MCP 来源/认证、authority/epoch、job 账本、进程结束和封存证据取回；不开放 Ledger/NAS kinds。
   缺授权或新 broker 健康证据时记录 E5 未完成，不能用上面三项 v1 PASS 代替。
6. 两种协议的账本、目标摘要和 writer 归属一致后，按 manifest 分别恢复其已授权入口；
   NAS/Ledger 新作业保持未准入直到 E6，绝不因恢复 v1 controller 自动开放。
7. 保存完整前后证据，逐项评定 S2-R01–R10 和 E5 对应 AX 验收；分别列出结论。

以上健康窗口与时限为待批准方案值，不能写成已执行或已冻结现场参数。
故障注入、CAS 和进程恢复试验先在 staging；现役写入哨兵另需准确允许文件与影响范围。
仅 active、只读 Task 成功或长期没有新任务均不足以独立判定 S2 PASS。

## S2-P06 失败与回退矩阵

| 观察到的状态 | 必须动作 | 恢复投递前证据 |
| --- | --- | --- |
| 启动或来源校验失败，证明新实例未执行 Task | 停新并确认退出，恢复原绑定及 service 状态 | 新实例无执行事实、旧安装完整且唯一 active writer |
| 新实例已执行，结果明确 | 冻结投递、停新、封存新增账本与目标变化；验证旧版兼容后纳入屏障 | 全部新任务不会被旧版重执行，旧来源和新来源均可核对 |
| 超时、intent-only、冲突、子进程或副作用不明 | 维护态保留现场，按原身份核对 | 未决项解决或有准确恢复决定；否则标记回退未完成 |
| 旧版本不理解新屏障 | 保持停止并报告兼容阻塞 | 明确的兼容恢复路径；不删除新 receipt 或倒退 mailbox |
| 单 writer 证明失败或发现额外生产者 | 冻结投递，按批准的停止方案停新并核对其他执行者，保留现场；不得继续消费 | 所有执行者与生产者重新列清并恢复唯一归属 |

正常回退与故障回退均保留新旧文件及失败产物，不运行会自动删掉新部署证据的 cleanup。
停止服务不是撤销已发生的文件/NAS 操作；本 S2 不通过恢复业务数据快照掩盖执行事实。
以上表格判断之前，必须先在服务端冻结所有新 job 准入并证明 broker/runner 的已排队启动已撤销、
所有相关进程树停止，保存新 job 事件/租约/证据及 authority/epoch。旧版不能读取 job 屏障时，
已证明无交叉的资源按原回退准入恢复；交叉资源只有核对完成、风险解除且具备准确恢复决定才恢复。
存在未解除的交叉风险或 UNKNOWN 时保持维护态，不删除或转换屏障来启动旧 Worker。

## 验证映射与出口

| 验证 ID | 需求 → 架构 → 步骤 | 关键证据 |
| --- | --- | --- |
| S2-V01 | R01/R02/R05 → A02 → P02/P03 | 固定 source→wheel→安装→实际进程及 controller 绑定 |
| S2-V02 | R03/R09 → A01/A03 → P01/P04/P05 | 全生产者冻结、旧进程退出、唯一 writer、准入范围 |
| S2-V03 | R04/R08 → A04 → P03/P04 | 全账本清单、兼容性、intent/conflict 屏障及原字节 |
| S2-V04 | R06 → A05 → P03/P06 | 未执行/已执行回退；v1 与 job 两账本、排队启动撤销、交叉资源未决不恢复 |
| S2-V05 | R07/R08 → A06 → P05 | v1 端到端/日志/outbox；新 broker 健康/身份/权限/证据单独验收 |
| S2-V06 | R09/R10 → A01/A06 → P01/P02 | A2 固定输入、能力缺口、权限及证据交付路径 |

完成定义：上述验证有实际证据、未决项准确标记、原环境保留、回退可核对，方可记录 S2 PASS。
A2 后续按能力映射保留既有 Ledger closure，并单独完成 Local Hand 项目/作业接纳。
Windows、A2 实机/NAS 验收和此前未归因的云端 outbox 现象分别记账，不随 S2 自动转绿。
