# Local Hand 核心实机验收交付：架构

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。
- Scope：`LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1`；R 与[需求](REQUIREMENTS.md)一致。
- 本文只设计准确 A、Owner B、独立 CLOSED C 之后的一次 test-only 交付；当前文档提交、
  既有只读观察和核心候选验证都不消费该次现场请求。
- namespace/watchdog 保持暂停；production `E3_SUPERVISION_UNVERIFIED` 保持。

## 1. 授权边界与静态 artifact

准确 A 固定核心 candidate `4b6e4a7c403362358192086b88679e1326dcb2e1` / tree
`4d4349580c9f4b67cc26f601126849c2bc8d76a4` / direct parent
`607100a57206f7dc7cfcbd6cae8507cfa599b813`、wheel
`infra_local_hand-0.2.0a1-py3-none-any.whl`（`288375` bytes，SHA-256
`ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9`）、payload digest
`b4d094a9f70c308c63870c9fbf273b6b0646ad211d6f61a79901f52e67cf2e23`，以及 canonical
projected-source/core-harness manifest `.local-hand-source-projection.json`（`11811` bytes，SHA-256
`55f555fc225edca943b8c86cee8119c4878f5ec1e9503a084ba7a560cf2c991d`，`89` 个 `files`
entry，不含 manifest 自身）。manifest schema 是 `local-hand-q2-source-projection/v1`；
`source_commit`、`source_tree` 和排序的 `files[path]={mode,sha256}` 共同定义唯一运行来源。A 同时
冻结 `artifact-receipt.json`（`1294` bytes，SHA-256
`f34baa40ceb3bbce99d02cfef1c8748990d9e405df7fe56d14c15cc8e49f3e5e`）；它只证明两次独立 build
逐字节一致、candidate direct parent、retention locator、安装态验证摘要和 exact-hash-only 复用，
不把未跟踪 `dist/` 路径提升为批准来源。receipt 明确
`installed_verification.report_retained_in_artifact_set=false`：其记录的 raw installed-verification
report 只以 bytes/SHA/check/command/status 事实被引用，不在 A artifact set 中，现场不得把它当作
package input 或 retained artifact。

完整 clean candidate checkout 仅是安装时的不可导入 provenance/build input。loader、installer
和运行时 verifier 都只允许 manifest 指定闭包，拒绝额外/缺失/漂移、预导入、路径别名及
namespace/watchdog 来源。wheel 延用已验证 build provenance 和
`q2_prepare_build.verify_wheel()`；现场生成的 projection 必须与 A artifact 逐字节相同。

JIT dispatcher、RAM bootstrap、strict loader 和 field package 不属于上述 candidate，也没有
A-time 摘要占位符。只有独立 C 形成后，才可依 A 实现并测试它们、冻结实际 D commit/tree，再冻结
唯一 package basename/长度/SHA-256/逐成员 manifest。D 必须直接下降于 C，不能与 C squash。

现场唯一新增治理前提是：已经隔离的 test-only Q1 guest 的 fixture source 确实给 `q1admin`
配置了 `ALL=(ALL) NOPASSWD:ALL`；这不是 exact-command sudo containment。Owner 只有显式接受
“本 scope 只授权固定 client argv 调用一次”，才可闭合本 scope；不声称该较宽 policy 技术上
只能调用一次或能阻止其它登录/并发 sudo。该前提不授权修改 sudo、sshd、账户、mount、quota、
网络或现役服务。

## 2. 固定 package 与管理入口

field package 采用唯一 framing：`LHCFP1\n`、uint64be manifest length、canonical manifest、按
member path ASCII 字节序拼接的 member bytes；禁止 tar/zip、压缩、padding、trailing bytes、
symlink、hardlink、special file 或 alias。manifest schema 固定为
`local-hand-q2-core-field-package/v1`，逐字段绑定 R、A 四文件摘要、Owner B、C、D、核心 candidate、
wheel、projection、管理入口、准确 argv、private locators、limits 和每个 member 的 path/role/mode/
length/SHA/origin。package 最多 `33550320` B，manifest 最多 1 MiB，member 最多 4096 个且单项
最多 16 MiB；解包前后所有同时实际分配都受共享池约束。

