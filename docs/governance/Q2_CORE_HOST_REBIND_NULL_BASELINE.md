# 同一 HR1–HR4 的串口后端最小修订基线

2026-10-11；当前CLOSED，准确修订A `4af01900cfe462cec4762cb04966dab139a0a31c`。
[Owner实际决定](Q2_CORE_HOST_REBIND_NULL_OWNER_DECISION.md)，事件
`LH-Q2-CORE-HOST-REBIND-NULL-CLOSURE-20261011-01`，批准null调整并按原HR1–HR4连续推进。
独立C仅登记；D下降自新C。准确三文档不改，无新增窗口/池/费用或逐项审批。
历史提议记录保留下文，其OPEN标签不再表示当前批准状态。

2026-10-11；**OPEN / NOT APPROVED**，仅原范围中 HR2 startup serial 后端及相关实现修订。
准确 A `4af01900cfe462cec4762cb04966dab139a0a31c`，tree `99679292050d02d5ae75d88309c6473950a1d1a1`。
原整批 A `ee69dc80db82c3fbf3bd2c5d5c0e0ad0882a84c0` 的 Owner 批准与
独立 C `608f8d70c8fd43b82b613f49b26d6870e5e7f944` 保持；不重复请求原镜像
采用、原固定Q1目的地/冻结载荷或整批HR1–HR4权限。需要确认的变化仅file串口后端→null。

| 文档 | SHA256 |
| --- | --- |
| [REQUIREMENTS.md](../a2-execution/q2-core-host-rebind-null-continuation/REQUIREMENTS.md) | `fd6f98eaf7308fbd4a3bc01a60d381a5b41ede4345523dd1842406d835e2e22f` |
| [ARCHITECTURE.md](../a2-execution/q2-core-host-rebind-null-continuation/ARCHITECTURE.md) | `2d120bd215c986ac6c41e0b127d658f7643dd2f2cec7bccf0c2fa3d1e3e2d394` |
| [IMPLEMENTATION_PLAN.md](../a2-execution/q2-core-host-rebind-null-continuation/IMPLEMENTATION_PLAN.md) | `ed5ff3b77f098735e78b29779a754297d17e826fc06da387fc7da28ac69f95e2` |

[离线发现及证据](../a2-execution/Q2_CORE_HOST_REBIND_FIELD_20261011.md)解释为什么原
“只改输出槽并继承有界串口”的前提不成立。此修订不产生新session、窗口、准备池或退款。
同一十九份完整义务及27497 MiB/8214 inodes仍全额保留；原核心捕获不重复计费。
代价是新启动不留串口日志，明确NOT_CAPTURED_NULL_BACKEND；其余受限诊断继续保留。

R仍为 `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，直接来源、完整性、Owner
mandate/authority、exceptions none及变更控制沿用[原批准基线](Q2_CORE_HOST_REBIND_CONTINUATION_BASELINE.md)。
本修订无Owner B/C或运行实现。批准后先单独登记新C，D下降自新C，正常PR merge；
准确D首次CI、独立安装、完整来源/序列化/生命周期验证及冻结完成后才HR2。
HR1 OFFLINE_REVIEW_BLOCKED、HR2/HR3 NOT_ISSUED、HR4/H01/Q4/H11 NOT_RUN。
旧HB2/RP2及其它已用caller仍终结，不重放、不补采；NAS和外围继续暂停。
