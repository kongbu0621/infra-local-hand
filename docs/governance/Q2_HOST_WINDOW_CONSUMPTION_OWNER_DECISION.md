# Q2 host 窗口消费方案：Owner 决定

- Decision Authority / Owner：当前项目 Owner（本工作会话用户）。
- 决定时间：2026-09-27 19:33:24 +08:00（本条消息的会话时间上下文）。
- 本地归档事件：`LH-Q2-HOST-WINDOW-CONSUMPTION-CLOSURE-20260927-01`。
  这是仓库归档事件标识，不冒充平台消息 ID。
- 稳定来源：本文件保留本次 Owner 回复与紧邻的准确确认请求；用户可核对。
- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- Documentation A：`8402f0cc82d8a0ac0b9a56716bf276f41cafea37`。
- Scope：`LH-Q2-HOST-WINDOW-CONSUMPTION-v1`，准确 A 的 H1–H6。

## 准确 Owner 回复 B

> 按原 R，批准 A 8402f0cc 的 host 窗口消费方案，继续实施。

## 紧邻确认请求（准确保留）

`c65ff4e2` 的批准已登记，对账组件已提交为 `8fd84521`，无需重复批准。

当前待确认的是修订 **[A `8402f0cc`](https://github.com/kongbu0621/infra-local-hand/commit/8402f0cc82d8a0ac0b9a56716bf276f41cafea37)**：调整 host 首次落盘和重试边界。原 R 要求这项设计变更单独确认，因此现场入口仍未启动。

若同意修订，请回复：

> 按原 R，批准 A 8402f0cc 的 host 窗口消费方案，继续实施。

## 准确关闭范围与独立登记

本次 B 对准确 A 的三个文档及 H1–H6 作出决定：原 capture 类内的固定 host
消费目录/单一意图；标记取得前的纯本地只读预检查可以重新完整核验；标记取得
以后永久消费并沿用赢家的原双钟；准确 carrier 派生位置、当前 host boot 采用、
可信存储假设及原传输/管理审计日志前置边界均按 A。其余 guest 联合准入、
计费、候选、原唯一运行批次与容量/时间上限保持。

既有 startup A/C 和对账 A/C 仍按各自范围保留。本决定不授权第二次已消费窗口、
任意提前落盘、扩大额度、修改系统配置或冻结 runtime。先实施并验证准确新 D，
再作同一批次的条件交付；Gate 关闭不是现场准入或 Q2 验收。

本记录与 AGENTS.md 的 CLOSED 登记单独构成 C；本提交仅含批准登记，不含实现。
A 的三个文档原字节与历史 OPEN 标签保持。D 必须以 C 为祖先，保留 R→A→B→C→D
顺序，不能把关闭与实现 squash 为同一提交。R 的固定来源、完整性、Owner mandate、
权限、无 exceptions 与变更规则不变。后续实质变更仍触发准确范围重开。
