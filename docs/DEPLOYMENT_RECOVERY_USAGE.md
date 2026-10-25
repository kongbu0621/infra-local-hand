# 部署恢复入口：使用与当前边界

本页对应 [部署恢复重构方案](DEPLOYMENT_RECOVERY_REFACTOR.md)。入口是
`python3 -B -m admin.local_hand_deploy`，源码夹具运行需设置 `PYTHONPATH=tools`。
安装态使用 `PYTHONPATH=<所选安装投影>/tools <所选Python> -B -m admin.local_hand_deploy`；
管理员组件沿既有受 manifest 约束的 source projection 发布，变更入口核对所选源码与实际投影，
不从普通业务 wheel 假定存在管理员权限。下列命令以源码夹具环境简写。
执行变更的管理员入口与其四包运行模块必须来自同一所选安装根；不能把另一目录的 wheel 模块
拼入管理员投影来通过实现身份检查。网关镜像内的四包 wheel 则是独立运行载荷。
保留 `-B`，或在相关进程中设置 `PYTHONDONTWRITEBYTECODE=1`，避免向所选投影写入额外缓存文件。
它管理节点内的文件、固定 systemd 服务和固定网关容器；不提交、恢复执行或重放业务任务。

## 当前可以执行到哪里

已有维护屏障、完整启动选择和实际运行证明的节点，可以生成只读计划，并沿同一部署记录执行、
恢复、补偿或回退。文件身份使用普通持久文件句柄与文件系统绑定；不支持时明确返回未具备迁移条件。
文件、服务和网关适配器均有有限集合与预算，计划不接受自定义 shell、Python 回调或插件路径。

旧部署首次接入现有 `bootstrap-plan` / `bootstrap-adopt` 离线导入路径，详见下方。
它核验已经关闭的旧入口及原在途责任，导入独立、停止的守卫版兼容基线，再由普通部署计划启动。
受控停机、旧入口持久封闭及新单元预装是执行前提；导入器不会停止业务、补造退出证明或重放任务。
没有最终维护准入检查的旧管理器或本地 CLI，不会因为新建 `gate.json` 就受其约束。

固定网关现有可交付的 [守卫源码、镜像构建入口和配置说明](../containers/gateway/README.md)。
候选仅提供本地状态，稳定选择与维护状态匹配后开放公共转发；宿主同时核对 Engine 容器身份及
实际 socket 进程身份。Compose 标签和调用者提供的就绪布尔值不能代替这些证明。
本页描述源码支持路径；现役迁移、真实 nginx/Docker 生命周期及 T14 平台验收仍以
[实现与验证边界](DEPLOYMENT_RECOVERY_IMPLEMENTATION.md)的具体证据为准。

## 状态初始化与命令

`init-state` 只创建部署数据库和节点锁，不初始化业务准入，不启动服务，也不生成启动选择。
已有状态应直接读取；损坏或缺失的准入记录不能通过重复初始化改成 `OPEN`。

```bash
umask 077
PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --state /var/lib/local-hand/deployment --node example-node init-state

PYTHONPATH=tools python3 -B -m admin.local_hand_deploy plan /protected/manifest.json \
  > /protected/plan.json

PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --state /var/lib/local-hand/deployment --node example-node apply /protected/plan.json

PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --state /var/lib/local-hand/deployment --node example-node status

PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --state /var/lib/local-hand/deployment --node example-node resume DEPLOYMENT_OPERATION_ID
```

执行这些管理员命令的身份必须能读取受保护配置、持有节点部署锁，并访问固定本地管理协议。
`plan` 不创建部署目录、监督子进程或业务责任；运行证明使用严格只读的
`deployment_observe`。排空步骤才使用 `deployment_status`，按原退出证明闭合责任。

普通部署的 `resume` 使用原计划和原尝试证据；`rollback OP` 对未提交操作选择补偿方向，对已提交操作生成
唯一绑定的回退后继。重复 `rollback OP` 继续同一后继。修订目标需先生成新计划，再调用
`supersede OP PLAN` 显式交接；这会保留前驱效果、原件和恢复责任。

完成状态分别说明本地决定、准入释放与外部连接观察。`check-public SPEC` 只检查明确指定的公网
端点，不隔离服务，也不把公网暂不可达改写成本地部署失败。遇到等待时读报告中的原操作和缺失证明，
确认旧调用闭合后接续，不能通过重建状态、改请求 ID 或重复业务提交绕过未决结果。

## 原准备与原成果的部署兼容检查

