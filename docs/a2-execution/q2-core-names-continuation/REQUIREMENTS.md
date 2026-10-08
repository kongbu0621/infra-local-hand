# Names 修复后的有界交接与原核心接续

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-NAMES-CONTINUATION-v1`，仅 NC1–NC3。
本[需求](REQUIREMENTS.md)、[架构](ARCHITECTURE.md)、[计划](IMPLEMENTATION_PLAN.md)
共同构成待决范围。沿用 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、根 AGENTS
的直接来源及完整性、Owner mandate/authority、无例外和 R→A→B→独立 C→D。

## 目标、事实与变更

唯一交付仍是原 journal 256→512 MiB 维护，完整验证后执行未发出的
`lhqcore-20261007a`：正常任务及结果 H01、运行取消 Q4、同任务恢复查询 H11。
消费者仍为原维护入口、核心构包/入口及独立 guest dispatcher，不增加产品功能或组件。

Names 修复输入为 `13ba2757aef0f3e48d334c371c367db7dc61a7ec`，已发布，
[首次准确 CI](https://github.com/kongbu0621/infra-local-hand/actions/runs/37710638042)
3/3成功。它只解码 systemctl 数组的显示格式，保留身份检查及同次有界失败信息。
旧08a没有具体被拒绝的 Names，修复不能证明历史失败只有这一原因。
随后 `82597b78824fe33cd0a1352954b36bb9a6f8041d` 登记交接长度冲突；没有实现新格式。

现短预检重复携带完整历史。用保留08a五件的实际长度/摘要追加第四条历史，旧格式
大时钟/最大计量样本4974 B，最小正计量样本4917 B，现解析器均受4096 B上限约束。
这是既有数据的离线长度反例，不是新有效预检或现场结果。必须在下次执行前解决。

本提案只把短预检中的重复 `resume` 改为准确完整历史的固定SHA-256引用；完整历史
仍在 manifest、marker、receipt、source binding 和核心投影中保留并逐件严格验证。
4096 B上限不提高，不压缩或裁剪原件，不因摘要相等跳过任何历史/身份/期限/用量检查。

## 一次批次

- NC1：四代原件绑定、短预检表示及两侧消费者一起实现、离线验证、发布、准确D CI、
  独立安装和冻结。先形成准确A、Owner B及独立C，当前不得写新实现或可执行交接。
- NC2：唯一固定 `lhqjgrow-20261008b` 维护。普通预检与execute沿同一原点、nonce、
  manifest及累计用量交接；原九名create-only，开始即消费，marker未建也不退款。
- NC3：仅NC2完整成功原件通过后，由同一冻结D发送一次原 `lhqcore-20261007a`。
  两段实现必须先完成，完整维护原件出现前不得生成真实核心包。

06a/07a/07b/08a均保留consumed/failed、原件、完整费用和remote_exit UNKNOWN。
[08a返回](../Q2_CORE_TEMPLATE_CONTINUATION_FIELD_20261008.md)仍为PRE_QUIESCENCE /
GROWTH_SYSTEMCTL_NAMES，动作空、无关机token。旧caller和条件核心权限不得重放或挪用。

## 保留保护、限额与披露

继承[已批准TC需求](../q2-core-template-continuation/REQUIREMENTS.md)的可信单管理员、
五镜像无其它任务操作、目标pidfd/start/executable/完整argv、镜像身份、guest静止、
正常关机及旧pidfd退出、qemu-img锁、独立备份/比较、一次原配置启动、ext4/UUID/内容/
容量检查。全宿主writer observation仍NOT_PERFORMED；前提冲突即停，不增加探测证明。

四旧加一新维护，各保留1296 MiB/370 inodes/120 CPU-s完整义务：每相关设备维护门槛
**6480 MiB/1850 inodes**，加原核心64 MiB/16为 **6544 MiB/1866 inodes**。
五代名义CPU义务600 CPU-s；原实际用量与UNKNOWN不释放，不抵销共享对象、不按旧
小文件减账。这是新增一次明确许可的累积准入，不提高任何单次额度。

维护900s双钟/780s修改截止、最多两次固定SSH/ConnectionAttempts=1、备份320 MiB、
目标576 MiB、capture8 MiB/32 inodes、每流1 MiB、120 CPU-s/峰值RSS512 MiB、
AS256 MiB/FD128、8个活跃控制子进程、原VM4 vCPU/8192 MiB、两源各98304 B、
bundle49152/393216 B均保持。核心900/800/750s、四旧加新1380 MiB/82560 inodes/
10450 CPU-s及更早义务、新核心276 MiB/16512 inodes/2090 CPU-s、32 MiB包、1 MiB
approved-input、60 MiB输出、64 MiB capture和原reserve保持；journal400 MiB/32768
inodes可用仍不能代替五池准入。transition65536 B和所有原流/记录限额保持。

本提案请求将本三文档及必要脱敏登记/验证/结果记录发布到
`kongbu0621/infra-local-hand` 的 `main`，并**仅公开旧08a五件basename/bytes/SHA-256
最小索引**，准确旧D `d5b34316bc93b37442eb5db64ba265b965e68379`。
私有附件事件 `TC2-08A-ORIGINALS-INDEX-REVIEW-20261008-01` 已对照原私有索引、
保留副本及已有调用输出核对。未经明确批准不公开这些值。原文、绝对路径、boot/PID、
环境、诊断和流正文不在披露范围。不得回现场补证。

## 完成与停止

验收须先证明准确候选的完整历史、摘要绑定和双方拒绝路径在原大小/资源边界内，
再由一次现场维护证明增长、备份、内容和容量，最终由原live finalizer判定三个case。
代码/CI/摘要长度估算不能代替现场成功。任一失败/超时/冲突即STOP_AND_RETAIN，
NC2不完整则NC3 NOT_RUN。没有重试、补采、清理、恢复、回滚、二次启动或扩展支线；
不自动申请下一窗口。Owner仅待决本准确格式变更、单次接续及上述最小披露。
