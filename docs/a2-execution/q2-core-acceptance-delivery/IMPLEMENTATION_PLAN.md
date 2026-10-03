# Local Hand 核心实机验收交付：实施方案

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。
- Scope：`LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1`；R 与[需求](REQUIREMENTS.md)一致。
- [需求](REQUIREMENTS.md) → [架构](ARCHITECTURE.md) → 本方案。
- 本草案不创建 Owner B 或独立 C，也不授予现场实施、package delivery 或 carrier request。

## P0：固定已完成的核心候选

在既有 CLOSED 核心开发权限内已经完成并冻结：

1. normal 入口继续执行一份 fixture raw empty-ledger gate，并在 resident submit 紧前执行原
   `compose()` 内部空账本断言；后者不生成第二份 raw snapshot。H11 test-only recovery 只使用原
   ledger/unit/grant/deadline，禁止 submit/start/result reread/new grant/reader/unit、deadline
   extension 和 release。
2. full-tree 来源绑定改为严格 manifest projection；generator、verifier 和 loader 拒绝缺失、额外、
   漂移、预导入、路径别名及 namespace/watchdog 来源。
3. production `E3_SUPERVISION_UNVERIFIED` 保持；H11 和本 scope JIT 路径不接普通 CLI/MCP/Plugin。

准确静态值是 candidate `4b6e4a7c403362358192086b88679e1326dcb2e1` / tree
`4d4349580c9f4b67cc26f601126849c2bc8d76a4` / direct parent
`607100a57206f7dc7cfcbd6cae8507cfa599b813`、wheel
`infra_local_hand-0.2.0a1-py3-none-any.whl` / `288375` B /
`ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9`、payload digest
`b4d094a9f70c308c63870c9fbf273b6b0646ad211d6f61a79901f52e67cf2e23`，以及 projection
manifest `11811` B / `55f555fc225edca943b8c86cee8119c4878f5ec1e9503a084ba7a560cf2c991d` /
89 entries，以及 `artifact-receipt.json` `1294` B /
`f34baa40ceb3bbce99d02cfef1c8748990d9e405df7fe56d14c15cc8e49f3e5e`。receipt 只允许
exact-hash-only 复用，不把 `dist/` path 提升为批准来源；它明确 raw installed-verification report
`report_retained_in_artifact_set=false`，故 A artifact set 不含该 report，D/package 不得读取、封装
或假称保留它。任何一项变化都须产生新的准确文档基线；不得用 dirty/ignored input 或占位摘要
freeze。

## P1：形成准确 A、Owner B 和独立 C

1. 以三份 authoritative document、现场输入只读复核及同 commit 的 projection artifact 与 artifact
   receipt 形成准确 A，登记各文件摘要、candidate/wheel/projection/receipt 身份和当前事实边界。
2. 向 Owner 提交可逐项审阅的准确请求：R、A、scope、唯一新增治理前提（隔离 fixture 的既有
   `q1admin ALL=(ALL) NOPASSWD:ALL` 仅供固定 argv 一次调用）、C 后 D/package 实施权、唯一管理
   anchor、固定 logical namespace/安装/case/operation/unit/project 对象、H01→Q4→H11 条件顺序、
   一次 marker/一次 carrier request/不重连不重试、全部 deadline、guest physical
   180 MiB/13440 与 admission 276 MiB/16512（其中 management headroom 不可写）、2090 CPU-s、
   2624 MiB/1160 pids 峰值、32 MiB input、60 MiB output、64 MiB host capture 和 stop/retain 规则。
3. B 原样保留 Owner 准确回复、紧邻批准请求、事件/时间和稳定引用。若回复改变对象、预算、前提或
   一次性边界，只按实际文字处理并按 R 重开；不得推定批准。
4. bookkeeping-only C 只登记准确 R/A/B/scope，不混入实现、package、现场 locator 或观察。
   任何 D 必须直接下降于 C，且 C 与 D 不 squash。

P1 完成前只能继续文档、只读审计和既有候选验证；不得实现 field dispatcher、构造可执行 package、
创建 marker 或连接 guest。

## P2：C 后实现并验证 D

