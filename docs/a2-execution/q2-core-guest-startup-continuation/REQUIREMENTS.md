# 收窄维护启动检查，接续原核心任务

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-GUEST-STARTUP-CONTINUATION-v1`，仅 GS1–GS3。
本[需求](REQUIREMENTS.md)、[架构](ARCHITECTURE.md)、[计划](IMPLEMENTATION_PLAN.md)
组成一个待决范围。沿用根AGENTS固定R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、
直接可读来源及完整性、Owner authority/mandate、无例外及R→A→B→独立C→D。

## 目标与具体问题

唯一交付仍是H01正常任务和结果、Q4运行取消、H11同任务恢复查询。先完成原journal
256→512 MiB维护，再接原未发出的 `lhqcore-20261007a`；不增加cron审计、脚本分析、
全机扫描或其它产品功能。复用原安装、SSH、VM及五镜像，不改变Local Hand任务语义。

输入基线 `d14be69e9947cd6672d2f7d103c0c9b56ccc0a7b` 的[08c返回](../Q2_CORE_EXEC_CONTINUATION_FIELD_20261008.md)
为 `PRE_QUIESCENCE / GROWTH_INDIRECT_STARTUP_UNVERIFIED`。准确执行D
`064bdd614db4224c8c7e9d3b011af90622c11066` 已通过首次CI3/3，但现场未关机/扩容/重启，
三个核心case仍NOT_RUN。现有实现有意拒绝启用单元中匹配到的通用调度器/解释器；
这不证明具体任务正在运行、写业务数据或发生冲突。现有persistent检查不验证cron队列。

## 唯一保证范围调整

删除维护中“未见直接业务引用的通用调度器/解释器一律阻断”的类别判定，覆盖普通
单元和模板两个入口；不是只给cron加白名单，也不逐个追踪shell/Python/脚本产生新支线。
没有直接命中不等于证明与业务无关。替代依据是Owner明确接受、执行者在既有交接中
确认的管理前提：**原隔离guest的旧业务不会通过cron、脚本或其它未声明入口自动启动，
从维护开始、停机前、按原配置重启后的post阶段，直到交接原核心批期间，不新增这种
入口，也不从其它会话手动启动旧业务或写入受保护业务目录。**
无法确认或已有相反证据时停止；不以新增现场扫描来证明这个前提。

这是间接启动覆盖缩减，不是安全等价修复。报告必须明确
`indirect_startup=NOT_PERFORMED`，不能保留CLASSIFIED或宣称穷尽验证。
之前K1可信单管理员批准仅覆盖host五镜像观察，不代替本次guest前提的批准。

继续保留：已声明业务unit静止及启动依赖、domain/cgroup、单元及模板中受保护根的
直接引用检查、现有当前进程/writer检查、必要持久证据、目标QEMU pidfd/start/executable/
完整argv、五镜像身份保护、正常关机及旧pidfd退出、qemu-img锁、完整独立备份与比较、
一次原配置启动、ext4/UUID/内容/容量核对。host访问前提和NOT_PERFORMED记录保持。
不改权限/凭据/allowlist/隔离，不停止或禁用cron，不修改guest配置来制造通过。

## 一个批次与资源

- GS1：一次完成检查删减、覆盖标记、六旧历史和维护/核心两侧消费者；离线验证、
  发布准确D、核对其CI和独立安装、静态私料及所有原限额，再冻结两个caller。
- GS2：唯一新维护 `lhqjgrow-20261008d`；普通预检和execute沿同原点/nonce/manifest/
  累计用量，新九名create-only，开始即消费。旧08c及此前窗口不能重放。
- GS3：仅GS2完整成功原件验证后，同一D发一次原 `lhqcore-20261007a` H01→Q4→H11。
  两侧实现先完成，维护成功前不生成真实核心包；核心对象已有即停，不改名替换。

六旧维护06a/07a/07b/08a/08b/08c及原件、消费、UNKNOWN全部保留。七代各1296 MiB/
370 inodes/120 CPU-s，每相关设备维护准入9072 MiB/2590 inodes，加核心64/16为
**9136 MiB/2606 inodes**；七代名义840 CPU-s，旧实际用量和未知义务不退款。
这是累计准入，不能按失败小文件减账或提高单次限额。

原维护900s双钟/780s修改截止、最多两次固定SSH/ConnectionAttempts=1、备份320 MiB、
目标576 MiB、capture8 MiB/32 inodes、每流1 MiB、CPU120s/RSS512 MiB、AS256 MiB/
FD128、8控制子进程、VM4 vCPU/8192 MiB、两源各98304 B、bundle49152/393216 B保持。
核心900/800/750s、四旧加新1380 MiB/82560 inodes/10450 CPU-s及更早义务、新核心
276 MiB/16512 inodes/2090 CPU-s、32 MiB包、1 MiB approved-input、60 MiB输出、
64 MiB capture和reserve保持。短预检4096 B、transition65536 B保持；journal至少
400 MiB/32768 inodes仍不代替五池准入。删掉的类别判断不换成其它工作额度。

## 验收、披露和停止

必须证明两侧明确绑定新的覆盖取舍、保留所有其它拒绝路径，随后由一次维护证明备份、
增长、内容、容量和新boot，再由原live finalizer判断三个核心case。CI不是现场成功。
失败STOP_AND_RETAIN，GS2不完整则GS3 NOT_RUN；不重试、补采、清理、恢复、回滚或
二次启动。本决定不产生后续窗口，不扩展支线，范围内不逐子步骤再次审批。

请求批准三文档及必要脱敏记录发布main，并允许本地执行者仅从已保留08c五件原件
生成/核对/公开basename、bytes、SHA-256最小索引，固定旧D为上述064bdd6。云端未见
该私有索引，本提案不填造pins或附件审查事件；实施须与原私有索引和保留副本一致，
冲突即停，不回现场补证。原文、路径、boot/PID、环境和流正文仍私有；新08d索引不自动公开。

Owner待决只有本管理前提与覆盖缩减、准确GS1–GS3及上述最小披露。未批准前不修改
运行/测试源码、配置或caller；旧批准和泛称继续不替代准确R/A/B及独立C。
