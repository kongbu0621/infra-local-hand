# A2 受限执行、MCP 与插件：实施和验收

- Authority：Owner；状态：DRAFT / **Gate OPEN**；日期：2026-09-22。
- 规则 R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，来源见根 `AGENTS.md`。
- scope：`LH-A2-EXEC-MCP-v1`；本次只申请 E1–E3 隔离开发、打包与验证。
- 文档基线 A 由本组三文档的实际提交完整 SHA 固定，随后记录于根 `AGENTS.md`；不预写自身 SHA。
- 三层依据：[需求](REQUIREMENTS.md)、[架构](ARCHITECTURE.md)、本文件。

## 当前动作与批准顺序

当前仅编写和发布方案，不新增可执行源文件、依赖或运行配置，不修改主机或投递新作业。
Owner“补齐一下”和“都设计进去”作为设计要求记录，不转换为尚不存在准确 A 的 implementation closure。
按仓库 Gate 保存 R → A → Owner 准确决定 B → 单独 closure 记录 C → 实现 D；
文档基线登记提交保持 OPEN，不是 C。批准文字须指明既有 A、R 和 E1–E3 范围。
本 scope 不关闭 S2，不重开或重复批准 Ledger 本体 A2 的已有 closure。

## 分阶段交付

| 阶段 | 交付与限制 | 出口 |
| --- | --- | --- |
| E1 固定契约与作业核心 | 独立 job schema/registry、SQLite 账本、同一 broker CLI、来源与预算检查、进程监督、封存与核对；冻结依赖和完整构建来源 | 原 id 防重放、未知不重跑、资源互斥和证据持久化故障测试通过 |
| E2 MCP 与 Plugin | 七项工具、逐请求认证、发现/挑战/PKCE 首次链接与再授权、固定 schema、结构化错误、分块传输与客户端文件重组核验、四类技能；loopback 与合成 issuer 测试 | adapter 不直接执行、CLI 无旁路、插件不自动投递、大小和权限边界通过 |
| E3 隔离发布候选 | 全源码／编译、wheel 干净安装、完整 payload 检查、Plugin 验证、固定 Ledger 程序的 fixture 集成和独立复审 | 准确候选 commit、wheel/插件摘要、验收矩阵、失败证据和部署候选说明 |
| E4 当前客户端私有接入 | 在已准入测试后端注册连接、OAuth、Tunnel 或 HTTPS，私有 Plugin 安装和完整文件取回 | 实际当前客户端的发现／授权／提交／查询／撤销／重连及 16 MiB ZIP 交付证据 |
| E5 GX10 与 S2 | 经真实主机管理入口安装候选，冻结私有 manifest、进程委派、现场预算和挂载观察；按 S2 迁移旧八动作并验收新 broker | 真实来源、单 writer、账本保留、受限操作、重启恢复、观察与回退证明 |
| E6 A2 实机验收 | 准入固定 Ledger、准备缓存、执行 GX10 本地及真实 NAS 合成闭环；补齐实际故障用例 | Ledger T01–T15 逐项证据与独立结论；余项明确 BLOCKED/UNVERIFIED |

E1–E3 closure 只允许前三行。E4–E6 是已设计的后续路线，不是自动授权；每行开工前冻结对应
私有输入、具体影响和准确授权，若增加实现或改变契约则另行修订文档并 closure。
E4 可以使用专门测试主机，无须先切换 GX10；E5 在 E4 验证入口与证据链后统一部署选定候选。
没有必要先升级一次仅含八动作的版本，再为新作业重复切换。E6 只进入已验收的部署。

## E1–E3 实现落点与依赖方向

下表仅规定未来获准实现的文件职责，不在 OPEN 阶段创建空模块或配置骨架。
采用同仓、同一 Python 发布版本、独立包加 `mcp` 可选 extra；不新建独立 GitHub 仓库或另一套执行器。

