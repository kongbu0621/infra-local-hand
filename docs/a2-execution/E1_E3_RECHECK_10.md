# 第十轮实现复核：读取完整性、失效准入与跨阶段预算补修

本轮修复确认的既有缺陷，并完成准确候选的源码、构建安装及 CI 验证。**部署状态仍为 `E1_INCOMPLETE_E3_BLOCKED_NOT_DEPLOYABLE`：E1 受监督启动准备和 NAS 硬配额适配未完成，E3 真实 cgroup 验收仍阻塞。**

## 准确身份与范围

- 输入 main：`dd4ebc886f8071c6acb465201f3bde6df17b6e18`。
- 首次候选及预算补修基线：`d71934a19a47931c208a18099f4d599005965796`。最终修复源码：`e349a83fde7ee1901d966303aba135b171d3d18d`；Git tree：`0852fa0c121928a2541e4b69eb54f21826b0298b`。
- 源码/测试变更 22 个路径，新增 37 个公开回归方法，其中预算补修涉及 6 个路径、新增 17 个方法。方法包含子场景；专项、交叉探针与全量覆盖重叠，不相加。
- 范围为既有 S1 维护及 E1–E3 隔离实现验证；未操作现役 GX10、真实 NAS、私有客户端或服务切换。
- R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、A `79f73faedcd9cde4164b0d1625782dae27db6c2f`、B 事件 `LH-A2-EXEC-MCP-E1-E3-CLOSURE-20260922-01`、C `367632126c1930983a06b1854f63789448633148` 保持原链。直接读取固定 R，三份权威文档与 A 字节一致，C 仅治理登记，D 以 C 为祖先。Owner 决定核验为保留副本连续性，不冒充独立平台消息认证。
- 未改变依赖、固定作业清单、七工具契约、Task v1 八动作、许可证决定或阶段授权；生产不支持保护保留。

## 首次候选与补修顺序

首次候选 `d71934a19a47931c208a18099f4d599005965796` 已完成本地 723 PASS / 3 SKIP、Linux CI 725 PASS / 1 SKIP，以及 Windows S1 CI 211 PASS / 132 SKIP。随后的源码与已批准架构复核发现：同一操作的各 helper 阶段仍重新获得完整预算。这些首次候选的通过事实保留，但不能据此关闭新发现；封存已暂停，随后补修并对最终准确源码重新完成验证。下方验证表仅列最终候选，不将首次候选数据转记到新源码。

## 确认的问题与修复

| 边界 | 原始反例与修复后行为 |
| --- | --- |
| S1 与 Ledger 输入读取 | 提前 EOF 可把合法 JSON 前缀伪装为完整文件；同尺寸改写也可能返回未经验证的快照。两者均核对实际读取长度和打开描述符前后元数据；Ledger 继续额外核对目录项绑定。S1 原有 limit+1 超限行为不变，不完整权威输入仍按 FileReadUnavailable 表达不确定。Ledger 读取清理只关闭一次，并保留先发生的读取错误 |
| 持久账本 JSON | 重复键、NaN/Infinity、指数溢出可被宽松解析；解码递归异常可能逃逸。现在拒绝歧义与非有限数值，将解码失败记为 IO_UNCERTAIN 并关闭不健康账本准入；合法有限浮点时间戳保留，无数据库迁移 |
| helper 日志与时间预算 | 解释器探针和业务采集原先可能各自用满一次日志预算；输入检查耗尽时限后仍可能以新的额度启动探针。现在解释器与业务共享 helper 剩余日志及墙钟预算，启动前拒绝已耗尽预算，成功和失败探针的输出、截断与丢弃计数均进入阶段证据 |
| MCP 关闭准入 | 已在真实线程池排队的控制调用可能在 adapter lifespan 退出后才到达 broker。现在在 SDK teardown 前及启动/生命周期失败时关闭准入，入口与排队 dispatch 均检查；已送达 broker 的调用不因传输关闭而被当作取消 |
| 服务端证据清理 | 嵌套目录遍历的 close 失败可能覆盖原有冲突、预算或读取错误。现在通过既有单次关闭辅助函数保留原始异常，仍尝试关闭每层描述符。此前公开 seal 已包装错误；此项不宣称发现公开原始异常泄漏 |
| 客户端下载身份 | 下载身份既可能缺失或为空，也可能因未限制字符串类型而出现 Python true/1/1.0 等值别名；两类问题均可能接受不合格的身份绑定。现在在 callback 与 writer 准备前核对非空字符串身份，固定其值再比较 seal；不改变 broker 的 UUID 协议 |
| Plugin 准入与恢复 | 失败或尚未完成的 preflight 曾不能阻断新的 reconcile；工具实际返回 STALE_DEPLOYMENT 后也未撤销旧缓存。现在新 reconcile 身份预留和下发要求完整成功的 preflight，结构化或抛出的 STALE 错误统一清空准入缓存。原持久身份重取、查询与精确取消保持可用，重新核验后沿原 id 重试 |
| 安装 wheel 完整性 | 声明长度可掩盖 STORED/DEFLATE 的额外展开、截断结束及尾随压缩数据。现在在同一 retained handle 上有界验证完整流，随后逐块检查全部成员，包括可选 dist-info 的头部/CRC/内容；保留既有压缩与展开预算，解码前拒绝加密及不支持的压缩方法，保留原安装错误语义 |

