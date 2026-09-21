# 仓库形成、参数化和迁移记录

> 2026-09-21 公开更新：Owner 已批准准确候选 `b763bd6714721d22278086db559fa3f6684aad7b` 及治理摘录的公开，暂不添加许可证，见 [公开决定](governance/PUBLICATION_OWNER_DECISION.md)。下文是批准前的形成评估记录，其中“Public 空仓”“尚未发布”“许可证待决定”等是历史状态；本段更新这些发布事实。原有 Authority admission、等价采用、Windows、新版实机服务及 A2 的未完成项不由本次公开自动关闭。

- Status: 候选拆仓论证；Public 空仓已创建；实现、发布、Git Authority admission 与新版本实机验收均未因此自动完成。
- 产品来源: `kongbu0621/engineering-sop`，固定提交 `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- 逐文件选择: [SOURCE_SELECTION.json](SOURCE_SELECTION.json)。记录的是上游 Git blob SHA，不能冒称为原始字节 SHA-256。

## 独立责任与证据

Local Hand 的变化原因是本机执行契约、传输适配、部署和跨平台一致性；SOP 的变化原因是治理和实践知识。产品拥有独立任务/结果契约和发布生命周期，存在可识别的执行职责和首个控制端使用证据。它不拥有认知目标、知识 Authority 或项目 Git Authority。私有治理/机器证据与公开可复用实现的可见性也不同。

这些事实支持独立产品候选，尚不能宣称“公开 clean-room 接入已经闭合”。两种操作系统不等于两个 consumer；空仓不等于完成拆仓。新包须由 S1 证明无隐含 SOP 实现依赖、通用参数可配置、稳定契约可独立验收，才补充最终 Formation 结论。拆分也增加协议、版本和文档协调成本；通过新仓唯一实现源、SOP 仅链接固定版本及证据，防止双份产品源码长期分叉。

## RFS-1.0 形成评估

采用同一固定来源提交的 `docs/principles/repository-formation-standard-v1.0.md`，Status Provisional / Owner-mandated，并保留 Established 的可复用模块边界原则。

| 项目 | 本候选的回答及证据状态 |
| --- | --- |
| A1 主要语义所有权 | 受控本地任务执行及其可关联结果/证据；既有八动作和 Task/Result 契约支持 |
| A2 负向边界 | 不拥有知识、认知目标、任务授权、项目源码 Truth 或 Git Authority |
| A3 变化原因 | 协议实现、执行安全、平台适配、包装和部署一起演化；SOP 治理实践另行演化 |
| A4 独立闭环 | 已有模块/测试提供输入；新包脱离宿主的安装、调用、测试和版本化待 V01/V07/V08 验证 |
| A5 稳定接口 | 保持 Task/Result v1；部署配置 v2 显式迁移，不能从宿主目录或环境猜测 |
| A6 Truth/Authority | 产品实现最终单一来源；旧 SOP 版本保留为历史，迁移完成后不作为另一个活动产品分支；任务/结果归准入部署 |
| A7 依赖方向 | 通用核心不依赖 artifact-ledger/SOP 特定业务；全部移植模块的 import/运行依赖须在 V01 最终证明 |
| A8 生命周期 | 独立 wheel、版本和平台支持矩阵；SOP 文档提交无需触发程序部署；是否出现长期锁步须持续观察 |

Atomic invariant：Task/Result schema 和 digest 保持同一 v1，controller 与 worker 在同一产品仓维护；新配置只在显式升级时成对迁移。每个运行部署只有一个 state/receipt Owner。跨旧新实例的未决任务核对、暂停投递、单 writer 切换和回滚属于 S2 前置方案，S1 不执行在线 rolling transition，不把“两个仓一起改”当作协议。

Evidence grade：候选按 **E2 的“职责高度稳定、明显 consumer-independent”路线**论证；已有一个真实控制流程，不宣称存在第二个外部 adopter。公开代码与私有机器资料的可见性分离也是明确物理边界理由，它不授予执行权限。公开 clean-room 安装还未完成。

收益包括可独立交付版本、减少 SOP 与程序发布耦合、隔离私有材料、统一两平台诊断。协调成本包括两平台 CI、wheel/配置兼容、跨仓固定版本链接、S2 运维及单维护者成本。保留共同 protocol/controller/worker 于同仓以限制版本矩阵；不拆出第三个协议仓。尚无独立两仓历史可据以量化 co-change，不声称已有长期低锁步证据。

| Hard veto | 评估 |
| --- | --- |
| V1 Authority collapse | 设计明确单一产品 Owner/来源；正式迁移时仍须验证旧副本的历史定位 |
| V2 共同修改运行 Truth | S1 不读写真实 state；S2 必须证明单 writer/state Owner，不能双活 |
| V3 隐含向上依赖 | 设计禁止；全包独立运行证据未完成，因此不宣告最终通过 |
| V4 未解决原子不变量 | v1 协议保留；配置/收据的在线迁移留在 S2 关闭后执行 |
| V5 长期锁步 | 尚无拆分后历史；S1 独立包验证和后续版本记录用于证伪 |
| V6 拓扑投影错误 | 拆分理由是执行语义与公开生命周期，不以 Linux/Windows 或验收阶段拆仓 |

**当前正式 verdict：REPO_LATER；目标候选：REPO_NOW_PUBLIC。** 这里“later”指公开产品形成和长期 Authority 准入的证据尚未闭合。Owner 本轮已明确要求先建 Public 空仓，该空仓保留；不从这一指令推导全部 Gate 通过。S1 在隔离 staging 中完成 package-first 证据，尚不发布产品实现。满足独立闭环、无未解决 veto、公开依赖/示例和材料审查后再更新 verdict，由 Owner 决定公开准确候选。

Repository class 候选为可复用基础设施能力，名称 `infra-local-hand`；名称不是拆分证据。更换 Git mailbox 或底层进程适配后，“受控本地任务执行及证据”责任仍成立。若持续出现跨仓成对 PR/发布、隐藏上层依赖或测试必须读取 SOP HEAD，应重新评估并可吸收回 package；若无实际使用且维护成本不能成立，可保留历史后退役。不得把既有空仓当作不可逆拆分承诺。

## 参数化清单

| 现状 | 处理 | 保留的边界 |
| --- | --- | --- |
| Node Profile 已有 node/root/repositories/validations | 保留并升级显式配置版本 | 白名单、原始配置摘要、single_writer |
| controller 的 `DEFAULT_BRANCH`/`FROZEN_MAILBOX_URLS` | 移到共享传输策略及准入 marker | SSH、精确 remote 和 branch，一致性校验 |
| Worker CLI 默认固定 mailbox branch | 必须与 profile 一致；移除静默旧值 | 启动前 fail closed |
| 两个平台 bootstrap 另有 mailbox 常量 | 使用同一配置校验器 | pinned known_hosts、独立凭据、固定运行可执行文件 |
| bootstrap 生成项目特定的 pytest profiles | 由显式批准的验证配置生成 | 固定 argv/timeout/replay_safe，Task 仅选名字 |
| 源码目录推断 implementation commit | 增加 wheel 内构建来源及部署交叉校验 | core digest 和 wheel digest 分开记录 |
| acceptance/CI 的真实身份和仓库 fixture | 重写为 synthetic 值并参数化 | 测试目的、负向断言和平台真实语义 |
| `linux_cutover.py` 的具体主机迁移常量 | 排除专用脚本及专用测试 | 私有历史证据保留；不伪装通用安装器 |

参数化的对象是部署差异；Task/Result envelope、权限边界、路径安全、结果状态和持久恢复语义不能成为随意关闭的选项。

## 历史证据与新候选

上游已有 Windows R1 及 GX10 的 Owner closure，后续限定的 v0.1 READY 范围为可信单控制端 scratch／非敏感任务；Publication 仍是独立未关闭项。后来的文档性提交不说明现役程序已经升级。

本会话已取得现役 GX10 的 `node.status` 结果，并核对任务摘要及来源。它证明当前受控 mailbox 通路有效，不证明新仓库或新 wheel 已安装，也不授予 artifact-ledger 项目权限。原始节点 ID、账户、home 路径、安装 UUID、key 位置及完整任务/结果保留在私有证据中，不随本候选公开。

新 package 删除文件、改变配置或改变构建方式后，应记录新 digest；不得照抄旧 digest 或沿用旧机器 PASS。新旧证据通过来源映射关联，验收结论分别陈述。

## 发布与切换边界

S1 不修改 SOP，不迁移机器、不添加运行权限、不触发真实任务。Public 候选先保存源码、测试、文档、许可证/notice、wheel 和依赖来源审查材料；原始证据与凭据不进入公开包。许可证与准确候选须由 Owner 决定后才发布。

产品仓库、运行 mailbox、开发工作副本、Git Authority、GitHub 发布副本和备份不是同一角色。新 GitHub 空仓不等于本地/NAS Authority 准入，也不能从本轮授权推导 mirror/force push、删除 refs 或重命名 origin。后续 Authority admission 如需进行，应另行验证 heads/tags/HEAD、完整性和复制一致性；S1 没有这类动作。

S2 先创建新安装目录、配置和 venv，完整保存旧版；静默期核对未决任务和收据后，单 writer 切换并核对实际进程身份、commit/core/profile/安装摘要。回滚也要核对新实例是否执行过任务；不能只启动旧服务就声明恢复。S3 在新批准的项目 profile 下执行 A2，并另存全部实机证据。
