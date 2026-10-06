# Journal 维护本地预检结果

2026-10-06，Asia/Shanghai。已同步并验证 `50ec8f2dcb4bbee97934b22cb5f24d372ce19613`，
但首次现场本地预检在 host boot 读取前返回 BLOCKED。没有创建 marker、发送 SSH、停机、
备份或增长镜像，也没有执行 H01/Q4/H11。真实 journal 容量未改变，维护尚未交付。

本记录续接[维护交接](Q2_CORE_JOURNAL_GROWTH_COMPLETION_20261006.md)，
原 R、A `59948ec4fedb807a31cdbff77acc134e84414160`、Owner B 和独立 C 保持。
`.codex` 是原有未跟踪本地文件，本轮未读取、修改或提交。

## 准确版本及验证

本地从 `8e91fa2631aa18a8469efa5a14e4145eaf781e28` 快进到上述 D，
没有覆盖工作区修改。准确 D 的 [CI 37412462742](https://github.com/kongbu0621/infra-local-hand/actions/runs/37412462742)
已完成：classify-change、Ubuntu semantic-core、Windows semantic-core 均 success。
这不是后续诊断修复的 CI。

执行交接列出的七个窄测试文件，结果 **311 passed in 2.19s，0 skipped**。
原生 pidfd 和独立临时 qcow2/ext4 的 256→512 MiB 验证均实际通过；
后者是合成离线文件系统，不是原 guest 在线增长成功。未重跑无关全量测试。

## 唯一现场预检

以真实宿主现有普通账号执行不带 `--execute` 的固定入口，准确绑定上述 D，
使用已经记录的固定 frame、原 plan archive 和六个历史 archive 目录。
没有试探 SSH、sudo 或镜像工具修改。入口返回退出码 3：

- `state=BLOCKED`，`reason=LOCAL_IO_OR_TRANSPORT`；
- `error_type=PermissionError`，`errno=1`；
- `marker_created=false`，`ssh_requests=0`；
- `window_binding` 仅有两项原始单调时钟起点，没有已取得的 host boot ID。

失败发生在 `main → bind_window → boot_id → read_kernel → os.open`。
该点位于 `freeze_growth_inputs`、VM 身份读取、writer 扫描及 marker 之前。
代码对固定 `/proc/sys/kernel/random/boot_id` 使用 `O_NOATIME`。
另外一次限定元数据核对确认：真实宿主执行 UID 为 1000、CapEff 为 0，目标文件 uid/gid 为 0、mode 为 0444。
没有读取 boot 内容、重跑预检、进入 root、修改权限或采用普通读取 fallback。

这是 host 复用了 guest 特权读取方式造成的真实权限冲突，不是工具 sandbox 的 PID 1 判断。
尚未读取完整现场输入，因此不能称清单已冻结或所有其它前置门已通过。

## 已修复的诊断缺口

本记录所在修复仅在既有 CLOSED J1 开发范围内补充有界诊断：
内核 open 失败报告 `GROWTH_KERNEL_OPEN`、固定 target、operation 和 errno。
保留原读取标志及一次 open，既不暴露异常原文也不重试。
新增回归确认 CLI 保留原时钟起点、缺失 boot 不被补造、后续输入和 marker 不被访问。

相同七文件范围再次实测 **313 passed in 2.19s，0 skipped**；`git diff --check` 通过。
两个实现文件为 64744 B、64892 B，仍各不超过 65536 B；原 A 三文件未修改。
诊断修复未重新执行现场入口，不构成权限故障已解决或 J3 通过。

## 剩余直接边界

已有 `LH-Q2-KERNEL-FACT-READ-v1` 的严格普通读取组件可以复用设计，
但其 K06 明确绑定旧 300s 窗口、K07 绑定旧 boot pin，不能无记录移植成新的 900s 维护授权。
本次 A 又保留 O_NOATIME 边界，因此需要准确的窄变更，而不是再次批准整个 journal 扩容方案。

静态核对还发现 `collect_image_writers` 需要穷尽宿主所有 PID/TID 的 stat、fd、fdinfo、maps。
普通账号不能据此承诺跨 UID 可读；**本轮尚未到达该扫描，不把它描述成第二项已实测失败**。
不能跳过不可读进程、以空结果替代 UNKNOWN，或把整个维护 coordinator 改用 root 执行。

首次预检的窗口已经开始但未取得完整 binding；即使没有 marker，也不能丢弃原起点再开窗口。
本轮停止于该失败。后续需明确处理固定 host 读取、只读 writer 权限及失败预检窗口的替代规则。
维护 marker/两条 SSH/关机/增长机会均未消费，但这不构成自动刷新时间或重试授权。

支线、生产 `E3_SUPERVISION_UNVERIFIED`、全部旧 UNKNOWN 和承诺保持。
