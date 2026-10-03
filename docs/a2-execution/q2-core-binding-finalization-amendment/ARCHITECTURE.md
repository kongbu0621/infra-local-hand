# Local Hand 核心输入绑定与终结证明修订：架构

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。
- Scope/R 与[需求](REQUIREMENTS.md)一致；只有独立 Owner B 和 bookkeeping-only CLOSED C 后才实施。
- 本文只 supersede 原 core A 的明确冲突字段；未列出的 schema、预算、对象、顺序、停止规则与 exclusion
  继续生效。

## 1. supersede 与版本闭包

| 原 core A | 本修订替代 |
| --- | --- |
| field package v1 | v2：新增一个 root-only approved-input member，entry 改用 local binding |
| management binding 同时声称 local 与 current remote preimage | local binding 只含 request 前可证明的 local facts、anchor/writer 与 static remote expectation |
| locator relation 引用旧 management binding | locator relation v2 引用 local binding；locator 值不变 |
| HELLO v1 只携带 Python | HELLO v2 增加五个 post-entry remote entity relation |
| 三组 approved input 未闭合 | canonical artifact 固定source horizon、policy、36-row obligation、46 configured-quota liabilities、retained和zero-release |
| receipt v1 持久化 `COMPLETE` | receipt v2 只持久化 pending；attestation证明 receipt timely；typed live result才可 COMPLETE |
| restart 可从单一 receipt 推定终结 | restart 最多 `RECEIPT_COMPLETE_ATTESTED`，terminal timing 为 `UNPROVEN` |
| 两流按 logical 60 MiB直接记 allocated | 60 MiB只保留outer refusal；实际capture收紧为52 MiB，并以fixed 4 KiB ext4 model、七对象全过程peak和live endpoint闭合 |

原900秒不变，不存在905秒或尾窗；阻塞调用可以晚返，但过期检查后不再发起持久化/终结调用。
本修订只有需求第2节三项新增治理前提：post-entry JIT guest self-observation、governed
source-horizon completeness，以及local trusted single-writer and stable capture-kernel window。第三项同时
覆盖同credential sibling和整个window内kernel/module/mount/ext4 allocator/ACL/xattr/quota/LSM/model
输入不发生不可回溯的change-and-revert；它不授予host sudo或配置变更。任何一项未被Owner按准确A接受，
本scope保持OPEN。

直接版本化的transport/persistence schema包括：

1. `local-hand-q2-core-field-package/v2`；
2. `local-hand-q2-core-approved-inputs/v1`；
3. `local-hand-q2-core-approved-source-relation/v1`；
4. `local-hand-q2-core-local-management-binding/v1`；
5. `local-hand-q2-core-locator-relation/v2`；
6. `local-hand-q2-core-carrier-consumption/v2`；
7. `local-hand-q2-core-carrier-hello/v2`；
8. `local-hand-q2-core-dispatch-session/v2`；
9. `local-hand-q2-core-local-acceptance-receipt/v2`；
10. `local-hand-q2-core-finalization-attestation/v1`；
11. `local-hand-q2-core-capture-manifest/v2`；
12. 非持久 `local-hand-q2-core-derived-acceptance/v1`。

approved-input nested object另有strict policy/source/obligation/configured-quota schema；local capture另有
`local-hand-q2-core-local-writer/v1`、`local-hand-q2-core-capture-resource-preflight/v1`、
`local-hand-q2-core-capture-filesystem/v1`、`local-hand-q2-core-ext4-allocation-source/v1`、
`local-hand-q2-core-ext4-allocation-proof/v1`、`local-hand-q2-core-loaded-module-measurement/v1`、
`local-hand-q2-core-kernel-source-object-proof/v1`、
`local-hand-q2-core-kernel-source-git-object-archive/v1`、`local-hand-q2-core-capture-write-profile/v1`、
`local-hand-q2-core-capture-immutable-projection/v1`、`local-hand-q2-core-capture-parent-sample/v1`、
`local-hand-q2-core-capture-parent-allocation/v1`和非持久
`local-hand-q2-core-capture-resource/v1`。本列表不是“恰12个schema”的遗漏式注册；需求中的每个exact
schema/keyset均须进入D registry与negative tests。