计划器从实际管理配置和受保护准备目录读取原任务清单，`QUIESCED` 后再次核对，
在第一个配置或服务动作前持久保存原准备、派发闭合证明和成果读取基线。
候选管理配置不能换一套空目录来隐藏旧任务；文件发布、回退和明确交接均保留同一原基线。

未提交的 `READY` 只有在原请求未过期、仍属本次开机、执行配置与载荷完全相同时才得到兼容决定。
决定绑定原任务、准备尝试、请求和资源，以及目标节点、组件、部署、配置、载荷和开机身份。
部署先保存决定，再在仍关闭的维护锁内发布；首次执行仍检查原授权。
更换执行器的准备返回 `STALE_DEPLOYMENT`，由原准备流程接续；部署不会自动重准备或提交业务。
有派发意图且无法证明退出时仍需核对。跨开机只能通过原控制器、业务 cgroup 和未决管理器作业的
独立观察闭合维护责任，不能补写 `finished.json` 或把原业务 `UNKNOWN` 改为成功。

运行中的守卫 MCP 提供 root 对端专用的 `deployment_retention_index` / `deployment_retention_read`，
只允许读取原状态、封存清单和成果分块。读取仍经过原调用者授权、任务归属和成果摘要检查。
目标原本停止时，用所选安装的一次性无监听读取器、原数据所有者身份完成相同读取，不为检查启动服务。
新读取器的发行身份与原写入策略身份分开验证，原策略、账本和成果不改写；缺失成果目录也不重建。

比较以原任务、请求、状态和成果完整字节摘要为准，不以 MCP／管理器组件名称为准。
任务扫描上限 128、合并成果上限 256 MiB，读取受画像总时限限制；超过限额明确失败，不略过旧成果。
该本地完整读回属于部署兼容证据，**不等于外部客户端已重新登录、恢复连接或取回成果**。
临时打开的只读账本在成功和失败时均释放，不让未执行 READY 被验收读取器永久持锁。

关闭准入和每次新效果之前，协调器检查剩余事件、操作记录增长以及数据库恢复空间预算。
普通等待记录不能占用恢复事件保留额；恢复读取确认闭合后才能使用恢复额度。
预算不足时不下发下一动作，原记录保留。这是逻辑容量检查，物理磁盘故障仍按原意图观察和恢复。

## 私有绑定接入统一入口

私有包只保存数据，不再复制 `install_mcp.py` 的安装、恢复或补偿函数。固定节点文件为
`{schema: "local-hand-node-binding/v1", node_id, state, profile}`；profile 使用本页定义的实际画像，
state 为独立部署状态目录，owner_uid 必须对应运行管理员。发行文件为
`{schema: "local-hand-release/v1", node_id, request_id, target, files}`。
它可以另外指定本次的 `gateway_compose`、`gateway_checks` 和 `security_repair`，不能携带脚本或命令。

```bash
umask 077
PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --binding /protected/node.json release-plan /protected/release.json > /protected/plan.json
PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --binding /protected/node.json apply /protected/plan.json
PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --binding /protected/node.json status
```

`release-plan` 读取当前稳定选择中实际生成的 decision_id，并观察固定服务和网关，生成普通部署计划；
不能将上次草拟的 target 当作现有基线。节点与发行不一致、启动选择未决、服务仍有作业或画像漂移时拒绝。
它不修改绑定、不构建镜像、不安装依赖，也不迁移旧实例。旧节点仍先完成下述离线导入条件。
`--binding` 也可用于原 `resume/rollback/supersede/init-state`，不能同时传入另一组 `--state/--node`。
发行完成后如要更新固定画像，必须保留原绑定并明确采用新的实际绑定；这里不静默改写部署输入。

原操作已经关门并部分发布时，使用 `repair-plan`，不要把混合文件伪装成稳定 source：

```bash
PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --binding /protected/node.json repair-plan ORIGINAL_OPERATION /protected/corrected-release.json \
  > /protected/corrected-plan.json
PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --binding /protected/node.json supersede ORIGINAL_OPERATION /protected/corrected-plan.json
PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --binding /protected/node.json resume SUCCESSOR_OPERATION
```

后继标识从 `supersede` 报告的 `recovery.successor` 读取。生成修复计划时仅持有原节点锁、以只读
SQLite 读取原记录，核对原调用闭合、当前启动描述及固定管理范围。普通 `apply` 不能独立执行这种计划。
文件前置条件绑定接手时的真实对象，恢复目标仍是原链最初的受信配置；失败补偿或已提交后回退均沿
该原目标恢复。独立修改保留其独立归属，旧备份不能因为交接而覆盖它。原安全隔离责任也不能被丢弃。

