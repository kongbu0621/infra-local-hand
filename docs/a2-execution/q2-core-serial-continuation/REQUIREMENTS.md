# 序列号修复后的单次维护与核心接续

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-SERIAL-CONTINUATION-v1`，仅 SC1–SC3。
本文、[架构](ARCHITECTURE.md)、[实施计划](IMPLEMENTATION_PLAN.md)构成同一待决范围。
沿用根 AGENTS 的 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、直接来源及完整性、
Owner mandate/authority、无例外和 R→A→B→独立 C→D；截图交接不是本范围的准确批准。

## 目标及现状

只完成原 journal 256→512 MiB 维护，再执行已设计的正常任务 H01、运行取消 Q4、同任务
恢复查询及结果回收 H11。支线保持停止，不增加扫描器、权限、helper、连接探针或恢复框架。

输入源码基线 `ac292911f1dc7d99606899e5695c3245d467286d` 的
[准确 CI 37613224302](https://github.com/kongbu0621/infra-local-hand/actions/runs/37613224302)
三 job 均成功。它包含序列号完整原字节比较修复；Linux CI 的25分钟总期限不改变现场期限。
该绿灯不覆盖本方案尚未实现的新维护代次及消费者接线。

[上一窗口](../Q2_CORE_MINIMAL_CONTINUATION_FIELD_20261007.md)已创建 marker 并发送一次 SSH，
在 `PRE_IDENTITY / GROWTH_JOURNAL_SERIAL` 失败，guest actions_started 为空，未发出关机 token。
transport/remote exit 仍 UNKNOWN。旧 K2 永久消费，不能删除、改名、覆盖旧文件或换提交重放。
旧 K3 尚未执行，其条件未成立；本方案只接续同一个07a核心批，不增加第二个核心批。

## 本次请求的准确变化

1. 保留旧 `lhqjgrow-20261006a` 的所有事实和对象，完整核验公开现场记录已索引的五件原件。
   它们仅证明失败前缀，不证明进程已退出或费用已释放。
2. 授权一个固定新维护代次 **`lhqjgrow-20261007a`**。原管理 anchor 内的九个输出仍按
   原后缀算法命名，只把维护 session 替换为本固定值。对象存在即停止，不由调用者选择名字。
   本方案明确批准该代次，不能将这种替换推广为通用重试机制。
3. 同步维护来源/普通预检/marker/结果及 host、guest、最终返回消费者，绑定新旧维护关系。
   只有新代次的完整成功原件才可采用新 boot；旧失败 receipt 不能升级为成功输入。
4. 新维护完整通过后，条件接续原 **`lhqcore-20261007a`** 一次 H01→Q4→H11。
   核心 session、三个 case、project/UUID/安装对象、固定 runtime/wheel/projection 均沿
   [原最小接续需求](../q2-core-minimal-continuation/REQUIREMENTS.md)，没有另一个核心身份。

SC1 实现、验证、发布和冻结两段接线；SC2 一次维护；SC3 合格维护后一次原核心链。
可信单管理员、维护期间无其它任务操作五镜像的前提沿原批准，发现相反证据即停止。
保留目标 QEMU pidfd/start/executable/完整 argv、五镜像身份、旧业务静止、正常关机、
原 pidfd 退出、正常 qemu-img 锁、独立完整备份、结构/内容比较、一次原配置启动、
ext4/UUID/内容/容量验证。全宿主 writer observation 继续明确 NOT_PERFORMED。

## 次数、费用与期限

新维护只批准一个900s双钟窗口，预检和 execute 共用起点/nonce及累计计量，780s后不启动
新的状态改变。最多两条固定 SSH，各 ConnectionAttempts=1；无就绪探针、重连或第三条连接。
两代维护累计保留旧一次已发请求和新最多两次请求，不能把旧次数归零；其它历史诊断仍单列。
最多一个新marker、一次正常关机、一个完整备份、一次镜像增长、一次启动、一次ext4增长。
新窗口开始即消费，marker未创建也不退回次数。SC2失败则SC3为NOT_RUN。

新维护单次上限沿原合同：备份320 MiB，目标镜像576 MiB，capture 8 MiB/32 inodes，
单stdout/stderr各1 MiB，管理120 CPU-s/峰值RSS512 MiB、单进程AS256 MiB/FD128、
最多8个同时活跃控制子进程；原VM仍4 vCPU/8192 MiB。
两维护源98304 B、guest bundle49152/393216 B等传输界不变。不借新窗口抹去旧实际用量或UNKNOWN。

为避免以旧失败前缀推断费用释放，**旧维护1296 MiB/370 inodes的完整host容量条件全额保留，
新维护再按同额保守计入**。两代维护的host当前可用条件为 **2592 MiB/740 inodes**；
进入原核心时另加64 MiB/16，合 **2656 MiB/756 inodes**，每个相关设备保守完整计入。
两个1296 MiB中存在共同目标镜像和历史义务的重叠，本方案有意不抵销；这不是新增镜像、
两个备份、排他预留或真实整机峰值。现场不足则停止，不改门槛或清理以通过。
旧维护名义120 CPU-s与新维护120 CPU-s分别保留（两代名义合计240 CPU-s）；不宣称旧进程已退出，也不把两次RSS观察
解释为已证明的整机并发上界。更早费用和未知义务继续沿既有记录，不退款。

guest核心四旧加新仍1380 MiB/82560 inodes/10450 CPU-s，另加更早义务；新批仍
276 MiB/16512 inodes/2090 CPU-s。核心900/800/750s、原阶段reserve、32 MiB输入、
1 MiB approved-input、60 MiB输出、64 MiB/16 host capture、六文件/82成员均不变。
维护后的journal至少400 MiB可用、32768 inode不是核心准入替身，五池仍须全部通过。

## 成功、失败及待决项

成功必须先有完整维护原件验证两层增长、备份、内容及容量，再由原live finalizer证明
三个case的实际输出/退出/取消/同任务恢复成立；不把CI或本地测试称为现场成功。
失败保留首因、原件、已开始动作、实际消费和UNKNOWN，停止后续步骤；不重试、补采、
清理、回滚、二次启动或自动申请下一窗口。生产E3、E4–E6、NAS和支线均不在范围。

待Owner决定为本固定新代次、保守累计条件、对应接线及SC1–SC3完整批次。
旧最小接续的三文档和已消费授权保持历史原样；本范围批准不改变原R或补写旧执行成功。
