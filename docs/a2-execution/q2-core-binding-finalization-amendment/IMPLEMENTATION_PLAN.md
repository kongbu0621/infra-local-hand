# Local Hand 核心输入绑定与终结证明修订：实施方案

- Authority：Owner；状态：**PROPOSED / Gate OPEN / REVISION REQUIRED**。
- Scope/R 与[需求](REQUIREMENTS.md)一致；[架构](ARCHITECTURE.md)规定唯一实现边界。
- 本 proposal 只含文档。Owner B 与独立 CLOSED C 前，不新增/修改 source、test、package、allowlist、
  marker、guest connection 或现场对象。

## 1. R → A → B → C → D 与阶段

当前先完成文档路线收敛：依据已有 management host 材料确认 capture 方案的真实依赖与权限。
第 6.1 节尚未具备的 loaded-ext4 measurement、source proof 和完整 allocation model 不能被
批准文字替代，也不能默认把实现阶段扩成内核分配路径证明项目。未解决前不请求整体批准或执行
下表 A0 之后的步骤；若选用替代存储机制，须明确其对数据、元数据和瞬时分配的覆盖，保持原上限。

| 阶段 | 工作 | 结束条件 |
| --- | --- | --- |
| A0 | 提交准确三文档 A；另建OPEN baseline；A后取得并保留Owner原文B；再建bookkeeping-only C | C引用准确R/A/B且无实现；首个D以C为direct parent |
| D1 | 实现held-source reader、24+12 row union、46 quota liabilities、policy/retained/reconciliation artifact | 两个builder逐字节一致，缺任一raw即失败 |
| D2 | 实现package/local writer binding/capture-FS preflight/marker/session v2与strict digest preimage | old/new schema混拼及FS UNKNOWN全部拒绝 |
| D3 | 实现 HELLO v2 alias/target JIT及 host/guest双向校验 | 单 HELLO/BIND/request；4096/4112不变 |
| D4 | 实现 policy/live admission、逐设备 bill与 post-marker absence | first mutation/H01 intent前全门成立 |
| D5 | 补齐原 review的八项 real field effect、H01/Q4/H11及失败收口 | 不以 FakeEffects替代 field truth |
| D6 | 实现receipt/attestation/capture-manifest v2/typed live result、fixed ext4 peak envelope与七phase总账及restart降级 | 原900秒内完成；restart不COMPLETE/不证明resource closure |
| D7 | targeted/full suite、独立审计、双 package build/parse；冻结 D/package/release digest | 唯一 package identity，红项为0 |
| F1 | 全部门通过后，才创建一次 marker并发一次 carrier request | 失败不重连、不重试、不退款 |
| F2 | 条件执行 H01→Q4→H11并真实收回结果 | 前项非PASS不创建下一 intent |

implementation D 必须直接下降于本 scope 的独立 C。D 发现需改变 candidate/wheel/harness、36-row
source horizon、policy predicate、对象、预算、900秒、一次性规则或治理前提时停止并按 R 重开；不得
在实现中静默扩大。

Owner B还须逐项接受且仅接受需求第2节三项新增治理前提：post-entry JIT、source-horizon completeness、
local trusted single-writer and stable capture-kernel window。第三项覆盖整个window内kernel/module/mount/
allocator/ACL/xattr/quota/LSM/model输入稳定，但不授权host sudo或配置变更。

## 2. D1：approved-input source closure

实现两个互不调用的 pure builder/parser，共同只接收需求固定的 held descriptors：

1. 校验 locator四 carrier与两个member的 bytes/SHA/schema；按16个固定 mapping构造locators与
   16 paths/4 domains retained preparation。
2. 校验 20260927 archive/manifest/48 blobs、A/C/D/tree与三个 producer blob；重算七行而不继承旧
   run permission。两项`CURRENT_OWNER_SUPPLIED_RAW`必须使用机械派生且逐字段等于source manifest的
   exact path/source_class/proof_id，不接受caller只给id/basename。
3. 校验五个 normal evidence archive中十个 plan/observed member、两批 code intent/receipt，以及
   `20261001e` corrected/evidence archive的固定 source members。
4. 从21086 B snapshot重算24 rows、总数与array digest；确认其前七行恰等第2步，不双计。
5. 从固定0048 `/capacity_observed/historical_physical_charges`重算24项source vector（4327 B /
   `edcb0bb95508c15e5b3fb60d679c46c93961e95d8e802a338fc1f4397c18ee0d`）及按0023 plan归一化的role
   vector（4549 B / `b6153d8c45e5b009bcc1f878406565e08bcf7c7d07c17f18361b562bf1096703`）；证明24 snapshot row
   与placement逐index相等，`system`由state/install两个parent解析到同一pool，其余role只取固定parent。
