# Q2 固定内核事实读取：Owner 决定

- Decision Authority / Owner：当前项目 Owner（本工作会话用户）。
- 决定时间：2026-09-27 23:41:45 +08:00（本条消息的会话时间上下文）。
- 本地归档事件：`LH-Q2-KERNEL-FACT-READ-CLOSURE-20260927-01`；不是平台消息 ID。
- 稳定来源：本文件保留本次准确 Owner 回复与紧邻确认语句，供 Owner 核对。
- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- Documentation A：`887b640b394f9983f37dfe97c58ba35aaa099359`。
- Scope：`LH-Q2-KERNEL-FACT-READ-v1`，准确 A 的 K0–K4。

## 准确 Owner 回复 B

> 按原 R，批准 A 887b640b 的固定内核事实读取方案，关闭 LH-Q2-KERNEL-FACT-READ-v1 Gate，继续实施；同意将本轮脱敏结论、方案及登记文档推送至公开仓库 infra-local-hand。

## 紧邻确认请求中的准确决定语句

> 按原 R，批准 A 887b640b 的固定内核事实读取方案，关闭 LH-Q2-KERNEL-FACT-READ-v1 Gate，继续实施；同意将本轮脱敏结论、方案及登记文档推送至公开仓库 infra-local-hand。

该请求明确说明：本地预检在 host boot 读取权限处阻断；已提交局部 A `887b640b`；
普通证据保护不变；原 R 要求架构变更批准后实现；自动审批曾拒绝本轮公开推送。
本次明确答复覆盖该局部方案和这些脱敏公开材料，不公开原图、私有 host 路径、
实际 boot 值或原始机器输出。

## 独立关闭范围

仅固定 boot 与本进程 mountinfo，在 fd/procfs/挂载身份资格核验后采用普通
只读内核视图读取，含准确 A 明示的 namespace 环境假设和内核元数据变化披露。
原普通身份、旧 pin、证据 O_NOATIME、预算、双钟及无消费/无远端本地分支不变。
授权 K1–K4 实现、隔离验证、准确交付与条件现场验证；不授权消费、完整执行、
提权、系统配置变更或新的内核读取对象。

本记录与 AGENTS.md 的 CLOSED 登记独立构成 C，只含关闭 bookkeeping，
不包含新实现、测试源或探针。准确 A 三文档原字节及历史 OPEN 标签保留。
后续 D 必须以本 C 为祖先，保持 R→A→B→C→D。原已关闭 scope 及冻结
runtime 均保留；H07、完整费用、wrapper 来源、文件系统资格仍不因此通过。
R 的直接来源/完整性、Owner mandate/authority、无规则例外及变更规则保持。
