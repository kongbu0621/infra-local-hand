# Q1 单次管理实验入口

本入口属于 `LH-E3-QUOTA-HARNESS-v1` 已批准的 Q1 隔离开发，沿用 A
`415327ebdcc251bb055da9931a7a88990f750b7a` 和独立 C
`5a4ea852091db06549a876e42bbd5f95d5869d3b`，不修改三份权威文档。
当前真实 fixture 仍 NOT_PREPARED，Q1 实机和整体 E3 仍 BLOCKED。

`tools/run_q1_experiment.py` 将准确管理输入接到既有 `Q1Controller.run` 或
`recover_original`，并输出一条有限私有诊断记录。它不是 listener、Q2 接口、安装器、
宿主准备程序或完整 Q1/三单元验收套件。源码 `e9b21b355a5dcb507d1b73d620b3307918d04533`
及准确测试见[本轮验证记录](E3_QUOTA_Q1_EXPERIMENT_VERIFICATION.md)。

## 输入和调用顺序

先完成[fixture 输入交接](E3_QUOTA_Q1_FIXTURE_HANDOFF.md)中的原配置和系统基准，
再由已存在的管理流程交付下列准确输入。没有默认主机、账户、根目录、运行 ID 或自动猜测。

| 管理输入 | 字段与限制 |
| --- | --- |
| 外部固定值 | 受保护实验输入文件的绝对路径、原始字节 SHA-256、完整 source commit |
| 实验原件 | schema=`local-hand-quota-q1-experiment-input/v1`；最大 16 KiB、深度 4；拒绝重复/额外字段 |
| 操作 | `operation` 明确为 `run` 或 `recover_original`；无默认动作、重试、准备、安装或清账动作 |
| 来源与安装 | `source_commit`、`runtime_path`、`runtime_digest`；与外部固定来源、原 manifest 和 installation digest 一致 |
| 原票据 | `ticket` 使用既有 `local-hand-quota-ticket/v1` 的 canonical base64；完整保留 slot/generation、request/allocation/execution/phase、issued/deadline |
| 控制账本 | `journal` 仅含 `path`、`owner_uid`（本 root 管理入口必须为 0）、`device`、`inode`；预建并按原规则验证 |
| 控制器监督 | `controller` 使用下表的准确监督身份及有限限制；声明仍须与实际宿主逐项一致 |

实验输入文件逐级 root 所有、不可被 group/other 写入，不接受符号链接、额外硬链接或 setid。
它必须与所有 root、journal、其他配置/安装输入互不交叠。管理侧源码、解释器系统库、loader 和
共享库须由外层基准固定；运行代码不能从可任意篡改的自身环境里证明自身可信。

以下只说明已准备控制器内部的调用参数，不是当前 GX10 上的执行指令：

```sh
python -I -B tools/run_q1_experiment.py \
  --input '<受保护实验输入绝对路径>' \
  --sha256 EXPERIMENT_SHA256 \
  --source-commit FULL_SOURCE_SHA
```

入口不生成 ticket、不取当前时间替换原 issued/deadline，也不延长恢复请求。
原 ticket 须由受信测试控制方在原管理分配下及时交付；超时就保留该次失败，不续时补投。
`run` 再次遇到已有意图时只返回原保留状态；不会自动转为恢复或新查询。
`recover_original` 使用完全相同的原票据及原安装配置，只观察/停止原身份，丢失原输出/launcher 时仍 UNKNOWN。

## 控制器的实际监督核验

| controller 字段 | 含义 |
| --- | --- |
| `schema` | `local-hand-q1-controller/v1` |
| `unit`、`invocation_id` | 准确 service 名与当前 32 位 hex InvocationID |
| `cgroup`、`cgroup_device`、`cgroup_inode` | 准确专用控制器 cgroup；末级为 unit，直接父目录是 slice，与 query 树分离 |
| `runtime_max_usec` | 1–120 秒，用整数微秒表示，与 manager 完全一致 |
| `timeout_stop_usec` | 1 毫秒–5 秒，用整数微秒表示 |
| `memory_bytes`、`tasks_max` | 16 MiB–1 GiB、2–64；manager 与实际 memory.max/pids.max 都必须匹配 |
| `cpu_quota_per_sec_usec` | 1000–1000000 微秒/秒；manager 与实际 cpu.max 的 quota/period 比值必须匹配 |
| `limit_cpu_seconds` | 1–120 秒；manager 软/硬 CPU 限制与进程实际 RLIMIT_CPU 均固定并核对 |

