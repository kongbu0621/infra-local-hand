# infra-local-hand

受控本地执行器：让 ChatGPT 等应用或本地 CLI 在已配置的机器上提交有限任务，查询或取消执行，中断后沿原任务恢复查询，并取回可核对的结果与证据。

这里的“本地”指任务执行位置。调用方可以通过网络连接服务，实际操作仍受登记的任务类型、项目、权限和资源上限约束。

**当前版本：`0.2.0a1` alpha · Python 3.12 为当前验证基线。** 从源码构建 wheel；包安装、服务部署和现场验收是分别需要完成的步骤。生产资格尚未完成，仓库暂未附许可证。

## 它解决什么问题

| 使用者的问题 | Local Hand 提供什么 |
|---|---|
| 怎么让应用在指定机器上完成一项操作？ | 按登记的任务类型和资源引用准备、提交并执行任务 |
| 任务是在运行、已经结束，还是结果未知？ | 用原任务 ID 查询执行、业务结果和证据状态 |
| 连接中断后，怎样继续确认结果？ | 沿同一任务和账本核对，保留未知事实，避免重复执行业务 |
| 怎样取消任务？ | 记录取消请求、停止原执行，并继续核对退出证明 |
| 怎样把执行结果带回来？ | 返回状态、文件清单和分块证据，供调用方完整取回并校验 |

