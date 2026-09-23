# E1–E3 实现候选状态

本文件记录实现事实，不替代已批准的三层文档。整体状态为 **受监督启动准备和结果读取已有隔离实现、E1 整体未完成、E3 实机验收 BLOCKED、候选不可部署**；
NAS 已有固定只读查询与响应校验，但实际查询、写入身份和限定网络尚未准入。结果读取已迁入独立受监督进程，真实阻塞 I/O、恢复和取消仍待 E3 实测；本轮未达到 E1–E3 全部出口。
实现边界见 [受监督启动与结果读取](SUPERVISED_BOOTSTRAP.md)和 [NAS 配额准入](NAS_QUOTA_ADMISSION.md)。上一检查点准确源码 `4be98b8`、运行结果、保留的本地安装失败和产物身份见 [启动准备验证报告](E1_BOOTSTRAP_VERIFICATION.md)，不转记为新增实现的验证。
当前结果读取与 NAS 查询合同的准确源码、测试和证据摘要见 [本轮验证报告](E1_RESULT_READER_VERIFICATION.md)。
后续 E3 准备核查确认了两项实现缺口：真实宿主测试仍为占位，且当前 project-quota 查询与固定 upstream 隔离权限模型冲突；不能仅换到 systemd 主机就完成验收。事实、来源和待验证范围见 [E3 实现缺口](E3_IMPLEMENTATION_GAPS.md)，当前可执行的只读盘点及后续场景见 [宿主验收准备](E3_HOST_ACCEPTANCE_RUNBOOK.md)。
只读准备检查点的准确源码 `287f6b9`、18 项定向验证、准确 main CI 及私有证据摘要见 [准备验证报告](E3_PREPARATION_VERIFICATION.md)；云端 BLOCKED 不转记为目标宿主验收。
随后修复了只读探针对合法 nsfs root 的解析误判；准确源码 `88b78b6`、22 项探针验证、准确 main CI 与重测交接见 [nsfs 修复验证](E3_NSFS_REPAIR_VERIFICATION.md)。两份原始宿主 ZIP 已独立核验，固定源码的现场解析修复通过，详见 [GX10 重测证据核验](GX10_E3_NSFS_RETEST_VERIFICATION.md)；整体 readiness 仍为 INCOMPLETE。
最新一次性输入确认包已独立核验：六项专用 E3 输入为 **NOT_PREPARED**，原 13 组命令和 5 个非零退出码均保留，详见 [输入确认核验](GX10_E3_INPUT_CONFIRMATION_VERIFICATION.md)。现场盘点在此结束，不重复无目标探针。
下一步的 [quota/harness 三层变更方案](e3-quota-harness/REQUIREMENTS.md) 已获 Owner 批准，scope `LH-E3-QUOTA-HARNESS-v1` 在 A `415327ebdcc251bb055da9931a7a88990f750b7a` 下仅对隔离开发 CLOSED，见 [开工决定](../governance/E3_QUOTA_HARNESS_OWNER_DECISION.md)。当前登记提交只记录批准，未新增该实现或宿主配置；Q1 实测仍依赖专用 fixture。
历史准确提交与结果见 [首轮验证](E1_E3_VERIFICATION.md)、[后续复查](E1_E3_RECHECK.md)、[第二轮复核](E1_E3_RECHECK_2.md)、[第三轮复核](E1_E3_RECHECK_3.md)、[第四轮复核](E1_E3_RECHECK_4.md)、[第五轮复核](E1_E3_RECHECK_5.md)、[第六轮复核](E1_E3_RECHECK_6.md)、[第七轮复核](E1_E3_RECHECK_7.md)、[第八轮复核](E1_E3_RECHECK_8.md)、[第九轮复核](E1_E3_RECHECK_9.md)、[第十轮复核](E1_E3_RECHECK_10.md)及 [fd55 中断交付恢复](E1_E3_RECOVERY_FD55C07.md)。批准基线 A 为
`79f73faedcd9cde4164b0d1625782dae27db6c2f`，规则 R 为
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，独立开工记录 C 为
`367632126c1930983a06b1854f63789448633148`。三份权威文档保留批准时原文。
Owner 决定及准确范围见 [开工决定](../governance/A2_EXEC_E1_E3_OWNER_DECISION.md)。

## 已实现的代码

| 边界 | 实现与可观察行为 |
| --- | --- |
| 协议与准入 | `local_hand_jobs.contract/policy/registry`；六类固定作业、七接口、严格原始 JSON、规范摘要、主体/目标/资源准入、有限预算及固定 Ledger 输入 |
| 持久后端 | `state/resources/broker`；单一 authority 锚、SQLite 意图和事件、资源屏障、稳定业务/核对 ID、精确取消、撤权和重启后原身份观察 |
| 启动根分配 | `bootstrap_roots`；私有有限预建 slot 池、准确目录身份、与执行意图同事务的永久消费；preflight/business 仅在同一操作内共享原分配，其他阶段消费独立 slot，不开放 profile 父目录写权 |
| 进程监督 | `runner/bootstrap/result_reader/ledger_jobs`；新阶段依次使用 bootstrap、helper、result_reader 三个固定 unit，每次交付有独立持久意图和启动围栏；启动根身份、硬配额和计划发布在 bootstrap 内进行，helper 写入前再验根身份。结果文件由只读 reader 读取，observer 只收有界非阻塞管道；生产入口仍固定拒绝启用 |
| 证据交付 | `evidence/evidence_client`；真实事件和停止证明、成员摘要、create-only ZIP/manifest/外 seal、fsync 后 DB 登记、有界读取和宿主直接文件续传 |
| MCP | `local_hand_mcp`；官方 SDK Streamable HTTP、成熟 JWT 验签、逐次权限检查、OAuth 发现和挑战；复用同一个 broker |
| 维护 CLI | `local-hand-jobs` 经私有 Unix socket 与 OS peer 映射调用同 broker；没有另一套直接执行路径 |
| Plugin | 独立 `plugins/local-hand-a2` 分发，四个工作流程与稳定 ID 客户端；公开 `mcpServers` 为空，等待 E4 私有配置 |

