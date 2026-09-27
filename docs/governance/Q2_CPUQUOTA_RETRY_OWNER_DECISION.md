# Q2 CPUQuota 单次新运行 Owner 开工决定

- Decision authority / speaker：Owner，本会话用户。
- Record event ID：`LH-Q2-CPUQUOTA-RETRY-CLOSURE-20260927-01`，仓库事件标识，不冒充平台消息 ID。
- Decision submission time：`2026-09-27T11:00:03+08:00`，本会话提供的消息时间。
- Source：Owner 对上一条准确基线及整批范围请求的直接批准；完整原文如下。
- Stable retained reference：本文件在独立 CLOSED 登记 C 中的副本；准确 C 由 Git history 定位。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；直接可读来源、完整性、Owner 权限、采用和变更规则沿用根 AGENTS。
- A：`d8e49617efecae199b0874f183530794f8c36e6a`。
- Scope：`LH-Q2-CPUQUOTA-RETRY-v1`。

## 准确决定

[已提交基线记录](https://github.com/kongbu0621/infra-local-hand/blob/ab0a98ec4085a8d8d2ea781ca4e4f383149305d7/docs/governance/Q2_CPUQUOTA_RETRY_BASELINE.md)
固定 R、A、三份文档摘要和新批次边界。紧接的助手答复说明原请求已经发行，
需要明确更换修复候选并开始一次新窗口。Owner 完整原文：

> 批准基线 `d8e49617efecae199b0874f183530794f8c36e6a`，关闭 `LH-Q2-CPUQUOTA-RETRY-v1` Gate，按方案一次 300 秒整批执行，范围内不再逐项询问。

该决定关闭准确 R/A 下的新范围，不改写原准备、恢复或 owner 的失败字节和期限，
不把旧发行恢复成未发行，也不改变原两项 closure 的历史范围。

## 授权边界

允许集中实现、验证、交付并执行一次新的 300 秒管理批次：准确旧失败鉴证、
累计费用核算、固定修复候选独立安装、新 policy/ledger/journal/session/control/
声明/捕获与身份、条件复用原账户配置及七个未消费 quota 根、一次固定三阶段，
完整原退出/EOF/独立停止/封存与旧材料保持复核。

运行候选固定为 A 中的 `9a556322183f0fa80d4edeada4b03c74a26524a5` 及其 tree/wheel 摘要。
编排工具 D 单独固定，不覆盖现场旧安装。原项目限额与新旧累计空间上界不变。
各正常 inactive 准确实例可 start 一次，禁止 restart 或重写旧配置；身份或未消费事实不明即停止。
时间、CPU、内存/PID 和输出遵守 A 的明确上界与嵌套期限，不分步刷新，不自动重试。

不允许新增账户/project、重设 quota、删除旧记录或 reservation、退款、清理、扩容、
系统升级、挂载变化、生产/GX10/E4–E6 或 Q3 接纳。原 Q2 验收仍须真实完整证据。

本 C 只记录准确 B 和 CLOSED 状态，不修改 A 的三份文档，不添加新源码、测试、
prototype、依赖或运行配置。后续 D 以本 C 为祖先；范围内不再逐项询问。