这些数值是准入上限与精确对照，不是已为环境预留资源的证明。
入口在任何 journal 构造之前核验：root 身份、boot、初始 user namespace、当前 PID/cgroup，
独立的 stdout/stderr 匿名写管道；固定 cgroup2 挂载、目录身份及实际有限控制文件；
准确 systemctl binary 摘要和一次有界 `show` 的当前 MainPID/InvocationID/单元配置。
manager 查询最多一次、双流共用 16 KiB、最多 2 秒观察；失败不派生替代查询。

控制器须为 Type=exec、ExitType=cgroup、Restart=no、RemainAfterExit=no、NotifyAccess=none、
KillMode=control-group、SendSIGKILL=yes、FinalKillSignal=9、TimeoutStopFailureMode=kill，
MemorySwapMax 和实际 memory.swap.max 均为 0。不得有 pending job/ControlPID、额外执行钩子、
TriggeredBy、OnFailure、OnSuccess 或 RestartForceExitStatus。systemctl 时间输出按已核对的有限
min/s/ms/us 格式解析，未知或 infinity 拒绝。

监督已经存在，入口才可以验证它；入口不会创建 supervisor。自身的配置读取、进程创建或
stdout 写入可能阻塞，不能靠自身定时器覆盖这些等待。外层仍须有准确独立停止入口和有界私有读端。
控制器被杀死不证明另外一个 systemd query unit 已停止；UNKNOWN 继续保留原资源。

当前 InvocationID 和 unit cgroup inode 在该控制器单元启动后才成立。外层受信启动器需要先在
该准确受监督单元中取得身份并完成保护输入交付，再以保留 PID 的 exec 进入本入口；
不能从普通终端的父进程代填，也不能把旧控制器身份沿用到新实例。
启动器本身须固定源码与安装；exec 不重启单元、不重置监督计时或 CPU 预算，也不重建 ticket 续时。
使用子进程代替 exec 会改变 MainPID，应被拒绝。
后续已补充[单元内启动适配与有限采集源码](E3_QUOTA_Q1_LAUNCH_HANDOFF.md)：
启动器在已存在的受监督单元内绑定当前身份，create-only 交付输入并保留 PID 地 exec。
外部采集组件只处理原管道并交付独立停止所需的已知身份，不创建监督或执行停止。
真实 fixture、其外部独立监督/停止入口及完整一键宿主验收仍未交付。

## 输出、失败和保留

输出 schema=`local-hand-quota-q1-experiment/v1`，最多 128 KiB、一条 JSON 行，属于
**私有管理诊断文件**。这不替代或扩大 Q2 架构的 32 KiB socket 响应上限。
外层须在已计入有限容量的私有证据存储中保存原输出、退出码及独立停止事实。
不要将真实输出直接提交到 Public：其中包含 boot、原请求、unit/cgroup、PID、根 dev/inode 和 FS/project。

| 退出码 | 含义 |
| --- | --- |
| 0 | 管理侧原次观察为 OBSERVED；不代表 Q1 完整出口、真实超限写入或 E3 通过 |
| 2 | 接触账本/控制器执行前的输入或监督拒绝，或命令行用法错误；不据此推导旧资源未消费 |
| 3 | 当前平台不支持 |
| 4 | 接触账本以后、执行或恢复结果为 UNKNOWN，原资源继续保留 |
| 74 | 结果管道写入失败，可能仅有部分输出；不得自动重查 |

结果保留原 ticket 摘要、精简 binding、控制器准确身份、原 query InvocationID/unit facts、
pending client PID、控制调用数、原 stdout/stderr 字节的 base64 及长度；原判定、query cleanup、
journal 和入口关闭错误分别记录。中断时尽量保留已捕获字节和已知子进程，不重放或认领未知退出。
输出记录不假造 Outcome 没有承载的 EOF/完整性信息；`evidence_complete` 保持 false。
任何 admission、Q1 实机出口、E3 或 production 接受标志均 false。

成功、失败、取消、中断、崩溃或响应丢失都不释放永久意图及原 allocation/slot/root/domain。
没有 reset/release/retry；更换 ID、generation、journal 或实例不能成为原 UNKNOWN 的成功重试。
关闭账本失败或编码失败也不能触发第二次 query。需要保存的首因与原不确定状态不被清理错误抹掉。

## 仍待实测的出口

管理观察之后仍须独立证明：普通隔离身份的原权限对照、真实 UUID/FS 绑定、固定代次且无其他
writer、真实超限写入拒绝和域外写入/改 project 负例、原 query/launcher/collector 全部退出，
以及本地账本与证据保留峰值。Q1 出口通过后才进入 Q2、Q3、Q4。
当前没有运行真实 systemd 查询或 quota，没有准备主机或操作 GX10。
