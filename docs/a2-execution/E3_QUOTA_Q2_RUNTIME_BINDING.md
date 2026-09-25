# Q2 第三批：管理运行器、认证通信与 broker 绑定

日期：2026-09-25。本批把保护配置、listener/admission/query 分工、完整多根观察、broker 原预算绑定和
bootstrap 回执管道一起实现。**这是隔离源码候选；Q2 整体验收和 Q3/Q4 尚未完成。**
生产 `E3_SUPERVISION_UNVERIFIED` 保留；没有宿主安装、创建账户、挂盘或重放 Q1 实验。

继承 `LH-E3-QUOTA-HARNESS-v1`：R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，
A `415327ebdcc251bb055da9931a7a88990f750b7a`，独立 C
`5a4ea852091db06549a876e42bbd5f95d5869d3b`。三份权威文档未改变。
第二批历史结果见[持久核心验证](E3_QUOTA_Q2_DURABLE_VERIFICATION.md)；本批准确提交、命令、结果和
发布映射见[准确验证与接续记录](E3_QUOTA_Q2_RUNTIME_VERIFICATION.md)。

## 本批行为

| 位置 | 实现与边界 |
| --- | --- |
| `q2_config.py` / `q2_entry.py` | 根所有者保护路径逐段 nofollow 读取；固定配置摘要、程序 ELF 摘要、模块字节和安装入口；导入器只执行固定模块，拒绝未固定模块与名称别名。配置包含有限原 grant 表、全部容量、journal 文件身份、peer 原命令摘要及固定 cgroup 父树。没有安装器或签发入口。 |
| `q2_listener.py` | 固定 8 KiB 请求、长度前缀、真实 EOF、连接数量和绝对接收窗口。外部 SCM_RIGHTS 拒绝；原接受 FD 仅转交预先认证的管理连接。派发之前即消耗该 listener 的一次机会，断连或交付不确定不重派；旧 socket 路径不删除重建。 |
| `q2_peer.py` | admission worker 独立读取 SO_PEERCRED、pidfd/start ticks、原 bootstrap 单元/cgroup、父树 dev/inode、执行文件和命令摘要、全部 UID/GID、零 capability、NoNewPrivileges、独立 user namespace 和 InvocationID。请求 JSON 不能自证身份。 |
| `q2_runtime.py` | 固定 listener、admission、query 单元参数；分开资源预算与能力，只有 query 带 SYS_ADMIN。停止宽限计入原运行上限，CPU 配额保留边界余量并核验实际 cgroup 值。多根 native 子进程串行留在同一 query 树中；原失败停止后续根，不另签 Q1 ticket。 |
| `quota_binding.py` / `broker.py` | 安装内部显式选择新版。先持久保存原 phase budget 与 root 分配；管理员只能绑定这份分配的 grant。后续 tick 复用原预算。helper 前校验回执，并在同一 SQLite 事务写入观察、bootstrap 完成及启动意图。reader 再对照不可变观察事件。公开 status 不泄露内部固定路径。 |
| `bootstrap.py` / `runner.py` | 新信封在根核验、marker/plan 创建、fsync 和最终截止检查后输出有界回执。runner 读取真实匿名管道 EOF，停止原单元后要求管道客户端成功退出；缺 EOF、截断、超时或身份漂移均不能启动 helper。helper/reader 屏蔽 observer endpoint，三个普通单元 capability 均为空。 |
| `budget.py` | 显式版本的 QUOTA_PREPARATION 可以解释已永久保留、尚未形成 EXECUTION_INTENT 的预算；不增加额度或退款。旧记录不隐式升级。 |

## 运行与恢复约束

管理配置为 `local-hand-quota-service/v1`。`service.request_id` 只激活已有有限表中的一个原请求。
独立 admission 单元在开始后先消费既有空 session 文件并 fsync；进程重启不重新获得该 session。
journal、保护配置、session、endpoint、程序和作业根必须按配置相互隔离。保护输入假定管理员不并发恶意替换。

listener 的磁盘读取与私有连接身份读取在接受普通请求前完成；接受后的循环只做有界内存解析、socket/select
及 FD 转交。目标根读取、quota syscall、journal/evidence fsync 和 manager 交互都在受监督 worker 中。
listener/admission 的启动、采集及最后停止仍须由独立受信 harness 管理；源码内部入口不是生产启用入口。

query 先确认专用父树为空及确定单元不存在，再启动固定名称。取得原 InvocationID 后持久记账；
任何不确定结果保留 UNKNOWN。原 query 单元停止、父树空、各 manager 客户端退出、stdout/stderr EOF
及 native 事实完整匹配共同决定 OBSERVED。有界原始运行输出保存在专用私有 evidence 目录；
receipt 的 proof digest 绑定这些字节。单独看到 exit 0 或 OBSERVED 不能证明完整业务链已结束。

broker 的 `quota_required` 仅是受信构造参数，没有新增 MCP/CLI 操作。绑定只在创建准备记录的同一 broker
进程 session 中生效。重启后保留原预算、分配和历史意图，拒绝自动续跑或重新签发。
取消不改用新单元：piped bootstrap 的原 InvocationID 未证明时不 retarget stop。

## 待闭合部分与下一批工作

1. 完成受信 harness 的 listener/admission 启停采集和完整 phase-close 证据装配。
   现有 phase-close 核心列出 bootstrap/helper/reader/query/collector 五项；新增独立 admission 的
   退出与管理父树空证明必须纳入受信装配，不能由普通请求补一个 true。
   本批没有自动调用 `close_phase`；未关闭 journal 状态继续阻止后继阶段。
2. 将 broker 已提交的准备记录、准确 bootstrap argv、有限 grant 表、保护配置、原容量和空 session
   组合为可审阅的固定 fixture 输入；有限运行时间必须覆盖实际装载、查询、采集和停止。
   不从旧 Q1 UNKNOWN/INCOMPLETE 对象中生成新可用分配，不新建宿主配额域。
3. 在明确提供的隔离 VM 中，一次验证跨 PrivateUsers 的真实认证 IPC、完整多根查询、三个普通执行单元、
   原预算资源限制、完整退出及保留记录。此后再做 Q4 故障/恢复组合；不把本机模型测试记成实机 PASS。

上述是已批准隔离开发内的待实现/待验证事项，不是新批准决定，也不是可以部署到 GX10 的声明。
历史 slot-001 UNKNOWN、slot-002 INCOMPLETE 与 slot-004 的限定成功分别保留。