6. 以固定`661e9677` accounting producer仅验证caller七键projection；由本A的deterministic transform从
   exact old-batch inputs生成12 enriched rows；断言management 32 MiB/1024存在、delta总计
   138412032/8064、36行总计765202432/40177。
   对12行只采用批准的 selector：code=`install_parent`、management/state=`state_parent`、
   journal=`journal_parent`、capture=`evidence_parent`、七根=`quota_parent`；
   management机械覆盖旧BASE/reservation/declarations，任一covered path跨设备即停止。
7. 从固定0048 source member重算46个configured hard-limit rows（249561088 B/17792），按live
   `(fs_uuid,project_id)`另加一次；证明12051..12057 absent/unconfigured，不与36 rows或current usage重复。
8. 固定三条 known later nonissuance；任何 source horizon冲突、未知后续 consumer或 release记录都
   返回 blocker，不猜测。
9. 生成四项strict policy object、完整helper execution contract及predicate digest；生成fixed zero-release
   reconciliation。

reader只认 exact archive/member relation，不接受 caller提供 approved rows、默认值、公开散文替代raw、
工作解包或 current guest值。canonical encoder必须有 duplicate/float/NaN/BOM/trailing/overflow负例。

`private/approved-inputs.json` 只可由 root package/bootstrap读取；测试必须证明它不出现在 ordinary
projection、candidate install、`sys.path`、remote output或公开 evidence。

## 3. D2：package、binding与一次性消费

package v2 builder/parser必须：

- 绑定原 core A/B/C、本 amendment A/B/C、新集成 D、candidate/wheel/projection、approved-input raw、
  local binding、locator relation与 field-code origin；顶层 implementation和 amendment implementation
  都等于新 D；
- members仅增加一个 mode 0600/role approved-inputs对象；拒绝 extra/missing/alias/mode/origin；
- 对九个 digest逐项使用需求固定 preimage，测试 newline与nested/full-object混淆；
- local binding加入anchor与完整writer identity；禁止把tool环境/guest root冒充field writer；
- marker v2严格包含`approved_inputs_sha256`、writer和capture-resource preflight，package/marker/session
  amendment逐字段相同；
- marker前双进程 clean build/parse得到相同 package bytes/SHA/member inventory；HELLO后不重冻。

pre-marker gate先完成不读current field的offline source/D/package-template allowlist gate，随后立即取得不可
刷新的BOOTTIME/MONOTONIC origin并固定+900s；只有此后才从held current parent/mount/device和D-tree
proof/model闭合`ext4-4k-seven-object-52m-envelope-v1`、writer、read-only baseline与exact field package。
profile必须以held-parent `STATX_MNT_ID`唯一选mountinfo row、以同fd `fstatfs`，并绑定`st_rdev`匹配的held
block-device source、同一parent dev/mount ID/major-minor+UUID、ext4/4KiB/no-bigalloc、三项fixed raw
kernel/config/module identity、同source closure的trusted loaded-ext4 SHA measurement与完整source manifest、
features/options、allocator、ACL/xattr/project/FIEMAP/inventory。origin前offline gate须读取D-pinned、
host-only的Git SHA-1 object-proof archive，验证canonical object archive、commit raw的root tree、每个
manifest path的逐component tree traversal、blob oid/raw SHA-256和最小无夹带closure；archive不得进入field
package/capture且F1/F2不得创建它。qualification source使用删除自身bytes/SHA字段的canonical body，且current
field model必须经独立review。另构造需求exact immutable projection，排除free counters与parent size/blocks
等phase-mutable事实，但保留parent statx mask与attributes/mask、完整mount/options、静态statfs和其它model
inputs。完整initial superblock raw SHA只留qualification evidence；每个create边界从同一held block-device raw
重建exact filesystem-static geometry/feature-mask projection，正常可变free counters、wtime、journal/recovery
state和checksum只有在review证明不影响profile界时才排除，禁止zero或现场选择mask。每个create边界重算
完整I。regular/directory read要求
O_NOATIME/no-follow且无fallback；只有proof明确证明不产生本scope durable-atime effect的pseudo-fs source
使用窄例外。guest filesystem、old-producer、单独`f_frsize`或历史endpoint净差都不得
采用，也无host-sudo/config fallback。本A不预断言当前field会资格化。最终package双build/parse与release
digest完成后，只检查local marker与六个local output basename。existing marker=已消费；marker
absent而output existing=`NOT_ISSUED_CONFLICT`，未消费且不清理；其它失败=`NOT_ISSUED`。

