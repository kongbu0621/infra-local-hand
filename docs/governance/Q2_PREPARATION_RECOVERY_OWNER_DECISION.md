# Q2 限定恢复 Owner 开工决定

- Decision authority / speaker：Owner，本会话用户。
- Record event ID：`LH-Q2-PREP-RECOVERY-CLOSURE-20260926-01`，仓库事件标识，不冒充平台消息 ID。
- Decision submission time：`2026-09-26T17:38:55+08:00`，本会话提供的消息时间。
- Source：Owner 对已固定恢复基线的直接批准；完整原文保留如下。
- Stable retained reference：本文件在独立 CLOSED 登记 C 中的副本；准确 C 由 Git history 定位。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；可读取直接来源、完整性、Owner 权限及采用关系沿用根 AGENTS。
- A：`72c06ec68d370333f5ffb1079023917828b3e681`。
- Scope：`LH-Q2-PREP-RECOVERY-v1`。

## 准确基线与批准原文

[已提交基线记录](https://github.com/kongbu0621/infra-local-hand/blob/5aa6d830539b7e0fa9ea12e54b291a99837235f5/docs/governance/Q2_PREPARATION_RECOVERY_BASELINE.md)
固定 R、A、三份文档摘要、300 秒新恢复时窗及准确部分失败边界。
紧接的助手答复请求关闭该范围并整批继续。Owner 本次完整原文：

> 批准恢复基线 `72c06ec68d370333f5ffb1079023917828b3e681`，关闭 `LH-Q2-PREP-RECOVERY-v1` Gate，按 300 秒恢复窗口整批继续，范围内不再逐项询问。

该决定绑定已经提交的 R/A 与范围，不替换原 `LH-Q2-FIXTURE-PREP-v1` 的历史批准，
不把已结束的旧准备窗口改写为有效，也不改判原失败回执。

## 授权边界

允许一个总计不超过 300 秒的恢复管理/捕获窗口：guest service 最多 270 秒、停止最多 3 秒，
鉴证/准备/装配从 guest 入口首次读取前起最多 140 秒，尚未发行的原 Q2 owner 保持最多 120 秒。
各层绝对期限、原较小对象/命令预算以及停止和 EOF 余量必须同时满足，不按步骤刷新期限。

仅接续精确已知边界：原主组创建成功，账户因准确配置解析错误退出且仍不存在，后续准备及运行均未交付。
保留原主组并执行一次更正账户命令、原未交付准备和装配，再进入尚未发生的唯一首次原监督运行。
保持同一 preparation ID、原 plan、失败字节、安装候选和累计容量。新 recovery ID 仅区分追加证据。

禁止重放已完成动作、第二次恢复、新预算、候选替换、回收清理、系统包/挂载变更或旧 Q1 改动。
Q2/Q3 验收、生产、GX10、现役 S1、真实 NAS 和 E4–E6 权限不由此决定产生。

本 C 仅保存决定及 CLOSED 状态，不改 A 的三份文档，不加入源码、测试、prototype、依赖或运行配置。
后续实现 D 必须以 C 为祖先。范围内集中实现、验证和交付，不再逐项询问。
