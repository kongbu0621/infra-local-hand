# 固定 helper 取消场景

本次补齐独立的测试入口：在唯一 `host.inspect` 请求的 preflight helper 已被现有执行器观察为
RUNNING 后，由同一 owner 调用真实 `broker.cancel`。它复用现有 Broker、SQLite、systemd
执行核心、管理单元和独立监督者；不属于产品命令，也不激活生产后端。

本轮源码工作属于已 CLOSED 的 `LH-E3-QUOTA-HARNESS-v1`（准确基线
`415327ebdcc251bb055da9931a7a88990f750b7a`）Q4 H06–H13，接续 Owner 对
[现有 systemd 修复](SYSTEMD_CANCELLATION_REPAIR.md)和[固定取消入口](SYSTEMD_ACCEPTANCE_HANDOFF.md)
的同意。没有新增主机操作或修改已退役原生实验。

## 固定入口与装配

| 对象 | 固定合同 |
| --- | --- |
| 静态装配事实 | `local-hand-q4-cancel-assembly-facts/v1` |
| 静态装配输出 | `local-hand-q4-cancel-static-assembly/v1` |
| 独立监督声明 | `local-hand-q4-cancel-supervisor/v1` |
| launcher 声明 | `local-hand-q4-cancel-launcher/v1` |
| resident 声明 | `local-hand-q4-cancel-resident/v1` |
| 场景快照 | `local-hand-q4-cancel-snapshot/v1` |
| 场景证据 | `local-hand-q4-cancel-case/v1` |
| 原始外层交接计划 | `local-hand-q4-cancel-original-handoff/v1` |
| 原期限交接声明 | `local-hand-q4-cancel-issued-handoff/v1` |
| 独立监督返回标记 | `local-hand-q4-cancel-supervisor-handoff-result/v1` |
| 外层交接结果 / 封存 | `local-hand-q4-cancel-handoff-result/v1` / `local-hand-q4-cancel-handoff-seal/v1` |

监督、launcher 和 resident 的 purpose 都是 `ISOLATED_Q4_CANCEL_HELPER`。
原 Q2 正常链的 schema、权限和完整关闭判据保持原义。

`q2_prepare_assembly.assemble()` 接受新的准确事实 schema，生成单 preflight 声明及新的私有
policy。该 policy 显式赋予同一合成 owner 既有 `lh:cancel` 能力，并重新生成 policy/request
摘要。它不修改旧 policy，也不使用旧请求。既有容量检查仍保守计入完整装配；未使用的声明
不构成退款或再次运行许可。静态装配只处理提供的真实事实，不创建现场资源。

继续使用 `q2_resident.py`、`q2_launcher.py`、`q2_supervisor.py` 的受保护入口；新模式明确
绑定 `q4_cancel_case.py` 和 `q4_cancel_runtime.py` 的源码摘要。resident 的 `cancel_case`
只能指向固定相邻模块，不能接受任意脚本。正常安装 wheel 不包含这些测试文件。

### 外层交接接线修复

候选装配复核发现：内部 supervisor/launcher/resident 已支持上述取消场景，但
`q2_prepare_run.static_template()` 仍只接受 Q2 正常链。旧入口实际拒绝新的取消计划并返回
`HANDOFF_SCHEMA`，因此仅完成内部场景不足以从现有管理入口启动。

本次在原入口增加显式 Q4 family：计划 purpose 为 `ONE_ORIGINAL_Q4_CANCEL_HANDOFF`，
其模板、launcher、单 preflight resident、issued envelope、child result、marker、summary、
reservation、result 和 seal 必须属于同一场景。正常 Q2 的合同不变，两个场景不能混搭。
旧 `q2_prepare_driver`、startup retry 和 reconciliation 仍仅消费原 Q2 合同。

真实装配仍须先提供独立的取消场景事实，经 `q2_prepare_assembly.assemble()` 生成模板，
再形成上述原始外层计划。此接线不提供新资源，不把旧 Q2 provisioner 变成取消 provisioner，
也不把已消费批次转换成 Q4。原管理 endpoint、同 MainPID、受保护来源 pins、create-only
记录、最多 120 秒 owner 期限、原停止余量、原客户端及双 EOF 判据均沿用原实现。

Q4 外层结果与封存明确 `ordinary_phase_closed=false`、
`independent_ordinary_cleanup_required=true`；监督服务关闭不能代替普通任务的独立清理。
原管理 endpoint 的自身退出仍由调用者持有原客户端和流来证明，结果继续保留
`owner_self_exit_verified=false`、`original_management_session_exit_required=true`。
该修复在现有 CLOSED Q4 范围内，不新增实验轮次或生产资格。