BIND、remote-result、output package 与 case/phase/evidence schema 保持原版本；capture manifest明确升级v2。
旧 v1
package/HELLO/session/receipt 与新对象不得混拼。所有 strict object 拒绝额外/缺失 key。

### 1.1 exact top-level key

| object | exact top-level key |
| --- | --- |
| field package v2 | `schema,scope,rule,baseline,owner_decision,closure,implementation,amendment,candidate,wheel,projection,entry,approved_inputs,locators,members,limits` |
| approved inputs v1 | `schema,scope,amendment,source_relation,policy_basis,historical_capacity_obligations,retained_preparation,reconciliation` |
| source relation v1 | `schema,locator,obligations,later_nonissuance,zero_mismatch` |
| local management binding v1 | `schema,anchor,writer,wrapper,fixture_start,fixture_cloud_config,profile,environment,dependencies,identity,identity_public,known_hosts,cwd,remote_expectation,transport` |
| locator relation v2 | `schema,local_management_binding_sha256,observation_record_sha256,locators` |
| carrier consumption v2 | `schema,scope,session_id,baseline,owner_decision,closure,implementation,amendment,candidate,package,approved_inputs_sha256,local_management_binding_sha256,writer,capture_resource_preflight,carrier_argv_sha256,host_boottime_origin_ns,host_monotonic_origin_ns,host_boottime_deadline_ns,host_monotonic_deadline_ns,state` |
| carrier HELLO v2 | `schema,scope,loader_sha256,bootstrap_sha256,guest_boot_id,guest_boottime_origin_ns,guest_monotonic_origin_ns,pid,uid,gid,euid,egid,python,remote_management,carrier_unit,process_limits` |
| dispatch session v2 | `schema,scope,rule,baseline,owner_decision,closure,implementation,amendment,package,entry,locators,consumption,session_id,outer,admission,installation,output,limits,cases,state` |
| local receipt v2 | `schema,scope,session_id,consumption,transport,remote_result,wait,capture,real_task_execution,result_evidence_collection,state,missing` |
| finalization attestation v1 | `schema,scope,session_id,consumption_sha256,receipt,host_window,state` |
| capture manifest v2 | `schema,session_id,consumption_sha256,stdout,stderr,output_package,wait,files,logical_bytes,allocated_bytes,inodes,fsync_complete,reread_equal,missing,resource_qualification` |
| derived acceptance v1 | `schema,scope,session_id,receipt_sha256,attestation_sha256,verification_mode,receipt_state,attestation_state,local_state,real_task_execution,result_evidence_collection,receipt_completion_timing,attestation_completion_timing,host_window,capture_resource,missing` |

package、marker、session 的 `amendment` 是逐字段相同的
`baseline,owner_decision,closure,implementation` object。package 顶层 `implementation` 与
`amendment.implementation` 都是新的集成 D；原 partial D 只出现在 predecessor evidence。

package `entry` 是原 exact keyset 中把 `management_entry_binding_sha256` 原位替换为
`local_management_binding_sha256`。`approved_inputs` 恰含
`path,bytes,sha256,approved_source_relation_sha256`。session `admission` 恰含
`binding,guest,programs,policies,parents,filesystems,capacity,absence`；binding 的九字段及 preimage 只取
需求第 4 节。session `output` 保持原 exact key
`stdout_basename,stderr_basename,remote_result_basename,capture_manifest_basename,local_receipt_basename,
output_package_bytes,stderr_bytes`；finalization attestation是固定host-local第七capture对象，不进入session
output或guest package。

package `locators.source_relation_sha256`保留原字段名但只绑定引用local binding的locator relation v2；
它不得与approved-input source relation的`approved_source_relation_sha256`复用preimage或值。

## 2. 静态 source-union 与 package 数据流

