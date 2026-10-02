# Q2 三项门槛：本轮实做、验证和补充方案

2026-10-02 +08:00。本轮在已有 CLOSED 范围内核对源码、修复实际偏差并完成离线反例。
本记录接续[上轮缺口复核](Q2_FIELD_GAP_REVIEW_20261002.md)，不产生现场发行或新的 Owner 决定。

## 实际完成与验证

1. **FILETYPE 漏检修复。** 当前旧生产者准确 A 要求 ext4 journal/filetype；
   已有 `_geometry` 检查 HAS_JOURNAL 和 EXTENTS，却接受缺失 FILETYPE 的合成 superblock。
   本轮仅收紧已读取 incompat 字段的 `0x2` 谓词，保持原来源、权限、拒绝规则及窄 profile。
   缺 bit、compat/rocompat 同值 bit 不能冒充，以及合法 FILETYPE/EXTENTS 的正反例均通过。
   EA_INODE 等既有拒绝反例保留全部必需 bit，避免被新检查提前拦截而掩盖原检查。
2. **H07 全域离线检查。** 新增 53 条固定义务/反例边，绑定请求、意图、Job/Invocation、
   原 client、各自双钟、原截止及共享预算；首次新增 29 项，顺序复核后共新增 31 项反例。
   原 v1 八个函数的 AST 不变。新模型没有实际 fence 或执行入口，
   旧 probe/独立 collector 只是保留反例；本批次候选仍要求唯一 SSH 的同通道收集。
   独立审查发现 stop ACK 前快照及迟到入队/实例绑定会误删局部缺项；实际 4 项失败
   反例保留，修复后旧快照失效，只接受 ACK 后未被更新事件失效的局部观察。
3. **FS2/FS3 静态复核。** 已有来源索引、准确 feature 谓词和两个落盘路径的操作/首错表
   见[文件系统工作单](Q2_FS_QUALIFICATION_WORK_ORDER_20261002.md)。
   合成峰值、端点 G 和真实组件 IO 均未冒称原机资格，未实施 consumer 写入路径仍单独标出。
   [FS4/FS6 属性与同步核对](Q2_FS_ATTRIBUTE_SYNC_SOURCE_REVIEW_20261002.md)补上九条
   准确源码映射，包括 default/access ACL、创建结果、五次同步、读回及首错留存的限度。
4. **namespace 最小设计。** 原终端启动固定 G，持有直系 R/O 的进程与 namespace FD，
   在固定本地匿名通道中交叉核对；明确新增终端/执行端点来源前提、读取边界和预算。
   方案只证明该活体观察器会话，不转给另一个 PID、将来窗口或 Q2 consumer。

支持 Python 3.12.14 / pytest 8.4.2 的 13 组整合回归：
首次为 **649 PASS / 21 SKIP / 0 FAIL**，6.59 秒；顺序修复后的完整同组回归为
**651 PASS / 21 SKIP / 0 FAIL**，6.62 秒。21 项是既有 root 专用 protected-record 测试。
普通 writer 的真实隔离 syscall 组已执行；四份源码在测试前后摘要完全相同。
本地未手工重复全库；完整源测试由准确候选的 CI 完成，不借用上轮统计。
准确源字节、私有 log/JUnit 的长度/摘要、
原批准文档摘要及结果在[验证索引](evidence/q2-field-gap-20261002/verification.json)。
[顺序修复验证](evidence/q2-field-gap-20261002/closure-order-verification.json)追加保留失败与最终字节，
不覆盖首次结果。[H07 独立定向复核](Q2_H07_CURRENT_ROUTE_OFFLINE_REVIEW.md)最终
114 PASS 是整合回归子集，不重复累计。

