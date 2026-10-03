# Local Hand 核心实机验收交付：需求

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。
- Scope：`LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1`。
- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；其来源、完整性、Owner
  权限、无例外及变更规则沿用根 `AGENTS.md`。
- 本文与[架构](ARCHITECTURE.md)、[实施方案](IMPLEMENTATION_PLAN.md)是三份 authoritative
  documents；它们与[现场输入只读复核](../Q2_CORE_LIVE_INPUT_REVIEW_20261003.md)共同构成 A 的四份
  documents，同一 A commit 还冻结下述 projected-source artifact 与 artifact receipt bytes。
  当前没有准确 A、Owner B、独立 CLOSED C 或本 scope 的现场实施 D。

## 1. 准确 A 固定的静态值

下列值来自同一干净候选和两次逐字节一致的独立 wheel build。候选、wheel 或 manifest bytes
发生任何变化都须形成新的文档基线；这些值本身不授权现场执行。

| 固定对象 | 准确值 |
| --- | --- |
| 核心 candidate commit / tree / direct parent | `4b6e4a7c403362358192086b88679e1326dcb2e1` / `4d4349580c9f4b67cc26f601126849c2bc8d76a4` / `607100a57206f7dc7cfcbd6cae8507cfa599b813` |
| 唯一 wheel | `infra_local_hand-0.2.0a1-py3-none-any.whl` / `288375` bytes / SHA-256 `ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9` |
| canonical payload digest | `b4d094a9f70c308c63870c9fbf273b6b0646ad211d6f61a79901f52e67cf2e23` |
| [`.local-hand-source-projection.json`](../artifacts/q2-core-acceptance-20261003/.local-hand-source-projection.json) | `11811` bytes / SHA-256 `55f555fc225edca943b8c86cee8119c4878f5ec1e9503a084ba7a560cf2c991d` / `89` `files` entries |
| [`artifact-receipt.json`](../artifacts/q2-core-acceptance-20261003/artifact-receipt.json) | `1294` bytes / SHA-256 `f34baa40ceb3bbce99d02cfef1c8748990d9e405df7fe56d14c15cc8e49f3e5e` / two byte-identical builds / exact-hash-only reuse |

候选、wheel 或 manifest bytes 变化都须重新固定。现场 boot、既有父目录的绝对路径/dev/inode、PID、
InvocationID、cgroup inode、文件系统使用量及 unit 状态是 **C 后观察**；下文固定的 relative path、
logical ID、project ID 和 unit 派生规则仍是 A 的事实。

## 2. 请求 Owner 决定的最小现场范围

准确 A、Owner B 和独立 bookkeeping-only C 形成后，仅授权：

1. 通过一个既有、现场复核的固定管理入口，最多发出一次 carrier request；发出即消费，连接失败、
   响应不明或断开均不重发，也不另建连接补采。
2. 通过下述单一 field package 暂存并验证完整 clean candidate checkout、唯一 wheel 与 C 后 D code，
   create-only 建立一个受保护安装；运行安装只含 wheel、manifest 限定的核心 harness、现场编译并
   pin 的 native helper 和 C 后实现的 JIT dispatcher。
   已存在、部分存在或摘要/保护不符即停止，不覆盖。
3. 严格按 `H01_NORMAL` → `Q4_HELPER_RUNNING_CANCEL_SUBSET` →
   `H11_SAME_LEDGER_RECOVERY` 条件运行。
4. 三个 case 各有独立 case identity、authority、ledger、operation 和七个 quota roots，共三个
   ledger、三个 operation、二十一个 roots；per-operation grant/evidence、15 个 `lhj-*`、15 个
   dynamic quota units 和三对 target/supervisor 不跨 case 复用。唯一安装、ordinary identity 及
   locators 中的既有 parent unit/cgroup 按候选合同串行共享；进入下一 case 前必须证明前一 case
   tasks 退出、相关 child parent empty 且 parent identity 未变。
5. 只有前一 case 达到完整语义 PASS，dispatcher 才 create-only 发布下一 case 的绝对计划；不预发
   后续可执行计划，不跳序。

这不是旧批次重放，不继承旧运行次数、deadline、对象或安装。历史失败、UNKNOWN、lease 和容量
义务保持原结论。

### 固定 logical object set

本 scope 的逻辑 namespace 固定为 `lhqcore-20261003a`，不得由 D、现场输入或调用者换名。现场只把
它解析到 `locators` 中五个已鉴证且 held-fd 的既有父目录：protected state、quota、install、
journal 和 evidence parent；调用者不能提供其它绝对路径。安装 basename 固定为
`local-hand-core-acceptance-20261003a`，staging basename 恰为
`.local-hand-core-acceptance-20261003a.staging`。两者都在 install parent 下 create-only，任一已存在都拒绝。
三个 case 的
对象如下；任何 basename、project ID、operation ID、unit prefix 或目标已存在/已占用即停止，不寻找
替代值：

| index / case | case basename | preparation ID | operation ID | controller prefix | project IDs |
| --- | --- | --- | --- | --- | --- |
| 1 / `H01_NORMAL` | `c01-h01-normal` | `lhqc01h01normal` | `b6638120-ed28-4ed1-b603-a153fab1c93d` | `lhqcore20261003a-c01` | `12101..12107` |
| 2 / `Q4_HELPER_RUNNING_CANCEL_SUBSET` | `c02-q4-cancel` | `lhqc02q4cancel` | `ade1b42f-f03d-48dc-b690-e588b44289f6` | `lhqcore20261003a-c02` | `12108..12114` |
| 3 / `H11_SAME_LEDGER_RECOVERY` | `c03-h11-recovery` | `lhqc03h11recovery` | `4b035797-229a-4cdc-8eca-8195869b7ac9` | `lhqcore20261003a-c03` | `12115..12121` |

operation ID 兼容既有 UUIDv4 validator，但不由现场随机选择：先取
`SHA-256(ASCII("urn:local-hand:LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1:<case name>"))` 的前 16 bytes，
再把 byte 6 的高四位设为 `0100`、byte 8 的高两位设为 `10`，最后按 canonical lowercase UUID
编码；表中值是唯一允许结果。

每 case 的 identity seed 恰为 `ASCII("lhqcore-20261003a:<case basename>")`。`identity.id`
恰为该 seed 加 `:identity` 的 SHA-256 前 32 hex；`authority_id`、`profile_ref`、
`principal_id`、`ledger_id` 分别恰为
`lhqcore-20261003a-<case>-authority`、`lhqcore-20261003a-<case>-profile`、
`q2-synthetic-lhqcore-20261003a-<case>`、`lhqcore-20261003a-<case>-ledger`。`node_id`
恰为 `lhqcore-20261003a-guest`，三 case 共用的 `install_uuid` 以上述 UUIDv4
派生方式从 `urn:local-hand:LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1:installation` 唯一产生，结果恰为
`2ba06c6f-d3e5-4e36-a41f-d5991cdd7232`；
`deployment_epoch=generation=1`；`epoch`、`slot_generation` 分别恰为 identity seed 加
`:epoch`、`:slot-generation` 的 SHA-256 前 32 hex，`session` 恰为 seed 加 `:session`
的完整 64 hex SHA-256。`authority_digest`、`manifest_digest`、`expires_at` 及完整 policy
expected record 只能由冻结 D/package、当前准入和
不超过 owner deadline 的实际时间生成，并在首次 submit 前写入 plan；不得由
调用者输入。
表中 preparation ID 是 D adapter 唯一允许值，符合原字段 token 边界但不冒充旧 scope 的
preparation identity；不得从 identity hash 截取、随机生成或沿用历史 preparation ID。

每个 origin 的唯一请求恰为 canonical `lh-job-v1`：`operation_id` 取上表值、
`kind="host.inspect"`、`profile_ref` 取上述固定值、`inputs={}`、`expected` 逐字节来自已
冻结 policy，`expires_at` 不晚于该 case owner 绝对 deadline 的 realtime 映射；
`expected` 的 key 恰为
`node_id,install_uuid,deployment_epoch,profile_digest,policy_digest,registry_digest`。H01/H11
principal scopes 恰按顺序为 `lh:submit,lh:read,lh:evidence`；Q4 在同三项后只多
`lh:cancel`，不得给 H01/H11 cancel 或给任一 case 其它 scope。
`request_digest` 只能由候选 `contract.request_digest()` 计算并冻结。身份、请求或 digest 的
任意其他形状都不准入。
序列化的 case `index` 恰为 1/2/3；令 `ordinal0=index-1`。第 `j` 个 role（`j`
从 0 计）的 project ID 恰为 `12101 + 7*ordinal0 + j`。
每组连续七个 project ID 按 offset `0..6` 严格映射为 `work-a`、`evidence-a`、`temporary-a`、
`work-b`、`evidence-b`、`temporary-b`、`retained_store`。每 case 必须复用冻结 harness 的
12 个 directory role：`reservation,state,authority,journal,capture,declarations,session,control,
profile_work,profile_evidence,profile_temporary,store_parent`。它们的 relative path 恰为
`lhqcore-20261003a/<case basename>/<role with underscore replaced by hyphen>`；前八个按 role 分别
解析到 state/journal/evidence parent，后四个解析到 quota parent，不得改名或平铺到
同一文件系统。具体映射恰为：`reservation/state/authority/session/control` 属 state，
`journal` 属 journal，`capture/declarations` 属 evidence，四个 profile/store role 属 quota。
owner/mode 恰按冻结 harness 为：ordinary `0700` 的
`state,authority,profile_work,profile_evidence,profile_temporary,store_parent`；root `0755` 的
`control,session,declarations`；root `0700` 的 `reservation,journal,capture`。`capture` 下七个
child 均为 root `0700`；`launcher_declarations` 为 root `0755`，其余两个 declaration child
为 root `0700`。`policy.json`、`authority.json`、`jobs.sqlite` 均必须是 ordinary UID/GID、
single-link regular `0600` file。

`state` 是 broker root，其 ledger 恰为 `jobs.sqlite`；活跃时只允许 SQLite 自身的
`jobs.sqlite-wal`、`jobs.sqlite-shm`、`jobs.sqlite-journal` sidecar，封存 snapshot 前必须按冻结
StateStore 合同关闭/checkpoint，不得把 sidecar 丢失当成完整 ledger。`authority` 是
authority root，只容纳 ordinary UID 私有 `authority.json`、`policy.json`；
`ledger.initialized` 不是本现有 harness 会生成的事实，不得伪造。`authority.json` 内容恰为
`{authority_id,ledger_id,state_root}` 且 `state_root` 指向同 case `state`。`reservation` 只容纳
create-only `preparation-plan.json,preparation-result.json,authority.json,manifest.json,prepared.json,
handoff.json,case-plan.json,
empty-ledger-gate.json,phase-preflight-receipt.json,phase-business-receipt.json,
phase-evidence-receipt.json,ledger-export.json,case-verdict.json,h11-recovery-proof.json`；
`ledger-export.json` 只允许 H01/Q4 在 ledger 完整 checkpoint/close 后 create-only 产生，H11 必须
不存在；不适用 phase/H11 文件也必须不存在。ledger export 最多 1048576 B，并与这些 reservation
文件一起计入既有 state 8 MiB/1536-inode physical cap，不产生新目录、quota 或 storage budget。
两个 `authority.json` 不是同一对象：authority root 下的是上述 AuthorityLock anchor；
reservation 下的 preparation provenance 恰为
`{schema:"local-hand-q2-preparation-authority/v1",scope,baseline,plan_sha256,preparation_id,
receipt_sha256}`，它的 canonical SHA-256 才是 `identity.authority_digest`。
`preparation-plan.json` 必须是传给 candidate `validate_plan()` 的 exact plan bytes；
`preparation-result.json` 必须是 status=`RESOURCES_PREPARED` 且其 `facts` 被传给
`facts_from_observed()` 的 exact receipt bytes。成功 result 的顶层 key 恰为
`schema,preparation_id,plan_sha256,status,reason,facts,q2_accepted,q3_accepted,
production_supported,fixture_generated`；`schema="local-hand-q2-fixture-preparation/v1"`、
`reason=null`，后三个 acceptance/support boolean 与 `fixture_generated` 均为 `false`，且
`plan_sha256` 恰为 raw plan bytes 的 SHA-256。两者都使用 candidate
`q2_prepare_driver.encoded()`（canonical JSON + 单一 LF）。intent 先在 shared carrier 内持久化；
随后只可 create-only 建立 reservation directory，并把 raw plan 作为其中第一个文件写入、fsync
file/parent、同 inode 回读相等，之后才可创建本 case 其它 directory/root、配额、authority 或 ledger。
result file 只可在全部 observed facts 取得、七个 root 逐项重新鉴证且 adapter 要求的 retained
preimage 前后相等后 create-only/fsync/同 inode 回读；它必须早于 reservation provenance
`authority.json`、manifest、policy、ledger、prepared/handoff、case plan、owner 或 submit。
`authority.json.plan_sha256` 和 `receipt_sha256` 必须分别恰为这两个**已保留 raw file**的 SHA-256；
进入 output package 的 `preparation-plan`/`preparation-result` member 也必须直接读取同一 retained
filesystem object，逐字节/长度/摘要相等，不能从解析后的 object 重编码或从 core intent/case-plan
重建 preimage。core intent/case-plan 不是这两个 preimage。reservation 下
H01/H11 的 `manifest.json` 恰为冻结 system harness 的
`{schema:"local-hand-q2-preparation-manifest/v1",source,ordinary,roots,parents,boot_id,epoch,
system_geometry}`；Q4 采用 non-system route，manifest 的 exact keys 是
`{schema:"local-hand-q2-preparation-manifest/v1",source,ordinary,roots,parents,boot_id,epoch}`，不得
出现 `system_geometry`。各自 canonical SHA-256 是 `identity.manifest_digest`。两者必须通过
candidate `q2_prepare_driver` 的原 constructor shape/canonical encoding 生成，并由
`q2_prepare_assembly` 的 identity digest binding 消费；两处都没有可由 D 替换的独立 decoder，
D 不得声称存在一个或替换记录形状。
`capture` 下恰创建 `preflight,business,evidence,management_evidence,launcher_output,
supervisor_output,owner_output`；`declarations` 下恰创建
`launcher_declarations,supervisor_declarations,owner_declarations`。不适用 phase 的目录仍属固定
bounded harness layout，但不得伪造 case 证据。

root path 分别恰为 `profile-work/work-a|work-b`、`profile-evidence/evidence-a|evidence-b`、
`profile-temporary/temporary-a|temporary-b` 和 `store-parent/retained_store`，均在本 case base 内。
H11 的 result-reader unit 已在 collector start 前被真实交付；该 reader 在 origin 内可能已打开、
读取并向随后丢失的匿名 pipe 发出 `result-<24hex>.json` bytes。barrier 只证明 manager collector
尚未 start，不证明 result file 不存在或原 reader 从未读取。D 不观察其存在性；recovery/回传路径
禁止 stat/open/复制/hash/重新读取或封装业务 result bytes，也不得生成 result receipt。
共享 carrier 对象在 state parent 下恰为 `lhqcore-20261003a/carrier`，只容纳准入、安装
receipt、最终 output manifest、有界运行记录，以及 `intents/<case basename>.json` 三个
pre-mutation intent；`intents` 和每个 intent 都 create-only/fsync/回读并计入 8 MiB/512-inode
carrier audit pool。所有路径逐 component `openat`/no-follow，
不能接受 alias。