前八组边界由首次候选的七个分工确认并修复，使用合成身份、真实隔离文件/解释器、受控错误注入和本地 SDK/线程池验证。Plugin 首次修复后，独立交叉检查又确认实际 STALE 回包未使缓存失效；准确输入和中间候选均复现，原稿与失败保留后才完成修复。这些证据不等于真实故障磁盘、GX10、NAS 或生产关闭验收。

## 跨阶段预算补修

操作预算现在绑定原准入计划、namespace/id、execution_id 和固定阶段；分额与执行意图在同一事务持久化。job 为 preflight、business、evidence 最多三个阶段预留固定份额；每个 reconcile_id 有独立总预算，为观察与证据两个阶段分额。wall/CPU/log 按整数向下分配，份额总和不超过原 profile；没有可信全程实际用量，因此不退款、不续额。同一身份重试、确认丢失及恢复不会重建预算；显式新 reconcile 身份才按既有授权申请独立观察。RSS、进程数及保留/共存磁盘峰值继续沿用既有峰值约束，不按累计 CPU 的方式机械分摊。

首个辅助意图保存同一 boot 的 CLOCK_BOOTTIME 绝对截止时间，阶段间隙也消耗它。新阶段、最后管理器投递和 helper 入口重新核对；延迟激活、重连及恢复不能获得新的操作时窗。helper 启动子程序前与排空期间继续核对截止时间。终止宽限包含在每阶段 wall 份额之内，CPUQuota 向下取整并按包含宽限的完整份额配置；无法表示的过小速率拒绝。

份额不足一个可执行单位，或 wall 份额不足以保留完整终止宽限时拒绝后续 helper，不向上补额。预算收紧意味着业务阶段不能借用预检或封存未用完的份额，过小 profile 可能在开始前被拒绝。已执行但没有可信预算的旧记录不补满；时钟不可用时新启动关闭，但历史 status/cancel 保留。恢复时无可信 grant 就放弃不可用 deadline，只沿已核对的 boot/unit/path/cgroup/invocation 身份观察和受控停止，不重新执行。即使 grant 有效，保留的阶段 deadline 类型或范围损坏时也只丢弃不可信计时；身份检查保持，观察时立即请求受控停止，不分配新的运行时窗。证据 helper 因预算拒绝时，已观察的 business_outcome 与 business_exit_proof 保留，不能伪称 SEALED。

独立 broker 链的七个反例覆盖 job/reconcile 分额、阶段间隙、封存 helper 启动前预算耗尽仍保留业务结果、旧执行缺额、重新打开账本与换 boot，准确首次候选七项均失败，修复后同脚本七项通过。broker 作者的三项反例和 runner 作者的三项反例分别保留原始失败与同脚本修复后结果；runner 另核对准备后最后投递、过期 helper 入口和包含终止宽限的配置。专项与公开回归、全量覆盖重叠，不汇总相加。另保留中间候选的恢复反例：缺失 grant 配合旧 deadline 曾使本来可归属的 unit 无法重新附着受控停止；修正后原独立探针通过。

