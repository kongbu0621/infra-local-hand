# HR1 原启动器离线复核：串口上界缺口

2026-10-11；范围 `LH-Q2-CORE-HOST-REBIND-CONTINUATION-v1` / HR1–HR4。
Owner 已明确批准 A `ee69dc80db82c3fbf3bd2c5d5c0e0ad0882a84c0`；
[准确决定](../governance/Q2_CORE_HOST_REBIND_CONTINUATION_OWNER_DECISION.md)由独立 C
`608f8d70c8fd43b82b613f49b26d6870e5e7f944` 登记，三文档字节保持。

## 最早阻塞及可核对依据

HR1 在离线核对启动器时确认，原方案关于串口已有边界的前提不成立。
原私有启动源码19,465 B / SHA256
`e3967e1aec61d4c35ac57ac0e56028e131ff8e3b51a2cde1496292c36dcd055d`，
原提议10,795 B / SHA256
`9b5d9a300452632232903e76ca359b192841eae1266f9e27c1d88af0474f4e81`，
均逐字节匹配旧 immutable freeze 和实际返回 index，未运行旧代码或读取新现场。

- 原 `save()` 在源码第49–58行限制单记录64 KiB、累计256 KiB；只覆盖其管理写入。
- 第240、297–301行以 `-serial file:…` 让 QEMU 直接写新文件，没有进入 `save()`。
- 第206–208行要求 VM 的 CPU/FSIZE无限；child只恢复原AS/FD，不为串口设文件上限。
- 新串口文件不在实际返回索引；源码没有持续监管该文件增长。旧串口保护不等于新输出有界。
- 保留控制流测试10,441 B / SHA256
  `3f60c289bc22a099f5442ee6aeec432be144e5c95aa481f7946bdf54ebf90082`
  模拟了创建和启动，没有建立实际串口写入上界。

因此不能证明原 HR2 file 后端在4 MiB启动捕获池内，也不能声称继承了已验证监督。
这不是实际超限或现场失败，未测量当前日志大小，旧启动成功记录仍保持其原有范围。

## 最小修订与实际状态

已准备[修订需求](q2-core-host-rebind-null-continuation/REQUIREMENTS.md)、
[修订架构](q2-core-host-rebind-null-continuation/ARCHITECTURE.md)、
[修订实施计划](q2-core-host-rebind-null-continuation/IMPLEMENTATION_PLAN.md)：
HR2将新启动串口后端改为现有维护已使用的null，不新增日志文件或转发进程。
原六镜像基线、启动/guest/维护/核心会话、出站目的地与载荷、次数、资源和费用保持。
修订后的v3和两侧argv消费者须明确支持null；不得改变旧v1/v2含义。

这个变化超出原A“只改pidfile/serial输出位置”，按固定R的Document evolution与原计划
第9项，受影响的启动接线/HR2及其依赖释放保持OPEN，等待准确修订的Owner决定。
原批准不撤销、不伪装未批准；未受影响的保留来源核对保持有效。

私有离线复核2,234 B，SHA256
`2f65af8a20d3462d9bead1c40e62e853eb37cac40b934625997814fdac349263`，
与独立私有release gate保留。HR1 OFFLINE_REVIEW_BLOCKED，HR2/HR3 NOT_ISSUED，
HR4/H01/Q4/H11 NOT_RUN。新caller/marker/启动/SSH/现场查询均0；自动审批拒绝0。
不存在被消费的新现场窗口。旧HB2/RP2、两归档及旧caller保持，不重放、不清理。
已批准十九份义务及27497 MiB/8214 inodes全额保持，无退款、新窗口或另一个准备池。
NAS及外围继续暂停。本提交只含批准登记、来源核对事实和待审最小修订，无运行实现。