execution ID 恰为 `job-<operation ID>-<phase>`。helper unit 恰为
`lhj-<sha256(UTF-8 execution ID)>.service`，bootstrap/result-reader unit 分别对
`execution ID + ":bootstrap"` 和 `execution ID + ":result_reader"` 取同样摘要。H01 的
`preflight/business/evidence` 每 phase 各三个，
共九个 unit；Q4/H11 的 `preflight` 各三个。case plan 在该 case 首次 start 前只固定这些
可静态派生的 phase 与 `lhj-*` 完整名，后续只能引用这些原值。

| case/phase | bootstrap unit | helper unit | result-reader unit |
| --- | --- | --- | --- |
| H01/preflight | `lhj-aae4ba630a74fdd7560da54e6010657893aa5a2fd990f181cf55aadfc75790e0.service` | `lhj-84de996780c9edb6a2778aa12a73263402df23034c80089937bff12ce6eb16bf.service` | `lhj-d194ad7792f85752fc8660df7917fd834afc2af1382abe4ffe899e3e6a73f413.service` |
| H01/business | `lhj-0a3e2fd27fd81f6e92167f10c639459ba34d7cb3ba0efc17383de41649c9da15.service` | `lhj-03c94c57c840717302854a3f63cbfff7c1f30092da9a65d28eaf5f7f37a80113.service` | `lhj-ca281cff2eb95c641933a3822eba37f7c4e7c50885b715b33f42ab7a10673443.service` |
| H01/evidence | `lhj-a34ba323d7430151e2990ecca8ddeb65c7b59389dfc2ab2c521e3f48511986ea.service` | `lhj-dd0a9d005e9a9244df3e5763bc4f21b38d49d9b5ace02c0e1f6428f3a447651a.service` | `lhj-99eca74432220bcc541fc0da9e629403dce53a3bae1c4fa6555055277c93e828.service` |
| Q4/preflight | `lhj-79ea1e0be60ce7cbebb3d0c3514f8048b36c977206668a9f2c0ff2cfc894f178.service` | `lhj-bf1dc74725df6b82ac28a1b38ad3b8fed2e20e921f7a6de8dff5ad17493affc4.service` | `lhj-c92795ec04845c7897f2cda2492b249418e465bd7828d08488c1906a797f1503.service` |
| H11/preflight | `lhj-56c1b5ea4f55dc4870e8155ad50c34a4c121fa99b10b48666a07150d92fea17b.service` | `lhj-f7b176ecb6b8081fac3a7a47defb34bc3519a240ebd35aa4e40d33e7fa6fced3.service` | `lhj-00fa627254f63f3e86f97859f492e251c45c4aaaa83340cdef5b3b04cc1d0de8.service` |

每 case 的 target/supervisor controller unit 恰为 `<controller prefix>-target.service` 和
`<controller prefix>-supervisor.service`。每 phase 的 quota query/listener/admission unit 仍由冻结
quota request digest 严格派生为 `lhqo-<digest>.service`、`lhqoc-<digest>.service`、
`lhqoa-<digest>.service`；该 digest 只在 roots 实体和 current boot/capacity 被准入、resident
submit 后的逐 phase manager path 中生成，不能伪装为 pre-owner case-plan 事实。候选必须在相应
launch 前完成原 query/listener/admission unit collision/identity 检查，D 在 phase 完成后把准确
digest 与三个 unit 名绑定到 phase receipt。未被静态 plan 或相应动态候选 binding 覆盖的
`lhj-*`、`lhqo-*`、`lhqoc-*`、`lhqoa-*` 或 controller service 均不得启动。

H01 的五个 phase/role quota allocation 共启动最多 10 个 native children（3+3+4），Q4/H11
preflight 各最多 3 个，合计上界 **16**；五个实际 phase 各有一组 query/listener/admission，故
quota query unit 上界 5、dynamic quota unit 总上界 15。再加上述 15 个 `lhj-*` 和 6 个
target/supervisor controller units；失败停止不退款，也不得用 namespace scope 的旧“12 native”
边界覆盖本 scope。

三个 origin 的 ledger 在首次 submit 前都须由既有 normal empty-ledger gate 证明为空。Q4 和 H11
固定 `phase=preflight`；H01 固定按 `preflight`、`business`、`evidence` 三阶段运行。上述逻辑对象
是 A 的固定合同；boot、dev/inode、filesystem UUID、实际父路径和由固定算法产生的完整 unit name
是 C 后只读观察/plan binding，不能改变逻辑 namespace 或选择另一组对象。

## 3. A 的静态 artifact 与 C 后现场 package

候选须先修复现有 full-tree 来源绑定，使 runtime launcher 能严格验证 manifest 指定的 projected
source，而不把完整 Git tree 安装为运行来源；commit/tree、逐 blob 摘要、受保护读取、最小 import
闭包及额外文件拒绝仍须成立。完整 checkout 仍是下述一次性 installer staging input。

准确 A 的 artifact set 恰为一个 wheel、它的 canonical payload digest、一个 canonical
projected-source/core-harness manifest `.local-hand-source-projection.json`，以及同 A commit 的
`artifact-receipt.json`。receipt 只固定候选的 direct parent、两次独立 build 的逐字节一致性、
workspace retention locator、安装态验证汇总/摘要和 exact-hash-only 复用规则；364843-byte raw
installed-verification report 不属于 A 的 artifact set，receipt 也准确记录它未在该 set 中留存。
它不把未跟踪的 `dist/` path 提升为批准来源，也不允许
换 wheel。若 retained bytes 缺失，只可重建并取得同一长度/SHA/payload 后继续。wheel 只含既有四个安装包
和 dist-info。manifest schema 固定为 `local-hand-q2-source-projection/v1`，字段恰为 `schema`、
`source_commit`、`source_tree`、`files`；每个排序 file entry 恰含 regular-file `mode` 和 `sha256`，
并另行固定 manifest bytes、SHA-256 和 `files` entry count（不含 manifest 自身）。它不能指向
整仓库或在运行时补项。

harness manifest 的 tools 侧只允许两个 admin 包和四个产品包的固定前缀；tests 侧恰允许
`q2_fixture_check.py`、`q2_launcher.py`、`q2_prepare_assembly.py`、`q2_prepare_driver.py`、
`q2_prepare_run.py`、`q2_resident.py`、`q2_supervisor.py`、`q4_cancel_case.py`、
`q4_cancel_runtime.py`、`q4_h11_recovery.py`。generator、verifier 和 loader 均拒绝其它来源，尤其
不得包含或加载 `tools/q2_namespace_delivery.py`、`tests/e3_host/q2_namespace_*.py` 或 watchdog 专项。

JIT dispatcher 不属于核心 candidate，也没有 A-time member/hash 占位符。A 只规定其精确 schema、
状态转换、预算和拒绝语义。它与现场 package 必须在 C 后按本 scope 实现/测试，形成实际 D，并在
carrier request 前固定 D commit/tree、package basename/长度/SHA-256、逐成员 manifest 和验证结果。
未冻结 D/package 或 package 与 A 固定 wheel/harness manifest 不符时，不得发 carrier。

### C 后 field package 的固定格式

field package 是一个 basename 以 `.lhfp` 结尾的单一 regular file，不是 tar/zip，也不接受实现自行
选择的 archive。其 bytes 恰为 ASCII magic `LHCFP1\n`、一个 8-byte unsigned big-endian manifest
长度、该长度的 canonical manifest bytes，以及按 manifest `members` 的 path 字节序升序直接拼接的
member bytes；没有 padding、压缩、稀疏区或 trailing bytes。manifest 是 UTF-8/ASCII JSON，拒绝
重复 key、float/NaN，按 `sort_keys=True,separators=(",",":"),ensure_ascii=True` 编码并以单一 LF
结束。schema 固定为 `local-hand-q2-core-field-package/v1`，顶层 key 恰为 `schema`、`scope`、
`rule`、`baseline`、`owner_decision`、`closure`、`implementation`、`candidate`、`wheel`、
`projection`、`entry`、`locators`、`members`、`limits`：

- `rule` 恰含 `commit,source_sha256`；`scope` 是本 scope 字符串；`baseline` 恰含准确 A 的
  `commit,tree,documents_sha256`；`documents_sha256` 是恰有四项的 object，key 分别为本 scope
  三份 authoritative document 和 `docs/a2-execution/Q2_CORE_LIVE_INPUT_REVIEW_20261003.md`
  的 repository-relative path，value 为各文件 lowercase SHA-256；`owner_decision` 恰含
  Owner B 的 `event,record_path,record_sha256`，`record_path` 恰为
  `docs/governance/Q2_CORE_ACCEPTANCE_DELIVERY_OWNER_DECISION.md`；
  `closure`、`implementation` 与 `candidate` 分别只含准确 C、D、核心 candidate 的
  `commit,tree`。所有摘要为 lowercase SHA-256；
- `wheel` 恰含 `basename,bytes,sha256,payload_digest`；`projection` 恰含
  `basename,bytes,sha256,file_count`，分别绑定 A 固定值；
- `entry` 恰含 `loader_path,loader_bytes,loader_sha256,bootstrap_path,bootstrap_bytes,
  bootstrap_sha256,dispatcher_path,dispatcher_bytes,dispatcher_sha256,carrier_argv_sha256,
  management_entry_binding_sha256`；三个 path 分别固定为 `field/loader.py`、
  `field/bootstrap.py`、`field/dispatcher.py`，摘要绑定相应 D Git blob；loader 最多 8192 B、
  bootstrap 最多 49152 B、dispatcher 最多 262144 B；
- `locators` 恰含 `schema,observation_record_sha256,source_relation_sha256,state_parent,quota_parent,
  install_parent,journal_parent,evidence_parent,
  ordinary_user,ordinary_group,user_manager_unit,query_parent_unit,controller_parent_unit,
  management_parent_unit,supervisor_parent_unit,ordinary_parent_unit,retained_ordinary_parent_path,
  carrier_unit`；
  `schema=local-hand-q2-core-private-locators/v1`，`carrier_unit` 恰为
  `lhqcore20261003a-carrier.service`。其它值只能从上述唯一 management anchor 指向的
  已有 Q1 fixture private source 逐字段解析并在 package 内冻结；不得现场搜索、备选、
  从环境变量覆盖或选择另一个“也合格”的 parent/account/unit。五个 parent 为 canonical
  absolute path，七个 unit 为 canonical systemd unit name，retained ordinary parent 是准确 canonical
  cgroup path；`observation_record_sha256` 绑定已有私有
  只读观察 bytes，但不把其提升为 attestation。`source_relation_sha256` 恰是 canonical object
  `{"schema":"local-hand-q2-core-locator-relation/v1","management_entry_binding_sha256":...,
  "observation_record_sha256":...,"locators":...}` 的摘要，其中 `locators` 恰是除该摘要本身外的其余
  locator fields。任一 private source/关系不可复核即 `NOT_ISSUED`；
- `limits` 恰含 `package_bytes`、`manifest_bytes`、`members`、`member_bytes`、
  `shared_allocated_bytes`、`shared_entries`、`carrier_audit_bytes`、`carrier_audit_inodes`、
  `carrier_output_bytes`，值依次为 33550320、1048576、4096、16777216、67108864、4096、
  8388608、512、62914560；
- 每个 `members` item 恰含 ASCII canonical relative `path`、`role`、`mode`、`bytes`、`sha256`、
  `origin`；path 唯一且排序，JSON integer mode 仅 420/493（即 `0644`/`0755`），对象只可为
  single-link regular file；role 仅
  `candidate-worktree`、`candidate-git-metadata`、`wheel`、`projection`、`field-code`。`origin` 是
  按 role 选一的严格 object：`candidate-worktree`/`field-code` 恰含
  `kind,commit,path,blob`，`kind` 分别为 `candidate-blob`/`implementation-blob`；
  `candidate-git-metadata` 恰含 `kind,commit,git_path`，`kind=candidate-git-metadata`；
  `wheel`/`projection` 恰含 `kind,basename,sha256`，`kind` 分别为 `wheel`/`projection`。
  Git path/blob 须与相应 commit 的 object format 和 tree 一致，其它形状拒绝；
- `candidate-worktree` path 恰在 `candidate/` 下并与 candidate tree path 一对一，
  `candidate-git-metadata` 恰在 `candidate/.git/` 下；wheel/projection 分别恰有一个
  `artifacts/infra_local_hand-0.2.0a1-py3-none-any.whl` 和
  `artifacts/.local-hand-source-projection.json` member；三个 field-code 各恰有一个
  `field/loader.py`、`field/bootstrap.py`、`field/dispatcher.py` member，且 path/mode/bytes/SHA
  逐字段等于 `entry`。缺项、重复 role/path 或同 role 的第二 artifact 均拒绝；
- member 数最多 4096，manifest 最多 1 MiB（1048576 B），单 member 最多 16 MiB（16777216 B），
  整个 `.lhfp` 最多 33550320 B（32 MiB 减去下述 4112 B BIND frame 上界）；
  解包前后所有实际分配仍须满足下述共享 64 MiB/4096-entry 峰值，而不是每项另得一个上限。

`carrier_argv_sha256` 的 preimage 恰为一个 canonical JSON object，key 仅有 `schema,argv`；
`schema=local-hand-q2-core-carrier-argv/v1`，`argv` 是现有 wrapper profile 产生的本地 `execve`
最终有序 UTF-8 字符串数组，禁止 NUL/空元素，末项恰为下述 remote token
数组经 Python `shlex.join()` 得到的单一 command string。remote token 数组恰为：

```text
exec /usr/bin/sudo -n -- /usr/bin/env -i
HOME=/root PATH=/usr/bin:/bin LANG=C LC_ALL=C SYSTEMD_COLORS=0
/usr/bin/systemd-run --system --no-ask-password --quiet --wait --pipe --collect
--service-type=exec --unit=lhqcore20261003a-carrier.service
--property=Restart=no --property=RuntimeMaxSec=800s --property=TimeoutStopSec=30s
--property=KillMode=control-group --property=ExitType=cgroup
--property=CPUQuota=100% --property=LimitCPU=800
--property=MemoryMax=1073741824 --property=MemorySwapMax=0 --property=TasksMax=128
--property=LimitNOFILE=256 --property=LimitFSIZE=67108864 --property=UMask=0077 --
/usr/bin/python3 -I -B -c <loader D blob> <base64 bootstrap D blob> <bootstrap_sha256>
```

上表是 token，不是允许调用端重新分词的 shell 文本。bootstrap 用 RFC 4648 canonical
base64 且解码后恰为 package 中的 D blob；base64 参数≤65536 B，完整 remote command
≤98304 B，本地 argv+environment 编码合计≤524288 B，并在发行前以当前 `SC_ARG_MAX`
和 Linux 单参数上限实测拒绝超限。loader 只可 strict-base64 decode、校验长度/SHA-256、
`compile`/`exec` bootstrap；不读文件、不导入 package code、不创建持久对象。

`management_entry_binding_sha256` 的 preimage 恰为 canonical JSON object，key 仅有
`schema,wrapper,fixture_start,fixture_cloud_config,profile,environment,dependencies,identity,
identity_public,known_hosts,cwd,remote,transport`：