package 恰含完整 candidate checkout/Git metadata、wheel、A projection manifest，以及来自 D Git
blob 的 `field/loader.py`、`field/bootstrap.py`、`field/dispatcher.py`。loader 只做 strict-base64
decode、长度/SHA 核验和 bootstrap 的 `compile`/`exec`；在 package inventory 完整核验前不读取
文件、导入 package code或创建持久对象。

既有管理 anchor 由 held directory fd 固定，并同时复核 `ssh.sh`、`start.sh`、`user-data`、
`known_hosts`、public key、protected private-key identity/derived public key、工作目录、依赖程序及
环境。其唯一 remote chain 是：固定本地 wrapper → fixed known-host/key 的非交互 SSH →
`q1admin` → `sudo -n -- env -i` → system `systemd-run --wait --pipe --collect` → root Python
loader/bootstrap。remote unit 恰为 `lhqcore20261003a-carrier.service`，并固定 `Restart=no`、
`RuntimeMaxSec=800s`、`TimeoutStopSec=30s`、`KillMode=control-group`、`ExitType=cgroup`、
CPU 100%/800 CPU-s、1 GiB memory、swap 0、128 tasks、NOFILE 256、FSIZE 64 MiB、umask 0077。
shell token、argv、environment 和相关实体都由 package 摘要约束，调用端不能重新分词或替换入口。

private locator 只可来自该 management anchor 指向的已知 Q1 fixture source；package 固定五个
filesystem parent、ordinary identity、user/query/controller/management/supervisor/ordinary parent
unit、retained-ordinary cgroup path 和 carrier unit。它们是后续准入的唯一候选，不允许现场搜索、
备选或环境覆盖。此前只读记录只是定位关系，不是当前 boot attestation。

## 3. 一次性本地消费与双钟握手

本地只可在 request 前完成 R/A/B/C/D/package/entry/management binding 的静态核验。任何本 scope
新现场读取或连接之前，调用端紧邻采样 host BOOTTIME-first/MONOTONIC-second，分别固定 `+900s`
deadline，然后在 held management anchor 下以 `O_CREAT|O_EXCL|O_NOFOLLOW` 直接创建
`.lhqcore-20261003a.carrier-consumed.json`。创建成功即 `CARRIER_CONSUMED`，即使后续短写、崩溃
或校验失败也已消费；只有 file fsync、同 inode 重开完整回读、parent fsync 和摘要都成功，才进入
`CONSUMPTION_RECORD_COMPLETE` 并允许启动 transport。既有任何同名对象、并发 loser 或不完整
marker 都拒绝，不删除、不重发。

bootstrap 在读取 stdin 前从实际 remote unit 内采 guest 双钟，输出唯一有界 `LHCHLO1` HELLO。
host 完整验证 HELLO 后紧邻重采双钟，取到两个固定 host deadline 的较小剩余量、向下取整 1 ms，
依次扣除 2 s processing margin 和 host 自己的 15 s local-final reserve：

```text
mapped_duration = floor_1ms(min(host_boot_remaining, host_mono_remaining)) - 2s - 15s
guest_duration  = min(mapped_duration, 750s)
```

非正即停止。host 在同一 stdin 写一次 `LHCBND1` BIND、紧接固定长度 `.lhfp`，随后真实 EOF；
BIND≤4112 B、总 stdin≤32 MiB。guest 只用 HELLO 自身双原点加 `guest_duration` 得到不可刷新双
deadline，并在读取 package 前复核尚未到界；不声称 host/guest clock 可直接排序。guest 最早 outer
deadline 前保留 45 s（最多前 30 s 用于有限 stop/remote final，最后至少 15 s 为无新业务/写入
guard）；host 已扣除的独立 15 s 只用于 wait、双 EOF、本地 capture fsync/复读与 receipt。

断连、HELLO/BIND/package 不完整、host deadline 到达或 unit 状态不明都只收尾并报告，不重连、
不发第二 request、也不另开 collector 通道。

## 4. 远端准入、安装与对象绑定

