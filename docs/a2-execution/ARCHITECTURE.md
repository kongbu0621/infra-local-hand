# A2 受限执行、MCP 与插件：架构

- Authority：Owner；状态：DRAFT / **Gate OPEN**；scope：`LH-A2-EXEC-MCP-v1`。
- 上游：[需求](REQUIREMENTS.md)；实现及验收：[实施方案](IMPLEMENTATION_PLAN.md)。
- 本文中的字段、工具名和目录结构是拟议契约，不宣称已经可调用。

## AX-A01 组件与信任边界（R02/R05/R08/R09）

| 组件 | 职责和边界 |
| --- | --- |
| 现有 GitHub Connector | 固定源码／设计读取及已有仓库操作；旧 v1 mailbox 使用原控制端和 Worker |
| A2 Plugin | 引导固定输入、原 id 查询、核对、证据取回；把返回内容当数据；不以技能文本授予权限 |
| MCP adapter | 验证每次请求的身份和 scope，严格解码契约，调用 job broker；不自己启动作业 |
| 本地维护 CLI | 经受保护本地 socket／OS 身份映射调用同一 broker API，无直执行、旁路或免鉴权模式 |
| 单一 job broker | 唯一准入、持久作业账本、部署核验、资源租约、runner 调度、核对和证据服务 |
| runner／主机进程管理器 | 在已委派的固定 cgroup 内执行固定程序，监督进程树、预算和停止；不暴露通用 systemctl |
| 部署管理入口 | 由已授权的主机管理通道首次安装账户、目录、服务与连接；不由新 MCP 自行 bootstrap |

第一版旧 v1 和新 job 协议没有自动桥接或失败回退。E1–E3 的可写根与旧 projects、state、
mailbox 和真实 NAS 完全隔离。E5 才决定旧服务与新服务是否并存；交叉资源须停旧或撤销旧权限。
新租约不能约束不认识它的旧 Worker，更不能排除管理员或其他 NAS 客户端写入。

## AX-A02 固定作业目录与来源（R01/R02/R06/R10）

第一版只包含下列六种作业。客户端传公开逻辑引用；broker 仅从已准入、摘要固定的私有 profile
解析路径、程序、存储配置和预算。没有任意 argv、shell、环境、URL、路径、代码或脚本字段。

| kind | 可变输入 | 固定执行内容和影响 |
| --- | --- | --- |
| `host.inspect` | 已准入 profile 引用 | 固定字段的 Python/SQLite、OS、文件系统和挂载观察；不扫描任意主机目录 |
| `ledger.prepare` | 已准入 source/build-cache 引用 | 独占新工作根中固定 checkout、build/runtime venv、wheel 与安装绑定；不升级工作副本 |
| `ledger.test.source` | 已完成 prepared artifact 引用 | 固定源码 unittest 和 compileall；显式测试环境；写本作业证据 |
| `ledger.test.resources` | prepared 引用；下表四项 suite 枚举之一 | A1 resources、response boundaries、A2 snapshot resources、semantic resources；逐项预算 |
| `ledger.test.installed_local` | prepared 引用 | 固定 A1 installed walkthrough 与 A2 local snapshot walkthrough，无真实 NAS |
| `ledger.nas.roundtrip` | prepared 与 storage 引用 | 固定 A2 NAS 程序；只对准入合成 archive 根发布、回读和恢复；有副作用、不可自动重跑 |

Ledger 固定输入 `6bd6acfbe5c35d581891eb87275e1173e17848fc`；验收脚本也属于受信执行内容。
`tools/acceptance/a2_nas_exercise.py` Git blob 为 `3dc8642cb3034db0e5451b5bf6dc6f4137f27f73`；
`tests/installed_snapshot_walkthrough.py` 为 `347e07b6c32042ddf10bebb0ddfab45c703c0c14`。
构建／运行解释器分离，固定源码树与脚本字节、构建依赖、wheel、完整安装 payload 和真实解释器。
`--source-commit` 是调用者传入声明，不是 Git 证明；`-I` 也不能证明外部验收脚本的来源。
prepared artifact 必须成功封存、属于当前准入且未被改写；下游再次校验，不接受任意 wheel。

