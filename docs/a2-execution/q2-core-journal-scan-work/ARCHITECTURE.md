# 按实际操作计费并保留扫描进度

Authority：Owner；**PROPOSED / Gate OPEN**。范围仅来自[需求](REQUIREMENTS.md)。
复用原 coordinator、固定生成的 root writer、终端认证和两阶段 guest 维护协议。
没有实现本修订，没有现场探测或执行。

## 同一次扫描的工作预算

维护扫描仍逐 PID、逐 task 走原顺序。每次 scanner 调用建立私有计数对象，绝不跨调用
缓存结果或重置已发生用量。仅替代原 FD_TOTAL 准入：

- 初始 `_fd_snapshot` 的 `entry.stat(follow_symlinks=True)`；
- 复核 `_fd_snapshot` 的同类调用；
- 匹配五镜像后对原 FD 路径的 `os.stat` 身份复核。

三处在真正调用之前，先以三个 attempt 计数之和加一计算候选值。候选值大于 2097152
则用固定 `GROWTH_PROC_LIMIT_FD_STAT_CALLS` 原有 N/MAX/PID/TID 格式拒绝，不调用 stat、
不增加 attempt 计数；否则先计费再调用，调用抛错也不退款。第 2097153 个候选拒绝时，
记录的真实 attempt 合计仍是 2097152。每 snapshot 第 65537 项先由原条目限制拒绝，
不收费也不调用 stat。fdinfo 和其它 proc 读取不伪装成 FD stat，仍服从原文件/时间界。

保留元数据、flags、匹配对象和全部复核谓词。旧 FD_TOTAL 不再作为新候选的早期门，
也不换个名字继续统计同一份逻辑 FD 数。新的计数不会证明全局排他性或未来没有写入；
原管理信任与正常镜像锁继续保留。

## 固定 progress 合同

成功结果 exact keys 为 `schema,request,complete,rows,usage,progress`；失败为
`schema,request,complete,reason,errno,progress`。schema 必须为
`lhq-journal-writer-result/v2`；旧 v1 仅作历史证据，不能作当前成功或 retained preflight。
原 request、D/nonce/images/boot/checkpoint/双钟绑定、rows、reason、errno、usage 的
严格规则全部保留。无合法 request 的早期失败只允许 request/progress 均为 null。
合法 request 的报告必须有 progress；缺失、额外字段、畸形、截断或版本混用均拒绝。

progress 使用以下 exact keys，canonical 编码最多 4096 B；无自由文本、路径、内容、
进程列表或逐 FD 明细。所有整数拒绝 bool/float、负数及超界值。

| 字段 | 语义和界 |
| --- | --- |
| phase | 下述固定阶段枚举 |
| scan_complete | bool；只在最终 PID 集合复核和 WRITER_ENTRY 内部最终期限检查通过后为 true |
| pids_listed | 初始 PID 枚举未完成为 null，否则整数 0..32768 |
| pids_completed | 已完成原 PID 全部复核，0..32768，已知时不大于 pids_listed |
| tasks_started / tasks_completed | 通过原 TASK_TOTAL 门后开始/完成的 task，0..65536，completed≤started |
| fd_initial_stat_attempts | 初始 FD snapshot 已发起 stat 数 |
| fd_recheck_stat_attempts | 复核 FD snapshot 已发起 stat 数 |
| fd_match_stat_attempts | 匹配 FD 的额外身份 stat 数 |
| maps_files_read | 已完整读回的 maps 文件数，0..tasks_started |
| maps_bytes_read | 上述完整文件累计字节，0..513 MiB |
| maps_max_file_bytes | 上述完整文件最大值，0..1 MiB |
| last_valid_elapsed_ns | null 或既有成功 check 样本减 request.started 得到的两个整数，各 0..14999999999 |