static template/dispatcher allowlist gate必须在clock origin前完成；任何current anchor/mount/superblock/writer/
absence read不得提前。origin后才做field requalification、exact package finalization和final release digest，且
所有sample仍在原deadline内。marker的open/write/file-fsync/reread/parent-fsync必须是window内第一组
durable syscall；只有完整实现的dispatcher Git blob可入allowlist。
marker及六个output的所有验证性reread都统一使用held-parent
`O_RDONLY|O_NOFOLLOW|O_NOATIME|O_CLOEXEC`，不得沿用v1无O_NOATIME路径。

## 4. D3：HELLO JIT

bootstrap使用已有 root Python process与标准库，不发第二SSH/sudo/systemd-run/carrier command或第二
transport。原 HELLO unit-property读取保持原边界。collector：

1. 从 current passwd ABI固定 q1admin uid/gid/home/login shell；
2. 对五个requested alias逐component lstat/readlink，执行8-hop/64-component/4096-byte限制；
3. 对resolved regular target以 `O_NOFOLLOW|O_NOATIME`读取，单项16 MiB/合计80 MiB；前后复核
   alias、resolved name、held fd与stable metadata；无 fallback；
4. 按`top-level.path=nested.resolved_path`及其余八个同名字段验证两种Python shape，token/command digest
   等于local expectation；
5. 一次编码并flush HELLO；中途失败只可有界stderr/exit，不发送半个成功frame。

host验证HELLO完整shape与4096/4112上界后才发BIND/package/EOF。guest package parser再验证同一
HELLO/local binding/approved input。测试必须明确这些entity是post-entry provenance，不是实际entry inode
或TOCTOU消除证明。

## 5. D4：policy与live admission

dispatcher先在RAM中解析approved input，再依固定顺序执行：

- sudo `-n -ll -U q1admin` current self-observation、C-locale parser、实际euid/root carrier交叉验证；
- sshd source closure与`/usr/sbin/sshd -T` current effective self-observation；
- authorized_keys exact-one-key/no-options及held ownership/mode；
- SSH rc三路径absence与四个shell startup provenance；
- retained path/domain identity、project/hard limit/owner/ancestry；
- reconciliation directory current absence；install/staging/三个case/21 roots/project IDs/fixed units
  current absence；
- current filesystem/quota/usage/available与36 rows逐pool映射：24 snapshot rows按0048 normalized
  `pool_roles`对每row在每个distinct live pool收取一次该row完整commitment，只在同一row内去重；不同
  row/category始终逐行相加。12 delta rows才按fixed selector取得唯一pool；
  两类covered paths均须逐项匹配且不split/择优。另按project加入46 hard-limit liabilities；full future+new
  admission加在current free上，actual不第三次加且绝不退款；
- 原保护、deadline、ARG_MAX、native/install/effect其余门。

sudo/sshd helper各最多一次且顺序执行；使用fixed clean env、cwd `/`、stdin `/dev/null`、no shell、并发
drain、per-stream+combined cap、5s wall/2 CPU-s、exit0/双EOF。overflow/timeout须SIGKILL+wait且不重试。
不得称其无副作用：plugin/NSS/atime/journal/audit incidental effect计入原carrier预算，结果只作第1治理
前提下的guest self-attestation。任何parser语法、Include/Match、symlink、alias、device、capacity、absence、
unlisted consumer或UNKNOWN停止。

guest current absence只能在marker后检查；测试必须拒绝“pre-marker已确认guest absence”的虚假状态。
marker后失败全部已消费、保留且无第二request。只有全PASS才允许第一项staging/install mutation或H01
intent。

session/admission raw member与remote-result作为output manifest的两个独立binding对象；保持remote-result
v1 shape。测试必须证明remote-result本身没有虚构九项digest，而output manifest/capture/receipt链仍可
交叉验证。

## 6. D5：原 core real effects、H01/Q4/H11

在新 admission门后补齐原 implementation review列出的current guest collector、protected staging/
install/native build、existing-account completion、H01、Q4、H11、dynamic phase facts、usage/peak与remote
failure finalization。真实candidate harness/system manager/quota evidence是field truth；fake只用于负例。

- H01：intent早于任何case object；plan早于owner/submit/start；held raw empty-ledger gate、完整fixture
  check与resident assertion三门独立；受监督业务真实执行、退出、tree/writer/collector/result/evidence
  closure全部满足才 semantic PASS。
