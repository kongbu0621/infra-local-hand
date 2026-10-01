# Q2 系统管理器启动修复：Owner 决定

- Owner：本仓库 Owner，当前项目会话的用户。
- 决定时间：2026-10-01 21:01:22 +08:00。
- 本地可追溯事件：`LH-Q2-SYSTEM-MANAGER-REPAIR-CLOSURE-20261001-01`。
- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- Documentation A：`ae50aea2639c32021794ecb70730f4b9e781c8d6`。
- Scope：`LH-Q2-SYSTEM-MANAGER-REPAIR-v1`，M1–M4。
- 原始来源：当前项目会话中，紧随准确方案审批请求的用户消息；本文件保留
  原文供 Owner 核验，不以执行器推断代替决定。

## 前置请求

助手已给出 A 的准确链接，说明由系统级 systemd 创建隔离环境，业务仍用
普通身份、零 capabilities，保留校验、原父域上限和旧现场。请求原文：

> 按原 R，批准 A ae50aea 的系统管理器修复，关闭该范围 Gate，执行 M1–M4。

前置请求同时说明确认覆盖实现、验证和含 TASK.txt 的单次 ZIP，
不重装、不清理、不自动重试。

## Owner 准确回复

> 按原 R，批准 A ae50aea 的系统管理器修复，关闭该范围 Gate，执行 M1–M4。

## 决定边界

该回复明确批准上述准确 R/A 和 M1–M4。完整技术、单次现场消费及资源边界
以 A 的三份文档为准，不从“继续”推导额外范围。原 SSH/普通身份/解释器复用，
新固定启动入口、嵌套普通子 slice、新候选 payload 与有限新对象按 A 实施。
安全校验不放宽，旧现场、UNKNOWN 和 lease 保留；无自动重试或生产资格。

本文件与根 AGENTS 的 CLOSED 登记组成独立 bookkeeping C。
A 的三份文档字节及历史 OPEN 标签保持原样；实现 D 必须以该 C 为祖先。
本 C 不包含程序、测试、运行配置或现场操作，不消费运行批次。