按 A 实现 strict loader、RAM bootstrap、existing-account JIT adapter、JIT dispatcher、package
builder/parser、固定 local carrier client 和 local finalizer。实现恰支持需求固定的十四类协议/证据
记录：HELLO、BIND、dispatch session、case intent、case plan、phase receipt、empty-ledger gate、
ledger export、case verdict、H11 recovery proof、remote result、output package、capture manifest 和
local acceptance receipt；所有 schema、顶层 key、nested shape、enum 和状态 edge 都拒绝扩展字段。

测试至少覆盖：

- `LHCHLO1`/`LHCBND1`/`LHCFP1`/`LHCOUT1` framing 的短读、追加、重复 key、NaN/float、长度、
  摘要、顺序、EOF 和总上界；
- package path/mode/type/origin、candidate tree/Git metadata、wheel/projection、三个 field-code blob、
  member≤4096、manifest≤1 MiB、member≤16 MiB、package≤33550320 B 及共享分配峰值；
- fixed wrapper/fixture source/key/known-host/dependency/environment、canonical remote tokens、argv 和
  broader-sudo disclosure 的逐字节 binding；
- marker 的 held-dir `O_EXCL` 唯一 winner、部分写即消费、同 inode 回读、parent fsync、既有对象/
  loser/崩溃不重试；
- 双钟 handshake 公式：host 900 s 固定 deadline、2 s margin、15 s local reserve、guest cap 750 s、
  guest 45 s remote reserve、不刷新且不跨 clock 排序；
- case intent 在 shared carrier `intents/` 先于任何 case object，固定 planned directories/roots 和
  preparation input hash；plan 补 principal/scopes、planned/observed roots 和 system geometry，早于
  owner/submit/start；下一 intent 只在前一 semantic PASS 后存在；315 s gate、preparation≤150 s、
  owner≤120 s 和 candidate 内部更早 deadline；
- case-plan 顶层 `case_id,preparation_id,predecessor,authority_path,ledger_path` 的固定归属和值，拒绝
  把它们误挂到 phase receipt/ledger export/verdict 或由 dynamic identity 改写；
- existing-account adapter 禁止 `q2_prepare.py` 新账号路径和旧 batch/root/receipt 复用；它只在完整
  checkout staging 中使用真实 contract invariants、driver `validate_plan()`/`facts_from_observed()`
  constructor shape 与 assembly pure validators/`assemble()`；显式禁止旧-scope `decode()`、新账号
  top-level 和 driver `complete()`，checkout 不进 runtime `sys.path`；
- retained raw `preparation-plan.json` 必须作为 reservation 第一文件早于任何 mutation，retained raw
  `preparation-result.json` 必须晚于完整 observed/root re-attestation 且早于 authority/manifest/ledger/
  owner/submit；两者 canonical+LF bytes、同 inode preimage、provenance 摘要与 output member 必须相同；
- direct held-fd raw empty-ledger gate、bound target MainPID 内完整 fixture checker 的独立 `CHECKED`
  report、resident 原内部 assertion 三者的顺序和不可互相替代性；SQLite sidecar/close/checkpoint，
  以及所有 unit/object/identity/deadline 漂移和 create-only race 的拒绝；
- phase receipt 的 `session/index/case/phase`、四个 deadline、`source_artifacts` 数组与其 canonical
  `source_artifacts_sha256`，并机械验证 H01 每 phase 五项、Q4 五项、H11 八项 closed set；每组都含
  candidate raw observer config，并须以冻结 `q2_config.decode()`/`Config.active()` 重建 active grant、
  dynamic units 与 budget/phase/stage deadline；每组还含 0600 candidate raw
  `launcher_output/reservation.json`（role `launcher-reservation`），
  `controller_deadline_ns` 唯一取其实际 `controller.deadline_ns` 并与 plan/其它 raw output 交叉核验；
- H01/Q4 只读 ledger export 的 held identity、原 TEXT、有序 events、无 sidecar与禁止 raw SQLite
  member；raw source 必须是 create-only 0600 `reservation/ledger-export.json`（≤1 MiB、计入 state
  cap），package 只 remap 同一对象到 `records/ledger-export.json`；H11 禁止 ledger export；