```text
held locator archive ───────────────┐
20260927 reconciliation archive ────┤
five normal evidence archives ──────┤
20261001e package/evidence ─────────┼─> two strict builders
  ├─ exact two CURRENT_OWNER_SUPPLIED_RAW paths
  └─ 0048 historical_physical_charges placement
fixed producer Git blobs ────────────┤      │
known later nonissuance records ─────┘      ├─> byte-identical approved-inputs.json
D-pinned held kernel-source object proof ──> offline source/model release gate
held local management anchor ─> local binding
candidate + A/B/C/D + above ─> deterministic .lhfp v2 ─> independent full parser
                                                     └─> release gate
```

source reader 只接收 held descriptors，先校验 archive/member bytes与摘要，再按固定 selector/parser 生成
relation。它不扫描相邻目录、不读 current guest、不从工作解包或 caller 参数补值。两项
`CURRENT_OWNER_SUPPLIED_RAW`必须使用从verified previous-candidate parent机械派生并逐字段等于source
manifest的exact path/source_class/proof_id；caller不能只给id或basename。snapshot 24 rows 的前七行必须
与20260927 producer结果等同，故只保留一次；`20261001e` 的12 rows由固定 accounting blob生成。
0048的`historical_physical_charges`必须重算4327-byte source vector和4549-byte normalized placement vector；
24-row snapshot用`pool_roles`，12-row delta才使用fixed `device_selector`。最终36 rows总计765202432 B/40177
inodes，但只作为completeness checksum，不能替代live按pool账单；46 configured-quota liabilities另为
249561088 B/17792 inodes，并按project/device只加一次。

旧 reconciliation adoption 只提供 integrity/normalization；两项 current-owner raw 的 source class与五项
atime 继续披露，旧一次运行权明确不继承。没有 eligible 五文件 seal时 release 恰为 0。

`.lhfp` v2 只增加一个 `private/approved-inputs.json` member。member origin exact key 为
`kind,bytes,sha256,approved_source_relation_sha256`，kind=`approved-inputs`；mode allowlist 增加 JSON integer 384，
role allowlist 增加 `approved-inputs`。该 member 不进入 ordinary projection、runtime import roots或 output。

两个 builder、完整 package parser、source/full suite、独立 reviewer与 release digest 全 PASS 前，
dispatcher allowlist为空。任何 placeholder/FakeEffects、缺 private raw、非确定 build、old/new schema混用
均 `NOT_ISSUED`。

## 3. local gate、消费与唯一 carrier

pre-marker 顺序固定：

```text
offline source/D/package-template allowlist gate
-> BOOTTIME then MONOTONIC origin; freeze +900s deadlines
-> held local binding + writer + capture-filesystem/profile/parent-baseline qualification + ARG_MAX
-> exact field package dual build/parse + final release digest
-> marker and six local output basename absence
-> O_EXCL marker persistence
-> exactly one carrier request
```

origin前不得读本scope current anchor/mount/superblock/writer/absence。origin后的regular/directory source read
须使用需求规定的O_NOATIME/no-follow held路径且无fallback；只有proof model明确证明不会产生本scope
durable-atime effect的pseudo-fs source可用需求规定的窄例外，UNKNOWN仍失败。pre-marker不得
fsync/write/create。这里的
absence只涉及held local anchor。已有 marker代表已消费；marker absent 而任一 local output存在为
`NOT_ISSUED_CONFLICT`，未消费且不清理。guest install/staging/reconciliation/case/root/unit 的 current
absence 不能在 marker 前声称。

从origin前的offline gate结束到live final sample，Owner接受需求第三项local trusted single-writer/stable
capture-kernel window；inventory与资格重验只发现可见漂移，不冒充排除同credential sibling、中间
change-and-revert或kernel/ext4 tunable热变更。无法维持该window时不创建marker；marker后发现则保留并停止。

