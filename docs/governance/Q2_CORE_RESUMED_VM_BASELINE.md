# 当前 VM 的原核心接续：准确已批准基线

**CLOSED for RC1–RC4 only**，scope `LH-Q2-CORE-RESUMED-VM-v1`。
[真实 Owner B](Q2_CORE_RESUMED_VM_OWNER_DECISION.md)，事件
`LH-Q2-CORE-RESUMED-VM-CLOSURE-20261010-01`，保留准确相邻请求和回复“批准”。
本独立 C 只登记闭合；实现 D 从 C 下降，不 squash。

准确 A `b0aa74f9f7a75d70a82575a2e679e540bb47dc1f`，tree
`ab4861032919d3db94c937100d713e3a35b81ba1`，仅含下列三文档。原字节和历史 OPEN 标签保持。

| 文档 | bytes | SHA-256 |
| --- | ---: | --- |
| [需求](../a2-execution/q2-core-resumed-vm/REQUIREMENTS.md) | 4582 | 7812cf87ef8e8d140d33cb05d37aabfe1705f045ed7fd2b73c98e532c25d0ca5 |
| [架构](../a2-execution/q2-core-resumed-vm/ARCHITECTURE.md) | 4951 | b194587e2860f38a77b789bbc55053cd167c8b21bccd0160aaf5f59011da7fd8 |
| [实施](../a2-execution/q2-core-resumed-vm/IMPLEMENTATION_PLAN.md) | 3150 | a3d0017794c63e50e4ce3472df4260993bfc298e19c8f4bf0611794c0e0b69fb |

R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 的直接规则来源已读取，SHA-256
`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
来源/完整性、Owner mandate/authority、无例外和变更控制不变。

RC1 完成历史安装＋当前启动＋新 guest 核验来源接线，保留 10b 六返回及原 freeze/失败/
终态；原 activation 归档 FD 替换为至多524288 B组合归档，55件custodian及128 FD限制不变。
完成 producer/独立consumer、全生命周期/大小/成本核验、main发布、准确D首次CI、
独立安装及三个caller冻结后，RC2只读核验一次原固定guest，不启动VM或重装包。
成功且最终数据冻结后，RC3唯一10c预检及同窗执行原维护（最多两SSH、一次正常关机、
原journal增长、一次原配置重启）；完整原件及实际顶层完成通过才接RC4原07a三案。

十五份维护义务加原核心捕获及RC2宿主输出共19505 MiB/5598 inodes；RC2实际费用
在独立host/guest原上限内另计，所有旧成本不退款。保护和trusted premises不变。
此闭合仅在RC1–RC4内取代旧“无新窗口/补采”限制；旧失败与不可重放条件保持。
批准三文档、必要实现和脱敏结果发布；原件、索引、归档、caller和机器信息私有。
在C：RC1 NOT_STARTED，RC2/RC3 NOT_ISSUED，RC4/H01/Q4/H11 NOT_RUN。