bootstrap 在 RAM 中验证完整 package framing/inventory/digests 后，才可按 `openat`/no-follow 规则
create-only 建 staging。它在任何 case mutation 前完成当前 guest 准入：boot、PID 1/systemd、
cgroup v2、ordinary identity/user manager、程序和当前 sudo/sshd/authorized-keys/rc 实体、五个
filesystem parent、全部 cgroup parent、filesystem/project-quota 能力、历史义务、实际容量，以及
安装/staging、三个 case、十二类目录、二十一个 roots/project ID、固定 `lhj-*`/controller/carrier
unit 的不存在性。quota query/listener/admission unit 只有逐 phase request digest 产生后，才由候选
原 manager 在 launch 前查 collision/identity，不能伪装成静态 absence。所有目录/cgroup/filesystem
都记录当前 path/dev/inode/mount/FS UUID/InvocationID；
任一 locator 关系、absence、保护或容量不符即停止，不动态换名或找替代 fixture。

staging 内先对完整 checkout 逐 tree/blob 核验并验证 wheel，再编译/pin native quota helper、生成并
逐字节核 A projection。最终 protected install 只含 wheel/venv runtime、projection 指定核心 harness、
native helper 和 D dispatcher；root-owned、不可组/他写，ordinary identity 只有合同所需读/执行权。
destination/staging 任一已存在或 create-only race 失败即停止；失败残留及已建立承诺不退款。

现场 ordinary account 已存在，原 `q2_prepare.py` 的新账号路径会拒绝，不能直接重跑或借此复用
旧 batch。D 必须提供本 scope 专用 existing-account JIT adapter：它仅采用 admission 固定的
UID/GID/user manager 和五个 parent，在 shared carrier `intents/` 先持久化 intent 后，才 create-only
建立本 case 十二目录、七个新 project roots、authority 和空 ledger；禁止 useradd/groupadd、账号
修改、旧 receipt/root 复用。完整且已验证 checkout 仍在 staging 时，adapter 使用其中真实的
`q2_prepare_contract.py` invariants、`q2_prepare_driver.py` 的 `validate_plan()`/
`facts_from_observed()` constructor shape 和 `q2_prepare_assembly.py` 的 pure validators/`assemble()`；
它不得调用固定旧 scope/baseline 的 contract `decode()`、新账号 `q2_prepare.py` 或会从最终 projection
再启动缺少 adjacent contract child 的 driver `complete()`。D 自己实现本 A 的 exact-scope decoder 与
create-only completion sequence，并在进入候选 pure functions 前完成等价或更严格的逐字段验证。

每 case 的 raw `preparation-plan.json` 必须是传给 `validate_plan()` 的 exact canonical+LF bytes，
作为新建 reservation directory 内的第一个文件，先于 reservation 之外任何 case directory/root/
ledger create-only 写入、fsync、同 inode 回读；raw `preparation-result.json` 则必须是
`status=RESOURCES_PREPARED` 且其 `facts` 被传给
`facts_from_observed()` 的 exact canonical+LF receipt，只有全部 observed facts、七根重新鉴证和
retained preimage 前后相等后写入，并早于 authority/manifest/policy/ledger/handoff/owner/submit。
两份 retained raw preimage 的 SHA 分别进入 preparation provenance，回传时必须读取同一 filesystem
object，禁止从 parsed object、intent 或 plan 重编码。H01 使用 system facts；Q4 仅把 non-system
facts 的 schema 改为 `local-hand-q4-cancel-assembly-facts/v1` 且无 `system_geometry`；H11 仅把
system facts 的 schema 改为 `local-hand-q4-h11-assembly-facts/v1` 并保留 geometry，其余字段不得改。
核验后的 policy/handoff 才移交 projected runtime；完整 checkout 不进入 runtime `sys.path`，也不
声称 projection 单独含 `q2_prepare_contract.py` 或 driver 存在独立 decoder。

A 固定 logical namespace `lhqcore-20261003a`、安装/staging basename、三个 case basename、operation
UUID、controller prefix、project `12101..12121`、十二 directory role、二十一 roots 及确定性 unit
派生。C 后动态事实只把这些固定对象绑定到已鉴证 parent、实际 dev/inode/FS UUID、current boot、
InvocationID、quota request unit 和 deadline，不能改变逻辑对象。

