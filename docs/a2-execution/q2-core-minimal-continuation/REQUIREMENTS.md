# 最小核心接续：删除维护附加扫描，完成任务闭环

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-MINIMAL-CONTINUATION-v1`，仅 K1–K3。
本文、[架构](ARCHITECTURE.md)、[实施计划](IMPLEMENTATION_PLAN.md)组成同一待决方案。
沿用根 AGENTS 的 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、可读取直接来源、
完整性、Owner mandate/authority、无例外和 R→A→B→独立 C→D 顺序。

## 只交付什么

响应 Owner 2026-10-07 的“直接推进核心功能，暂停搞分支功能。不要做我不需要的功能”。
目标只有：任务受理、正常执行并收回结果（H01）；运行中取消（Q4）；查询和收回同一任务
的恢复结果（H11）。H11 不重放任务，不借另一 case 的 ledger/unit。
本轮同时处理已知必要前置和其后的核心接线，不再交付只多一次扫描的方案。

代码/现场基线为 `b531d448741eda69463ed6c31b81976672caab58`。
[最新维护返回](../Q2_CORE_JOURNAL_DRIFT_RESUME_FIELD_20261007.md)为
`GROWTH_PROC_DRIFT_PID_TASK_SET`：任务集合前后不同，具体 PID/原因仍未知。
这是维护工具的全宿主检查；marker false、SSH 0，容量维护和三个核心 case 均未开始。
此前容量观察已定位 journal 不足；维护后还需要接通新 boot，不能直接运行旧核心包。

## 明确删除的前置及取舍

从当前 journal 维护路径移除全宿主 PID/TID/FD/maps writer 扫描、全宿主集合稳定要求、
八次 root observer 调用及专属认证/报告/进度依赖。旧实现和失败证据保留在 Git 历史；
不开发扫描重试、重采样、缓存、扩大扫描预算、替代扫描器或整机持续排他机制。
未执行的全宿主观察明确记录为 `NOT_PERFORMED`，不能输出“无额外 writer”的通过报告。

**拟接受的访问前提：原隔离 VM 由可信单管理员管理，维护期间没有其它任务直接操作
这五个镜像。** 本方案不再检测不遵守 QEMU 锁的其它可写 FD/mmap；正常工具锁只在
相应调用期间起作用，不宣称全程排他或安全能力完全相同。已有证据出现并发镜像操作、
无法确认该管理前提，或必要目标检查失败，就不执行维护；不再扫描整机来证明这个前提。
前提由执行者在既有管理交接中确认，发现相反证据即停止；不另造机器证明器或逐项审批。
这是需要 Owner 明确接受的保证范围变化；此前“不要放宽安全校验”不被解释为已批准此变化。

保留目标 QEMU pidfd/starttime/executable/完整 argv、五镜像 held FD/路径身份及保护、
guest 旧业务静止及必要证据保留、正常关机与原 pidfd 退出、正常 qemu-img 锁和结构检查、
完整独立备份、增长前后内容比较、一次原 VM 启动、ext4/UUID/内容/容量核对。
不改 Local Hand 的权限、凭据、allowlist、隔离、任务取消、结果验证或停止条件。

## 一个范围内完成三个步骤

- **K1 实现和验证：**一次接齐维护删减、新 boot 接续、第四旧批保留和第五固定核心批。
  可用合成输入完成接续验证；真实维护原件未产生前，不发行可现场执行的核心包。
- **K2 一次维护：**沿原 `lhqjgrow-20261006a`、原八输入/五镜像/SSH/安装，允许一个新的
  维护窗口，条件完成尚未执行的原 256→512 MiB 扩容。旧窗口全部保持消费。
  不重复安装、停宿主应用、清现场、补采或自动重试。
- **K3 一次核心链：**只有 K2 合格原件和 K1 最终发行检查通过，才允许一个新固定核心
  批次 H01→Q4→H11；前项未完整通过，后项 NOT_RUN。K2 与 K3 各用原独立期限，互不续期。

新核心身份固定为 `lhqcore-20261007a`，carrier `lhqcore20261007a-carrier.service`，
install/staging 为 `local-hand-core-acceptance-20261007a` /
`.local-hand-core-acceptance-20261007a.staging`。包、marker 和另五输出沿原命名算法仅替换
日期后缀；case controller prefix 为 `lhqcore20261007a-c01` 至 `c03`；preparation ID 为
`lhqc07a01h01normal`、`lhqc07a02q4cancel`、`lhqc07a03h11recovery`，projects 分别
12501..12507、12508..12514、12515..12521。UUID 为 ASCII
`urn:local-hand:LH-Q2-CORE-MINIMAL-CONTINUATION-v1:<原完整 case name 或 installation>`
的 SHA-256 前16 B，再设 UUIDv4/variant 位；沿原确定性算法，编码时固定派生结果。
对象已存在即停止，不改名绕行。

核心 runtime、288375 B wheel、89 文件 projection、三 case 原语义均沿
[原核心批准需求](../q2-core-post-locale-acceptance/REQUIREMENTS.md)的准确固定身份。
只在新隔离批次创建其原合同要求的安装；不重装或覆盖现有安装，不切换生产服务。

## 预算、历史与成功条件

维护原 A `59948ec4fedb807a31cdbff77acc134e84414160` 的对象、备份、镜像/文件系统增长、
CPU/AS/FD/存储限额、900s 双钟、780s 修改截止、正常停机和最多两条 SSH 保持。
普通预检与 execute 共用原窗口/nonce，跨进程 CPU/RSS 累计不因删 observer 被重置。
原每 observer 15s、八报告及其专属 wire/认证约束随被删除能力停止适用；其预算不转给其它动作。
两维护源码 98304 B、guest bundle 49152/393216 B 等未被删除的传输上限保持。

四旧核心 03a/05a/05b/05c、两旧诊断和全部维护历史保留，退出/用量 UNKNOWN 不重写、不退款。
新增核心仍为 276 MiB/16512 inodes/2090 CPU-s；四旧加新合 1380 MiB/82560 inodes/
10450 CPU-s，另加更早义务。维护已占空间和未闭合义务不能被核心新窗口漏掉。
host 当前容量条件保留原维护 1296 MiB/370 inodes，再加新核心 64 MiB/16，
合 **1360 MiB/386 inodes**，按设备保守分组；这是可用量条件，不是排他预留或整机峰值保证。
core approved-input 1 MiB、总输入 32 MiB、输出 60 MiB、host capture 64 MiB/16、
六文件/82输出成员及 900/800/750s 和原阶段 reserve 保持，不能自动增额。
四旧各两次当前状态检查共八 SHOW，每次仍 5s/2 CPU-s/32768 B，总40s/16 CPU-s/262144 B，
全部计入新批原预算；不是新增 unit、额度或无限轮询。

只有完整维护原件证明备份、两层增长、内容保留及至少 400 MiB/32768 inode 后，才采用新 boot。
只有原 live finalizer 证明三个 case 的语义、退出、结果和证据全部成立，才称核心链通过。
失败保留首因和已取得结果，不补采、不重连、不清理、不自动回滚或发下一批。
生产 E3、namespace/watchdog、E4–E6、NAS、监控/诊断平台均不在交付范围。

待 Owner 决定只有本方案的范围变更与 K1–K3：接受上述可信单管理员前提和缩小的观察覆盖，
批准删除扫描并条件执行一次维护和一次核心批。不要求再次批准各个已列明的实现子步骤。
