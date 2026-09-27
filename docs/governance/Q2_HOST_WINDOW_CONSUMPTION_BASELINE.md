# Q2 host 窗口消费：准确待审基线

Authority：Owner；Gate **OPEN / AWAITING OWNER**。
Scope：`LH-Q2-HOST-WINDOW-CONSUMPTION-v1`。
R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；来源、完整性、强制采用及
无自动例外的规则沿用根 AGENTS.md。本记录不关闭 Gate，不新增执行授权。

准确 A：`8402f0cc82d8a0ac0b9a56716bf276f41cafea37`；tree
`138a59d697c86abaae46c03cd04af91b3a7c5360`。
三文档分别位于 [需求](../a2-execution/q2-host-window-consumption/REQUIREMENTS.md)、
[架构](../a2-execution/q2-host-window-consumption/ARCHITECTURE.md)、
[实施方案](../a2-execution/q2-host-window-consumption/IMPLEMENTATION_PLAN.md)。

| 文件 | SHA-256 |
| --- | --- |
| `REQUIREMENTS.md` | `400fe60987be3de44f78ea747b51458f4ccdd08f21cff7654be0b9dd7e2d66cc` |
| `ARCHITECTURE.md` | `82daca9a1a3dd31df423aa6e0904fd44d5e5c6aa19a6364ad3a632dcae84ac7c` |
| `IMPLEMENTATION_PLAN.md` | `8e74f4721017b86c5957a120d6ee1ba33a814d66ffb801443234b6dda76f5881` |

## 已有批准与实际进度

对账 A `c65ff4e25ea6373aabf8db25d304ee7614b96eb5` 的准确 Owner 决定已独立
登记为 C `1491765c64c60a63d6bddf10a049308e404885ca`。受限组件 D
`8fd84521cdd25b455ff148e0c0fed6b5d8e39fe1` 已发布：新增154 PASS/2 SKIP、
旧相关115 PASS，并以准确D复验42工具blob及48真实输入blob。结果及限制见
[实现复核](../a2-execution/Q2_RECONCILIATION_IMPLEMENTATION_REVIEW.md)。

原新旧三文档的首次持久写顺序与跨进程消费在准入失败时冲突，受影响范围已
依 R 重新 OPEN；静态 host 入口在任何窗口和现场副作用前拒绝。本轮未探测
实际 host/guest、未开始运行窗口、未发行，也未提前实现本新 host 顺序。
既有对账批准对不受影响范围继续有效；不要求重复批准它。

## 这次准确决定的内容

- 原预算内允许一个固定 host 消费目录和一份意图，在完整 guest 联合准入前
  持久化；逻辑 ≤16 KiB、实际分配 ≤64 KiB、inode ≤4，均计原 capture 类。
- 明确消费边界：建立固定目录之前只允许本地只读预检查，可重新完整核验；
  排他取得目录后永久消费，赢家沿用其预检查前的原双钟，绝不重新计时或续跑。
- 消费位置由准确旧 carrier 父目录及原 startup C 唯一派生；采用准确回传
  current host boot，只用于本 scope 未来比较，不变更原对账来源分类。
- 明示原已授权传输/管理机制自然产生审计记录的有限前置范围，计入原预算；
  不允许任意诊断文件、新日志设施、系统配置变更或第二次远端运行。

三文档与两份定位/boot原件均已独立复核，准确SHA/长度、AST唯一常量/同父、
固定目录派生和boot字段复算一致。可信文件系统不被范围外回滚/删除是明示
假设；工具不声称能检测已消失的记录。现场保护、完整计费及硬期限仍须验证。

固定候选、总容量、原唯一guest/owner批次和实际执行时间上限保持；本地只读
预检查的重新核验是明示的新语义，不能宣称所有旧重试语义不变。

如 Owner 接受该准确 A，可回复：

> 按原 R，批准 A 8402f0cc 的 host 窗口消费方案，继续实施。

以上只是待审回复示例，不是已发生的 Owner 决定。收到准确 B 后才单独登记 C，
之后实施 H1–H6；不得把本 A、后续关闭和实现合并成一个提交。