- `schema=local-hand-q2-core-management-entry-binding/v1`；`profile=env-bash-literal-ssh-v1`；
- `wrapper`、`fixture_start`、`fixture_cloud_config`、`identity_public` 和 `known_hosts` 各恰含
  `path,dev,ino,mode,uid,gid,nlink,bytes,sha256`，内容 SHA-256 分别固定为
  `aed91e80483d4df103f95c1d4cd5bf9bd18720f4dc51720702c329c937f93c63`、
  `1acc8c4cb09bc5b14c32adc35e87d8500098cbf3968d53f406269e96df30f96a`、
  `5b81deabefb7bc70aa6ee13b72053d65556fac1e400b5a37919ca1f90e4b6523`、
  `e67e15549d3e8586af936108f666612841d31612705236dd8ce265a3da18b25c` 和
  `d1025c074e532f29534fcab1d10ec1bc2f38d2137173c74d0bc921bbab420bbd`；
- `dependencies` 是按 `env,bash,ssh,ssh-keygen` 此顺序的四项数组，每项恰含
  `role,path,dev,ino,mode,uid,gid,nlink,bytes,sha256`，path 依次为
  `/usr/bin/env,/usr/bin/bash,/usr/bin/ssh,/usr/bin/ssh-keygen`；`identity` 恰含
  `path,dev,ino,mode,uid,gid,nlink,bytes,derived_public_key_sha256`，
  `derived_public_key_sha256` 固定为
  `e67e15549d3e8586af936108f666612841d31612705236dd8ce265a3da18b25c`，不读取或摘要
  私钥内容；只允许以固定 `ssh-keygen -y` 从 held fd 验证它派生与
  `identity_public` 相同的公钥；
- `environment` 恰含 `HOME,USER,LOGNAME,PATH,LANG,LC_ALL,SYSTEMD_COLORS`，其中
  `PATH=/usr/bin:/bin`、`LANG=C`、`LC_ALL=C`、`SYSTEMD_COLORS=0`，并明确删除
  `SSH_AUTH_SOCK/SSH_AGENT_PID/BASH_ENV/ENV`；`cwd` 恰含 `path,dev,ino,mode,uid,gid`；
- `remote` 恰含 `account,uid,gid,login_shell,parser_profile,shell,sudo,env,systemd_run,python,
  remote_tokens_sha256,remote_command_sha256`。`account=q1admin`；`parser_profile` 只可是已在固定
  fixture source 中逐字节证明的非交互 `-c` profile；`shell/sudo/env/systemd_run/python`
  各恰含 `path,dev,ino,mode,uid,gid,nlink,bytes,sha256`，后四者 path 分别固定为
  `/usr/bin/sudo`、`/usr/bin/env`、`/usr/bin/systemd-run`、`/usr/bin/python3`；两个 command
  摘要分别绑定 canonical token array 和它唯一 `shlex.join()` bytes；
- `transport` 恰含 `no_pty,stdin_binary,stdout_stderr_separate,known_host_preexisting,
  batch_mode,invocation_matches_frozen_command,sudo_noninteractive,sudo_no_password,
  sudo_policy_is_exact,fixture_policy_broader_than_command`。除 `sudo_policy_is_exact=false` 外其余恰为
  `true`。已有 fixture cloud-config source 明确是 `q1admin ALL=(ALL) NOPASSWD:ALL`；它不是
  技术性的 exact-command containment。本 A 把 residual broad-sudo trust 作为需 Owner 显式接受的
  唯一新治理前提：本 scope **只授权**固定 client argv 一次，但不声称该 policy 技术上只能调用
  一次、也不声称它能阻止其它登录或并发 sudo。当前 guest 的 sudo/sshd/authorized-keys/rc
  实体只能在已消费的同一 carrier 内由 root 准入读取并写入 `admission.policies`；与
  固定 fixture source 关系不符即停止，不重试。

上述两个 preimage 均使用与 package manifest 相同的 canonical JSON + 单 LF bytes；路径及
现场 object identity 留在私有记录，package 只携带摘要。任一字节/对象/环境变化都要重新
冻结 package，但不得在同一次 carrier 发出后更换。

package 不含 directory member；bootstrap 仅可为已验证 member path 的严格 ancestors create-only 建立
mode `0755` 目录，最终 inventory 把这些 derived directories 也计入 4096 entries。member path 只能
含 ASCII `[A-Za-z0-9._/-]`、不得绝对、空 component、`.`、`..`、反斜线或重复 slash。

package 必须携带一个由 bootstrap 以 root 身份 create-only 解包的、无
alternates/hooks/network dependency 的完整 clean candidate Git checkout，供既有
`verify_source()` 逐 tree/blob 核验并供 quota native C 源编译；它也携带准确 wheel、
A 固定 projection manifest 和来自 D Git blobs 的 loader/bootstrap/dispatcher 三个
field-code entry。完整 checkout 只是 root-owned build/JIT-preparation staging input；除下节 D adapter
准确加载的三个 preparation helper 外，不得被导入或进入 ordinary/runtime `sys.path`。其中即使存在
仓库历史上的 namespace/watchdog 文件也不得安装、导入或执行。installer 在完整 source 与 wheel
两次核验后编译/pin native quota helper，生成的
projection bytes 必须与 A 固定 manifest 逐字节相同，然后只安装该 projection、wheel runtime、native
输出和 D dispatcher。candidate checkout、Git metadata、compiler inputs/build outputs、package blob、
临时文件与最终安装的同时峰值统一计入共享 delivery pool；失败残留不退款。

### 既有 ordinary account 的 JIT preparation route

现场已有普通账号，原 `q2_prepare.py` 的新账号路径会以 `PREPARE_ACCOUNT_EXISTS` 拒绝，不能被
直接重跑，也不能因此复用任何旧 batch。C 后 D 必须实现一个本 scope 专用的 existing-account
JIT adapter：它只采用 admission 固定的 existing UID/GID/user-manager 与五个 parent，按 intent
create-only 建立本 case 的十二个 directory、七个全新 project roots、authority 和空 ledger；
不得调用 useradd/groupadd、修改账号、重放旧 receipt 或复用旧 root。

adapter 在完整且已验证的 candidate checkout 仍作为 staging input 时，复用其中
`q2_prepare_contract.py` 的 field/path/budget invariants、`q2_prepare_driver.py` 的
`validate_plan`/`facts_from_observed` constructor shape 与 `q2_prepare_assembly.py` 的 pure
validators/`assemble`，生成并复核 preparation plan、observed facts、authority/manifest、policy、
empty ledger 和 handoff。旧 contract 的 `decode()` 固定旧 scope/baseline，原 `q2_prepare.py` 固定
新账号，原 `q2_prepare_driver.complete()` 又会从最终 projection 启动一个缺少 adjacent contract
的 driver child；D **不得调用这三个 top-level path**。D 必须为本 A 实现 exact scope/baseline
adapter decoder 和 create-only completion sequence，并在进入上述 pure candidate functions 前完成
等价或更严格的全字段验证。reservation provenance 的 `scope` 必须是本 scope，`baseline` 必须是
准确 A；旧 scope/baseline 只作历史，不进入新记录。

`facts_from_observed()` 只能从 candidate 的 system/non-system plan 生成
`local-hand-q2-system-assembly-facts/v1` 或 `local-hand-q2-assembly-facts/v1`，本身不会选择 Q4/H11
schema。D 的唯一允许转换是：H01 采用 system plan 并保持 system schema；Q4 采用 non-system plan，
仅把返回 facts 的 `schema` 替换为 `local-hand-q4-cancel-assembly-facts/v1`，且不得出现
`system_geometry`；H11 采用 system plan，仅把返回 facts 的 `schema` 替换为
`local-hand-q4-h11-assembly-facts/v1` 并保留原 `system_geometry`。除该单一 schema 字段外，
facts/authority/manifest 必须与 `facts_from_observed()` 返回值逐字段相同，随后必须由原
`q2_prepare_assembly.assemble()` 对相应 Q4/H11 shape 完整严格校验；不得手工构造 launcher 对象。

ledger 初始化必须由 D 以 existing ordinary UID、final projected
`q2_prepare_assembly.initialize_ledger()` 和已验证 policy/ledger ID 执行，再按 candidate 原
prepared/handoff shape 验证；不得临时向 final projection 加入未列文件。每个 case 只把核验后的
policy/handoff 移交给 A 固定 projected runtime 和 ordinary owner；完整 checkout 始终为 root-only
staging input，永不进入 ordinary/runtime `sys.path`。adapter、其 exact argv/
schemas、negative tests 和 full inventory 都属于 C 后 D，必须在 package freeze 前验证。

### 跨进程一次性消费

本地 management anchor 恰为 2026-10-03 已观察 Q1 入口的唯一 private locator；它的 held
directory fd 必须同时命中固定 `ssh.sh`、`start.sh`、`known_hosts`、`id_ed25519.pub`
、`user-data` 摘要以及 `id_ed25519` 的受保护 identity/derived public key 和
management binding 中的实体，不得搜索、复制目录或由 output/attempt 参数换 anchor。
在该 held fd 下的 marker basename 恰为 `.lhqcore-20261003a.carrier-consumed.json`。marker
schema 为 `local-hand-q2-core-carrier-consumption/v1`，top-level key 恰为
`schema,scope,session_id,baseline,owner_decision,closure,implementation,candidate,package,
management_entry_binding_sha256,carrier_argv_sha256,host_boottime_origin_ns,
host_monotonic_origin_ns,host_boottime_deadline_ns,host_monotonic_deadline_ns,state`；
`state=CONSUMPTION_RECORD_COMPLETE`，其它批准链/artifact 记录与 package 逐字段相等。

调用端以 held-dir `openat(O_CREAT|O_EXCL|O_NOFOLLOW|O_WRONLY|O_CLOEXEC,0600)` 直接创建
最终 basename，写入≤16384 B canonical JSON，fsync file，保留其 dev/inode 后 close；再以
`openat(O_RDONLY|O_NOFOLLOW|O_CLOEXEC)` 重开同名对象，要求同一 dev/inode、single-link
regular 0600 file、完整回读与原 bytes 相等，然后 fsync parent 并计算摘要。
不用 temp/rename；从 `O_EXCL` 创建成功起，哪怕部分写、fsync/回读失败或进程崩溃，该 scope
都已消费，只保留且不发 request。已有任何类型/长度/内容的同名对象均按已消费拒绝；
并发进程只有 `O_EXCL` 唯一 winner 可继续，loser 不得重试或删除。marker 恰占本地
capture 预算的 16384 B/1 inode；后续 capture/receipt 只能使用剩余预算。BIND 必须携带
完整 marker 的 `consumption_sha256`，session/remote result/local acceptance receipt 必须回显
同值。`O_EXCL` 成功事实名为 `consumption_object_created=true`，完整记录事实名为
`consumption_record_complete=true`；前者已消费，但只有两者都真才允许启动 transport。

远端 bootstrap 只能来自 `entry.bootstrap_path` 的 D blob；调用端在本地复核同一 bytes 后，通过上述
准确 argv 启动。bootstrap 在读 stdin 前立即取 guest BOOTTIME-first、MONOTONIC-second，并向
stdout 写入一个 `LHCHLO1\n` + 8-byte unsigned big-endian length + canonical HELLO JSON 并
flush；JSON 长度最多 4096 B。HELLO schema 为 `local-hand-q2-core-carrier-hello/v1`，顶层
key 恰为 `schema,scope,loader_sha256,bootstrap_sha256,guest_boot_id,
guest_boottime_origin_ns,guest_monotonic_origin_ns,pid,uid,gid,euid,egid,python,carrier_unit,
process_limits`。`python` 恰含 `path,dev,ino,mode,uid,gid,nlink,bytes,sha256`；`carrier_unit`
恰含 `name,control_group,invocation_id,active_state,sub_state,runtime_max_usec,timeout_stop_usec,
memory_max,memory_swap_max,tasks_max,cpu_quota_per_sec_usec,restart,kill_mode,exit_type`；
`process_limits` 恰含 `cpu_soft,cpu_hard,nofile_soft,nofile_hard,fsize_soft,fsize_hard,umask`。
loader/bootstrap 摘要必须与 package `entry` 相等，`uid=gid=euid=egid=0`，unit/properties
必须逐项等于固定 remote tokens。HELLO 不声称已准入、安装或
执行 case。

调用端在完整验证 HELLO 后紧邻采样两个 host clock，以它们到已固定 carrier
deadline 的较小剩余量向下取整到 1 ms、再减 2 s processing margin 和 15 s
local-final reserve，得到正数 `mapped_duration_ns`。
它向同一 stdin 写入 `LHCBND1\n` + 8-byte unsigned big-endian length + canonical BIND JSON，
BIND JSON 长度最多 4096 B；随后紧接恰好 `package_bytes` 的 `.lhfp` 原始 bytes 并关闭
stdin，总 stdin 不超过 33554432 B。BIND schema 为
`local-hand-q2-core-carrier-bind/v1`，顶层 key 恰为
`schema,scope,session_id,hello_sha256,consumption_sha256,package_basename,package_bytes,package_sha256,
host_boottime_origin_ns,host_monotonic_origin_ns,host_boottime_deadline_ns,
host_monotonic_deadline_ns,host_boottime_bind_ns,host_monotonic_bind_ns,
host_remaining_floor_ns,clock_margin_ns,local_final_reserve_ns,mapped_duration_ns,
guest_duration_cap_ns,guest_duration_ns`。
`hello_sha256` 摘要 canonical HELLO JSON bytes；`clock_margin_ns=2000000000`；
`local_final_reserve_ns=15000000000`；
`host_remaining_floor_ns` 恰为两个 host deadline 分别减去同名 bind sample 后的较小值向下
取整到 1 ms；`mapped_duration_ns=host_remaining_floor_ns-clock_margin_ns-
local_final_reserve_ns`，且 package 三项与已冻结
artifact 一致；`guest_duration_cap_ns=750000000000`，`guest_duration_ns` 恰为
`min(mapped_duration_ns,guest_duration_cap_ns)`，并且必须为正。

bootstrap 以 HELLO 中的 guest 双原点各加 `guest_duration_ns` 得到 guest 内部双
deadline，收到 BIND 时重采两钟且任一已到界即拒绝。`2s` margin 只是有界处理余量，
不声称 host/guest clock 可直接排序；远端另由 `RuntimeMaxSec=800s` 独立强制，内部 750s cap
为有限 stop/final 留 50s guest-clock 余量。只有实际 stop/status/EOF 在 host 绝对 deadline 前被收回
才能 PASS；host 先到界时立即停本地 client，远端状态保留 UNKNOWN，不重连。bootstrap 再有界读取恰好长度的
`.lhfp`，要求随后真实 EOF，核 package/manifest/member 摘要与完整 inventory，然后才可创建
staging；不得先导入 package code。任何短读、追加 bytes、额外 member、保护/摘要/来源/预算
不符或 EOF 缺失都进入停止状态，不执行 dispatcher。

### dispatcher 的固定记录和状态机

所有 carrier/dispatcher/local-final JSON 都使用与 package manifest 相同的 canonical JSON
规则并拒绝额外/缺失字段。核心十四个 schema 及顶层 key 固定如下；D 只能实现，
不能另选形状：

