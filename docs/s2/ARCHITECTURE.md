# GX10 S2 架构：部署身份、单 writer 与任务账本

- Authority：Owner；状态：DRAFT / **S2 Documentation Gate OPEN**。
- 已复核前身：`e6412a1a38e91906355fbd9ec21974993449d743`；新增实现候选另行固定和验证。
- 上游需求：[REQUIREMENTS.md](REQUIREMENTS.md)；实施映射：[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)。
- 本文描述 S2 约束与选型，不创建部署配置、迁移器或新执行能力。

## S2-A01 组成与权限边界

controller 通过已准入 mailbox 提交 Task；Worker 依据固定 profile 执行现有八动作，
将执行意图和结果持久化，再发布 Result。部署管理入口负责主机安装和服务生命周期，
不能由 Task 权限替代。私有 evidence 保存真实配置、运行账本和原始命令，公开仓库保存通用方案。
对应 S2-R01/R08/R09/R10。

旧通道能执行什么以真实回执和 allowlist 为准，见 [READINESS.md](READINESS.md)。
`node.status` 不提供完整 systemd、部署路径或 state 盘点；仓库读取不得跨到主机配置目录。
没有经准入的主机管理入口时保持阻塞，不通过写验证脚本扩大八动作语义。
新增 MCP、唯一作业后端与 Plugin 的具体方案见 [A2 架构](../a2-execution/ARCHITECTURE.md)。
旧 v1 和新 job 不桥接；新锁不能约束旧 Worker，真实部署须停止交叉资源 writer 或证明资源隔离。

## S2-A02 独立安装与来源绑定

新旧 checkout、build/runtime venv、安装目录、state 和 mailbox clone 独立；旧环境保留。
拟部署 wheel 从新作业 E1–E3 验收固定的完整实现提交 D 构建，使用 D 固定的构建依赖。
e6412a1 保留为已复核前身，不再作为默认最终切换输入；D 在实现完成前不得预填。
文档提交不冒充已测试实现，新增 jobs/adapter/Plugin 必须单独纳入完整来源和安装验证。
对应 S2-R01/R02/R05。

完整 wheel payload、构建元数据、安装记录和运行入口共同证明来源。
`provenance.py::core_digest` 只覆盖 `local_hand/*.py`，不能单独证明 controller 或 bootstrap。
`implementation_commit` 必须来自真实 build metadata，不能用环境变量覆盖为 d3a629d/b12e9c0。
profile digest 为原始文件字节摘要；重新格式化也须重新准入并同步 controller 预期。

`installation.py::verify_record` 精确核对 Python、profile、state/mailbox/projects/package 路径，
Git/SSH/key/known_hosts 绑定、install UUID、元数据及原 wheel 摘要。
新部署重新生成 create-only 安装记录；原 wheel 持续保留，不能复用旧安装记录或就地换包。
私有 manifest 冻结全部实际值；公开文档不填写机器专用路径和账户。

## S2-A03 单 writer 与状态转换

生命周期为：只读准备 → 独立 staging 验收 → 冻结生产者 → 排空并核对 → 停旧 →
封存并迁移 → 启新 → 只读健康观察 → 恢复准入投递。任一不确定状态先停止推进。
这是一条维护窗口内的单 writer 迁移，不依靠并行实例实现无停机。对应 S2-R03/R05/R07。

现有锁的覆盖范围必须如实保留：

| 代码位置 | 实际锁域 | S2 含义 |
| --- | --- | --- |
| `runtime_lock.py::worker_instance_lock` | 单一 state root | 独立 r1/r2 state 不互斥 |
| `act.py::_repository_write_lease`、`worker.py::execute_task` | 各 state 下的 write-leases | 新旧部署即便同一目标仓库也可能同时写入 |
| `controller.py::_controller_mailbox_lock` | 单一 controller clone | 不能冻结其他 clone、机器或自动化入口 |

