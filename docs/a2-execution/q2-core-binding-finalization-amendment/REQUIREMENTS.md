# Local Hand 核心输入绑定与结果收回：最小修订需求

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING EXACT OWNER DECISION**。
- Scope：`LH-Q2-CORE-BINDING-FINALIZATION-AMENDMENT-v1`。
- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；来源、完整性、Owner-only
  决定权限、无例外和变更规则沿用根 [AGENTS.md](../../../AGENTS.md)。
- 本文与[架构](ARCHITECTURE.md)、[实施方案](IMPLEMENTATION_PLAN.md)组成准确三文档 A。
  没有本 scope 的准确 Owner B、独立 bookkeeping-only CLOSED C 或集成 D。

本修订直接服务于正常任务执行及结果收回、运行中取消、同一任务恢复查询。
撤回未批准 `4009e1b560dd873bc3d9b937be539f329b93371a` 的第七个 attestation 文件、
restart 验收扩展、宿主 loaded-ext4 测量、内核源码证明与完整文件系统分配模型。
保留其已纠正的 approved-input 来源、sudo 语义、package/HELLO JIT 绑定。
本文 §3 从该版本逐字保留；其余章节由本版替代，不能混用旧 proposal 的字段或前置条件。

**资源保证发生一项显式变化，必须由 Owner 接受：**本机 capture 改为应用写入硬限额、
固定六个自有文件，以及每次 write/fsync 后实际文件分配量的观测验收上限。
64 MiB / 16 inode 保留为这些对象的逻辑总上限和观测验收限额；不再承诺共享宿主文件系统
包含目录、journal、元数据或未观测瞬时分配在内的全过程物理硬上限。
逻辑写入限额和 `st_blocks*512` 观测分别报告，不能互相替代或写成原物理保证已证明。
guest 的 physical/admission/quota/CPU/memory/pid 上界以及全部身份、安全与结果真实性校验不变。

## 1. 已知事实与工作边界

原核心 scope `LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1` 的准确 A 为
`74366b3fe41e675b1aa2d677228714a5606c275c`，Owner B event 为
`LH-Q2-CORE-ACCEPTANCE-DELIVERY-CLOSURE-20261003-01`，独立 C 为
`a8dd077392ebb656770c8f94ca3b051e93fc296d`；部分 D 为
`520f77f578b90d31870517e33e29bee42918f3c0`。原 A/B/C 不改写，部分 D 仍不可 release。

1. 原 package 在唯一 request 前要求 current guest 实体预像，同时只允许在该 request 内观察
   guest，存在时序冲突。本修订用静态 remote expectation 与唯一 carrier 内 JIT HELLO 分开绑定。
2. approved-input 三组关系缺乏完整 source-horizon、schema 和 preimage；§3 保留准确来源与计费，
   不漏计历史 commitment、不退款、不以历史记录充当当前 guest 状态。
3. 原 A 已允许调用端观察 receipt 的 fsync/回读完成，不要求 receipt 自证未来步骤；因此恢复原六文件
   和 live caller 终结，不另建 attestation/restart 证明链。H11 的 guest 同任务恢复继续属于核心目标。
4. [本地既有材料回传](../Q2_CORE_LOCAL_HANDOFF_RESULT_20261004.md)在提交
   `c83dad17040e9f8cec148303083c47311f8b7fb9` 确认：准确 capture anchor 是历史 4 KiB 的
   control parent，不是另一个 12 KiB 的 host parent；与 VM 镜像共享 ext4，未找到专属硬限额记录。
   这是保存时点的事实，当前权限、mount 或 quota 仍不能据此认定通过，也不能推断机制必定不存在。
   不重复索取 K4/R3，不读 VM 内容，不迁移目录、不新建存储或开启内核证明支线。

本次尚未签发的核心批次 package 为 null / NOT_ISSUED，marker、carrier、H01/Q4/H11、真实任务、
退出确认和结果收回均未发生。既往其它批次的现场事实不被清零，也不因此可重放。
云端源代码测试和 CI 成功不等于这些真实效果已实现或现场通过。

## 2. 需明确接受的治理前提与失败边界

除原 A 已披露的 broad-sudo 前提外，Owner B 须明确接受下列三项前提及上面的 capture 保证变化：

1. **唯一 carrier 内的 JIT 自观察。** bootstrap 进入后、读取 package 前，按 §4 固定 alias 和有限
   symlink 算法产生 current account/program HELLO；dispatcher 验证 package 后、首个 guest
   mutation/H01 intent 前，按 §3 各至多一次调用 `sudo -n -ll -U q1admin` 与 `sshd -T` helper。
   两者不是第二 SSH、carrier、systemd-run、unit 或 request；不有意修改配置或业务对象。
   loader/shared-library/plugin/NSS/atime/journal/audit 等 incidental effect 仍计入原 carrier
   CPU/memory/pid/audit 边界。这些观察不能追溯证明已发生的 SSH/sudo entry inode、loaded image、
   daemon/config/dependency，也不能排除 alias race、change-and-revert 或 TOCTOU。
   host 只验证固定 D 的有界 self-attestation 与摘要链，不声称拥有 guest private raw 的独立复算。
2. **source-horizon 完整性。** §3 的 `20260927` source、五个 normal batch、`20261001e` 与
   三项 later-nonissuance 是 B 时已批准或消费的 Q2 guest obligation/field batch 完整集；本批次
   终结前不再签发其它 Q2 batch。它是治理责任，文件系统扫描无法独立证明。发现相反决定、记录
   或 current object，marker 前 NOT_ISSUED，marker 后 STOP_AND_RETAIN。
3. **本机可信单写者窗口。** 从 origin 前最后 offline gate 至 live final sample，没有同 filesystem
   credential 或等价 DAC 能力的其它 writer 改动 held anchor 身份/权限及本 scope 六个 basename。
   writer credentials、namespace、name-to-inode 和 held fd 检查只能发现可见漂移，不能排除不可回溯的
   change-and-revert。已知竞争者或漂移须停止；此信任不授予 host sudo、杀进程、系统变更或锁服务。
   不再要求 kernel、allocator 或全宿主 metadata 模型固定来推导一个本版并不承诺的物理峰值。

原 scope 的准入、UID/GID/PID、文件身份、摘要、凭据、安全 policy、单次消费、失败保留规则均保留。
任何 UNKNOWN 不提升为 PASS。900 秒总窗口、15 秒 local-final reserve 均不延长。
原调用进程在 receipt file/parent fsync、同 inode 回读及最终资源检查返回后，双钟采样仍严格早于
原 deadline 才可接受 COMPLETE。晚返只能失败；磁盘上的 receipt 本身不证明最后步骤或其及时性。
不实现 local restart COMPLETE；H11 对其自己 origin 的同 ledger/request/execution 恢复不受此删减。

## 3. canonical approved-input bundle

marker 前必须从固定 private retained sources 构造唯一 canonical
`local-hand-q2-core-approved-inputs/v1` JSON，作为 field package 中唯一
`private/approved-inputs.json` member。raw bytes≤1048576、mode `0600`、role `approved-inputs`；
它计入原 package/shared delivery pool，不增加预算。该 member 只供 root bootstrap/admission 在 RAM
中严格解析；不得进入 ordinary projection、runtime `sys.path`、candidate installation、remote output
或公开 evidence。失败后只可随原 root-only protected package/staging 按保留规则留存。

所有本修订 JSON 统一采用：UTF-8/ASCII-compatible object、拒绝 BOM/duplicate key/float/NaN/Infinity、
integer 为有符号 63-bit；bytes/count/time/identity/mode等字段按各自合同另要求非负，明确的process
wait/exit status可为负。编码固定`sort_keys=True,separators=(",",":"),ensure_ascii=True`。完整文件恰加一个
LF；nested digest 的 preimage 不加 LF。数组保持本文规定的 source/order，不做集合重排。

artifact 顶层 key 恰为：

```text
schema,scope,amendment,source_relation,policy_basis,
historical_capacity_obligations,retained_preparation,reconciliation
```

`scope=LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1`。`amendment` 恰含
`baseline,owner_decision,closure,implementation`；它们的 shape 与原 core chain 同型：`baseline`
恰含 `commit,tree,documents_sha256`（后者以三个 authoritative document repo path 为 exact key）；
`owner_decision` 恰含 `event,record_path,record_sha256`；`closure` 和 `implementation` 各恰含
`commit,tree`。所有 commit/tree 为完整 40-hex，SHA-256 为 64-hex，record/document path 为 repo-relative
ASCII path。这些字段只能在准确 A/B/C/D 已存在后填入；任一 placeholder 均拒绝。

### 3.1 source relation

`source_relation` 顶层 key 恰为 `schema,locator,obligations,later_nonissuance,zero_mismatch`；
`schema=local-hand-q2-core-approved-source-relation/v1`，`zero_mismatch=true`。

`locator` 恰含 `schema,historical_only,carriers,members,mappings,zero_mismatch`；其中
`schema=local-hand-q2-core-locator-source-relation/v1`，`historical_only=true` 只修饰 locator relation，
不能修饰 obligation adoption，`zero_mismatch=true`。`carriers` 为按下表顺序的
四项，每项 exact key 为 `role,bytes,sha256`；`members` 为随后两项，每项 exact key 为
`role,carrier_role,path,bytes,sha256`：

| role / source | bytes | SHA-256 |
| --- | ---: | --- |
| `collection_capture` / `collection-capture.json` | 1835 | `56c29ed9ffe2cf79235baca6b000afaec9ae84b51b2356c664e44d6b34a4fb18` |
| `guest_raw` / `guest-raw.tar.gz` | 20164157 | `078b4a5bc198caa42760c31d2a4f8d0be1dd3564090ea316c799bfe6d9e653f7` |
| `guest_manifest` / `guest-manifest.json` | 3419814 | `82c8c13e250ac0be0957b766e84827514dd50cc5cc53d461c126d6dd0523f735` |
| `guest_inventory` / `guest-inventory.jsonl` | 922584 | `0b1f337f219d3b8d06f2d2a22fc30d2d034afef40decfa7db26051c0ea009a62` |
| `original_plan` / `root/q2-transfer-20260926a/plan.json` | 9814 | `efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c` |
| `retry_preparation` / `root/q2-retry-setup-20260927a/retry-preparation.json` | 61119 | `586f0fd79ceb869a8e1ed238d925b6cdbf2cceaddf233687df81ea320bded4fb` |