固定调用模板如下；`build-python`、`runtime-python`、source、wheel 和各 parent 均由 broker
按准入映射生成 argv 元素，不经 shell 展开，也不是客户端可提交字符串。源码调用的 cwd 是受控源码副本，
安装态调用从该副本外运行并使用固定脚本绝对路径。

| 作业／suite | 固定参数模板 | 显式环境／判据 |
| --- | --- | --- |
| `ledger.test.source` | build-python `-m unittest discover -s tests -v`；随后 `-m compileall -q src tests tools/acceptance` | `PYTHONPATH=src`；普通 discovery 跳过的专项保留为未覆盖 |
| `a1_resources` | build-python `tests/test_resources.py -v` | `PYTHONPATH=src`；固定输入 8 项 |
| `a1_response_boundaries` | build-python `tests/test_response_boundaries.py -v` | `PYTHONPATH=src`；固定输入 1 项 |
| `a2_snapshot_resources` | build-python `-m unittest discover -s tests -p test_snapshot_resources.py -v` | `PYTHONPATH=src`、`A2_RESOURCE_TESTS=1`；固定输入 7 项 |
| `a2_semantic_resources` | build-python `-m unittest discover -s tests -p test_snapshot_semantic_resources.py -v` | 同上；固定输入 4 项，覆盖 12 个边界场景 |
| `ledger.test.installed_local` | runtime-python `-I tests/installed_walkthrough.py --repo source`；随后 `-I tests/installed_snapshot_walkthrough.py --scratch-parent job-parent --source-commit source-sha` | 不设 PYTHONPATH；第一程序路径同样解析为绝对路径 |
| `ledger.nas.roundtrip` | runtime-python `-I tools/acceptance/a2_nas_exercise.py --local-parent job-parent --storage-config admitted-config --source-commit source-sha --wheel admitted-wheel` | 不设 PYTHONPATH；四参数均后端绑定 |

两个 A1 专项须直接运行文件，不能用 discovery 代替其 `__main__` 启用条件。
A2 资源测试中的文件系统分类模拟必须保留 `LOGIC_ONLY` 标记，不因在 GX10 运行而变成真实 NAS 验收。
用例数只用于固定输入漏跑检查，不能替代用例结果和语义覆盖。

构建只用预先准入并逐件校验的本地输入缓存，执行时不联网下载或 pip 升级。缓存准备由管理流程完成。
Ledger 构建工具版本依其固定 runbook，不能套用 Local Hand 自身 `requirements-build.txt`。
只在对应固定测试环境显式设置 `PYTHONPATH=src` 和所需 `A2_RESOURCE_TESTS=1`；
不放宽旧 validation 的环境过滤。`TMPDIR`、`TMP`、`TEMP` 统一指向本 job 的受控临时根，
避免测试默认写到系统临时目录。默认干净环境，无 GitHub、SSH、OAuth、Tunnel 密钥。
运行账户仅可写专属工作／证据根与准入合成 NAS 根；固定源的 build/tests 本身是受信代码执行，
这不是任意恶意代码的沙箱。部署隔离与网络限制须由 OS/账户实际落实并验收。

## AX-A03 提交、身份与授权（R01/R03/R05/R08）

`lh-job-v1` 请求必含：`operation_id`（客户端生成 UUID）、`kind`、`profile_ref`、
`expected`（node、install UUID、deployment epoch、profile digest、policy digest、registry digest）、
类型对应的逻辑输入、请求有效期及 `request_digest`。所有字段固定 schema；拒绝多余字段。
拒绝重复 JSON key、非法 UTF-8／未配对 surrogate、浮点／NaN、超长／超深输入和不支持版本。
规范化规则固定为 UTF-8、键排序、无额外空白、不做 Unicode 归一化；只允许 schema 定义类型。
digest 对除自身外的完整规范请求计算 SHA-256；broker 独立重算。

