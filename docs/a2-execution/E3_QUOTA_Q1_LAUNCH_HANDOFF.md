# Q1 单元内启动适配与外部有限采集

本交付继续属于 `LH-E3-QUOTA-HARNESS-v1` 的已批准隔离开发，沿用 A
`415327ebdcc251bb055da9931a7a88990f750b7a`、C
`5a4ea852091db06549a876e42bbd5f95d5869d3b`。三份权威文档和生产封堵保持。
本文件说明新增源码的接线与边界，不生成实际账户、服务、文件系统或配置。
真实 fixture 仍 **NOT_PREPARED**，Q1 实机和 E3 仍 **BLOCKED**。

## 本轮连接的边界

`tools/launch_q1_experiment.py` 在已经存在的受监督控制器单元内取得当前身份，
保护交付一份既有格式的实验输入，再用同 PID 的 `exec` 进入
`tools/run_q1_experiment.py`。它不创建监督单元，不从普通终端替控制器填写身份。
实际控制器的有限资源与独立停止入口须在调用前存在。

`tools/admin/local_hand_quota_observer/experiment_capture.py` 是外部受信管理流程的
内部采集组件：仅消费已经创建的原进程管道，不发起实验、查询或停止命令。
采集保留原字节、双流 EOF、客户端退出和读端关闭的独立事实；这些事实不代替
controller/query 单元及其所有子孙进程的停止证明。

## 固定输入与动态身份

启动输入通过外部 SHA-256 和完整 source commit 固定。原 operation、runtime、journal、
ticket 及 issued/deadline 保持；静态 controller 限制由部署侧明确给出。

| 输入 | 严格范围 |
| --- | --- |
| schema | `local-hand-quota-q1-launch-input/v1`，最大 32 KiB、JSON 深度 4，拒绝重复或额外字段 |
| operation / source_commit | `run` 或 `recover_original`；来源为外部固定的完整 40 位提交 |
| runtime_path / runtime_digest | 原受保护 runtime 的准确路径和原字节 SHA-256 |
| journal / ticket | 沿用实验输入合同中的准确 journal 身份及原 canonical base64 ticket |
| controller | 既有 controller schema、unit、cgroup 和六项有限资源字段；不接受预填 InvocationID 或 cgroup dev/inode |
| output | 准确输出路径，以及预建父目录的 path、owner_uid=0、device、inode；父目录须私有且受保护 |
| installation | 准确 tools_path 和 `launcher.SOURCE_FILES` 的完整逐文件摘要；拒绝缺失或额外条目 |

下列仅说明已准备监督单元内部的参数，当前不是 GX10 执行指令：

```sh
python -I -B tools/launch_q1_experiment.py \
  --input '<受保护launch输入绝对路径>' \
  --sha256 LAUNCH_INPUT_SHA256 \
  --source-commit FULL_SOURCE_SHA
```

当前 InvocationID 和 cgroup dev/inode 在单元启动后取得，并经已有
`admit_controller` 核对实际 MainPID、manager、cgroup 限额与匿名写管道。
`INVOCATION_ID` 环境值只作为候选，不能替代 manager 核验。

启动器和实验入口依赖的管理侧源码单列固定字节清单；既有 runtime 的
`installation_digest` 仍只覆盖它原来声明的范围，不被重新解释为全部安装摘要。
管理侧使用固定的 source-only 安装；缓存字节码及会优先于已固定源码加载的模块入口
不能混入该安装。Python、stdlib、loader、共享库及宿主管理程序仍须由准确外层系统基准固定。

绑定输入写入独立预建的受保护父目录，与 journal、全部 slot、配置及安装文件无交叠。
输出 create-only，完成文件与目录持久化后才允许 exec；已有文件、短写失败、fsync 失败、
身份变化或 exec 失败保留现场，不覆盖、不删后重试、不触碰查询 journal。
exec 保留 PID、原匿名管道、单元监督计时及 CPU 限制，不重新生成或延长 ticket。

## 采集、恢复与停止交接

管理流程必须先固定有限采集期限和证据保留容量。正常运行和恢复都使用事先固定的管理
采集窗口，最长 120 秒；可以覆盖原查询 deadline 后的有限收尾，以保留原 `UNKNOWN`
和清理失败诊断。原 ticket 和 query deadline 始终保留，管理采集时间不能被计为查询
新增预算，`capture_complete` 只表示字节收集完整，不判断原查询成功。

开始采集无需先拿到最终诊断中的控制器观察：原进程与实际匿名读管道即可保留早期拒绝
和部分输出。若已有独立取得的控制器观察，则同时核对其原 boot 和管道身份；缺失时
控制器身份保持未知。不会解析输出的自报字段并据此授予可信身份或停止权限。

内部调用为 `capture_existing(process, binding, operation=..., collection_started_ns=...,
collection_deadline_ns=..., controller=..., original_query_invocation_id=...)`。
`process` 必须是外部已启动的原 `Popen`，两条管道未缓冲、未读且独占；本组件接管读端并
在返回前分别尝试关闭。`binding` 保留原查询，两个管理时间为外层事先固定的 BOOTTIME；
可选控制器观察和 query InvocationID 须独立取得，不能从未经核对的输出反填。
外层创建该原进程时须使用 `bufsize=0`；不能把内部 query 的
`Q1Controller.launcher.process` 接进这里，其管道属于另一层控制器且不是本接口的未缓冲读端。

诊断输出最多 128 KiB，错误流还受独立限制，并共同消耗有限总预算。
超时、超量、流错误、中断、客户端已退但管道未 EOF、输出仅部分到达分别记录。
关闭读端失败不覆盖首因，输出丢失不会触发新的查询。

采集结束只交付已知原身份和未解决状态。外层已有的独立停止入口负责控制器；
已记录 query 的恢复继续经 `Q1Controller.recover_original` 观察或停止原身份。
没有原 query InvocationID 时不能停止猜测的同名单元。结束采集、杀死客户端、
控制器退出或停止命令返回都不能证明另外一个 query 已退出。
未知资源继续保留，不释放 slot、root、计费域或永久启动意图。

## 真正运行前仍须交付

沿用 [fixture 清单](E3_QUOTA_Q1_FIXTURE_HANDOFF.md)：准确候选与安装、ABI/系统基准、
受信账户与监督单元、独立 controller/query 树、真实 FS/UUID/project/slot、保护配置与
输出目录、有限 journal/证据容量、独立采集监督和准确停止入口。
部署侧还须验证 systemd 对匿名管道的实际转交关系，以及所有控制器、查询、启动客户端
和采集器的退出事实。源码及本地 pipe/exec 测试不提供这些宿主事实。

本轮交付单元内启动适配和采集组件源码，不是已安装的外层 fixture 或完整一键 Q1 验收。
真实权限对照、硬配额超限拒绝、域外写入负例及全部独立退出仍按
[Q1 实验交接](E3_QUOTA_Q1_EXPERIMENT_HANDOFF.md)验收。Q1 出口后才进入 Q2 → Q3 → Q4；
GX10 现役切换、E4–E6 和真实 NAS 的原授权边界保持。