| schema | 顶层 key（恰为这些） |
| --- | --- |
| `local-hand-q2-core-carrier-hello/v1` | `schema,scope,loader_sha256,bootstrap_sha256,guest_boot_id,guest_boottime_origin_ns,guest_monotonic_origin_ns,pid,uid,gid,euid,egid,python,carrier_unit,process_limits` |
| `local-hand-q2-core-carrier-bind/v1` | `schema,scope,session_id,hello_sha256,consumption_sha256,package_basename,package_bytes,package_sha256,host_boottime_origin_ns,host_monotonic_origin_ns,host_boottime_deadline_ns,host_monotonic_deadline_ns,host_boottime_bind_ns,host_monotonic_bind_ns,host_remaining_floor_ns,clock_margin_ns,local_final_reserve_ns,mapped_duration_ns,guest_duration_cap_ns,guest_duration_ns` |
| `local-hand-q2-core-dispatch-session/v1` | `schema,scope,rule,baseline,owner_decision,closure,implementation,package,entry,locators,consumption,session_id,outer,admission,installation,output,limits,cases,state` |
| `local-hand-q2-core-case-intent/v1` | `schema,session_id,index,case_id,kind,predecessor,preparation_id,identity,operation_id,controller_prefix,project_ids,directory_roles,planned_directories,planned_roots,preparation_input_sha256,phases,budgets,state` |
| `local-hand-q2-core-case-plan/v1` | `schema,session_id,index,case_id,kind,predecessor,preparation_id,identity,principal,authority_path,ledger_path,request,operation_id,roots,controllers,system_geometry,phases,empty_ledger_expectation,deadlines,budgets` |
| `local-hand-q2-core-phase-receipt/v1` | `schema,session_id,index,case_id,phase,quota_request_id,quota_request_sha256,query_unit,listener_unit,admission_unit,budget_deadline_ns,phase_deadline_ns,stage_deadline_ns,controller_deadline_ns,source_artifacts,source_artifacts_sha256` |
| `local-hand-q2-core-empty-ledger-gate/v1` | `schema,session_id,index,case_id,ledger_path,dev,ino,authority_id,ledger_id,snapshot_sha256,operations,events,leases,sidecars,checked_boottime_ns,stage,before_submit` |
| `local-hand-q2-core-ledger-export/v1` | `schema,session_id,index,case_id,authority_id,ledger_id,operation_id,ledger_identity,operation,events,sidecars,exported_boottime_ns` |
| `local-hand-q2-core-case-verdict/v1` | `schema,session_id,index,case_id,status,semantic_pass,observations,artifacts,missing,stop` |
| `local-hand-q2-core-h11-recovery-proof/v1` | `schema,session_id,index,case_id,candidate,ledger_identity,recovery_plan,recovery_summary,launcher_result,gateway_snapshot,origin_capture,control_seal,result_identity,assertions` |
| `local-hand-q2-core-remote-result/v1` | `schema,session_id,consumption_sha256,state,cases,h01_business_execution,h01_result_package,usage,missing` |
| `local-hand-q2-core-output-package/v1` | `schema,session_id,remote_result,cases,members,limits` |
| `local-hand-q2-core-capture-manifest/v1` | `schema,session_id,consumption_sha256,stdout,stderr,output_package,wait,files,logical_bytes,allocated_bytes,inodes,fsync_complete,reread_equal,missing` |
| `local-hand-q2-core-local-acceptance-receipt/v1` | `schema,scope,session_id,consumption,transport,remote_result,wait,capture,real_task_execution,result_evidence_collection,state,missing` |

session 的 `rule/baseline/owner_decision/closure/implementation/entry/locators` 必须逐字段等于已验证
package manifest；`session_id` 恰为 `lhqcore-20261003a`；`package` 恰含已冻结 `.lhfp` 的
`basename,bytes,sha256,manifest_sha256`；`consumption` 恰含固定 marker 的
`basename,bytes,sha256,state`。`outer` 恰含不可刷新双钟原点/截止和独立 guest cap；`limits`
恰含本节所有 time/resource/transport 上界；`cases` 是上述三 case 的完整静态模板，
顺序固定；每项 key 恰为
`index,case_id,kind,predecessor,preparation_id,operation_id,controller_prefix,project_ids,phases`，其值逐项等于
本 A 中的表和派生规则。session `state` 只能是下述 remote 链字面值或
`REMOTE_STOP_AND_RETAIN`，不能出现本地 `COMPLETE`。
其中 `outer` 的 key 恰为 `host_boottime_origin_ns`、`host_monotonic_origin_ns`、
`host_boottime_deadline_ns`、`host_monotonic_deadline_ns`、`clock_margin_ns`、
`host_boottime_bind_ns`、`host_monotonic_bind_ns`、`hello_sha256`、`mapped_duration_ns`、
`host_remaining_floor_ns`、
`guest_duration_cap_ns`、`guest_duration_ns`、
`guest_boot_id`、`guest_boottime_origin_ns`、`guest_monotonic_origin_ns`、`guest_boottime_deadline_ns`、
`guest_monotonic_deadline_ns`、`remote_final_reserve_ns`、`local_final_reserve_ns`；`limits` 的 key
恰为 `carrier_seconds`、`remote_unit_seconds`、`guest_duration_cap_seconds`、
`preparation_seconds`、`owner_seconds`、`case_gate_seconds`、
`hello_frame_bytes`、`bind_frame_bytes`、`package_bytes`、`carrier_input_bytes`、
`output_package_bytes`、`carrier_stderr_bytes`、`carrier_output_bytes`、`host_capture_bytes`、
`host_capture_inodes`、`carrier_cpu_seconds`、`carrier_memory_bytes`、`carrier_pids`、
`carrier_audit_bytes`、`carrier_audit_inodes`、`shared_bytes`、
`shared_inodes`、`case_physical_bytes`、`case_physical_inodes`、`all_case_physical_bytes`、
`all_case_physical_inodes`、`case_admission_bytes`、`case_admission_inodes`、
`all_case_admission_bytes`、`all_case_admission_inodes`、`all_case_cpu_seconds`、
`total_cpu_seconds`、`all_case_output_bytes`、`peak_memory_bytes`、`peak_pids`、
`job_units`、`controller_units`、`quota_query_units`、`dynamic_quota_units`、`native_children`、
`total_guest_physical_bytes`、`total_guest_physical_inodes`、`total_guest_admission_bytes`、
`total_guest_admission_inodes`。值恰为：

| limit key | 固定值 |
| --- | ---: |
| `carrier_seconds / remote_unit_seconds / guest_duration_cap_seconds` | `900 / 800 / 750` |
| `preparation_seconds / owner_seconds / case_gate_seconds` | `150 / 120 / 315` |
| `hello_frame_bytes / bind_frame_bytes / package_bytes / carrier_input_bytes` | `4112 / 4112 / 33550320 / 33554432` |
| `output_package_bytes / carrier_stderr_bytes / carrier_output_bytes` | `58716144 / 4194304 / 62914560` |
| `host_capture_bytes / host_capture_inodes` | `67108864 / 16` |
| `carrier_cpu_seconds / carrier_memory_bytes / carrier_pids` | `800 / 1073741824 / 128` |
| `carrier_audit_bytes / carrier_audit_inodes` | `8388608 / 512` |
| `shared_bytes / shared_inodes` | `67108864 / 4096` |
| `case_physical_bytes / case_physical_inodes` | `37748736 / 2944` |
| `all_case_physical_bytes / all_case_physical_inodes` | `113246208 / 8832` |
| `case_admission_bytes / case_admission_inodes` | `71303168 / 3968` |
| `all_case_admission_bytes / all_case_admission_inodes` | `213909504 / 11904` |
| `all_case_cpu_seconds / total_cpu_seconds / all_case_output_bytes` | `1290 / 2090 / 50331648` |
| `peak_memory_bytes / peak_pids` | `2751463424 / 1160` |
| `job_units / controller_units / quota_query_units / dynamic_quota_units / native_children` | `15 / 6 / 5 / 15 / 16` |
| `total_guest_physical_bytes / total_guest_physical_inodes` | `188743680 / 13440` |
| `total_guest_admission_bytes / total_guest_admission_inodes` | `289406976 / 16512` |

`admission` 恰含 `guest,programs,policies,parents,filesystems,capacity,absence`。`guest` 恰含
`hostname,dmi_vendor,dmi_product,initial_userns,boot_id,pid1_exe,pid1_version,cgroup_version,ordinary_user,ordinary_uid,ordinary_gid,
ordinary_groups,user_manager_unit,user_manager_invocation_id,user_manager_cgroup`；`programs` 恰以
`python,git,cc,setpriv,systemctl,systemd_run` 为 key，每值为上述严格 program identity，其中
`setpriv.path=/usr/bin/setpriv`；`policies` 恰含 `sudo,sshd,authorized_keys,rc`，每项恰含
`paths,bytes,sha256,relation`，并证明当前实体与已批准的 broader fixture sudo 前提及冻结
transport 关系一致。`dmi_vendor` 必须为 QEMU/KVM 或 `dmi_product=KVM`，PID 1 必须是 systemd、
cgroup 必须为 v2，initial user namespace/boot/account/manager 必须通过 candidate 原 isolation/
identity checks；这在进入 root 后只会形成条件性 admission，不能倒推 broader sudo 在技术上安全。
`parents` 恰以
`state,quota,install,journal,evidence,controller_cgroup,management_cgroup,supervisor_cgroup,
query_cgroup,ordinary_cgroup,retained_ordinary_cgroup` 为 key，
目录值恰含 `path,dev,ino,mode,uid,gid,nlink,mount_id,fs_uuid`，cgroup 值恰含
`path,dev,ino,unit,invocation_id,controllers`；`filesystems` 恰以 `state,quota,install,journal`
和 `evidence` 为 key，每值恰含
`mount_id,dev,fs_uuid,fstype,mount_options,bytes_available,inodes_available`；`capacity` 是按
`(dev,fs_uuid)` 排序并对 alias role 只合并一次的数组，每项恰含
`dev,fs_uuid,roles,historical_bytes,historical_inodes,new_required_bytes,new_required_inodes,
bytes_available,inodes_available,admitted`。`absence` 按 `kind,name` 排序，每项恰含
`kind,name,parent_dev,parent_ino,project_id,unit,absent,collision`，覆盖 install/staging、三 case
base/12-role directories/21 roots/21 project IDs、固定 `lhj-*`/controller units；不适用字段
为 `null`。quota query/listener/admission unit 名只能在逐 phase request digest 产生后由候选原
manager 在 launch 前检查，并进入对应 phase receipt，不能塞进静态 `absence`。任一绑定缺失、
`admitted=false`、`absent=false` 或 create-only race 失败都不得继续。
carrier unit 在 admission 时已经运行，不能要求 absent；它的 pre-start 唯一性由单次
`systemd-run --unit=...` 创建失败语义约束，当前 identity/properties 由 HELLO 与 admission 共同绑定。

`installation` 恰含 `destination,staging,receipt_path,dev,ino,mode,uid,gid,
members_sha256,native_sha256,projection_sha256,wheel_sha256,allocated_bytes,allocated_inodes,status`；
`members_sha256` 恰为已验证 field-package manifest 的完整 `members` 数组（连同每项的
`path,role,mode,bytes,sha256,origin`）按 package 已规定的 path ASCII 顺序、以同一 canonical JSON
编码但**不加** trailing LF 所得 SHA-256；它不是目录列表、安装后 inventory 或各
member digest 的字符串拼接。bootstrap 必须在 staging 解包后逐项重读并验证该数组，
只有验证成功后才能把同一值写入 installation receipt；`native_sha256` 、
`projection_sha256`、`wheel_sha256` 则分别绑定实际 native build output、A 固定 projection raw
bytes 和 A 固定 wheel raw bytes，不能以 `members_sha256` 代替。
`status` 只可 `NOT_STARTED,STAGING,INSTALLED,INCOMPLETE`。`output` 恰含
`stdout_basename,stderr_basename,remote_result_basename,capture_manifest_basename,local_receipt_basename,
output_package_bytes,stderr_bytes`，五个 basename 依次固定为
`.lhqcore-20261003a.stdout`、`.lhqcore-20261003a.stderr`、
`.lhqcore-20261003a.remote-result.json`、`.lhqcore-20261003a.capture-manifest.json`、
`.lhqcore-20261003a.acceptance-receipt.json`，都直接位于同一 management anchor 且
create-only。marker 前任一
已存在均 `NOT_ISSUED`；marker 后任一创建/写入失败均已消费且不重试。

case intent 只携带 A-time 逻辑对象和固定预算，并固定写入 shared carrier
`intents/<case basename>.json`，不得写入尚未创建的 case reservation。`identity` 只含创建 roots 前已可
派生的 `id,authority_id,node_id,install_uuid,deployment_epoch,generation,operation_id,profile_ref,
principal_id,epoch,slot_generation,session,ledger_id`；`project_ids`、`directory_roles`、`phases`、
`budgets` 逐字段等于本 A。`planned_directories` 按上述十二 role 顺序，每项恰含
`role,parent_role,relative_path,owner,mode`。`planned_roots` 按 project ID 顺序为七个原
preparation-contract record，恰含 `ref,slot,role,path,project_id,hard_bytes,inode_hard_limit`；
`ref` 依次固定为 `work-a,evidence-a,temporary-a,work-b,evidence-b,temporary-b,retained_store`，
对应 `slot` 依次为 `a,a,a,b,b,b,store`，对应 `role` 为
`work,evidence,temporary,work,evidence,temporary,retained_store`，path/project/limits 逐项等于
本 A。`preparation_id` 等于表中固定值。`preparation_input_sha256` 是 canonical object
`{schema,session_id,index,case_id,preparation_id,identity,planned_directories,planned_roots,budgets}` 的 SHA-256；
其中 `schema="local-hand-q2-core-preparation-input/v1"`。`state="INTENT_RECORDED"` 是唯一允许值。
intent 须在创建该 case 任何 directory/root/ledger 之前 create-only/fsync/回读。完整 case plan
只能在 roots、authority、ledger 被 create-only 创建并
验证后生成，但必须仍早于 owner、submit 或任何 unit start；它补入现场 dev/inode/
filesystem UUID、capacity、authority/manifest digest 和 request digest，不得改动
intent 的逻辑值。