- H01 全链缺项、Q4 非 RUNNING/第二 cancel、H11 submit/start/result read/new grant/reader/unit/
  deadline mutation/release 的不可达性；
- H11 proof 带 `session/index/case` binding，只封装 candidate 实际 artifact references、held-ledger
  identity 和标识清楚的 candidate assertions；`recovery_plan` 只摘要 declaration 内嵌 object，不
  伪造 standalone plan、raw-before snapshot、lease rows、PID starttime 或 pidfd，也不在 recovery
  触碰业务 result bytes；
- H01 common 8+special 24=32、Q4 common 8+special 13=21、H11 common 8+special 18=26 的 exact
  path/role/mode/multiplicity closure；H11 0644 declaration 以外均 0600，并拒绝 wildcard、standalone
  identity、raw business result/evidence；
- persisted verdict 只允许 PASS/INCOMPLETE、remote index 只允许 NOT_RUN/PASS/INCOMPLETE 的前缀
  闭包；verdict.artifacts 排除自身，PASS/INCOMPLETE 分别精确列 required-minus-self/实际 packaged
  approved members，verdict 仅由 output manifest 与 remote index 外部绑定；local truth summary 的
  YES/NO/UNKNOWN evidence preimage 与 COMPLETE 组合约束；
- 60 MiB carrier output、64 MiB/16-inode host capture、每 case physical 36 MiB/2944 与 admission
  68 MiB/3968、guest physical 180 MiB/13440 与 admission 276 MiB/16512、1290 case CPU-s/
  2090 total CPU-s 和 2624 MiB/1160 pids 的准确计费与拒绝；admission headroom 不得成为写入额度。

形成干净 D commit/tree；在 D 未冻结并通过上述定向/完整验证前，不得准备 field package。

## P3：冻结唯一 field package 和静态本地资格

从 D 构造唯一 `.lhfp`：完整 clean candidate checkout/Git metadata、固定 wheel、A projection
manifest、D 的 loader/bootstrap/dispatcher。manifest 逐字段绑定 R/A/B/C/D、candidate、artifact、
管理入口/argv、private locator 关系、limits 和成员 origin；记录 package basename、长度、SHA-256、
manifest SHA-256 和全部成员清单。独立 parser 对最终 bytes 完整复核，两次结果须一致。

在任何本 scope 新现场读取前，仅本地完成：

1. R/A/B/C/D 关系、repository object/tree、四份 A 文档摘要、candidate/wheel/payload/projection，
   以及 A 固定 artifact receipt 的 exact-hash-only reuse 条件；
2. held management anchor、`ssh.sh`、`start.sh`、`user-data`、known_hosts、public key、private-key
   identity/derived public key、依赖程序、cwd、环境和固定 local argv；
3. package limits、remote command/ARG_MAX/单参数上限、五个 output basename 与 marker 的本地
   create-only absence；
4. locator relation 能从唯一 private source 逐字段复核，而不是搜索另一个 fixture。

任一不符即 `NOT_ISSUED`。静态资格不得连接 guest、读取 current boot 或创建 marker；工具环境
PID 1 是否 systemd 不是 guest 支持结论。

## P4：一次性消费、握手和远端准入

紧邻首次现场动作采 host BOOTTIME-first/MONOTONIC-second，各固定 `+900s`。在 held anchor 直接
`O_EXCL` 创建最终 marker；创建成功即消费，只有完整 fsync/reopen/same-inode/reread/parent-fsync
后才执行一次固定 client argv。request 发出、连接失败、HELLO 不完整或断线均不重发。

在原通道内依次：

1. 收取并验证有界 `LHCHLO1`，证明实际远端 root Python 处于固定 carrier unit/properties；
2. 重新采 host 双钟，按 `floor_1ms(min(remaining))-2s-15s` 计算一次
   `mapped_duration`，再 cap 到 750 s；写一次 `LHCBND1`、固定 `.lhfp` 和 stdin EOF；
