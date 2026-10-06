# journal 保留数据扩容准确方案及待决记录

2026-10-06，Asia/Shanghai。状态 **OPEN / NOT APPROVED / NOT ISSUED**。
Scope `LH-Q2-CORE-JOURNAL-GROWTH-v1`，仅 J1–J3。本记录不是 Owner B 或 CLOSED C。
当前交付为本地核查和可审阅方案，未实现工具、未建立新 marker/SSH、未停机或扩容。

## 准确基线

Authority 为 Owner；原 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，
[直接固定规则](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)
本轮完整读取；源 SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
Owner mandate、无例外、无自动升级/弱化和 material change 重新审阅规则保持。

Documentation A：**`59948ec4fedb807a31cdbff77acc134e84414160`**。
Tree `57b57cc151c711f630bb047ac63fed35c74285dc`，parent `3412fa65c5fdced51db4254e44dfbc4d8ad9f89b`。
A 仅包含三个新文档，无新实现、测试、依赖、运行配置或原始机器数据。

| 文档 | bytes | SHA-256 |
| --- | ---: | --- |
| [需求](../a2-execution/q2-core-journal-growth/REQUIREMENTS.md) | 9415 | `93ac5383bb1823086dc0546fb4eebcf1f70ffd7e7a824247b3f6c9e210417f4d` |
| [架构](../a2-execution/q2-core-journal-growth/ARCHITECTURE.md) | 8858 | `5b703c51afab91676851af1bcaf4464469ea2183f7bd5dbc79d120a1efcc6f28` |
| [实施计划](../a2-execution/q2-core-journal-growth/IMPLEMENTATION_PLAN.md) | 5520 | `aa3c04b8fce9a914dd7009644ac0a3a853a8d4f38de8f85b73a0d644dd723e60` |

准确 B 后必须先独立 bookkeeping-only CLOSED C，再以其后继实施 D，不能 squash。
本 OPEN 登记不会更新原已消费观察或四个核心请求的授权状态。

## 已核查事实及其限度

固定 start.sh/原 plan/保存的容量输出均按架构 pins 本地 O_NOATIME 读取，未再次连接 guest。
另外仅读取由同一启动配置绑定的 journal 镜像头 104 B，两次头部与前后文件身份稳定：
qcow2 v3、cluster bits 16、virtual size 268435456 B，backing offset/length、snapshot count、
encryption method 和 incompatible features 均为 0。未调用 qemu-img 去抢正在使用的镜像锁，
这不是全镜像检查或当前 VM 静止证明。

保存的 guest mount 结果是整块 virtio 盘 ext4；固定启动脚本无 QMP、monitor 关闭。
据此选择停机扩容路线，但 J3 仍要核对真正运行实例和设备，不能把静态脚本冒充现场身份。
本地宿主图像所在文件系统当前有超过 1296 MiB/370 inode 的可用量；仅是一次宿主观察，
既不补采 guest，也不保证执行时容量或排他性。没有读取私钥原文或公开原始路径/UUID。

保留 [O1–O3 实测](../a2-execution/Q2_CORE_CAPACITY_OBSERVATION_REVIEW_20261006.md)：
journal 218.51953125 MiB 可用，四旧核心条件门槛 286 MiB；假定再一批同预算，基础门槛 321 MiB。
拟扩到 512 MiB 虚拟容量并要求最终至少 400 MiB 普通可用，不把虚拟大小等同于可用大小。

当前核心代码 `q2_core_delivery_dispatcher.py` 的旧 scope 检查要求旧 boot 与新 HELLO 对应
（检查基线的 `CORE_PRIOR_SCOPE_BOOT`，并见原 post-locale A 的明确要求）。
因此不能在扩容重启后直接重跑旧包。本次还需披露新 pidfile/serial 参数；未来核心批准必须
明确采用这次维护代次和实际管理关系。不能删校验或把 VM 重启算作 H11。

## 待批准的最小动作及风险

一次固定 `lhqjgrow-20261006a`：先实现/验证并冻结工具，再条件执行一轮维护。
最多一个 marker、一次正常关机、一次 VM 启动、两条固定 SSH；仅 journal 256→512 MiB。
完整离线备份与校验先于镜像修改，原文件内容/UUID/挂载关系保留，正常启动后原 ext4 增长并回收证据。
失败不重试、不补采、不强制关机、不自动回滚、不清理；可能留下已关机或部分扩容状态。

新维护新增控制/捕获 8 MiB/32 inode，备份池 320 MiB，整个目标镜像池 576 MiB，维护余量 128 MiB；
连同旧 264 MiB/80 的当前 host 条件为 1296 MiB/370 inode。900s 观察窗口、780s 后不启新修改。
其余准确数量、字段、工具动作及差异以三文档为准。维护预算不是新核心预算。

必须接受整个隔离 guest 的中断、易失状态/boot 改变；必要旧证据若只有易失副本则关机前阻断。
新 pidfile 保留旧 pid 文件，串口 backend 改 null 保留原串口原件但不收新启动串口；
这不是日志完整保证。超时不以强杀正在修改数据的工具制造“硬退出”，底层退出/用量可能 UNKNOWN。
保留完整历史承诺，更早 host UNKNOWN 不单独阻断；容量不排他、可能发生空间竞争或掉电损坏，
备份不等于四盘一致性恢复。所有这些改变都须准确批准，不属于原 O1–O3 权限。

本范围不运行 H01/Q4/H11，不修改生产限制，也不批准下一核心批次或其新 boot 采用。
支线继续暂停。只读事实、计算、文档链接和 `git diff --cached --check` 已核对；未运行新源码测试、
未取得扩容实测或业务结果，不以历史 CI 代替新维护验证。

## 可核对的批准文本

以下只是待决请求，不是已发生的 Owner 决定：

> 按原 R，批准 A `59948ec4fedb807a31cdbff77acc134e84414160` 的 `LH-Q2-CORE-JOURNAL-GROWTH-v1`，关闭该范围 Gate，执行 J1–J3；先独立 C 再实现。接受文档中的一次隔离 guest 停机/启动、journal 256→512 MiB、两条固定维护连接、新 pidfile 与 serial null、boot/易失状态变化、备份及非原子恢复、历史 UNKNOWN/全额承诺、非排他容量和 mutator 可能逾期未闭合的边界。仅一次 `lhqjgrow-20261006a`，按 A 的新维护预算及时限，不重试、不补采、不强制关机、不自动回滚、不清理，不执行 H01/Q4/H11；支线暂停，生产 E3 限制保持。
