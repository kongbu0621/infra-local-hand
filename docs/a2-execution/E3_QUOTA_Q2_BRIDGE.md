# Q2 第五批：常驻桥接、单阶段驱动和外层采集

2026-09-25。沿用 `LH-E3-QUOTA-HARNESS-v1` 已 CLOSED 的隔离开发范围；
不改变批准的 R/A/C、三层文档、生产封堵或历史实机结果。

## 本批行为

- `quota_bridge.Channel` 使用既有继承的 AF_UNIX/SEQPACKET；每包检查实际
  SCM_CREDENTIALS 的 PID/UID/GID、保留 pidfd、boot、原 deadline、session、序号和分片偏移。
  不使用继承 socketpair 的创建者 SO_PEERCRED 来冒充实际发送者。
  单消息 2 MiB、分片 16 KiB、总传输 16 MiB、2048 包、每方向 64 消息、单次传输至多 2 秒。
  拒绝所有传入 FD；拒绝前关闭已收到的 FD。失败永久毒化当前通道，不重连或重传。
- `quota_bridge.Phase/serve_phase` 留在原 broker 进程，只开放预先固定的一个 operation/phase 的
  snapshot、bind、start、close；每个请求必须来自准确 root 管理进程。普通 MCP/CLI 不暴露这些动作。
  导出准备、观察、退出和关闭记录时逐项核对 SQLite 原事件；重启和快照损坏不补写。
- 管理侧 `q2_coordinator.Coordinator` 先比对原 preparation，再按
  listener → 私有 socket ready → admission → 外部 socket ready → 原管理 invocation → bind/start
  顺序推进。ready 只查受保护路径，不消耗一次性 socket 连接。
- 同时采集两个原管理客户端，并用有限次数 systemctl 观察先停止已经退出的原服务，再等 EOF。
  不能等 `RemainAfterExit` 服务的 `--pipe` 客户端先退出再去停止服务。
  管理原 deadline 与普通阶段/外层 deadline 分开，管理关闭后不再读取已关闭管道。
- 核对双方原 receipt、原普通三阶段证明和三个准确空 parent，组装六阶段 fence。
  **先持久化管理员 CLOSED，再向原 broker 发送 close 并核验 ACK**。
  ACK 丢失保留管理员关闭和普通预留；不声称双账本原子提交，不重放查询。
- `q2_capture.capture_existing` 只接管已启动且外部独立监督的原 Popen 双管道。
  保留实际 EOF、退出码、部分字节、摘要和关闭错误；总字节至多 32 KiB、窗口至多 120 秒。
  非零退出仍可构成“采集完整”，但从不据此推断服务停止或 Q3 接受。超时不杀客户端以伪造 EOF。

## 显式单阶段入口

`tests/e3_host/q2_phase_driver.py --fixture ABSOLUTE_PATH --sha256 SHA256`
仅用于已经存在的原常驻 broker 和已经绑定其原 preparation 的管理配置。
默认无 fixture 返回 `BLOCKED / EXPLICIT_PRIVATE_FIXTURE_REQUIRED`、退出 3。
即便返回 `PHASE_CLOSED`，仍固定 `q3_accepted=false`、`production_supported=false`。

保护的 fixture 严格包含 `schema=local-hand-q2-prepared-phase/v1`、`preflight`、`bridge`。
`preflight` 是上一批完整 v1 预检声明，源码 pins 必须包含本入口；继续核验源码、原配置、
账户、parent、原 deadline、空管理 record 和真实独立 controller。
`bridge` 严格包含 `fd,pid,uid,gid,start_ticks,session,boot_id,deadline_ns`。
这些来自受信 fixture 启动者，不能来自 ordinary 请求；start_ticks 在取得 pidfd 前后核验，
UID/GID 对应专用账户，通道 deadline 不得超过原外层 envelope。
两端须在发送首包前启用 SO_PASSCRED。普通端运行在原常驻 broker 的有限桥接 worker 中，
不能把旧 SQLite 状态加载进新 broker 后充当原会话。

原管理 record 仍使用已有、保护且空的 RunRecord；不创建账户、挂载、配额、slice、服务安装、
新 grant 或新账本。失败时保留两份账本和所有原记录；外层须独立观察/停止原身份。
原始 fixture、配置、stdout/stderr 和主机事实继续私有保存。

## 精确的剩余缺口

本入口是**已准备阶段的驱动**，不是从零可运行的完整 Q3 harness。
仍须实现并验证：

1. 独立启动并保留专用非 root broker 的 test-only composition，固定源码/wheel/安装载荷；
   分离真实 OS 准入与生产资格封堵，不能 monkeypatch support 或新增公开 support=true。
2. 在原 broker 创建 preparation 后，于原预算内从受保护固定模板封装对应管理 grant/config/journal；
   目前入口只消费已经准确匹配的原配置，不伪造未来 BOOTTIME 或刷新预算。
3. 将上述生命周期、继承 FD、外层 controller 监督/停止、create-only 原始证据保存，
   以及 preflight/business/evidence 各阶段连接成完整 fixture 启动器。
4. 准确私有 systemd/账户/委派/真实 quota fixture，H01–H05 后再做 H06–H13。

因此当前阻塞同时包含**源码装配尚未完成**和**实机 fixture 未交付当前执行器**。
不能表述为“代码全部完成，只差换一台虚拟机”。Q1 slot001 UNKNOWN、slot002 INCOMPLETE、
slot004 限定真实 EDQUOT 的历史结论保持；没有重新运行或清理这些对象。
