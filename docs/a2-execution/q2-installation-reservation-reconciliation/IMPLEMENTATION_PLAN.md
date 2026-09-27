# Q2 历史未来安装承诺对账：实施提案

- Authority：Owner；状态：**PROPOSED / Gate OPEN / BLOCKED ON HISTORICAL INPUTS**。
- Scope：`LH-Q2-INSTALLATION-RESERVATION-RECONCILIATION-v1`。
- [需求](REQUIREMENTS.md) → [架构](ARCHITECTURE.md) → 本方案。
- 本轮仅形成文档与可核查的阻断。不得实现对账算法、可执行原型、测试脚手架、运行配置或 guest 对账入口。

## 先完成可评审的输入

保留已批准 startup A `47b351b2b943bf1d6f1c71cfeb031157a2eb70cc`、独立 C
`d4a925c883672fadc7d1b10a8dfe58df18b922cd`、准确 Owner 决定及原文档字节。
其 P1/P2 可继续完成无释放分支的严格工具与隔离验证，结果应是当前容量条件下
BLOCKED。不得输出 READY 或调用 guest 来试试看；唯一获批新运行仍未发行。

本提案先完成以下非实现性工作：

1. 取得原 preparation/transfer、recovery、第二次 bootstrap 所缺的真实 raw。
   有既存可信历史树摘要的，完整展开并复算；第二 staging 无历史锚时，要求真实
   留存来源，不从现状自设 hash 或把源码预期值当作执行回执。
2. 补齐原 preparation/recovery 及后续外层/监督器的准确历史实例身份，逐项证明
   允许保留的失败对象。当前 failed 不能替代原 InvocationID 的来源。
3. 为十条历史 reservation 制作私有可审阅的来源清单：两 owner、两 bootstrap、
   原 intent/preflight、recovery-intent、retry-intent、recovery stage、第二
   bootstrap-attestation；记录 raw 是否取得、原摘要或历史树证明、类别与相互引用。
4. 在不改旧文件的前提下核实 192 MiB、嵌套恢复 192 MiB、独立 64 MiB 的精确
   byte/inode 含义、实际覆盖与未消费 future，固定对账目标和保留集合。
5. 固定唯一尚未发行 startup 计划、准确 runtime 和本 amendment 的非扩大边界。
   缺输入时停在 PROPOSED；不把“批准原则”当成缺失 bytes 的补证。

完成后才能将准确三文档提交为新 A，并让 Owner 审阅明确目标、摘要和金额后一次
决定 B。C 只登记该准确 R/A/B 的关闭，不混入实现；D 从 C 继续。现有 startup C
不能替代本 amendment 的 B/C，也不因本提案而被删除或改写。

## 关闭后拟实施的最小范围

| 阶段 | 交付 | 对应要求 |
| --- | --- | --- |
| R0 | 补真实历史输入、来源与静态账单；准确三文档 A、Owner B、独立 C | I01、I03 |
| R1 | 独立严格 amendment 合同与只读来源/义务校验；原 v1 保持失败关闭 | I01–I06 |
| R2 | create-only 追加记录和采用该记录的有限容量准入；不改变 runtime 或原安装原语 | I03–I07 |
| R3 | 合成及真实本地文件验证、准确 D 和私有交付；明确没有 guest 运行 | I01–I07 |
| R4 | 在原唯一 startup 窗口内联合现场鉴证、保存一次对账记录、重新核算并按原权限决定是否发行 | I02–I07 |
| R5 | 保留新旧记录、完整费用与分层运行证据；如实报告未通过边界 | I04–I07 |

设计落点限于 `tests/e3_host/` 的专用 amendment 合同、对账/容量适配及其测试，
不进入普通 wheel/Plugin，不修改冻结 runtime。具体接口及 schema 在真实输入
与新 A 完整后固定；本轮不提前生成代码。实现应保留严格原入口，明确拒绝把
amendment 记录当作旧 schema 中的任意 release 字段或本次通用重放权限。

现场顺序为来源/状态/预算联合鉴证 → 新意图与唯一对账记录 → fsync/seal → 原
startup 的容量与期限复核 → 如成立才继续原独立安装与一次发行。对账记录本身
的最大 bytes/inodes、日志和收尾开销在首次写前纳入现有类别；部分失败保留，
不删除、不回滚旧对象、不换 ID 或重新启动窗口。

## 验证与阻断

| 必须覆盖的风险 | 预期行为 |
| --- | --- |
| raw 缺失、摘要不符、当前内容冒充旧事实 | INPUTS_BLOCKED；不生成对账记录、不安装、不发行 |
| 只给树根 hash 或不完整 manifest | 拒绝；必须复现原算法全部条目与已锚定根摘要 |
| 192 MiB 恢复义务被重复计算或错误归入第二批 | 核验同一原候选/目标/回执；只承认真实嵌套，不按名称猜测 |
| 已用安装 bytes/inodes 被终止或退款 | 拒绝；实际对象与原摘要始终保留并进入新账单 |
| capture/runtime/quota 等被混入释放范围 | 拒绝；非安装类别和全部 quota before/after 相等 |
| 无历史身份、unit 有 job/PID、树非空或 boot 变化 | BLOCKED；不 reset-failed、stop/restart 或清理 |
| 旧 ledger/七根/配置/来源改变 | BLOCKED；不把停止服务当成可复用的充分条件 |
| alias、并发、重复或部分发布 | 排他创建、完整原请求匹配、缺 seal 不采用；不删除后重做 |
| 新账单仍超 byte/inode/设备容量 | BLOCKED；原 256 MiB/16384 inode 及其他 ceilings 不变 |
| 期限不足、输出超限或捕获不完整 | 保留缺项；不新增窗口、不补判、不发第二个 owner |

离线静态下界与原始回执分别报告。320 MiB 下界不能替代真实旧 raw 验证；补齐 raw
也不能自动消除容量阻断。只有准确 Owner B/C 和成立的新追加记录才允许变更
指定未来义务；尚未终止的任何承诺继续完整计费。

## 完成与当前下一步

当前下一步是取得缺失的真实留存材料或有效历史树展开证明，并核实准确失败实例
身份。输入清单未闭合时，本提案保持 OPEN，不向 Owner 请求立即运行，也不交付
可误解为 READY 的入口。

关闭后实施完成须有准确 D、义务前后账单、原材料保持证明、新追加记录及其 seal，
并严格分开该记录与原 startup 的 prepared/issued/captured/stopped/sealed/accepted
状态。原 startup 的一次运行机会不能复制：本 amendment 不增加第二次批次，
不把未发行变成已完成，不为任何已消费尝试改期限或追认成功。