`original_plan` 和 `retry_preparation` 两个 member 的 `carrier_role` 都固定为 `guest_raw`。

`mappings` 每项 exact key 为 `role,source_role,pointer,transform`，按以下顺序且不得增删：

```text
state_parent                  original_plan /directories/state/path dirname
quota_parent                  original_plan /mounts/quota/path identity
install_parent                original_plan /candidate/destination dirname
journal_parent                original_plan /mounts/journal/path identity
evidence_parent               original_plan /mounts/evidence/path identity
ordinary_user                 original_plan /account/name identity
ordinary_group                original_plan /account/name identity
user_manager_unit             retry_preparation /facts/parents/manager/unit identity
query_parent_unit             original_plan /parents/query/unit identity
controller_parent_unit        original_plan /parents/controller/unit identity
management_parent_unit        original_plan /parents/management/unit identity
supervisor_parent_unit        original_plan /parents/supervisor/unit identity
ordinary_parent_unit          original_plan /parents/ordinary/unit identity
retained_ordinary_parent_path retry_preparation /facts/parents/ordinary/path identity
retained_paths                original_plan /retained source_order_identity_array
retained_domains              original_plan /retained_domains source_order_identity_array
```

`obligations` 恰含
`schema,legacy_20260927,horizon_20261001e,producer,configured_quota_liability,placement,row_relation,source_horizon,
snapshot_rows_sha256,delta_rows_sha256,effective_rows_sha256,source_union_sha256,
run_permission_adopted,zero_mismatch`。
`schema=local-hand-q2-core-approved-obligation-sources/v1`。

- `legacy_20260927` 恰含 `chain,archive,manifest,inventory,producer_blobs,adoption`。
  `chain` exact key为 `baseline,closure,implementation,tree`；`archive` 为
  `basename,bytes,sha256`；`manifest` 为 `bytes,sha256`；`inventory` 为
  `unique_blobs,blob_bytes,reservation_inputs,trees,old_pins,typed_sources,forward_entries,
  reconciliation_rows`；`producer_blobs` 为
  `startup_retry,reconciliation_sources,reconciliation_billing`；`adoption` 为
  `current_owner_supplied_raw,forward_baseline_entries,disclosed_atime_changes,
  run_permission_adopted,released_bytes,released_inodes`。
  `chain` 固定 A `c65ff4e25ea6373aabf8db25d304ee7614b96eb5`、C
  `1491765c64c60a63d6bddf10a049308e404885ca`、D
  `8fd84521cdd25b455ff148e0c0fed6b5d8e39fe1`、tree
  `5fb64e578d06e2954c1eedbc1b15e00069dc32a4`；`archive.basename`固定
  `q2-history-readonly-return-20260927T151622+0800.tar.gz`，并固定 38014204 B / SHA-256
  `869a859fcbe7a952d11e22db6f6534c9b9a3025cec27471fe3e2a054a6a96018`；`manifest` 固定
  34010 B / SHA-256 `f705d3c77885887c7b6f799f4721dfefd0e9c588dbd11085cc8456fe623c6d40`；
  `inventory` 恰记录 48 unique blobs/5686734 B、10 reservation inputs、12 trees、15 old pins、
  47 typed sources、610 forward entries、7 source-ordered rows。`producer_blobs` 固定
  `q2_startup_retry.py=8057e5c34c228b456a7ebbb1a1c06c631e499328`、
  `q2_reconciliation_sources.py=b5f904ee7053836be5f57d5e72574fa86f73d97a`、
  `q2_reconciliation_billing.py=46f753e39f0185698f105dbf5b2a48941c2cfa42`。
  `adoption.current_owner_supplied_raw` 是 source-order 两项，每项 exact key
  `id,path,bytes,sha256,source_class,proof_id`：`source_class`均固定
  `CURRENT_OWNER_SUPPLIED_RAW`、`proof_id`均固定`owner-adoption`。`path`不得由调用者提供：
  `second-bootstrap-intent`机械取已验证previous candidate source parent的同级`.intent.json`，
  `second-bootstrap-attestation`机械取同一parent下`bootstrap-attestation.json`；两者还必须逐字段等于
  已验证reconciliation source manifest中的exact path。其余值为`second-bootstrap-intent` / 556 /
  `58992ee2ff0d66fec5e10c7e138e8de4529089ca35d76f71200db1a05ac160b6`，
  `second-bootstrap-attestation` / 7766 /
  `cfc6c07265b4edc6d0b26e67a6ca9cfc19c652b4d011a2386b9bd95e945a34cb`。`adoption` 另准确保留
  610 baseline 与五项 disclosed atime，
  但 `run_permission_adopted=false`、release/refund 为零；不得继承旧
  `run_permission=existing_startup_once`。
- `horizon_20261001e` 恰含 `archives,source_members,snapshot,predecessor`。`archives` item exact key为
  `batch,basename,bytes,sha256`；`source_members` item exact key为
  `batch,role,path,bytes,sha256`；`snapshot` exact key为
  `path,bytes,sha256,rows,rows_bytes,rows_sha256,total_bytes,total_inodes`；`predecessor` exact key为
  `baseline,event,closure,implementation,candidate,corrected_package,evidence_package`，其中两个 package
  object都恰含 `basename,bytes,sha256`。`archives` 按
  `20260930b,20261001a,20261001b,20261001c,20261001d,20261001e` 排序，逐项 exact key
  `batch,basename,bytes,sha256`，绑定 retained private evidence archive；`source_members` 对前五批
  固定每批 plan/observed，另对 `20261001c/d` 固定 code intent/installation receipt，对
  `20261001e` 固定 installation、client intent/result、consumed、staged、code intent/complete、plan、
  original budget、historical snapshot、preflight、failure 的 member path/bytes/SHA。

  `archives` 的逐字节值固定为：

  | batch | basename | bytes | SHA-256 |
  | --- | --- | ---: | --- |
  | `20260930b` | `local-hand-normal-5ca9753-run-20260930b-evidence.zip` | 289401 | `eeef31dc11bb277caec267cd11590654cb2e6d036485f941607dce0dc9af0ac1` |
  | `20261001a` | `local-hand-normal-5ca9753-run-20261001a-evidence.zip` | 297168 | `d9e26cdbdd393a83cd83e396e560cbd1ea6b01f84dab10e58d0e1974c00f181d` |
  | `20261001b` | `local-hand-normal-5ca9753-run-20261001b-evidence.zip` | 308465 | `ae969b050c6d20761af05b0b87c0be0e8c45d059fcd851db0c24f0b605736f43` |
  | `20261001c` | `local-hand-normal-b37935d-run-20261001c-evidence.zip` | 349790 | `2013877a266b87509579ea6b05e539cfb562fbbb2e11275c8a80100cb1ad0264` |
  | `20261001d` | `local-hand-normal-7780364-run-20261001d-evidence.zip` | 356297 | `6707359a14565747a673db4862d435d56e4967fc50aded26e3ac1ec93e90dd5c` |
  | `20261001e` | `local-hand-system-manager-1a900e4-run-20261002-evidence.zip` | 129584 | `f352d1d8bc70d3d4c419c21de493efca2c51a3453dc90d04fba3ec654e7e33b6` |

  前五批的 source member pins 固定为：

  | batch / role | bytes | SHA-256 |
  | --- | ---: | --- |
  | `20260930b/plan` | 13383 | `6836678f2c2a5bc320bb18f40344cd83e162e53801f08140e78d87c75f3e1363` |
  | `20260930b/observed` | 59349 | `1458436d63130589b42cea02d438c92c5d151f041e49d76be074fe1d5daa159e` |
  | `20261001a/plan` | 15072 | `50f1c8c157d0515f4dd27337c474d2345e010f63271e3866b1d32d96bca0c8f5` |
  | `20261001a/observed` | 62307 | `afaf940b1a0671c152d951e0a8ba2ee670333aef8561e76337b558ca1b8dab18` |
  | `20261001b/plan` | 16838 | `998dc901303967660c5bcc19768d03002a00eb594f260cdbbf598fc3acefdd89` |
  | `20261001b/observed` | 65268 | `c2dd6ab190a8e96fd98ea93a0b1f5fb88120f6d482137500e8491db07383df6c` |
  | `20261001c/plan` | 18595 | `7144977af9f3ff874f4e41317420a01b40fa601c9c420e288c9c1fab2f55b9a5` |
  | `20261001c/observed` | 68505 | `7f62ccabf4063d292b443c034bfb3c4fbd4d0fdb14b633e6003986ae6a0ae14b` |
  | `20261001c/code-intent` | 519 | `2ae23f8d219b265fdb98c8e54d678ca540499b9e1390897b9f8a26ae08b11fd1` |
  | `20261001c/installation` | 45338 | `56cd30fe64c26923a0bf4aab10f4dab6f8c7793883fa83f056c50d23246a4893` |
  | `20261001d/plan` | 20429 | `35aa2fb4fc0f5fc5ea00f1e895fbee330d1fe2825f46cb7f3ca0ddfbda0f85e8` |
  | `20261001d/observed` | 72163 | `b15625827d845ab7d54e8fef42c63a8bc85ce18d5c3ee3289a178d536cd80e88` |
  | `20261001d/code-intent` | 519 | `30e68dd477eaafac70c1142dc567a70c028eaaf05b1696008745e4e731b3bfbd` |
  | `20261001d/installation` | 45338 | `df92885a74f4df2b14e06aa4420c2fb876fe987e3d35a722574a37718549f853` |

  前五批全局 source-order 恰为：每批 `plan`、`observed`，然后仅 `20261001c/d` 各紧接
  `code-intent`、`installation`。normal member path机械固定为
  `root/q2-normal-setup-<batch>/resume-plan.json` 与同目录 `observed.json`；code member分别固定为
  `opt/local-hand-resume-5ca9753-<batch>/prepare-log/0006-code-update-intent.json` 和
  `opt/local-hand-code-<batch>/installation.json`。不得按basename搜索替代。

  `20261001e` 的十二个 source member pins 按上文 role 顺序固定为：

  | role | exact archive member path | bytes | SHA-256 |
  | --- | --- | ---: | --- |
  | `installation` | `guest/opt/local-hand-code-20261001e/installation.json` | 47699 | `1bc8d61538d0c48f604e3bf2fb7002b481bb62e7f0c3c7ffc433c0818ef5b1f5` |
  | `client-intent` | `guest/opt/local-hand-resume-5ca9753-20261001e/client-log/intent.json` | 1402 | `ab57768eb5efe19015c4dcc4e2d4f79db7901684b932c91f65444d2cbd2e1377` |
  | `client-result` | `guest/opt/local-hand-resume-5ca9753-20261001e/client-log/result.json` | 305 | `ef898352c22ffc601f2617327918a0f0baa45d45def99e487bde45e41e1878cd` |
  | `consumed` | `guest/opt/local-hand-resume-5ca9753-20261001e/consumed.json` | 331 | `ba29f6c3dcfab18708f1d67de58a5bb8bff1918b4d01c3fd49b67ee1c70156ee` |
  | `staged` | `guest/opt/local-hand-resume-5ca9753-20261001e/staged.json` | 523 | `63fd8aa4b3f8cc406b47b94109d547d4ecdc85d147034e45b068e65e222a08ae` |
  | `code-intent` | `guest/opt/local-hand-resume-5ca9753-20261001e/prepare-log/0006-code-update-intent.json` | 895 | `c4e45fc7fa217722fe57f7576d85c72181ad93a9cdf422e0a3919b77a1493a48` |
  | `code-complete` | `guest/opt/local-hand-resume-5ca9753-20261001e/prepare-log/0019-code-update-complete.json` | 326 | `896066511a5a5656073aa858a6e4c0c23e2b1550faef38597ee7e0603854c97e` |
  | `plan` | `guest/opt/local-hand-resume-5ca9753-20261001e/prepare-log/0023-plan.json` | 30813 | `85633b837718282ba6590b7a6679d51aa60addfb0f5be39ea929af83de4a45c1` |
  | `original-budget` | `guest/opt/local-hand-resume-5ca9753-20261001e/prepare-log/0046-original-budget-bounds.json` | 619 | `6e19304516853a0b3c4d89deb4a4011e9a3ea72d287904ef7dfd5b484ff97621` |
  | `historical-snapshot` | `guest/opt/local-hand-resume-5ca9753-20261001e/prepare-log/0047-historical-issued-obligations.json` | 21086 | `9e0bfb17a58c8fec064601ef675e391a8ef358269b775daca60f7ea47150cb8e` |
  | `preflight` | `guest/opt/local-hand-resume-5ca9753-20261001e/prepare-log/0048-resource-preflight.json` | 94533 | `eabe18b207e68967e65b9dc9d114466aad7284063cff6e90814938a0ae9fb086` |
  | `failure` | `guest/opt/local-hand-resume-5ca9753-20261001e/prepare-log/0053-failure.json` | 943 | `79ccccf1745bcad29089c381e692ca777c7fc2165cd31cc1f54ed825db545b85` |

  上表就是十二项全局顺序；不得接受同字节的 `0022-resume-plan.json.json`、
  `0049-preflight.json`、
  重复 member、alternate prefix 或 basename-only lookup。

  `snapshot.path` 固定
  `guest/opt/local-hand-resume-5ca9753-20261001e/prepare-log/0047-historical-issued-obligations.json`；
  raw member 固定 21086 B / SHA-256
  `9e0bfb17a58c8fec064601ef675e391a8ef358269b775daca60f7ea47150cb8e`；其 24-row array canonical
  恰为 11433 B / SHA-256
  `82bdb7a94c85a7450a45d9ee7dff2baa4e5fef7b8a7a7d8f7787a0cb7bea358e`，`rows=24`，合计
  626790400 B/32113 inodes。前七行 canonical SHA-256
  `09f107f265986afd0dcc0535de84d2df37ac47ddeff78d20569c2bb8a5513e88`、
  340529152 B/13681；后十七行 SHA-256
  `60885e762f1dfe007f43b6ae1e056dabdce9b1e142688741d333f806f6952a68`、
  286261248 B/18432。前七行必须与 `legacy_20260927` 的七行逐字段同序相等，不能再相加。
  `predecessor` 固定系统管理器 A `ae50aea2639c32021794ecb70730f4b9e781c8d6`、B event
  `LH-Q2-SYSTEM-MANAGER-REPAIR-CLOSURE-20261001-01`、C
  `23702d6e55396d7941389817ab875a4610d3e142`、D
  `6470592cc29efb45b8f38172b8e69a48fcfeab2a`、candidate
  `1a900e4a38e9567655f21cbf3c3f17941de1a8d5`、corrected ZIP basename
  `local-hand-system-manager-1a900e4-20261001e-corrected.zip` / 3887651 B / SHA-256
  `5805dcd2a45f150f0e5b7062a17b46137d53e889e1ea160601d7c75fb529e886`、evidence ZIP
  basename `local-hand-system-manager-1a900e4-run-20261002-evidence.zip` / 129584 B / SHA-256
  `f352d1d8bc70d3d4c419c21de493efca2c51a3453dc90d04fba3ec654e7e33b6`。D 必须取得并校验这一
  `f352…e33b6` carrier；只有部分 member 相同的其它 ZIP 不等价。