3. bootstrap 在读 package 前复核 guest 双钟界，在 RAM 中解析完整 package/EOF，之后才允许
   create-only staging；
4. 在任何 case mutation 前验证 actual guest boot、PID 1/systemd、cgroup v2、ordinary identity/
   user manager、program/policy、五个 filesystem parent、全部 cgroup parent、project quota、历史
   义务、filesystem 容量和所有固定目标/project/unit absence；
5. 把 actual path/dev/inode/mount/FS UUID/InvocationID 写入 private session admission。任何事实与
   package locator/fixture source 不一致，本地立即 `STOP_AND_RETAIN`；远端只有实际持久化停止事实时
   才记 `REMOTE_STOP_AND_RETAIN`，不得换 locator。

P4 只确认真实 guest；不能把当前 Codex 工具环境当宿主，也不能把其 PID 1 状态外推给 guest。

## P5：受保护安装与 dispatcher 运行前门

仍在同一 carrier 内完成 staging：对完整 checkout 逐 tree/blob 核验、验证 wheel、编译并 pin native
quota helper、生成并逐字节匹配 A projection。create-only 建最终 protected install，只安装 wheel/
venv runtime、projection 核心 harness、native helper 和 D dispatcher。记录 destination/staging
identity、成员摘要、compiler/header/native 摘要及 allocated peak；现有/部分 destination、权限错误
或共享 64 MiB/4096-entry 峰值超限都停止且不退款。

dispatcher 在创建首 case intent 前联合验证：

- session 对 R/A/B/C/D/package/entry/locators/marker 的逐字段 binding；
- H01/Q4/H11 唯一顺序、固定 namespace、case/operation/controller/project/root/directory/unit 对象；
- 14 schema、独立 local/remote 状态机、当前 315 s gate、45 s remote reserve 和不可刷新 deadline；
- 每 case physical 36 MiB/2944、三 case 108 MiB/8832；shared physical 64 MiB/4096、carrier/audit
  physical 8 MiB/512，guest physical 总计 **180 MiB（188743680 B）/13440**；
- management 32 MiB/1024 只作为每 case admission headroom，使每 case admission 68 MiB/3968、
  三 case 204 MiB/11904、guest admission 总计 **276 MiB（289406976 B）/16512**；它不得成为
  directory/quota/写入额度，两种总额都与历史义务按实际 filesystem 合并准入；
- carrier 800 CPU-s/1 GiB/128 pids、每 case 430 CPU-s、三 case 1290 CPU-s/48 MiB output，合计
  2090 CPU-s、峰值 **2624 MiB（2751463424 B）/1160 pids**；case output 嵌套于 60 MiB
  carrier output，不重复相加。

任何一个门失败都不能创建 H01 intent。

## P6：执行 `H01_NORMAL`

证明 guest 到 `outer-45s` 的剩余量满足 315 s gate后，create-only/fsync/回读
shared carrier `intents/c01-h01-normal.json`；intent 固定十二个 planned directories、project
`12101..12107` 七个 planned roots、预算和 preparation input 摘要。existing-account adapter 在完整
checkout staging 中用 contract invariants、driver constructor shape 和 assembly pure validator；
先 create-only 建 reservation directory，把传给 `validate_plan()` 的 raw canonical+LF plan 作为其
第一文件 create-only/fsync/同 inode 回读，再建立其余 directories/roots。全部 observed facts 与七根
identity/retained preimage
复核后，create-only 写入供 `facts_from_observed()` 消费的 raw canonical+LF result；它早于
authority/manifest/policy/ledger/handoff/owner/submit，两个 raw file 的摘要进入 provenance，且最终
从同一 filesystem object 封装。然后按本 A adapter sequence 初始化空 `state/jobs.sqlite` 和
handoff，生成带 principal/scopes、planned/observed roots、controllers/system geometry/request/预算/
deadline 的 `H01_PLANNED`；不得调用旧 scope `decode()`、新账号路径或 driver `complete()`，仍不
启动业务。