marker 把同一local writer与capture resource preflight完整持久化，并使用需求规定的exact v2 keyset和原
create-only原语。O_EXCL成功瞬间即消费；完整持久化前失败
不发 request。完整 marker 才能启动原固定 argv；不允许为了 JIT 先发 probe carrier。
marker及随后六个local output的所有验证性reread统一从同一held parent使用
`O_RDONLY|O_NOFOLLOW|O_NOATIME|O_CLOEXEC`且无fallback。

bootstrap 在唯一 root process 中、读 BIND/package与任何 mutation 前：

1. 以一次 account-record read取得 current passwd account/uid/gid/home/login shell，home必须等于
   `/home/q1admin`；
2. 以固定有界算法解析五个 alias 的 symlink chain并读取 resolved target；
3. 生成 remote-management object，按需求规定的alias→resolved映射验证top-level九字段Python；
4. 绑定原 fixed token/command与 parser profile；
5. 一次编码/flush HELLO v2。

HELLO JSON≤4096 B、frame≤4112 B。实体读取单项≤16 MiB、合计≤80 MiB；它不写guest持久对象，也不产生
第二 input/output pool。host完整验证HELLO后才发送原BIND/package/EOF。host已在marker前对held
local/private raw与approved inputs完成逐字验证；guest只能验证package中自足artifact/digest与current guest
predicate，不能重新读取host-only raw/RFC6901 pointer。任一方都不能用对方的boolean冒充自己可见的raw。

alias/target摘要与policy helper facts是post-entry self-observation，不是执行前containment，也不回溯证明
已建立SSH/首次sudo所用daemon、config、plugin或依赖。这个边界由需求第2节第1项治理前提承接；实现与
报告不得改写为“实际entry inode/loaded image已技术证明”。

## 4. live policy、capacity 与 mutation gate

guest package parser通过后，dispatcher先在同一carrier内执行固定admission：

```text
sudo/sshd/authorized_keys/rc predicate
-> account/program/HELLO cross-binding
-> retained path/domain identity
-> reconciliation + install/staging/case/root/project/unit absence
-> filesystem/quota/current usage observation
-> 36-row historical + 46 configured-quota liabilities + current core per-device capacity bill
-> original protection/deadline/native/effect gates
-> first guest mutation / H01 intent
```

sudo/sshd各至多一次，是carrier内current semantic helper，不是transport、carrier、unit或request；argv、
完整clean environment、cwd/stdin/no-shell、双EOF、combined output、timeout/kill/reap与parser全来自approved
policy object。它们不故意改配置/业务对象，但plugin/NSS/atime/journal/audit incidental effect计入原carrier
预算；其结果只是guest self-attestation。rc shell startup bytes只作provenance。

24个snapshot row不含`device_selector`；它们按固定0048 placement的`pool_roles`映射：`system`必须由
`state_parent`和`install_parent`解析到同一live pool，`quota/journal/evidence`分别由同名held parent解析。
每row的covered paths所得distinct pool set必须逐项等于其roles所得set，并在每个distinct pool收取一次完整
commitment。12个delta row才按fixed `device_selector`取得唯一pool，全部covered path须同pool。两类都不
split、不择优。46个已配置quota hard limits再按`(fs_uuid,project_id)`加一次，并证明新`12051..12057`
absent/unconfigured。同一物理义务只在source relation完全相同才去重；不同义务相加。current free已反映
actual allocation，所以actual只验证“不再加”；full unreleased future与当前core admission都另加。alias、
未知设备、未知inode ceiling、missing source或unlisted consumer都停止。

guest current gate失败发生在 marker后，状态为已消费的 `STOP_AND_RETAIN`。不删除、不退款、不重连。
只有全 PASS 才创建 staging/install或 H01 intent。

九项 binding 原文存入 session/admission member。同一 output-package manifest分别绑定该 session member与
保持 v1 shape 的 remote-result；capture manifest绑定 output manifest/members，receipt再绑定capture。
remote-result本身不新增或声称直接携带九摘要。

## 5. H01、Q4、H11 执行序列

原 execution contract不变：