认证主体不由请求指定。授权使用服务端映射的稳定 project/owner principal，不以短期 token 字节
作为身份。账本将 operation_id、request digest、principal 和解析后不可变执行计划 digest 绑定。
跨主体不得认领已有 id；同主体同 id 同 digest 返回原记录，异 digest 返回冲突；不覆盖。
请求过期只阻止首次准入；已有记录仍可按授权查询，过期或断线不取消正在运行的作业。
UI／MCP 请求 id 是传输身份，不能作为 operation_id。未确认提交回执必须用原 id 查询或原请求重送。

创建意图前及实际 spawn 前都核对预期部署、当前策略、固定输入、授权和资源租约。
排队期间变更策略或撤销准入则拒绝启动；运行中撤销阻止新读取／新作业，并按部署预设的受控停止策略处理，
不把 token 到期解释为业务撤销或成功取消。调用者不能选择 state root、提升 epoch 或设置自己的预算。
epoch 由受保护部署记录管理；安装 UUID 改变也不能绕开旧账本。管理员清空账本不属于正常恢复途径。

## AX-A04 账本、资源锁与崩溃（R03/R04/R05/R11）

唯一 broker 根位于准入的可靠本地文件系统，使用 SQLite 事务与 `synchronous=FULL`，
保留不可覆盖的作业身份和事件。数据库是状态权威；文件报告是可核验产物，不是另一套可冲突账本。
必须先持久接受记录和执行意图，再 spawn；持久化失败不产生新的执行。
数据库事务无法与进程启动或 NAS 提交构成原子事务，故意图后崩溃进入 UNKNOWN 核对，不能声称 exactly-once。
文件和数据库跨介质提交失败分别记录；SQLite/底层 FS 的实际持久化能力在 E5 验证。

受保护部署登记绑定唯一 broker authority ID、账本实例 ID、固定根和公共锁锚点；
broker 启动先校验登记并取得锚点锁，不能以第二 state root 另建 authority。
资源租约使用服务端准入的稳定资源 ID：目标节点/项目工作根、prepared artifact、storage/archive 根。
不同 profile、路径别名、bind 或 storage_ref 指向同一资源时映射同一 ID；不能证明独立则拒绝并发。
相关 job 串行化；测试产生独立工作副本，prepared 本体不可写。两个 adapter 或 CLI 无独立 executor。
租约超时只触发观察，不授权抢占；需证明原进程树已停止、原 epoch 已被围栏隔离且副作用已核对。
恢复时先扫描登记的 cgroup 和账本：孤儿、损坏、冲突、I/O 不明均阻止相关资源继续执行。
id 与防重放记录不随证据清理过期；本版不自动 GC 或删除失败现场。

三种状态独立呈现：生命周期（ACCEPTED/RUNNING/RECONCILE_REQUIRED/TERMINAL）、
执行结果（PENDING/SUCCEEDED/FAILED/CANCELLED/UNKNOWN）、证据（STAGING/SEALED/DURABILITY_UNKNOWN/FAILED）。
状态对象另列阶段、已知副作用、进程退出证据、缺失事实和事件序号。
UNKNOWN 不因查询超时转 FAILED；程序 exit 0 不自动把证据写成 SEALED。
结论更正追加新事件并引用原证据，不改写历史事实。

## AX-A05 进程、取消与核对（R02/R04/R05）