D 在 owner 前以 held fd 取得稳定 raw ledger snapshot、调用 pinned `empty_ledger()` 并持久化唯一
一份带 session/index/case binding 的 raw empty-ledger gate；preparation 与该 direct gate PASS 后，
owner 才取得一次不超过 120 s 的更早 deadline并启动，随后须在 bound target MainPID 内独立运行完整
checker 并保留 raw `CHECKED` fixture report，两个门不可互相替代。resident 在 submit 紧前由 pinned
`compose()` 内部断言原 ledger 仍空，并只 submit
固定 `host.inspect` 一次。verdict 只记录受限 `resident_empty_gate` assertion 和随后唯一匹配的
ACCEPTED operation/event，不伪造第二份 raw snapshot。真实 Broker/Runner、quota grant、system
manager 和 supervisor 依次执行 preflight→business→evidence。

收取并联合验证 request/plan/grant、manager delivery、固定 unit identity/InvocationID、helper/
result-reader exit、真实 result、client wait、双 EOF、future-start/tree、writers/collectors、ledger
终态和 evidence seal，并在 writers/collectors 退出与 checkpoint/close 后只读导出原 ledger；export
先以≤1 MiB、0600、canonical+LF create-only 写入 `reservation/ledger-export.json`、fsync/回读并计入
state cap，再把同一 source object remap 到 package `records/ledger-export.json`。
H01 output exact set 是 common 八项（intent、plan、两份 raw preparation preimage、empty gate、
fixture-check、authority、verdict）加三份 raw observer config、三份 phase receipt、三份 phase result、
launcher reservation、gateway、launcher result、resident stdout/stderr、capture/wait、ledger export、固定 business result、
同一 `seal_id` 的 evidence archive/manifest/seal、supervisor/owner 两份 stop 与两份 control seal，
共 32 项，全部 source mode 0600。`required_members_sha256` 只绑定这 32 项；不得补造 result receipt
或 standalone unit receipt。每份 phase receipt 的 `source_artifacts` 都严格为 preparation result、
相应 phase 的 raw observer、phase result、launcher result 和同 case launcher reservation；D 用冻结
q2_config decoder 联合 plan/launcher 重建 dynamic grant、units 与三个 dynamic deadline，并只从
reservation 的实际 controller envelope 取 controller deadline。两份 raw stop 还须与 control seals、wait、
verdict 交叉绑定。
只有完整 `H01_NORMAL=PASS` 才可创建 Q4 intent；否则立即停止，且本地最终 receipt 必须按真实证据
给出任务执行/结果收回的 YES/NO/UNKNOWN。

## P7：执行 `Q4_HELPER_RUNNING_CANCEL_SUBSET`

在 H01 semantic PASS 后且仍满足 315 s gate时，依同一 shared intent→adapter
raw preparation plan→directories/roots→raw preparation result→authority/ledger→plan→direct raw
empty-ledger gate→bound-target full fixture check→resident 内部 assertion 顺序建立 `c02-q4-cancel`，
使用 operation
`ade1b42f-f03d-48dc-b690-e588b44289f6` 和 project `12108..12114`。

preflight 中只在固定 helper 被真实观察为 RUNNING 且期限有效时调用一次 `broker.cancel`；不注入
延时、不循环、不发第二 cancel。验证 durable cancel、cancel return、无 late delivery、原 unit
identity、stop ACK、helper exit/完整 flags、client return、双 EOF 和 supervisor evidence。
semantic PASS 固定保留 `full_h07=false`、`chain_closed=false`、`ordinary_phase_closed=false` 和
`independent_ordinary_cleanup_required=true`。自然结束、未命中 RUNNING、UNKNOWN 或缺证都停止；
不借其它专项结果提升为 H07。

Q4 phase receipt 的 source artifacts 恰为 retained preparation result、raw `preflight/observer.json`、
raw `phase.json`、launcher result 和 raw `launcher_output/reservation.json`，并以冻结 q2_config
decoder 重建 dynamic facts、以 reservation 的实际 envelope 固定 controller deadline。writers/collectors
退出与 checkpoint/close 后只读导出 ledger，按 H01 相同规则从 reservation raw source remap 到 package
records path。output exact set 是 common 八项加 observer、preflight receipt、launcher reservation、
`phase.json`、launcher result、resident stdout/stderr、capture/wait、ledger export、supervisor/owner
两份 stop 与两份 control seal，共 21 项，全部 source mode 0600；不得要求 candidate 不产生的
standalone `cancel.json`。只有
这组机械闭集与固定 Q4 observation 真值全部成立才写 PASS，否则写 INCOMPLETE 并停止，不得创建
H11 intent。