- `producer` exact key为
  `adoption_baseline,adoption_closure,adoption_implementation,commit,tree,path,blob,file_sha256,
  categories,device_selectors`；`categories` 固定为下述12项有序数组，`device_selectors` 以12个category
  为exact key。它固定 old-producer adoption A `68424df2ddbf812b9479ffa7a64dcaa59a2a9f76`、C
  `179652cb9487163d83c004d358e4d4b49409694c`、D
  `4b71824a4660723d064969cbf0c39cd4325dd62a`，以及 accounting producer commit
  `661e96772c64433d1cd0eebf122e165781d8c11c`、tree
  `2e977e9887f9e6e1a97b86082d1664772c0f7e3b`、path
  `tests/e3_host/q2_old_producer_admission_retry_accounting.py`、blob
  `659df7ee2bab92413fa41d348c17219e4d9de0c7`、file SHA-256
  `f2f4b57b4a34bbfabe483b20865275246cdf35d3497a1c24b375deb7a508ae1b`。
  pinned producer **不生成**下述 enriched rows；它只以 `FULL_BUDGETS` 和 `_commitments()`
  验证 caller projection 的 category/amount/status/completeness。本 amendment 另行定义确定 transform和
  12 条 row，再在 live selector 解析后投影为 producer 的
  `reservation_id,batch,category,device,allocated_bytes,inodes,status` shape 复核；不得把新字段冒充为
  producer 历史输出。`categories` 每项 exact key为 `category,commitment`，`commitment` 恰含
  `bytes,inodes`；12 项 canonical 为 875 B / SHA-256
  `895a58811735dd97b5d06ee0c6101be0b8a5e03cf86575f31a28ad189e3ad8b2`。`device_selectors`
  canonical 为 372 B / SHA-256
  `48bfde21c0abfb0288424a5221054a9e53f4ad28b2e55684998170958b2c87f3`；完整 `producer`
  canonical 为 1778 B / SHA-256
  `851583a3a5268cb43fcd50990b2ef297f45fa7fe6e3ad679e9ea5af8ed978ab1`。

  12 条 delta row 每项 exact key恰为
  `reservation_id,batch,category,covered_paths,evidence,commitment,device_selector,status,
  actual_allocation_already_excluded_from_free`，`batch=20261001e`、`status=UNRELEASED`、
  `actual_allocation_already_excluded_from_free=true`。以下符号只是文档缩写，builder 必须展开
  成完整 string array：

  ```text
  E = [/opt/local-hand-resume-5ca9753-20261001e/consumed.json,
       /opt/local-hand-resume-5ca9753-20261001e/prepare-log/0023-plan.json,
       /opt/local-hand-resume-5ca9753-20261001e/prepare-log/0053-failure.json]
  EC = [/opt/local-hand-code-20261001e/installation.json,
        /opt/local-hand-resume-5ca9753-20261001e/consumed.json,
        /opt/local-hand-resume-5ca9753-20261001e/prepare-log/0006-code-update-intent.json,
        /opt/local-hand-resume-5ca9753-20261001e/prepare-log/0053-failure.json]
  EM = [/opt/local-hand-resume-5ca9753-20261001e/client-log/intent.json,
        /opt/local-hand-resume-5ca9753-20261001e/consumed.json,
        /opt/local-hand-resume-5ca9753-20261001e/prepare-log/0023-plan.json,
        /opt/local-hand-resume-5ca9753-20261001e/prepare-log/0053-failure.json]
  ```

  | reservation_id / category | covered_paths（source order） | evidence | commitment bytes/inodes | selector |
  | --- | --- | --- | ---: | --- |
  | `20261001e:code_pool` / `code_pool` | `/opt/local-hand-code-20261001e` | `EC` | 67108864 / 4096 | `install_parent` |
  | `20261001e:management` / `management` | `/opt/local-hand-resume-5ca9753-20261001e`; `/root/q2-normal-setup-20261001e`; `/var/lib/local-hand-q2-normal-declarations-20261001e` | `EM` | 33554432 / 1024 | `state_parent` |
  | `20261001e:state` / `state` | `/var/lib/local-hand-q2-normal-state-20261001e`; `/var/lib/local-hand-q2-normal-authority-20261001e`; `/var/lib/local-hand-q2-normal-session-20261001e`; `/var/lib/local-hand-q2-normal-control-20261001e` | `E` | 8388608 / 1536 | `state_parent` |
  | `20261001e:journal` / `journal` | `/srv/local-hand-q1/journal/q2-normal-20261001e` | `E` | 1048576 / 128 | `journal_parent` |
  | `20261001e:capture` / `capture` | `/srv/local-hand-q1/evidence/q2-normal-capture-20261001e` | `E` | 20971520 / 384 | `evidence_parent` |
  | `20261001e:quota.work-a` / `quota.work-a` | `/srv/local-hand-q1/quota/q2-work-20261001e/slot-a` | `E` | 1048576 / 128 | `quota_parent` |
  | `20261001e:quota.evidence-a` / `quota.evidence-a` | `/srv/local-hand-q1/quota/q2-evidence-20261001e/slot-a` | `E` | 1048576 / 128 | `quota_parent` |
  | `20261001e:quota.temporary-a` / `quota.temporary-a` | `/srv/local-hand-q1/quota/q2-temporary-20261001e/slot-a` | `E` | 1048576 / 128 | `quota_parent` |
  | `20261001e:quota.work-b` / `quota.work-b` | `/srv/local-hand-q1/quota/q2-work-20261001e/slot-b` | `E` | 1048576 / 128 | `quota_parent` |
  | `20261001e:quota.evidence-b` / `quota.evidence-b` | `/srv/local-hand-q1/quota/q2-evidence-20261001e/slot-b` | `E` | 1048576 / 128 | `quota_parent` |
  | `20261001e:quota.temporary-b` / `quota.temporary-b` | `/srv/local-hand-q1/quota/q2-temporary-20261001e/slot-b` | `E` | 1048576 / 128 | `quota_parent` |
  | `20261001e:quota.retained_store` / `quota.retained_store` | `/srv/local-hand-q1/quota/q2-store-parent-20261001e/store` | `E` | 1048576 / 128 | `quota_parent` |

  该 array canonical 恰为 6678 B / SHA-256
  `b8af1d3264b77b9142a48288482c26d2eafa894523f85baa0fc71d595da90352`，总计
  **138412032 B/8064 inodes**。原 producer 没有 device mapping；上表是本 amendment 新采纳的
  **single-pool placement**，不是旧 `0048` multi-device accounting 事实，也不宣称比旧 physical bill
  更保守。每行所有 covered path 必须 live 映射到 selector 的同一 `(dev,fs_uuid)`，否则停止；
  不拆分、不选更有利设备。actual 已在 current free 中，不第三次加收，也不减去完整
  future commitment。