补修中间候选还暴露完成出口语义问题：已核验业务/观察完成后，最后 deadline/clock 检查失败曾覆盖成功事实。现在将这次辅助失败单列，helper 非零退出，但保留已核验的 business/reconcile outcome、effects 和结果；preflight 或 evidence 未闭环则仍失败，不借成功输入事实启动业务，也不注册 SEALED。相关中间红例与修复后结果保留。

**CPU 结论限于 grant 守恒及条件化配置核对。** 这里没有可信累计 cgroup CPU 计量，周期配额和内核调度有粒度，LimitCPU 是单进程限制；不能把分额和配置算术称为完整进程树的物理 CPU 上限验收。绝对截止检查也不能单独中断阻塞存储调用或补齐尚未实现的受监督启动准备。

## 准确候选验证

| 环境 | 源码 PASS | SKIP | 说明 |
| --- | ---: | ---: | --- |
| 本地 Linux | 740 | 3 | 单次完整源码；740 passed, 3 skipped in 344.75s (0:05:44)；前后 HEAD/tree 与干净状态一致 |
| Linux CI | 742 | 1 | 源码 352.01 秒；job 638.0/900 秒 |
| Windows CI（S1） | 211 | 132 | 源码 352.76 秒；job 416.0/900 秒 |

本地跳过原因：

- 1 项：UNSUPPORTED: host policy prohibits AF_UNIX sockets; synthetic transport tests are separate
- 1 项：UNSUPPORTED: this host forbids the real Unix maintenance socket
- 1 项：UNSUPPORTED real systemd/cgroup integration: SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED; PID 1 is not systemd; no predelegated manager admission; dedicated non-root account is required

