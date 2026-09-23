# Q1 原生 quota 查询原语

批准范围：`LH-E3-QUOTA-HARNESS-v1`，A `415327ebdcc251bb055da9931a7a88990f750b7a`，
独立 CLOSED 记录 C `5a4ea852091db06549a876e42bbd5f95d5869d3b`。

`quota_fd_query.c` 是管理侧 observer 的内部 ABI 原语。`admission.py` 和 `supervision.py`
补充固定 manifest 数据校验、原语回包核对、有界管道采集和独立退出判定核心；
当前还没有 observer 服务、持久请求账本、peer 鉴权、真实 manifest/namespace 准入或进程监督装配。
这些组件不接入 broker，也不打进 wheel/Plugin。
**本目录当前只能作为 Q1 开发检查点，不能安装或提权后独立运行。**

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
- 固定有界 JSON，小于 4096 bytes；不输出路径，不把错误文本拼成协议。
  `hard_bytes` 未能验证/换算时为 null。保留成功 syscall 的 errno 快照，判定以 rc 为准。
- close 只调用一次；失败保留原 substantive error，不能用清理错误覆盖原权限错误。
  输出不完整、非正常退出或无原记录时，未来监督器必须记 UNKNOWN。

退出码：0 = OBSERVED（仅取得该次事实），2 = REJECTED，3 = UNSUPPORTED，4 = IO_UNCERTAIN；
70/74 或信号退出表示报告内部/传输失败。所有 JSON 固定保持 admission_proven、real_e3_accepted、
production_supported 为 false。没有 PASS 或支持启用开关。

当前不核验已准入额度、mount/boot/namespace/generation、原执行或预算，也不证明查询原子性、
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

Q1 仍缺最小权限过滤/受监督装配、管理侧固定对象的真实 OS 准入和真实 fixture 结果；Q2 的认证通信、
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
  本模块没有重新启动的能力；**服务级持久防重和 UNKNOWN 占容仍属于尚未实现的 Q2 账本**。

`UnitObservation` 必须由未来的受信 manager adapter 获取，不能从客户端或 query JSON 反序列化。
当前逻辑测试直接构造它，所以不证明 systemd/cgroup 约束已经生效。`Decision` 只描述原观察；
成功缓存不是新的主机健康证明，也不授予资源释放或作业执行。admission_proven、real_e3_accepted、
production_supported 始终 false。

下一装配检查点须把以下行为实际连接起来：受保护配置/安装身份读取、准确 FS/namespace 绑定、
query unit **内部**的固定根打开与 FD 3 交付、管理权限/系统调用限制、真实 manager 观察及持久启动围栏。
不得先在 listener 打开可能阻塞的根，也不得假设普通 systemd-run 会传递任意继承 FD。
本检查点不生成可安装服务、不执行配额查询，不把逻辑组件完成转记为 Q1 或 E3 完成。

定向验证：`python3 -m unittest discover -s tests -p 'test_e3_quota_*.py' -v`。
其中真实匿名管道负例验证持有 writer 时读取立即返回；manager/成功 quota 分支均为 LOGIC_ONLY。
新增 native→monitor 联合测试使用已编译 C emitter 和独立 syscall shim，保持实机 quota 调用数为 0。
