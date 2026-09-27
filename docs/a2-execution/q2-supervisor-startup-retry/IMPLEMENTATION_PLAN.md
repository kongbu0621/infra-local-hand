# Q2 监督器启动修复后单次新运行：实施方案

- Authority：Owner；状态：**PROPOSED / Gate OPEN**。
- Scope：`LH-Q2-SUPERVISOR-STARTUP-RETRY-v1`；R 与根 `AGENTS.md` 相同。
- [需求](REQUIREMENTS.md) → [架构](ARCHITECTURE.md) → 本方案。
- OPEN 期间只完成文档、只读复核及既有代码的隔离验证；本 scope 的新执行器、测试实现和运行配置均在 B/C 后创建。

## 准确基线与输入

运行候选 commit/tree/wheel 固定在需求文档。A 提交前完成准确 commit 的源码验证、
离线 wheel 构建/来源核验和隔离安装，将准确 wheel SHA-256 写入三文档基线，
不保留占位符。修复记录区分模型、真实文件/权限/管道/安装与实机证据；不能将
验证通过当成 guest 已执行。编排实现 D 在独立 CLOSED C 后产生并单独固定。

原准备 A `2ea59b8d1b262632bae5636938107ef2f002a59b`、恢复 A
`72c06ec68d370333f5ffb1079023917828b3e681` 和 CPUQuota retry A
`d8e49617efecae199b0874f183530794f8c36e6a` 及各自三文档、B/C/D 保留。
CPUQuota retry 的 CLOSED C 为 `b0964e7adb50a49064f522fedbb1d46c3af08911`；
其一次运行已消费，不授权新候选或刷新期限。

双前驱材料包括原准备/恢复来源、准确 CPUQuota 解析失败，以及紧接着的监督器
启动失败。后一轮 runtime 为 `9a556322183f0fa80d4edeada4b03c74a26524a5`，
tree `0687d7cd8eaf6a901d565a60b99042827437354c`；编排来源为
`15af5f19b27211f237f1d66f7e11c9aeef59a3a5`，tree
`a300cd9888960bf9d25eef61cc4098242e1a7f70`。这些是历史来源，不是本次运行候选。
已回传包作为不可变输入；两份 SQLite、七根 quota/成员、历史 unit 精确终态和
当前静止性仍须在新窗口内现场复核，不声称旧静态包代表当前事实。
私人计划、机器路径/身份和原始证据不提交公开仓。

## C 后整批实施与一次交付

| 阶段 | 交付内容 | 对应要求 |
| --- | --- | --- |
| P0 | 固定候选和准确三文档 A；一次 Owner B；独立、仅含关闭登记的 C | S01–S08 |
| P1 | C 后实现新严格合同、双前驱鉴证、累计成本、独立状态及一次交付/收集，固定 D | S01–S07 |
| P2 | 负例、真实文件/权限/管道、候选安装和完整模拟贯通，明确证据层次 | S01–S08 |
| P3 | 一次现场窗口内只读预检全部前驱、FAILED/静止性、两份 ledger、七根和空间；排他保存新意图 | S01–S03、S06、S07 |
| P4 | 独立安装固定候选，必要时 start 准确正常 inactive manager/父 slice；创建新状态、映射和装配 | S03、S04、S06、S07 |
| P5 | 发行前复核后交付一次新 owner；同 MainPID 绑定，运行固定三阶段，收集退出/EOF/独立停止/seal | S05、S07、S08 |
| P6 | 封存原流与结构化结果，核验新旧关联和历史保持，发布脱敏结论及未验收边界 | S02、S08 |

Owner 对准确 R/A 的关闭覆盖 P1–P6 整批，不逐命令或逐对象再次询问。现有 CLOSED
开发范围内的源码修复和验证不需要重批；本方案只在新 A 可评审、候选摘要准确后
请求一次新的 Owner 关闭。B 保留准确决定、R/A、scope、时间或事件和稳定来源；
C 不混入实现，D 必须从 C 继续，不能 squash 关闭与执行器实现。

新 schema 为 `local-hand-q2-supervisor-startup-retry/v1`，严格绑定双前驱类型、
本次权限与候选、完整旧身份集合、七根映射、所有历史 reservation、预算及原始
issued/deadline。专用实现置于 `tests/e3_host/`，按合同、鉴证/容量、安装装配、
外层交付和只读收集分责；这是设计落点，OPEN 期间不创建实现脚手架。
可复用已验证的安装、装配、时钟和捕获原语，不直接调用原账户准备/恢复变更入口，
也不宽化旧 CPUQuota v1 来接纳新失败。

P3 在任何本次持久修改前完成有界预检，后续副作用前保留 intent/result。
P4 不重设 quota、不初始化旧 ledger、不修改旧 authority，不清理任何失败实例。
新 authority 同时绑定原准备和两轮失败、双 ledger、未消费七根与本 scope 的
R/A/B/C/D。所有新身份/路径对全部前驱检查；并发败者、重复入口和部分完成都不能
删除后重试。P5 前再次核验原材料保持、空树/空表、容量及剩余时间，不足就不发行。

## 必须处理的旧实现差异