现有 Task v1 的八动作和 GitHub mailbox 保持原协议。新 job 不通过旧 v1 自动桥接或故障回退。
Connector 继续用于获准的 GitHub 访问，仓库文件中不存在实际客户端连接、凭据或实机运行配置。

## 当前不能宣称完成的门槛

| 项目 | 准确状态 |
| --- | --- |
| E1 受监督执行 | 已有私有 root allocation、三个固定单元、受监督配额／计划发布与结果读取、三次 durable guard 和不重放恢复代码；真实 OS 约束、阻塞 I/O 及完整取消链尚未验收，不据此声明 E1 整体完成 |
| E3 真实独立进程监督 | `SystemdManager.support()` 固定包含 `E3_SUPERVISION_UNVERIFIED`，即使其他主机条件齐备也拒绝生产启动；没有配置布尔值可解除。现有实机用例仍为 SKIP/FAIL 占位，尚缺完整 host fixture/harness；委派、namespace、子孙进程、延迟启动、broker 崩溃、配额和阻塞 I/O 的真实验收未完成 |
| 本地 project quota | 固定 Linux/systemd 源码显示，当前 PRJQUOTA 查询的 host capability 要求与 `PrivateUsers=yes` 冲突，`PrivateDevices=yes` 还可能影响设备定位；目标内核、准确失败点与 errno 待实测。现实现未保存 quotactl errno。预建配额不能单独消除此实现障碍；不为普通作业提权或放宽隔离。独立管理侧观察机制已获隔离开发批准，尚未实施或实机验收 |
| E3 只读准备 | 独立探针的 nsfs 修复已完成现场重测；原始 mountinfo 未归档，不声称云端重放。随后一次性输入确认的 44 成员 ZIP 已独立核验，六项专用账户/manager/slice/cgroup/隔离/委派输入为 NOT_PREPARED；slots/quota/store 仍 UNVERIFIED。只读库存阶段结束，整体 E3 仍未验收 |
| helper 结果读取 | 新 v3 将文件读取迁入独立只读 reader unit，父端仅处理有界匿名管道；旧布局不补授 reader 预算、不回退直接读盘。重启丢失管道不重读，结果保留 UNKNOWN；原三 unit 退出可独立记录，允许新显式 reconcile，旧 local CLI 停止仍不冒充已证明。真实 E3 尚未验收 |
| 真实 Unix maintenance transport | 宿主限制和各准确候选结果按对应验证报告分别记账；独立 TCP/SDK 测试不替代 Unix socket |
| NAS 运行时 | `nas_quota` 已有固定 CIFS 只读请求、准确响应与身份／时间校验，结果始终 LOGIC_ONLY；实际 collector、写入身份、凭据及限定网络未准入。`ledger.nas.roundtrip` 和真实查询仍明确 UNSUPPORTED，Plugin 不提交该类型。现场事实按 [私有输入工作表](NAS_PRIVATE_INPUT_WORKSHEET.md) 收集，填写不启用查询 |
| E4 | 真实当前客户端 OAuth、私有 MCP 连接及工具结果到可下载文件的宿主桥接未执行。16 MiB 合成证据下载属于 E2 客户端组件验证 |
| E5 / S2 | 未安装到 GX10、未停止或切换旧服务；S2 仍按独立 OPEN 基线管理 |
| E6 | 未执行真实 GX10 → NAS → GX10 A2，不把 Linux 合成文件或逻辑测试当 NAS 证据 |

本实现保留硬约束；没有跳过认证、配额、进程树证明或挂载检查的运行时开关。
本地 quota 查询机制与真实 host harness 须先补齐，再完成启动准备、结果读取和真实 cgroup 验收；NAS 配额适配仍单列未完成，不能靠改一个配置布尔值宣称支持。
私有 root slot 由受信部署侧预先创建、绑定账户与硬配额；broker 只消费已声明身份，不能自动扩池、回收或重新分配已用 slot。
Bootstrap、helper 与 result_reader 共享原阶段绝对截止时间；新 v3 的 CPU 三分固定且不退款，旧 v2 原分额不改。不会因排队、切换子阶段或重启而续额。
不能把线程超时当作进程树退出证明，也不能把新增启动准备隔离解释成所有存储观察已具备有限停止保证。
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
各验证报告分别绑定准确候选提交、最终测试数量、产物摘要及失败记录，不把旧候选计数沿用给新实现。