## 5. 协议记录和状态机

全部 JSON 采用 package 相同的 canonical encoding 并拒绝额外/缺失字段。架构包含十四类固定
协议/证据记录；每类的准确顶层 key 和 nested shape 以需求为准，D 不得扩展：

1. `local-hand-q2-core-carrier-hello/v1`；
2. `local-hand-q2-core-carrier-bind/v1`；
3. `local-hand-q2-core-dispatch-session/v1`；
4. `local-hand-q2-core-case-intent/v1`；
5. `local-hand-q2-core-case-plan/v1`；
6. `local-hand-q2-core-phase-receipt/v1`；
7. `local-hand-q2-core-empty-ledger-gate/v1`；
8. `local-hand-q2-core-ledger-export/v1`；
9. `local-hand-q2-core-case-verdict/v1`；
10. `local-hand-q2-core-h11-recovery-proof/v1`；
11. `local-hand-q2-core-remote-result/v1`；
12. `local-hand-q2-core-output-package/v1`；
13. `local-hand-q2-core-capture-manifest/v1`；
14. `local-hand-q2-core-local-acceptance-receipt/v1`。

case intent 固定 A-time 逻辑身份、预算、十二个 `planned_directories`、七个原 preparation-contract
`planned_roots` 和整个 preparation input 的摘要；它只写入 shared carrier
`intents/<case basename>.json`，必须在创建该 case 任何 directory/root/ledger 前
create-only/fsync/回读。case plan 只能在 adapter create-only 建立并验证 roots、authority 和空 ledger
后产生，但必须早于 owner、submit 和任何 unit start；它绑定 `principal/scopes`、planned/observed
root、实际 controller/system geometry、canonical request、empty-ledger expectation 和不可增长
deadline。quota request/grant 及阶段 deadline 是 candidate 内部 launch fence 的运行事实，只能事后
形成带 `session_id/index/case_id` 的 phase receipt，不能伪装成 pre-owner plan。
case plan 顶层自身拥有 `case_id,preparation_id,predecessor,authority_path,ledger_path`：case ID 是
basename，preparation ID 来自固定表，H01 predecessor 为 null、Q4/H11 指向前一 basename，两个 path
分别是本 case `authority/authority.json` 与 `state/jobs.sqlite`；这些字段不得误挂到 phase receipt、
ledger export 或 verdict，也不得由 dynamic identity 改写。

phase receipt 同时携带 `source_artifacts` 数组及其 `source_artifacts_sha256`：数组按 `role,path`
排序，每项恰为 `{role,path,bytes,sha256}`，摘要 preimage 是该完整数组的 canonical JSON、无 LF；
两者都必须存在、重算一致，而且每项必须同时是 output-package member。H01 每 phase 的闭集恰为
retained `preparation-result`、candidate raw `<phase>/observer.json`、相应 `phase-<phase>.json` 和
共同 `launcher_output/result.json`，再加本 case 共同 `launcher_output/reservation.json`
（`launcher-reservation`），共五项；
Q4/preflight 恰为 preparation result、raw `preflight/observer.json`、`phase.json`、launcher result
与 launcher reservation 五项；H11/preflight 恰为 preparation result、
raw observer、0644 recovery declaration、recovery summary、gateway、origin capture 和 launcher
result，再加 launcher reservation，共八项。H01 的 observer 是 candidate
`q2_chain.install()` create-only 保存的 exact `q2_config.Config.wire`；Q4/H11 的 observer
则是 candidate `q2_assembly.install()` create-only 保存的同一 exact wire 格式。D 必须用冻结
`q2_config.decode()`/`Config.active()` 联合同一 plan 和
launcher raw output 重建 active grant/request、dynamic units 与 budget/phase/stage deadline，不得从 summary 或
预期值补齐。candidate 在启动 resident 前 create-only 保存的 0600 launcher reservation 含完整实际
`controller_envelope`；receipt 的 `controller_deadline_ns` 只能取其 `controller.deadline_ns`，并与
plan/其它 raw output 交叉核对，不能抄 plan 预期值。
缺一项、mode/path/role/摘要不符即 receipt 不成立；receipt 不伪造 candidate 未产生的 quota/grant
raw artifact。