- `configured_quota_liability` exact key 为
  `schema,source_member,project_ids,rows_sha256,total_bytes,total_inodes,relation,zero_mismatch`，
  `schema=local-hand-q2-core-configured-quota-liability/v1`。`source_member` exact key为
  `batch,role,path,bytes,sha256,pointer`，前五项逐字段等于上述固定`20261001e/preflight` source-member
  record，`pointer=/capacity_observed/quota_inventory`。以 source array order 只取
  `hard>0`，把每项唯一转换为 exact-key
  `{project_id,hard_bytes,inode_hard_limit}`，值分别为 `project,hard*1024,ihard`；重复
  `(plan.mounts.quota.uuid,project_id)`、非整数或乘法溢出即停止。`project_ids` 恰为升序
  `10001..10004,11001..11007,12001..12007,12011..12017,12021..12027,12031..12037,12041..12047`；
  共46项。前四项值依次为 `10001:(67108864,4096)`、`10002:(67108864,4096)`、
  `10003:(4194304,128)`、`10004:(67108864,4096)`；其余 42 项都为
  `(1048576,128)`。canonical rows 恰为 2997 B / SHA-256
  `95b59d878d643bfbce2eef6ce88145bf1086058694dee127b3de49d13319bde0`，合计
  **249561088 B/17792 inodes**，`zero_mismatch=true`。`relation`
  固定 `UNMATCHED_CONFIGURED_HARD_LIMITS_ADDED_ONCE`：它们不是 snapshot 24 行中的独立
  quota rows，必须按 live `(fs_uuid,project_id)` 另加一次；不与 normal state row、current usage 或
  `retained_preparation.domains` 重复。delta `12051..12057` 只由上述七行加一次，live 必须证明
  它们 absent/unconfigured；任一 alias、limit/path/device 漂移、重复匹配或 UNKNOWN 都停止。
- `placement` exact key为
  `schema,source_member,source_rows,source_rows_bytes,source_rows_sha256,normalized_rows_bytes,
  normalized_rows_sha256,snapshot_profile,delta_profile,split_allowed,zero_mismatch`；schema固定
  `local-hand-q2-core-obligation-placement/v1`。`source_member` exact key为
  `batch,role,path,bytes,sha256,pointer`，前五项逐字段等于上述固定`20261001e/preflight` source-member
  record，`pointer=/capacity_observed/historical_physical_charges`；其24项每项exact key为
  `id,category,devices,full_commitment,no_refund`，canonical no-LF恰为4327 B / SHA-256
  `edcb0bb95508c15e5b3fb60d679c46c93961e95d8e802a338fc1f4397c18ee0d`。builder必须逐index证明
  `id/category/full_commitment/no_refund`分别等于24-row snapshot的`id/category/commitment/true`；再以
  同一固定0023 plan的mount device把历史device唯一规范化为`system,quota,journal,evidence` role，拒绝
  alias、缺role或其它device。normalized item exact key为
  `id,category,pool_roles,full_commitment,no_refund`，source-order array恰为4549 B / SHA-256
  `b6153d8c45e5b009bcc1f878406565e08bcf7c7d07c17f18361b562bf1096703`。
  `snapshot_profile=PINNED_ROLE_POOLS_FULL_COMMITMENT_PER_DISTINCT_LIVE_POOL`：live时每个role必须由held
  parent解析到唯一current `(dev,fs_uuid)`：`system`同时由`state_parent`与`install_parent`解析且二者必须
  得到同一pool，`quota/journal/evidence`分别只由同名parent解析；并与该row全部`covered_paths`的
  distinct pool集合逐项相等；
  对每个snapshot row，在该row的每个distinct live pool恰加一次该row完整commitment；仅同一row内多个
  role/covered path命中同一pool时去重，不同row/category始终逐行相加（只有source relation完全相同的
  同一义务才按下文规则去重）。不split、不择优。
  `delta_profile=FIXED_SINGLE_SELECTOR_POOL_FULL_COMMITMENT`，12行各以fixed selector得到恰一个pool且
  全部covered path必须在该pool。`split_allowed=false,zero_mismatch=true`。
- `row_relation` exact key为
  `reconciliation_prefix_count,reconciliation_prefix_sha256,snapshot_count,snapshot_sha256,
  snapshot_tail_count,snapshot_tail_sha256,delta_count,effective_count,effective_construction,prefix_equal`；
  值依次为 7、`09f107f...3e88`、24、`82bdb7a9...a358e`、17、`60885e76...2a68`、12、36、
  `SNAPSHOT_24_PLUS_DELTA_12`、true。完整 canonical object 为 462 B / SHA-256
  `89dea12770f6c6ab19b901adcf4c4d42e6b8b42300c1ca470b1ec7ac03ec47e6`；实现仍须保存完整64位摘要，
  文中的省略显示不得进入 artifact。
- `source_horizon=20261001e`；`run_permission_adopted=false`；`zero_mismatch=true`。
  `source_union_sha256` 的唯一 preimage 是 canonical no-LF object
  `{"schema":"local-hand-q2-core-source-union/v1","locator":source_relation.locator,
  "legacy_20260927":obligations.legacy_20260927,"horizon_20261001e":obligations.horizon_20261001e,
  "producer":obligations.producer,"configured_quota_liability":obligations.configured_quota_liability,
  "placement":obligations.placement,"later_nonissuance":source_relation.later_nonissuance}`，不含摘要自身。
  `snapshot_rows_sha256` 摘要上述 24 rows；`delta_rows_sha256` 固定
  `b8af1d3264b77b9142a48288482c26d2eafa894523f85baa0fc71d595da90352`；
  `effective_rows` 恰为 `snapshot_rows + delta_rows`，canonical 18110 B，`effective_rows_sha256`
  固定 `7c2786f240144e7a2de90bc9a70561089a7334559bd8e962371132cf1db806e9`。36 行逻辑总计
  必须为 **765202432 B/40177 inodes**；它不包含上述 unmatched configured-quota addend。admission 必须按
  source path/current `(dev,fs_uuid)` 分池，不能以总和替代逐设备账单。duplicate ID 只有 row bytes 与
  source relation 完全相同才可去重；冲突/重叠/UNKNOWN 立即停止。

`later_nonissuance` 是按 `20261002a,namespace_delivery,core_20261003a` 排序的三项，每项 exact key
`scope,batch,state,evidence`，state 必须 `NOT_ISSUED`，evidence exact key 为 `path,sha256`。三项
evidence 分别固定为：

1. scope `LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1`、batch `20261002a`；
   `docs/a2-execution/Q2_OLD_PRODUCER_ADMISSION_RETRY_IMPLEMENTATION_REVIEW.md` /
   `de276883d2a0b1a68009ef994bf24211ac0adb4fe5a5053da70c349e241c7d9d`；
2. scope `LH-Q2-NAMESPACE-FIXTURE-DELIVERY-v1`、batch `namespace_delivery`；
   `docs/a2-execution/Q2_NAMESPACE_FIXTURE_DELIVERY_IMPLEMENTATION_REVIEW.md` /
   `bd5d530652380777bca60905b11ef56caa760c794fee611748ae7c4f1aee5026`；
3. scope `LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1`、batch `core_20261003a`；
   `docs/a2-execution/Q2_CORE_ACCEPTANCE_DELIVERY_IMPLEMENTATION_REVIEW.md` /
   `e64f1be1287ac8bed5f582b01e179b66dd79ead0eb91e8ccf1c71d3ea0095da0`。

三项 `state` 都固定 `NOT_ISSUED`。它们的技术 evidence 只封住已知后续批准线；未知私有批次
不存在由第 2 节的 Owner completeness premise 承担，不得冒充为扫描证明。合同列举的
path/project/unit/record 中发现任何未列消费或冲突对象仍立即 `STOP_AND_RETAIN`；
不宣称该有界检查能发现任意未知对象。

### 3.2 policy basis

`policy_basis` 恰含
`schema,fixture_cloud_config,identity_public,known_hosts,remote_expectation,policies,
policy_predicates_sha256`；`schema=local-hand-q2-core-policy-basis/v1`。前三项 exact key 为
`binding_pointer,sha256`；pointer 分别固定为
`/fixture_cloud_config,/identity_public,/known_hosts`（相对 local-management-binding 根的 RFC 6901
pointer），SHA 分别固定为
`5b81deabefb7bc70aa6ee13b72053d65556fac1e400b5a37919ca1f90e4b6523`、
`e67e15549d3e8586af936108f666612841d31612705236dd8ce265a3da18b25c`、
`d1025c074e532f29534fcab1d10ec1bc2f38d2137173c74d0bc921bbab420bbd`，并引用 local binding
中同名 held entity。pointer 必须解析到 exact record，held raw 的 bytes/SHA 须重算一致；这些是
approved source，不是 current guest attestation。

