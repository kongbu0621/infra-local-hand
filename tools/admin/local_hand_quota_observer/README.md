# Q1 原生 quota 查询原语

2026-09-25 进展：Owner 已返还私有隔离 fixture 的查询、PrivateUsers 权限/边界、真实
EDQUOT 和完整退出复核结果；原专用 guest 的容量复核已完成，见
[限定范围结论](../../../docs/a2-execution/E3_QUOTA_Q1_GUEST_CAPACITY_REVIEW.md)。准确状态与历史失败保留见
[Q1 收口清单](../../../docs/a2-execution/E3_QUOTA_Q1_CLOSEOUT_REVIEW.md)，后续接线差异见
[Q2 设计草案](../../../docs/a2-execution/E3_QUOTA_Q2_INTEGRATION_DRAFT.md)。
Q2 第一批无特权协议/客户端已有源码与 31 项逻辑验证，11 项实际 IPC 尚未验证，见
[客户端验证记录](../../../docs/a2-execution/E3_QUOTA_Q2_CLIENT_VERIFICATION.md)。第二批已增加固定准入、
持久防重和管理预算服务核心，并提供 bootstrap 新版回执消费；107 项定向测试通过，见
[持久核心设计](../../../docs/a2-execution/E3_QUOTA_Q2_DURABLE_CORE.md)及
[准确验证记录](../../../docs/a2-execution/E3_QUOTA_Q2_DURABLE_VERIFICATION.md)。本目录仍无 Q2 listener，
受监督运行适配和 broker 持久接线尚未完成。
下文“尚未实测/NOT_PREPARED”等措辞保留各次源码交付当时的状态；不能据新结果授予生产资格。

批准范围：`LH-E3-QUOTA-HARNESS-v1`，A `415327ebdcc251bb055da9931a7a88990f750b7a`，
独立 CLOSED 记录 C `5a4ea852091db06549a876e42bbd5f95d5869d3b`。

本目录是 **Q1 管理侧内部装配源码**，没有监听服务、安装脚本、公开作业入口或支持启用开关；
不接入 broker，不进入默认 wheel/Plugin。源码已具备单次 systemd 查询装配，
**尚未在专用 systemd/quota 环境实测，不能据此安装到 GX10 或宣布 E3 通过**。

| 组件 | 当前职责 |
| --- | --- |
| `admission.py` / `supervision.py` | 不可变 manifest、原绑定/截止时间、有界回包与独立退出事实判定 |
| `protected_inputs.py` / `worker.py` | 保护配置/安装读取，在 query unit 内核验身份、打开固定根，将 FD 3 交付已验证 native ELF |
| `quota_fd_query.c` / `quota_syscall_filter.h` | 固定 FD quota 观察、原始 errno、查询阶段参数级 seccomp 过滤 |
| `journal.py` | 最多 32 个永久意图，文件与目录 fsync 后才交付；原请求/资源永不自动重用 |
| `systemd_runtime.py` | 固定 system-manager argv、启动竞态等待、原 InvocationID 停止、专用父 cgroup 空状态、双管道与采集进程退出 |
| `fixture_inputs.py` / `tools/validate_q1_fixture.py` | 两份固定字节快照的离线绑定与全部路径交叠检查；不读取声明的宿主对象、不创建 ticket 或启动查询 |
| `controller_guard.py` / `experiment.py` / `tools/run_q1_experiment.py` | 单次管理测试入口；先核验自身实际监督，再接原票据运行或恢复，不准备宿主或重投 |
| `experiment_evidence.py` | 有界私有诊断记录，保留原始输出与各层错误；不是 Q2 receipt 或完整验收证明 |

## 精确行为

- 零参数；只接受管理侧父进程继承的固定 directory FD 3，不打开任何客户端路径或 block device。
  这不是公开 FD 接口：未来 observer 必须拒绝客户端传入 FD，只从自己的受保护 manifest 映射打开根。
- 检查真实 directory/只读 FD、ext-family/XFS magic、非零 project ID 和继承标志。
  ext 系列共享 magic；这里只作预筛，不据此证明准确 ext4 类型或完整 filesystem 准入。
