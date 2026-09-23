# E3 quota/harness 变更基线与待决范围

- Authority：Owner；日期：2026-09-23；Gate：**OPEN**。
- scope：`LH-E3-QUOTA-HARNESS-v1`。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，固定直接来源和完整性见根 AGENTS。
- 提议 A：`415327ebdcc251bb055da9931a7a88990f750b7a`。
- A tree：`6dfdd7341186f14c0a1f58d7ab75ababd8873edd`。
- B：尚无 Owner 对本次变更的准确 closure decision。C：尚无 CLOSED 登记。
- 本记录只登记已有 A，不是 C，不批准实现，不改变三份文档内容。

## 可审阅的准确文档

| 层 | 固定版本 |
| --- | --- |
| 需求 | [REQUIREMENTS.md](https://github.com/kongbu0621/infra-local-hand/blob/415327ebdcc251bb055da9931a7a88990f750b7a/docs/a2-execution/e3-quota-harness/REQUIREMENTS.md) |
| 架构 | [ARCHITECTURE.md](https://github.com/kongbu0621/infra-local-hand/blob/415327ebdcc251bb055da9931a7a88990f750b7a/docs/a2-execution/e3-quota-harness/ARCHITECTURE.md) |
| 实施方案 | [IMPLEMENTATION_PLAN.md](https://github.com/kongbu0621/infra-local-hand/blob/415327ebdcc251bb055da9931a7a88990f750b7a/docs/a2-execution/e3-quota-harness/IMPLEMENTATION_PLAN.md) |

## 要作出的工程决定

是否在上述 R 和 A 下关闭且只关闭 `LH-E3-QUOTA-HARNESS-v1`，允许：

1. 开发独立管理侧、固定对象的 quota observer 和有界无特权客户端；
2. 开发准确配额事实、原分配/预算/代次绑定和恢复记录；
3. 开发真实 bootstrap/helper/reader 的 test-only harness，并在明确交付的隔离 fixture 上验证；
4. 按 Q1 最小可行性 → Q2 绑定/预算 → Q3 正常链 → Q4 故障/恢复的顺序推进。

关键取舍是增加一个拥有 host quota 查询能力的受信组件。普通作业保留非 root 及原隔离。
这个组件的能力较大、查询可能阻塞或涉及 quota 元数据；固定接口、监督、资源上限和实际验收
都是必要实现，尚不能宣称已经安全可用或证明 target kernel 的实际结果。

该决定不批准 GX10 账户创建、特权服务安装、委派、mount/quota 设置、现役服务切换、
E4 客户端接入、E5/S2 或 E6 真实 NAS。实际主机准备须另有准确私有装配和影响交接。
生产支持封堵保持；本地/CI 或部分场景通过不自动成为 E3 PASS。

## 为什么需要新决定

根 AGENTS 已采用的规则要求实质改变架构/受信边界时，仅受影响范围重新为 OPEN，
并按 R → A → Owner 决定 B → 独立 CLOSED 记录 C → 实现 D 推进。
此前“继续推进”覆盖已有范围的必要工作，未明确选择这项新增 host 权限组件。
本轮已先完成证据核验、具体方案和可审阅提交；不能代 Owner 合成决定。

原 A `79f73faedcd9cde4164b0d1625782dae27db6c2f` 的三份文档逐字节未变，
原 C `367632126c1930983a06b1854f63789448633148` 和不受变更影响的范围继续保留。
S1、Ledger A2 无需重新批准。已完成 nsfs 修复及现场输入核验的证据不重写。

若 Owner 接受上述准确基线及范围，随后保存其实际回复和关联上下文，再单独提交 C；
如果 Owner 选择不同权限路线，则先更新三层文档和 A，不能沿用本 A 假称已批准。

## A 的文档完整性

| 文档 | SHA-256 |
| --- | --- |
| REQUIREMENTS.md | `04f28701209a044fbf1b644cb71262ad0e17684702415a783c8f4058f3e41c48` |
| ARCHITECTURE.md | `ffa20073619247b9413667795289633bae396271df53a6cdf798005423c663ff` |
| IMPLEMENTATION_PLAN.md | `943c65fc5f894c96c9b00b421bd6add3828ac6c1657318f06b944c6e5d8fe728` |