真实 Linux 部署采用已预先委派的 systemd/cgroup v2 作业边界；broker 无任意 unit 管理权限。
保存 boot ID、受控 cgroup/job unit、进程启动身份和作业关联，不单用可复用的 PID。
监督器独立于 MCP 连接；broker 异常退出仍由进程管理器控制子进程树，重启前核对存活任务。
每类作业固定 wall-time、终止宽限、CPU、RSS、进程数、临时磁盘、NAS 和日志上界；
预算值在 profile 中经准入冻结并纳入 digest，缺失／无限值拒绝准入。不能从 1 GiB 测试文件推断 RSS 上限。
stdout/stderr 独立排空并写私有文件；超限仍排空并执行受控停止，记录截断位置和丢弃计数，不把截断当完整证据。

cancel 是持久化取消请求；按进程归属 TERM → 限时 → KILL，并核对整个 cgroup 退出。
只有证明未 spawn 才可说明“未执行”；执行过但没有业务副作用仍属于已执行。
停止后的 NAS/文件事实另记，取消不是撤销。
reconcile 只读取原作业账本与归属路径、核对已发布对象，并保存核对证据；
允许在独立核对 scratch 做只读来源的内容校验，不重新发布、不执行原程序、不删除原作业文件。
调用 reconcile 需要独立权限；不能因它主要是读取就把它标成无写入。

## AX-A06 Ledger NAS 的具体恢复边界（R04/R06/R12）

固定 NAS 脚本只有 `--local-parent`、`--storage-config`、`--source-commit`、`--wheel`，
没有 `--run-id`、`--resume` 或分步恢复接口。broker 必须在启动前持久登记独占的每作业 local-parent；
脚本生成的随机 `a2-nas-*` 子目录／snapshot ID 要按原作业记录收集。
丢失 stdout 时只在该专属 parent 中核对唯一候选、OWNED.json、snapshot-reference 与内容摘要；
零个或多个候选、权限错误、归属不明均保持 UNKNOWN，不能猜 run-id 或用新 id 再跑。

真实执行前后由 broker 观察本地 FS、NAS 挂载 ID、类型、源/目标、archive 根与配置摘要。
固定库内部的 Directory 检查绑定其当次打开的 mount；脚本没有各阶段 hook，也没有把初始
endpoints 的 mount ID 作为所有后续独立进程的统一 fence。后台观察不能替代这个跨阶段边界。
E6 准入另须证明受保护的稳定挂载绑定／私有挂载命名空间等机制，或经 Ledger 新基线提供阶段 fence；
未证明时对应真实作业 BLOCKED。任何变化或不明均停，不得在 NAS 不可用时回落到底下本地目录。
路径检查不能提供跨主机原子锁；依赖持续独占、精确归属、最小账户权限与故障验收共同限制风险。
只在 snapshot 已关闭、NAS 完整发布并独立回读成功后，允许固定程序移除本轮本地合成 source/snapshot/temp。
操作者必须持续独占本轮目录；删除前与逐项删除按固定工具的实际检查核对。
发现新文件、内容替换、符号／硬链接、挂载越界或类型变化即停，可能已部分删除，须保存实际状态；
这不是抵抗任意并发管理员修改的原子删除保证。
不得删除 NAS 归档、旧项目、业务数据或失败现场。恢复使用独立进程，仅从 NAS 取数据，随后逐行/Blob 对账。

`ledger.nas.roundtrip` 成功只证明固定合成闭环；不自动覆盖 Ledger T01–T15。
真实挂载变化、真实发布失败和响应丢失等缺口，需要 E6 中固定、隔离、可恢复的故障用例。
若需要改动 Ledger 工具，先在其自身规则下取得准确新基线，重新准入；不把任意故障脚本塞入本契约。

## AX-A07 MCP 工具和二进制证据（R03/R04/R07/R08/R09）

