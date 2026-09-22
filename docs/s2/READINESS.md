# GX10 S2 准备状态与 A2 出口

日期：2026-09-22。状态：**只读准备已执行；S2 Gate OPEN；未切换服务**。

最终目标是 `infra-artifact-ledger` 的 GX10 A2 验收。Local Hand 是受控执行能力，
公开仓库、S1 测试和 S2 部署各自有完成条件，不代替 A2 的业务验收。
本文件是事实与缺口记录；S2 三层权威文档分别为 [需求](REQUIREMENTS.md)、
[架构](ARCHITECTURE.md)、[实施方案](IMPLEMENTATION_PLAN.md)。

## 本轮已执行

Owner 要求继续使用旧 Local Hand 自行操作，并同意 S2 方案与只读准备。
执行器通过既有、已确认是 Private 的 GitHub mailbox 投递以下四项新任务。
每项均取得 `succeeded` Result，并核对精确字段、Task canonical digest、
task ID、action、target/node、预期 implementation/core/profile 三元组；
Result 又按固定 Git commit 回读，内容与 blob 身份一致。

| 真实动作 | 本轮可证明的事实 | 不能由此推导的结论 |
| --- | --- | --- |
| `node.status` | GX10 Linux/aarch64、Python 3.12.3；安装 UUID、PID、运行身份和来源与旧实例记录匹配；返回八动作和现有项目 allowlist | systemd 完整状态、进程树清理、所有 controller 已停、新版已安装 |
| `repo.audit` | 已准入仓库处于 detached HEAD，工作区 clean；读取了实际 HEAD 和经脱敏的 remote 描述 | 该仓库是最新上游、Git Authority 已准入、项目可以自动 fetch/升级 |
| `fs.list` | 已准入仓库目录可读 | 主机部署目录、状态目录或任意仓库可读 |
| `fs.read_text` | 读取该仓库实际 `AGENTS.md`，核对返回字节数及 SHA-256 | 复制 Private SOP 到 Public、变更现役权限获得授权 |

这些操作证明旧通道可用。现役 allowlist 未包含 `infra-local-hand` 或
`infra-artifact-ledger`；不得把它解释成通道不存在，也不得越过 allowlist 操作。
四项任务、回执、固定提交引用和核验记录保留在私有证据交付物中。
该 ZIP SHA-256 为 `e5d14e802ddcb5a5217b308b50e4d0331f5049a14a1c35cc8e38b68123036930`，
15,039 bytes，16 个成员；只覆盖本轮四项旧部署只读操作。
公开文档不包含原始主机路径、账户、安装 UUID、mailbox 地址、任务 ID 或 SOP 正文。

## S2 仍需取得的现场事实

| 字段组 | 当前状态 | 获得方式与阻塞范围 |
| --- | --- | --- |
| 旧安装身份和允许动作 | 新回执已核对 | 仅覆盖 `node.status` 明确返回字段 |
| unit/drop-ins、解释器与真实包路径、启动参数、enabled/restart 状态 | 本轮未取得；S1 留存快照仅为历史证据 | 经批准的主机只读管理入口；阻塞真实切换 |
| 旧 profile 原始字节、权限、Git/SSH/key/known_hosts 路径和安装记录 | 摘要已匹配，完整绑定尚待现场核对 | 秘密只保留引用和权限信息；阻塞部署 manifest 冻结 |
| state/receipt/outbox/conflict/quarantine 完整账本和文件类型 | 本轮未取得 | 静止窗口下读取并封存；权限错误和 dangling symlink 不能当作不存在 |
| 所有 controller、手工 Worker、service/cgroup、子进程与重启来源 | 本轮未完整枚举 | 经批准的主机管理入口；阻塞单 writer 证明 |
| 新运行账户、独立目录、精确 profile、unit 与 controller 绑定 | 尚未生成运行配置 | 在 S2 相应 scope closure 后准备，准确值留在私有 manifest |
| A2 项目接纳与有限作业执行契约 | 尚未批准部署 | 依据准确 A2 runbook 单独限定；不借现有 validation 绕过 |

现有八动作没有任意 shell/systemctl；仓库内读取也不能跨到部署或运行状态目录。
没有发现已准入、可完成上述主机盘点的入口，因此这些项目仍为 **UNVERIFIED**。
本轮未写文件 CAS、运行验证 profile、生成 runtime 配置、安装软件、修改服务或扩大权限。

## 本轮决策依据

- 已有邮箱继续用于准入范围内操作；无需让 Owner 人工转抄任务和结果。
- Owner 随后明确支持在更有利于 A2 时评估 MCP。接入方式与后端执行能力分别评估；
  单独增加 MCP 包装不改变项目 allowlist、动作和主机权限。
- A2 准确输入、既有授权、八动作缺口及 MCP 选项见 [A2 能力映射](A2_CAPABILITY_MAP.md)。
- 实现仅有 state-root / controller-clone 局部锁，不能证明独立新旧部署互斥。
  Task v1 也没有部署 epoch/version fence；Result 来源核验发生在执行之后。
- 新 state 不能从空目录直接扫描历史 mailbox。迁移必须覆盖全部防重放证据，
  回滚必须计入新实例已执行及执行状态不明的任务。
- 现有 Linux bootstrap 会变更并重启服务，不能当作只读准备或 wheel staging 入口。
- S1 的 299 项源码测试与 94 项安装检查属于原始实机修复候选，
  不把本轮四项旧部署只读成功写成新版部署、S2 或 A2 PASS。

## 下一次可执行范围

先完成 S2 三层文档交叉审查和 A2 能力映射，形成既有完整 commit 作为文档基线。
当前未知项不阻塞编写和审查方案，但阻塞真实服务切换；不得把未知项标成已冻结。
新实施入口、配置、迁移或 MCP 开发均须先有对应准确基线与 scope 的 Owner closure，
按根 `AGENTS.md` 保留 R → A → B → C → D。
任何真实切换还需完整私有部署 manifest、单 writer 与恢复演练证据及准确切换授权。