| 落点 | 职责与约束 |
| --- | --- |
| `tools/local_hand_jobs/contract.py`、`registry.py`、`policy.py` | 严格 schema/canonical、固定六种作业/前置证据、来源和授权；不依赖 MCP SDK |
| `tools/local_hand_jobs/broker.py`、`state.py`、`resources.py` | `local-hand-broker` 本地服务入口、唯一准入 API、SQLite 事务/事件、authority 锚点、容量/资源租约、原 id 去重 |
| `tools/local_hand_jobs/runner.py`、`ledger_jobs.py` | 启动/取消围栏、固定程序映射、进程管理器监督与 Ledger 证据判据；无任意 shell |
| `tools/local_hand_jobs/evidence.py`、`evidence_client.py` | 静止封存/有界读取；客户端以宿主回调重组文件，不获取宿主 token |
| `tools/local_hand_jobs/cli.py` | `local-hand-jobs` 维护入口，只用受保护本地 socket 调用同一 broker |
| `tools/local_hand_mcp/server.py`、`auth.py` | `local-hand-mcp` 服务入口、原始请求解码、官方 Python SDK Streamable HTTP、JWT 验签及进程内主体上下文；所有执行交给 broker |
| `plugins/local-hand-a2/` | 根 plugin.json/mcp.json、四类 skills 及版本/摘要说明；无真实连接映射、凭据或自动 hooks |
| `tests/test_local_hand_jobs_*.py`、`tests/test_local_hand_mcp_*.py`、`tests/test_local_hand_plugin_*.py` | V01–V12 的契约、崩溃/并发、认证、文件交付、打包与旧行为回归 |
| `pyproject.toml`、`setup.py`、构建/安装来源检查 | 显式纳入新包和 CLI，`mcp` extra 锁定 SDK/签名验证依赖；完整 payload 与 Plugin 摘要覆盖，旧 core digest 不代替全链 |

依赖方向固定为 MCP/CLI → broker → contract/registry/policy/state/resources/runner/evidence；
job 核心只用标准库，旧 worker/controller 不导入 MCP。local-hand-mcp 启动带 adapter 的同一 broker 服务，
两个服务入口受同一 authority 锁约束，不同时各起一个 executor。MCP adapter 与 broker 同一服务进程，
验证主体不通过可伪造的公开 JSON 字段传递；本地 CLI 使用 OS peer 映射。
E1 选择并锁定实际 SDK 与成熟 JWT 验签库的完整版本/摘要，记录许可；不自行实现密码学。
远端 v1 选择签名 JWT，连接注册方式在 E1 从受支持选项冻结；opaque token/introspection 不在首版实现内。

## E1–E3 的可执行边界

1. 新建独立工作树和 fixture 根，合成 node/install/epoch/profile/账号与测试 issuer。
   显式拒绝现役 projects/state/mailbox、真实 NAS 和主机配置路径；不使用真实凭据。
2. 将旧 Task v1 源码和既有验收保留为兼容基准。新 jobs 分离命名空间、包和账本；
   任何共有代码变动都补有针对性的旧行为回归，不以新接口替换旧用户入口。
3. 将架构 A02 的准确固定调用模板编入六类 job registry，冻结参数、显式环境、可写根、阶段及预算规则，建立严格 schema。
   Ledger 输入和工具 bytes 先校验；构建／测试不得继承控制端 token、Git/SSH 或代理凭据。
   后端执行 NAS 前置证据依赖，不接受客户端自报 PASS；临时目录真实绑定及回落路径均做负例验证。
4. E1 冻结选定 SDK 及全部传递依赖的版本和来源摘要；核心、MCP 与 Plugin 的打包关系单独验证。
   可按平台 marker 分别锁定，不用浮动 `latest`。新增依赖的许可证记录不改变本仓库许可证决策。
5. 数据库意图／spawn、退出／状态、证据 rename/fsync／seal 的每个交界模拟崩溃、I/O 失败和响应丢失。
   测试确认副作用未知时租约不释放给新作业，重启和原请求重投不再次执行。
6. 进程监督在隔离环境中验证子孙进程、PID 复用、日志满额和取消；若环境没有委派 cgroup，
   单元模拟只能记录为模拟，真实 cgroup 集成列为 E3 的未完成项，不得用普通进程组冒充等价 PASS。
   具备条件的隔离 Linux runner 应补齐此项后才标记“可部署候选”。
