# E3 配额机制与真实 harness：变更架构

- Authority：Owner；状态：PROPOSED / Gate OPEN；scope：`LH-E3-QUOTA-HARNESS-v1`。
- 上游：[需求](REQUIREMENTS.md)；落地：[实施方案](IMPLEMENTATION_PLAN.md)。
- 继承原 A 的 broker authority、授权、租约、预留、三单元预算和 UNKNOWN 恢复边界。
  本文增加 AX-A01 的管理侧查询组件，并细化 AX-A05 的受监督配额事实取得；不改六类 job 或七接口。

## 1. 选定的候选路线及替代方案

推荐独立管理侧 quota observer。普通 bootstrap 不再承担需要 host capability 的 quota 查询，
但仍核对自己 namespace 内的准确根、project ID、继承和只读/可写边界。
observer 只观察管理侧固定的资源，不设置配额，也不能运行任务、安装软件或创建挂载。
这是一项需要批准和验证的设计，当前没有可运行实现。

| 路线 | 判断 |
| --- | --- |
| 给普通作业 root/CAP_SYS_ADMIN 或关闭 PrivateUsers/PrivateDevices | 改变原隔离边界，不采用 |
| 只改成 quotactl_fd | FD 可改善定位；固定 Linux 实现仍检查权限，不能独立解决问题 |
| 使用“预配置完成”标志或长期 quota 快照 | 缺少当前身份、变化约束和 enforcement 证明，不采用 |
| 改用 user quota 或容量有限的新存储类型 | 改变计费、身份或存储合同，本次不并行扩张 |
| 独立固定对象 observer | 增加明确受信组件；可保留普通作业隔离，作为本次待验证路线 |

## 2. 组件和权限

| 组件 | 所有权与职责 |
| --- | --- |
| 管理侧 fixture/provisioner | 预建固定本地 FS、有限 roots/projects、独立 evidence/控制容量、账户及服务；管理配置只允许受信管理员修改；不从 MCP 接受管理请求 |
| quota observer | 固定来源的本机管理服务；验证 peer、逻辑引用和部署代次；将每次观察交给准确身份的受监督查询进程；无 shell、任意路径、设置 quota 或自动重试入口 |
| 查询进程 | 仅取得该次固定 root/FS/project 的 kernel quota 事实；具有所需初始 user namespace 能力；独立有限 CPU/RSS/pids/日志/时间及保留容量 |
| bootstrap 客户端 | 原 bootstrap unit 内运行；校验 observer 身份、响应及当前 root 绑定；失败阻止计划发布和后续 helper |
| broker/manager | 持久记录观察引用与三单元交付；控制线程不做存储 syscall，不变成主机管理入口 |
| test-only harness | 以合成请求走同一 broker/manager 核心和原三单元链；保存真实 OS 观察、预算、故障和退出证据 |

三个作业单元仍是 bootstrap → helper → reader。管理侧观察进程是额外需要记账和监督的依赖，
不能隐去为三单元已经覆盖的成本。它不继承作业凭据，也不把 capability 或设备 FD 交给业务 helper。
第一版只支持明确验证过的隔离 Linux fixture；运行平台/内核/文件系统支持逐项记录。

## 3. 有界接口和事实绑定

本机 Unix socket 位于管理员拥有、调用者不可替换的父目录；服务和客户端双向核验 OS peer 身份。
客户端预先固定 endpoint、可信服务身份和部署摘要，不信任请求或响应自报身份。
socket 权限只准入专用 fixture 身份，helper/reader 的 namespace 不暴露该入口。
仅把目录设成只读不能阻止连接 Unix socket，须实际验证可见性/访问控制。

请求使用严格版本化 JSON，最大 8 KiB、深度 4，拒绝重复/额外 key。
仅含固定 `observe` 动作、request_id、authority/install/epoch、manifest digest、slot_ref/generation、
execution/phase、原 allocation digest 和绝对 deadline；精确类型/枚举在实现时随 schema 固定。
不接受路径、device、quota ID、期望成功值、额度覆盖、文件描述符或任意命令。
server 从管理员保护的 manifest 解析有限映射，核对 peer、允许 authority、代次、阶段及额度。
请求 deadline 只能缩短服务端最大值，不能提高额度。

同 request_id/绑定只取原记录；异绑定冲突。响应丢失或 query 退出不明，不重新发起 syscall。
当前阶段每个 allocation 只允许一份活动观察；新的明确请求须经当前准入且不能越过旧 UNKNOWN。
observer 保留自己的有界持久请求/进程记录，broker 账本引用其 receipt；二者无分布式原子事务承诺。
observer 先持久意图再交付查询；崩溃恢复只观察/停止原身份，不补投、不重建记录继续执行。