plan 的 `identity` 恰含
`id,authority_id,node_id,install_uuid,deployment_epoch,generation,operation_id,profile_ref,principal_id,
epoch,authority_digest,manifest_digest,slot_generation,expires_at,session,ledger_id`，并严格遵守
本 A 的固定值/派生规则。`principal` 恰含 `principal_id,scopes`，ID 等于 identity，scopes
逐项等于本 A 的 H01/H11 三项或 Q4 四项数组。`request` 恰为上述 canonical `host.inspect`
对象，key 恰为
`schema_version,operation_id,kind,profile_ref,expected,inputs,expires_at,request_digest`。
`roots` 是七个严格 record：每项恰含 `ref,slot,planned,observed`；
`planned` 恰含原 preparation contract 的
`ref,slot,role,path,project_id,hard_bytes,inode_hard_limit`，`observed` 恰含原 assembly root 的
`path,role,device,inode,uid,gid,mode,filesystem,filesystem_uuid,project_id,xflags,hard_bytes,
accounting,enforcement,identity_unchanged,hard_inodes`。wrapper 与 `planned` 的 `ref/slot` 相同，
planned/observed 的 path、role、project ID、hard byte/inode limits 必须相等；logical relative
path/project ID 必须等于 intent，其余是 create-only 后的现场事实。`controllers` 恰含
`target,supervisor,controller_parent,query_parent,management_parent,supervisor_parent,
target_storage_bytes,target_storage_inodes,supervisor_storage_bytes,supervisor_storage_inodes`，两个
controller 是候选 `controller_guard.SPEC_FIELDS` 减去现场才可得的
`invocation_id,cgroup_device,cgroup_inode` 后加上固定 unit/cgroup parent 的完整 spec，四个 parent
是独立 held identity，两组 storage 值等于固定预算。公共 case-plan 保留 `system_geometry` key：
Q4 的值必须为 JSON `null`；H01/H11 的值逐字段等于 candidate assembly manifest 的
`local-hand-q2-system-geometry/v1` object，顶层恰含
`schema,controller_parent,ordinary_parent,retained_ordinary_parent`；三个 parent record 各恰含
`parent,memory_bytes,tasks_max,cpu_quota_per_sec_usec,memory_swap_max`，不得由 D 重构另一形状。
`deadlines` 恰含
`case_origin_ns`、`preparation_deadline_ns`、
`owner_deadline_ns`、`remote_final_deadline_ns`、`carrier_deadline_ns`；`budgets` 必须是下表既有
per-case 值的完整副本，top-level 恰为 `operation,phases,controller,ordinary,
retained_ordinary,target,supervisor,owner,management,durable,roots`。`phases` 是按固定 phase
顺序的数组，每项恰含
`phase,bootstrap_unit,helper_unit,result_reader_unit`；H01 三项，Q4/H11 各一项。quota request/
grant/deadline 只在 resident submit 后且每 phase 实际准备时由冻结 candidate 内部产生，不伪造为
pre-owner plan 事实。case plan 的 `case_id` 恰为 case basename，`preparation_id` 恰为同一表项；
`predecessor` 对 H01 为 `null`，对 Q4/H11 分别为前一 case basename；`authority_path` 恰为该 case
`authority/authority.json`，`ledger_path` 恰为 `state/jobs.sqlite`。除明确列出的 dynamic identity
外，所有 nested budget/controller/root/request 形状必须逐字段通过 candidate `4b6e4a7c` 冻结的
相应 q2 contract/assembly/guard validators；planned 与 observed root 分别按其真实 shape 验证，D
不得把两者合并成一个不存在的 decoder schema。

H01 phase 正常闭合后、Q4 cancel case 已记录后、H11 recovery result 成功后，
D 才可从候选已有 manager/ledger output 导出对应的
`local-hand-q2-core-phase-receipt/v1`，key 恰为
`schema,session_id,index,case_id,phase,quota_request_id,quota_request_sha256,query_unit,listener_unit,admission_unit,
budget_deadline_ns,phase_deadline_ns,stage_deadline_ns,controller_deadline_ns,source_artifacts,source_artifacts_sha256`；
它是事后证据，不回填 plan，也不冒充独立 pre-launch fence。candidate 的原内部 decoder/
manager fence 仍负责在 launch 前验证这些值。字段只准按以下候选事实映射：
`quota_request_id=grant.request.as_dict()["request_id"]`；`quota_request_sha256=grant.request.digest`
（完整 quota Request canonical bytes 的摘要，包含 `observation_grant_digest`，无 trailing LF）；
`query_unit=grant.request.query_unit`；`listener_unit="lhqoc-"+grant.request.digest+".service"`；
`admission_unit="lhqoa-"+grant.request.digest+".service"`；`budget_deadline_ns` 等于保存的 budget
grant `deadline_boottime_ns`；`phase_deadline_ns=budget.phase_deadline_ns(grant)`；
`stage_deadline_ns=phase_deadline_ns-grant["limits"]["terminate_grace_seconds"]*1000000000`；
`controller_deadline_ns` 等于原 controller envelope deadline。尤其 Q4 case report 中名为
`phase_deadline_ns` 的字段实际是这里的 stage deadline，不能单独用它填充 receipt 的 phase deadline。
`source_artifacts` 本体恰是按 `role,path` 排序的
`{role,path,bytes,sha256}` source artifact reference 数组；`source_artifacts_sha256` 的 preimage 恰为
这个数组以本节 canonical JSON 编码且不加 trailing LF 的 bytes。数组本体与摘要两者
必须同时出现并重算一致；所有成员必须也在 output package 中。这个数组不能由
实现自选，而是下列机械闭集（除明示的 H11 recovery declaration 为 mode 420 外，每项 mode 均为 384）：

- H01 的每个 phase 恰有五项：同 case 的
  `reservation/preparation-result.json`（`preparation-result`）、
  `<phase>/observer.json`（`observer-config`）、
  `launcher_output/phase-<phase>.json`（`phase-result`）和
  `launcher_output/result.json`（`launcher-result`）、
  `launcher_output/reservation.json`（`launcher-reservation`），其中 `<phase>` 只能逐项为
  `preflight,business,evidence`；
- Q4/preflight 恰有五项：同 case 的
  `reservation/preparation-result.json`（`preparation-result`）、
  `preflight/observer.json`（`observer-config`）、
  `launcher_output/phase.json`（`phase-result`）和
  `launcher_output/result.json`（`launcher-result`）、
  `launcher_output/reservation.json`（`launcher-reservation`）；
- H11/preflight 恰有八项：同 case 的
  `reservation/preparation-result.json`（`preparation-result`）、
  `preflight/observer.json`（`observer-config`）、
  `launcher_declarations/recovery-resident.json`（`recovery-plan`，mode 420）、
  `launcher_output/recovery.json`（`recovery-summary`）、
  `launcher_output/gateway.json`（`gateway`）、
  `launcher_output/origin-capture.json`（`origin-capture`）和
  `launcher_output/result.json`（`launcher-result`）、
  `launcher_output/reservation.json`（`launcher-reservation`）。

上述相对路径在 output package 中均以 `cases/<case basename>/` 为前缀。H01 的每个
`observer.json` 是 candidate `q2_chain.install()` 在对应 capture phase directory
create-only 保存的 exact `q2_config.Config.wire`；Q4/H11 的 observer 则是 candidate
`q2_assembly.install()` create-only 保存的同一 exact wire 格式。它含完整
active grant/request/budget/config，D 必须用冻结
`q2_config.decode()`/`Config.active()` 与同一 case plan、launcher raw output 联合重建 receipt 的
request ID/digest、dynamic units 和 budget/phase/stage deadline；candidate launcher 在启动
resident 前 create-only 保存的 `launcher_output/reservation.json` 含完整原
`controller_envelope`，receipt 的 `controller_deadline_ns` 只能取其
`controller.deadline_ns` 并与 case plan/其它 raw output 交叉核对，不能从 plan 预期值抄录。该闭集只绑定
candidate 已有 preparation/observer/launcher raw output；不声称 candidate 产生了另一个
quota-request、grant 或 deadline raw artifact。闭集的成员数、role、path、mode 或摘要任一不符，
即 phase receipt 不成立。`session_id,index,case_id` 逐字段等于 plan，
H11 恢复证据必须证明四个 deadline 不增长。
`empty_ledger_expectation` 只固定
`ledger_path,authority_id,ledger_id,expected_operations,expected_events,expected_leases,
expected_sidecars`，其中三个 count 均为 0、sidecars 为空。实际 gate 不回填 plan：D 在调用
owner 前以 held fd 读取并摘要 quiescent raw ledger，直接调用 pinned
`q2_fixture_check.empty_ledger(policy,uid,generation)`，再复核 held fd/path identity、raw bytes 和
sidecar absence 均未变；只有这个 direct check 成功后、首次 submit 前，才 create-only 产生一个
`local-hand-q2-core-empty-ledger-gate/v1` record，key 恰为
`schema,session_id,index,case_id,ledger_path,dev,ino,authority_id,ledger_id,snapshot_sha256,operations,events,leases,
sidecars,checked_boottime_ns,stage,before_submit`；`stage="fixture"`，三个 count 均为 0、
`sidecars=[]`、`before_submit=true`，三个 case-binding 字段逐项等于 plan。`snapshot_sha256` 摘要
D held fd 的原始 ledger snapshot bytes，而不是 deserialize 后或重新编码的内存对象；candidate
`empty_ledger()` 不导出 raw bytes/hash/dev/ino，故不得把这个摘要归因给 candidate。owner 启动后，
bound target MainPID 内的完整 `q2_fixture_check.check()` 仍须独立取得 `CHECKED`，其 fixture report
与 direct gate 一起进入 verdict/artifacts；D 不在该完整 checker 返回与 submit 之间插入写入。
gate 必须使用候选已有 fixture checker 的完整规则：broker root 是 ordinary `0700`；
`jobs.sqlite` 为 single-link ordinary `0600`、不超过 32 MiB；内存 deserialize 后通过
quick-check、`metadata/operations/events/leases/counters` 五张 required table 均存在、metadata 的
schema/authority/ledger 与 plan 一致、
generation 与 policy 一致；operations/events/leases 均为 0；无 WAL/SHM/journal sidecar；
读前后 file/root identity 和 bytes 稳定。StateStore 还可含 candidate 自身创建的其它 schema
objects（包括 `revocations`），不得把“五张 required table 存在”写成数据库恰有五张 table。
resident 在 submit 前仍以未改动的原 `compose()` 内部断言核查 all/events/leases 为空；候选不会
序列化第二份 raw snapshot/dev/ino/check time，D 不得补造。verdict 的 `resident_empty_gate`
只能恰含 `passed,candidate_commit,resident_source_sha256,accepted_operation_id,accepted_event_seq`；
`passed=true` 只表示 pinned source 的内部断言已通过，且随后同一 ledger 中唯一受理的原 operation/
ACCEPTED event 与 plan 匹配，不声称有第二份独立 snapshot。

H01/Q4 的终态 logical ledger export 只能由 D 在对应 owner 、writer 和 collector 全部退出、
StateStore 按冻结候选合同 checkpoint/close 且 sidecar 为空后生成；H11 不生成该 export。
raw source file 固定为各 case `reservation/ledger-export.json`：D 以 canonical JSON + 单一 LF、
`O_EXCL`、mode 0600 写入，fsync file/parent 并从同一 inode 完整回读；最多 1048576 B，计入既有
case state physical cap。output package 只把这个同一 source object 映射为 member path，分别固定为
`cases/c01-h01-normal/records/ledger-export.json` 和
`cases/c02-q4-cancel/records/ledger-export.json`，role 恰为 `ledger`、mode 恰为 384，对应 schema 恰为
`local-hand-q2-core-ledger-export/v1`；`records/` 只是 package path，不是另一个 guest directory 或
第二份文件。`ledger_identity` 恰含
`path,dev,ino,bytes,sha256`，摘要绑定 checkpoint 后 held-fd 读取的同一 raw SQLite file；
`operation` 恰含
`namespace,id,parent,principal,digest,reserved_bytes,request_json,plan_json,record_json`，后三个值是数据库
TEXT 的原 UTF-8 字符串，必须先通过 candidate `StateStore.get()` 采用的同一 duplicate-key/
finite-number/dict 规则严格解码，但不在 export 中重编码它们；`events` 按 `seq` 升序，
每项恰含 `seq,namespace,id,kind,observed_at,data_json`，`data_json` 同样是经上述规则验证但
未重编码的原 TEXT，`observed_at` 是 SQLite `printf('%.17g',observed_at)` 得到的 canonical
ASCII decimal string，从而不引入本 scope 禁止的 JSON float；`sidecars=[]`。D 只可以 SQLite `mode=ro`、
`query_only=ON` 在 held identity 上读出 metadata/唯一 operation/其 events，并只按各 case
已有合同校验而不在 export 中重编码 lease 事实；不得切换
journal mode、创建 sidecar、更改 ledger 或把 raw ledger bytes 封装为 member。`authority_id,ledger_id,
operation_id` 必须与 plan 一致；H01 PASS 另要求 operation 内唯一 seal registration 与
business evidence seal 逐字段一致，Q4 PASS 要求原 cancel 终态/events 与 raw Q4 case output 一致。
任一额外 operation、identity 不符、sidecar、读取不稳定或解码失败都使 export 和 case PASS
不成立；这个 D 导出不声称 candidate 本身产生了 `ledger-export.json`。

case 状态全集为 `NOT_RUN,RUNNING,PASS,INCOMPLETE`，但 create-only verdict 文件只记录下文定义的
两个终结值；只有 case 专用 verifier 取得全部事实才可令 `semantic_pass=true`。`artifacts` 是按 path
排序的数组，每项恰含
`role,path,bytes,sha256,sealed`；其中 `path` 必须恰为 output package member 的 canonical relative
path，`bytes/sha256` 必须逐字段等于该 member；guest absolute path 只能出现在 artifact raw content
内部。verdict 绝不把自身列入 `artifacts`，避免摘要自引用：PASS 时 `artifacts` 恰为该 case exact
required set 中除 `reservation/case-verdict.json` 自身外的全部 member reference；INCOMPLETE verdict
存在时，`artifacts` 恰为 output package 中该 case 已实际封装、且属于本 A 允许的 exact path universe
的全部 member reference（仍排除 verdict 自身）。verdict 本身只由 output manifest 的 member
reference 和 remote result case index 从外部绑定；不存在额外未列 case member。所有 schema 的
`missing` 都只能是按 `code,role,detail_sha256` 排序的数组，每项恰含这三个
字段。`stop`
恰含 `requested,acknowledged,tree_exited,writers_stopped,deadline_ns`。`observations` 按 case 恰含：

- H01：`empty_ledger_gate,resident_empty_gate,request_accepted,grant_issued,manager_delivered,unit_identities,bootstrap_exited,
  helper_started,helper_exited,result_reader_exited,result_verified,client_waited,stdout_eof,stderr_eof,
  future_start_blocked,tree_exited,writers_stopped,collectors_stopped,ledger_terminal,evidence_sealed`；
- Q4：`empty_ledger_gate,resident_empty_gate,request_accepted,helper_running_seen,cancel_called,cancel_durable,cancel_returned,no_late_delivery,
  unit_identities,stop_ack,helper_exited,exit_flags_complete,client_returned,stdout_eof,stderr_eof,
  chain_closed,ordinary_phase_closed,independent_ordinary_cleanup_required,full_h07`；
- H11：`empty_ledger_gate,resident_empty_gate,original_request_accepted,recovery_plan,recovery_summary,
  launcher_result,gateway_snapshot,origin_capture,ledger_identity,recovery_proof,result_identity,future_start_blocked,
  tree_exited,writers_stopped,collectors_stopped,effects_checked,outcome,leases_retained,result_reread,
  start_replayed,business_evidence_sealed,control_closure_sealed`。