- 用本机已审阅 Linux headers 的 `SYS_quotactl_fd`，不猜 syscall 编号；缺少 ABI 则 UNSUPPORTED。
- 固定三次 quota syscall：`Q_XGETQSTATV/PRJQUOTA` → `Q_GETQUOTA/PRJQUOTA` →
  `Q_XGETQSTATV/PRJQUOTA`。前后状态须具有 project accounting/enforcement 标志；
  generic Q_GETQUOTA 的 hard limit 是 1024-byte 单位，并检查有效位、零值和换算溢出。
- 中途失败立即停止后续查询，不重试、不更换 API、不设置 quota；逐项保存原 rc 和即时 errno。
- 再次观察 FD 的 dev/inode/uid/gid/mode 和 project/继承，保存前后事实；漂移/复查失败为 IO_UNCERTAIN。
- 固定 `local-hand-quota-abi/v2` 有界 JSON，小于 4096 bytes；不输出路径，不把错误文本拼成协议。
  `hard_bytes` 未能验证/换算时为 null。保留成功 syscall 的 errno 快照，判定以 rc 为准。
- close 只调用一次；失败保留原 substantive error，不能用清理错误覆盖原权限错误。
  输出不完整、非正常退出或无原记录时，未来监督器必须记 UNKNOWN。

退出码：0 = OBSERVED（仅取得该次事实），2 = REJECTED，3 = UNSUPPORTED，4 = IO_UNCERTAIN；
70/74 或信号退出表示报告内部/传输失败。所有 JSON 固定保持 admission_proven、real_e3_accepted、
production_supported 为 false。没有 PASS 或支持启用开关。

native 原语本身不核验准入额度、mount/boot/namespace/generation、原执行或预算；外围组件负责绑定，仍不证明查询原子性、
身份不会在未来变化或真实超限写入已被拒绝。前后观察不是连续保证；这些须由后续受信绑定与实测补齐。
Q_GETQUOTA 仍可能等待存储或涉及 quota 元数据，父进程须有独立监督和停止/未知保留机制后才能实机调用。
禁止添加 setuid 或文件 capability；普通作业始终不携带 host 管理能力。

## 开发验证

独立输出目录内编译，不安装到主机路径：

```sh
cc -std=c11 -O2 -Wall -Wextra -Werror -Wconversion -Wformat=2 \
  -fstack-protector-strong -D_FORTIFY_SOURCE=2 \
  tools/admin/local_hand_quota_observer/quota_fd_query.c \
  -o /absolute/new-build-directory/quota_fd_query
python3 -m unittest discover -s tests -p test_e3_quota_abi.py -v
```

测试真实 binary 的“无 FD”和“拒绝参数”负例，不进行 quota syscall。
成功/权限/限额/漂移分支通过单独链接 `tests/fixtures/quota_query_syscalls.c` 验证；
该 test-only shim 拦截全部 quota syscall，结果为 **LOGIC_ONLY**，不是宿主 quota 验证。
生产原语没有该 shim 的环境开关。准确编译器、headers 和二进制摘要须随每次产物记录；
云端 x86_64 编译不能替代 GX10 aarch64 的 ABI 和运行验证。

## 来源与下一步

固定 Linux `adc218676eef25575469234709c2d87185ca223a` 的
[fs/quota/quota.c](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/fs/quota/quota.c)
中 `quota_getxstatev` 使用 filesystem `get_state` 返回 accounting/enforcement，
`quotactl_fd` 仍走原权限检查，不能仅凭 FD 解决权限。目标 filesystem 不支持这些观察即停止。

Q1 的权限过滤和受监督装配已有源码，但管理侧固定对象的真实 OS 准入和 fixture 结果仍缺失；Q2 的认证通信、
持久防重、绑定/预算、Q3/Q4 三单元和故障 harness 也未完成。生产 support 封堵保持。
后续先补可审阅装配与监督，再交接准确隔离对象；当前不向 GX10 发起新的盘点或安装命令。

## Q1 固定对象与监督判定核心

这两个 Python 模块是管理侧内部组件，没有 CLI、监听入口、启动/重试方法或安装脚本。
它们提供以下已实现的检查，不把传入的逻辑事实称为主机实测：