D 在 owner 前以 held fd 固定并摘要 quiescent raw ledger，调用 pinned
`q2_fixture_check.empty_ledger()`，复核 path/fd identity、bytes 和 sidecar absence 未变后，才
create-only 写一份带完整 case binding 的 `empty-ledger-gate`。owner 启动后，bound target MainPID
内仍须独立运行完整 `q2_fixture_check.check()` 并产生真实 `CHECKED` fixture report，D 不在该返回
与 submit 之间插入写入；这是正常入口的第二个独立门，不能被 direct gate 或 summary 替代。
resident 在 submit 前还执行 pinned `compose()` 的内部空账本断言，但候选不序列化第二份 raw
snapshot/dev/inode/check time；verdict 只能以受限 `resident_empty_gate` assertion 记录其通过及随后
唯一 ACCEPTED operation/event。不得补造第二份 direct gate，也不得把五张 required table 描述为
数据库恰有五张 table。

H01/Q4 的 writers/collectors 退出、StateStore checkpoint/close 且 sidecar 为空后，D 才可在 held
identity 上只读导出固定 raw source `reservation/ledger-export.json`：canonical JSON+单一 LF、0600、
create-only/fsync/parent-fsync/同 inode 回读，最多 1 MiB，并计入既有 state 8 MiB/1536-inode physical
cap。output package 只把同一 source object remap 为 `records/ledger-export.json`；`records/` 不是 guest
目录或第二份文件。export 中 raw ledger identity、唯一 operation 和有序 events 保持数据库 TEXT 原
字符串并按需求严格 decoder 校验；不得切换 journal mode、创建 sidecar、修改 ledger 或把 raw
SQLite bytes 作为 member。H11 不生成 ledger export，也不回传 raw ledger。

本地消费/收回与远端 dispatcher 使用两条独立状态机：

```text
local:  STATIC_VERIFIED -> CARRIER_CONSUMED -> CONSUMPTION_RECORD_COMPLETE
        -> TRANSPORT_STARTED -> LOCAL_AWAITING_REMOTE -> LOCAL_FINALIZING -> COMPLETE

remote: REMOTE_PREFIX_STARTED -> BOUND -> REMOTE_ADMITTED -> INSTALLED
 -> H01_INTENT -> H01_PLANNED -> H01_PASS
 -> Q4_INTENT -> Q4_PLANNED -> Q4_PASS
 -> H11_INTENT -> H11_PLANNED -> H11_RECOVERY_PASS
 -> REMOTE_FINALIZING -> REMOTE_FINALIZED
```

remote session 只能记录 remote 链值或在确实持久化停止事实时记录
`REMOTE_STOP_AND_RETAIN`，永不写本地 `COMPLETE`；local receipt 只能是 `COMPLETE` 或
`STOP_AND_RETAIN`。拒绝、非合同预期 UNKNOWN、timeout、disconnect、stop/EOF/证据缺失使本地
单向停止；断线/硬杀时远端状态可保持未知。之后不能再生成 intent/plan、换名、清理后重试或连接。
下一 case intent 在前一 semantic PASS 前必须不存在；remote result 至多生成一次，通道丢失时只由
local receipt 记录缺失，不能合成远端成功。

create-only case verdict 只可持久化 `PASS` 或 `INCOMPLETE`；`RUNNING` 仅是内存/session 状态，
`NOT_RUN` 只用于从未持久化 intent 的 final remote case index。final remote result 不得含
`RUNNING`，三项只能形成需求规定的顺序前缀闭包；`REMOTE_FINALIZED` 只允许三项均 PASS，否则只能
是实际生成的 `REMOTE_STOP_AND_RETAIN`。local `COMPLETE` 还要求 transport、wait/双 EOF、capture
fsync/同 inode 回读全部闭合，且 H01 任务执行与结果/证据收回两个 truth summary 都为 `YES`；连接
或证据不明只能 `UNKNOWN`，不能把未观察到误写成 `NO`。
H01 verdict 为 `INCOMPLETE` 时，`result_evidence_collection` 若仍具备需求规定的 exact result、
同 seal-id 三份 business evidence、gateway、wait、verdict 与完整 frame/capture binding，可以为
`YES`；否则只能 `UNKNOWN`，不得为 `NO`。后续 Q4/H11 事实不能改写该 H01 truth。
`real_task_execution=YES` 的 truth evidence member closure 还必须包含 retained preparation result、
business observer config、business phase receipt/result、launcher reservation、gateway、launcher
result、wait 与 verdict；缺 launcher reservation 时不得从 plan 推断 controller deadline 或执行事实。