共享 systemd 树只接受原画像、记录内发布/补偿效果及准确保留暂存对象；独立树变化明确拒绝。
修复计划保存当前树作为动作前置条件，保留原 loaded_snapshot，并显式执行受监督 reload；不把磁盘
观察冒充管理器已经加载。容器修复保留链上有限的原/中间 Compose 规格，仅观察和补偿准确匹配的对象。
交接前再次核对；观察变化则重新生成修复计划，已经交出的旧命令不能重新取得维护权。

## 安全检查、隔离与结果

需要运行网关的目标必须提供 `profile.gateway_checks`，包含 `authority`（预期公网 Host，不含 scheme）
及最多八项固定路径 GET。至少覆盖以下四种 `purpose`；检查不携带认证、请求体或任意请求头，不跟随重定向：

| purpose | 预期状态 | 额外约束 |
| --- | --- | --- |
| `anonymous_protected` | `[401]` | 指向 MCP 受保护路径；匿名 2xx 即安全失败，不等待 SSE 流结束 |
| `management_hidden` | `[403]` 或 `[404]` | 指向本部署实际管理路径；成功响应为安全失败 |
| `issuer_metadata` | `[200]` | `json_equals.issuer` 为准确 issuer |
| `resource_metadata` | `[200]` | `json_equals` 明确 resource 和单个 authorization_servers |

每项格式为 `{path, statuses, purpose, json_equals?, www_authenticate?}`。候选网关的受保护状态接口
在容器内读取 nginx 回环监听，宿主仍核对 Engine、PID、开机身份、配置和载荷。全部检查通过后才允许
稳定发布及释放；这不是公网 DNS/TLS 或 ChatGPT 客户端验收。单个 GET 总时限一秒；检查线程独立且最多一个，
不因观察阻塞公网许可续期。响应体和路径以摘要留证，未知值不改为通过。

确认安全错误后，在修复发行中提供
`security_repair: {unsafe_deployment_digest, reason, evidence_digest}`，reason 使用上述四种之一，
摘要绑定私有原始观察记录，unsafe_deployment_digest 必须为本计划原部署，目标必须为另一个准确部署。
协调器持久关闭准入及启动描述后，先停止画像内的准确网关，再等待业务自然结束；文件、管理器和 MCP
变更仍在排空后执行。该隔离覆盖网关新连接及既有连接，不能用于终止任务进程。
重启时被撤销的公共许可不能自行恢复。已知不安全的原部署不能因补偿而重新 OPEN，也不能成为已提交
安全修复的直接回退目标；保留关闭责任，继续明确的修复/交接。检查本身始终只读，返回 `isolation: NOT_EXECUTED`。

公网 `check-public` 的各项使用 `url` 替代 `path`，可指定同样的 purpose；只有所有项通过才返回退出码 0。
未通过或安全失败返回 4，本地等待返回 3，输入/执行错误返回 2。这些退出码不是重新安装指令。
报告分为部署、准入、公网、客户端、恢复及诊断六层，绑定记录或观察摘要；无外部证据保持 NOT_CHECKED，
另一部署的客户端成功标为 STALE，不能复制为当前验收。进行中报告的 planned_source 表示计划基线，
不是混合状态已经核验为原部署的声明。

## 宿主 MCP 与容器网关连接

宿主 `127.0.0.1` 不能直接作为独立网络 namespace 中容器的 MCP 上游。通用 MCP 入口支持
`--http-socket /protected-runtime/http.sock --http-socket-mode 660`，与 `--port` 二选一；Unix 模式必须
同时传入 `--startup-config`。守卫配置保留 `port: null`，增加
`unix_socket: {path: "/protected-runtime/http.sock", mode: 432}`（432 为八进制 660 的十进制 JSON 值）。
该监听信息进入实际配置摘要，创建监听和配置核对仍持有同一启动准入锁。

socket 父目录须预先存在且受保护，目录须以相同路径只读挂入网关。nginx 的上游可显式使用
`server unix:/protected-runtime/http.sock;`，通过准确目录/组权限允许 worker 访问。支持 mode 600、660、666；
如选择 666，其本地访问范围与回环 TCP 类似，HTTP OAuth 仍必需，不能把文件权限当作认证。
旧普通文件、链接或活动 socket 不会被覆盖；仅准确路径、原 owner/mode 且拒绝连接的残留 socket 可重建。
退出清理核对本次 inode，不删除独立替换对象。此路径已进入源码与隔离监听回归，真实 Docker 迁移另行验收。

