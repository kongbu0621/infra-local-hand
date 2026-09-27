# Q2 监督器启动修复后单次新批次 Owner 决定

- Decision authority / speaker：Owner，本会话用户。
- Record event ID：`LH-Q2-SUPERVISOR-STARTUP-RETRY-CLOSURE-20260927-01`，仓库事件标识，不冒充平台消息 ID。
- Decision submission time：`2026-09-27T13:13:13+08:00`，本会话提供的消息时间。
- Source：Owner 对紧接在前的准确基线与整批范围请求的直接答复。
- Stable retained reference：本文件在独立 CLOSED 登记 C 中的决定副本；准确 C 由 Git history 定位。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- A：`47b351b2b943bf1d6f1c71cfeb031157a2eb70cc`。
- Scope：`LH-Q2-SUPERVISOR-STARTUP-RETRY-v1`。

## 准确决定及其请求上下文

请求引用的[已提交基线记录](https://github.com/kongbu0621/infra-local-hand/blob/79b1c7b7840a78c53c30098659a9d58e6b8bfa56/docs/governance/Q2_SUPERVISOR_STARTUP_RETRY_BASELINE.md)
固定 R、完整 A、三文档摘要、运行候选及一次新批次边界。紧接在 Owner 决定之前的
助手请求中，与本决定相关的原文为：

> 下一次运行的三文档基线 `47b351b`也已提交。旧尝试仍为 INCOMPLETE，尚未重跑。
>
> 仓库 `AGENTS.md` 和旧批次 T05 限定原授权只能执行一次，现已消费。因此需要你一次批准新基线：使用固定修复候选，保留全部旧证据，在原累计预算内完成新工具实现、验证、交付及一次新的 300 秒 Q2 批次。
>
> 回复“批准新批次”即可，范围内不再逐项询问。

Owner 完整原文：

> 批准新批次

此答复批准上述准确基线及其明确的一次整批范围，关闭该范围的 Gate。它不是
无限范围的“继续”，也不为已消费的旧尝试刷新期限或补写证据。R 的可读直接来源、
摘要、Owner 权限、采用规则、无例外及变更规则沿用根 `AGENTS.md`。

## 获批边界

允许 C 后实现、验证和交付专用新严格合同及工具，并在准确同一隔离 guest 上完成
一次不超过 300 秒的新批次。固定运行候选为 `b49d3df3d1e76813faf08e59ab4975e25279c2fc`，
tree `2d957ccf1d9cbdf5e538189c6b68d56f34590a42`，wheel SHA-256
`c077a8f8aa2f0c3147228602746fd459a6d13267df299a84835331ad35ef158b`。
新编排 D 单独固定，不能动态改写冻结运行候选。

双前驱失败、两份历史 ledger、全部原准备/恢复/运行来源、发行、reservation、
期限、流与不完整结论保留。准确历史 FAILED 实例不重置、不重启、不删除。
仅在全部联合现场鉴证通过后复用原普通账户配置和七个未消费根；新对象及身份
create-only，与全部历史去重。四类 byte/inode 上界按历史与本次累计，保留未释放
承诺、安装峰值和最终证据费用；时间、CPU、内存、tasks 及输出遵守 A。

只运行原 `host.inspect`、空 inputs 与固定三阶段；准备、发行、捕获、退出、停止、
树空、seal 与 Q2 接纳分别报告。代码或收集通过不代表实机接纳，新结果不补判旧失败。
不新增账户/project、不改 quota、不清理或退款、不扩容或增加 capability/依赖，
不包含 production、GX10、真实 NAS、Q3、H06–H13 或 E4–E6。

范围内不再逐项询问。第二次新运行、更换冻结候选或实质范围变化仍须另有准确决定。
本 C 仅记录 B 和 CLOSED，不修改 A 三文档，不混入源码、测试、prototype、依赖或
运行配置；D 必须以独立 C 为祖先。以前的已批准文档与不受影响 CLOSED 范围保持。
