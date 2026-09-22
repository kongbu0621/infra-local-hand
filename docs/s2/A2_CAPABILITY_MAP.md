# 面向 Artifact Ledger A2 的能力核对

日期：2026-09-22。状态：**只读核对与方案选项；没有新增执行权限或 MCP 实现**。

## 目标与准确输入

最终验收是 GX10 → 真实 NAS → GX10 的 Artifact Ledger A2 合成保存、丢失恢复和
逐行／Blob 对账。Local Hand 的公开发布、S1 PASS、S2 服务 active 都不是这一终点。

| 基线 | 角色 |
| --- | --- |
| `bd5128e7cebc844d8fca622c791681f7c65184f8` | Owner 所给仓库链接，A2 设计采用的 A1 输入；该提交没有 A2 runbook |
| `6707a1b521c9c4718674620e6c584656bd434e4c` | 原 S1 计划所指的 S3 文档入口；为上述输入的后代，包含 A2 设计、实现与运行手册 |
| `6bd6acfbe5c35d581891eb87275e1173e17848fc` | 该入口的 A2_VALIDATION §7 明确指定的 GX10 实机源码输入，包含 D9；到入口提交的差异仅为文档及日志 |

本表不自动升级 Ledger 到最新 `main`，也不把文档入口 SHA 写进旧 wheel 来源。
依据：[基线比较](https://github.com/kongbu0621/infra-artifact-ledger/compare/bd5128e7cebc844d8fca622c791681f7c65184f8...6707a1b521c9c4718674620e6c584656bd434e4c)、
[A2_VALIDATION](https://github.com/kongbu0621/infra-artifact-ledger/blob/6707a1b521c9c4718674620e6c584656bd434e4c/docs/A2_VALIDATION.md)、
[实机输入与文档入口差异](https://github.com/kongbu0621/infra-artifact-ledger/compare/6bd6acfbe5c35d581891eb87275e1173e17848fc...6707a1b521c9c4718674620e6c584656bd434e4c)。

Ledger [A2 Gate](https://github.com/kongbu0621/infra-artifact-ledger/blob/6707a1b521c9c4718674620e6c584656bd434e4c/docs/a2/GATE.md)
已经对 R `91ac1ad72a423079785725fafd4eb139f5cd7943`、
A `29ae340addde172781aa2199f864dbb25ea29ccc` 的
`A2-snapshot-nas-restore-v0.1` S1–S5 CLOSED。
它明确排除 Local Hand 接纳、NAS 服务配置、生产数据、业务切换和 Git Authority。
本方案保留该既有授权，不重复要求 A2 本体开工；Local Hand S2 的 R/A/scope 单独管理。

## 当前能力与缺口

对照 [A2_RUNBOOK](https://github.com/kongbu0621/infra-artifact-ledger/blob/6707a1b521c9c4718674620e6c584656bd434e4c/docs/A2_RUNBOOK.md)
和 [验收矩阵](https://github.com/kongbu0621/infra-artifact-ledger/blob/6707a1b521c9c4718674620e6c584656bd434e4c/docs/a2/ACCEPTANCE.md)，
现役新回执直接证明八动作名称和现有 allowlist；下表的具体接口、参数及实现限制
依据新版公开源码 `e6412a1a38e91906355fbd9ec21974993449d743`。
旧部署的同项限制未在本轮逐条核验，不因动作同名而推定实现完全相同。

| A2 所需操作 | 已有动作可覆盖部分 | 仍需正式准入／实现的部分 |
| --- | --- | --- |
| 机器和源码盘点 | `node.status`、准入仓库的 `repo.audit`、文本读取 | 实际解释器、SQLite、完整部署绑定、本地及 NAS 挂载身份；现役 allowlist 尚无 Ledger |
| 固定 checkout、build/runtime venv、wheel 构建与安装 | 可读取已有文件和 Git 状态 | 创建新目录、准备环境、固定来源并安装；不是 CAS 替换既有文件的语义 |
| 源码、编译、资源、安装态验收 | 合法、固定且回放安全的验证可由已准入 profile 运行 | 逐项冻结 argv、环境、工作目录、资源预算及输出；不能临时借 profile 执行任意脚本 |
| NAS 能力探测、发布、独立回读、移除本轮合成副本、恢复 | Ledger 已交付相关验收程序 | 新的有副作用作业契约、运行目录归属、NAS 绑定、结果不明核对；不能标成 replay-safe 来绕过 |
| 私有完整证据交付 | 有界文本结果和文件读取 | wheel、ZIP、较大日志的私有传输、成员清单、摘要和失败保留 |

该新版源码中的 `validation.run_profile` 只接受已配置的 repository/profile 名称，要求
`replay_safe=true`；最长 3600 秒、stdout/stderr 各有 2 MiB 上界。
环境过滤不会透传 `PYTHONPATH` 或 `A2_RESOURCE_TESTS`。
`fs.read_text` 和 CAS 为 1 MiB 文本边界，CAS 只替换准入仓库内既有文件。
这些都不是可以为赶进度关闭的限制；新增作业须有自己的受限契约。

## Mailbox 与 MCP 的选择

Owner 已支持在更有利于 A2 时采用 MCP。MCP 提供工具／资源接口；实际权限、
固定可执行内容和持久恢复仍由后端与部署约束决定，不能由协议名称推导。
参见 [MCP 架构规范](https://modelcontextprotocol.io/specification/2025-11-25/architecture)。

| 路线 | 已有价值 | 新增成本与本轮判断 |
| --- | --- | --- |
| 继续 GitHub mailbox | 已完成四项真实只读闭环，保留 Task/Result 与提交历史 | 有轮询及 Git 成本；二进制证据需另有私有传输；当前准备继续使用 |
| MCP 包装相同八动作 | 可统一工具发现和结构化调用 | 不填补上表主机、安装、NAS 副作用和证据传输缺口，不应作为 A2 已可执行的依据 |
| 受限作业后端 + 可选 MCP 接口 | 可针对 A2 提供作业状态、核对、受限取消和证据读取 | 需要正式设计、鉴权、可达性、持久任务身份及部署验收；尚未实现或验证当前客户端接入 |

建议：继续用已工作的 mailbox 做现有准入准备；先冻结 A2 受限作业契约，
再决定是否增加 MCP。若增加，两种入口必须共用同一任务身份、执行租约和恢复账本，
不能形成两套会重复执行 NAS 作业的后台。此处是设计建议，不是新增开工授权。

## 新作业契约必须回答的问题

1. **固定输入**：Ledger source/wheel/工具摘要、允许的操作阶段、私有配置引用与
   profile 摘要、节点和部署身份；在产生副作用之前拒绝不符，不能只核对执行后的 Result。
2. **允许的影响**：专属 checkout、venv、acceptance/run-id 和 NAS 合成 archive 根；
   固定 argv/no shell、显式环境和资源预算；不接收任意命令／路径，不挂载或重配 NAS。
3. **作业身份与状态**：提交前持久登记 id/digest，同身份不重执行；记录各阶段与
   副作用。不明结果保留原 run-id、snapshot ID、摘要及证据，通过核对判定，不能换 ID 重试。
4. **长任务与取消**：提交和状态查询分离；等待超时不等于执行失败；取消须确认
   子进程及实际磁盘状态，不能将已发布对象或结果不明任务写成无副作用取消成功。
5. **恢复与删除**：使用 Ledger 既有精确归属清单规则；新增、替换、改写、链接或
   挂载变化阻止移除；不删除既有项目、业务库、NAS 归档或失败现场。
6. **证据取回**：独立私有对象、大小／摘要／成员清单、受限读取和下载关联，
   原始机器数据不进 Public。报告未可靠保存不等于操作没有发生。
7. **入口可用性**：明确当前控制端如何连接、凭据归属、连通性、重连与撤销；
   MCP 的可达性和客户端支持必须实测，不能用本地 server 启动代替端到端接入。

这些问题解决并按准确文档基线授权后才可增加后端或 adapter。
S2 的真实切换前应明确这一后续路径，避免反复部署而仍不能完成 A2。
Linux/Python 3.11 已有 Cloud 验证记录；GX10、受支持本地文件系统正向闭环、
真实 NAS 以及 T01–T15 尚缺实机项目分别记账；
一次合成 NAS roundtrip PASS 不代表全部 A2、设备断电或业务切换已经验收。