`remote_expectation` exact key 为
`account,home_path,login_shell,hello_schema,parser_profile,aliases,remote_tokens_sha256,
remote_command_sha256,remote_entity_preimages_stage`；account 固定 `q1admin`，home 固定
`/home/q1admin`，login shell 固定 `/bin/bash`，parser profile 固定
`bash-noninteractive-c-v1`，HELLO 固定 v2，stage 固定 `HELLO_JIT`；三项 account value 必须与同一次
passwd record read 相等。`aliases` 恰含 `shell,sudo,env,systemd_run,python`，值依次固定为
`/bin/bash,/usr/bin/sudo,/usr/bin/env,/usr/bin/systemd-run,/usr/bin/python3`。
`remote_tokens_sha256` 的 preimage 是原 A 第 304–320 行规定的完整 token array，只把 loader/bootstrap
引用解析为最终 D 的 verified field-code raw；`remote_command_sha256` 的 preimage 是该 exact array 经
Python `shlex.join()` 后的 UTF-8 bytes。两值在 D/package freeze 时确定，必须由两个 builder 独立重算；
不得留 placeholder、从 HELLO 回填或使用 observed command 选择 token。
local-management-binding的`remote_expectation`必须逐字段等于本`policy_basis.remote_expectation`；
两处不得分别构造、分别默认或容许摘要相同而raw不同。

`policies` exact key 为 `sudo,sshd,authorized_keys,rc`。每个 value exact key 均为
`schema,mode,sources,paths,argv,environment,execution,predicate,limits,predicate_sha256`；
`predicate_sha256` 只摘要同项
`predicate={profile,parameters}` 的 canonical no-LF bytes，完整四项另由顶层
`policy_predicates_sha256` 摘要；每项
`schema=local-hand-q2-core-policy-basis-item/v1`。四项固定如下：

- `sudo`：sources 恰为 `[/fixture_cloud_config,/remote_expectation]`，mode
  `same-carrier-current-self-observation`；paths 恰为 `/etc/sudo.conf,/etc/sudoers,/etc/sudoers.d` 的 fixed
  no-follow closure，最多 66 files/3 directories/8 depth，单文件≤262144 B、总计≤1048576 B、
  每目录≤256 entries；argv 恰为
  `[/usr/bin/sudo,-n,-ll,-U,q1admin]`；固定 parser
  只接受至少一个 runas users `[ALL]`、无显式 RunAsGroups、tag `NOPASSWD`、command `ALL` 的完整
  current-host entry；C-locale `Options: !authenticate` 归一化为 `NOPASSWD`。缺省 RunAsGroups
  归一化为 `[]`，表示未显式配置组列表，不表示任意组或目标用户无组。host `ALL` 必须由已绑定
  cloud-config 中唯一 `q1admin ALL=(ALL) NOPASSWD:ALL` 及 current held sudoers closure 中对应
  grant 证明；`-ll` 输出只证明该 grant 当前对本 host 生效，不能独立恢复原 Host_List。
  不得将 `(ALL)` 改为 `(ALL:ALL)` 或修改 guest 配置来满足 predicate。未知 locale/grammar/额外
  include/plugin relation 不猜测；固定 carrier 实际已以 `sudo -n` 到达 euid=0 仍须独立交叉验证。
- `sshd`：sources 恰为 `[/known_hosts,/remote_expectation]`，mode `source-plus-effective`；paths 固定
  `/etc/ssh/sshd_config` 与其仅允许的
  `/etc/ssh/sshd_config.d/*.conf` lexical regular-file closure；任一 symlink、其它 Include、active Match、
  超 65 files/1048576 B 即停止。argv 恰为 `[/usr/sbin/sshd,-T]`；C parser 要求
  `pubkeyauthentication yes`、`forcecommand none`、`permituserenvironment no`、
  `authorizedkeyscommand none`，且 `authorizedkeysfile` 恰为有序
  `[.ssh/authorized_keys,.ssh/authorized_keys2]`。sshd executable
  本身按与 HELLO entity 相同的 resolved-target 算法绑定在 admission，不塞入 HELLO。
- `authorized_keys`：sources 恰为 `[/identity_public,/remote_expectation]`，mode `exact-single-key`；
  path 只能由 current passwd home 加 `.ssh/authorized_keys` 与 optional `.ssh/authorized_keys2` 机械
  派生，后者必须 absent；held component 不跟随 symlink，目录/文件 owner 为 current uid，
  文件 single-link regular、mode 不宽于 0600、≤65536 B。去除空行和 `#` 行后必须恰一行、无 key
  options，key type+base64 bytes 逐字节等于从固定 `identity_public` 按下文 transform 得出的
  `approved_key`；comment 可有但不参与 key 比较。
- `rc`：sources 恰为 `[/remote_expectation]`，mode `ssh-rc-absence-shell-provenance`；必须 absent 的 exact paths 为
  `$HOME/.ssh/rc,$HOME/.ssh/environment,/etc/ssh/sshrc`。另按固定顺序读取存在的
  `$HOME/.profile,$HOME/.bash_profile,$HOME/.bash_login,$HOME/.bashrc`，逐项绑定
  path/existence/entity，单项≤1048576 B、合计≤4194304 B。对于实际 login shell 为 bash 的
  noninteractive `-c` profile，`.bashrc` 若存在，只接受 blank/comment 后第一个 executable AST 为
  无重定向/扩展副作用的 `case $- in *i*) ;; *) return;; esac`；guard 前出现 assignment、source、trap、
  function、command 或 continuation 即停止。其它 startup bytes仍全量稳定读取/hash；这些观察只作
  post-entry provenance，不宣称 pre-entry 语义安全，风险由第 2 节第 1 项治理前提承接。

上述 sudo/sshd 是唯一 carrier 内由已运行 dispatcher 发起的两个 fixed semantic helper；“无配置/业务
mutation”不等于无 audit/NSS/plugin/atime incidental effect。每项最多调用一次、不得并行、不得重试；
它们不是第二 SSH、sudo carrier、systemd-run、unit 或 request。任何命令不可用、输出不稳定、被截断、
timeout、非零退出、双 EOF 缺失或 predicate 不完整均已消费并停止。

每项 `paths` object 恰含 `profile,fixed_paths,home_relative_paths,include_roots,limits`；path item 恰含
`path,required`，include item 恰含 `path,required,selection`，limits 恰含
`max_files,max_directories,max_depth,max_file_bytes,max_total_bytes,max_directory_entries`。所有系统路径从
`/`、home path 从 HELLO 固定 home 以 held component fd逐级 no-follow解析；禁止 alias/`..`/symlink，
regular须 nlink=1，系统对象 uid=0、home对象 uid=HELLO uid，present object与祖先不得 group/other
writable。include只在固定 root内按ASCII排序展开；cycle/repeat/outside-root/unsupported glob/unknown
syntax即停止。每项 observation stage 固定 `POST_ENTRY_PRE_H01_INTENT`，
`pre_entry_containment=false`。

四个 `paths` 的值也固定，不留 D-time 选择：

- sudo：profile `sudoers-fixed-closure-v1`；fixed 为
  `[/etc/sudo.conf:true,/etc/sudoers:true]`，home-relative为空，include为
  `/etc/sudoers.d:true:sudoers-includedir-v1`；limits=`66,3,8,262144,1048576,256`；
- sshd：profile `sshd-fixed-closure-v1`；fixed为 `/etc/ssh/sshd_config:true`，home-relative为空，include为
  `/etc/ssh/sshd_config.d:true:ascii-star-dot-conf-v1`；
  limits=`65,2,8,262144,1048576,256`；executable 另由 `execution` 的 16 MiB 上界和 snapshot object
  绑定，不混入 config closure；
- authorized_keys：profile `authorized-keys-fixed-home-v1`；fixed/include为空，home-relative依次为
  `.ssh/authorized_keys:true,.ssh/authorized_keys2:false`；limits=`2,3,4,65536,131072,64`；
- rc：profile `ssh-rc-bash-noninteractive-v1`；fixed为 `/etc/ssh/sshrc:false`，home-relative依次为
  `.ssh/rc:false,.ssh/environment:false,.profile:false,.bash_profile:false,.bash_login:false,.bashrc:false`，
  include为空；limits=`7,4,4,1048576,4194304,64`。

两个 helper 的 `environment` 都恰为
`{"HOME":"/root","LANG":"C","LC_ALL":"C","LOGNAME":"root","PATH":"/usr/sbin:/usr/bin:/sbin:/bin","SYSTEMD_COLORS":"0","USER":"root"}`；
authorized_keys/rc 的 `environment={}`。`execution` exact key 为
`executable,executable_identity_source,executable_max_bytes,cwd,stdin,shell,max_invocations,
required_exit_status,require_stdout_eof,require_stderr_eof,drain_profile,overflow_action,timeout_action,
side_effect_class`。sudo的`executable,executable_identity_source,executable_max_bytes`依次为
`/usr/bin/sudo,HELLO_REMOTE_MANAGEMENT_SUDO,16777216`，sshd依次为
`/usr/sbin/sshd,POLICY_SNAPSHOT_OBJECT,16777216`；两者的`cwd="/"`、`stdin="/dev/null"`、
`shell=false`、`max_invocations=1`、`required_exit_status=0`、两个EOF字段均true、
`drain_profile=concurrent-nonblocking-v1`、`overflow_action=SIGKILL_THEN_WAIT_NO_RETRY`、
`timeout_action=SIGKILL_THEN_WAIT_NO_RETRY`、
`side_effect_class=CURRENT_GUEST_SEMANTIC_HELPER_WITH_AUDIT_NSS_PLUGIN_EFFECTS`。
这里两个 action 值相同但分别处理 output overflow 与 wall/CPU timeout；kill 后必须 reap 并取得双 EOF。
authorized_keys/rc的前三值为`null,null,0`，`cwd=null`、`stdin=NOT_APPLICABLE`、`shell=false`、
`max_invocations=0`、`required_exit_status=null`、两个EOF字段均false、三个action/profile字段均
`NOT_APPLICABLE`、`side_effect_class=NO_HELPER_PROCESS`。