- Q4：只有helper实际RUNNING才发恰一次cancel；停止、ledger/control/evidence闭合才PASS。
- H11：复用同一ledger dev/inode、request/execution/unit/grant与原deadline；只恢复observation/control；
  禁止submit/start、result reread、new grant/unit、deadline extension或业务evidence封装。

remote failure在通道仍可用时至多产生一个bounded `REMOTE_STOP_AND_RETAIN`；断线/硬杀可无frame，host
不得合成remote success。任一case非PASS不创建下一intent。

## 7. D6：finite finalizer

抽取单一双钟helper：验证marker deadline恰等origin+900s；每次按BOOTTIME-first/MONOTONIC-second采样，
分别与同名deadline比较，不跨clock排序；任一 `remaining<=0` 失败。

marker、stdout、stderr、remote-result、capture manifest v2、receipt、attestation的每个可能阻塞持久/
termination/resource-observation边界都在调用前后检查deadline。
receipt/attestation共用一个create-only writer，严格执行：

```text
O_EXCL open -> write-all -> file fsync -> fstat -> close
-> O_NOFOLLOW|O_NOATIME reopen (no fallback) -> identity/protection -> full reread -> stable fstat -> close
-> parent fsync -> parent-allocation phase sample -> post-return dual-clock sample
```

成功receipt只能写pending；失败receipt可按原deadline/reserve的逐步前后检查尝试写STOP，绝不创建
attestation。未创建且检查已禁止下一调用时保持absent；O_EXCL成功后失败、晚返或无法确认则保留
partial/full对象，不补写、覆盖、删除或重试。partial/invalid receipt无derived，strict-valid STOP只判STOP。
pending的post-parent-sample及时双钟进入
attestation。attestation每一步也必须在900秒内返回，且完整local finalizer仍受原15秒reserve；
最终post-parent-fsync/parent-allocation/resource sample及时且live resource总账闭合，才生成非持久
`verification_mode=LIVE/local_state=COMPLETE` result。LIVE mode只能由创建marker且连续持有原fd/namespace/
starttime/in-memory结果的原host进程内部决定，caller不能选择；受控carrier child不接管该资格。过期检查后不发持久化/终结syscall；已阻塞调用可
晚返并由post-return clock read判FAIL。不删除、不补写、不重试，没有5秒tail或stopper。
只有LIVE pending+VALID进入terminal clock/resource sampling；其它LIVE组合的terminal clock字段为null且
timing为UNPROVEN。

restart verifier只读pair、marker/capture/package/chain；只有strict-valid完整chain才生成derived，valid pair返回
`RECEIPT_COMPLETE_ATTESTED`、`attestation_completion_timing=UNPROVEN`和
`capture_resource.state=UNPROVEN_RESTART`。strict-valid pending-only标为UNATTESTED，strict-valid receipt配
INVALID attestation标为STOP；partial/old-v1/extra-key/identity-drift chain直接拒绝且不生成derived。绝不在
restart返回COMPLETE或从当前endpoint推历史closure。
task/result字段逐字复制receipt完整truth object。

成功inventory必须是七basename完整顺序；失败只允许该顺序的subsequence。remote-result缺失后仍可写
capture-manifest与及时STOP receipt，但不得写attestation；partial samples不生成complete aggregate。
五个非stream role在每次O_EXCL前用RAM中完整canonical bytes分别检查需求固定raw/base ceilings，未用额度
不可转移；receipt raw/base均≤1048576 B，五项base合计不得超过2392064 B。

capture测试覆盖unsupported/missing proof、qualification source非递归preimage、held parent mount-ID/
fstatfs/block-rdev与跨dev/UUID/superblock/options/source拼接、ext4 magic/4KiB/no-bigalloc、三项kernel raw
source的kind/path/identity/preimage、trusted loaded-module measurement缺失/伪造/与磁盘image不一致及
built-in拒绝、source-object archive locator/digest/minimality、commit→root-tree→path→blob机械关系、
manifest row raw SHA与independent review、
allocator/ACL/xattr/quota/LSM/model input drift、baseline 249/full 256 entries及O_NOATIME no-fallback。52 MiB
stream的所有split/4KiB tail、五role pre-create ceiling、成功full sequence/失败subsequence、七个parent
endpoint/nonmonotonic/concurrent drift、statx mask/attributes drift、initial raw superblock可变字段的允许变化、
static geometry/feature-mask漂移和zero/unreviewed mask拒绝、exact immutable projection、child metadata 2097152、
transient 4194304、parent 2097152、uncovered 1048576 B/7 inodes及actual `st_blocks*512`总账都要覆盖；
child peak固定59023358 B/7，conservative peak固定66363390 B/14，余745474 B/2且总上界仍67108864/16。