例如，对一个已登记项目修改单个文件：Local Hand 在任务独立副本中执行修改和固定验证，返回补丁、前后内容与验证输出。调用方核对证据后，再用[本地应用入口](docs/USAGE.md#land-a-verified-workspace-edit-locally)检查并应用到目标副本；任务完成本身不会自动提交或合并 Git。

## 与其他组件的关系

四个组件分别承担任务执行、成果保存、生产协调和运行知识管理。Local Hand 与 Ledger 已有可选归档接入；P 已接通任务执行、成果读回与候选验收；K 已有知识审查、版本、采用与反馈接口。实际执行、知识准入和生产资格分别核对。

| 组件 | 主要职责与本仓关系 |
| --- | --- |
| **infra-local-hand** | 执行获准任务，保留原任务状态，返回结果和封存证据；生产目标与后续决策由调用方负责 |
| [infra-artifact-ledger](https://github.com/kongbu0621/infra-artifact-ledger) | 保存成果身份、版本、内容与来源；本仓可选的 `local-hand-archive` 已能将成功封存的任务结果归档并按准确版本读回 |
| [control-production-plane（P）](https://github.com/kongbu0621/control-production-plane) | 已接入的调用方：通过本仓公共入口准备、提交、查询和取消任务，协调修复、成果核对与候选验收；候选验收不等于补丁已应用 |
| [domain-operational-knowledge-core（K）](https://github.com/kongbu0621/domain-operational-knowledge-core) | 运行知识组件：P 或其他应用通过 K 公共接口采用已审查的准确版本，并回流原任务结果；K 管理候选、审查与知识生命周期，不直接管理本仓任务 |

应用可直接使用 Local Hand，接入 P 或 K 不是执行任务的前提。现有归档的安装与使用方式见下方[与 Artifact Ledger 配合](#与-artifact-ledger-配合)。

## 工具 API 一览

下面列出常驻入口支持的 **8 个工具**。这些名称用于 MCP 工具调用；本地 CLI 也可调用所连接后端支持的同名工具。
实际暴露和可调用的范围取决于运行模式、部署配置及调用者权限，先用 `lh_capabilities` 确认获准的作业与资源引用。

### 查询与读取（5 个）

| API 与用途 |
|---|
| **查能力** · `lh_capabilities`<br/>查询获准使用的功能、资源引用和身份绑定；预备单任务入口还可返回原 `prepared_request` |
| **读源码** · `lh_workspace_read`<br/>读取已登记项目来源快照中的 UTF-8 文件，返回原文、SHA-256 和源码提交；读取不会准备或提交任务 |
| **查状态** · `lh_job_status`<br/>按原 `operation_id` 查询执行、业务结果和证据状态；查询不会重放业务 |
| **列证据** · `lh_evidence_manifest`<br/>按任务分页读取已封存的证据清单，包括文件的 `artifact_id`、大小和 SHA-256 |
| **读分块** · `lh_evidence_read_chunk`<br/>按 `artifact_id`、偏移量和可信清单中的摘要读取文件分块，返回 Base64 数据供调用方组装并校验 |

### 任务准备与控制（3 个）

| API 与用途 |
|---|
| **准备任务** · `lh_job_prepare`<br/>为获准任务准备资源和确定的请求，返回 `PREPARING`、`READY` 或 `FAILED`；`READY` 后原样提交返回的 `request`，准备本身不执行业务 |
| **提交执行** · `lh_job_submit`<br/>提交确定的任务请求并持久保存记录；响应不明时保留原 `operation_id`，先查询原任务 |
| **申请取消** · `lh_job_cancel`<br/>用原任务 ID、原请求摘要和明确目标申请取消；收到回执后仍需查询并确认退出 |

常驻任务通常按 `lh_capabilities` → `lh_job_prepare` → `lh_job_submit` → `lh_job_status` 调用，
证据封存后再通过 `lh_evidence_manifest` 和 `lh_evidence_read_chunk` 取回文件。

源码还定义了 `lh_job_reconcile`，用于核对原任务已产生的影响；**当前常驻入口不提供它**。
它与恢复连接后的状态查询不同，其他入口是否可用以服务暴露的工具及权限为准。

完整参数与必填字段以已连接服务的工具 schema 为准。运行模式、参数和调用约束见
[作业使用说明](docs/USAGE.md#作业入口与运行模式)；源码定义见
[contract.py](tools/local_hand_jobs/contract.py) 和 [server.py](tools/local_hand_mcp/server.py)。

## 从请求到可用结果

[![调用方经接入入口向 Local Hand 作业后端发起请求；侧边账本与证据保存原任务状态和产物；最下方由调用方取回状态与证据，核对后继续工作。](docs/diagrams/task-results.svg)](https://raw.githubusercontent.com/kongbu0621/infra-local-hand/fe3a75fe1133566b8527a0698b7f4a5a01dd4176/docs/diagrams/task-results.svg)

[查看原图（可缩放）](https://raw.githubusercontent.com/kongbu0621/infra-local-hand/fe3a75fe1133566b8527a0698b7f4a5a01dd4176/docs/diagrams/task-results.svg)

图中主线表达职责和结果关系。只有获准提交才可能启动业务；查询、恢复和读取围绕原任务进行，不会重放已执行的业务。返回结果仍可能是失败或未知，证据是否可取回以实际封存状态为准。

任务账本保存执行状态，封存证据保存可供核对的产物。调用方负责决定下一步做什么；Local Hand 按已登记的能力执行，并如实返回已观察到的结果。

## 怎么接入

| 接入方式 | 入口及职责 |
|---|---|
| ChatGPT 等支持 MCP 的应用 | 通过 MCP Server 调用任务工具；客户端需能访问配置的网络入口并完成认证 |
| 本地 CLI | `local-hand-jobs` 通过受保护的本地 Unix socket 访问作业后端，以操作系统身份映射鉴权 |
| 部署侧 | 配置允许的任务、项目、验证和预算；管理服务准备资源，MCP 服务处理网络请求 |

包中还保留 `local-hand-worker` / `local-hand-connect` 的 Task/Result 与 Git mailbox 入口，其配置和权限边界见[使用说明](docs/USAGE.md#explicit-admission)。它与作业后端的 MCP/CLI 入口使用不同协议，不能混用任务参数。

### 客户端、Server、MCP 与 Tailscale 是什么关系

上一张图说明请求怎样得到可核对的结果；下面这张图展开 ChatGPT 通过网络连接本地执行的路径。
其中 MCP Server 对应上一张图的接入入口，任务进程由作业后端管理；任务账本与证据见上一张图的侧边。
本地 CLI 则通过上表中的 Unix socket 接入，不需要经过图中的 ChatGPT 客户端或 Tailscale。

**Local Hand Server 负责接收和处理请求；MCP 规定双方怎样通信；Tailscale 可以提供网络连接入口。**

| 名称 | 在这里是什么意思 |
| --- | --- |
| 客户端（Client） | 发出请求并接收结果的程序。通过 ChatGPT 操作 Local Hand 时，具体指 ChatGPT 中负责连接 Local Hand、发起工具调用的组件。浏览器是用户操作 ChatGPT 的界面。 |
| 服务端（Server） | 在本机环境中运行、等待并处理请求的后台程序。这里指 Local Hand 服务，可以运行在已有电脑或其虚拟机中。 |
| MCP | Model Context Protocol，一套通信规则，规定如何发现工具、调用工具和返回结果。 |
| MCP Server | 支持 MCP 通信的服务端。Local Hand 的网络服务入口就是一个 MCP Server，背后连接本地作业后端。 |
| Tailscale | 部署时可选的网络入口，把请求转发到 Local Hand。任务管理和执行由 Local Hand 实现，MCP 规则也不绑定 Tailscale。 |

按 [MCP 的正式术语](https://modelcontextprotocol.io/docs/learn/architecture)，ChatGPT 这类 AI 应用称为
Host（宿主应用），其中连接 MCP Server 的组件称为 Client（客户端）。下图把这层关系展开。
下图以 Tailscale 作为可选部署入口；图中省略了宿主机与虚拟机之间可能存在的端口转发。
调用方需要能够访问配置的网络入口。

```mermaid
flowchart LR
    U["你：通过浏览器使用 ChatGPT"] --> C["ChatGPT 中的 MCP 客户端"]
    C <-->|"MCP 请求与结果（HTTPS）"| G["Tailscale 入口"]
    G <-->|"转发请求与结果"| S["Local Hand MCP Server"]
    S <-->|"提交、查询、取消"| B["本地作业后端"]
    B <-->|"启动、停止与结果收集"| T["本地任务进程"]
```

例如，你说“查询任务状态”：

1. ChatGPT 按 MCP 规则调用 `lh_job_status`，携带原任务的 `operation_id`。
2. 网络入口把请求转发给 Local Hand MCP Server。
3. 服务端校验身份、权限和参数，再由作业后端查询该任务。
4. 服务端按 MCP 规则返回结果，ChatGPT 再把结果告诉你。查询本身不会重新执行任务。

网络入口的访问范围由部署配置决定：Tailscale **Serve** 面向 Tailscale 私网，
**Funnel** 可以向公网提供入口，区别见 [Tailscale 官方说明](https://tailscale.com/docs/features/tailscale-funnel/how-to/host-websites)。
本机浏览器能打开登录页、拥有 `ts.net` 地址或服务处于运行状态，都不能单独证明 ChatGPT 的工具调用端已能访问 MCP 入口；
需要分别确认网络可达和 OAuth 授权。Local Hand 会继续校验调用者身份及每项工具的权限。
连接中断只表示客户端暂时无法取得响应，不能据此认定任务取消或失败；
恢复连接后应沿原 `operation_id` 查询。取消请求已受理也不等于进程已退出，需要继续查询退出证明。
后端按原任务 ID 和请求摘要识别重复提交；换一个任务 ID 会被视为新的任务，不能用它重试结果未知的业务。

## 开始使用

1. **确认部署与权限。** 已有服务时先读取 `lh_capabilities`，确认允许的作业、项目或运行环境引用。新部署从[构建与安装](docs/USAGE.md#build-and-install)及[服务部署输入](docs/USAGE.md#job-service-deployment-inputs)开始；管理组件需另行部署，安装 wheel 不会自动建立可用的远程服务。
2. **按入口模式提交确定的任务。** 常驻入口使用新的任务 UUID 调用 `lh_job_prepare`；`PREPARING` 时沿同一 UUID 和参数查询，`READY` 后原样提交返回的 `request`。预备单任务入口则提交能力返回中的原 `prepared_request`；只读入口不能准备或提交新任务。
3. **沿原任务查询或取消。** 保存完整原请求及 `operation_id`、`request_digest`；响应丢失先查原任务，不能换一个 ID 重试结果未知的业务。取消已受理不等于进程已退出。
4. **取回并核对结果。** 查询状态；证据封存后，读取 `lh_evidence_manifest` 与 `lh_evidence_read_chunk`，完整组装文件，并按可信返回核对原任务关联、大小和摘要，再决定如何使用结果。

入口模式与当前工具参数见[作业使用说明](docs/USAGE.md#作业入口与运行模式)；取消、恢复和证据的设计约束见[作业架构](docs/a2-execution/ARCHITECTURE.md#ax-a07-mcp-工具和二进制证据r03r04r07r08r09)。

## 与 Artifact Ledger 配合

Local Hand 负责执行任务和取回结果；[Artifact Ledger](https://github.com/kongbu0621/infra-artifact-ledger) 为数字成果保存稳定身份、不可变版本、内容及来源关系。

可选的 `local-hand-archive` 能将已经成功封存的单个任务结果保存到独立 Ledger，再按返回的制品 ID 和版本 ID 读回原证据。当前消费者支持 Linux；归档不会重新执行任务，也不会自动应用补丁。安装、可信输入与重试方式见[结果归档](docs/USAGE.md#archive-and-read-a-completed-result-locally)。普通 Local Hand 使用不依赖安装 Ledger。

## 当前能力与边界

| 范围 | 已有能力与限制 |
|---|---|
| 提交、查询、取消、同任务恢复和证据读取 | 已在已有部署完成真实 ChatGPT 入口验证；具体任务的未知结果与证据缺口仍按原记录保留 |
| `host.inspect`、`workspace.edit` | 检查主机；在登记项目的任务独立副本中修改单文件、运行固定验证并返回结果。具体引用以服务能力列表为准 |
| NAS 新作业 | 当前被实现屏蔽；历史任务记录仍保留 |
| 平台 | 核心包有 Linux/Windows 验证；当前作业后端、本地 socket 与管理服务按已有 Linux 部署使用，不能据此宣称所有入口都已跨平台验收 |

任务不能携带任意 shell 命令或自行扩大项目、路径与权限范围。身份校验、任务关联、数据保护及资源上限始终生效；任务、日志、凭据和原始证据保存在部署者的私有环境。

工具调用存在偶发 `-32603` 的保留记录，根因尚未确认；连接错误不等于任务没有执行。已有任务先按原 ID 查询，仍未知的结果如实保留。

## 文档

| 想了解什么 | 阅读入口 |
|---|---|
| 如何安装、连接、应用补丁或归档结果 | [使用说明](docs/USAGE.md) |
| 作业入口、当前参数及任务设计约束 | [运行模式与工具参数](docs/USAGE.md#作业入口与运行模式) · [作业架构](docs/a2-execution/ARCHITECTURE.md) |
| 产品需求及早期 Task/Result、Git mailbox 设计 | [需求](docs/REQUIREMENTS.md) · [架构](docs/ARCHITECTURE.md) |

开发过程、阶段记录和任务接续见[开发与接续记录](docs/DEVELOPMENT.md)；参与维护从 [AGENTS.md](AGENTS.md) 开始。