## 旧部署的受控离线导入

此入口覆盖明确列出的旧 `resident` / `prepared` 管理服务及 MCP、网关自动入口。操作前须按已有
授权完成受控停机准备，保留旧配置、单元原件、任务记录、失败和回执。不能先杀旧管理器，再把它
不在运行当作所有准备进程、控制器及任务阶段都已退出。

导入器现场核对以下条件，不接受一个 `offline: true` 声明代替：

1. 所有声明的旧入口单元均为**持久 mask**，管理器已加载该 mask；`masked-runtime` 不满足要求。
   单元没有 MainPID、ControlPID、待决 systemd job，关联 cgroup 为空。旧自动入口保持封闭。
2. 原管理服务的 `service.lock` 已存在且身份符合原绑定，能够独占取得；不会通过创建新锁伪造
   旧派发者退出。准备派发、执行派发、原控制器及原声明的任务阶段逐项核对；缺失闭合证明时保留
   未完成状态。旧宿主开机身份变化只证明旧进程/通道不能存活，不改写原业务结果。
3. 新守卫服务使用**独立单元名称**，预先安装、加载并保持停止，policy 为 `disabled` 或 `static`，
   没有待重载定义。其实际 `ExecStart` 指向本次选定 Python、固定 manager/MCP 模块及独立配置路径；
   `PYTHONPATH` 必须指本次管理员安装投影的 `tools`，使用 `-B` 或 `PYTHONDONTWRITEBYTECODE=1`。
   不从旧未受守卫的导入树启动，也不在导入时执行单元 hook 或共享 reload。
4. 每个新入口的守卫配置路径起初不存在，位于独立受保护位置。导入只发布完整选择中的配置文件，
   不覆盖旧配置、launch 声明、锁、socket、任务/输出目录或 gate/selection 控制文件；新单元定义
   本身须提前准备，不能混入配置发布动作。
5. 如果画像包含网关，所绑定的原网关容器必须由 Engine 确认为 **absent**，导入目标明确为
   `present: false, running: false`。镜像和已有外部网络等画像前提仍须成立。导入器不删除旧容器，
   也不在此阶段创建替代容器；后续普通计划创建守卫版网关。

旧 `--session` 路径依赖原 root 控制器及其继承认证通道；核对原控制器和任务 cgroup 闭合后，
保留的旧描述文件不会自行产生新执行通道。普通交互 OS 账户不因此被禁用。
画像之外的管理员启动仍须遵循同节点协作维护规则，不能在导入期间重新开放旧来源。

离线导入 manifest 的顶层字段严格为：

| 字段 | 实际含义 |
| --- | --- |
| `schema` | `local-hand-offline-bootstrap/v1` |
| `request_id` / `node_id` | 固定幂等请求与节点身份 |
| `legacy` | 1–8 个旧入口；manager/MCP 项为 `{kind: "resident"、"prepared" 或 "mcp", unit, configuration}`，网关项为 `{kind: "gateway", unit}`；至少声明一个原派发管理者 |
| `target` | 与普通目标相同的完整部署结构；所有 `selection.components` 的 `running` 为 `false`，服务目标逐项停止，网关目标按上文缺失 |
| `files` | 新配置的固定发布表；目标须属于完整 `selection.members`，不允许删除操作 |
| `profile` | 与普通部署相同的固定画像，绑定全部新单元、入口配置、证明来源、状态位置及预算 |

已有 `gate.json` 或启动选择的节点走原普通部署恢复，不能另做离线引导覆盖既有状态。
旧 MCP 配置接受原 `gx10-single-owner-mcp/v1` 入口配置或标准 `local-hand-mcp-startup/v1`。
导入器读取其原 anchor/config、retained 与 catalog 路由，并用新只读安装逐项读取原历史策略。
这些历史账本可能不在当前管理器准备目录中，不能仅核对当前任务就将它们遗漏。
旧配置及读取路由在接续时再次核对；新入口必须覆盖相同的原任务与成果。
执行命令如下；将路径与节点替换为本次受保护的实际文件与准确身份：

```bash
umask 077
PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  bootstrap-plan /protected/offline-bootstrap.json > /protected/offline-plan.json

# 仅当尚未创建部署数据库时执行；已有状态直接复用。
PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --state /var/lib/local-hand/deployment --node example-node init-state

PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --state /var/lib/local-hand/deployment --node example-node \
  bootstrap-adopt /protected/offline-plan.json

PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --state /var/lib/local-hand/deployment --node example-node resume BOOTSTRAP_OPERATION_ID
```

