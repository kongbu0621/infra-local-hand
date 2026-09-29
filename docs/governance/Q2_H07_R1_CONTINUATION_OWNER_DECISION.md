# H07 首轮历史异常限定续验：Owner 决定

- Decision Authority / Owner：当前项目 Owner（本工作会话用户）。
- 决定时间：2026-09-29 22:38:51 +08:00（本条消息的会话时间上下文）。
- 本地归档事件：`LH-Q2-H07-R1-CONTINUATION-CLOSURE-20260929-01`；不是平台消息 ID。
- 稳定来源：本文件保留准确 Owner 回复及紧邻请求，供 Owner 核实。
- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- Documentation A：`a08a5055c35009a896ad6c6059d709758cc78436`。
- Scope：`LH-Q2-H07-R1-CONTINUATION-v1`，仅准确 A 的 U1–U4。
- 三文档及摘要：[准确基线登记](Q2_H07_R1_CONTINUATION_BASELINE.md)。

## 准确 Owner 回复 B

> 按原 R，批准 A a08a5055 的 H07 首轮限定续验方案，关闭 U1–U4 范围 Gate；接受首轮清理未知仅不阻断剩余最多两轮，保留原失败及后续停止条件，继续实施。

## 紧邻确认请求中的准确决定语句

> 按原 R，批准 A a08a5055 的 H07 首轮限定续验方案，关闭 U1–U4 范围 Gate；接受首轮清理未知仅不阻断剩余最多两轮，保留原失败及后续停止条件，继续实施。

确认请求已给出准确 A 链接，说明原失败与清理未知不变、仅考虑剩余最多两轮、
后续新清理未知继续阻断，并解释原 R 对准确变更的 Owner-only closure。
本条准确回复关闭该变更范围，不重复关闭未受影响的原 F1–F4。

## 准确生效边界

仅对 run `36577764454` / attempt 1 / round 1 / 原源码
`6b085d9ceb536b9785ea683cd108e92cd8a4eec4` / artifact `11038133434` 适用
新需求“唯一受影响的原合同”supersede 表：该唯一历史 UNKNOWN / cleanup=false
在新准入成立后，不再单独阻断第2/3轮。原失败、原件、未运行的六例与已消费1/3
永久保留；托管新 VM 设施约定及不同 boot 不补原清理/销毁事实。

U1–U4 包括准确来源/续验绑定、有界账户观察和 observed/admitted 身份分离、
schema 2 严格收件、最多剩余两轮手动实验及结果记录。第3轮仍须新的准确源码
修复理由，无新增阻断；不为竞态重复，不重置额度，不 Re-run。后续异常不能继承
首轮历史接受，原病例、限额、停止条件和生产/原 Q2 排除项按准确 A 保持。

本文件与 AGENTS 的 CLOSED 声明构成独立 bookkeeping C；不包含实现、测试、
workflow、runtime 配置或三层文档语义修改。新 A 三文档原字节和历史 OPEN 标签
不变。新 D 必须从此独立 C 下降，C 的准确 SHA 由 Git 历史定位，不预写自身 SHA。
原 R/source/integrity、Owner mandate/Authority、无例外及变更规则均保持。