verdict 的 `artifacts` 永不列 verdict 自身，避免摘要自引用。PASS 时它恰列该 case exact required
set 除 `reservation/case-verdict.json` 外的所有 member；INCOMPLETE 时恰列 output package 已实际
封装且属于批准 path universe 的全部 case member，仍排除自身。verdict 只由 output manifest 的
verdict member reference 与 remote-result case index 从外部绑定；不得另造未列 member。

## 6. 三个隔离 case

三个 case 分别是 `c01-h01-normal`、`c02-q4-cancel`、`c03-h11-recovery`，各有独立 policy、
authority、`state/jobs.sqlite` ledger、operation、两组三角色 slot、retained store、capture、
declarations 和 supervisor envelope。每 case 十二 directory role 的 owner/mode、AuthorityLock anchor、
preparation provenance、manifest、SQLite sidecar/close/checkpoint 规则都沿用冻结 candidate；不得伪造
`ledger.initialized`。七根按 work-a/evidence-a/temporary-a/work-b/evidence-b/temporary-b/
retained_store 映射连续 project ID，跨 case、历史对象、安装和输出均不得 alias。

三个 origin 都先走一份 fixture raw empty-ledger gate；resident 紧邻 submit 仍运行原内部空账本
assertion，但不生成第二份 direct snapshot。case 顺序严格串行；任一时刻最多一个 owner/target/
supervisor 活跃。前一 case 的 grant、lease、capture 和 UNKNOWN 义务在后续容量准入中持续列账。

output-package 的 member closure 是机械闭集。carrier 恰有 `session.json`、`admission.json`、
`installation.json` 三项；每 case common 八项恰为 intent、case plan、retained preparation plan、
retained preparation result、empty-ledger gate、bound-target fixture-check、authority anchor 和 verdict。
除 H11 recovery declaration 的 source mode 为 0644 外，下述 required source artifact 均为真实 0600；
封装读取前后须是稳定 single-link regular file，manifest 的 mode 必须等于 producer contract 的真实
permission，而不是 host 端重建 mode。

### H01 normal

`H01_NORMAL` 从空 ledger 只受理一次固定 `host.inspect`，依次真实执行 preflight、business、
evidence。PASS 必须联合证明 request/plan/grant、manager delivery、固定 unit identity/InvocationID、
helper/result-reader 退出、真实 result、client wait、双 EOF、future-start 阻断、tree/writers/
collectors 停止、ledger 终态和 evidence seal。单独零退出或离线文件一致性不能提升为 PASS。

H01 的 required set 恰为 common 八项加 24 项：三份 candidate raw observer config、三份 phase
receipt、三份 phase result、launcher reservation、gateway、launcher result、resident stdout/stderr、capture/wait、ledger
export、固定 basename
`result-03c94c57c840717302854a3f.json`、由 ledger 唯一 seal registration 的同一 `seal_id` 实例化的
evidence archive/manifest/seal，以及 supervisor/owner 两份 stop 与两份 control seal，共 **32** 个
case member。不得补造 candidate 不产生的 result receipt 或 standalone unit receipt。
`required_members_sha256` 只摘要这 32 项按 `role,path` 排序的 `{role,path,bytes,sha256}` 数组，不含
carrier 三项、manifest 或 remote result；三个 business-evidence member、ledger seal registration、
observer config、launcher reservation 与 H01 result-reader identity/wait/verdict 必须交叉一致。stop/deadline/exit 还须由
两份 raw stop、两份 control seal、wait 与 verdict 交叉绑定，不能只从 seal 摘要推断。

### Q4 cancel subset

