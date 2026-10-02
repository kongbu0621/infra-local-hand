# H07 当前路线的纯离线资格合同复核

2026-10-02 +08。本轮补齐已有来源的固定域/请求边及合成缺口检查，
不新增监督机制、来源采用、权限、现场读取或生产入口。H07 真实资格仍为
UNKNOWN，`field_ready=false`，`allow_run=false`；未形成可执行 P4 交付。

本轮工作区基于 `6cce996d17ccde1aa4fe48feaaa4cec226d834c0`。
下列 SHA 固定本轮受测实现字节；最终提交 D 由独立集成记录定位，
本文不预写尚未形成的提交身份。

| 受测文件 | SHA-256 |
| --- | --- |
| `tests/e3_host/q2_host_window_h07.py` | `a54a3a52a340f4a3d2478ebd7c670098bfcbf62f32a005380cec26917fa85faa` |
| `tests/test_e3_q2_host_window_h07.py` | `b26aad838fa3ff558315a0cc27e804a70db80e68c873b4bdb85de4971c2ff921` |

本轮 executor 已读取当轮直接取得的固定 R
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 完整原文，其 SHA-256 为
`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
本交付属于原 CLOSED H1/H3/H4 的纯数据证据合同及反例范围：H A
`8402f0cc82d8a0ac0b9a56716bf276f41cafea37`、C
`271c07cd16140aa5942dcf3fad468003c58b6b0e` 保持不变。
[既有资格复核](Q2_FIELD_QUALIFICATION_NEXT_REVIEW.md)明确允许此范围内准备
H07 逐域合同和已有材料映射。旧生产者 A
`68424df2ddbf812b9479ffa7a64dcaa59a2a9f76` 的 P2 限制及独立 P4 event
要求未被本交付改变。

原 v1 的八个既有函数逐一与本轮工作区基线进行 AST 比较，body 均未改变。
`review_h07` 的字段/输入合同及原两边模型保持；新增 API 和 schema 独立存在于
同一个已纳入源码闭包的测试模块，不成为生产 dispatcher 或运行入口。

当前 [system-manager 架构](q2-system-manager-repair/ARCHITECTURE.md) 已经要求
原请求、原 Invocation、无未决启动、stop ACK、client exit、双 EOF 和完整父树，
并把普通子 slice 固定为 controller-parent 内 target 的兄弟。新合同复述这些
既有职责和 geometry，不据此宣布实际 host 已有合格监督。

固定图共 53 条义务/反例边，覆盖 host SSH 和 guest 会话、loader/outer/owner/
supervisor/target/gateway、三 phase 的九个 ordinary stages、管理控制端、
listener/admission/query、bootstrap 请求与 worker handoff，以及 query 的既有
native 子进程：preflight/business 各三个 root，evidence 四个 root。
这里的 native 是现有 quota-query 子程序，未恢复已经退休的 cgroup spike。
stage 名称按实际协议使用 `bootstrap/helper/result_reader`。

这张图是已有来源义务与保留反例的保守集合，不是已部署或已观测的全图。
每条边标记 coverage：旧 `first_probe`、独立 host/remote collector 是
`RETAINED_LEGACY_COUNTEREXAMPLE`；首次派发保护、stop-finalizer 和同通道证据
流是未证明的资格义务。准确 `20261002a` A 的候选拓扑要求一条 SSH 内完成
bootstrap、正常链、停止和收集，禁止第二 SSH/单独补 collector；合同明确保留
这一限制，不把旧反例边变成新运行步骤。完整实际域仍需准确现场证据核对。

`qualification_contract` 只复算固定图与既有 geometry/次数上限。
`review_qualification_model` 仅接收供模型使用的 trace bytes 和外部独立提供的
clocks、requests、budget pins；它们都属于未认证合成输入。严格绑定包括：

- 固定完整边集合及原 request/intent/command 摘要，禁止缺边、重复边或换请求；
- 各自 host/guest boot、本地双钟原点/原截止，以及每个请求的更小原截止；
- 原 Job、unit/Invocation、PID/start_ticks/cgroup dev/inode 和原 client 身份；
- gateway stage 的 original/manager client 分别退出和各自 stdout/stderr EOF；
- 原 budget ledger/预留摘要、各类用量及独立 stop/EOF/fsync/seal 余量。

两台机器的 clock 数值不相互比较。模型只在各自 clock 内检查倒退、到限和
继承的 2 秒样本差额诊断；这种诊断不证明整个运行期的 rate/pause 上界。
同一预留摘要的所有边费用累计到同一限额，不能为各边重复取得一份额度。
所有边、每边最多 20 events、输入/输出长度及严格 key/type/integer 上界固定；
没有任意图、任意命令、数据源调用或新增期限能力。

模型保留未观测原实例、stop 后迟到入队/绑定、普通 sibling 未关闭、收尾 endpoint
缺退出或任一 EOF 的缺项。即使所有合成观察看似完整，也逐边保留
`FUTURE_ADMISSION_FENCE_NOT_PROVEN`，全局 rate/pause、首次派发保护、
source admission 和真实 stop/readiness 标志始终为 false。没有支持的
FENCE/CLOSED 操作，Caller 不能插入一个事件自授准入。

定向验证使用私有 Python 3.12.14 / pytest 8.4.2、普通 umask 022 和隔离临时目录。
首次与末次均 **112 PASS / 0 SKIP / 0 FAIL**，分别为 4.35 秒、4.36 秒；
新增 29 项是其中子集，不重复累计。本轮没有发生失败，首次原始输出仍完整保留。
日志与 JUnit 留在私有验证目录，公开仅记录摘要：

| 验证原件 | SHA-256 |
| --- | --- |
| first log | `e5b9c8f0a53c92937fb9c7dac71d091bce8b2d1196ba107766c94ac2bae2546b` |
| first JUnit | `5cf6c853b30528e1b6d03d176029ea8d8730dfa4e625863f95908fbc94ed942c` |
| final log | `5a8e182379465901e0b37de03cf4940148ab1f6da4a1bd993db828a6817d94af` |
| final JUnit | `ce693357783fbc18873bc7f33f31ae14ab94117df395302749287ed07c6c7244` |

反例覆盖丢回复后原实例不明、stop/空树后的迟到入队或激活、target 已关闭但
普通 sibling 仍运行、终态外观后 endpoint 缺退出/单流 EOF，以及请求/Job/
实例/client 漂移、缺边、原 deadline 倒退/到限、bool 整数、共享预算超额和
Caller 自报 fence。阻断 open/stat/process/socket/live-clock 操作的测试验证
新增 API 的纯数据边界。它不把模型来源变成可信现场材料。

`git diff --check` 通过。实际 gateway/lifecycle 的正常终态及丢 seal ACK
fail-closed 路径无需因本轮模型而扩大 runtime 修复。
完整集成回归由根执行器另行记录，本定向统计不冒充全源码或真实系统验证。

下一步可在已有 CLOSED 范围内将准确保留材料映射到该合同并审查缺项。
真正补足首次远端前监督、服务端迟到请求控制、全程 rate/pause 或新 FS 权威
来源若需要改变机制、来源、权限、配置、持久对象或冻结 runtime，则须先形成
准确受影响补充 A、Owner B、独立 C，再实施 D。纯模型不能替代该顺序，
不能清除 `E3_SUPERVISION_UNVERIFIED`、FS/峰值/持久性或 namespace 资格缺口，
也不能发行 P4。退休 native spike 继续退休。
