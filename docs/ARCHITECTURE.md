# 架构：受控 Execution Plane

- Authority: Owner；Status: DRAFT / 待确认；对应 [R01–R12](REQUIREMENTS.md)。
- 提议只改变产品封装、配置准入及构建来源绑定；Task/Result v1 和八种动作保持兼容。

## A01 职责和依赖

控制端把意图转换为有限任务；Transport Adapter 负责投递和收取；Worker 校验任务并调度本机能力；Platform Adapter 处理服务、路径和进程；配置准入确定允许的资源。控制端或模型不能通过任务自行改变准入配置。SOP 保留治理和历史证据；新仓库拥有通用执行实现和公开产品文档。

| 部件 | 责任 | 不拥有的责任 |
| --- | --- | --- |
| `local_hand.protocol` 与 Worker | Task/Result、校验、分派、来源、持久收据 | 用户目标、模型记忆、决策 Authority |
| 文件/Git/validation handlers | 白名单内操作和结果验证 | 任意 shell、Git Authority 写入 |
| `local_hand_connect` | 组装任务、关联结果、有限等待、传输适配 | 节点提权、自动重放不确定写入 |
| 共享配置/传输策略模块 | 解析一次、跨入口统一校验 | 从不可信任务接受部署参数 |
| Linux/Windows bootstrap | 安装预检、版本目录、账户和进程绑定 | 自动扩展项目白名单、删除旧环境 |

保持现有 `tools/local_hand` 和 `tools/local_hand_connect` 模块边界，首阶段不做无必要的目录重写。控制端对现有 Worker 校验函数的依赖可保留，不为“分层”另造相互冲突的协议校验器。打包后模块可独立导入，不依赖 SOP 文件树。

## A02 Task/Result 与配置分离

Task schema 是 `local-hand-task/v1`，顶层精确五项：`schema_version, task_id, target_node, action, params`。Task ID 为 `LH` 加 4–64 位十进制数字。digest 是 UTF-8 JSON（sort_keys、无多余分隔空白、ensure_ascii=False）的 SHA-256，保持上游算法。

| action | 必需 params | 可选 params |
| --- | --- | --- |
| node.status | 无；使用空对象 | 无 |
| repo.audit / git.status / git.diff | repository | 无 |
| fs.list | repository | relative_path |
| fs.read_text | repository, relative_path | 无 |
| fs.write_text_cas | repository, relative_path, expected_sha256, content | 无 |
| validation.run_profile | repository, profile | 无 |

Result schema 为 `local-hand-result/v1`，顶层精确十四项：`schema_version, task_id, task_digest, target_node, node_id, action, worker_version, implementation_commit, package_digest, profile_digest, status, details, error_code, error`。控制端拒绝错关联、错节点和来源不匹配的结果。等待时间到只表示尚未取得可信终态；不能等价为节点未执行。

安装配置采用 JSON。现有 `node_id`、`projects_root`、`repositories.<name>.path/single_writer/validations` 已经可配置，继续保留其语义。新增配置版本及受控 `transport_policy`，具体字段见实施方案；所有入口共用同一校验器。部署版不默默回退到旧节点/仓库/branch。旧格式迁移是显式 staging 步骤，原始文件保留。

`profile_digest` 仍为完整 Node Profile **原始字节** SHA-256，不改成部分字段摘要。将准入的传输策略纳入该文件，使 transport 变化反映在 profile_digest；controller 另保存相同 transport 对象的规范 JSON 摘要和准入 marker，用于本地防漂移，不增加 Task/Result 顶层字段。JSON 格式变化也会改变 profile_digest，这是保留的行为。

## A03 传输与准入

首阶段保留 Git mailbox；`_executor_spike/tasks`、`results`、`conflicts` 路径属于现有布局，保持兼容，不因产品改名而偷偷改路径。Public 产品仓库不是运行 mailbox。产品不得自动创建、公开或重定向 mailbox。