- `decode_manifest` 只处理受信调用者交付的字节快照，限制 32 KiB、32 个 slot、JSON 深度和节点数；
  固定 schema，拒绝重复/未知字段、浮点数、布尔伪整数、非法路径及版本。摘要必须与外部固定值一致。
  返回不可变对象，逻辑 slot/generation 精确匹配；不接收作业传来的路径或 FD。
- 每个 slot 固定目录 dev/inode/uid/gid/mode、FS 类型/UUID、project/继承标志及非零有限 hard bytes。
  拒绝根别名、父子重叠、同 device/UUID 的矛盾映射、同计费域的矛盾额度；共享域只计一次额度。
  这些是**配置一致性**检查；不是已查明真实 UUID、准确 ext4 类型、namespace、保护权限或容量准入。
- `bind_query` 固定 manifest/slot、原 allocation、execution/phase、request、确定的 unit/cgroup。
  时间输入必须来自同一 boot 的 `CLOCK_BOOTTIME` 纳秒；deadline 取原阶段截止时间和管理侧上限的较小值，
  管理侧上限最多 30 秒。恢复须保留原 Binding，不重新调用绑定函数续时。
- `QueryMonitor.read_once` 只接受调用者独占的非阻塞 pipe FD，一次最多读取 4096 bytes；
  保留的原始回包前缀最多 4095 bytes。没有等 EOF 的循环、线程、子进程或目标文件读取。
  FD 更换、超量、部分/重复 JSON、EOF 后数据、时钟倒退和超时均保留 UNKNOWN。
- 完整回包与退出证明分开。manager 提供同 boot/unit/InvocationID/cgroup 的原始观察，并证明
  原启动交付已结束、重新启动已围栏、没有排队 job、unit 已终止、递归 cgroup 为空、全部采集器已停止，
  才能确认 query 停止。TERM/KILL/ACK、仅主 PID 消失、仅 JSON 完整均不满足这些条件。
- 成功还要求正常 exit 0、完整 EOF，以及 C 原语的准确调用顺序、UID/ABI、前后根/project/enforcement、
  计费单位与额度全部匹配。成功 syscall 的非零 errno 原样保留，以 rc 判定。
  原始失败输出保留于 `raw_prefix`，不会被通用错误或零 errno 改写。
- 恢复丢失响应时永久保留 UNKNOWN；没有原 InvocationID 时不能凭当前同名 unit 认领停止证明。
  判定核心没有重新启动的能力；Q1 journal 已永久消费单次意图，**服务级鉴权、防重及与 broker 联合占容仍属于尚未完成的 Q2**。

`UnitObservation` 必须由受信 manager adapter 获取，不能从客户端或 query JSON 反序列化。
当前逻辑测试直接构造它，所以不证明 systemd/cgroup 约束已经生效。`Decision` 只描述原观察；
成功缓存不是新的主机健康证明，也不授予资源释放或作业执行。admission_proven、real_e3_accepted、
production_supported 始终 false。

## 单次真实运行装配源码

`Q1Controller(config_path, config_digest, journal).run(original_ticket)` 只供外部独立监督的
管理员测试控制进程调用。它不创建账户、slice、root、quota 或安装目录，也不是 listener。
管理配置读取、目录 fsync、进程创建仍可能阻塞；本组件不声称具备 Q2 的有限控制响应服务。
`recover_original(original_ticket)` 只读取原记录、观察/停止准确原身份；不启动新的 query。

1. 配置与安装：`local-hand-quota-runtime/v1` 绑定 manifest、Python/worker/模块/native/systemd 工具摘要，
   初始 user namespace 的 dev/inode、专用 slice 及其 cgroup dev/inode，以及有限内存/进程/CPU/输出预算。
   文件逐祖先 root 所有、不可被非 root 写入，拒绝符号链接、非普通文件、setid、硬链接及可执行 file capabilities。
   worker 核验后执行相同源码字节，native 用核验并保留的 ELF FD 执行。哈希不替代可信初始安装；
   解释器标准库、ELF loader 和共享库仍需要专用环境的固定系统基准。
   此 installation_digest 覆盖 worker 依赖及配置中的可执行文件；控制器/runtime/journal 源码须由外层
   fixture 另行固定准确提交与字节，不冒称该摘要覆盖完整管理侧安装。