FILETYPE/首次 H07 源 D 为 `38a9e15697469f6590e54ddd89754a5d3344f23e`；
顺序修复 D 为 `b707f1b0a4755aa0b2b6455d53ea8eae641182cd`，tree
`055aa585817f3d46f56275c224eba0e4b2734c6b`。两份提交、验证产物和准确 Git source
映射见[独立提交登记](evidence/q2-field-gap-20261002/committed-source.json)。
首次 D 的 [CI 37005186888](https://github.com/kongbu0621/infra-local-hand/actions/runs/37005186888)
已 3/3 SUCCESS：Linux 3781 PASS / 51 SKIP、root collector 16 PASS / 0 SKIP、
installed wheel 94 checks / 292 commands PASS；Windows 1465 PASS / 1173 SKIP、
wheel 10 checks / 10 commands PASS。
[准确候选 CI 记录](evidence/q2-field-gap-20261002/source-ci-38a9e15.json)不覆盖后续顺序修复；
后继源码的 CI 必须另定位准确 head，不能借用这次 PASS。

顺序修复和六份文档登记一起推送后的准确 head
`41309e2369ddad201ecc7a27c965028d820fecf4`，tree
`c142963b33494da9eed1f121e59cb822ad8bf1be`，其
[CI 37007087897](https://github.com/kongbu0621/infra-local-hand/actions/runs/37007087897)
已 **3/3 SUCCESS**：Linux 源码 **3783 PASS / 51 SKIP**，root collector
**16 PASS / 0 SKIP**，wheel **94 checks / 292 commands PASS**；Windows 既有范围
**1465 PASS / 1173 SKIP**，wheel **10 checks / 10 commands PASS**。
[最终 CI 索引](evidence/q2-field-gap-20261002/native-ci-41309e2.json)登记原始私有 API/log
的 bytes/SHA，以及 b707f1b→41309e2 的源码/build/workflow 无变化映射。
后续 FS4/FS6 和本 CI 摘要为文档补充；CI 结论仍精确归属 41309e2，不扩大为实机资格。

上轮准确 `6cce996d17ccde1aa4fe48feaaa4cec226d834c0` 的
[CI 37000830396](https://github.com/kongbu0621/infra-local-hand/actions/runs/37000830396)已完成，
3/3 SUCCESS：Linux 源码 3751 PASS / 51 SKIP、root collector 16 PASS / 0 SKIP，
wheel 94 checks / 292 commands PASS；Windows 既有平台范围 1465 PASS / 1173 SKIP，
wheel 10 checks / 10 commands PASS。
[准确 CI 观察](evidence/q2-field-gap-20261002/prior-native-ci.json)仅对应该提交，
不覆盖本轮新增源码，不扩大 Windows/A2 支持。

## 准确授权和补充文档

FILETYPE 收紧属于原 CLOSED H2/H4 及当前 A 对 journal/filetype 的明确要求；
H07 纯检查属于原 CLOSED H1/H3/H4，仍无来源采用或实际资格。
R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 已由本轮 executor 直接读取，
SHA-256 与保留 pin 一致。原旧生产者 A
`68424df2ddbf812b9479ffa7a64dcaa59a2a9f76` 三文档字节保持；
独立 C `179652cb9487163d83c004d358e4d4b49409694c` 和旧失败均保留。

namespace 新增读取来源及信任用途不能从已接受的 storage premise 推出。
其三个补充文档是：
[需求](q2-namespace-reference/REQUIREMENTS.md)、
[架构](q2-namespace-reference/ARCHITECTURE.md)、
[实施计划](q2-namespace-reference/IMPLEMENTATION_PLAN.md)，
scope `LH-Q2-NAMESPACE-REFERENCE-v1`，状态 **PROPOSED / OPEN**。
拟闭合范围限 NS1–NS2：独立有界 collector 合同与隔离验证。
原终端实际 local-only 采集 NS3、consumer 采用 NS4 均 excluded，另需准确后续批准；
其后也不能替代 P4。
[设计论证](Q2_NAMESPACE_REFERENCE_DESIGN_20261002.md)固定新增来源前提及技术结论的限度。
准确提案 A 为 `dfdd653dd48388d8ab1a2554d16bf5b610edba10`；
[基线登记](../governance/Q2_NAMESPACE_REFERENCE_BASELINE.md)固定三个 authoritative SHA。
尚无该范围 Owner B、C 或新 collector 源码。

## 仍需成立的实际条件

H07 仍缺首次远端前已经生效的保护、全程 rate/pause 上界、服务端未决/迟激活终结
以及实际完整域的独立 stop/exit/双 EOF；现有 runtime 的 stage 证明没有扩大为全机证明。
两个 parent 仍缺实际适用设备/构建/创建峰值/隐式费用/存储和完整审计账单。
namespace 的独立原终端来源及实际 FD 对照也尚未采集或采用。

已有授权内的原件映射和严格条件证明可以继续。
需要新增设施的 H07/FS 方案先固定真实候选原语和来源，不能请求“任选机制”的空白许可；
已具体化的 namespace 三文档则可独立审查准确 A 和 NS1–NS2。
本轮 `field_ready=false`、`allow_run=false`、`guest_executed=false`，
真实正常链计数 0；没有新系统配置、host 消费对象、guest 连接、可执行 ZIP 或 `TASK.txt`。