Task v1 没有部署版本、install UUID、epoch 或有效期字段。
controller 的 expected provenance 在读取 Result 后核验，不能阻止错误版本先执行 Task。
因此必须实际冻结全部生产者、停止旧 Worker 及其子进程、核对自动重启来源，才可启动新实例。
后续若设计 mailbox/MCP 双入口，必须共用任务身份、执行租约及恢复账本，不能各自执行一次。

## S2-A04 全账本迁移与防重放

对应 S2-R04/R08。逻辑身份使用 `task_id + task_digest`，保留原 Task 和所有证据原始字节。
账本覆盖全部 receipts、outbox、conflicts、quarantine，以及 mailbox Task/Result/conflict 和
未跟踪控制文件；当前远端已不可见的历史 receipt 也不能丢弃。
旧 writer 停止前采集只算动态观察；停旧确认后才形成迁移用一致快照及文件清单。

`worker.py::process_once` 会扫描历史 Task：有 Result 时可导入 receipt，有 saved receipt 时可补发，
只有执行意图时生成 `outcome_unknown`，没有 Result/receipt/barrier 时将执行任务。
新 state 因此不得为空直接接入现役 mailbox，也不能仅检查 outbox 数量。
恢复保留旧 Result 原 provenance；不得为满足新 controller 预期而重新盖新版本来源。

迁移选择为：在独立新 state 中按核对清单导入兼容的防重放证据，保留旧完整快照。
不共用运行目录，不合并未知文件，不复制旧安装绑定。复制 lock 文件不等于取得运行锁。
真实旧 schema、完整账本和新旧读取兼容性尚待确认；验证应使用隔离副本。
发现不兼容、缺失、悬空链接、冲突或 I/O 不确定时阻塞迁移；需要转换器则先修订范围并完成 closure。

## S2-A05 回退保持执行事实

对应 S2-R06/R08。回退不倒退 mailbox 历史，也不以旧 state 快照覆盖新实例产生的事实。

| 回退时事实 | 可以采取的路径 | 禁止的快捷方式 |
| --- | --- | --- |
| 新实例从未执行 Task且已退出 | 核对该事实后恢复旧绑定、旧 state 和原 service 状态 | 仅凭启动失败推断没有执行 |
| 已执行 Task，结果和屏障完整 | 封存新账本与目标变化，验证旧版读取兼容并纳入防重放证据后恢复 | 丢弃新 receipt 或只启动旧服务 |
| 是否执行、进程退出或副作用不明 | 保持维护态，保留新旧证据，按原任务身份核对 | 换 task ID 重试、强行合并或声明回退成功 |

即便新实例仅执行只读健康 Task，也须保留其 receipt/Result 和来源记录。
旧版不能理解新屏障时不恢复消费；回退只有服务、绑定、账本和目标状态均核对后才算完成。

## S2-A06 实施入口与验收边界

现有 `bootstrap_linux.sh` 会直接变更 unit 并启动服务，无 staging-only；它使用 source-staging
和系统 Python，并固定运行 state 子目录，其内部回退还可能清理失败安装产物。
因此不将它作为本轮只读准备或 wheel+venv staging 入口，也不把三秒 active 检查当作 S2 验收。
S2 部署步骤须在相应 closure 后按私有 manifest 准备；若需新脚本，另行明确实现范围。

Worker 轮询错误会被记录后继续循环，`active` 不代表业务健康。
验收以准确来源的端到端只读结果、进程/重启状态、严格目录检查和连续观察共同判定。
不可用项目明确标记 UNAVAILABLE；S1 未查明的云端 outbox 异常不能在 S2 无复现时宣布归因。
A2 接纳设计及受限能力实现可在独立授权 scope 中与 S2 准备协调推进；
选定的新候选完成 E1–E3 与当前客户端 E4 后统一部署，再进入真实 A2；
S2 不等待真实 A2 验收先完成，也不把新能力的隔离测试写成 S2 closure。
真实 A2 作业只进入已验收且明确准入的部署；主机/NAS/证据交付能力各自记录实际状态。
