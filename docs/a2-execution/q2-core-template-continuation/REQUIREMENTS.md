# 模板与别名修复后的一次维护及原核心接续

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-TEMPLATE-CONTINUATION-v1`，仅 TC1–TC3。
本[需求](REQUIREMENTS.md)、[架构](ARCHITECTURE.md)、[实施计划](IMPLEMENTATION_PLAN.md)
共同定义待决范围。沿用原 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、根 AGENTS
的直接来源和完整性、Owner mandate/authority、无例外、变更规则及 R→A→B→独立 C→D。

## 目标与输入

唯一目标仍为原 journal 256→512 MiB 维护，完整验证后执行同一个未发出的
`lhqcore-20261007a`：正常任务及结果 H01、运行取消 Q4、同任务恢复查询 H11。
不新增功能、宿主扫描器、权限/helper、探针或通用恢复机制。

输入修复 `94f289e8da83d3d79e2dc1fc09069a1c19eed871` 已发布；其
[首次准确 CI](https://github.com/kongbu0621/infra-local-hand/actions/runs/37650335186)
3/3成功，Linux 6419 passed / 89 skipped，独立安装94 checks / 292 commands。
修复区分模板配置与运行单元，验证普通别名 Id/Names，声明目标仍须正式Id精确匹配。
模板保留fragment/drop-in和受保护路径检查；其保守Exec文本检查可能拒绝被覆盖的间接命令，
不是完整systemd合并解析器。不得为通过现场而跳过这些检查或把CI成功当作现场就绪。

[06a](../Q2_CORE_MINIMAL_CONTINUATION_FIELD_20261007.md)、
[07a](../Q2_CORE_SERIAL_CONTINUATION_FIELD_20261007.md)、
[07b](../Q2_CORE_SYSTEMCTL_CONTINUATION_FIELD_20261007.md)三维护代次均已消费且失败，
各一次SSH，动作空、无关机token、remote_exit UNKNOWN。07b停在PRE_QUIESCENCE，
同次诊断已证明show拒绝未实例化模板。旧原件、期限、消费和完整费用全部保留。
原核心批仍NOT_RUN，不能作为绕过失败维护的独立执行权限。

## 批次及边界

- TC1：三代历史和修复接入固定新维护，维护与完整核心消费者一并实现、验证、发布、
  准确候选CI和冻结。必须先有本A的准确Owner B与独立C；现有修复不替代新D验证。
- TC2：仅一次固定 `lhqjgrow-20261008a`，普通预检与execute同原点、nonce、manifest、
  累计用量；九名create-only。开始即消费，预检失败或未创建marker也不退回次数。
- TC3：仅TC2完整成功原件通过后，由同一冻结D发送一次原 `lhqcore-20261007a`。
  核心session/case/project/UUID、runtime/wheel/projection/loader及任务语义保持。

继承[上一需求的目标保护和所有单次限额](../q2-core-systemctl-continuation/REQUIREMENTS.md)：
可信单管理员、五镜像无其它任务操作；目标pidfd/start/executable/完整argv、五镜像身份、
guest静止、正常关机和旧pidfd退出、qemu-img锁、完整独立备份/比较、一次原配置启动、
ext4/UUID/内容/容量验证均保留。全宿主writer observation仍明确NOT_PERFORMED。
出现前提冲突即停，不增加宿主探测以证明它。两段实现必须在维护前同时完成。

## 历史与有限披露

三代各五件consumed/events/pre两流/receipt及各四个后续缺席名必须保护核验。
06a、07a沿已批准公开pins；07b严格为D `b2bc054d0c06526b454cd320f167cc1a40242ab8`。
07b五件保留副本已与原SY2私有索引、预检/执行输出及流摘要一致核对。

本提案同时请求**仅公开旧07b五件basename/bytes/SHA-256最小索引**，用于公开实现和CI
固定历史身份。Owner私有附件事件 `SY2-07B-ORIGINALS-INDEX-REVIEW-20261008-01`。
当前未公开固定值；未经明确批准不得发布。原文、绝对路径、boot/PID、环境、流正文、
诊断及其它机器元数据不在披露范围。不得重新采样或用新数据替换旧pins。

## 累计条件与验收

三代旧维护各1296 MiB/370 inodes完整义务加一次新维护：每相关设备保守门槛
**5184 MiB/1480 inodes**；加原核心64 MiB/16为 **5248 MiB/1496 inodes**。
不抵销共享对象，不按旧实际小文件减账，不代表新增四个备份或物理预留。
四代各120 CPU-s分别保留，名义合计480；旧实际用量和UNKNOWN不释放。

单次维护900s双钟/780s修改截止、最多两次固定SSH/ConnectionAttempts=1、备份320 MiB、
目标镜像576 MiB、capture8 MiB/32 inodes、每流1 MiB、120 CPU-s/峰值RSS512 MiB、
进程AS256 MiB/FD128、8个活跃控制子进程、原VM4 vCPU/8192 MiB、两维护源各98304 B、
guest bundle49152/393216 B均不增加。核心900/800/750s、guest四旧加新1380 MiB/
82560 inodes/10450 CPU-s及更早义务、新核心276 MiB/16512 inodes/2090 CPU-s、
32 MiB包/1 MiB approved-input/60 MiB输出/64 MiB host capture和原reserve全部保持。
journal可用400 MiB/32768 inodes仍不能代替核心五池完整准入。

完整维护原件证明增长、备份、内容和容量后，仍须原live finalizer确认三case实际结果。
任一失败/超时/拒绝即STOP_AND_RETAIN；TC2失败则TC3 NOT_RUN。无重试、补采、清理、
恢复、回滚、二次启动或支线，不自动申请下一窗口；实质变更按原R处理。