部署者显式给出 SSH remote、精确允许的 remote 拼写和 branch；共享校验器验证它们一致且属于支持的 SSH 语法。拒绝 ext/file/http、本地路径、选项注入、控制字符及未经允许的 host/user/repository。SSH key、known_hosts、Git/SSH/Python 的绝对路径由安装绑定提供，凭据内容不进入配置模板、包或结果。Git 环境、hooks、filters、fsmonitor 与 remote 展示仍执行原有加固。安全语义的改变不能伪装成“替换常量”。

不存在本阶段 MCP 服务器或公网 relay 实现。ChatGPT 已可通过受控 mailbox 协议交互；给 adapter 取名不等于部署了新连接。未来 transport 必须保持任务关联和外部授权语义，并重新评估威胁边界。

## A04 文件、验证与一致性

路径采用规范 POSIX 相对路径/NFC。拒绝 traversal、Windows 设备名及别名、分隔符歧义、`.git`、符号链接和原生路径身份不一致。读写 UTF-8 文本上限 1 MiB；Task/Result 各 8 MiB；validation stdout/stderr 分别最多保留 2 MiB，并发有界排空。

CAS 只对 `single_writer=true` 的仓库开放，保留跨进程协作锁、写前二次摘要检查、同目录临时文件、同步和原子替换、独立读回验证。锁不能排除外部编辑器；不得宣称一般线性一致性。

验证 profile 是部署配置中的固定 argv、有限 timeout 和明确 `replay_safe`，任务只选择名字。使用 `shell=False`、受限环境和确定 cwd。受控进程超时后清理进程树；无法确定清理完毕时 indeterminate。修改验证脚本本身仍可能改变执行语义，必须处于可信仓库和变更审查范围，不能用 CAS 写脚本绕过权限边界。

## A05 状态、恢复与来源

单 active worker/state-root 锁保护本地处理。任务经校验后进入持久执行收据，完成后写入 outbox 再发布；恢复按照现有收据状态核对，不能凭网络超时再次执行。相同 ID/不同 digest、远端错误结果或冲突不覆盖已有证据，形成隔离记录。无法确认副作用时保留 indeterminate。对崩溃、发布失败和恢复的行为以原有代码及迁移测试共同验证。

`implementation_commit` 标识本产品源码版本；`package_digest` 保持原算法：排序后的核心包顶层 `*.py` 文件名、NUL、原始内容、NUL 的 SHA-256。它不覆盖控制端、bootstrap 或整个 wheel；额外记录 wheel 全文件 SHA-256 与发布文件清单，不能混用两种摘要。

wheel 内包含构建产生的来源元数据，绑定干净源码提交；安装记录绑定 wheel 摘要、core digest、profile digest、运行可执行文件和 install UUID。部署启动核对记录和实际文件，缺失或不一致 fail closed。源码模式与 wheel 模式均不得信任当前 cwd；外部 `implementation_commit` 环境值不能单独证明包来源。wheel 内元数据不记录 wheel 自身摘要，避免自引用。

## A06 平台、演化与回滚

S1 首批明确验收 Python 3.12，平台为 Linux 与 Windows/PowerShell 7+；其他版本不未经验证宣称支持。Python 核心共用，服务、进程树、路径预算、ACL 和 exit code 传播由平台适配负责。5.1 只允许 parse 并拒绝安装。运行时依赖以现有标准库实现为基线，build/test 工具独立于 runtime venv。

旧版与新版的 state/receipt/profile 迁移不通过直接复用目录实现。S2 先冻结新任务、核对或排空旧 outbox、停止旧 writer，再启新 worker；中途失败时停止新 worker、恢复旧版绑定，并审计任务是否执行。不能同时保留两个 active writer 来实现“无停机”。

候选方案选择 JSON 配置、现有 Git transport、wheel 和版本目录；暂不采用 YAML 依赖、通用插件发现、任意命令 API 或新增 task 授权字段。新协议、严格 JSON 解析强化、多控制端、嵌套根消歧与生产沙箱需要独立范围。事实推翻假设时按 Gate 重新确认，不以兼容名义静默改变行为。
