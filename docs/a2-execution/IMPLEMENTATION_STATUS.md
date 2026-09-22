# E1–E3 实现候选状态

本文件记录实现事实，不替代已批准的三层文档。整体状态为 **E1 尚有受监督启动准备及 NAS provider 代码缺口、E3 环境验收 BLOCKED**；
本轮是实现检查点，未达到 E1–E3 全部出口。准确提交与结果见 [首轮验证](E1_E3_VERIFICATION.md)、[后续复查](E1_E3_RECHECK.md)、[第二轮复核](E1_E3_RECHECK_2.md)及[第三轮复核](E1_E3_RECHECK_3.md)。批准基线 A 为
`79f73faedcd9cde4164b0d1625782dae27db6c2f`，规则 R 为
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，独立开工记录 C 为
`367632126c1930983a06b1854f63789448633148`。三份权威文档保留批准时原文。
Owner 决定及准确范围见 [开工决定](../governance/A2_EXEC_E1_E3_OWNER_DECISION.md)。

## 已实现的代码

| 边界 | 实现与可观察行为 |
| --- | --- |
| 协议与准入 | `local_hand_jobs.contract/policy/registry`；六类固定作业、七接口、严格原始 JSON、规范摘要、主体/目标/资源准入、有限预算及固定 Ledger 输入 |
| 持久后端 | `state/resources/broker`；单一 authority 锚、SQLite 意图和事件、资源屏障、稳定业务/核对 ID、精确取消、撤权和重启后原身份观察 |
| 进程监督 | `runner/ledger_jobs`；固定单元和分阶段状态、输出上界、独立封存 helper 已有实现；不能证明归属或退出时保留 UNKNOWN。启动前目录/配额/计划文件 I/O 尚未进入独立监督边界，生产入口明确拒绝启用 |
| 证据交付 | `evidence/evidence_client`；真实事件和停止证明、成员摘要、create-only ZIP/manifest/外 seal、fsync 后 DB 登记、有界读取和宿主直接文件续传 |
| MCP | `local_hand_mcp`；官方 SDK Streamable HTTP、成熟 JWT 验签、逐次权限检查、OAuth 发现和挑战；复用同一个 broker |
| 维护 CLI | `local-hand-jobs` 经私有 Unix socket 与 OS peer 映射调用同 broker；没有另一套直接执行路径 |
| Plugin | 独立 `plugins/local-hand-a2` 分发，四个工作流程与稳定 ID 客户端；公开 `mcpServers` 为空，等待 E4 私有配置 |

现有 Task v1 的八动作和 GitHub mailbox 保持原协议。新 job 不通过旧 v1 自动桥接或故障回退。
Connector 继续用于获准的 GitHub 访问，仓库文件中不存在实际客户端连接、凭据或实机运行配置。

## 当前不能宣称完成的门槛

| 项目 | 准确状态 |
| --- | --- |
| E1 受监督启动准备 | `_start` 尚在 broker 进程内进行可能阻塞的目录、配额及计划文件操作；后台线程不能证明有限停止。`SystemdManager.support()` 固定返回 `SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED`，即使其他主机条件齐备也拒绝生产启动。这是缺口的安全封堵，不是实现完成 |
| E3 真实独立进程监督 | 当前隔离宿主无已委派 systemd/cgroup，不能完成子孙进程、延迟启动、broker 崩溃及真实 quota 的集成验收。合成 manager 测试不替代此项，候选不可标记可部署 |
| 真实 Unix maintenance transport | 当前宿主拒绝 Unix socket 创建（EPERM），两项实际 transport 测试明确跳过。各准确候选的独立 Linux CI 结果见对应复核记录；未逐项输出的跳过原因不靠汇总数量推断，也不据此宣称完整生产传输验收。独立 TCP/SDK 测试不替代 Unix socket |
| NAS 运行时 | 网络归档硬配额适配器尚未实现。虽然固定四参数调用、前置证据依赖和挂载身份检查已有实现，`ledger.nas.roundtrip` 明确 `UNSUPPORTED`，Plugin 不提交该类型 |
| E4 | 真实当前客户端 OAuth、私有 MCP 连接及工具结果到可下载文件的宿主桥接未执行。16 MiB 合成证据下载属于 E2 客户端组件验证 |
| E5 / S2 | 未安装到 GX10、未停止或切换旧服务；S2 仍按独立 OPEN 基线管理 |
| E6 | 未执行真实 GX10 → NAS → GX10 A2，不把 Linux 合成文件或逻辑测试当 NAS 证据 |