`Q4_HELPER_RUNNING_CANCEL_SUBSET` 从独立空 ledger 只受理一次 preflight；仅在准确 helper 被真实观察
为 RUNNING 且期限有效时调用一次 cancel。PASS 必须保留 durable cancel、cancel return、无后续
delivery、原 unit identity、stop ACK、helper exit/flags、client return、双 EOF 和 supervisor evidence。
它固定 `full_h07=false`，并保留 `chain_closed=false`、`ordinary_phase_closed=false`、
`independent_ordinary_cleanup_required=true`；不借其它专项结果补成 H07，也不重试提高命中率。

Q4 的 required set 恰为 common 八项加 13 项：preflight raw observer、phase receipt、launcher
reservation、原 `phase.json`、launcher result、resident stdout/stderr、capture/wait、ledger export、
supervisor/owner 两份 stop 与两份 control seal，共 **21** 个 case member。`phase.json` 就是候选 raw cancel case
record，不要求不存在的 standalone `cancel.json`。

### H11 same-ledger recovery

`H11_SAME_LEDGER_RECOVERY` 的 origin 同样经正常空 ledger gate 且只 submit 一次。固定故障点是
result-reader manager receipt 已持久、`h11_delivery_barrier=true`、collector 尚未 start；root
launcher 用已持有 pidfd 有界 SIGKILL 原 ordinary resident/broker 并收回 wait，原 root launcher/
owner/Gateway 保持并启动 recovery resident。recovery 只重开同一 `jobs.sqlite` dev/inode，
恢复/观察/停止原 units，不重启业务。

恢复调用边界禁止 submit、start、result reread、新 grant/reader/unit、替换 operation/execution/
unit identity、延长 deadline 和 release。带 `session_id/index/case_id` 的 proof 只引用 candidate 实际
导出的 origin capture、gateway/recovery output、outer control 和 held-ledger identity；
`recovery_plan` 引用 `recovery-resident.json` declaration 内唯一 recovery object，而不伪造 standalone
plan。D 把 candidate 内部已执行的同 ledger/request/
handle/grant/deadline/lease/delivery/unit、单一 barrier/`QUOTA_EXIT_PENDING`、无 reread/replay 断言明确
标为 candidate assertions；不得把 candidate 未导出的 raw before snapshot、lease rows、PID
starttime 或 pidfd 伪称为 D 独立观察。缺少合同必需事实只能 `INCOMPLETE`，不能由 dispatcher 推断。

H11 PASS 仅证明恢复屏障与退出安全不变量，同时保持 `outcome=UNKNOWN`、
`collectors_stopped=false`、`effects_checked=false`、`leases_retained=true`、
`result_reread=false`、`start_replayed=false` 和业务 evidence 未 seal。origin reader 可能已打开、
读取并向随后丢失的匿名 pipe 写过 result bytes；`result_reread=false` 只约束 recovery，不对 origin
content state 作独立结论。expected result identity 仅是
候选算法派生的 `result-f7b176ecb6b8081fac3a7a47.json` path/name 加原 handle/unit/execution 引用；
recovery 路径严禁 stat/open/copy/hash/package result bytes 或生成 result receipt/business seal。
外层 control-closure seal 仍须真实成立；该 PASS 不是业务成功。

H11 的 required set 恰为 common 八项加 18 项：preflight raw observer、phase receipt 与 launcher
reservation；唯一 0644 的 `launcher_declarations/recovery-resident.json`；recovery summary；origin resident stdout/stderr 与
origin capture；gateway、launcher result、recovery resident stdout/stderr 与 capture/wait；H11
recovery proof；supervisor/owner 两份 stop 与两份 control seal，共 **26** 个 case member。
不接受 `recovery*` wildcard，也不接受 standalone manager/unit/ledger-identity/result-identity/
recovery、raw ledger、raw business result 或任一 business-evidence member；proof 内 ledger/result
identity 只是 nested object。recovery 和封装路径都禁止对业务 result bytes 执行 stat/open/copy/hash，
也不得生成 result receipt。launcher result、recovery summary、origin capture、gateway declaration
digest 和两层 raw control seal 必须逐字段交叉绑定。

