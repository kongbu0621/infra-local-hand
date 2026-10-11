# 宿主重启后的固定本机读取：待审基线

2026-10-11；PROPOSED / Gate OPEN / NOT APPROVED。
Scope `LH-Q2-CORE-HOST-REBOOT-READ-v1`，仅HB1–HB2。

规则R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，直接规则来源与完整性、Owner
mandate、Owner-only authority、无例外及变更控制均保持。准确A
`b2a326036b634bb007a6adeec8929084bce3ccbd`，tree
`be83d89f0bd22249b3d576c4b4c56e00816d3107`，只新增以下三文档：

| 文档 | SHA256 |
| --- | --- |
| [需求](../a2-execution/q2-core-host-reboot-read/REQUIREMENTS.md) | `56c4b766a082366529a6c05b067c9bba520998e7be22bcc304a78a1f796f2ffa` |
| [架构](../a2-execution/q2-core-host-reboot-read/ARCHITECTURE.md) | `6d56e57ea204ff3a97ab8ae7c9f765bdee7191e06f843b94db7f59fa2bfbdc1f` |
| [实施方案](../a2-execution/q2-core-host-reboot-read/IMPLEMENTATION_PLAN.md) | `dfa75333447a68a25ce2477a772003fd650ef17307a1855b07de021031cf283e` |

Owner直接要求修复问题、推进核心及继续屏蔽外围，随后对重启历史回答“重启过宿主机”。
这些说明支持准备本方案；没有针对新A的Owner B，不登记CLOSED或执行许可。

当前11b为INVOKED_FAILED_UNCONSUMED；RP2终态、RP1冻结及全部旧原件保持。
普通失败输出修复见[原现场记录](../a2-execution/Q2_CORE_RUNTIME_PREPARATION_FIELD_20261011.md)。
后续读取只针对原Q1 fixture的固定本机对象，不向任何远端发送信息：host boot/命名
空间、原pidfile/serial、最多两个来源绑定PID、六个镜像对象metadata、固定工具及一次
原TCP转发端口的本机监听查询。不启动VM、不发SSH、不修改镜像/配置或发行07a。

私有review已核对两归档重建、原启动argv的NUL字节摘要、六镜像device/inode、十个
RP2实际本地返回、十五个caller/dependency摘要和原freeze/terminal。仅评审的数据
proposal SHA256 `2deacf7102795f99ea789c20c91ad6ee4b8ff57352156dcd951f112d069c108d`；
目的地、对象清单和路径私有。没有创建新reader、执行准备池、执行归档或现场观察。

已批准成本仍25283 MiB/7364 inodes及十八份完整维护义务。待批新增准备及捕获各
2 MiB/64 inodes，拟总25287 MiB/7492 inodes；不新增维护代数、不退款。源/运行上限
使用现档位2，单次读取、单个控制命令；失败即停，不补采、不重放、不换工具重试。

Owner若关闭准确R/A的HB1–HB2，独立C只记录真实决定，D下降自C；正常PR merge
保留次序，HB1验证/发布/冻结完成才HB2。当前HB1 NOT_STARTED，HB2 NOT_ISSUED；
H01/Q4/H11 NOT_RUN。读取成功不是启动、维护或核心的授权，必要后续方案依真实返回确定。