每项顶层 `limits` 恰含
`command_seconds,command_cpu_seconds,stdout_bytes,stderr_bytes,combined_output_bytes`：sudo与sshd依次
固定 `5,2,65536,65536,65536` 与 `5,2,1048576,1048576,1048576`；authorized_keys/rc全部为0且argv为空。每项
`predicate` 恰含 `profile,parameters`：sudo parameters exact key为
`account,cloud_config_literal,cloud_config_literal_count,required_grant,on_unknown`；sshd为
`required_effective,on_unknown`；authorized_keys为
`account,home_path,authorized_keys_files,approved_key,key_comparison,allowed_options,
required_effective_entries,comments,blank_lines,on_unknown`；rc为
`account,home_path,required_absent,shell_startup_paths,bashrc_guard_profile,
forbidden_environment,shell_parser_profile,on_unknown`。四项 profile 依次固定
`sudo-ll-c-v1,sshd-T-c-v1,authorized-key-single-v1,ssh-rc-bash-noninteractive-v1`。

- sudo parameters 值固定为：`account=q1admin`，`cloud_config_literal="q1admin ALL=(ALL) NOPASSWD:ALL"`，
  count=1，`required_grant` exact key/value 为
  `{"commands":["ALL"],"host":"ALL","runas_groups":[],"runas_users":["ALL"],"tags":["NOPASSWD"]}`；
  host 来自 source/config closure，组列表来自 helper 的 absent-RunAsGroups 归一化，两者不得混淆；
- sshd `required_effective` exact key/value 为
  `{"authorizedkeyscommand":"none","authorizedkeysfile":[".ssh/authorized_keys",".ssh/authorized_keys2"],"forcecommand":"none","permituserenvironment":"no","pubkeyauthentication":"yes"}`；
- authorized_keys 的 account/home/files 固定 `q1admin`、`/home/q1admin`、
  `[.ssh/authorized_keys,.ssh/authorized_keys2]`；`approved_key` exact key 为
  `type,key_base64,source_sha256`，前两值由固定 `identity_public` raw 严格解析为唯一 non-option
  `ssh-ed25519` record 后逐字复制，source SHA 固定
  `e67e15549d3e8586af936108f666612841d31612705236dd8ce265a3da18b25c`；
  `key_comparison=TYPE_AND_DECODED_KEY_BYTES_EQUAL`、`allowed_options=[]`、entries=1、
  `comments=IGNORED_AFTER_KEY`、`blank_lines=IGNORED`；
- rc 的 account/home 固定 `q1admin,/home/q1admin`；`required_absent` 固定
  `[/home/q1admin/.ssh/rc,/home/q1admin/.ssh/environment,/etc/ssh/sshrc]`，
  `shell_startup_paths` 固定
  `[/home/q1admin/.profile,/home/q1admin/.bash_profile,/home/q1admin/.bash_login,/home/q1admin/.bashrc]`，
  `bashrc_guard_profile=first-executable-interactive-return-v1`，
  `forbidden_environment=[BASH_ENV,ENV]`，`shell_parser_profile=bash-noninteractive-c-v1`。

四项 `on_unknown=STOP_AND_RETAIN`；不得从 current observation 选 profile或放宽 parameters。parser 的
grammar/version 实现在 package 已绑定的 D dispatcher Git blob内；未知 sudo plugin/include、
sshd Include/Match/quote/glob、key/shell grammar一律停止，不以 helper exit 0 替代 predicate。

令 `C(x)` 为本文 canonical no-LF bytes、`H(x)` 为 lowercase SHA-256 hex。每项
`predicate_sha256=H(C({"profile":predicate.profile,"parameters":predicate.parameters}))`；
`policy_predicates_sha256=H(C(policies))`，`policy_basis_sha256=H(C(policy_basis))`。current snapshot
schema固定 `local-hand-q2-core-policy-snapshot/v1`，顶层 key恰为
`schema,policy,account,objects,facts`；account恰含 `name,uid,gid,home,login_shell`，objects按ASCII path
排序并恰含 `path,state,kind,dev,ino,mode,uid,gid,nlink,bytes,sha256`；PRESENT regular/executable 的
`bytes,sha256` 是 held raw，PRESENT directory 的二者为 null，ABSENT 时 `kind` 至 `sha256` 全部为 null。
`facts` 按 policy 使用以下 exact key：sudo 为
`helper,cloud_config_literal_count,parsed_grants,matched`；sshd 为 `helper,effective,matched`；
authorized_keys 为 `effective_entries,matched`；rc 为
`required_absent,shell_startup,bashrc_guard,forbidden_environment_absent,matched`。`helper` 恰含
`argv_sha256,environment_sha256,started_boottime_ns,finished_boottime_ns,exit_status,stdout_bytes,
stdout_sha256,stderr_bytes,stderr_sha256,combined_bytes,timed_out,stdout_eof,stderr_eof`；两个时间必须在
原 guest deadline 内，输出摘要只绑定有界 raw，raw 本身不回传。其它 facts 的 value shape 必须逐字段
固定如下：`parsed_grants` 是helper output order的array，每项与`required_grant`使用同一exact key/type；
`effective`与sshd `required_effective`同shape；authorized `effective_entries`按path/line排序，每项恰含
`path,line_number,key_type,key_sha256,options,comment_present`，其中options必须[]、key摘要的是decoded key
bytes；rc `required_absent`按predicate顺序且每项恰含`path,absent`，`shell_startup`按predicate顺序且每项
恰含`path,state,bytes,sha256`，ABSENT时后两值为null，`bashrc_guard`恰含
`path,state,profile,matched`，`forbidden_environment_absent`按predicate顺序且每项恰含`name,absent`。
所有`matched`为boolean；不得自由增键。`helper.argv_sha256`与`environment_sha256`分别摘要approved argv
array和environment object的canonical no-LF bytes。`snapshot_sha256`
是完整 snapshot canonical no-LF 摘要，`facts_sha256` 是 `facts` canonical no-LF 摘要。
admission policy仍使用原 exact `paths,bytes,sha256,relation` shape；relation恰含
`stage,pre_entry_containment,policy_basis_sha256,predicate_sha256,snapshot_sha256,facts_sha256,matched`。
任何字段不得由current value回填static predicate。

### 3.3 obligations、retained 与 reconciliation

`historical_capacity_obligations` exact key 为
`schema,source_horizon,source_union_sha256,snapshot_rows,delta_rows,effective_rows,row_relation,
placement,configured_quota_rows,totals,released_or_refunded`；
`schema=local-hand-q2-core-historical-capacity-obligations/v1`。24-row `snapshot_rows` item 的基础
exact key 为
`id,category,commitment,covered_paths,evidence,accounting_categories`，只允许 retained source 中原有的
`released_or_refunded` 和 `actual_allocation_already_excluded_from_free` 两个可选 key；12-row delta
item exact key 由本 amendment 定义为
`reservation_id,batch,category,covered_paths,evidence,commitment,device_selector,status,
actual_allocation_already_excluded_from_free`。`released_or_refunded=false`；current filesystem/device
identity 不得伪造进 static row，只能在唯一 carrier live 映射。`effective_rows` 必须逐字等于
`snapshot_rows + delta_rows`；不得再把 7-row reconciliation prefix 相加。`row_relation` 逐字等于
source relation 中的同名 object，`placement`逐字等于source relation obligations中的同名object；
`configured_quota_rows` 恰为上文 46-row canonical vector。

`totals` exact key 为
`snapshot_bytes,snapshot_inodes,delta_bytes,delta_inodes,effective_bytes,effective_inodes,
configured_quota_bytes,configured_quota_inodes`，值依次固定为
`626790400,32113,138412032,8064,765202432,40177,249561088,17792`。configured quota 是按
project/device 另加的 liability，不得把它简单并入 36-row checksum 或与 current usage 相减。

`retained_preparation` exact key 为 `paths,domains`：paths 恰为 16 个 source-order
`{path,device,inode}`，domains 恰为 4 个 source-order
`{project_id,hard_bytes,inode_hard_limit}`。canonical no-LF paths 为 1196 B / SHA-256
`1ea38f024d0ed06ec5d801ac9fc1b99f4938366d3cc979d8f5ba3b9eddd013c6`，domains 为 267 B /
SHA-256 `45c231e6f4dd1360888b9e4e3f790ce175440b8af89231801feeede2b21a2c4c`，完整 object 为
1484 B / SHA-256 `24772cefec5e2c51364a1f4d1dadf692a2a666999077772138201004f811a808`。
它们来自 locator plan，不是 current existence/capacity 证明。

retained sources 中没有完整可采用的 reconciliation 五文件 seal；因此 `reconciliation` 恰为：

```json
{"state":"NO_ELIGIBLE_RETAINED_SEALED_RECORD_SOURCE","applied":[],"released_bytes":0,"released_inodes":0,"record_basenames":["evidence-adoption.json","reconciliation-intent.json","live-attestation.json","reconciliation-record.json","reconciliation-seal.json"]}
```

这只说明 retained source 中没有 eligible seal，不证明 current guest absence。live 必须在派生
`.reconciliation` 位置检查目录本身 absent；目录存在（即使为空）、五名任一存在、枚举不完整或 UNKNOWN
都 `STOP_AND_RETAIN`。不得退款或采用旧 run permission。

两个独立 builder/parser 必须由同一 held raw closure 得到逐字节相同 artifact。source/archive/member
缺失、schema/selector 不明、摘要漂移、source horizon 不闭合、重复 credit 或关系不一致均
`NOT_ISSUED`；Owner 文字不能替代 raw bytes。

## 4. package、marker、digest 与 JIT identity