本实现保留硬约束；没有跳过认证、配额、进程树证明或挂载检查的运行时开关。
受监督启动准备、NAS 配额适配与真实 cgroup 验收必须补齐，不能靠改一个配置布尔值宣称支持。
启动准备修复须先明确已有可写根的准入、分配和持久消费身份；不得借此开放 profile 父目录写权，
也不得把线程超时当作进程树退出证明。
宿主执行的账户、解释器、安装和准入配置须在服务加载前由受信部署侧保护；包摘要是漂移检测，
不能从已被任意篡改的解释器或正在执行的恶意进程中建立信任。

## 构建与安装身份

产品发布版本为 `0.2.0a1`。基础安装仍无第三方运行依赖，四包同版本分发；
MCP 使用独立可选 extra。已冻结 Linux x86_64 / CPython 3.12 的
[完整 wheel 哈希锁](../../requirements-mcp-linux-x86_64-py312.lock)和
[28 项依赖版本、wheel 摘要与许可记录](MCP_DEPENDENCIES.json)。
其他平台须另行解析、审查并冻结其哈希锁；依赖许可不改变本仓库未添加许可证的决定。

对受信取得的 wheel，基础安装和可选依赖安装分别执行：

```sh
python -m pip install --no-index --no-deps /absolute/path/infra_local_hand-0.2.0a1-py3-none-any.whl
python -m pip install --require-hashes -r requirements-mcp-linux-x86_64-py312.lock
```

以上是独立环境的安装说明，不授予连接或部署权限。基础安装调用 MCP 入口时若缺少 extra，
明确报告缺失。`local-hand-worker`、`local-hand-connect` 的使用仍见 [原使用说明](../USAGE.md)。

准入前可用 `python -m local_hand_jobs.deployment --service broker` 或 `--service mcp`
读取准确 source commit、完整四包 payload digest 和实际服务模块入口。私有 policy 必须固定这些值，
服务启动在创建 authority 锁、线程和监听前重新核验。旧 `core_digest` 保持 v1 含义，
不能替代新完整摘要。生成的 Python 缓存额外与同解释器新编译的源码匹配；缓存不参与稳定源码摘要。
旧 source-staging 仍可服务旧 Worker，不能据此启动新 job 服务。

从干净提交单独生成 Plugin：

```sh
python tools/build_plugin.py --output /absolute/new/output/local-hand-a2-plugin.zip
```

分发包含逐文件摘要、准确来源提交和冻结工具契约；输出 create-only，不能覆盖已有交付物。
Plugin 不隐式安装 Python 包，不创建真实 endpoint，不提供第二套认证或执行器。

## 验证解释

测试覆盖原有行为、严格输入、身份和策略变化、迟到回执、重复 ID、延迟启动、取消与恢复、
未知副作用屏障、事件封存、并发文件、持久化失败、分块撤权和真实文件续传。
真实模块的七接口合成集成只替换 OSManager/固定业务结果，授权、Registry、SQLite、
证据发布和客户端文件校验均使用实现本体。它不能证明真实 Ledger 程序已经受该 OS 监督执行。

CI 保留既有 Windows S1 测试；新 job/Plugin 的当前实现与测试范围为 Linux。
Linux CI 安装冻结 MCP 依赖并构建独立 Plugin。CI 源码/安装测试通过也不自动关闭上述实机门槛。
准确候选提交、最终测试数量和产物摘要由随后提交的验证记录固定，不把旧候选计数沿用给新实现。
