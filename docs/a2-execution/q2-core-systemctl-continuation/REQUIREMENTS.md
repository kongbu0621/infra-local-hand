# Systemctl 修复后的一次维护与原核心接续

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-SYSTEMCTL-CONTINUATION-v1`，仅 SY1–SY3。
本文、[架构](ARCHITECTURE.md)、[实施计划](IMPLEMENTATION_PLAN.md)是同一待决范围。
沿用根 AGENTS 的准确 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、直接来源及完整性、
Owner mandate/authority、无例外、变更规则和 R→A→B→独立 C→D。

## 目标和现状

只完成原 journal 256→512 MiB 维护，然后执行原正常任务 H01、运行取消 Q4、同任务
恢复查询和结果回收 H11。停止支线；不增加扫描器、helper、权限、探针或通用恢复框架。

输入源码基线 `c1fa156e68cf4b9e1909881f859736a933310794` 已发布，其
[准确首次 CI 37635861016](https://github.com/kongbu0621/infra-local-hand/actions/runs/37635861016)
三 job 成功，包含两平台源码和独立安装步骤。本机原有18项 systemctl 定向测试通过。
修复为 show 的单元操作数加 `--`，避免 `-.slice` 被当成选项；只在同次失败输出中保存
有界信息，原返回码、双EOF、空stderr要求保持。已隔离复现参数缺陷，但旧现场没有
保留具体systemctl结果，不能把确定源码缺陷说成已复原全部现场原因。

原 06a 维护在 PRE_IDENTITY/serial 失败；后续
[07a/SC2](../Q2_CORE_SERIAL_CONTINUATION_FIELD_20261007.md)通过serial后，在
PRE_QUIESCENCE/GROWTH_SYSTEMCTL_STDERR 失败。两次都已创建marker、各发一次SSH，
报告动作为空、未发关机token，remote exit仍UNKNOWN。两窗口永久消费，不重放、退回
次数或释放旧费用。原 `lhqcore-20261007a` 及 H01/Q4/H11 仍未发出。

## 请求的准确范围

- SY1：保留两次失败和现有修复，把维护和完整核心消费者同时接至一个固定新维护代次，
  实现、验证、发布、准确CI和冻结。新source必须承接本A的独立C；旧修复绿灯不代替新D。
- SY2：仅一次固定 `lhqjgrow-20261007b` 维护。普通预检与execute同窗、同nonce和累计用量；
  新九名create-only，任一存在即停。窗口开始即消费，未创建marker也不退款。
- SY3：仅在新维护完整成功原件验证后，执行同一个尚未发出的 `lhqcore-20261007a`
  H01→Q4→H11批次。核心身份、case/project/UUID、runtime/wheel/projection均沿原最小接续，
  不另造核心session或第二个核心批。

可信单管理员、维护期间无其它任务操作五镜像的前提保持，出现相反证据即停止。
保留原目标QEMU的pidfd/start/executable/完整argv、五镜像身份、guest静止、正常关机、
旧pidfd退出、正常qemu-img锁、完整独立备份、镜像/内容比较、一次原配置启动、
ext4/UUID/内容/容量核验。全宿主writer observation继续明确NOT_PERFORMED。
新维护和消费者在SY2前必须都完成，不能维护后才补核心接线。

## 历史原件和有限索引披露

保护核验06a和07a各五原件：consumed.json、events.jsonl、pre.stdout、pre.stderr、receipt.json；
两代各四个未到达后续名称保持缺席。没有旧原件或关系不符不得假装首次维护。
06a沿已公开固定pins；07a五件的精确长度/摘要已在原SC2私有索引和保留副本中一致。

本提案的闭合申请**同时请求仅公开07a这五件的固定basename/bytes/SHA-256索引**，
用于公开实现与准确CI固化历史身份。Owner可在本机核对附件事件
`SC2-07A-ORIGINALS-INDEX-REVIEW-20261007-01`，其五件逐项来自原SC2私有索引，
旧D严格为 `a20bf2a4575df7578341af744630ceaac131a6a7`。当前未公开这些固定值。
批准后才发布该最小索引；批准不包括原文、绝对路径、boot/PID、环境、流正文或其它
机器元数据。不得借批准采用后补原件或重新采样。正文和失败诊断持续私有。

## 次数、费用和期限

新增维护只允许一个900s双钟窗口，780s后不开始状态改变；最多两条固定SSH，
ConnectionAttempts=1，无就绪探针、重连或第三条连接。最多一次新marker、关机、
完整备份、镜像增长、启动和ext4增长。旧两次SSH及更早历史保留，新上限不覆盖旧消耗。

单次上限不变：备份320 MiB、目标镜像576 MiB、capture8 MiB/32 inodes、每流1 MiB、
管理120 CPU-s/峰值RSS512 MiB、单进程AS256 MiB/FD128、8个同时活跃控制子进程；
原VM4 vCPU/8192 MiB。两维护源各98304 B、guest bundle49152/393216 B保持。

两代旧维护各1296 MiB/370 inodes的完整host条件不释放，新维护再计同额：
维护每相关设备当前可用门槛 **3888 MiB/1110 inodes**；加原核心64 MiB/16后为
**3952 MiB/1126 inodes**。有意不抵销共享镜像等重叠；不是新增三个备份或物理预留。
旧120+120和新120 CPU-s分别保留，名义合计360；旧实际用量及UNKNOWN不抹去，
不宣称整机并发RSS或未知旧进程已收束。现场不足停止，不清理或提高单次预算以通过。

核心仍900/800/750s，guest四旧加新1380 MiB/82560 inodes/10450 CPU-s，另加更早义务；
新核心仍276 MiB/16512 inodes/2090 CPU-s。32 MiB包、1 MiB approved-input、60 MiB输出、
64 MiB/16 host capture、六文件/82成员和原阶段reserve均保持。
journal至少400 MiB可用/32768 inodes不代替核心五池完整准入。

## 验收及停止

成功须由完整维护原件证明增长、备份、内容与容量，再由原live finalizer给出三个case
的实际verdict。CI和合成结果不等于现场成功。任一拒绝、超界、错误或超时停止，保留
实际已开始步骤、原件、费用和UNKNOWN；SY2失败则SY3 NOT_RUN。
不重试、补采、清理、恢复、回滚、二次启动或扩展支线；不自动申请另一个窗口。
本次待Owner决定仅为上述固定代次、最小索引披露、保守累计条件及SY1–SY3完整批次。