CI 为 [run 35821923399](https://github.com/kongbu0621/infra-local-hand/actions/runs/35821923399)，push / main / attempt 1，3 个 job 均 success。完整 decoded logs、步骤与 artifact metadata 留存；**未下载 CI artifact ZIP 二进制**。Windows workflow 排除 A2 jobs/MCP/Plugin，不能据此宣称 Windows A2 通过。CI 跳过位置/原因按原始摘要保留，不把 skip group 当成每个测试节点都已逐项列明。

Linux CI 的 2 项真实 Unix socket 测试结论为 **依据完整套件证据推定通过**：固定源码中可定位这些测试，按准确工作流纳入常规 Linux 全量收集范围；套件成功且完整跳过清单不含这些节点。`pytest -q` 未逐一输出已通过节点 ID，因此这不是独立的逐节点 PASS 日志；也不证明 GX10 实机部署。

| 已核对的测试节点 | 结论口径 |
| --- | --- |
| `tests/test_local_hand_jobs_cli.py::CliTests::test_real_unix_socket_roundtrip_when_host_permits` | `PASS_INFERRED_FROM_COMPLETE_LINUX_SUITE` |
| `tests/test_local_hand_jobs_integration.py::JobIntegrationTests::test_real_maintenance_transport_shares_broker_and_original_identity` | `PASS_INFERRED_FROM_COMPLETE_LINUX_SUITE` |

- 本地 wheel 安装态：94 项检查、292 条命令、584 份 stdout/stderr 通过；命令包含预期非零的拒绝用例，不表示全部退出码均为 0。
- 安装态 MCP：外部复制测试在 `-I` 下运行，37 PASS / 0 SKIP。
- CI 安装态：Linux 94 项检查 / 292 条命令；Windows S1 10 项检查 / 10 条命令。
- 新 build worktree、新 base/MCP venv；使用已存在且准确固定的 9 项构建工具版本，构建前后核对。未新安装构建工具链；缓存 MCP wheel 匹配冻结锁文件后离线安装。
- Python `-W error` 编译、Linux shell 语法、pip check、Plugin 构建与 wheel 安装通过；40 个 payload 文件匹配 Git blobs，13 个 Plugin 成员。完整 payload 摘要 `ecb4a044882ad8a6d6c61ce0d214feaa2ed0c229327a318442179bb97f625221`。
- Plugin 仍为 `UNCONFIGURED_E4_REQUIRED`，公开 `mcpServers` 为空；没有据此建立真实连接或扩大授权。

| 产物 | 字节 | SHA-256 |
| --- | ---: | --- |
| `infra_local_hand-0.2.0a1-py3-none-any.whl` | 200608 | `3e9b97c511a2d446816645c775af8c36369f586c622cd89fc9672a80df85a2a6` |
| `local-hand-a2-plugin-0.1.0.zip` | 19219 | `56156642be0f441c506809257c67d7e573da715fd0705ef2de71cf5623a7e163` |

## 复审关系与失败保留

各专项及跨模块审查保留原始源码、红例、修复后验证、命令与日志。源码总审结论为 `PASS_WITH_LIMITS`。**作者关系如实披露：最终补修源码总审者是首次候选 MCP 关闭补丁的作者，该旧补丁已有独立交叉复审；总审者未编写本次 broker、runner 或预算模块。**原七分工报告只绑定首次候选字节；被预算补修替换的路径单独绑定新作者报告、独立探针与最终源码验证。预算算术和恢复接口另由未编写本次补修的审查者检查，早期各分工作者关系继续保留；不能称全部历史路径均由完全无作者关系的审计者验收。最终完整证据报告还需在本预封存报告生成后接受独立审计，审计通过后才封存。

RESULTS 汇总快照含 195 条已完成命令记录，其中 27 条为非零历史记录。快照先于自身记录和后续审计/报告；完整 ZIP 的成员、命令与日志以最终 MANIFEST 及 seal 另列。非零记录包括产品红例、中间修复遗漏及验证工具问题，不计作最终通过；不同分工和全量测试计数不相加。

中间产品修复也如实保留：wheel 的初版 RuntimeError 包装同时捕获了既有 LocalHandError，导致原拒绝信息保真回归失败；现先保留原安装错误，再处理归档异常，相关定向检查重新通过。该初版 traceback 已留存，但不宣称保存了当时完整模块的独立快照。

验证工具问题分别记账：最初 JSON 深度探针错误假定该运行时会在指定嵌套层数失败，后改为明确注入解码递归错误；证据客户端探针首次顺带收集了导入的既有测试，随后以相同脚本精确选择新探针；空补丁被工具拒绝且未改文件。独立审计辅助程序两次沿用旧轮字段假定而失败：候选审计读取 frozen-source 字段，本地发布审计读取 helper-provenance 字段；均按本轮真实 schema 修正，保留原稿和失败。这些首次候选执行器、收集或断言问题不增加产品缺陷数。预算补修还保留独立探针夹具未推进完成阶段、错误限定拒绝码等工具问题及更正；它们与真实的中间恢复缺陷分开记账。测试方法与子场景计数不混算。

本轮 CI 采集记录无已登记的工具失败；不把旧轮采集问题移记为本轮事实。

R9 及更早封存证据、R10 首次候选完整证据均按只读边界保留；本次预算补修另用独立证据目录。Public 只提交代码与脱敏结论；原始治理来源、探针、日志、主机目录与恢复记录不进入 Public。本次改变内容的模式扫描不构成全历史秘密扫描保证。

## 保留的实现边界与尚未完成的出口

- **标准库命名探针仍存在。** 实际解释器仍调用真实 `tempfile.gettempdir()` 观察选址与回落；Python 标准库内部可能创建并 unlink 命名测试文件。既有修复消除了 Local Hand 自身写入探针的命名清理，没有证明任意同 UID 并发干扰下标准库内部操作安全。没有预填 `tempfile.tempdir` 缓存或替换选择算法，以免弱化真实回落观察。
- **socket 失败可能需要可信恢复。** 随机私有 staging/隔离目录依赖独占 ownership，不承诺抵抗拥有相同服务账户权限或更高权限者任意改写。捕获到并发替代物后若原名又被占用，既不覆盖新对象，也不删除被捕获对象；保留隔离 entry、可用的私有恢复记录并报告 IO_UNCERTAIN。目录身份不明或恢复记录写入失败同样保留可能残留，不能把关闭返回失败解释成目录已清空；后续应由受信执行者核对恢复。
- Linux O_TMPFILE、O_PATH 和内核 FD 视图缺失时对应检查拒绝，不能回退到不具备同样边界的命名删除或 chmod。受控 inode 探针与云端 Linux CI 不能替代实际运行账户、文件系统权限、GX10 身份和资源委派验证。
- MCP 的关闭检查是 dispatch 准入边界，已送达的 broker 调用仍依原身份与容量继续处理；正常 uvicorn 退出会先排空其默认线程池，本轮反例未证明数据库已关闭后仍被调用，不能据此声称修复了数据库关闭漏洞。
- helper 的启动前预算核对不能替代 OS 对阻塞 I/O 和完整进程树的监督；无法中断的存储系统调用仍受尚未完成的生产监督边界限制。文件元数据检查、私有根和最后观察不保证抵抗任意同 UID 或管理员并发改写。
- wheel 仅声明普通 STORED/DEFLATE 完整验证，不声明支持其他压缩方法；账本修复不建立新的通用递归深度或完整语义行 schema 保证。
- E1 受监督启动准备与 NAS 硬配额 provider 仍未实现，`SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED` 等生产保护未移除。E3 真实已委派 systemd/cgroup 尚未证明。E4 当前客户端私有连接与实际文件桥接、E5 GX10/S2 切换、E6 GX10→NAS→GX10 A2 均未执行；S2 继续 OPEN。

上述限制对应状态 `E1_INCOMPLETE_E3_BLOCKED_NOT_DEPLOYABLE`；源码、隔离测试、安装态和 CI 通过均不关闭后续门槛。

## 证据交付

最终独立证据审计通过，审计记录 SHA-256 `71a32ca12a5c5692891ee6fb4676d8672264271f3b87ff04176f004126922042`。完整 ZIP 已执行 CRC、成员唯一性、逐成员字节/摘要及内部 manifest 绑定核验，并与外部封存记录一同交付。

| 交付物 | 字节 | SHA-256 |
| --- | ---: | --- |
| `infra-local-hand-A2-recheck10-e349a83-evidence-20260923.zip` | 22172604 | `fb900a50adfe1fa2b01c059a583c3738cbfb289f861b01f2a30976b3bf987714` |
| `infra-local-hand-A2-recheck10-e349a83-evidence-20260923.zip.seal.json` | 909 | `f219c8b83764a2a75f84c9a2a10ff382e62a4a26cdc7ad8d8881bd0061698edb` |
| `infra-local-hand-A2-recheck10-e349a83-postseal-audit-20260923.zip` | 12627 | `31d192316df7bb88af23943f798a63e9cd6ccfe9fc9237ec03627a48ae5c0826` |

ZIP 含 2853 个成员、198 条结构化命令记录、另有 584 条安装态命令记录和 1568 份 stdout/stderr 日志；两轮候选的完整六份 CI decoded logs 也在包内留存；安装态命令数合计包含首候选与最终候选两轮。原始失败、审计、wheel、未配置 Plugin 与已校验依赖 wheel 均在包内。虚拟环境、bytecode 和可重建的 S1 合成仓库内容不作为完整现场交付。

最终结构化命令记录含 27 条非零历史退出；包含修复前反例、中间修复遗漏及验证工具错误，按各分工与审计报告区分保留，不计为最终通过。

封装后独立复验记录 SHA-256 `ca2d77f6e94a5d56b004fe066697bdf3f2a55bda8114ff48f142966fbcb90199`。首次外置归档审计因只计名称恰为 stdout.log/stderr.log 的文件，漏计两轮各两份 pytest.stdout.log/pytest.stderr.log，导致统计断言失败；归档本身的 1,568 份日志统计正确。保留该失败后，仅修正外置审计脚本并重新核验完整成员、字节、摘要及两轮安装态记录；该封存后工具失败不计入 ZIP 内的 27 条历史非零记录，ZIP 和外 seal 均未改写。上表补充审计包单独保存此次首败、修正说明、修正脚本与复验记录，共 3 条命令记录（其中 1 条非零），不与主 ZIP 的记录统计混算。

外 seal 的 `archive_name` 与 ZIP 准确配对；摘要记录是完整性封存，不是数字签名或实机验收证明。ZIP 内保存审计对应的预封存报告，本文只在本节补充封存后产生的实际摘要，避免自引用。原始证据未推送 Public；本报告和两个入口文档的后续提交不改变上述已验源码/产物。