```text
H01 intent -> plan -> empty-ledger gate -> supervised business execution
-> actual exit/tree/writer/collector/result/evidence closure -> semantic PASS
-> Q4 intent -> helper RUNNING proof -> exactly one cancel -> closure -> semantic PASS
-> H11 intent -> original ledger/unit/request/execution/grant/deadline recovery only
-> no submit/start/result reread/new grant/new unit/deadline extension -> recovery PASS
```

任一前项非 semantic PASS，不创建下一 intent。H11只恢复 observation/control closure；业务不得重启，
result bytes不得读/复制/hash/封装。fake harness只可覆盖负例与顺序，不能成为 field truth。

## 6. finite finalization 与 restart降级

```text
real wait + stdout/stderr EOF
-> remote-result and capture durable+reread
-> success receipt v2 pending (or only-if-still-timely failure receipt STOP) durable+reread + parent fsync
-> receipt parent-allocation sample
-> timely receipt-completed sample
-> one attestation durable+reread + parent fsync
-> attestation parent-allocation sample
-> timely final post-return sample + live capture-resource closure
-> nonpersistent LIVE COMPLETE
```

receipt与attestation都采用完全相同的唯一顺序：create-only/write-all/file-fsync/fstat/close，随后
O_NOFOLLOW|O_NOATIME同 inode reopen（无fallback）、完整 reread、stable fstat、close，最后 parent fsync。对象必须 regular、
0600、nlink=1，uid/gid逐字段等于marker前冻结的local writer filesystem identity，held-parent
name-to-inode不漂移；parent fsync返回后先取得该phase allocation sample，再取post-return双钟。
guest root身份绝不外推到host。existing/partial attestation永久阻止第二次写。STOP receipt也只有在同一
原deadline内能够完成整个durable+reread+parent-sample序列时才允许创建；否则receipt absent，不补写。

每个持久化/终结syscall前后都按BOOTTIME-first/MONOTONIC-second检查原marker deadline。过期检查后
不再发起后续调用；已发起调用若晚返，检测它的post-return clock read可以在900秒后发生但只能失败。
若最终parent fsync、parent-allocation sample或resource closure晚返，留下对象仍保留，live不返回成功。
没有独立stopper尾窗、sample+5s或cutoff；COMPLETE在及时最终sample点决定，不声称调用者return也及时。

状态判定只使用需求第6节的exact 12-row table。只有strict-valid marker/package/capture/receipt-v2 chain才
生成derived object；missing/partial/old/extra-key/identity-drift chain直接拒绝且不生成derived。strict-valid
STOP receipt可产生STOP derived；pending+ABSENT为UNATTESTED，pending+INVALID为STOP；只有LIVE pending+
VALID进入terminal clock/resource sampling，且timely final sample与verified-within resource才COMPLETE；
其它LIVE组合的terminal clocks为null/timing UNPROVEN；RESTART valid pair仅ATTESTED/UNPROVEN。

live typed result必须包含最终post-return双钟事实和保守capture resource closure，才能
`local_state=COMPLETE`。该result不落盘。restart只能由pair证明receipt-completed sample及时，不能证明
attestation自身completion time或历史parent-allocation endpoint序列，故固定
`attestation_completion_timing=UNPROVEN`、`capture_resource.state=UNPROVEN_RESTART`和
`local_state=RECEIPT_COMPLETE_ATTESTED`。task/result字段逐字复制receipt的完整truth object；它不重写
文件、连接guest或改变事实。

## 7. 资源与故障边界

approved-input≤1 MiB但 package≤33550320 B、members≤4096、single member≤16 MiB、shared
allocation≤64 MiB/4096 entries不变。