安装态仍使用本页开头的所选管理员投影和 Python。`bootstrap-plan` 只核验并暂持原锁，不创建状态
或启动进程。`bootstrap-adopt` 在节点锁及原派发锁下保存固定计划，先准备全部文件原件，再发布配置；
失败或进程中断后重复同一命令，或使用原 operation ID 的 `resume`。不要重新生成计划掩盖部分发布。

导入完成报告为本地 `COMMITTED`、释放完成及 `OPEN`，其含义是**全部守卫组件仍停止的兼容基线**；
没有启动服务或执行新业务。之后读取实际 `startup_descriptor` 中已发布的稳定选择，作为普通
manifest 的准确 `source.selection`；其 `decision_id` 由导入操作生成，不能沿用草拟 target 中的占位值。
普通 `plan → apply` 才按固定顺序启动管理器、MCP，并创建/启动网关，经过本地核验与稳定选择后开放。
旧入口的 mask、原配置、任务与失败记录继续保留。

尚未提交的离线导入可 `rollback BOOTSTRAP_OPERATION_ID`，只补偿新配置并保持旧入口封闭，
不会解除 mask 或开放旧服务。已经 `COMMITTED` 的导入不能回退到未受守卫的旧版；后续版本回退从
该兼容基线使用普通部署协议。此规则保留旧事实和旧原件，不以恢复旧派发入口作为补偿结果。

## manifest 与 profile

manifest 固定包含：

| 字段 | 含义 |
| --- | --- |
| `schema` | `local-hand-deployment-manifest/v1` |
| `request_id` / `node_id` | 本次幂等请求与准确节点身份 |
| `source` / `target` | 各自的 `deployment_digest`、完整 `selection`，以及显式服务、网关目标 |
| `files` | `{target, source, mode?, uid?, gid?}`；准确删除用 `{target, remove: true}` |
| `profile` | 固定目录、全部入口守卫、只读证明来源、受管服务/网关、文件与观察预算 |

`selection` 的结构由 `local_hand_jobs.startup` 定义；其 `members` 是实际加载的完整配置文件集合，
`components` 绑定配置摘要、载荷摘要、入口类型和运行要求。源选择必须与当前受保护选择完全一致。
同一个部署摘要不能表示两套配置。准备、首次执行及本地 CLI 必须共用最终屏障。

profile 的 `schema` 为 `local-hand-deployment-profile/v1`。必须有
`startup_descriptor`、`maintenance_directory`、`guarded_components`、`probes` 和
`filesystem_support`。文件系统三项声明 `ordinary_handles`、`fsid`、`reboot_verified`
仅选择已经验证的支持画像；不能把尚未执行的重启验证填成通过。
默认文件上限为 64 个、单文件 4 MiB、准备与恢复总预算 64 MiB；失败暂存件同样占预算。

`probes` 支持固定 Unix `resident`、`prepared`、`mcp` 和 `gateway` 协议；观察核对 socket 对端 UID、
实际 PID、进程起始 tick、本次开机和加载摘要。MCP 配置摘要采用其实际输入文件集合、模式及端口，
不套用管理器配置的摘要算法。systemd 画像须给出完整共享 reload 范围及其已加载基线；
网关画像须给出固定 daemon、服务、镜像、原 Compose、外部网络身份和实际守卫证明。

若固定 systemd 服务有 `BindsTo`，在 `profile.systemd.units[单元名]` 中用 `read_only_bindings`
完整列出绑定的服务／挂载，同时列入 `read_only_dependencies`，保留实际 `After` 顺序，并设置
`start_job_mode: "ignore-requirements"`。适配器先核对依赖活动且无待决作业，再只派发该服务的启动；
依赖在此间停止时也不会被本次请求隐式拉起。依赖缺失时先解决其原维护问题，再接续原部署操作。
停止仍使用 `fail`，未声明画像仍保持原限制。此模式要求受管服务写入方共用节点维护锁；不能用来
替代启动守卫、协议就绪检查或放行未声明 hook。无绑定的既有画像默认启动模式为 `fail`。