field package 升级为 `local-hand-q2-core-field-package/v2`。manifest 在原顶层加入
`amendment,approved_inputs`；`approved_inputs` 恰含
`path,bytes,sha256,approved_source_relation_sha256`，其中path固定
`private/approved-inputs.json`、bytes/SHA逐字绑定该canonical+LF member，
`approved_source_relation_sha256=H(C(approved_inputs.source_relation))`。该member的manifest item仍用
原`path,role,mode,bytes,sha256,origin` keyset，role=`approved-inputs`、mode=384；origin exact key为
`kind,bytes,sha256,approved_source_relation_sha256`，kind=`approved-inputs`且其余三值逐字段等于顶层
approved_inputs。package framing magic仍为`LHCFP1\n`，只由strict v2 schema区分；v1/v2不得混拼。
原`locators.source_relation_sha256`字段保留，且只摘要下述引用local binding的locator relation v2；
它与approved-input顶层source relation的`approved_source_relation_sha256`不是同一preimage，禁止复用。
locator relation v2的唯一preimage是canonical no-LF object
`{"schema":"local-hand-q2-core-locator-relation/v2","local_management_binding_sha256":...,
"observation_record_sha256":...,"locators":...}`；`locators`恰为除自身`source_relation_sha256`外的原
private-locators fields，后两项逐字段来自已验证package value。
原 entry 中 `management_entry_binding_sha256` 精确替换为
`local_management_binding_sha256`；其 preimage 只含 request 前 held local wrapper/start/cloud-config/
profile/environment/dependencies/key/known_hosts/cwd/transport 与 static remote expectation，绝不偷带
current remote UID/GID/entity bytes；其 exact top-level key 为
`schema,anchor,writer,wrapper,fixture_start,fixture_cloud_config,profile,environment,dependencies,identity,
identity_public,known_hosts,cwd,remote_expectation,transport`，
`schema=local-hand-q2-core-local-management-binding/v1`。`anchor` 恰含
`path,dev,ino,mode,uid,gid,nlink`，必须是held `0700` directory且无setgid，完整identity/nlink前后稳定；private path只留在
root-only binding，不进入公开 evidence。`writer` schema 为 `local-hand-q2-core-local-writer/v1`，exact key为
`schema,user_namespace,pid_namespace,process,uid,gid,supplementary_gids`；两个namespace各恰含held
`/proc/self/ns/user`、`/proc/self/ns/pid`的`dev,ino`，`process`恰含`pid,starttime_ticks`并由同一次held
`/proc/self/stat`严格解析，`uid/gid` 各恰含 `real,effective,saved,filesystem`，`supplementary_gids` 是升序无重复 integer
array。上述值来自同一次受限 `/proc/self/status`、stat和held namespace read并在 release 前后稳定；四个 UID
必须都等于 `anchor.uid`，四个 GID 都等于 `anchor.gid`。不得把 current tool environment 或 guest HELLO
的 root 身份当作 host writer 事实。writer/anchor 数值在 package freeze 时成为固定 field fact；每个 local
create/open/fsync/reread 前后都须重验同一 writer 和 anchor，local 对象 uid/gid 必须等于绑定的
filesystem uid/gid。

manifest 顶层 `implementation`、`amendment.implementation` 与 marker/session 同名字段都逐字段等于本
amendment C 后冻结的新集成 D。所有 `field-code` member origin 仍使用原 A 的 exact
`kind,commit,path,blob` shape：`kind=implementation-blob`、`commit` 等于 D，path/blob 必须由 D tree
逐项解析；origin 不含 tree key。旧 partial D `520f77f578b90d31870517e33e29bee42918f3c0` 只作
predecessor，不是 executable origin。

consumption marker v2 exact top-level key 为：

```text
schema,scope,session_id,baseline,owner_decision,closure,implementation,amendment,
candidate,package,approved_inputs_sha256,local_management_binding_sha256,writer,
carrier_argv_sha256,host_boottime_origin_ns,host_monotonic_origin_ns,
host_boottime_deadline_ns,host_monotonic_deadline_ns,state
```

existing marker（任意类型/partial）表示该唯一批次已消费。marker absent 但五个 local output basename
任一存在时为 `NOT_ISSUED_CONFLICT`，未消费、不清理。其余 source/package/local gate 失败为
`NOT_ISSUED`。只有 O_EXCL marker 完整持久化后才可发唯一 carrier request。

dispatch session 升级 v2并加入同一 `amendment`；`admission.binding` 恰含九项：

```text
approved_inputs_sha256,approved_source_relation_sha256,policy_basis_sha256,
historical_capacity_obligations_sha256,retained_preparation_sha256,reconciliation_sha256,
local_management_binding_sha256,hello_sha256,remote_management_sha256
```

preimage 分别且仅为：approved inputs 完整 raw canonical+LF；中间五个 approved-input component value
canonical no-LF；完整 local-management-binding canonical+LF；实际 HELLO v2 frame JSON canonical+LF；
HELLO `remote_management` value canonical no-LF。不得把九项 binding object 自身的摘要冒充任一字段。

HELLO v2 在原字段增加 `remote_management`。其 exact key 为
`account,uid,gid,home,login_shell,parser_profile,shell,sudo,env,systemd_run,python,
remote_tokens_sha256,remote_command_sha256`。五个 entity exact key 为
`path,resolved_path,symlink_chain,dev,ino,mode,uid,gid,nlink,bytes,sha256`：

- `account,uid,gid,home,login_shell` 必须来自同一次 current account-record read，home恰等
  `/home/q1admin`；`path` 是 actual argv/account requested absolute alias；依次为 current login shell、
  `/usr/bin/sudo`、`/usr/bin/env`、`/usr/bin/systemd-run`、`/usr/bin/python3`；
- `symlink_chain` source-order item exact key 为 `path,target`。collector 以 held parent fd 逐 component
  `lstat/readlink`，最多 8 hops、64 components，每个 path/target≤4096 UTF-8 bytes，拒绝 `..`、
  magic-link、loop、越界、absolute-root 切换或漂移；`resolved_path` 是最终 canonical absolute target；
- final target 以 `O_RDONLY|O_NOFOLLOW|O_NOATIME|O_CLOEXEC` 打开，不允许无 `O_NOATIME` fallback；
  读前/后重验 alias-follow identity、resolved-name identity、held fd 和 stable metadata。每项
  `0<bytes<=16777216`，五项总读取≤83886080 B；
- top-level `python` 仍为原九字段
  `path,dev,ino,mode,uid,gid,nlink,bytes,sha256`；它必须逐字段等于
  `{path:remote_management.python.resolved_path,dev,ino,mode,uid,gid,nlink,bytes,sha256}`，其中后八值
  取同名 nested field。nested `remote_management.python.path` 固定为 requested alias
  `/usr/bin/python3`，不得把 nested 的 alias/resolved/symlink 三个字段硬塞进 top-level shape。

HELLO JSON≤4096 B、完整 frame≤4112 B；超限或任一 UNKNOWN 停止且 host 不发送 BIND/package。
HELLO framing magic仍为`LHCHLO1\n`；BIND仍为原`local-hand-q2-core-carrier-bind/v1`及`LHCBND1\n`，
不得用wire magic未变来接受v1 HELLO/package schema。

## 5. marker 前后与 live admission

offline static source/D/package-template release gate结束后，调用端立即按BOOTTIME-first、
MONOTONIC-second取得不可刷新origin并固定`+900s` deadline；此前不得读取本scope current
management anchor/writer/absence事实。随后在同一900秒窗口内完成held local binding、writer、
ARG_MAX、exact package双build/parse及release digest。先完成这些门，再检查held anchor下唯一marker
和五个fixed output basename的absence；package中的guest object names仅作静态closed-set验证，
不得声称已检查current guest。原local file/directory只读路径保护与NOATIME要求保持，无权限fallback。
本版不需要capture kernel/module/superblock/raw-device资格化或内核source proof。

absence PASS后，O_EXCL marker的open/write/file-fsync/reread/parent-fsync是本window第一组durable
syscall；每次create/write/fsync后的allocation检查均按§6执行。marker完整返回并通过及时性与identity
检查后，才可发唯一carrier。marker raw仍≤16384 B；它与其余五文件共同受§6的应用与观测限额。
marker后，HELLO/BIND/package/EOF全部留在唯一carrier；host在marker前把approved inputs对held
local/private raw与Git source逐字验证。guest仅验证package内自足canonical artifact、固定transform/
digest与current guest predicate，不可能也不得声称重新解析host-only RFC6901 pointer或private raw。
六个basename的验证性回读按§6的held parent、NOFOLLOW/NOATIME与同inode身份规则执行。
guest 验证 package 后、任何 staging/install/
create-only state/case intent 前，live admission 必须依次完成：

1. 本文四项 policy 与 account/program cross-binding；
2. 16 retained paths、4 domains 的 identity/limits/owner/ancestry；
3. `.reconciliation`、installation/staging、三个 case、21 roots/project IDs 和固定 units 的 current
   absence/identity；
4. filesystem/quota/current usage 与 36 个 historical rows 的逐设备映射；在 current free 上另加全部
   unreleased future commitment 和本次新 admission，不第三次加 actual，不退款、不填零；
5. 原 A 的保护、ARG_MAX、deadline、package/install/native/effect 其余全部门。

任一 existing/partial/race/UNKNOWN 为已消费的 `STOP_AND_RETAIN`；不重连、不重试、不换名。只有 live
gate 全 PASS 才能创建首个 guest mutation或 H01 intent。

保持 v1 shape 的 remote-result 不新增 admission digest，也不得被描述为直接携带九项 binding。
九项 binding 原文进入 session/admission member；同一 output manifest 的 member references/raw SHA
同时绑定 session 与 remote-result，capture manifest 再绑定完整 output manifest，local receipt 最后绑定
capture。private approved-input raw 不进入 output。

## 6. 六文件 capture 与 live 终结

### 6.1 对象、写入限额与实际占用

沿用原 A 的唯一六个 basename：消费 marker、stdout、stderr、remote-result、capture manifest、
acceptance receipt；准确名字由原 fixed object table 决定。不得新增 attestation、临时文件、旁路日志、
持久化 allocation ledger 或额外副本；已存在任何类型的 marker 代表已消费，marker absent 但任一
五个 output 名存在则 NOT_ISSUED_CONFLICT。不改名、覆盖、truncate、删除、清理或重试。

| 对象 | 本版 logical bytes 最大值 | inode 数 |
| --- | ---: | ---: |
| marker | 16384 | 1 |
| stdout，含 HELLO/frame 开销 | 54525952 | 1 |
| stderr | 4194304 | 1 |
| remote-result，重复 payload 仍再次计费 | 262144 | 1 |
| capture manifest | 262144 | 1 |
| acceptance receipt | 65536 | 1 |

stdout + stderr **合计**不得超过 54525952 B（52 MiB），因此六文件 logical 总量最大
55132160 B，低于总 application ceiling 67108864 B。固定最多六个文件/inode，同样不超过原 16。
原 frame 58716144 B 与 carrier 合计 62914560 B 拒绝门保持，但 52 MiB 接收/capture 门更早触发；不能借剩余额度。
原单次 read 的 remaining+1 sentinel 仍只用于判定溢出，超出的 chunk 不进入 capture，不把探测字节
伪装成已保存的结果。remote-result 不以内容已在 stdout 中为由去重。