本次外层交接定向回归为 **167 passed，1 skipped**（7.54 秒），覆盖 Q4 handoff、
既有 owner、Q4 contract/runtime、原 preparation driver、supervisor、evidence review 和
reconciliation collector。独立复跑新增 handoff 文件为 **22 passed**，独立只读审查
未发现阻塞。首次局部回归曾因旧诊断测试替身缺少 schema 而失败，补齐替身合同后通过；
跳过项未计入成功。实际命令为 `python -B -m pytest -q -p no:cacheprovider`，后接上述八个
`tests/test_e3_*.py` 文件；未使用真实主机服务、账户或 quota。这些结果不替代新候选 CI。

## 一次请求及有界日志

观察子类透传实际执行器结果；不改写 OS 观察，不替换原生命周期算法。只有准确原 helper
RUNNING 且原期限有余量时，才唤醒一个本地控制线程，最多调用一次真实取消 API。
请求 ID、request digest、owner 和 policy 均沿用原受理记录。

场景日志记录原时间、执行身份、取消事件顺序、实际投递、停止请求及 ACK、原 helper
退出和流状态、账本状态与保留资源。日志有固定大小上限；超限明确记为不完整，不无限增长。
其中不保存密钥、环境变量全集或工作文件内容。

取消命中须有原 helper 仍非 terminal、原 deadline 前的实际 stop 交付证据。
RUNNING、取消 API 返回和 StopUnit ACK 都不能单独证明退出。观察到原实例终态、无待处理
Job、原父级为空、原客户端退出及双 EOF，才沿用实际核心的退出结论。自然结束抢先发生时
记录 `NOT_EXERCISED`；不延长任务、不注入休眠、不自动重试。

观察窗口以执行器实际 helper 期限为准（它已从 phase 总期限扣除原停止余量），再从其中
预留一次原 terminate grace，用来保存证据和结束通信；没有新增时间预算。
完成的 case 快照按观察时点冻结，后续通信只重复该快照。它不证明该时点之后的
所有状态。存在已投递但未确认的工作时，仍需原独立停止者负责后续观察和清理。

## 结果含义

`CANCEL_CASE_RECORDED` 只表示场景记录完成。报告分别表达行为是否命中、helper 退出是否
证明、业务账本状态和资源是否仍被占用。取消抑制 reader 后，不能伪造它的退出或套用正常
`PHASE_CLOSED` / `CHAIN_CLOSED`；此路径不发送 `close`、不调用 quota phase closure、
不释放两本账中的原保留资源。

外层监督仍须独立证明原 controller 的停止、客户端退出和双 EOF，才能封存。
外层退出、离线文件一致性、helper 停止、业务关闭和生产资格是不同结论；报告继续保留
`q3_accepted=false`、`production_supported=false`。失败记录保留已取得的证据。

## 验证和现场边界

本地验证覆盖真实 policy/request 装配、真实 Broker/SQLite 的取消和资源保留，以及采用明确
OS/传输替身的停止时序、错误、版本和结果一致性负例。这些测试不等于实际 systemd 验收。

2026-09-30 内部 driver 候选当时的本地集成回归：**668 passed，3 skipped**（37.04 秒）。范围为当时新增 Q4
测试、既有 Q2 harness 测试、resident/chain、quota lifecycle 和 runner；三个跳过项保留。
其中新增取消用例覆盖取消已提交但 API 尚未返回、读账本期间取消完成、停止命令发出前失败、
原 ACK 丢失、自然先结束、缺 RUNNING、日志超限/日志异常、预算/owner/原实例冲突，以及旧新
报告混搭。独立只读审查未发现剩余阻塞。没有真实 Linux systemd 或 Windows 运行结论；
Windows 分支的导入保护不替代实际 Windows CI。

上述计数属于外层交接修复前的内部 driver 验证；本次外层回归为前述 167 passed / 1 skipped，
准确新候选及其 CI、产物和现场交接见[最新候选记录](CANDIDATE_HANDOFF_20260930.md)。

当前没有与新候选匹配的现场 fixture，本轮不执行 SSH、安装、真实任务或主机状态修改。
实际运行仍须先核对新源码与 Linux wheel、真实安装和现场身份，以及两次场景各自的独立
资源、预算、使用次数和停止责任；先完成正常链并独立复核其证据，再运行此取消场景。
旧运行额度、原截止和历史未完成结论保持原记录。不能将新入口当作放行证明。

平台拦截的内部原因没有原始证据，不能归因于文件命名。本轮也不尝试规避检查；采用的是
既有产品取消路径的有限测试实现。