网关 `probe.kind` 为 `gateway`，`socket` 是容器内受保护状态路径，`peer_uid` 固定为 0；
宿主从准确容器的 `State.Pid` 定位 `/proc/PID/root` 下的 socket，并复核 PID namespace 和进程身份。
正在运行的 MCP/网关必须绑定运行中的管理器。网关的守卫 JSON、nginx 配置和 manager socket
必须采用同绝对路径的只读**目录**挂载，避免文件发布或管理器重启后容器仍指向旧 inode。
直接 bind 单个输入文件或 socket 会被拒绝。固定入口 argv、镜像构建、九字段守卫配置及有界代理
语法见 [网关使用说明](../containers/gateway/README.md)；部署 `apply` 不隐式构建或拉取镜像。

## 最小可运行文件夹具

以下生成器只在新的临时目录内生成两个配置版本、一个明确停止的组件描述，以及独立的 gate。
不接触现役服务、真实任务或系统配置。它用于演示文件计划与持久恢复，不能用来证明 systemd、
网关、主机重启或旧入口迁移验收通过。文件系统支持声明在这个夹具中是固定测试输入；生产画像
必须来自已经完成的实际验证。

```bash
fixture_root=$(PYTHONPATH=tools python3 -B - <<'PY'
import hashlib, os, tempfile
from pathlib import Path
from local_hand_jobs import maintenance, startup
from admin.local_hand_deploy.planner import MANIFEST_SCHEMA, PROFILE_SCHEMA

root = Path(tempfile.mkdtemp(prefix='local-hand-deploy-example-'))
gate_dir = root / 'gate'; gate_dir.mkdir(mode=0o700)
config_path, candidate_path = root / 'manager.json', root / 'candidate.json'
selection_path = root / 'selection.json'
def write(path, value):
    path.write_bytes(startup.canonical(value)); path.chmod(0o600)
def configuration(version):
    return {'installation': {'installed': {'payload_digest': 'c' * 64}},
            'maintenance': {'schema': maintenance.CONFIG_SCHEMA, 'node_id': 'example-node',
                'deployment_digest': version, 'directory': str(gate_dir),
                'startup_descriptor': str(selection_path)}}
def deployment(version, config):
    return {'deployment_digest': version, 'selection': {'schema': startup.SCHEMA,
        'node_id': 'example-node', 'deployment_digest': version, 'decision_id': 'example-original',
        'mode': 'stable', 'owner': None, 'permit': None,
        'members': [{'path': str(config_path), 'sha256': hashlib.sha256(startup.canonical(config)).hexdigest()}],
        'components': {'manager': {'configuration_digest': maintenance.digest(
            {k: v for k, v in config.items() if k != 'maintenance'}),
            'payload_digest': 'c' * 64, 'entry': 'local', 'running': False}}}}
old, new = configuration('a' * 64), configuration('b' * 64)
source, target = deployment('a' * 64, old), deployment('b' * 64, new)
write(config_path, old); write(candidate_path, new); write(selection_path, source['selection'])
maintenance.MaintenanceGate(gate_dir, 'example-node', owner_uid=os.geteuid()).initialize(
    'a' * 64, 'example-original', bootstrap=True)
profile = {'schema': PROFILE_SCHEMA, 'owner_uid': os.geteuid(),
    'startup_descriptor': str(selection_path), 'maintenance_directory': str(gate_dir),
    'filesystem_support': {'ordinary_handles': True, 'fsid': True, 'reboot_verified': True},
    'guarded_components': {'manager': {'configuration': str(config_path), 'entrypoints': ['listener']}},
    'probes': {'manager': {'kind': 'resident', 'socket': str(root / 'unused.sock'), 'peer_uid': os.geteuid()}}}
write(root / 'manifest.json', {'schema': MANIFEST_SCHEMA, 'request_id': 'example-request',
    'node_id': 'example-node', 'source': source, 'target': target, 'profile': profile,
    'files': [{'source': str(candidate_path), 'target': str(config_path)}]})
print(root)
PY
)
umask 077
PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --state "$fixture_root/state" --node example-node init-state
PYTHONPATH=tools python3 -B -m admin.local_hand_deploy plan "$fixture_root/manifest.json" > "$fixture_root/plan.json"
PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --state "$fixture_root/state" --node example-node apply "$fixture_root/plan.json"
```

报告中的 operation ID 可继续用于 `status`、`resume`、`rollback`；不要另造业务任务来验证恢复。
源码下的 `tests/test_local_hand_deploy_files.py` 与 `tests/test_local_hand_deploy_runtime.py`
还覆盖实际临时文件、子进程中断、持久身份、原缺失恢复、独立替换冲突和已提交回退去重。
