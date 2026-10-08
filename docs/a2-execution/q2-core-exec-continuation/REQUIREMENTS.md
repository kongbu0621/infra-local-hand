# 多命令属性修复后的单次核心接续

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-EXEC-CONTINUATION-v1`，仅 EX1–EX3。
本[需求](REQUIREMENTS.md)、[架构](ARCHITECTURE.md)、[计划](IMPLEMENTATION_PLAN.md)
共同定义待决范围；沿用R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、根AGENTS的
直接可读来源及完整性、Owner mandate/authority、无例外和R→A→B→独立C→D。

## 目标和现状

唯一交付仍是原journal 256→512 MiB维护，完整成功后执行原未发出的
`lhqcore-20261007a`：H01正常任务与结果、Q4运行取消、H11同任务恢复查询。
消费者仍为原维护入口、核心构包/入口及独立guest dispatcher，不增加产品功能。

输入修复 `e2d27ca51317ccd449772d82a2366b2f3092711e` 已发布，
[准确首次CI](https://github.com/kongbu0621/infra-local-hand/actions/runs/37717057010)3/3成功，
Linux6840 passed/89 skipped，独立安装94 checks/292 commands。
修复仅允许六个既有Exec数组属性多行，按顺序保留全部命令及重复次数，保留标量唯一性、
身份、别名、属性摘要与动作检查，并记录同次已有响应的具体格式失败条件。
这是可复现的代码缺陷；08b原输出没有具体响应行，不能补造其唯一根因。

[08b返回](../Q2_CORE_NAMES_CONTINUATION_FIELD_20261008.md)仍为
PRE_QUIESCENCE/GROWTH_SYSTEMCTL_FORMAT，动作空、无关机token、remote_exit UNKNOWN。
08b及旧06a/07a/07b/08a全部consumed/failed，不能重放旧caller或挪用条件核心权限。
NC已实现的短预检摘要表示保持，不提高4096 B上限或引入另一种历史表示。

## 单次范围和成功标准

- EX1：将第五代08b失败原件及准确授权绑定到维护和全部核心消费者；完成实现、离线
  验证、发布、准确新D首次CI、独立安装、输入核验和冻结，再准备唯一维护与条件核心caller。
- EX2：一次固定 `lhqjgrow-20261008c` 维护，普通预检与execute保持同原点、nonce、
  manifest和累计用量。独立九名create-only；开始即消费，即使marker未建也不退款。
- EX3：仅完整EX2成功原件通过后，由同一冻结D执行一次原 `lhqcore-20261007a`。
  两侧完整实现必须先完成，维护成功前不得生成真实核心包。

验收先证明五代历史及短交接绑定、所有原件与拒绝路径在原限额内，再由一次维护验证
备份、增长、内容、容量和新boot，最后由原live finalizer判定H01→Q4→H11。
源码、CI、模拟成功和已发布状态均不等于现场成功；EX2不完整则EX3 NOT_RUN。

## 保护和预算

完整继承[已批准NC需求](../q2-core-names-continuation/REQUIREMENTS.md)的可信单管理员
维护前提、五镜像无其它任务操作、pidfd/start/executable/完整argv、镜像身份、静止、
正常关机和旧pidfd退出、qemu-img锁、独立备份及比较、一次原配置启动、ext4/UUID/内容/
容量检查。全宿主writer observation仍NOT_PERFORMED；前提冲突即停，不增加探测。

五旧加一新维护，各1296 MiB/370 inodes/120 CPU-s完整义务：每相关设备维护门槛
**7776 MiB/2220 inodes**，加原核心64 MiB/16为 **7840 MiB/2236 inodes**。
六代名义CPU义务720 CPU-s；实际用量和UNKNOWN不释放，不按小失败文件减账或抵销共享
对象。这是批准新一次窗口所需的累计准入变化，不提高任何单次额度。

维护900s双钟/780s修改截止、最多两次固定SSH/ConnectionAttempts=1、备份320 MiB、
目标576 MiB、capture8 MiB/32 inodes、每流1 MiB、120 CPU-s/峰值RSS512 MiB、
AS256 MiB/FD128、8个活跃控制子进程、原VM4 vCPU/8192 MiB、两源各98304 B、
bundle49152/393216 B保持。核心900/800/750s、四旧加新1380 MiB/82560 inodes/
10450 CPU-s及更早义务、新核心276 MiB/16512 inodes/2090 CPU-s、32 MiB包、1 MiB
approved-input、60 MiB输出、64 MiB capture和原reserve保持；journal400 MiB/32768
inodes可用仍不能代替五池准入。transition65536 B及原流/记录限额保持。

## 披露和停止

请求将本三文档及必要脱敏登记、验证、结果和AGENTS声明发布至
`kongbu0621/infra-local-hand` 的main，并仅公开旧08b五件basename/bytes/SHA-256最小
索引。旧D为 `dc538b9034f00c635344defae57b7054319c2184`，私有附件事件
`NC2-08B-ORIGINALS-INDEX-REVIEW-20261008-01` 已核对保留副本及原私有索引。
具体pins未经批准不公开；原文、绝对路径、boot/PID、环境、诊断与流正文保持私有。
新08c原件及其索引不因本决定自动获准披露。

任一失败、超时、超界或冲突即STOP_AND_RETAIN；没有重试、补采、清理、恢复、回滚、
二次启动或扩展支线，不自动申请下一窗口。Owner待决本准确单次接续、累计义务与上述
最小披露；既有NC批准不替代本范围的准确B及独立C。