固定 writer 必须在每次创建前检查 basename、单次 O_EXCL 与对象数；每次写入前按完整待写 chunk
检查 role cap、两流合计和总 logical 余额。允许 short-write 的 write-all，但每个实际正返回字节均
单调计费；禁止 seek 后覆盖、truncate、重新打开追加或释放额度。输入超过本角色 cap 即停止，不能裁剪
JSON、丢弃 evidence 或借其它对象的余额来写出成功。不得在 six-object 集合之外增加本 scope 的持久 writes。

每次 create、成功 write、file fsync 和 parent fsync 返回后，以 held fd 对已创建的六文件实际集合
采样 `st_blocks*512`，并重验类型、dev/ino/name、uid/gid、0600、nlink=1、bytes 和稳定性。
任何 observed 合计 >67108864 B、对象数 >6/16、身份不符或采样失败立即停止后续持久动作并保留。
保存内存中的 `max_observed_allocated_bytes`，不是只看最后一次；receipt 写前也必须检查已经观察的
余额与 logical cap，写后仍做真实采样。`st_blksize` 向上取整、free space 或 guest quota 不能替代
实际值，也不能作为下一次 syscall 物理分配增量的证明。

**观测超限会停止，但可能已经产生超限 allocation；未观测瞬时 allocation 也可能更高。**
本版不声称上述用户态检查强制了全过程物理上限，不把 parent/journal/共享 ext4 元数据归零或冒充
已计入六文件 `st_blocks`。不读取 raw block device、superblock、loaded module、runtime IKCONFIG 或
内核 Git proof archive，也不以缺少它们阻塞这条已明确降低物理保证的路线。普通 host 身份仍需通过
原 held-path 权限和对象安全检查；历史目录记录不是当前资格证书。

marker 及 output 每次验证性回读都沿用 held parent 的 `O_RDONLY|O_NOFOLLOW|O_NOATIME|O_CLOEXEC`，
无取消 NOATIME 的 fallback。任一权限不满足，marker 前 NOT_ISSUED，之后 STOP_AND_RETAIN。
不为满足这些条件索取 host sudo 或修改权限。公开诊断只报告固定 reason code、数字计数/身份与摘要，
不输出 credentials、private raw、完整私有路径或环境变量。

### 6.2 receipt 与成功判断

capture manifest 保留 `local-hand-q2-core-capture-manifest/v1` 及原完整字段。
`files` 恰为已创建 marker/stdout/stderr/remote-result 的 basename 排序子集；成功时四项俱全。
每项 allocated_bytes 都是实际 `st_blocks*512`。manifest 不列自身和未来 receipt；receipt 的
`capture.bytes/inodes` 仍是此子集，完整六文件总量由 live finalizer 另行实际计算，不能混淆。

receipt 保留 `local-hand-q2-core-local-acceptance-receipt/v1` 与原十二项 exact top-level keys：
`schema,scope,session_id,consumption,transport,remote_result,wait,capture,real_task_execution,
result_evidence_collection,state,missing`。state 仍只为原 COMPLETE 或 STOP_AND_RETAIN。
原 package/output/remote-result/session/admission 摘要链、所有 case semantic PASS、真实 exit status、
两个 EOF、fsync/reread 与两项 `{status,evidence_sha256}` truth summary 均必须通过，不放宽成字符串或假值。
在磁盘写 COMPLETE 前这些先决条件必须已满足；写出的值只是待 live caller 完成最后持久化的记录。
只有下列流程全部成功，live 调用端才能接受并返回成功；单独重读磁盘 COMPLETE 字样没有这项资格。

receipt 的唯一持久化顺序为：held-parent O_CREAT|O_EXCL|O_NOFOLLOW|O_WRONLY|O_CLOEXEC,0600；
write-all；file fsync；fstat/close；同 parent 以 NOFOLLOW/NOATIME 重开；同 inode/owner/mode/nlink
完整回读相等与 stable fstat；close；parent fsync；最终六文件 allocation/identity 采样；双钟终结采样。
所有步骤复用 marker/local binding 中实际 host writer fsuid/fsgid，不假设是 guest root:root。
capture manifest 和其它文件也保留原 file/parent fsync、身份与回读要求。

origin 后每个可能阻塞的 persistence/termination/resource-observation syscall（clock read 自身除外）
发起前和返回后都按 BOOTTIME-first、MONOTONIC-second 检查，严格早于 marker 原 origin+900s。
最终 receipt parent fsync、allocation/identity 检查及 post-return clock sample 都必须及时；15s local-final
reserve 从原 transport 留给 finalizer，不增加窗口。及时发起但晚返只能失败，之后不再发起持久/终结
调用；不增加905秒尾窗，不保证磁盘调用一定能按时返回，也不宣称用户收到函数 return 的时间仍在窗内。
原 carrier 的超时终止/退出确认规则仍必须在其既有时限内安排，不以本条另发 unit 或 request。

receipt 创建前已知失败，仅在原剩余时间、role/logical 余额与实际观测限额全部允许时，最多尝试一次
STOP_AND_RETAIN receipt。create 前检查失败就保持 absent；O_EXCL 后任何失败、无法完成的短写/零写入、晚返、fsync/
回读异常或资源超限保留已形成的 partial/full 对象。已经创建的 COMPLETE receipt 如最终步骤失败，
不补写或改成 STOP；live 调用报告失败，不能因盘上文字而成功。无重试、补 seal 或 attestation。

成功返回沿用现有 finalizer 的 receipt、capture、semantic、files 与 total_allocated_bytes/total_inodes，
另附仅存在于该原调用进程返回值中的 `capture_accounting` object，exact keys 为
`mode,logical_bytes_written,created_inodes,max_observed_allocated_bytes,full_filesystem_peak_proven`。
mode 固定 `APPLICATION_LIMIT_AND_OBSERVED_FILE_ALLOCATION`，三项数值字段按实际计费；
`full_filesystem_peak_proven` 恒为 false。该对象不落盘，不成为新 runtime 文件或原 receipt 增键。
调用端报告功能结果时必须同步说明此计费语义，不能省略后宣称原全物理保证通过。

没有独立的 local restart verifier 或 derived-acceptance schema。进程退出后只保留原始文件供调查；
它们不自证最后 fsync、deadline 或完整物理峰值，不能导入后重新派生 COMPLETE。
guest H11 仍严格恢复 H11 自己 origin 的原 ledger/request/execution/unit/grant/deadline，
只做原允许的查询与恢复确认，不重启业务、不读取/打包业务 result、不新增 grant/unit、不刷新 deadline。

## 7. 不变项、条件顺序与成功定义

- candidate `4b6e4a7c403362358192086b88679e1326dcb2e1`、tree
  `4d4349580c9f4b67cc26f601126849c2bc8d76a4`、direct parent
  `607100a57206f7dc7cfcbd6cae8507cfa599b813`；wheel
  `infra_local_hand-0.2.0a1-py3-none-any.whl` / 288375 B / SHA-256
  `ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9`；payload
  `b4d094a9f70c308c63870c9fbf273b6b0646ad211d6f61a79901f52e67cf2e23`；projection
  11811 B / SHA-256 `55f555fc225edca943b8c86cee8119c4878f5ec1e9503a084ba7a560cf2c991d` /
  89 entries；原 harness 闭包保持。
- guest physical 188743680 B/13440、admission 289406976 B/16512、2090 CPU-s、peak
  2751463424 B/1160 pids、32 MiB input、60 MiB outer output refusal 保持；
  host capture 的 64 MiB/16 inode 按§6改为应用上限与实际文件分配观测验收，绝非原全过程物理保证。
  本次可接受stdout+stderr实际logical capture收紧为52 MiB，不能使用余下8 MiB。
- host 900 s、remote unit 800 s、guest cap 750 s、2 s mapping、15 s local final reserve、45 s remote
  reserve、315/150/120 s case/preparation/owner bounds均不延长。
- 最多一次 O_EXCL marker、最多一次 carrier request、一次 BIND/package/EOF；不 reconnect、retry、
  另行 probe、第二 request、换名、退款或重放旧批次。
- 严格 `H01_NORMAL → Q4_HELPER_RUNNING_CANCEL_SUBSET → H11_SAME_LEDGER_RECOVERY`。H01 保留
  empty-ledger gate；H11 只用原 ledger/request/execution/unit/grant/deadline，不重启业务、不读取/封装
  业务 result、不新增 unit/grant、不延长 deadline。
- namespace/watchdog 保持暂停；production `E3_SUPERVISION_UNVERIFIED` 保持；不授权生产启用、
  cutover、E4–E6、系统配置变更、公开 private raw evidence或把 UNKNOWN 提升为成功。

原固定 case/object 继续恰为：

| 顺序 | case / basename | operation | controller / projects |
| ---: | --- | --- | --- |
| 1 | `H01_NORMAL` / `c01-h01-normal` | `b6638120-ed28-4ed1-b603-a153fab1c93d` | `lhqcore20261003a-c01` / `12101..12107` |
| 2 | `Q4_HELPER_RUNNING_CANCEL_SUBSET` / `c02-q4-cancel` | `ade1b42f-f03d-48dc-b690-e588b44289f6` | `lhqcore20261003a-c02` / `12108..12114` |
| 3 | `H11_SAME_LEDGER_RECOVERY` / `c03-h11-recovery` | `4b035797-229a-4cdc-8eca-8195869b7ac9` | `lhqcore20261003a-c03` / `12115..12121` |

logical namespace `lhqcore-20261003a`、installation `local-hand-core-acceptance-20261003a`、staging
`.local-hand-core-acceptance-20261003a.staging`、十二 directory roles、二十一 roots、identity/unit
派生和 predecessor 全沿用原 A。

只有本 scope 的 A/B/C 后完成实现、全部 static/live/release 门通过、两次独立 package build/parser
逐字节一致并经独立审计，才可消费仍未消费的唯一现场批次。真实任务执行、退出确认、结果/证据收回
以及 live local `COMPLETE` 必须分别报告；任一缺失都不能以 source test、package freeze、磁盘receipt字样或批准文字代替。