## P8：执行 `H11_SAME_LEDGER_RECOVERY`

仅在 Q4 subset semantic PASS 且仍满足 315 s gate时，按相同 create-only/JIT 顺序建立
`c03-h11-recovery`，使用 operation `4b035797-229a-4cdc-8eca-8195869b7ac9` 和 project
`12115..12121`。同样先保留 raw preparation plan/result，并依次通过 direct held-fd empty gate、
bound-target full fixture check 和 resident 内部 assertion；origin 只 submit 一次。固定
result-reader delivery barrier 持久后、collector start 前，root launcher 以已持有 pidfd 有界 SIGKILL
原 ordinary resident/broker并收回 wait；原 root launcher/owner/Gateway 保持并启动 recovery
resident。recovery 只打开同一 held `jobs.sqlite` dev/inode并恢复/观察/停止原 units，不重启业务。

在调用边界和最终 evidence 同时证明无 submit/start/result reread/new grant/reader/unit/deadline
extension/identity replacement/release。带 `session/index/case` binding 的 recovery proof 只记录
candidate 实际 artifact references、一直持有并交叉复核的 ledger filesystem identity、外层控制摘要
及候选自身已执行 assertion 的明确清单；`recovery_plan` 只绑定 declaration 内嵌 recovery object。
不得将 standalone plan、before snapshot、原始 lease rows 或 PID starttime/pidfd 合成独立证据。
任何合同所需事实不够即 `INCOMPLETE`。

PASS 必须保持业务 `outcome=UNKNOWN`、`collectors_stopped=false`、`effects_checked=false`、
`leases_retained=true`、`result_reread=false`、`start_replayed=false`、business evidence 未 seal，
并证明单一 recovery barrier、原身份/deadline 不变、future start blocked、tree/writers stopped。
origin reader 可能已打开、读取并向随后丢失的匿名 pipe 写过 result bytes；`result_reread=false` 只
约束 recovery，不对 origin content state 作独立结论。expected result identity 仅可记录
`result-f7b176ecb6b8081fac3a7a47.json` path/name 和 handle/unit/execution 引用；禁止 stat/open/hash/
copy/package result bytes，禁止 result receipt 或替代 business seal。外层 control-closure seal 仍须
真实成立；该 PASS 不得写成业务成功。

H11 phase receipt 的 source artifacts 恰为 retained preparation result、raw
`preflight/observer.json`、0644 recovery declaration、recovery summary、gateway、origin capture 和
launcher result，再加 raw launcher reservation；以冻结 q2_config decoder 重建 dynamic facts并以
reservation 的实际 envelope 固定 controller deadline。output exact set 是 common 八项，加
observer、phase receipt、launcher reservation、该 0644 declaration、recovery summary、origin stdout/stderr/capture、
gateway、launcher result、recovery stdout/stderr/capture、recovery proof、supervisor/owner 两份 stop
与两份 control seal，共 26 项；其余 source mode 均为 0600。禁止 wildcard、standalone manager/unit/ledger-identity/
result-identity/recovery、ledger export/raw SQLite、business result 或任一 business-evidence member。
proof 内 ledger/result identity 只是 nested object；recovery、proof 和 packaging 都不得 stat/open/
copy/hash 业务 result bytes。

## P9：远端封装、本地收回与报告

远端在最早 deadline 前停止所有仍持有对象，只生成至多一个 remote result；HELLO 后 stdout 只再
输出一个 `LHCOUT1` frame≤58716144 B，stderr≤4194304 B，连 HELLO 后总输出≤62914560 B
（60 MiB），随后真实 stdout/stderr EOF。manifest 只列实际成员和缺项；每 case members≤16 MiB，
完整 remote result 只在 output manifest 字段出现一次，不得另作 member。每个 member 的 mode 必须
等于封装前 source artifact 的真实 permission（只可 0600/0644），读取前后 single-link identity、
mode、bytes 稳定。H11 不得含 raw ledger、result/result-receipt/business-evidence 或 standalone
ledger/result identity；identity 只在 recovery proof 内嵌。断线或硬杀可没有完整 frame，但不得补写
成功。