三个 case 的 `empty_ledger_gate` observation 恰为对应 artifact 的 `path,bytes,sha256`；
`resident_empty_gate` 恰含
`passed,candidate_commit,resident_source_sha256,accepted_operation_id,accepted_event_seq`；
`unit_identities` 是按 `phase,stage,unit` 排序的数组，每项恰含
`phase,stage,unit,invocation_id`。除这些 object、H11 下述 object 和 H11 `outcome` 外，其余
observation 值均为 JSON boolean。H11 的 `recovery_plan,recovery_summary,launcher_result,
gateway_snapshot,origin_capture,ledger_identity,result_identity` 必须逐字段等于同一
recovery-proof 中同名 object；`recovery_proof` 恰为该 proof member 的 `path,bytes,sha256`；
`outcome` 只能为字符串 `UNKNOWN`。不得用预期值或 artifact 存在性把任一 boolean 改写成 true。

持久化的 case verdict 只能是终结记录，故其 `status` 只可为 `PASS` 或 `INCOMPLETE`；运行中的
`RUNNING` 只存在于内存/session 状态，不得提前 create-only 写成 verdict，尚未持久化 intent 的
`NOT_RUN` 只进入 final remote case index 且不得有 verdict member。case 真值恰按下表闭合：

| case / verdict | `semantic_pass` | 必须成立的 observation 真值 | `missing` / artifact 约束 |
| --- | --- | --- | --- |
| H01 `PASS` | `true` | 两个 gate 与完整 unit identity object 有效；其余列出的 boolean 全为 `true` | `missing=[]`；本节 H01 required set 全部存在并绑定 |
| Q4 `PASS` | `true` | 两个 gate/unit object 有效；`chain_closed=false,ordinary_phase_closed=false,independent_ordinary_cleanup_required=true,full_h07=false`；其余列出的 boolean 全为 `true` | `missing=[]`；Q4 required set 全部存在并绑定 |
| H11 `PASS` | `true` | object 逐字段等于 recovery proof；`outcome="UNKNOWN"`；`collectors_stopped=false,effects_checked=false,result_reread=false,start_replayed=false,business_evidence_sealed=false`；其余列出的 boolean 全为 `true` | `missing=[]`；H11 只含允许的 recovery/control required set，严禁业务 result/evidence bytes |
| 任一 `INCOMPLETE` | `false` | 每项只写实际观测值，未知 boolean 不得以默认值补齐 | `missing` 至少一项并准确指出未闭合事实；只列真实存在的 artifact |

`stop` 中 `deadline_ns` 必须等于该 case 原 owner deadline；PASS 时
`requested,acknowledged,tree_exited,writers_stopped` 均为 `true`。`INCOMPLETE` 时这些 boolean 仍只反映
真实 stop 事实，deadline 不得刷新。任一 required artifact、object binding 或上述固定正/负真值不符，
只能得到 `INCOMPLETE/semantic_pass=false`，不能把“预期失败”当 PASS。

remote result 的 `cases` 恰为三项有序数组，每项恰含
`index,case_id,status,semantic_pass,verdict_path,verdict_sha256`。`NOT_RUN` 表示该 case 的 intent
从未持久化，故 plan/start 均未发生，此时 `semantic_pass=false` 且两个 verdict 字段均为 `null`；
`PASS` 时 `semantic_pass=true` 且两个 verdict 字段必须成对绑定真实 verdict member path/SHA-256；
final remote result 中不得出现 `RUNNING`；已持久化 intent 但未 PASS 的 case 必须为 `INCOMPLETE`，
`semantic_pass=false`，两个 verdict 字段只能同为 `null` 或成对绑定实际 `INCOMPLETE` member。三项只可
呈现以下前缀闭包：`PASS/PASS/PASS`、`NOT_RUN/NOT_RUN/NOT_RUN`、`INCOMPLETE/NOT_RUN/NOT_RUN`、
`PASS/NOT_RUN/NOT_RUN`、`PASS/INCOMPLETE/NOT_RUN`、`PASS/PASS/NOT_RUN` 或
`PASS/PASS/INCOMPLETE`；不得跳过前驱或令后项先 PASS。
`usage` 只能含 guest 在回传前
已知的
`guest_elapsed_ns,carrier_cpu_ns,carrier_memory_peak_bytes,carrier_pids_peak,stdin_bytes_received,
output_frame_bytes,guest_allocated_bytes,guest_allocated_inodes,job_units_started,
controller_units_started,quota_query_units_started,dynamic_quota_units_started,native_children_started`；
最后五项分别不得超过 `15/6/5/15/16`，失败或提前停止也报告实际启动数而非预算数；`missing`
沿用上述三字段形状。
`h01_business_execution` 恰含
`status,operation_id,execution_id,unit,invocation_id,wait_status,business_started,outcome,evidence_sha256`；
`status` 只能为 `NOT_RUN,INCOMPLETE,VERIFIED`；`operation_id` 为固定 H01 ID 或 `null`，其余 identity
字段为已观测字符串或 `null`，`wait_status` 为 JSON integer 或 `null`，`business_started` 为 boolean，
`outcome` 只能为 `NOT_RUN,SUCCEEDED,FAILED,UNKNOWN`，摘要为 lowercase SHA-256 或 `null`。
只有 H01 PASS 才允许 `status=VERIFIED,business_started=true,outcome=SUCCEEDED`。
`h01_result_package` 恰含 `status,result_member,result_sha256,required_members_sha256`；其 `status` 使用
同一三值枚举，`result_member` 为恰含 `role,path,bytes,sha256` 的 member reference 或 `null`，两个摘要
为 lowercase SHA-256 或 `null`，且只有完整 required set 时才允许 `VERIFIED`。这两项只是
remote packaged facts，不声称 host 已 wait/EOF/fsync/回读。`evidence_sha256` 恰为 H01
`business-evidence-seal` member raw bytes 的 SHA-256；`result_sha256` 恰为 `result_member` raw bytes 的
SHA-256；`required_members_sha256` 的 preimage 是按 `role,path` 排序的全部 H01 required
`{role,path,bytes,sha256}` member reference 数组的 canonical JSON。三者引用的 member 必须
实际出现在同一 output manifest。

两个 H01 summary 的状态也必须闭合：H01 case 为 `NOT_RUN` 时二者都必须为 `NOT_RUN`，所有 identity/
member/digest 为 `null`、`business_started=false`、`outcome="NOT_RUN"`；H01 case 为 `PASS` 时二者
都必须为 `VERIFIED`，上述必需 identity、wait、result、evidence 和 digest 全部非空并相互绑定；H01
case 为 `INCOMPLETE` 时二者都不得为 `VERIFIED`，每个 summary 只可在它所描述的阶段没有开始时为
`NOT_RUN`，否则为 `INCOMPLETE` 并保留已观测字段。`result_member=null` 时 `result_sha256` 必须为
`null`；非空时两者必须绑定同一 raw member。`required_members_sha256` 只在 exact required set 完整时
非空。remote result 的 `state` 只可为 `REMOTE_FINALIZED`（三 case 均 PASS）或
`REMOTE_STOP_AND_RETAIN`（上述任一 NOT_RUN/INCOMPLETE）；若无法真实生成这个 final record，则本地只能记录
remote result 缺失，不能合成它。

local acceptance receipt 的 `consumption` 恰含
`object_created,record_complete,basename,bytes,sha256`；`transport` 恰含
`execve_succeeded,hello_valid,bind_written,package_written,stdin_bytes_written,stdin_eof`；`wait` 恰含
`status,stdout_eof,stderr_eof,host_deadline_met`；`capture` 恰含
`bytes,inodes,manifest_sha256,fsync_complete,reread_equal`。`remote_result` 恰含
`present,sha256,frame_sha256`；`real_task_execution` 和 `result_evidence_collection` 各恰含
`status,evidence_sha256`，status 只能 `YES,NO,UNKNOWN`。只有完整 remote business unit identity/
InvocationID/wait 证据与有效 frame 一致时才可令前者 `YES`；只有 H01 result 及必需
evidence members 通过 frame 长度/摘要、本地 create-only capture、fsync 和回读时才可令后者
`YES`。只有直接证明 H01 从未 plan/start 才可记 `NO`；连接/证据不明必须是
`UNKNOWN`。Q4/H11 不能改写这两个 H01 事实。
`remote_result.sha256` 是 output manifest 中嵌入的 `remote_result` object 按相同 canonical JSON
规则编码、但不加 trailing LF 的摘要；`frame_sha256` 是从 `LHCOUT1\n` magic 起至最后一个 raw
member byte 为止的完整 frame SHA-256。

两个本地 truth summary 的 `evidence_sha256` 不是自由文本摘要。其 preimage 恰为 canonical JSON
object（无 trailing LF），key 仅有
`schema,kind,status,frame_sha256,remote_result_sha256,capture_manifest_sha256,h01_case,
h01_business_execution,h01_result_package,members`；`schema` 固定为
`local-hand-q2-core-local-truth-evidence/v1`，`kind` 分别为 `real_task_execution` 或
`result_evidence_collection`，`status` 等于 summary status，三个摘要逐字段等于本地验证后的
frame/remote-result/capture manifest，三个 H01 object 逐字段复制 final remote result 中对应值。
`members` 是按 `role,path` 排序、每项恰含 `role,path,bytes,sha256` 的实际 output member reference：

- execution=`YES` 时，恰含 H01 retained `preparation-result`、business `observer-config`、
  `phase-receipt`、`phase-result`、`launcher-reservation`、`gateway`、`launcher-result`、`wait` 和 `verdict` members，
  unit/InvocationID 只从这些 raw member 严格投影，不要求 standalone manager/unit artifact；
  execution=`NO` 时只允许 H01 case 和
  两个 H01 summary 均为上述 `NOT_RUN`，`members=[]`；
- collection=`YES` 时，恰含 H01 raw `result`、三个同 seal-id 的 `business-evidence-*`、
  `gateway`、`wait` 和 `verdict` members，result-reader identity 仅为上述 raw 证据的投影；
  collection=`NO` 也只允许 H01 从未 intent/plan/start 的同一
  `NOT_RUN` 证明且 `members=[]`。

`YES/NO` 必须有非空 `evidence_sha256` 并等于上述 preimage 摘要；任一引用缺失、frame/remote/capture
不完整或是否执行/收回无法直接决定时，status 必须为 `UNKNOWN` 且 `evidence_sha256=null`。因此
H01 已启动但 result/evidence 缺失不能写成 `NO`，Q4/H11 事实也不能替代 H01 truth evidence。

local receipt 状态与 truth 的允许组合恰为：

| local `state` | remote/case 条件 | `real_task_execution` | `result_evidence_collection` |
| --- | --- | --- | --- |
| `COMPLETE` | valid `REMOTE_FINALIZED`；三 case 均 `PASS`；transport、wait/EOF、capture fsync/回读全部闭合 | `YES` | `YES` |
| `STOP_AND_RETAIN`，H01 未开始且有完整 final frame | H01=`NOT_RUN`，后两项=`NOT_RUN` | `NO` | `NO` |
| `STOP_AND_RETAIN`，H01 已 PASS、后续 case 未闭合 | valid `REMOTE_STOP_AND_RETAIN`；H01=`PASS` | `YES` | `YES` |
| `STOP_AND_RETAIN`，H01 已开始但 case 未闭合 | H01=`INCOMPLETE` | 可由上述 exact execution evidence 决定时 `YES`，否则 `UNKNOWN` | 可由上述 exact result/evidence collection 证据决定时 `YES`，否则 `UNKNOWN`；不得为 `NO` |
| `STOP_AND_RETAIN`，连接/remote result/frame/capture 不完整 | final case truth 不足 | `UNKNOWN` | `UNKNOWN` |

不存在 `COMPLETE+UNKNOWN/NO`、`REMOTE_FINALIZED` 含非 PASS case、或后续 case 改写 H01 truth 的组合。

### 结果与证据回传

HELLO 后 stdout 不得有中间文本/日志；远端收尾只写一个 `LHCOUT1\n` + 8-byte
unsigned big-endian manifest length + canonical output-package manifest + 按 member path ASCII
字节序排序的 raw member bytes，随后真实 stdout EOF。output manifest 最多 1 MiB，
member 最多 4096 个/单个 16 MiB，整个 `LHCOUT1` frame 最多 58716144 B；stderr 最多
4194304 B；加上最大 HELLO 4112 B 后 stdout+stderr 总计仍最多 62914560 B（60 MiB）。
断线/硬杀时可以没有完整 output frame，但不得补写成功结果。

output-package 的 `remote_result` 是完整 remote-result object；`cases` 逐字段等于其三项
case index；`limits` 恰含 `frame_bytes,manifest_bytes,members,member_bytes,stderr_bytes`，值
依次为 58716144/1048576/4096/16777216/4194304。每个 `members` item 恰含
`path,case_id,role,mode,bytes,sha256`，path 使用与输入 package 相同的 canonical 规则，
`mode` 是封装前 source artifact 的真实 permission，只能为 384（`0600`）或 420（`0644`），且须
逐 member 等于对应 producer contract；source 必须是
single-link regular file，受保护读取前后 identity/mode/bytes 必须稳定。frame 只承载 raw bytes，
不声称在 host 重新创建了相同 mode 的文件；`case_id` 只能三个 case basename
或 `carrier`。每 case 的 member bytes 合计不得超过 16777216。role 只能为
`session,admission,installation,intent,plan,preparation-plan,preparation-result,phase-receipt,
empty-ledger-gate,authority,ledger,fixture-check,observer-config,phase-result,gateway,origin-capture,
launcher-reservation,launcher-result,stdout,stderr,wait,result,
recovery-plan,recovery-summary,recovery-proof,stop,verdict,
business-evidence-archive,business-evidence-manifest,business-evidence-seal,control-seal`，且须与
case 语义匹配。完整 remote result 只在 output manifest 的
`remote_result` 字段出现一次，不得再复制成 member。manifest 只列实际成员，缺项只进
`missing`。“必需”是下述 role/path/mode/重数的机械闭集，不是同名 role 任意出现一次即
满足；每个列出的 path 恰出现一次，不得用 summary 代替 raw producer record。

carrier-level required 成员恰为三个 mode 384 的 member：
`carrier/session.json` (`session`)、`carrier/admission.json` (`admission`) 和
`carrier/installation.json` (`installation`)。三个 case 的包内前缀均为
`cases/<case basename>/`；每 case 恰有下列八个 mode 384 的 common member：
`intent.json` (`intent`)、`reservation/case-plan.json` (`plan`)、
`reservation/preparation-plan.json` (`preparation-plan`)、
`reservation/preparation-result.json` (`preparation-result`)、
`reservation/empty-ledger-gate.json` (`empty-ledger-gate`)、
`owner_declarations/fixture-check.json` (`fixture-check`)、
`authority/authority.json` (`authority`) 和 `reservation/case-verdict.json` (`verdict`)。

H01 在 common 八项之外恰再要求：

- `preflight/observer.json`、`business/observer.json`、`evidence/observer.json` 三项
  （`observer-config`）；
- `reservation/phase-preflight-receipt.json`、`reservation/phase-business-receipt.json`、
  `reservation/phase-evidence-receipt.json` 三项（`phase-receipt`）；
