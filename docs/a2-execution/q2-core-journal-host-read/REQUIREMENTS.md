# Journal 维护宿主读取修订需求

状态 **PROPOSED / Gate OPEN / NOT APPROVED**。Scope `LH-Q2-CORE-JOURNAL-HOST-READ-v1`，仅 R1–R3。
这是原 `LH-Q2-CORE-JOURNAL-GROWTH-v1` 的窄修订，不是新的业务批次或通用管理功能。
原规则 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、Owner authority、无例外及
R→准确 A→Owner B→独立 bookkeeping-only C→D 顺序保持。
本文与[架构](ARCHITECTURE.md)、[计划](IMPLEMENTATION_PLAN.md)共同构成待批准 A。

## 已证实的问题及未证实的风险

原维护 A 为 `59948ec4fedb807a31cdbff77acc134e84414160`，C 为
`6493b1ae035dfa852952165046417c78f0f5383c`。执行候选 `50ec8f2dcb4bbee97934b22cb5f24d372ce19613`
CI 成功，311 项本地窄测试通过、无 SKIP；首次真实宿主本地预检仍在读取 boot ID 时返回 EPERM。
执行 UID 1000、有效 capabilities 为零，固定内核文件归 root 所有。
失败在输入/VM/writer 检查之前，marker、SSH、关机、备份、镜像增长及 H01/Q4/H11 均为零。
详见[本地预检记录](../Q2_CORE_JOURNAL_GROWTH_LOCAL_PREFLIGHT_20261006.md)。

诊断修复 D `9c63f25b43ef713f51930f8927e55456c9a0a9fb` 只补充错误定位，未改变读法或执行现场。
原有 writer 实现另外要求读取所有 host PID/TID 的 FD/maps；普通身份的完整可见性尚未证实。
不宣称已经实际扫描失败，也不在没有权限的情况下将不可读进程排除。

原窗口已开始但缺少完整 boot binding。未创建 marker 不代表可以刷新时间。
本修订必须同时明确读取权限和一次替代预检窗口；不把这两项伪装成已有 A 的普通实现修复。

## 唯一允许的改变

1. 仅 host boot ID 与自身 mountinfo 两个固定内核视图，复用已有
   `q2_host_kernel_facts.py` 的 held-fd、逐段 no-follow、procfs、statx mount identity 与对象资格检查。
   允许这两个视图的明确普通读取及内核动态元数据变化；不先失败再降级，不扩到任意 proc 文件。
   这是把旧 K01–K05 的读取方式明确采用到本维护；旧 K06/K07 的 300s/旧 boot pin 不自动迁移。
   原件、管理文件、镜像、历史证据和 guest 文件树的 O_NOATIME 规则保持。
2. 为原五个镜像对象的 writer 观察，允许通过**既有**非交互 sudo 管理入口运行固定、只读、短生命周期
   root observer。它只读必要 proc 元数据，不能修改文件、镜像、进程、服务或系统配置，不能发网络请求。
   coordinator、QEMU、qemu-img、capture、marker 和备份仍用原普通身份，绝不整体 sudo 运行。
   不安装依赖、添加 sudoers、能力、账号或常驻服务；没有既有权限就在 marker 前停止。
   这是新增 host 特权可信组件和管理审计副作用，必须由 Owner 明确接受，不是安全检查的绕过。
3. 仅替代上述失败的、未创建 marker 的本地预检窗口一次。仍使用固定维护 ID `lhqjgrow-20261006a`。
   修订后的准确 D、J2、相关 CI 及静态输入准备完成后，首次新本地预检起一个 900s 双时钟窗口；
   780s 后禁止新修改。保留旧失败和旧时钟事实；新窗口内预检与执行共享原 binding，不刷新。
   新预检也失败就停止，不再次申请同一入口自动重开或隐式恢复。

这是替代未进入执行的预检，不增加维护机会：跨原方案及本修订合计仍最多一个 marker、
两条维护 SSH、一次正常关机、一次 journal 镜像增长、一次 VM 启动和一次 ext4 增长。
不得运行旧 consumed 入口，不补采旧业务，不强制关机、不自动回滚、不清理。

## 不变的对象与预算

仍仅原 Q1 VM 的 journal qcow2，256→512 MiB，要求原内容/UUID/挂载关系保持，
最终 journal 普通可用至少 400 MiB/32768 inodes，其它原 parent 无新增拒绝。
新 pidfile 与 serial null、备份及非原子恢复、boot 变化、固定管理来源等边界均沿用原 A；
这里不改变原 A 的五份管理文件 pins 或原图像身份。

原 host 条件每设备 1296 MiB/370 inode、旧完整承诺 264 MiB/80 inode、备份 320 MiB、
目标镜像 576 MiB、capture 8 MiB/32 inode、维护余量 128 MiB 均不增加。
原两个实现文件各 65536 B 上限保持；允许额外复用一个既有、准确 pin 的内核读取模块，不新增第三实现模块。

root observer 每次输入和 stdout 各 ≤65536 B、stderr ≤4096 B，源码 payload ≤32768 B；
原五个镜像 dev/inode 为唯一观察选择器，不能由任意路径选择文件内容。
最多八次串行调用，对应原检查点：本地预检、同窗执行复核、关机前、关机后、备份前、增长前、启动前、启动后。
没有 sudo 探测、认证保温、重试或额外连接。首次调用失败就在 marker 前停止。
每次子窗口最多 15s 且截于原 900s 绝对期限，超时停止后续步骤，不声称已退出。
所有输入、输出和统计纳入原 8 MiB capture、120 CPU-s、512 MiB 观测预算；
单进程 AS 256 MiB/FD 128，同时控制子进程 ≤8，VM 仍 4 vCPU/8192 MiB。
调用次数上限不是额外 CPU 预算。只读管理程序也不强杀以制造成功；未知费用保持 UNKNOWN。

root observer 的源码、Python/sudo 身份、调用 argv 和输入算法必须在 J2 准确冻结。
sudo/PAM/audit 费用及祖先不属于完整用量证明；共享空间仍非排他。
接受 root 只读代码和现有 sudo/解释器的管理信任，不宣称获得内核级只读沙箱或原子全进程快照。
PID/FD 变化、不可读或可见性不完整一律拒绝，不能为提高成功率降低原 writer 判定。

## 授权停止边界

原扩容的离线完整备份、正常锁、旧逻辑区相同及新增区零、前报告落盘后才关机、
被动启动等待、两阶段 guest 静止/持久性/内容检查保持。
原所有 UNKNOWN、不退款、非排他容量和 mutator 可能逾期未闭合保持。
本修订不批准 H01/Q4/H11、未来新 boot 的核心采用、namespace/watchdog 或 production E3 启用。
它不保证下一轮必然通过；任一新 material 差异重新审阅，不能消耗维护机会做 feasibility spike。
