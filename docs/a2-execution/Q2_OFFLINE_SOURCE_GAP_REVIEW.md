# Q2 完整回执后的离线来源差额

2026-09-28 +08。本记录接续[完整本地观察回执复核](Q2_KERNEL_FACT_READ_FULL_RETURN_REVIEW.md)，
核对源码基线为 `044cee6962980f02c13db54d38c770531029c21a`。
K4 回执已收到并完成限定核验；无需重跑、再次粘贴相同 JSON 或重复批准已关闭范围。
本次是既有材料与源码的离线核对，没有新增现场事实、实现 D、运行包、Gate 关闭或执行批次。

## 本轮收敛

| 项目 | 已有证据能确定什么 | 仍不能确定什么 |
| --- | --- | --- |
| 对象与费用 | K4 的五树包含 42 个去重对象；已分配量为 13,189,120 bytes。另有 7 个已知相邻对象未观察。 | 这不是完整 host 账单。费用分类、历史未来义务、原生审计峰值和联合准入不能从当前 stat 或目录名产生。 |
| H07 历史时钟 | 两份固定旧 anchor 原件均已找到；其 schema 确实不含历史 host boot/BOOTTIME。guest sample 本身有 BOOTTIME 来源。 | 缺项不能由 K4 的当前 boot 或新采样倒填。首次远端以前生效的绝对截止与独立停止覆盖仍未证明。 |
| wrapper 原件 | 当前 attestation 保留控制文件的 metadata/hash；原 collector 读取原字节后没有将其保存进结果。 | 当前私有索引和两个后续预检包未找到准确 wrapper 原件。摘要不能还原脚本，也不等于获准采用为执行 pin。 |
| 写入器身份 | K4 原件报告普通身份及同一普通身份拥有的固定父目录；现有写入器仅接受 root 身份和 root 所有目录。 | 若身份和目录条件与该次回执相同，现有写入器会拒绝。此结论限于报告时点，不声称当前原机条件未变。 |
| 文件系统 | 回执已有 ext4、4 KiB statvfs、父目录分配量及 flags 等局部事实。 | 未证明 superblock 几何、父目录增长、写前峰值、原生审计或 fsync 持久资格；不能据此放行 marker。 |

私有对象清单及来源关系留在既有私有归档；不公开真实路径、用户数值、boot、设备或 inode。
42 项观察与 7 项已知未观察对象合计只是 **49 项核对清单**，不是“完整系统只有 49 个对象”。
已观察目录下三份派发输入副本也不能因目录位置直接归入 capture。
`capture_admissible`、完整账单和未知义务继续保持未知，不将未知填零或断言 64 MiB 必过／必超。

## 实现与批准要求的区别

下列引用均按上述准确源码基线核对；冻结 A 的历史字节保持不变。

| 来源 | 核对结果 |
| --- | --- |
| [host A 要求](q2-host-window-consumption/REQUIREMENTS.md)与[架构](q2-host-window-consumption/ARCHITECTURE.md) | 要求可信受保护父目录、准确身份／对象绑定、写前资源上界、持久资格及 H07 全域期限。A 没有要求为了准入而将既有普通用户目录改为 root 所有。 |
| [窗口写入器](../../tests/e3_host/q2_host_window_record.py) | `HeldPrecheck`、目录链及预检验证附加 root-only 条件；文件系统实现还采用真实块设备 superblock 和禁用全局 DIR_INDEX 等窄 profile。这些是当前 D 的支持限制，不是让 Owner 修改主机以满足实现的指令。 |
| [完整入口](../../tests/e3_host/q2_reconciliation_entry.py)和[事实门](../../tests/e3_host/q2_host_window_contract.py) | 完整入口目前仅离线验证后拒绝；`guest_input_builder` 未派发。现场事实门有意拒绝，因此身份不匹配是附加实现差额，不是当前已经尝试 marker 后的现场错误。 |
| [远端交付组件](../../tests/e3_host/q2_host_window_delivery.py) | `remote_deadline_proof` 对现有来源保持 UNPROVEN。loader 的迟到拒绝层不能代替对阻塞操作及 manager 另建域的独立监督；内存 wrapper 适配也不建立来源采用权。 |
| [旧启动入口](../../tests/e3_host/q2_startup_retry_entry.py) | 首次远端时钟 probe 早于后续带相对运行时限的 guest 命令，不能证明首次 probe 已受原绝对期限监督。旧入口不能绕过现行拒绝。 |
| [停止组件](../../tests/e3_host/q2_supervisor.py) | 对已经绑定的原实例提供停止与树空核对；不能由此推导首次 probe、SSH/sudo、管理器另建 unit、collector 与持久收尾全部受同一个域覆盖。 |

普通身份支持是既有 CLOSED 范围内的修复候选：必须绑定准确可信操作者、原 host/boot、
固定父目录及完整保护检查。不能只把某个用户数值加入 allowlist 或删除 root 判断；
身份支持也不会自动证明分配峰值、完整账单、wrapper、H07 或联合 guest 资格。
目前没有因以上发现而放宽任何产品拒绝条件。

## 后续工作的边界

| 工作 | 接续方式 |
| --- | --- |
| 既有原件映射、状态修复、费用／机制证明义务表、既有 CLOSED 内的实现修复与隔离验证 | 可继续自主进行，不重复请求原范围批准。 |
| 在既有档案中恢复准确、已采用的原件或原有监督证据 | 先只读核验；保持原来源用途、机制、对象、预算和顺序时，不因新找到证据而自动重开范围。 |
| 扩大固定取证对象，或将仅获准用于 boot 的 attestation 字段提升为 wrapper 执行来源 | 先形成准确可审查的受影响方案和 A，再依固定 R 处理该具体变化。 |
| 新增远端监督设施、改变首次远端之前的准备顺序或证明语义 | 先形成机制、资源、来源及停止覆盖方案；不先执行远端 probe 再补证明。 |

当前没有可证明完整 Q2 准入的路线，也没有新的用户操作请求。
原单次启动重试仍 NOT ISSUED；`allow_run`、`allow_consume`、Q2/Q3 验收及生产支持仍为 false。
本次未运行 wrapper、host/guest 命令、marker 写入器或新产品测试。
既有[定向验证与通用 CI 失败](Q2_KERNEL_FACT_READ_IMPLEMENTATION_REVIEW.md)分别保留，未改写为全仓 PASS。