## 7. 预算、输出与停止

每 case 的可写 physical cap 恰为 state 8 MiB/1536 + journal 1 MiB/128 + capture/declarations
20 MiB/384 + 七根 7 MiB/896，即 **36 MiB（37748736 B）/2944 inodes**；三 case 为
**108 MiB（113246208 B）/8832**。另把 management 32 MiB/1024 作为不可写的保守 capacity
headroom 计入准入，得到每 case **68 MiB（71303168 B）/3968**、三 case
**204 MiB（213909504 B）/11904**；它不是额外目录、quota 或可消费空间。共享 source/build/
package/install physical pool 是 64 MiB/4096，carrier/admission/audit physical pool 是 8 MiB/512，
故本 scope guest **physical 总额为 180 MiB（188743680 B）/13440**，**admission 总额为
276 MiB（289406976 B）/16512**。二者都与历史未释放义务按实际 filesystem 合并准入，但只有
physical 数约束实际写入。

management capacity 是每 case 的嵌套 envelope，operation 30 CPU-s/64 MiB/8 processes 不在其中；
每 case CPU 恰为 400+30=430 CPU-s，三 case 不退款共 **1290 CPU-s**，再加 carrier 800 得总计
**2090 CPU-s**。三个 case 串行，因此 peak 只保守相加 carrier 1 GiB/128、单 case management
1536 MiB/1024 和 operation 64 MiB/8，恰为 **2624 MiB（2751463424 B）/1160 pids**。case
management output 三 case 合计 48 MiB 嵌套在 carrier 60 MiB 内，不另相加。

远端最终 stdout 只可在 HELLO 后输出一个 `LHCOUT1\n` frame（最大 58716144 B）并真实 EOF；stderr
最多 4194304 B，连同 HELLO 后 stdout+stderr 总计最多 **60 MiB（62914560 B）**。output manifest
只列实际成员和缺项；完整 remote result 只在 manifest 的 `remote_result` 字段出现一次，不得复制成
member。output member 的 mode 是 source artifact 封装前真实 0600/0644 permission。H11 禁止 raw
ledger、result/result-receipt/business-evidence member，也禁止 standalone ledger/result identity；
两种 identity 只可作为 recovery proof nested object。
本地 create-only capture
最多 64 MiB/16 inodes，其中 marker 16 KiB/1 inode、两流 60 MiB/2，剩余 4177920 B/13 inodes
用于提取的 remote-result、capture manifest 和 receipt。`.remote-result.json` 是 frame 内 bytes
的物理副本，最多 262144 B，必须在剩余额度中再次计费，不能按逻辑事实去重。capture manifest
只列实际已创建的 marker/stdout/stderr/remote-result 有序子集，逐对象记录 basename/bytes/
allocated-bytes/SHA/dev/inode/mode/nlink；它不自引用，也不摘要未来 receipt。只有全部对象与 parent
fsync、同 inode 回读相等才声明完整。local acceptance receipt 是唯一终结记录，不另设 local seal；
receipt 自身 fsync、parent fsync、同 inode 完整回读成功后才可接受 `COMPLETE`。

remote-result 只陈述 guest 已知事实。本地在真实 wait、双 EOF、frame digest、capture fsync/完整
回读后，才独立生成 acceptance receipt 的 `real_task_execution=YES|NO|UNKNOWN` 与
`result_evidence_collection=YES|NO|UNKNOWN`。只有 H01 business unit identity/InvocationID/wait 和
有效 frame 联合成立，前者才可 YES；只有 H01 result 与必需 evidence members 本地封存复读一致，
后者才可 YES。连接或证据不明必须 UNKNOWN，Q4/H11 不能改写 H01 事实。

所有层只使用固定 outer 与内部更早 deadline。每个 case 创建任何对象前须有至少 315 s guest
remaining；preparation=`min(case_origin+150s, outer-45s-120s)`，owner 仅在 preparation PASS 后取
`min(owner_origin+120s, outer-45s)`，并再取 candidate 内部更早期限。未用时间不转移。停止只引用
原身份；不得 reset-failed、换 ID、清 ledger、回收 roots、刷新 deadline 或清理后重试。