三个 FD attempt 均为整数 0..2097152，合计不得超过2097152；不添加冗余总计字段。
失败时不得强求 recheck 数≤initial 数：复核可能先遇到新增 FD，再由原 drift 条件拒绝。
maps 计数在完整读取后、原总额检查前更新，故包含首次总额越界文件；单文件读取失败
仅保留此前完整文件数值，具体单文件 N/MAX 仍由原 reason 表达。零文件时 bytes/max 均零，
否则 max≤bytes≤files×max（全为空文件时允许 bytes=max=0）。这里的 bytes 不是包含
未完成读取的全部内核 I/O。pids_listed=null时，PID完成、task、FD及maps的全部数值计数
必须为0：初始PID枚举尚未完成，后续循环不能已经开始。
时钟字段只保存已有成功检查样本，失败处理不另读时钟，不能把它当作失败精确时刻。

阶段枚举固定为 `PRE_SCAN,PROC_MOUNT,PID_LIST,PID_STAT,TASK_LIST,TASK_STAT,FD_INITIAL,
FD_MATCH,FD_RECHECK,MAPS_READ,MAPS_PARSE,TASK_RECHECK,PID_RECHECK,FINAL_PID_RECHECK,REPORT`。
scan_complete=true 仅允许 REPORT 阶段，且对成功和失败均要求 pids_listed 与
last_valid_elapsed_ns 非null、pids_completed=pids_listed、
tasks_started=tasks_completed=maps_files_read、maps_bytes_read≤512 MiB。
若后续 usage/输出准备失败，失败报告可以保留这个已完成扫描事实，但 result.complete
仍 false，绝不可用于准入。该标志不表示父层尚未执行的 verify_writers 已接受预期writer集合。
成功报告必须 scan_complete=true、phase=REPORT，并通过所有原成功及父层准入判据。

没有完整 v2 child 报告（如进程被外部中止或父期限先到）时，父层只保留已取得信息，
不补造 progress。合法 child failure 的 progress 随原 child_failure 传播至最终 CLI
和私有交接摘要，不覆盖更早的超时/TTY/传输首因，不据此新增调用。

## 协调预算与实现边界

| 维度 | 本方案 |
| --- | --- |
| FD 元数据操作 | 单次2097152，三类共享、调用前收费 |
| PID / 每进程 task / 全部 task | 32768 / 32768 / 65536，初读和复核保持 |
| 每 FD snapshot | 65536项，初读和复核保持 |
| maps | 每文件1 MiB；累计接受512 MiB；首次越界已读值最多513 MiB |
| stat / fdinfo 文本 | 每文件16384 / 4096 B，原复核保持 |
| 时间与资源 | 每writer15s、900s/780s；AS256 MiB、FD128、原CPU/RSS观测保持 |
| 输出及固定root代码 | 输入/stdout65536 B、stderr4096 B、payload32768 B、argv65536 B |
| 两维护源文件 | host/guest各98304 B；其它来源保持原界和准确pin |
| guest传输 | 仅guest源限98304 B；reader和descriptor仍65536 B；压缩49152 B、解压393216 B保持 |

相互独立的界必须同时成立，不承诺每个理论最大值都能在15秒内处理完。认证、宿主调度、
全局 PID/task/FD 活动、proc 可见性、maps 解析与 AS 均可能另行拒绝。期限为原协作式检查，
不可中断读取不被伪称可及时强制结束；不为吃满计数预算延长时间。
原设备1296 MiB/370 inode条件、264 MiB/80旧承诺、备份320 MiB、镜像576 MiB、
capture8 MiB/32 inode及全部历史UNKNOWN保持。这些不是新增额度或排他预留。

`growth_sources` 只扩大两文件的源长度门；`source_bundle/GUEST_LOADER` 只对 guest
条目采用新界，不能把所有输入一并放大。根writer仍从准确函数和固定内核模块生成，
原loader/payload摘要、隔离解释器、真实终端和全部工具资格保持；不从可写仓库import。
本范围A/C及文档完整性/祖先校验加入清单，保留全部旧pins；清单显式绑定v2、计量规则
和固定上限，禁止旧包/旧报告/旧窗口被作为新候选。

取舍：不新增 kcmp 等内核接口，不按共享猜测省略线程，不以正常镜像锁替代观察，不停止
宿主应用来凑快照，不取消全局漂移校验。新预算和进度能改善当前适配和诊断，仍不保证通过。
