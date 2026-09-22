# A2 受限执行 E1–E3 Owner 开工决定

- Decision authority / speaker：Owner，本会话用户。
- Record event ID：`LH-A2-EXEC-MCP-E1-E3-CLOSURE-20260922-01`，仓库事件标识，不冒充平台消息 ID。
- Observation time：`2026-09-22T13:56:14Z`，executor 记录已收到决定的 UTC 时间，不声称是原始发信时间。
- Source：本会话中，Owner 紧接下面保留的准确基线/范围确认请求作出的直接答复。
- Stable retained reference：本文件在独立 CLOSED 登记提交 C 中的副本；C 的准确 SHA 由 Git history 定位。
- Gate rule baseline R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，沿用根 AGENTS 已固定且已读取的规则。
- Documentation baseline A：`79f73faedcd9cde4164b0d1625782dae27db6c2f`。
- Authorized implementation scope：`LH-A2-EXEC-MCP-v1` 的 E1–E3 隔离实现、打包与验证。

## 保留的直接上下文

助手上一条审查结果明确保持以下准确基线：

> `79f73faedcd9cde4164b0d1625782dae27db6c2f`

并明确请求：

> 新 MCP 尚未实现。按仓库 `AGENTS.md` 的开工规则，下一步仍需你明确批准该基线的 **E1–E3**；本轮检查不代替实现后的测试或 GX10/NAS 实机验收。

Owner 随即答复，原文完整保留：

> 好，进入下一步

## 决定的上下文绑定与执行范围

上述答复接受紧邻的、已经给出准确 A 和 E1–E3 范围的开工请求；R 沿用该请求引用的根 AGENTS。
本记录保留 Owner 原话，不将其改写成 Owner 没有说过的长句，也不把“下一步”扩展到未请求的阶段。
据此将且仅将准确 R/A 下的 `LH-A2-EXEC-MCP-v1` E1–E3 登记为 CLOSED。

允许独立 job 核心、固定六类作业映射、同 broker 的维护 CLI、MCP adapter、Plugin、客户端证据重组，
以及合成身份/隔离目录中的契约、恢复、权限、构建安装与证据验证。
E3 真实隔离 cgroup 集成仍是可部署候选的必要门槛；当前环境不能验证的项目必须如实保留，不能改成 PASS。
E4 实际客户端私有接入、E5 GX10/S2 部署切换、E6 真实 NAS/A2、Git Authority 和生产范围不在本次决定内。

本提交 C 只保存决定及 Gate 状态，不修改三层文档或加入源码、测试、依赖和运行配置。
实现提交 D 必须以 C 为祖先。三层文档在 A 上的 DRAFT/OPEN 标记是批准前状态，准确字节保留。
既有 S1 与 Ledger 本体 A2 closure 保持原范围；S2 仍 OPEN。实质变更按既定规则重新审查。