- `launcher_output/phase-preflight.json`、`launcher_output/phase-business.json`、
  `launcher_output/phase-evidence.json` 三项（`phase-result`），以及
  `launcher_output/reservation.json` (`launcher-reservation`)、
  `launcher_output/gateway.json` (`gateway`)、`launcher_output/result.json` (`launcher-result`)、
  `launcher_output/resident.stdout` (`stdout`)、`launcher_output/resident.stderr` (`stderr`) 和
  `launcher_output/capture.json` (`wait`)；
- `records/ledger-export.json` (`ledger`) 和
  `business/result-03c94c57c840717302854a3f.json` (`result`)；
- 从 ledger 唯一 seal registration 导出的 canonical lowercase UUID `seal_id` 实例化的
  `business-evidence/<seal_id>/evidence.zip` (`business-evidence-archive`)、
  `business-evidence/<seal_id>/manifest.json` (`business-evidence-manifest`) 和
  `business-evidence/<seal_id>/seal.json` (`business-evidence-seal`)；
- `supervisor_output/stop.json` 和 `owner_output/stop.json` 两项（`stop`）；
- `supervisor_output/seal.json` 和 `owner_output/seal.json` 两项（`control-seal`）。

本 H01 列表中每项 mode 都恰为 384。`<seal_id>` 不是 glob：它只能是 ledger export
中那一项 seal registration 的 `seal_id`，三个 member 的 parent component 必须逐字节相同。
H01 `required_members_sha256` 恰对 common 八项与本 H01 列表的所有成员合并后，
按 `role,path` 排序的 `{role,path,bytes,sha256}` 数组做无 trailing LF canonical JSON
SHA-256；它不包含 carrier-level 三项、output manifest 或 remote result object。H01 的三个
`business-evidence-*` member 必须来自同一 `seal_id` directory；seal raw JSON 中的 artifact set
必须恰绑定 archive 与 manifest 两个 member，且 ledger 的 seal registration 必须逐字段与这个
seal ID/digest 一致。H01 stop/deadline/exit confirmation 必须由两份 raw `stop`、两份 raw
`control-seal`、`wait` 和 verdict 交叉绑定，不能只从 seal 内摘要推断 stop 内容。H01
result-reader unit/InvocationID/wait 必须由上述 `observer-config`、`launcher-reservation`、
`gateway`、`launcher-result`、
`wait` 和 `verdict` raw members 交叉绑定，不得增加 standalone unit receipt。H01 required set
因而恰为 **32** 个 case member（common 8 + H01 特有 24）；
只有这一精确集合全部进入 output package 并在本地 fsync/同 inode 回读
后，`result_evidence_collection.status` 才能为 `YES`。
H01 business raw result basename 恰为
`result-03c94c57c840717302854a3f.json`（candidate `result_name()` 对固定 business execution ID 的
唯一结果）；其 member reference、result-reader unit/InvocationID、wait 和 verdict 必须相互绑定，
不得补造一个 candidate 不产生的 result receipt。
每个 PASS case 的 `fixture-check` member canonical relative path 分别固定为
`cases/<case basename>/owner_declarations/fixture-check.json`；它必须是 bound target MainPID 内
完整 checker 实际 create-only 输出的 raw `CHECKED` report，不能由 direct empty-ledger gate 或
dispatcher summary 代替。H11 required set 同样必须包含这一项。
每个 PASS case 的 `preparation-plan` 与 `preparation-result` member path 分别固定为
`cases/<case basename>/reservation/preparation-plan.json` 和
`cases/<case basename>/reservation/preparation-result.json`；其 raw bytes/SHA 必须与同目录
preparation authority 的两个摘要逐字节对应，`case_id` 必须等于该 basename、role 必须分别恰为
`preparation-plan`/`preparation-result`、source mode 必须为 384。两项都是每个 PASS case 的 required
member（包括 H11），并须从创建后一直保留的同一 source dev/inode 受保护读取；plan 必须证明早于
case mutation，result 必须证明晚于 observed/retained equality 且早于 authority/manifest/ledger/
owner/submit。任一项只剩解析后的 object、摘要而无 raw preimage，或 packaging 时 source identity/
bytes 改变，case 只能 `INCOMPLETE`。

Q4 在 common 八项之外恰再要求下列全部 mode 384 的成员：
`preflight/observer.json` (`observer-config`)、
`reservation/phase-preflight-receipt.json` (`phase-receipt`)、
`launcher_output/reservation.json` (`launcher-reservation`)、
`launcher_output/phase.json` (`phase-result`)、`launcher_output/result.json`
(`launcher-result`)、`launcher_output/resident.stdout` (`stdout`)、
`launcher_output/resident.stderr` (`stderr`)、`launcher_output/capture.json` (`wait`)、
`records/ledger-export.json` (`ledger`)、`supervisor_output/stop.json` 和
`owner_output/stop.json` 两项（`stop`）、`supervisor_output/seal.json` 和
`owner_output/seal.json` 两项（`control-seal`）。`phase.json` 是候选已有 raw cancel case
record，不得再要求 candidate 不产生的 standalone `cancel.json`。Q4 required set 因而恰为
**21** 个 case member（common 8 + Q4 特有 13）。

H11 的 required set 在 common 八项之外恰为下列十八项，除明示者外 mode 都恰为
384，每 path 重数恰为 1：

- `preflight/observer.json` (`observer-config`)；
- `reservation/phase-preflight-receipt.json` (`phase-receipt`)；
- `launcher_output/reservation.json` (`launcher-reservation`)；
- `launcher_declarations/recovery-resident.json` (`recovery-plan`，mode 420)；
- `launcher_output/recovery.json` (`recovery-summary`)、
  `launcher_output/origin-resident.stdout` (`stdout`)、
  `launcher_output/origin-resident.stderr` (`stderr`)、
  `launcher_output/origin-capture.json` (`origin-capture`)、
  `launcher_output/gateway.json` (`gateway`)、
  `launcher_output/result.json` (`launcher-result`)、
  `launcher_output/resident.stdout` (`stdout`)、
  `launcher_output/resident.stderr` (`stderr`) 和
  `launcher_output/capture.json` (`wait`)；
- `reservation/h11-recovery-proof.json` (`recovery-proof`)；
- `supervisor_output/stop.json` 和 `owner_output/stop.json` 两项（`stop`）；
- `supervisor_output/seal.json` 和 `owner_output/seal.json` 两项（`control-seal`）。

H11 因而恰有 common 八项 + 上述十八项，即 **26** 个 case member；不接受 `recovery*` wildcard、standalone
`manager`、`unit`、`ledger-identity`、`result-identity`、`recovery`、raw `ledger`、raw
business `result` 或任一 `business-evidence-*` member。对业务 result bytes 的打开、复制、hash
或封装仍严禁。verdict `unit_identities` 只是 D 从 raw `gateway.json.stages[]` 严格投影的
`{phase,stage,unit,invocation_id}` 排序数组；proof 内 `ledger_identity` 和
`result_identity` 也只是 nested object，三者都不是 output member。

launcher result 的 `recovery` 必须逐字段等于 recovery summary raw JSON object，
`origin_capture` 必须逐字段等于 origin-capture raw JSON object，gateway 的 recovery-plan digest
必须等于 declaration 内嵌 plan digest。proof 的 `control_seal` 固定引用 outer-owner seal；
supervisor raw seal 仍必须单独存在。candidate 没有对既存 seal bytes 的通用 decoder；D 必须
按两个 producer 固定的 schema/status/files shape 复核 raw seal，并与 candidate 返回的
`sealed=true` 及逐层 result/control identity 交叉绑定，才能令
`control_closure_sealed=true`。任一 required 成员缺失、mode/path/role/重数不符或 raw 读取
不稳定，都使对应 case 非 PASS。

本地以上述固定五个 basename 收取 stdout/stderr、解析并 create-only 写出 remote result，再生成
包含 marker、两流、output manifest/member 摘要、wait status 和缺项的 capture manifest 与 local
acceptance receipt。capture manifest 的 `stdout,stderr` 各恰含 `basename,bytes,sha256,eof`；
`output_package` 恰含 `present,frame_bytes,manifest_sha256,members_sha256,valid`；`wait` 恰含
`status,host_deadline_met`。
`output_package.members_sha256` 恰为已验证 output-package manifest 的完整 `members` 数组（每项恰含
`path,case_id,role,mode,bytes,sha256`）按 path ASCII 顺序、以同一 canonical JSON 但不加
trailing LF 编码的 SHA-256；它不包含 `remote_result`、manifest 本身或 raw member bytes，
也不是各 member SHA 字符串拼接。`present=false` 时 `frame_bytes=0`，
`manifest_sha256=members_sha256=null`、`valid=false`；只有完整 frame/manifest/member 边界、该
members digest 和每个 raw member digest 全部一致时才能 `valid=true`。
`files` 是按 basename 排序的
`basename,bytes,allocated_bytes,sha256,dev,ino,mode,nlink` 数组，只能是消费 marker、stdout、stderr
和提取的 remote-result 中已实际创建对象的 basename 有序子集；`COMPLETE` 时才必须恰有这四项，
断线/无完整 frame 时 remote-result 必须缺席。数组不含 capture manifest 自身或未来 receipt；
`allocated_bytes=st_blocks*512`。顶层 `logical_bytes/allocated_bytes/inodes` 分别是该实际子集的逻辑 bytes、
实际分配 bytes 和对象数合计，
`fsync_complete/reread_equal` 只有全部对象及 parent fsync、同 inode 回读相等后才可为 true。
本地总分配
最多 64 MiB/16 inodes：marker 最多 16384 B/1 inode，两流最多 60 MiB/2 inodes，
其余解析记录/最终报告共享剩余 4177920 B/13 inodes；其中提取出的
`.remote-result.json` 是 stdout frame 中 bytes 的物理副本，最多 262144 B，必须在该剩余额度内
再次计费，不能以“同一逻辑事实”去重。remote-result、capture manifest 和 receipt 自身共同分享
streams/marker 后剩余的 4177920 B/13 inodes；remote-result 创建后，后两者只能使用扣除其实际
allocated bytes/inode 后的余额。capture manifest 不自引用，也不预先摘要未来 receipt。local receipt
是唯一终结记录，不另设 local seal；finalizer 必须在写完 receipt 后 fsync file/parent、同 inode
重开并完整回读相等，只有这个调用端可观察的最终步骤成功才可接受 `COMPLETE`。receipt 不自摘要，
其中 `capture.bytes/inodes` 等于上述实际子集的
`allocated_bytes/inodes`，`manifest_sha256` 只绑定完成后的 capture manifest。任一超限、短读、额外
stdout bytes、摘要不符、wait/EOF 缺失或 fsync/回读失败都使本地 acceptance 不成立。

本地消费/收回与远端 dispatcher 是两条独立序列化的状态链：

```text
local:  STATIC_VERIFIED -> CARRIER_CONSUMED -> CONSUMPTION_RECORD_COMPLETE
        -> TRANSPORT_STARTED -> LOCAL_AWAITING_REMOTE -> LOCAL_FINALIZING -> COMPLETE

remote: REMOTE_PREFIX_STARTED -> BOUND -> REMOTE_ADMITTED -> INSTALLED
 -> H01_INTENT -> H01_PLANNED -> H01_PASS
 -> Q4_INTENT -> Q4_PLANNED -> Q4_PASS
 -> H11_INTENT -> H11_PLANNED -> H11_RECOVERY_PASS
 -> REMOTE_FINALIZING -> REMOTE_FINALIZED
```

remote session `state` 只能是 remote 链字面值或在其自身确实持久化停止事实时的
`REMOTE_STOP_AND_RETAIN`；它永不写 `LOCAL_FINALIZING/COMPLETE`。local receipt `state` 只能是
`COMPLETE` 或 `STOP_AND_RETAIN`。任一拒绝、FAIL/BLOCKED、非合同预期 UNKNOWN、timeout、
disconnect、stop/EOF/证据缺失使本地从当时状态单向进入 `STOP_AND_RETAIN`；远端仅在仍可记录时
进入 `REMOTE_STOP_AND_RETAIN`，断线/硬杀时远端状态保持未知。远端 result 只能生成至多一次；
通道已不可用时只由本地 acceptance receipt 记录缺失，绝不合成 remote result。之后不能再生成
intent/plan、换名或重新连接。`CARRIER_CONSUMED` 是本地 marker `O_EXCL` 成功的瞬间；
`CONSUMPTION_RECORD_COMPLETE` 必须在发出任何 transport 字节前完成。每个 `*_INTENT`
必须在该 case 的 roots/ledger 之前，每个 `*_PLANNED` 必须在 owner/submit/start 之前
create-only 持久化；后一个 intent 在前一 case 语义 PASS 前必须不存在。

## 4. case 对象和语义

每 case 有两个 slot；每个 slot 各含 `work`、`evidence`、`temporary`，另有一个
`retained_store`。每根 1 MiB / 128 inodes，须有唯一 filesystem/project identity、project
inheritance、accounting/enforcement 和稳定 dev/inode。二十一个 domain 全局不重合。case
preparation 才能 create-only 建立该 case 的 roots、ledger 和计划输入；正常入口在首次 submit 前
继续执行原 empty-ledger 检查。

### `H01_NORMAL`

H01 从自己的空 ledger 只受理一次固定 `host.inspect`。真实 Broker/Runner、quota grant、system
manager 和 supervisor 完成 `preflight → business → evidence`；PASS 同时要求原 request/plan/grant、
三类 unit identity、helper 退出、result_reader 实际 result、client wait status、双 EOF、future-start
阻断、writer/collector 停止、树退出、ledger 终态和 evidence seal。单个状态字符串或离线一致性
不能补判 PASS。

### `Q4_HELPER_RUNNING_CANCEL_SUBSET`

该 case 从自己的空 ledger 受理一次 preflight。只有原 helper 被真实观察为 RUNNING 且期限有效时，
原 owner 才调用一次 `broker.cancel`。PASS 要求既有 Q4 合同的 durable cancel、cancel 返回、无 cancel
后 delivery、原 helper identity、停止 ACK、helper 真实退出、全部 exit flags、client return code、
双 EOF 和外层停止/evidence 均完整。

必须记录 `full_h07=false`：它不是 H07，也不验证完整 generation/start-gateway 矩阵；现有
`chain_closed=false`、`ordinary_phase_closed=false`、`independent_ordinary_cleanup_required=true`、
`q3_accepted=false` 和 `production_supported=false` 保持。自然先结束、未命中 RUNNING、UNKNOWN
或缺证都不是 PASS，且不重试提高命中率。

### `H11_SAME_LEDGER_RECOVERY`

H11 origin 仍经 normal empty-ledger 检查，只 submit 一次，形成原非空 ledger、operation/execution、
grant/deadline/lease、delivery intents 及 bootstrap/helper/result_reader 原 unit identities。固定故障点是
result-reader manager receipt 已持久且 `h11_delivery_barrier=true`、collector 尚未 start；此时 root
launcher 以已持有 pidfd 有界 SIGKILL 原 ordinary resident/broker 并收回其 wait 事实。原 root
launcher/owner/Gateway 保持，随后由它们启动 recovery resident；recovery 只按**原 canonical
`jobs.sqlite` path**重新打开并恢复/观察这些原 unit，不重启业务。同一 filesystem object 的结论
仅来自 D 一直持有的 fd 与最终 path binding；candidate origin/recovery 两次 StateStore open 只分别
证明打开成功，不声称 candidate 导出或比较了两次 open 的 dev/inode。