| 工具 | 输入／输出要点 | 权限与提示 |
| --- | --- | --- |
| `lh_capabilities` | 支持版本、工具 schema digest、准入 kind、脱敏部署与可用预算 | `lh:inspect`；readOnly |
| `lh_job_submit` | 完整固定请求 → operation_id、digest、接受状态 | `lh:submit` + kind/resource grant；非 readOnly，按副作用保守声明 destructive |
| `lh_job_status` | operation_id → 三维状态、阶段、事件序号和缺口 | `lh:read` + 归属；readOnly |
| `lh_job_cancel` | operation_id、期望 request digest → 取消请求及实际结果 | `lh:cancel` + 归属；非 readOnly |
| `lh_job_reconcile` | operation_id、期望 request digest → 原作业核对记录 | `lh:reconcile` + 归属；非 readOnly |
| `lh_evidence_manifest` | operation_id、分页游标 → 已封存 artifact 清单与 seal | `lh:evidence` + 归属；readOnly |
| `lh_evidence_read_chunk` | artifact_id、offset、length、期望摘要 → base64、范围、块摘要、全件摘要 | `lh:evidence` + 归属；readOnly |

提示属性是客户端体验信息，授权始终由后端执行。统一错误区分 UNAUTHORIZED、CONFLICT、
STALE_DEPLOYMENT、UNSUPPORTED、RESOURCE_BUSY、NOT_SEALED、LIMIT_EXCEEDED、IO_UNCERTAIN；
不得把错误包装为成功空结果。异常文本脱敏，不在错误中返回私有路径或 token。
状态接口只给有界进度与计数；完整原始日志走封存产物，不把日志塞进模型上下文。

完整证据封存前须证明作业进程树、采集器和相关文件 writer 已停止，冻结账本事件序号与成员集合，
并核对文件读取前后稳定性。无法证明静止时保留 STAGING，或单独封存带 partial/cutoff 标签的诊断快照；
诊断快照不能冒充完整作业交付。核对作业新增记录另封新版本并引用原始事件，不修改旧 seal。
证据先写专属 staging，再计算逐件摘要／大小／ZIP 成员清单，fsync 文件与目录、原子 create-only 发布，
最后持久登记 seal。目录持久化不明或 DB 登记失败保持 DURABILITY_UNKNOWN，核对后才能开放读取。
不覆盖已存在 artifact，不因清理失败删除他人的并发文件。seal 不把自身放进自身摘要；
外部 seal 绑定 ZIP 字节摘要、内部 manifest 摘要、成员总数及冻结事件序号；ZIP 内部 manifest 排除自身并明确覆盖规则。
ZIP 成员禁止绝对路径、`..`、重复名和链接。只读打开须核对类型/归属/不可变摘要，路径不来自客户端。

manifest 默认每页 100 项；chunk 默认 64 KiB，最大 256 KiB，单次 JSON 响应上限 512 KiB。
这些是拟议应用边界，不是平台保证。客户端必须实际重组文件并验证总大小、全件 SHA-256、成员清单，
支持原 artifact/offset 重取；连接中断不重跑作业。授权撤销后逐块拒绝；artifact_id 不是 bearer secret。
E2 包含客户端文件重组与核验组件／流程，工具编排直接把 chunk 写入专属临时文件，不把 base64 逐块铺入模型上下文，
完成后交付实际文件链接。它只消费证据接口，不新增主机执行或绕过认证路径。
E4 必须通过至少 16 MiB 非高压缩率 ZIP 的当前客户端取回与中断续传；仅拿到哈希或截图不算交付。
若当前客户端无法可靠重组并交付文件，该项 BLOCKED，另行设计受认证文件通道；不偷偷改用公开 URL。
Tunnel 不被假设为任意二进制 HTTP 代理。本版不提供公共下载地址或任意预签名 URL 工具。

## AX-A08 MCP 连接与 Plugin 包（R08/R09/R10）

优先评估私有 MCP + Secure MCP Tunnel，由主机主动连接；备选是受认证的 HTTPS gateway。
前者的 Platform 组织权限、工作区关联、开发者模式、网络和 Tunnel 凭据归属要在 E4 逐项验证，
不能由订阅等级推定。授权服务也须实际可达，Tunnel 不自动替它提供网络入口。
HTTPS 备选须冻结 TLS、路由和准入范围，不能因 Tunnel 不可用就自动公开 GX10 服务。