2. 意图：`StartJournal` 使用准确 dev/inode 的 0700 本地控制目录、非阻塞锁和 create-only 记录。
   意图文件及目录 fsync 完成后只调用一次交付；崩溃、原 deadline 到期、响应丢失均不补投。
   原 slot（包括换代次）、根 dev/inode、FS UUID/project 计费域及 allocation 持续占用；无 GC/回收接口。
   journal 路径通过 `InaccessiblePaths` 对 worker 隐藏，且不与目标根或固定输入重叠。
3. 单元：固定 `systemd-run --system --pipe`，`Type=exec`、`ExitType=cgroup`、`RemainAfterExit=yes`、
   `Restart=no`、`KillMode=control-group`。argv 无 shell 或客户端属性；RuntimeMaxSec 只取原剩余时间。
   管理命令固定禁止密码提示（`--no-ask-password`），systemctl 同时禁止 pager，避免交互助手。
   单元 root UID、初始 user namespace、能力仅 `CAP_SYS_ADMIN CAP_DAC_READ_SEARCH`，NNP 开启，
   关闭继承/ambient 能力，并限制内存、Tasks、CPU、设备、网络、挂载操作和写入路径。
   `User=` 使用 system manager 默认 root；显式 `User=0` 在 systemd 255 的 setuid/seccomp
   路径会留下继承能力。worker 仍核验实际 UID/EUID 0、准确 Prm/Eff/Bnd 和零 Inh/Amb，
   不接受配置声明代替实际权限，也不放宽非零继承位检查。
   `ProtectSystem=strict` 下仅固定 slot 有 `ReadWritePaths` 例外，因为 Q_GETQUOTA 需要 mount write access。
   这不承诺 quota 元数据零变化，也不保证 CAP_SYS_ADMIN 组件失陷时仍安全。
4. 根与 FD：systemd-run 仅负责标准流；worker 在自己的单元内打开固定根，核对普通作业 UID/0700、
   dev/inode、当前 mount namespace 的 mount ID、FS 类型/设备/rw，再把同一个只读目录 FD 放到 3。
   UUID 目前仍是管理员保护的设备映射，**没有独立读取真实 FS UUID 的证明**。
5. 查询限制：native 受信检查前奏后、第一次 quota 调用前安装 seccomp。只准 FD 3 上的
   `Q_XGETQSTATV(PRJQUOTA,0)` / `Q_GETQUOTA(PRJQUOTA,observed_project)`、FSGETXATTR、fstat/close、
   stdout 有限 write 及最小 UID/退出调用；不准 open、setquota、mount、exec 或 fork。
   仅支持本机 headers 定义的 little-endian LP64 x86_64/aarch64；未知 ABI 不猜号。
   filter 不能消除检查前奏/loader 的信任，也不能消除 project 并发变更；仍须管理员保持原代次及无其他 writer。
6. 退出：先留存原 InvocationID/ExecMainCode/Status/Result，再按同身份停止；最后核验排队 job、
   launcher/control 进程和双流 EOF。systemd 可在 active/exited 时删除叶 cgroup，因此用预先固定且保持存在的
   专用父 cgroup 的真实 cgroup2 身份和 `cgroup.events populated=0` 证明整个后代树为空。
   查询控制器必须在该树外；目录不存在、身份变更、读失败绝不当作空。
7. 截止和恢复：成功要求 stop 与双 EOF 也在原 query deadline 内。额外最多 3 秒仅用于管理侧清理，
   不能转为成功或续额。最多 32 次管理命令，为最终停止保留额度；不围绕未退出控制子进程派生替代者。
   异常保留回包前缀、已观察 unit 事实、未收口 PID、原失败及记账失败，不用二次错误覆盖首因。
   `pending_clients` 仅列已取得进程句柄的未收口 PID，空列表不能证明全部采集器停止。
   恢复若缺原 InvocationID，不认领/停止当前同名单元；即使已知原单元停止，原 launcher/pipe 归属丢失仍为 UNKNOWN。

`Outcome` 是管理侧内部对象，不是认证服务 receipt。所有观察均不能自动释放原资源、启动普通作业或启用生产。
Q2 的 peer 鉴权、外部协议、防重及 broker 账本/原三段预算绑定尚未完成；不能用 Q1 journal 冒充完整 Q2。

## 专用环境交接前仍需具备