## 8. 必须通过的发行验证

定向测试至少覆盖：

1. 所有source archive/member SHA、两项current raw exact path/class/proof、24 snapshot+12 amendment row
   transform、前七行去重、0048 placement的4327/4549-byte vectors、system双parent同pool、snapshot role
   set/delta fixed selector、management row缺失或跨设备、36-row总数、46 configured-quota rows及其去重/absence、
   duplicate/conflict/unknown/release/horizon drift；
2. canonical JSON duplicate/float/NaN/BOM/newline/overflow，approved-input missing/extra/mode/origin，
   private member泄漏；
3. package/marker/session/capture-manifest v1/v2混淆、implementation identity、九digest preimage、writer
   real/effective/saved/filesystem ID与userns/pidns/process/anchor漂移、HELLO后refreeze、package/member/shared预算；
4. symlink hop/component/loop/magic/absolute/rename/O_NOATIME、单项/合计bytes、Python mismatch与HELLO
   4096/4112边界；失败只有一个request且无mutation；
5. sudo/sshd/authorized_keys/rc每个strict predicate、unsupported grammar/include/match、helper clean-env/
   cwd/stdin/no-shell/一次性/双EOF/per-stream+combined cap/timeout kill+reap、incidental-effect计费，以及
   self-observation不冒充pre-entry containment或host独立复算；
6. marker前仅local absence；marker后reconciliation/install/staging/case/root/project/unit existing/partial/
   race/UNKNOWN全部已消费停止；
7. historical snapshot按role distinct pool、new delta按唯一selector、46 quota hard-limit addend、alias、
   actual-free relation、inode ceiling与未知consumer；不采用旧run permission，不退款；
8. 原八项real effect、H01 empty ledger、Q4 running-only cancel、H11 same-ledger/no-restart/no-reread/
   no-new-grant/no-deadline-extension与exact member closure；
9. remote-result v1/session sibling binding、remaining+1 sentinel不入capture、SC_ARG_MAX marker前失败与
   marker后/request前drift、无第二carrier Popen/request或额外cancel；
10. BOOTTIME/MONOTONIC单独过期、恰等deadline、origin缺失/交换/刷新、每个finalizer syscall晚返；
    receipt不直接COMPLETE；
11. STOP/PENDING receipt×ABSENT/INVALID/VALID attestation完整状态表、truth object复制/nullability、receipt
    identity/hash漂移；STOP create前被截止则absent，create后失败或晚返保留partial/full且无attestation，
    partial/invalid或strict chain外不生成derived；final parent fsync/sample晚返；
    live timely+resource正例才COMPLETE，restart同一pair仅ATTESTED/UNPROVEN；
12. 52 MiB effective/60 MiB outer边界、fixed 4KiB profile/source/proof、七次parent endpoint、七对象全过程
    peak各分量、actual child allocated边界、single-writer/stable-kernel premise与可见漂移，以及restart不得从
    endpoint恢复历史closure；
13. production `E3_SUPERVISION_UNVERIFIED`保持，namespace/watchdog不进入package/import/execution，
    Windows skip不算Linux live PASS。

执行targeted与完整source suite，保留所有PASS/FAIL/SKIP；任一红项不得隐藏。独立reviewer逐项核对
source、test、candidate/artifact bytes、private build与package parse。只冻结审计通过的准确D/tree/
dispatcher/package digest；后续代码变化重新冻结。

## 9. 条件现场与最终报告

package release后再次只做local held prechecks；完整O_EXCL marker后发唯一carrier。guest live checks留在
同一carrier，随后条件执行H01→Q4→H11。每case后先闭合真实监督、退出、writers/collectors、ledger/
control和证据；前项非PASS立即停止。

最终报告必须列出准确R/A/B/C/D、candidate/wheel/harness/package、marker/request/case计数，并分别回答：

- H01真实任务是否受理并执行；
- 受监督树是否确认退出；
- 结果与证据是否真实收回；
- Q4取消与H11同账本恢复是否实际运行并PASS；
- persistent receipt/attestation pair是否成立；
- live local COMPLETE是否在900秒内的最终sample点形成（不夸大随后return时点），或restart为何只能
  ATTESTED/UNPROVEN；
- 所有retained blocker与production/namespace guard状态。

无现场执行写NO；断连/缺证写UNKNOWN。source test、fake harness、package freeze、pending receipt、restart
attested状态或批准文字均不能替代实测。