| 既有实现 | 本次设计要求 |
| --- | --- |
| `q2_retry.py` 的 startup/preflight 接受退出 1、准确 CPUQuota stderr、supervisor/target 均 NOT_FOUND | 新类型接纳准确已执行的监督器失败；明确保留历史 FAILED，target 未创建与未消费必须联合鉴证；旧失败校验语义不变 |
| `q2_retry_contract.py` 固定旧 scope/A/C/candidate、单个 old ledger，并主要与原 preparation 去重 | 新合同显式双前驱、两份 ledger、全部旧身份/路径集合、准确新候选和新授权；拒绝旧 plan 冒充新 plan |
| `q2_retry.py` 的成本计算显式读取单次旧 owner reservation | 枚举全部历史 reservation 的实际与未用承诺，去重后累计，原 byte/inode ceilings 不增加 |
| `q2_retry_driver.py` 的 prepared/authority 和失败关联针对单前驱 | 新版本保存完整来源链和七根未消费映射；不改写前驱回执 |
| `q2_retry_collect.py` 绑定旧 schema、旧 receipt 与原窗口 | 本次收集绑定新唯一窗口；旧包只作不可变历史输入，不能另开窗口补旧 EOF/stop/seal |
| `q2_retry_delivery.py` 提供保守跨钟绑定和剩余时间准入 | 可复用算法；不放松总 300 秒、2 MiB 总池、阶段上限或收尾余量 |
| 修复后失败结果增加有界 diagnostic | 新结果明确字段、类型和预算；旧原始 JSON/摘要按旧版本保留，不允许任意异常文本或未知字段 |

Namespace pin 只从已鉴证并受保护的同 boot 来源传递；受限角色比较实际 self，
管理员准备/owner 保留 PID 1 与 self 对照，原 Q1 guard 不变。noatime/no-follow
历史读取和 SQLite 无副作用读取贯穿 P3/P4/P5/P6；拒绝权限错误后的放松重试。
如果实现需要新增保护对象、声明或诊断文件，须在原空间内列入白名单、来源摘要、
存储 reservation 和 seal；不能把新增输出作为未计费旁路。

## 窗口、容量与验证

外层在首次探测前起 300 秒；guest≤270 秒，准备≤140 秒，owner≤120 秒，stop≤3 秒。
一次保守时钟映射和同一绝对截止时间贯穿运行、停止、收集、EOF、fsync 与 seal。
内部原更小角色限额保留。新增管理 CPU≤300 秒、512 MiB/64 tasks；独立运行域
CPU 合计≤400 秒、内存合计≤1536 MiB、tasks≤1024，分别检查嵌套峰值。
探测/交付/只读收集共享外部双流 2 MiB 总池，不另开第二窗口或输出额度。

P3/P4/P5 列账全部旧安装/source/build、普通 state、journal、捕获/声明以及两轮
保留承诺，再加新峰值安装、账本、日志和最终封存。保留需求的 256/32/64/64 MiB
四类总上界、原各类 inode ceilings、七根各 1 MiB/128 inode 及 Q1 196 MiB 承诺。
唯一设备/project 和同一实际费用正确去重，块与 inode 分别核对。不能以未完成
运行、ledger 空或新 epoch 退款；容量不足 BLOCKED，不清理、扩容或借用别类额度。

| 风险 | 必须验证 |
| --- | --- |
| 新失败被误当旧 parser 失败 | 双前驱准确来源/argv/流/结果；缺前驱、错类型、未知交付、已有 target 或消费均拒绝 |
| 历史 FAILED 被清掉或泛化 | 精确历史 unit/InvocationID/退出状态且无工作可保留；未知 failed、重置、重启、身份漂移、failed manager 均拒绝 |
| namespace pin 被自证或伪造 | 管理员/owner 双观察到受保护配置/来源/boot 的完整链；错 pin、错 boot、self 不符、读取被拒和来源变更均失败关闭 |
| 排队状态被误认运行 | 真实排队状态只有限观察；job/InvocationID/PID 变化、回退或 deadline 耗尽不得重发或当作运行/停止证明 |
| 历史读取产生副作用 | no-follow/实际 fd/noatime、无保护降级拒绝；SQLite 合法固定 schema、空表/generation、无 sidecar、摘要保持 |
| 空根复用不成立 | 七根精确身份/限额/成员及两份 ledger、grant/消费材料共同核验；部分已用、未知状态或 store 结构误判均阻塞 |
| 新对象覆盖或身份重用 | 全部旧身份/路径去重、别名拒绝、create-only、并发败者、重复入口与部分完成拒绝 |
| 漏算第二轮或未来证据 | 全部历史实际/承诺、安装峰值、块/inode、未来诊断/封存、唯一域计费和设备剩余容量负例 |
| 假完整或窗口刷新 | 准备耗时、跨钟、guest 挂起、非零退出、缺 EOF、输出超限、stop 失败、树不空、缺 seal 分层保留 |
| 来源与安装不一致 | 准确 commit/tree/wheel/source metadata、普通账户访问和原能力集合；摘要不符即拒绝 |

P2 明确区分模型、真实本地文件/权限/管道及安装验证；只有 P5 形成新的 guest Q2
运行证据，不以本地 PASS 代替。无需为本 scope 重跑 Q1 历史实验或 H06–H13。
失败仍交付结构化报告、完整可得原流、缺项说明和唯一保留材料，不要求用户清理重跑。

## 完成定义

交付包括准确 D 与固定安装物、私有一次入口、P3/P4 回执、一次实际运行材料、原
client 退出/EOF、实际 child 身份、独立停止、树空、分层 seal 与历史保持结果。
代码就绪但未运行时明确 READY/BLOCKED，不能宣称 Q2 完成。收集 complete 与
Q2 acceptance 分开；缺任一原 Q2 合同所需证据均不接纳，production 仍受原限制。

两次旧尝试的已证实 EOF/退出事实保留，原缺失的 invocation、独立 stop 或 seal
不由新结果补判。任何本次失败都保留实际边界；此后只允许保留式只读核验，不
刷新原窗口、不替换冻结候选、不自动再发请求。第二次运行或实质变更另行决定。