7. 源码编译、必要的全回归和外部干净安装覆盖真实 wheel，Plugin 从分发产物验证。
   固定 A2 工具的本地 fixture 集成可验证语义，模拟 NAS 不提供真实 NAS 证据。
8. 独立复审权限、并发／恢复、身份／证据和三层语义一致性；保存原始失败与修复后结果。
   不为凑旧计数重复无关测试；测试数量变化有对应覆盖说明。

## 接口、边界与故障验收矩阵

| ID | 需求 → 架构 | E1–E3 必测 | 后续真实验收 |
| --- | --- | --- | --- |
| AX-V01 | R01/R06/R10 → A02/A03/A09 | 伪来源/替换工具/prepared 漂移/错部署拒绝；NAS 缺必需证据、异候选/环境、更新失败或未决均拒绝，客户端不能自报 PASS | E5 全链来源；E6 真实先决证据绑定，不是只比 core |
| AX-V02 | R02/R08 → A01/A02/A03 | 未知字段/自由命令/路径拒绝；原始 JSON 重复 key、超深/Unicode/大整数/布尔冒整数负例；Python/JS 摘要向量；临时根失效/回落、全局队列/容量上限；CLI 同权限 | E5 账户/网络/临时目录隔离及预算实际生效 |
| AX-V03 | R03 → A03/A04 | 同 id 同 digest 去重、异内容冲突、跨主体拒绝、接受响应丢失、过期与重连；意图后崩溃不重放 | E4 客户端断线与 token 更新仍沿用原作业；E5 重启保留账本 |
| AX-V04 | R04 → A04/A05 | 排队取消、intent/spawn 间取消、延迟启动回执及重启；退出/状态交界、PID 复用、broker 死亡、cancel/完成竞争；UNKNOWN 不续跑 | E5 已排队启动撤销与实际 cgroup/监督器证据，停止不声明 NAS 回滚 |
| AX-V05 | R05/R11 → A01/A04/A09 | 两入口同账本；同一 authority 拒绝第二根；同资源不同引用/新 id 不能越过 UNKNOWN；租约过期/旧 epoch 不抢占、换安装不清身份 | E5 全部旧 writer 与生产者枚举；资源重叠先停旧 |
| AX-V06 | R06 → A02/A06 | NAS 不可用不回落本地；专属 parent、丢 stdout 定位、零/多候选 UNKNOWN；发现新增/替换/链接停删并记录部分状态 | E6 跨阶段稳定挂载绑定门槛、真实挂载/独立回读、只删合成本地副本、独立恢复及 SQL/Blob 核对 |
| AX-V07 | R07 → A04/A07 | writer 存活拒绝完整 seal；固定事件/成员、半写与并发不覆盖、fsync/DB 不明、ZIP 安全；上游自清理标记；封存峰值容量不足不删旧证据 | E4 真实 ZIP/seal/manifest 校验与保留范围说明 |
| AX-V08 | R02/R07/R09 → A05/A07/A08 | 分页/chunk/错偏移与摘要/断线；宿主回调→writer 不取 token；多作业及重复 reconcile 配额、日志截断、磁盘满停止 | E4 当前 Work 原始结果接桥、≥16 MiB ZIP 实际取回，无能力则 BLOCKED |
| AX-V09 | R08/R09 → A03/A07/A08 | 首链/再授权；伪签名/alg=none/错alg/kid/iss/aud/exp/nbf/不受信密钥/opaque token拒绝，密钥服务失败不降级；本地撤销/越权拒绝 | E4 用户授权、Tunnel/HTTPS、本地逐块撤销及 issuer 撤销实际传播界限 |
| AX-V10 | R09/R10 → A08/A09 | 插件版本/contract 不符阻止提交、无私有ID/secret/hooks、核心无 MCP 依赖也可安装 | E4 私有连接映射和当前客户端支持；公网目录上架不在验收内 |
| AX-V11 | R11 → A04/A09 | 旧 v1 行为保持、历史 Task 不因新 job 重放；双协议冻结/回退先停所有新入口/排队启动/进程树，保留两账本 | E5 S2 全账本迁移和新 job 独立屏障；旧版读不懂则阻塞相关资源 |
| AX-V12 | R12 → A06/A09 | fixture/模拟/真集成分列，FAILED/SKIP/UNKNOWN 不算 PASS，证据未保存不等于没副作用 | E6 Ledger T01–T15 分项结论、Python/SQLite/FS 实测、未完成故障项保留 |

