# Q2 第七批：同一操作三阶段与外层控制器监督

2026-09-25。延续 `LH-E3-QUOTA-HARNESS-v1` 已 CLOSED 的隔离开发范围；
不修改批准的 R/A/C、生产支持结论或历史 Q1 记录。
本文接续第六批 `E3_QUOTA_Q2_RESIDENT.md`，不把历史首阶段验证改写成整链验证。

## 本批入口

`tests/e3_host/q2_launcher.py` 保留 v1 首阶段合同，新增显式 v2 三阶段合同。
同一 ordinary resident、broker session、SQLite 操作和原总预算依次完成：
`preflight → business → evidence`。每阶段只能在前阶段六类原执行单元的 v2 CLOSED
已写入管理账本、broker 已持久确认且管理记录关闭之后继续。阶段切换不是新授权，也不重置总 deadline。

v2 顶层仍为 `source/resident/assembly/controller_envelope/setpriv/output/declarations/session`，
schema 为 `local-hand-q2-launcher/v2`，purpose 为 `ISOLATED_Q2_CHAIN`。
`resident` 采用 `local-hand-q2-resident/v2`，phases 必须准确为上述三个阶段。
`assembly` 为 `local-hand-q2-chain/v1`、`ISOLATED_Q2_THREE_PHASE`：

| 固定字段 | 约束 |
| --- | --- |
| `installation` | 相同 source、程序、容量权限、user namespace 和管理证据目录 |
| `original_budgets`、`broker_generation` | 同一原操作预算与原 broker generation |
| `journal` | 单一已存在、固定身份的永久管理账本目录 |
| `phases` | 准确三个阶段；各自固定 grant 骨架、output、service、peer |
| 每阶段 grant | 未来原 reservation 尚未发生；模板不能预造 budget、发行时间或 deadline |
| 每阶段 peer | 相同 ordinary parent、解释器及固定 runner；query/management parent 也固定 |

三阶段均属于 `job` 命名空间和同一 operation/record。business 复用原 allocation；
evidence 使用新且隔离的工作 quota 域，只按批准的绑定保留原 evidence store。
每阶段 output 分离。没有创建账户、挂载、quota、slice 或系统服务配置的功能。

## 单一容量与永久账本

启动 ordinary resident 前，预先计入全部三个管理阶段集合，以及 controller/resident 的资源、
每阶段管理控制输出、声明和结果文件。任何静态阶段管理时间不足，都在首次启动前拒绝。
发行时只复制该阶段实际原 preparation；各阶段必须保有相同原总预算起点、deadline、limits 和 digest。

`q2_journal` 的 v3 policy 在原 lock 下追加 hash-linked grant 注册记录。
新阶段只能接在准确原 CLOSED 前缀之后，其原 reservation 不得早于前驱关闭时间。
每阶段配置累计保留全部已有 grants/peers，旧配置字节不改写；扩展后旧 journal pin 不能重新执行。
容量始终累计占用，不把 CLOSED 当作可退款额度。
部分 cell、policy、配置或 fsync 失败均保留并阻止重用；不能通过新建单阶段账本绕过前驱。

## 原进程通道与执行计划

继承的 SEQPACKET、逐包 SCM_CREDENTIALS、pidfd/start_ticks、transport nonce 和原总 deadline 保持不变。
bridge v2 显式携带 phase，跨阶段序号单调；每阶段上限固定为 64 次收发、16 MiB、2048 包，
三阶段总上限为 192 次、48 MiB、6144 包。失败使原通道失效，不提供重连或重放。

resident 从原 SQLite 事件校验 preparation、preflight facts、CLOSED 与唯一冻结的 evidence snapshot。
共享 `broker.phase_plan` 纯转换供实际执行和声明使用；管理侧再次绑定不可变 base plan、
原 allocation/budget、同一操作、business quiescence、evidence 根与 store，再自行生成精确 argv 摘要。
任何阶段都不接受 ordinary peer 提供的任意命令。

实际 SQLite 模型发现证据事件超出旧 64 KiB bootstrap 载荷限制，且历史 `observed_at` 含小数。
`quota_payload` 用带版本前缀的 canonical JSON/zlib 编码保留原历史值；只有两个固定历史事件列表的
`observed_at` 允许有限小数。quota 权限仍使用原整数合同。解压上限 2 MiB，编码上限沿用
87,384 bytes，仍低于 Linux 单参数上限；同时核对原 temporary/reservation/evidence-root 写入预算。
旧格式可承载的 bootstrap 保持原字节。重复键、压缩炸弹、尾随字节、多重压缩流、非 canonical
编码、凭据字段和不合法环境仍拒绝。超过上限的证据保持失败并保留原记录。
bridge v2 对 ordinary proof 使用独立有界编码，仅保留真实执行阶段 `elapsed_seconds` 的有限小数；
budget、quota、身份与关闭时间仍为整数。传输前后原 proof 摘要相同，不靠删字段绕过校验。

## 外层控制器

新增入口：

```text
python -I -B tests/e3_host/q2_supervisor.py --fixture ABSOLUTE_PATH --sha256 SHA256
```

它要求**已经运行且独立监督的 root supervisor**，以及现有专用空 controller parent。
fixture 采用 `local-hand-q2-supervisor/v1`、`ISOLATED_Q2_SUPERVISION`，包含完整 nested launcher、
固定目标 controller 属性、自己的原监督 envelope、独立 output/declarations 和准确 source pins。
只有目标 InvocationID 与 cgroup dev/inode 可从本次实际启动补入；不能替换原预算、路径或计划。

一次 systemd-run 交付后保留原客户端和双输出流，目标同一 PID 执行 launcher 并等待原 StopUnit。
外层核对实际 InvocationID/PID/cgroup，独立停止准确目标，核对无待处理 Job、专用 parent 为空、
原客户端实际退出和双流 EOF，才可封存有限证据。目标结果不完整、过期、身份改变、输出缺失或持久化失败
均不能产生成功封存。supervisor 自身已有的外部监督费用与三阶段管理费用在同一容量内合算。
controller 完成标记先写入并 fsync，再以不覆盖目标的原子 rename 发布；轮询者看不到半段 JSON。
磁盘 `result.json` 在封存前只记录 `CLOSURE_OBSERVED_SEAL_PENDING`；成功还必须有单独的有效 seal。

## 结论边界与后续输入

- launcher v2 最多报告 `CHAIN_CLOSED`；supervisor 最多报告 `CONTROLLER_CLOSED`，
  scope 为 `TARGET_CONTROLLER_CLOSURE_ONLY`。
- supervisor 自己的原独立退出仍由其外部所有者负责，保留 `independent_supervisor_stop_required=true`。
- 所有结果固定 `q3_accepted=false`、`production_supported=false`；生产 `E3_SUPERVISION_UNVERIFIED` 不变。
- 不带显式 fixture 的入口只返回 `BLOCKED / EXPLICIT_PRIVATE_FIXTURE_REQUIRED`。
- 当前执行器没有 systemd、专用账户/委派和真实 project quota fixture。本地模型及文件/通道验证
  不等于 H01–H13 实机结果，也不能代替 Q3 总容量峰值、外层原退出及最终接纳。
- 实机接续需要交付上述准确私有 fixture、同一 clean source 安装及原监督者；不重放历史 Q1 请求或写入实验。

本批准确源码、测试数量、跳过项与发布树映射另见独立验证记录。