响应最大 32 KiB，包含请求绑定、观察起止 BOOTTIME/boot ID、准确 query invocation/cgroup、
固定源码/安装摘要、每个 root 的 host dev/inode/uid、FS 标识、project ID/继承、
hard bytes/计费类型/enforcement 观察、syscall 返回值/即时 errno、退出与缺失事实。
失败响应保留失败阶段，不用零 errno 或通用 UNSUPPORTED 冒充实测权限错误。
bootstrap 核对本地 root FD 与事前准入映射；不同 namespace 的 mount ID 不作数字相等比较。
需要建立同一底层 FS/root 的跨 namespace 绑定，不能仅比较 mount source 字符串。

## 4. 系统调用与变化约束

首个可行性检查在专属可丢弃 FS 上比较当前 generic 查询与 FD 定位；优先 FD 绑定，
但必须先确认准确平台 ABI/可用入口。任何兼容路径都必须单列并审阅，不能猜 syscall 编号或静默降级。
查询只允许 `Q_GETQUOTA/PRJQUOTA` 及明确列出的 enforcement/identity 观察；设置/启停 quota、
改变 project、任意扫描和任意 mount 操作不属于服务接口。query 的 syscall 过滤及 capability 集需实测。
若需要本机小型 ABI 适配器，作为独立管理侧产物固定编译器/headers/源码/二进制摘要，
不为作业 Python 包引入隐式编译或运行依赖。

Q_GETQUOTA 可能有 quota 元数据及冻结等待行为；影响范围包含所准入的专用 FS 元数据。
不能一面把挂载完全只读，一面预设该 syscall 一定成功；实际挂载模式和副作用须记录。
不承诺具有 CAP_SYS_ADMIN 的组件在失陷时仍被“只查询”接口约束；它是新增受信计算基。
因此仅在独立测试实例准入初版，host FS/网络/设备可达面必须实际核验，再讨论真实部署。

事实有效性依赖管理员保护的 generation 与稳定绑定：在任一相关 query、排队启动、三单元或
collector 未证实结束前，不改 mount/project/limit、不重新分配 root。计划变更须先关闭准入、
围栏旧代次并确认相关工作停止，再变更及重新取证。TTL 或一次成功查询不构成此保证。
同时验证普通作业无法更改 project/继承或写出计费域；必要的 OS 限制纳入准确 unit 属性和负例。
这个模型不抵抗并发恶意管理员；无法保证受信管理流程和无其他 writer 时拒绝准入。

## 5. 预算、阻塞、恢复与兼容

观察管理开销使用独立有限管理预算；quota 观察等待计入 bootstrap 原 deadline，
不能延长原三段 wall/CPU 分额。全局容量同时计入观察记录、原件、日志与封存峰值。
每次请求只派生一个已登记的固定 query unit，禁止无界 fork/thread 或挂起后反复补进程。
worker 卡在内核 I/O 时 listener/broker 仍须在冻结的控制响应界限内答复；
TERM/KILL/断开 socket 都不证明 query 已退出。UNKNOWN 继续占容量并阻止新观察和业务启动。
退出证明关联 boot、准确 unit/InvocationID、cgroup、queued activation 与全部采集器。

新的 receipt 与 allocation 绑定引入新版本内部合同；旧 v3 记录不补字段、不重读文件、
不重新观察以回写成功。实现前固定升级 schema 和测试向量；未知版本拒绝。
回退关闭新准入并保留 observer 与 broker 两份账本；未确认停止不能卸载管理服务或回收 FS。
旧版本不能理解新事实时保持阻塞，不能利用回退重新执行。

## 6. Harness 与支持声明

harness 不进入分发 wheel/Plugin，不提供公开绕过字段、环境变量或 `support=true` 开关。
将真实执行核心与“是否已完成生产资格认定”分开：普通入口保留固定封堵，
test-only 入口只使用准确私有 fixture、合成身份及真实资格检查调用同一核心。
测试准入是独立有限 scope；核心不依赖测试模块，不以 monkeypatch/mock 替换 OS 事实或持久围栏。
它能证明各机制实测结果，但不能自行授予生产权限或将不完整矩阵写成 E3 PASS。
宿主前置条件不足时停止；正常链通过后才进入有准确影响根和解除手段的故障场景。

## 固定官方依据与剩余假设

Linux `adc218676eef25575469234709c2d87185ca223a` 的
[quota.c](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/fs/quota/quota.c)
说明 project 查询权限、FD 入口仍走同一检查，以及 Q_GETQUOTA 的 write/thaw 路径。
systemd `70bae7648f2c18010187c9cf20093155eaa26029` 的
[systemd.exec](https://github.com/systemd/systemd/blob/70bae7648f2c18010187c9cf20093155eaa26029/man/systemd.exec.xml)
说明 user namespace capability、设备隔离及只读目录不阻止 Unix socket 通信。
[Linux man-pages 的 FD 接口说明](https://man7.org/linux/man-pages/man2/quotactl_fd.2.html)
用于定位方式核对，不替代固定目标 ABI。
这些是设计依据，不是目标主机 syscall 实测。实际 ABI、LSM、namespace、enforcement、
可控真实 I/O 故障及全部 H 场景仍待验证；无条件完整成功并非本提案的已知事实。