恢复禁止 submit、start、result reread、新 grant、新 reader、新 unit、替换 operation/execution/unit
identity 或延长 deadline。语义 PASS 恰要求唯一恢复屏障、原身份不变、future start blocked、trees
exited、writers stopped，同时保持 `outcome=UNKNOWN`、`collectors_stopped=false`、
`effects_checked=false`、`leases_retained=true`、`result_reread=false`、`start_replayed=false`，且
evidence 不得提升为 SEALED。H11 只能收回 recovery observation/verdict、原 handle/unit/
execution 身份引用和仍持有的外层流；不得打开、复制、hash 或封装原业务 result bytes，
也不得生成替代
business evidence seal。本故障点没有可接受的业务 result content digest/receipt；origin reader
是否已经读取内容不作独立结论，`result_reread=false` 只描述 recovery。可不读取
bytes 固定的 identity 只是 evidence root 下由候选 `result_name(execution_id)` 派生的
expected path/name，以及原 `handle_sha256`、result-reader unit/InvocationID 和 execution identity。
对 H11/preflight，expected basename 恰为
`result-f7b176ecb6b8081fac3a7a47.json`；记录它不允许 stat/open/hash 该文件。外层 launcher/supervisor/
owner 的 control-closure seal 仍必须存在，不能与 `record.evidence != SEALED` 的业务事实
混淆。该 PASS 不是业务成功。

H11 的 `recovery-proof` 不扩写候选没有导出的 raw 事实。其顶层 key 恰为本节 schema 表所列；
`candidate` 恰含 `commit,tree,h11_source_path,h11_source_sha256,resident_source_path,
resident_source_sha256,launcher_source_path,launcher_source_sha256`，路径/摘要逐字段来自 A 固定
projection。`recovery_summary,launcher_result,gateway_snapshot,origin_capture,control_seal` 各恰为
`path,bytes,sha256` 的现有 create-only artifact reference；path 逐项等于上文固定的 recovery、
launcher-result、gateway、origin-capture 和 outer-owner seal member path，不得根据预期值重写其内容。
supervisor raw seal 虽不重复进入 proof 字段，仍是 H11 required control-seal member，并由 verdict 的
`control_closure_sealed` 与两层交叉验证绑定。
`recovery_plan` 恰含 `path,bytes,sha256,embedded_plan_sha256`，其 path 指向现有
`recovery-resident.json` declaration；`sha256` 摘要 launcher `encoded()` 产生的含 LF raw
declaration bytes，`embedded_plan_sha256` 恰为
`SHA256(quota_contract._canonical(declaration["recovery"], REQUEST_LIMIT))`（无 trailing LF）并等于
`gateway.json.recovery_plan_sha256`。不声称
候选产生了 standalone recovery-plan 文件。`ledger_identity` 恰含 `path,dev,ino,unchanged`：D 在
owner/submit 前以 O_NOFOLLOW 打开并一直持有同一 ledger fd，origin/recovery 后比较 held fstat、
path lstat 全部一致，且 candidate origin/recovery 两次 StateStore open 各自成功，才可令
`unchanged=true`；candidate 不导出两次 open 的 dev/ino，故该事实不声称逐值比较二者，也不排除
无法观察的中间换回，只证明 D 持有对象未变和最终 path 仍指向它。它不声称存在 content before
snapshot。`result_identity` 恰含
`expected_path,expected_basename,stat_performed,opened,hashed`；basename 固定为上述值，后三项
必须均为 `false`。

`assertions` 恰含
`same_operation,same_request_digest,original_handle_admitted,same_original_stage_units,
same_grant_and_deadlines,leases_retained,delivery_intents_unchanged,recovery_launch_forbidden,
gateway_parts_unchanged,recovery_barrier_count,quota_exit_pending_count,
start_replayed,result_reread,deadline_extended,
future_start_blocked,tree_exited,writers_stopped,collectors_stopped,effects_checked,outcome,
business_evidence_sealed`。前九个布尔项均为 `true`，两个 count 均为 `1`；
`start_replayed,result_reread,deadline_extended,collectors_stopped,effects_checked,
business_evidence_sealed` 均为 `false`；
`future_start_blocked,tree_exited,writers_stopped` 均为 `true`，`outcome="UNKNOWN"`。
这些值只在 pinned candidate 的 `_admit()`/`run()`、launcher validator 和真实 summary 全部成功时
记录；`original_handle_admitted=true` 只表示 recovery 开始时原 handle digest 命中 plan，不能
升级为 recovery 后 handle raw bytes 未变。`same_original_stage_units` 只在
`recovery_plan.units == recovery_summary.units ==
{item.stage:item.unit for item in gateway_snapshot.stages}` 时为 true；`gateway_snapshot.stages` 必须
恰含三个 `phase="preflight"`、stage 唯一且分别为 `bootstrap/helper/result_reader` 的 record，三个
`invocation_id` 必须是互异的 32-hex。`gateway_parts_unchanged` 只表示 gateway 原三 part keyset 未扩展；
`recovery_launch_forbidden` 只由 pinned `dispatch()` 的 recovery-only whitelist 在源码上排除 launch，
再联合最终 raw gateway snapshot 的 `recovery_only=true,recovery_finished=true,failure=null` 和原三
stages 未扩展；snapshot 的 `calls` 只是计数，不是逐次 op log，故不声称它能证明 whitelist 或全局
新 unit 不存在。它们也不声称全局 unit/reader inventory 未变化。其余值只明确表示
候选内部已执行相应断言；它们不是
D 独立观察到的 lease-before 明细、grant raw
bytes、pre-recovery ledger snapshot 或 origin PID starttime/pidfd。候选不导出的这些字段不得在
verdict、package 或最终报告中伪造为独立证据。

## 5. 新时间请求与既有 per-case 上界

本 scope **新请求**一个最大 900 秒、永不刷新的 carrier 绝对 deadline，覆盖首次本 scope 现场
读取、唯一连接、package 传输/安装、三个 case、停止、EOF 和证据收回。调用端在任何该类现场读取
或发出连接前紧邻取得 BOOTTIME-first、MONOTONIC-second 原点并固定各自 `+900s` deadline；先
持久化 `CARRIER_CONSUMED`，再且只再发一个 request。此前 2026-10-03 的历史只读观察不属于该
request，也不能替代本次 binding。

remote HELLO 后，调用端以紧邻 BOOTTIME-first/MONOTONIC-second bind sample 到两个 host
deadline 的较小剩余量向下取整到 1 ms，先减固定 2 s processing margin，再减 host
自己的 15 s local-final reserve；非正即拒绝。
guest 只使用 BIND 中这个一次传入的 duration 从 HELLO 的自身 BOOTTIME/MONOTONIC
原点派生独立的双 deadline，不能用后续握手刷新，也不声称它们可与 host
deadline 直接排序。guest 在自身最早 outer deadline 前固定保留 45 s：最多前 30 s
只用于有限 stop、remote final/evidence manifest 和 remote EOF，其余至少 15 s 是无新
业务/无新写入的 guest guard。另外，host 以自己的 deadline 独立保留已在 BIND 前
扣除的 15 s，只用于 local wait、双 EOF、capture fsync/复读和最终 receipt；两个
15 s 不是跨 clock 映射。业务、安装或新 plan 不得借用任一 reserve。

每个 case 在创建任何 root/ledger/plan 前都须证明到 guest `outer-45s` 至少还剩
`150s preparation + 120s owner = 270s`。preparation deadline 恰为
`min(case_origin+150s, outer-45s-120s)`；owner 只有 preparation 完整 PASS 后才取得一次 deadline
`min(owner_origin+120s, outer-45s)`。两者都再取既有内部 deadline 的较早者，未用时间不转给另一
case。换言之，JIT case gate 的固定最小 guest remaining 是 315 s（270 s case envelope + 45 s
final reserve）；不满足时该 case 保持 `NOT_RUN` 并进入 `STOP_AND_RETAIN`。这些是本 scope 的新
聚合/逐 case 上界，不来自旧批次批准；D 必须覆盖 2 s margin、45 s reserve、315 s gate、不刷新、
前项未 PASS、剩余不足和重复 request 的拒绝测试。

每 case 保持现有核心合同的下列上界；取消和恢复不因只运行 preflight 而退款：

| 层级 | 每 case 上界或固定值 |
| --- | --- |
| operation | 72 s wall、1 s terminate grace、30 CPU-s、64 MiB、8 processes、1 MiB temporary、0 NAS、98,304 B log、8 MiB reservation |
| phase/stage | 每 phase 24 s / 10 CPU-s；bootstrap/helper/result_reader 为 3/4/3 CPU-s |
| controller/ordinary parents | controller 512 MiB/64 tasks；ordinary 256 MiB/32；retained ordinary 256 MiB/64；均 100% CPU rate、swap=0 |
| target | 256 MiB、32 tasks、100% CPU rate、85 s + 1 s stop；1 MiB/64 inodes |
| supervisor | 64 MiB、32 tasks、100% CPU rate、100 s + 1 s stop；8 MiB/64 inodes |
| owner | 120 s、120 CPU-s、512 MiB、64 tasks、8 MiB/64 inodes、69,632 B output |
| management stages | collector/admission/query 各 64 MiB、8 tasks、2 CPU-s、32,768 B output；runtime 依次 8/7/5 s，receive/stop 各 1 s |
| management capacity | 400 CPU-s、1536 MiB、1024 pids、16 MiB output、32 MiB/1024 inodes；4 MiB manager wire 计入 output |
| durable storage | state 8 MiB/1536 inodes；journal 1 MiB/128；capture/declarations 20 MiB/384 |
| quota roots | 七根各 1 MiB/128 inodes |

表中的 30 CPU-s 是既有 operation CPU 上界，不是新 carrier 的分段时间或 case 间窗口。

预算 charge topology 固定如下，D 不得另选相加/取最大规则：

1. `management capacity` 是每 case 对三项 management grant、target/supervisor control envelope 和
   owner 的**嵌套总 envelope**；表中这些子项不得再与它相加。三个 case 串行且进入下一 case 前原
   tasks 必须全退出，因此 management memory/pids 的现场并发上界仍为 1536 MiB/1024，而不是三倍。
   operation 的 30 CPU-s、64 MiB/8 processes 不属于这个 management envelope：每 case 可消耗 CPU
   恰为 `400+30=430 CPU-s`，三 case 不退款合计 **1290 CPU-s**；management output 三 case 合计仍为
   48 MiB。
2. management/owner/target/supervisor 的 storage 子项只在每 case 的 32 MiB/1024-inode management
   capacity 内嵌套，彼此不得再相加；其最终写入必须落入 state、journal、capture 或七根的既有
   physical cap，不能另建 32 MiB pool，也不能用逻辑 management headroom 扩大实际写入。
3. candidate 实际可写 physical cap 每 case 恰为 state 8 MiB/1536 + journal 1 MiB/128 +
   capture 20 MiB/384 + roots 7 MiB/896 = **36 MiB（37748736 B）/2944 inodes**；三 case 即
   **108 MiB（113246208 B）/8832 inodes**。为在不能证明全部逻辑重叠时保守准入，本 A 另要求把
   management 32 MiB/1024 作为只读 capacity headroom 加入 admission：每 case
   **68 MiB（71303168 B）/3968 inodes**，三 case **204 MiB（213909504 B）/11904 inodes**。
   这不是新的 directory、quota 或可消费 storage；`capacity.new_required_*` 使用 admission 数，
   实际写入仍受前述 36 MiB/2944 physical cap。case PASS、取消、UNKNOWN 或提前结束均不退款。
4. 唯一共享 code/install delivery 池为 **64 MiB/4096 entries**，覆盖 `.lhfp`、完整 clean checkout/
   Git metadata、wheel、A projection manifest、D bootstrap/dispatcher、compiler inputs/native build、
   projected harness、venv/安装树和所有 staging 的同时实际分配峰值；不是各成员各得 64 MiB，也不
   按 case 重发。另有唯一 carrier/admission/audit 池 **8 MiB/512 inodes**，只覆盖 shared install
   和三个 case pool 之外的 carrier session、准入、聚合与 final records，不得被 case 或安装借用。
   故本 scope guest physical cap 合计恰为 **180 MiB（188743680 B）/13440 inodes**；把上述保守
   management headroom 计入后，capacity admission 合计恰为
   **276 MiB（289406976 B）/16512 inodes**。两者都须与现场已有/历史未释放义务相加后准入，
   但 admission 数不能被写入路径当作 physical cap。
5. 单一 carrier stdin 的 BIND frame 最多 4112 B，`.lhfp` 最多 33550320 B，两者
   合计最多 32 MiB；stdout+stderr（连同 HELLO）合计最多 **60 MiB**。三个 case 各自
   management output 仍最多 16 MiB，三者合计 48 MiB 是 60 MiB carrier output 的嵌套子预算，
   不是可再相加的额外额度；其余 frame/protocol/final manifest 必须共享剩余 12 MiB。
   本地 private capture 最多 64 MiB/16 inodes；stdout/stderr 按实际流 bytes 计，提取的 remote
   result、capture manifest 和 receipt 作为额外物理 bytes 再计入剩余 4177920 B，不能按
   逻辑内容去重。它不是可供 guest 消费的新 storage。超限立即截断为不完整，截断不能产生 PASS，
   且不得另连补采。
6. 外层 carrier 可消耗 800 CPU-s，与三 case 的 1290 CPU-s 相加得到本 scope 总上界
   **2090 CPU-s**。现场 peak admission 保守相加 outer 1 GiB/128、单个串行 case 的 management
   1536 MiB/1024 和 operation 64 MiB/8，得到 **2624 MiB（2751463424 B）/1160 pids**；不得把
   串行三个 case 的 memory/pids 再乘三，也不得用这个 peak 扩大任何 unit 自身限制。

dispatcher 须把上述静态承诺、共享父级和全部历史未释放义务按实际 filesystem 分别做容量检查；
串行执行不退款，也不把逻辑 envelope、物理持久承诺和瞬时并发上界互相冒充。

## 6. 停止与排除

- 任一非合同预期的 FAIL、BLOCKED、UNKNOWN、timeout、disconnect、身份/摘要/预算漂移、stop
  缺失、应有 EOF 缺失或证据不完整，立即禁止新 case并有限停止；不重试、不发第二 request。
- H11 合同要求的业务 UNKNOWN 和丢失原匿名 collector 事实按原样保留；除此之外，本次仍持有的
  carrier/dispatcher streams 必须取得真实 stop/EOF。
- namespace/watchdog 保持暂停并从 harness 排除；不借用其入口、fixture、预算或现场权限。
- production `E3_SUPERVISION_UNVERIFIED` 保持；test-only 通道不接普通 CLI/MCP/Plugin 或生产配置。
- 不改 host/guest 系统配置、账户、mount、quota 上限、网络或现役服务，不用 mock/model/手写结果
  代替实测，不扩展到 S2、E4–E6、真实 NAS 或其余矩阵。

最终必须分别报告：carrier 是否发出；三个 case 是否实际运行；H01 任务是否真实执行并收回
result/evidence；Q4 subset 的 `full_h07=false`；H11 的原 ledger/unit/deadline 与保守 UNKNOWN；
以及剩余直接阻塞点。
