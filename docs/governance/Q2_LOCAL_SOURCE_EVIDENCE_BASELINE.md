# Q2 固定本地来源补证：准确待审基线

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；根 AGENTS 中的直接来源、完整性、Owner mandate/authority、无例外及变更规则保持。
- Scope：`LH-Q2-LOCAL-SOURCE-EVIDENCE-v1`。
- 状态：**PROPOSED / OPEN / AWAITING OWNER**；本范围尚无 Owner B、关闭登记 C 或实现 D。
- Documentation baseline A：`b8b9ec3da3de43b72e4e17416ea6633494d50c1d`。
- A tree：`5c889b608aaca378e3fa22566b08fbf5701df8d5`。
- A 直接父提交：`14d19f1f52d687afa360353aadecd6ea17725310`，为另行完成的既有 v1 记录绑定修复。

| 文档 | bytes | SHA-256 |
| --- | ---: | --- |
| [需求](../a2-execution/q2-local-source-evidence/REQUIREMENTS.md) | 8554 | `0ae9ee2403851191be6863c4fdd685d477586d94fccfb9312e11d19f160b15f7` |
| [架构](../a2-execution/q2-local-source-evidence/ARCHITECTURE.md) | 9516 | `b31f342c6fbef4411daa63af1c4c7993cc28507fa989438959816c3e086bbc2d` |
| [实施方案](../a2-execution/q2-local-source-evidence/IMPLEMENTATION_PLAN.md) | 7460 | `9452714bcab444c68089e790f3e5ee378ec0c368fcd13f7fe5d0edc49212c200` |

A 只新增上述三份文档。其“尚无 A/B/C/D”描述形成 A 前的历史状态，本文登记真实 A，
不修改冻结字节，也不把本登记当成 B 或 C。

## 需要这次准确决定的原因

原 K A `887b640b394f9983f37dfe97c58ba35aaa099359` 保留原五组目标与 pin，
两项固定内核读取只用于旧 local preflight。本提案新增七个相邻文件和四份控制文件，
将固定内核读者限定复用于新的 local-only 分支，并窄采用原 attestation 中四项
路径、长度和摘要作为静态匹配基准。因此它改变固定目标和来源采用，须按原 R 的
受影响范围规则先有准确 Owner B 和独立 C，再实施；一般“继续”不替代这项具体决定。
已关闭且未受影响的分析、修复与隔离验证继续有效。

## 准确范围与复核

本地原普通身份，仅七文件 metadata/hash、四文件条件匹配 raw、两个固定父目录
及必要 metadata 祖先、两项固定 kernel 视图。不重扫 K4 的42对象，不把异时观察
合并成同刻完整49；普通文件有效内容上限10,490,352 bytes，含超长检测实际读取
上限10,490,363 bytes。内核实际读取另限1,048,707 bytes；输入16MiB、双流输出
2MiB、准备140秒/总300秒保持。只有一次初始原host调用，无自动重试。

独立最终文档复核已核对固定 P/M/T、49成员结构、7+4长度及摘要、单次实际读取
计量、错误分类、私有 raw 和来源采用边界，没有剩余必须修正项。完整报告私有保留。
此为提案审查，不是原 host 权限/ABI/文件系统资格、实现或现场通过证据。

不执行 wrapper，不连接 guest，不创建 marker，不消费 Q2；不批准普通 writer
内核例外、H07 监督准备、完整账单、FS 分配峰值/持久资格或 Q2/Q3 验收。
四份 raw 和真实路径/机器身份只私有留存。本轮没有新采集代码或 RAM 包。

Owner 如决定实施，可明确回复：

> 按原 R，批准 A b8b9ec3d 的固定本地来源补证方案（LH-Q2-LOCAL-SOURCE-EVIDENCE-v1），关闭该范围 Gate，继续实施。

上句是待决定文本，**不是已发生的 Owner B**。收到准确决定后先独立登记只含关闭
记录的 C，再从该 C 实施 L1–L6；不重开无关 CLOSED 范围。