capture filesystem不能从guest ext4事实、历史old-producer、单独`f_bsize/f_frsize/st_blksize`或当前工具
环境推定。marker前local reader必须在origin后从held current parent/mount/device和D-tree fixed proof/model
生成需求规定的filesystem/writer/read-only baseline。唯一profile为
`ext4-4k-seven-object-52m-envelope-v1`：held parent `STATX_MNT_ID`必须唯一选中mountinfo row，statfs来自
同一parent fd；held mount source必须是`st_rdev`匹配major/minor的block device。同一parent dev、mount
ID+major/minor+UUID、ext4 magic、4 KiB block/frsize/cluster、no-bigalloc、三项fixed raw kernel/config/
module source、由同一source closure解释的trusted loaded-ext4 SHA measurement、完整kernel-source manifest、
features/options、allocator parameters、ACL/xattr/project/FIEMAP/inventory和independent review必须全部
交叉绑定。origin前offline gate还要严格解析D-pinned、host-only且不进入field package/capture的Git SHA-1
object-proof archive：由commit raw机械证明`commit^{tree}`，逐component解析每个manifest path到blob并
重算blob raw SHA-256；self-asserted manifest或只有磁盘module image均拒绝。baseline最多249 entries，全程
最多256；qualification source用删除自身bytes/SHA两key后的canonical body计算，不自引用。独立immutable
projection包括完整mount/options、静态statfs、kernel/allocator、parent policy（含statx mask与
attributes/mask）、write profile/proof/claims，以及从每阶段同一held block-device raw重建的exact
filesystem-static projection。后者只含review固定的geometry、allocation-relevant stable feature masks/
values、UUID/device和mount options；完整初始superblock raw SHA仍留qualification evidence，但free counters、
wtime、journal/recovery state与checksum等经review证明不影响该profile界的正常可变字段不参加阶段等值。
不得用zero/现场mask排除未知feature或allocation path。投影同时排除parent size/blocks等phase-mutable事实；
每个create边界和terminal重算匹配。任一UNKNOWN都
`NOT_ISSUED`，不以host sudo、配置改变或fallback补齐；本A不预先断言当前field已匹配。

原60 MiB仅是outer output拒绝线，本次stdout+stderr有效logical cap收紧为54525952 B。五个非stream role
的raw/base ceiling分别为marker 16384/16384、remote-result 262144/262144、capture-manifest
1048576/1048576、receipt 1048576/1048576、attestation 4096/16384 B；每次O_EXCL前在RAM拒绝超界，未用
role额度不可转移。固定全过程peak为：
两流+tail 54534142 B/2 inodes、child extent/xattr metadata 2097152 B、其余五对象2392064 B/5 inodes，
child peak 59023358 B/7；再加transient preallocation 4194304 B、parent growth 2097152 B、未被child blocks
覆盖的metadata 1048576 B/7 inodes，合计66363390 B/14，距67108864 B/16尚余745474 B/2。marker前
`f_bavail*f_frsize`与`f_favail`至少覆盖该合计。成功路径七个file+parent fsync后各取source-ordered parent
sample；失败路径只允许固定顺序subsequence，remote-result缺失后仍可manifest+及时STOP receipt但不写
attestation，partial samples不成为成功aggregate；
endpoint净增长只验证≤2097152且不冒充中间peak。capture manifest v2复制qualification source并绑定
preflight；LIVE才可凭完整七对象、七phase、不可变资格重验形成VERIFIED_LIVE。restart固定
UNPROVEN_RESTART，不能从当前endpoint恢复历史peak。

故障归类固定：

- source/binding/package/release/writer/filesystem qualification/ARG_MAX/local absence失败：`NOT_ISSUED`或
  `NOT_ISSUED_CONFLICT`，无 marker/request；
- marker O_EXCL成功后的任何 HELLO/BIND/admission/install/case/finalization失败：已消费的
  `STOP_AND_RETAIN`，不重连不重试；
- strict-valid receipt pending而attestation缺失：`UNATTESTED_RETAINED`；strict-valid receipt配INVALID
  attestation为`STOP_AND_RETAIN`；partial/old/extra-key/identity-drift chain拒绝且不生成derived；
- restart看到完整 pair：只闭合 `RECEIPT_COMPLETE_ATTESTED`，不提升 remote UNKNOWN、task/result缺失、
  case失败、local terminal timing或resource endpoint/upper-bound closure；
- production guard与namespace/watchdog路径不进入 package/import/execution。