远程用户认证采用受支持的 OAuth 授权码 + PKCE S256；每次调用验证 issuer、audience、有效期、
scope 和归属，精确 redirect URI。Tunnel 的机器凭据与用户授权分离；不以共享静态 key 冒充用户 OAuth。
发布 protected-resource metadata 与授权服务器 discovery，逐工具声明 `securitySchemes` 的 oauth2/scopes。
HTTP 未认证响应包含 401／`WWW-Authenticate`；工具级认证错误含 `_meta["mcp/www_authenticate"]`，
其 challenge 含标准 error/error_description。缺发现或挑战信息不能算当前客户端 OAuth 接入完成。
E1 冻结支持的注册方式（CIMD、DCR 或预定义 client），E4 才填写真实 issuer/client/redirect 值。
测试阶段使用独立测试 issuer 与合成主体，不能把测试绕过开关带入可部署包。
依赖选型和完整版本锁在 E1 的获准实现中冻结；接口语义变化须回到文档审查。

拟议 Plugin 使用根 `plugin.json`、`mcp.json`、`skills/`；OpenAI 特定映射放在
`extensions.com.openai`。包中提供 preflight、submit/observe、reconcile、evidence 四类工作流程，
技能不得在启动时自动投递。没有自动执行 hooks，不内嵌私有连接技术 ID、主机地址或凭据。
公开分发模板与私有已配置安装副本分别有摘要；精确远程连接映射由 E4 注册后生成。
技能版本、tool contract digest、后端兼容范围一起核验；不兼容禁止提交而保留旧接口查询路径。
仅私有安装与验收，不包含公共插件目录上架或自动安装推荐列表中的无关插件。

当前网页版与 GX10 本地 CLI/IDE 的连接配置分别验收：在 GX10 配置 stdio server 不会自动让
当前网页获得工具。E4 要在当前对话环境验证发现、认证、撤销、重连、七项接口和证据下载。
官方产品能力会变化，接入时复核；本方案是项目选择，不宣称当前账户已具备相关能力。

## AX-A09 交付来源及后续切换（R10/R11/R12）

新增 job 与 adapter 不静默改变现有八动作或核心依赖；MCP 可选依赖／独立环境单独冻结。
构建清单覆盖 worker/controller/jobs/adapter 与包外固定执行工具，Plugin 单独封存。
现有 `core_digest` 仅覆盖 `local_hand/*.py`，不能作为新执行链的完整证明。
安装记录绑定完整发布清单及真实启动入口；回退保留新 job 账本，即使旧版不能读取也不允许重放。
真实部署只选 E1–E3 产出的准确新候选 D，原 e6412a1 作为已复核前身；无需为八动作和新 jobs 连续切换两次。
S2 的全生产者冻结、旧任务迁移、单 writer、观察与回退要求仍见 [S2 架构](../s2/ARCHITECTURE.md)。

## 外部依据

核对日期 2026-09-22；外部文档不是本项目的权限授予。

- [当前 MCP 接入面](https://learn.chatgpt.com/docs/extend/mcp)
- [插件包结构](https://developers.openai.com/plugins/build/plugins)
- [MCP server 集成](https://developers.openai.com/plugins/build/mcp-server)
- [OAuth 鉴权](https://developers.openai.com/plugins/build/auth)
- [Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [ChatGPT 连接验收](https://developers.openai.com/plugins/deploy/connect-chatgpt)
- [Ledger A2 运行手册](https://github.com/kongbu0621/infra-artifact-ledger/blob/6707a1b521c9c4718674620e6c584656bd434e4c/docs/A2_RUNBOOK.md)
- [Ledger A2 验收矩阵](https://github.com/kongbu0621/infra-artifact-ledger/blob/6707a1b521c9c4718674620e6c584656bd434e4c/docs/a2/ACCEPTANCE.md)