新实现的编译仅在获准新增源码后进行。OPEN 期间允许对准确既有代码做隔离编译检查，结论单独记账，
不能作为尚未存在的新实现已经通过编译的证据。
本轮文档检查包括链接、准确 SHA、范围和 R→A→B→C→D 顺序、需求/架构/验收映射及公共披露检查。

## E4–E6 私有输入与阻塞项

| 输入 | 当前状态 | 必须在何时满足 |
| --- | --- | --- |
| 实际当前客户端开发者模式、插件安装面、组织 Tunnel Read/Manage/Use、工作区关联 | 未验证；订阅等级不作证明 | E4 注册前；Tunnel 不可用则评估受认证 HTTPS，不能擅自开放 |
| JWT issuer/JWKS/算法/时钟/缓存、client 注册/redirect/audience、主体/scope、本地与 issuer 撤销策略 | 尚未冻结 | E4；测试 issuer 不可用于真实准入；issuer 撤销时延须实测 |
| MCP/Tunnel/gateway 运行位置、网络、TLS、密钥保管、连接技术 ID | 尚未冻结 | E4；仅保存在私有 manifest，不写公共插件 |
| GX10 已授权且可调用的首次管理入口、运行账户、目录和进程委派 | 旧八动作不能提供；尚未找到替代入口 | E5 准备；可用本机已授权执行会话或受限管理通道，不能让 MCP 自装 |
| 全部旧服务/手工进程/生产者、状态账本、配置及回退点 | 仅完成旧通道四项只读核对 | E5 按 S2 READINESS 补齐、冻结、静止快照 |
| 本地 FS 与 NAS 真实挂载、端点、root、存储配置、账号最小权限、精确删除范围和跨阶段稳定绑定机制 | 未冻结；固定脚本不提供全阶段初始 mount fence | E5 观察、E6 准入；稳定绑定不能证明则 BLOCKED；不允许网络FS/tmpfs/overlay 冒充支持的本地 FS |
| 单 job 与 reconcile 预算、全局队列/并发/请求速率/留存上限、封存峰值和账本应急容量 | 未在真实主机定值 | E5；E1–E3 采用有限 fixture 预算，不外推性能或假定磁盘无限 |
| Ledger 固定源码与脚本、构建缓存、Python、wheel、installed payload | 准确源码已选；GX10 新安装未验证 | E6；Linux/Python 3.11 必验与 GX10 本次实测版本分别留证，历史 3.12 不预填为新值 |

私有 manifest 本身须有版本、摘要、采集时间、来源、准确 scope 和准入记录。
未知 live 值不阻塞 E1–E3 的合成契约实现，但对应行未满足就不能进入真实阶段。
只有实际必须由账户持有人完成的认证／授权步骤才交由 Owner；不让 Owner 转抄正常任务或日志。

## A2 出口与故障用例补齐

E6 先依固定 Ledger runbook 完成来源、构建、源码/编译、A1/A2 资源、纯安装态本地闭环，
再进入真实 NAS roundtrip。固定脚本没有续跑接口；失败先核对原 job，不自动重新提交。
对 T05 挂载变化、T06 发布失败、T08 响应丢失等真实缺口，实施前形成固定隔离用例、
影响根、故障触发/解除、观察点和独立判据；优先使用专属测试存储／隔离代理，不做全机断网或卸载。
六类首版 job 不暗含任意故障注入能力；缺少固定用例时该项 BLOCKED。
需要新增 kind 或修改 Ledger 工具时，按各自规则固定新增文档/源码和授权后再纳入 registry。

证据交付包括来源／安装、作业账本事件、原始命令与退出、stdout/stderr、挂载和文件归属、
prepared/wheel、报告、ZIP、manifest 和外部 seal；原始失败同样保留。
只有完整证据实际取回并校验后，才记录“已交付”；文件只在 GX10 生成不等于对话端已经收到。
本方案不把公共 GitHub 发布替代 NAS Git Authority 验收，也不把 A2 合成 PASS 扩大为生产切换。
