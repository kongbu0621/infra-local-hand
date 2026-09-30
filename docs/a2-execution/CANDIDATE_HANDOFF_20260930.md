# E3 最新候选与实测装配交接

2026-09-30。当前处于 **E3 真实隔离验收准备**：正常链及固定取消场景的源码入口已连接，
真实 Q2 startup、Q3 正常链、Q4 取消、生产启用、E4–E6 和 NAS 尚未完成验收。
本文件接续[此前候选记录](SYSTEMD_ACCEPTANCE_HANDOFF.md)和[取消场景说明](Q4_CANCEL_CASE.md)。

## 本轮修复及准确候选

复核发现内部 Q4 已支持取消，外层 `q2_prepare_run` 却仍只接受 Q2 正常模板。
已先重现拒绝，再增加严格 Q4 plan/envelope/result/marker/seal 接线；正常 Q2 合同、
原始资源和时间、独立停止、同 MainPID 与原双流证据保持。详细诊断和验证见取消场景说明。
修复仅涉及测试交接入口及其测试，没有恢复已退役 H07 实验。

- 源码候选：`5ca9753cc777c246cdabe99e4a00f92078b0df08`。
- Git tree：`648a3aa484cc06d0369e71c522c20501db51f665`。
- 普通 CI：[36696638094](https://github.com/kongbu0621/infra-local-hand/actions/runs/36696638094)，
  push、attempt 1，已核实 HEAD 等于上述源码候选，**3/3 jobs SUCCESS**。
- 本地相关回归：167 passed、1 skipped；独立复跑新增 handoff 测试：22 passed。
- 新候选 CI 和两平台实际下载产物均已核验；此前 `28ac716` 产物仅为修复前基线。

| 验证范围 | 本候选准确结果 |
| --- | --- |
| Linux 源码测试 | 3265 passed、51 skipped |
| Linux 独立 root collector | 16 passed、0 skipped |
| Linux 独立安装态 | 94 checks PASS、292 commands，整体 PASS |
| Windows 源码测试 | 1131 passed、1057 skipped |
| Windows 独立安装态 | 9 checks PASS、1 SKIP、10 commands，整体 PASS |

Windows 安装态跳过的是 POSIX SSH fixture 的 CLI Git transport；未将该项算作通过。
源码测试数、安装态检查数和真实主机资格分别记录。

## 准确产物与来源绑定

产物核验按实际下载 ZIP 的 GitHub SHA-256 和大小、准确 Git blobs、wheel metadata、完整
payload 成员、RECORD，以及独立安装报告与各命令双流摘要逐项进行。
源码测试计数来自同一 HEAD/run/attempt 的 job 日志，运行身份来自 GitHub API，单独核实。
安装态测试明确 `fixture_only=true`、`physical_node_tested=false`，不等于现场 systemd 验收。

Linux 装配使用准确 Linux artifact，实际通过 `q2_prepare_build.verify_wheel()`。
Windows wheel 独立核对源码和 RECORD 一致，但其 CRLF metadata 被现有 Linux 严格检查器
拒绝为 `BUILD_DISTRIBUTION`；保留该拒绝，不替换文件或放宽检查器。
未配置 Plugin 逐成员对应源码，连接状态保持 `UNCONFIGURED_E4_REQUIRED`。

| Linux 对象 | 准确标识 |
| --- | --- |
| artifact | `11088696405` / `local-hand-Linux-36696638094-1` |
| artifact SHA-256 | `bd9822e3e7eeef1d6baaf43ef19650fe6b04275ff7a3ac1893580da8e655bff1` |
| wheel 成员 | `dist/infra_local_hand-0.2.0a1-py3-none-any.whl` |
| wheel SHA-256 | `64e73a11c23e1e59b4e0500268043539697afe22b405633f677b236689ed3111` |
| 完整 payload 摘要 | `f75a18f2b7b8d52dadb51285e0a7ae392541076855164e85aac45b7abcc4972e` |
| 未配置 Plugin ZIP SHA-256 | `d7eb1f63c03d775cc35dd6761e0a0d970ec8d7b7462f58b42b114588d6241ad2` |

完整两平台结果见 [CI 与产物核验](evidence/candidate-handoff-5ca9753/ci-verification.json)，
清单见[来源对齐](evidence/candidate-handoff-5ca9753/source-alignment.json)。它们是来源核验材料，
`is_runtime_fixture=false`，不是现场安装收据或可执行 fixture。现场安装和装配仍需真实观察，
不能把清单填进旧运行后直接重试。

| 接口 | 正确来源字段 |
| --- | --- |
| `install_candidate()` 安装收据 | `source = {root, commit, tree, files}` |
| `assemble()` 输入 | `source = {root, commit, files}` |
| 嵌套 launcher | `source = {commit, files}` |

本候选有 148 个 host-loader Python pins、74 个 admin Python pins、50 个 installed Python
pins；wheel 含四包的 53 个 payload 文件。测试入口不在 wheel 中，现场须保留准确受保护源码。
本次 owner 修复改变 host-loader pin，因此旧安装 receipt 不能只改 commit 后继续使用。

实际安装后还须绑定新 `installation.files/payload_digest/programs`、admin `package_files`、
入口及原生 quota FD 查询程序/ABI、Python device/inode、`peer.runner.sha256`、查询的
`installation_digest`，再形成 policy/request/assembly/fixture 摘要。既有 quota 查询器与已退役
实验不同；本轮仅固定其源码，未执行编译或安装。

## 现场装配输入

下表是事实清单，不含假路径、假 inode、预填 InvocationID 或可消费的运行窗口。
完整字段合同以 `tests/e3_host/q2_prepare_assembly.py::assemble` 和 `q2_prepare_run.decode`
为准。正常链与取消场景分别提供真实身份、资源、账本、原预算和一次性操作。

| 输入组 | 需要的准确事实 | 当前状态 |
| --- | --- | --- |
| source / installation / admin / python_identity | 本候选安装收据、实际程序摘要、ABI、解释器 device/inode | 源码清单已固定；现场安装未取得 |
| identity | preparation/operation/authority/manifest/principal/session/ledger 等本次身份及摘要 | 两个场景分别形成，不复用旧受理 |
| ordinary | 专用 uid/gid、普通父 cgroup pin、初始 user namespace pin | 当前动态观察待取得 |
| paths | broker、authority、policy、profile、endpoint，以及 journal、阶段输出、各层声明和证据目录 pin | 按角色准备：空的专用输出目录、已保存的准确 policy、已初始化的本次 ledger；保护正确且无物理别名，不清空旧路径 |
| slots / store | 两 slot × work/evidence/temporary，加 retained store；七个 project quota domain | 每根需 FS UUID、project ID、device/inode、上限、计费/执行状态 |
| capacity | 文件系统容量、所有已有承诺、retained 占用、管理 CPU/内存/PID/输出与存储 | 须包括历史未释放义务；CI 不提供此证明 |
| management | admission/query/collector 额度、receive/stop/accept 时限及连接数 | 使用原预算和原停止余量 |
| controllers | target/supervisor 静态 spec，以及 controller/query/management/supervisor 父级 pins | 与 ordinary 分离，不声明未来运行身份 |
| setpriv / original_budgets / limits | 实际程序摘要，原 wall/CPU/memory/process/storage/log 额度，policy 限额 | 每场景独立核定，不能事后补量 |
| 外层 owner | 当前 boot、原 issued/deadline、输出/声明目录、资源预算、现有管理入口及原客户端双流 | 不在 assemble 输出内；必须另行准确绑定 |
| 独立停止与复核 | 普通任务、query/management、target、supervisor、管理 endpoint 的各自停止者与证据 | 每层分别证明，外层退出不能代替内层清理 |

既有 11 项历史来源补证及维护记录继续作为历史事实复用，不重复相同采集。
boot、UID、cgroup/InvocationID、FS 使用量、根身份和新安装属于当前动态事实，须重新观察。
原首次远端边界、完整计费和 FS 资格的未完成结论仍保留；本次源码交接不替代这些现场证明。
旧冻结 runtime、已消费次数、原绝对截止和原预算不会因新候选而重置、续期或转移。

## 装配与运行顺序

1. 在既有受控准备入口内，核对准确源码和 Linux wheel，再使用原有界命令执行器完成本次
   隔离安装。`q2_prepare_build.py` 的 CLI 本身只返回 `ORIGINAL_PREPARATION_REQUIRED`，
   不能当安装命令；本轮未调用 `install_candidate()`。
2. 收齐现场事实，正常链选 `local-hand-q2-assembly-facts/v1`；独立取消场景选
   `local-hand-q4-cancel-assembly-facts/v1`，调用纯函数 `assemble(real_facts)`。
   它生成 policy/resident/chain/launcher/supervisor_template，不创建账号、服务或 quota。
   随后在原受控准备预算内，以既有 create-only 写入组件保存准确 policy，再以真实 ordinary
   身份调用既有 `initialize_ledger(policy, ledger_id)`，核验准确 `broker_root/jobs.sqlite`
   的路径、身份、初始化结果并保留收据。Q2 preparation driver 已有相应步骤；Q4 必须明确
   绑定自身事实和收据，不能假定 `assemble()` 自动持久化或旧 Q2 driver 自动准备取消账本。
3. 使用该模板、supervisor parent、本次独立 owner 输出/声明目录及原 owner 预算形成私有计划。
   计划字段固定为 `schema,purpose,preparation_id,boot_id,template,supervisor_parent,output,declarations,owner_envelope`。
   正常计划是 `local-hand-q2-original-handoff/v1` / `ONE_ORIGINAL_Q2_HANDOFF`；取消计划是
   `local-hand-q4-cancel-original-handoff/v1` / `ONE_ORIGINAL_Q4_CANCEL_HANDOFF`。
   旧 `q2_prepare_driver` 仍是 Q2 provisioner，不把旧已消费准备计划转换为取消计划。
4. 由原管理 endpoint 使用固定命令形状
   `<已固定Python> -I -B <受保护源码>/tests/e3_host/q2_prepare_run.py --plan <本次私有计划> --sha256 <原文件摘要>`
   交接。这只是参数合同，不是含现场值的执行命令；该入口没有 `--execute` 参数。
   内部固定 `--bind` 在 supervisor 的同一 MainPID 绑定真实身份、
   前检并进入监督。另开 shell 跑一次前检不能替代这一过程。
5. **先运行正常链** preflight→business→evidence，复核原普通及管理进程身份、实际终态、
   无待处理 Job、父级树空、原客户端退出及双 EOF、各层封存。`CHAIN_CLOSED` 或
   `CONTROLLER_CLOSED` 单个字段不是 Q3 验收通过。
6. 正常链独立复核后，再进入另一份独立资源的固定取消场景。只有真实原 helper RUNNING
   且原期限仍有余量时，同一 owner 调用一次 `broker.cancel`；自然先结束记为
   `NOT_EXERCISED`，不加延迟、循环重试或刷新窗口。
7. 复核原证据和摘要；`q2_evidence_review` 已支持 Q4 controller 证据，但它不能自证外层
   supervisor 或管理 endpoint 退出。取消命中、helper 停止、普通任务清理和整体验收分别登记。

## 预算、诊断和退出结论

owner 仍最多 120 秒，CPU/内存/PID/存储/输出全部计入既有容量；target 和 supervisor
依次保留原停止余量。正常三个阶段沿用同一 operation 的总预算，阶段切换不重新发放。
取消虽然只有单 preflight，静态装配仍保守计入完整链和七个 quota domains，不因未执行
阶段退款。Q4 helper 的执行期限先扣除 phase 原停止余量，记录期限再从其中预留原 grace。

取消诊断至多 24 条 / 4 KiB，场景报告至多 16 KiB、4 条停止记录；4 条记录不表示 4 次运行。
原时间、执行身份、取消顺序、投递/停止/ACK、退出/流、账本和保留资源分别记录；超限和
缺证据明确保留不完整状态。外层既有诊断记录失败阶段、异常类型和 errno，不记录敏感正文。

Q4 外层成功只表示 `SUPERVISOR_CLOSED`：仍有 `ordinary_phase_closed=false`、
`independent_ordinary_cleanup_required=true`，不调用正常 phase closure，不退款。
已投递未确认的启动仍可能迟到，由原独立停止者继续处理；UNKNOWN 保留对应占用。
`owner_self_exit_verified=false` 与 `original_management_session_exit_required=true` 保留，
最后一层退出必须由持有原客户端和流的调用者证明。Q2/Q3/production accepted 不自动变真。

## 现场接续：已恢复的材料与最小下一步

后续接续已恢复现存私有历史归档，并单独恢复 2026-09-29 的 rerun3 原始回执。
历史 Git 检查通过，1183 条逻辑索引对应的 824 个内容对象均按长度和 SHA-256 核对一致；
rerun3 的 32,439 bytes 及摘要也与已发表的补证完成记录相符。
历史归档只覆盖其自身检查点，后续独立回执不冒充已包含在旧归档内。
机器地址、原始配置、控制正文和私有对象路径继续私有保留。

旧 Q1 机器导出早已收到，为 `EXPORTED / 28 OBSERVED`；既有 11 项来源补证也已完成。
二者均不需要重新采集。新的现场事实应只针对会变化的状态，以及本候选尚未存在的安装。
已恢复的真实安装收据对应旧源码 `9a5563`，不能作为 `5ca9753` 已安装的证明。

接续复核确认：旧准备、恢复及 CPUQuota 重试的已消费状态不变；唯一未发行的旧 startup
计划绑定其冻结候选和自身范围，不能通过替换源码 SHA 转给 `5ca9753` 或取消场景。
新候选的真实安装、独立状态、累计成本与运行次数需要准确的后续计划，不能从历史空表、
未使用根或 CI 通过推导出新的运行额度。该约束不阻止既有 CLOSED 开发范围的修复或只读核对。

下一份现场任务只确认入口和少量当前状态：沿用此前原 PRO6000 的本地 Codex 接单与私有
回传安排。用户随后提供的本地回执截图表明原 guest 是无交互控制台的后台 QEMU；
上一版把已有控制台作为必要条件并禁止新建 SSH，使任务无法接续，现纠正该交接限制。
本地 Codex 可只读核对已知启动参数和既有 SSH 配置，确认固定目标后，使用已有凭据和
严格主机密钥校验建立一次有界只读连接，读取 guest 身份、boot、PID 1、版本和准确普通
user-manager 状态。没有可确认入口或连接失败时记录实际缺口；不执行旧 wrapper、
启动服务、改变认证配置或回放旧采集。该修正不签发旧批次或扩张安装、配额、生产范围。
通用 probe 的固定历史 blocker 不能替代当前候选判断；root 会话也不能冒充 ordinary 身份。
此任务不安装软件、不改权限/配额、不生成消费 marker，不等于完整 fixture 前检或实机验收。

本轮未执行 SSH、主机安装、账号创建、quota/cgroup 修改、真实任务提交或退役实验。
下一步是取得准确现场安装与装配事实，完成正常链真实验收，再做固定取消及其余故障验收。
本文件的后续文档提交不改变上述 CI 候选 SHA；新增源码须另建准确候选和证据。