本地仅从原 client 通道收取 wait/双 EOF；使用固定五个 output basename create-only 封存两流、
output manifest/members 和提取的 remote result，再生成固定 schema 的 capture manifest。总
capture≤64 MiB/16 inodes：marker≤16 KiB/1 inode，两流≤60 MiB/2，其余≤4177920 B/13；提取的
`.remote-result.json` 是 frame bytes 的物理副本（≤262144 B），必须在剩余额度内再次计费，不能
按逻辑事实去重。capture manifest 的 files 只列实际创建的 marker/stdout/stderr/remote-result 有序
子集并记录 allocated bytes/identity/digest/EOF/wait；它不自引用、不预摘要 receipt。其
`output_package.members_sha256` 必须是 manifest 完整 members 数组按 path ASCII 顺序的 canonical
JSON（无 LF）摘要，而不是 digest 字符串拼接。只有全部对象及 parent fsync、同 inode 完整回读
相等后才写 local acceptance receipt；receipt 是唯一终结记录，不另设 local seal，并须自行 fsync/
parent fsync/同 inode 完整回读后才可接受 `COMPLETE`。

local 状态只走 `STATIC_VERIFIED`→消费/transport→`LOCAL_AWAITING_REMOTE`→
`LOCAL_FINALIZING`→`COMPLETE`，失败为 `STOP_AND_RETAIN`；remote session 只走 remote prefix/
admission/case/final 链或在确实可持久化时进入 `REMOTE_STOP_AND_RETAIN`，永不写本地 COMPLETE。
断线/硬杀可使 remote state 未知，不能由本地补写。

receipt 分开报告：carrier marker 是否创建/完整、request 是否发出、三 case 最终的
NOT_RUN/PASS/INCOMPLETE、H01 `real_task_execution=YES|NO|UNKNOWN`、H01
`result_evidence_collection=YES|NO|UNKNOWN`、Q4 `full_h07=false`、H11 原 ledger/unit/deadline、
candidate assertions、保守 UNKNOWN 与 result-byte prohibition、实际 usage/峰值和全部缺项。

持久化 verdict 只可为 `PASS` 或 `INCOMPLETE`；`RUNNING` 只在内存/session 中存在，final remote
case index 只可为 `NOT_RUN/PASS/INCOMPLETE` 的顺序前缀闭包。verdict `artifacts` 排除 verdict
自身：PASS 恰列 exact required-minus-self，INCOMPLETE 恰列实际 packaged approved members；verdict
本身仅由 output manifest member reference 与 remote case index 外部绑定。两个 H01 local truth summary 的
`evidence_sha256` 必须按需求固定的 local-truth canonical preimage 重算；H01 已启动但事实不足时不得
写 `NO`。execution=`YES` 的 evidence closure 必须包含 launcher reservation，并与 business observer/
phase receipt/result、gateway、launcher result、wait、verdict 共同证明实际 controller deadline 与
执行身份；缺它不得从 plan 补推。H01=`INCOMPLETE` 时，collection 若 exact result、同 seal-id evidence 三件套、gateway、
wait、verdict 与 frame/capture binding 全部成立可以写 `YES`，否则只能 `UNKNOWN`。只有有效
`REMOTE_FINALIZED`、三 case 均 PASS、transport/wait/双 EOF/capture/receipt
终结完整且两个 truth 都为 YES，local state 才能为 COMPLETE。

任一步失败只有限停止并保留原状态；不得 reset-failed、换 ID、清 ledger、回收 roots、刷新 deadline、
重连或重试。即使三个 test-only case 各自达到语义 PASS，也不移除 production guard、不恢复
namespace/watchdog，不自动完成 Q2/Q3、S2、E4–E6 或生产 cutover。