先按[准确输入与实测交接](../../../docs/a2-execution/E3_QUOTA_Q1_FIXTURE_HANDOFF.md)交付 manifest/runtime
快照、外部摘要、完整 source commit 及 runtime/journal 安装路径。Linux 离线入口必须使用 `python -I -B`；
`CONFIG_CONSISTENT` 只表示配置一致，始终为 OFFLINE_ONLY，不证明宿主准备完成或授予运行权限。
它与运行装配复用全部 slot 的路径检查，拒绝任一 root 与固定输入/journal 交叠及固定文件路径的相互别名。
不对声明的宿主路径作 resolve、stat 或 open，不生成运行 ticket、资源预留或启动意图。

- 预先确认的可丢弃 ext4/XFS project-quota filesystem 与 slot、普通测试 UID/generation/project/hard limit，
  以及其当前 boot、真实 FS 身份和无其他 writer 的保护流程。
- 预先创建并持续保留的专用 system slice/cgroup，控制器运行于树外的独立监督单元；准确路径和 dev/inode。
- 受保护的解释器/native/源码/systemd 安装、初始 user namespace 身份、独立本地有限 journal 存储。
- 准确 kernel/systemd/compiler/headers 基准，实际能力与 syscall/文件系统观察、超限写入和未知退出负例。

这些是后续环境交接要求，当前没有创建或采用现有桌面/服务账户，也没有操作 GX10。
Q1 实机出口通过前不把普通作业切到新机制；随后依次 Q2 绑定、Q3 真实三单元正常链、Q4 故障恢复。
生产 `E3_SUPERVISION_UNVERIFIED` 保持。

定向验证：`python3 -m unittest discover -s tests -p 'test_e3_quota_*.py' -v`。
真实匿名管道、临时文件持久化和无 quota 的 kernel seccomp 负例单独分类；manager/成功 quota 均为 LOGIC_ONLY。
普通开发的公开安全日志随验证记录入库，不逐次生成 ZIP；真实主机原始路径/账户等证据继续私有保管。

固定来源：
[systemd service.c](https://github.com/systemd/systemd/blob/70bae7648f2c18010187c9cf20093155eaa26029/src/core/service.c)
的 SERVICE_EXITED prune 和 stdio 释放，及上文固定 Linux quota.c 的权限/mnt_want_write。
源码核对不能替代目标版本的实测。

## 单次管理测试入口

[准确调用与监督交接](../../../docs/a2-execution/E3_QUOTA_Q1_EXPERIMENT_HANDOFF.md)规定
`tools/run_q1_experiment.py` 的受保护输入、外部摘要、原票据和当前控制器身份。
入口要求 Linux、root 与 `python -I -B`；在构造 journal 前，核验实际 MainPID/InvocationID、
初始 user namespace、独立 cgroup2 及 memory/pids/cpu 限制、进程 CPU rlimit 和独立匿名输出管道。
管理观察只调用一次固定 systemctl，不通过配置布尔值代替实际检查。

原请求只选择一次 `run` 或 `recover_original`。关闭账本失败单独记录；中断尽量保留原字节，
编码或管道失败均不补投。单条私有诊断最多 128 KiB，与 Q2 的 32 KiB socket 上限分开；
不补造内部 Outcome 没有携带的 EOF 事实，`evidence_complete` 与全部准入标志保持 false。

准确控制器身份在 unit 启动后才存在。后续新增
[`tools/launch_q1_experiment.py`](../../launch_q1_experiment.py) 与 `launcher.py`，
在已存在的受监督 unit 中核验当前身份和管理安装字节，create-only/fsync 交付输入后
保留 PID 地 exec 此入口；原票据、期限和监督预算不重置。
`experiment_capture.py` 只采集已存在的原进程匿名管道，保留有限原字节、EOF、客户端退出
及读端关闭错误；不解析诊断为准入、不发起或停止查询。有限管理采集窗口可保留原查询
超时后的收尾诊断，但不延长原查询期限。准确接线见
[启动与采集交接](../../../docs/a2-execution/E3_QUOTA_Q1_LAUNCH_HANDOFF.md)。
这两个内部组件不创建 fixture 的监督单元、独立停止入口或有限存储；真实 fixture 和
完整 Q1 实机验收仍未交付。
