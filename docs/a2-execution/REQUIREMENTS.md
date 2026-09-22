# A2 受限执行、MCP 与插件：需求

- 日期：2026-09-22；Authority：Owner；状态：DRAFT / **Gate OPEN**。
- 规则 R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；采用方式见根 `AGENTS.md`。
- 拟议 scope：`LH-A2-EXEC-MCP-v1`；本次申请的首批实施边界仅为 E1–E3 隔离实现与验证。
- 权威三层文档：本文件、[ARCHITECTURE.md](ARCHITECTURE.md)、[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)。
- 本提交只补齐设计，不包含新源码、测试源码、依赖、插件包或运行配置；不构成 Owner closure。

## 目标与已有事实

最终目标是从当前对话发起受限作业、取得完整私有证据，完成
`infra-artifact-ledger` 的 GX10 → 真实 NAS → GX10 A2 验收，无须人工转抄命令和结果。
Local Hand 提供执行和取证能力；Ledger 定义 A2 的业务语义与验收标准。
SOP 保留治理规则，产品设计和实现放在本仓库；不把 Private SOP 内容搬入 Public。

已实际打通的 GitHub Connector → 私有 mailbox → 旧 Worker → Result 通道继续保留。
该旧部署的当前项目 allowlist 不含 Local Hand 或 Ledger，也不提供主机安装管理能力。
新增 Connector、MCP 或 Plugin 本身都不赋予主机权限。S1 PASS 不证明 S2 切换或 A2 完成。

Ledger 准确基线及已有授权见 [A2 能力映射](../s2/A2_CAPABILITY_MAP.md)：
Owner 链接 `bd5128e7cebc844d8fca622c791681f7c65184f8` 是 A1 输入；
文档入口是 `6707a1b521c9c4718674620e6c584656bd434e4c`；实机拟用源码是
`6bd6acfbe5c35d581891eb87275e1173e17848fc`。不自动追随最新 main。
保留 Ledger `A2-snapshot-nas-restore-v0.1` S1–S5 已有 CLOSED，不重复要求其开工批准。
Local Hand 的新作业能力、项目准入、主机部署和 NAS 影响范围另行管理。

## 三种扩展如何配合

| 层 | 本方案用途 | 明确边界 |
| --- | --- | --- |
| Connector／连接器 | 复用已有 GitHub 接入，读取固定源码和文档，按已有授权操作仓库及旧 mailbox | 不开发重复的 GitHub 连接器；不把 GitHub 凭据交给 Ledger 子进程 |
| MCP | 新增受限作业提交、查询、取消、核对与证据读取工具，连接同一 GX10 作业后端 | 不提供任意 shell、路径、环境或任意 Python 函数调用 |
| Plugin／插件 | 打包 A2 工作流程、工具契约说明、MCP 连接映射与兼容版本 | 不授予额外权限，不自动安装／切换 GX10 服务，不默认公开运行端点或私有配置 |

第一版新作业只经 MCP 或调用同一后端的本地维护 CLI 进入；不增加新作业 mailbox 桥接。
旧 Task v1 和 Result 协议保持原语义；新作业使用独立 `lh-job-v1` 契约和持久账本。
保留旧通道不等于允许它与新后端写同一资源；真实部署须证明资源不重叠或停止旧 writer。
今后若增加 job mailbox adapter，须单独设计主体认证，并复用同一账本、租约和权限检查。

## 可验收需求

| ID | 要求 | 判定依据 |
| --- | --- | --- |
| AX-R01 | 来源和权限在执行前匹配 | 节点、安装、epoch、策略、目录与固定输入不符即拒绝；执行后的来源核验不能替代 |
| AX-R02 | A2 操作有固定契约 | 仅固定作业目录中的类型、参数和程序；显式环境、资源预算和影响根；未知字段拒绝 |
| AX-R03 | 重连不产生重复副作用 | 同 id、同 digest 返回原作业；同 id 异内容冲突；提交超时用原 id 查询；不保证外部系统 exactly-once |
| AX-R04 | 崩溃、取消和结果不明可核对 | 持久意图、进程归属、阶段与副作用分开记录；无回执不等于未执行，核对不自动续跑 |
| AX-R05 | 只有一个资源所有者 | 固定后端根、资源租约、受保护 epoch 与进程退出证明；不同服务／state root 不构成隐含互斥 |
| AX-R06 | NAS 恢复验证真实且删除受限 | 核对真实挂载、发布与独立回读；持续独占本次精确归属的本地合成范围；发现变化或不明即停并保留可能部分删除的事实 |
| AX-R07 | 完整证据私有、可取回、可校验 | 私有封存 manifest、ZIP、摘要、成员清单；分块续传重建文件；报告和副作用状态分开 |
| AX-R08 | 鉴权与撤销覆盖所有工具 | 每次请求核对用户／scope／作业归属；资源 ID 不是授权；日志或源码中的指令不能扩大权限 |
| AX-R09 | 三种接入实际可用且可独立升级 | Connector 保留；MCP 端到端验证；Plugin 绑定契约版本；未具备客户端支持明确标记阻塞 |
| AX-R10 | 实施与部署来源完整 | worker、controller、job runner、adapter、插件均有准确来源与摘要；不只用旧 core digest |
| AX-R11 | 保留旧环境及可核对回退 | 不覆盖现役部署；S2 独立全账本迁移；回退不删除新作业事实或自动重执行 |
| AX-R12 | 结论对应实际覆盖 | 云端、模拟、本地安装、GX10、真实 NAS、故障项分别记账；SKIP/UNKNOWN 不能算 PASS |

## 首批实施范围与后续门槛

E1–E3 拟批准：独立作业核心、固定 A2 程序映射、MCP adapter、本地维护 CLI、Plugin 包和客户端证据重组核验，
以及隔离 fixture 上的源码、安装、协议、恢复、证据与打包验证。全部使用合成身份与目录；
模拟 NAS 明确标记，不能接入真实挂载或现役 mailbox，也不能读取真实部署凭据。
本范围允许在 closure 后新增所需源代码、测试和冻结依赖；无需先取得 GX10 的管理权限。

E4 是实际当前客户端的私有连接与证据交付验收，E5 是 GX10 部署和 S2 切换，
E6 是真实 A2 作业与缺失故障项验收。三者均不在首批 closure 内。
其准确输入、授权及门槛见实施方案；E1–E3 PASS 不能自动启动 E4–E6。

排除：任意远程命令、自动扩大项目 allowlist、NAS 挂载／服务重配、生产数据、全机断网或卸载、
Windows、新 job mailbox adapter、公共插件目录上架、Git Authority 接入。
不新增许可证；Public 源码不等于公开任务、日志、凭据、主机路径、连接技术 ID 或原始证据。

## 当前未知与完成定义

实际 GX10 管理入口、所有 writer、委派 cgroup、磁盘与 NAS 配额、挂载身份、身份服务、
ChatGPT 工作区接入能力、Tunnel 权限及网络均尚未冻结。它们不妨碍用明确 fixture 验证 E1–E3，
但分别阻塞 E4/E5/E6；没有权限的旧 Worker 不能安装新 MCP 来解决这个权限缺口。

首批完成须满足 AX-V01–V12 的隔离列，给出准确 commit、wheel／插件摘要、真实测试结果、
失败保留与未验证项；形成可部署候选。最终完成还须在真实客户端和 GX10 上达到相应列，
按 Ledger T01–T15 逐项补齐真实 NAS 与故障证据。一次 roundtrip 成功只算其中一项。
