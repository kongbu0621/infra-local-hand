# Local Hand 核心完成修订：需求

- Authority：Owner；状态：**DRAFT / Gate OPEN / NOT APPROVED**。
- Scope：`LH-Q2-CORE-COMPLETION-ADJUSTMENT-v1`。
- R：`kongbu0621/engineering-sop` 的 `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，
  `docs/workflow/program-repository-documentation-gate.md`；原文 SHA-256
  `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- 本文与[架构](ARCHITECTURE.md)、[实施方案](IMPLEMENTATION_PLAN.md)共同构成待审文档 A；
  A 的准确 commit 在独立 baseline 登记中固定。尚无本修订的 Owner B、独立 CLOSED C 或实施许可。

## 1. 目标与原批准关系

只完成现有 Local Hand 核心链：H01 正常执行并收回结果，随后 Q4 取消，随后 H11 查询自己的原任务。
现场仍须满足原单次条件；源码完成、离线测试、CI 成功均不等于现场验收成功。

本修订保留以下历史基线与对应 B/C，不修改其原文或倒签批准：

| 已批准范围 | 准确文档 A |
| --- | --- |
| 核心验收交付 | `74366b3fe41e675b1aa2d677228714a5606c275c` |
| 输入绑定与结果收回修订 | `0bdb49cae5586be60a7ba31d4a8e8367854d1e8c` |
| host writer 传递 | `60756caedf6a2d978627272e44784d11009ac309` |

原 A 与本 A 冲突时，仅在本 A 明确列出的修订项经 Owner 批准后，以新项为准。
其余既有 CLOSED 工作仍按原范围推进。本草案不把修订范围自动视为 CLOSED。

## 2. 为什么需要修订

现有实现 D `3f1c4745d8ee888f0c0057794532aa78cfcddbbe` 的 dispatcher 为
262044 bytes，SHA-256 `8330044bead3ba2db0e801e102e57e8a4fb6ccafd8c0298166e41626ea352add`，
距离原 262144-byte 上限仅余 100 bytes。随后原范围内 deadline 修复 `6316770` 为 262072 bytes，
仅余 72 bytes。已保留的准入实现与前述测量源码合并估算为 319323 bytes，
尚未包含真实 usage 及后续集成。该数值是源码整合观察，不是已发布、已验收的实现。
继续通过删除校验或不可读压缩满足原上限，会损害实现与复核；不得这样处理。

原 guest 资源合同还要求瞬时物理峰值上界。共享安装池有编译器、venv 的短暂文件；冻结的 state
使用 SQLite WAL 而无 DB/WAL/SHM 总分配限额；journal 的逻辑长度和 capture 的结束分配观察，
也不能证明全程分配峰值；carrier 的创建/fsync/回读同样没有物理硬隔离。
现有应用记账、受控文件 I/O 与前后分配观察不能证明这些未观察区间从未超限，也不能证明
文件系统内部元数据或共享 journal 的全程峰值。
这是一项保证能力的差异，不能把增加采样、保留相同数值或测试通过当成已解决。

## 3. 修订一：可读 dispatcher 的源码上限

仅将 `q2_core_delivery_dispatcher.py` 的上限从 **262144** 改为 **524288 bytes**。
仍只有原来的 loader、bootstrap、dispatcher 三个 field 源码文件；loader 的 8192-byte 上限与
bootstrap 的 49152-byte 上限不变。源码必须可直接阅读和审查，不引入第四运行模块、压缩可执行
载荷或经字符串重构执行的代码。该修订不允许删除任何原权限、身份、路径、摘要或资源校验。

用于选择新上限的工程预算如下；后四项是规划额度，不是实测保证或预先获得的额外资源：

| 内容 | 字节规划 |
| --- | ---: |
| 当前源码与已保留准入闭包的合并估算 | 319323 |
| 准入迁移、现有接口接合 | 16384 |
| 真实 CPU、内存、pids、流和启动量 usage | 49152 |
| 存储记账与实际分配观察整合 | 32768 |
| 失败路径与停止诊断 | 16384 |
| 合计 | 434011 |
| 相对新上限的余量 | 90277 |

实际最终源码必须重新量出准确字节数并通过原 package 全部检查。32 MiB 输入、60 MiB 输出、
manifest/member 数量与长度、传输、内存及所有时间界不增加；更大的源码只消费原有预算。
任一最终 package 不能同时满足这些原限制时，停止发行，不能自动再扩额。

## 4. 修订二：11 个非 quota 池的资源保证

以下 11 个非 quota 池由未经证明的瞬时物理硬峰值保证，改为应用记账与实际 owned allocation
观察；数值和固定对象集合不增加。21 个 project quota roots 的原内核限额及检查保持。

| pool | 数量 | 每池字节 / inode 阈值 | 观测方式 |
| --- | ---: | ---: | --- |
| `shared_install` | 1 | 67108864 / 4096 | 受控文件/目录的完整分配扫描 |
| `carrier_audit` | 1 | 8388608 / 512 | 受控文件/目录的完整分配扫描 |
| 每 case `state` | 3 | 8388608 / 1536 | 受控文件/目录的完整分配扫描 |
| 每 case `journal` | 3 | 1048576 / 128 | 受控文件/目录的完整分配扫描 |
| 每 case `capture` | 3 | 20971520 / 384 | 受控文件/目录的完整分配扫描 |
| 每 case 七个 quota roots | 21 | 1048576 / 128 | 原 project quota 汇总和 enforcement 核验 |

固定 32 个 pool 互不重叠。其 ID 恰为上述两个 shared ID，以及按原 case 顺序生成的
`<case_id>/state`、`<case_id>/journal`、`<case_id>/capture`、
`<case_id>/quota/<ref>`，其中 ref 顺序为
`work-a,evidence-a,temporary-a,work-b,evidence-b,temporary-b,retained_store`。
所有已有 quota/root、path、owner 与用途保持，不重新分配 project 或迁移路径。

每 case 的 journal、capture/declarations 与七根按上述专属 pool 计费；其余 case-owned
目录与文件，包括 reservation/state/authority/session/control 以及四个未分配 project 的 profile/store
父目录与 case 祖先，归该 case `state` pool。跨 case 的新 SESSION 祖先归 `carrier_audit`。
这明确此前未逐项规定的记账归属，不新增目录或预算。安装相关 staging/最终安装/编译与 venv 临时
对象归 `shared_install`；已有祖先、历史义务和其它 writer 的对象不成为 owned pool 内容。

应用创建/写入之前检查原时间和已知请求是否会突破该池剩余额度；短写按实际写入计账，失败的部分
对象仍保留。重复扫描不能重复计同一 inode，独立副本必须分别计费；发现未授权 hardlink/alias
仍拒绝。观察到的当前用量降低不重置最大观测量，不返还任务/执行权或已作出的历史承诺。
应用已知累计写入、创建数量只记录受控 I/O；它们不是物理用量，也不能声称覆盖冻结子进程内部写入。

dispatcher 直接控制的创建、写入、fsync 后观察其触及的非 quota 池；安装子进程开始前和结束后、
每 case owner 开始前和结束后、原受控交接点、阶段转换、最终打包及 remote-result 形成前，
对相应已准备池完成观察。完整 32 池记录在最终报告中闭合，不要求每次初始化中间点所有池均已完成。
原 root 创建 → project assignment → hardlimit 设置继续原顺序及 guards；quota 完整汇总观察从
setup 成功后、准备提交、owner 前后与 final 边界取得。初始化中的 quota pool 不能报告 OBSERVED
或 ABSENT，失败保留部分状态并记录 INCOMPLETE。冻结 child 内部 create/write/fsync
不受逐次观察；不新增监视线程/进程，不修改冻结 child，不伪称其内部已逐次记账。若对象尚不存在，必须以原准入 absence
和此后未发生创建的受控事件记录共同证明，不以 case=NOT_RUN 自行填零。
完整扫描采用实际 `st_blocks * 512` 与 inode 数，持有身份、前后重检并覆盖固定分类的全部对象。
边界外共享目录、文件系统元数据、journal 与观察间隙不被伪装成已完整覆盖。

身份未知、扫描不完整或观测超限均停止；停止时可能已经超过阈值，未观察的瞬时峰值还可能更高。
原单 case **36 MiB / 2944 inodes** 与 guest **180 MiB / 13440 inodes** 保持为这些固定 pool
的应用/观察验收总账阈值，不能再称全程物理硬峰值。admission **276 MiB / 16512 inodes**、
逐设备历史义务与不退款保持；每 case management 32 MiB / 1024 仍只是不可写的准入 headroom。

非 quota 池只作受保护的元数据扫描，不复用逐文件读取/hash 内容的 retained snapshot 实现。
扫描遇到已归其它 pool 的子树即按固定分类排除，不遍历整个 filesystem；对象在一次观察期间变化
即该观察失败并保留，不重试。H11 ledger 只按原允许的 metadata/identity 核对，不导出 raw ledger。
七根均不递归遍历；H11 的七根只使用原允许的 project quota 汇总读取；不得为计算资源数字 stat/open/hash/重读
原业务 result 或 business evidence。quota identity 使用准备时已绑定的原 root 与 project，
不能通过新增业务结果读取补证据。若允许的观察不足，报告 INCOMPLETE。

### 4.1 逐设备保守准入

对每个固定 pool，依据其全部原允许输出路径、原角色归属和实际 `(dev,fs_uuid)` 得到 distinct
设备集合；在每个相关设备各预留完整 pool 预算。同设备同 pool 只计一次，不因多个目录重复。
跨设备的完整重复是不可消费的准入 headroom，不增加任一 pool 可写或观测阈值。metadata wrappers
与 SESSION/case 祖先必须进入实际设备归属；不得只因逻辑归入 state 就一律把它们算到 state 设备。
历史义务沿原按设备绑定、别名检查、无退款规则处理；已有 state/install 同设备等合同条件保持。

276 MiB / 16512 是所有逻辑 pool 加原 management headroom 各计一次的准入基准。
逐设备 `new_required_*` 合计可因上述保守跨设备重复而更大；不能硬凑 276 MiB 掩盖设备漏账，
也不能把新增预留当作可消费额度。本条明确原“按实际 filesystem 合并准入”的保守算法，
替代将不同设备表合计仍要求恰等于单次逻辑基准的解释，不新增路径、物理写入池或系统配置。

### 4.2 精确 supersede 范围

只 supersede 原 core A 的 REQUIREMENTS 第 3 节中“解包前后所有实际分配仍须满足下述共享
64 MiB/4096-entry 峰值”及“临时文件与最终安装的同时峰值统一计入共享 delivery pool”，
其 installation/usage 资源证据定义，以及第 5 节资源表和汇总里把上述 11 池及
36 MiB/180 MiB 当作全程硬峰值的部分；原第 5 节其它数值、逐设备容量、276 MiB 逻辑 admission 基准、
CPU/memory/pids 和执行上界不变。原 ARCHITECTURE 的资源预算/安装与分配证明段，
IMPLEMENTATION_PLAN 的 P1 资源批准项、P2 峰值测试项及 P5/最终验收中相同断言同步被本项替代。
原 binding-finalization amendment REQUIREMENTS 开头与排除节的“guest physical 保证不变”，
仅就这 11 池及聚合物理硬峰值被替代；21 根 kernel quota、其它安全校验与 host capture 保证不变。
原文件字节和历史批准保留，不把此修订追溯成旧批准已有内容。

## 5. 机读合同与真实 usage

### 5.1 唯一版本与授权绑定

新现场仅使用 `local-hand-q2-core-remote-result/v2`，保留原 remote-result 顶层字段，
恰增加 `resource_accounting`。原 package v3、session、marker、HELLO、BIND、frame magic、
output package、case/phase 原语义及六个 host 文件保持。固定 82 个 output members 不增加；
新对象内联原 remote-result，计入原 remote-result 文件和全部原输出限制，不产生第七文件。

`resource_accounting` exact keys 为
`schema,completion_adjustment,basis,full_guest_filesystem_peak_proven,pools,observed_maxima_sum,snapshot_sha256,missing`。
schema 固定 `local-hand-q2-core-resource-accounting/v1`；basis 固定
`APPLICATION_AND_OBSERVED_OWNED_ALLOCATION`；full_guest_filesystem_peak_proven 必须是 `false`。

completion_adjustment 恰含 `baseline,owner_decision,closure,implementation`，沿用现有 amendment
的严格形状：baseline 为 `commit,tree,documents_sha256`，documents_sha256 恰绑定本目录三文档；
owner_decision 为 `event,record_path,record_sha256`；closure 与 implementation 各为 `commit,tree`。
A/B/C 的准确值在批准后固定于 D 的 source constants；implementation 必须等于原
manifest.implementation。离线 source-lineage verifier 新增这第三条准确 A/B/C pin 和 C→D 祖先检查。
原 manifest 已有的 implementation 与三文件 SHA-256 继续绑定 D，不给旧 marker/package 增加新字段。
local finalizer 同时验证原 source horizon、准确 dispatcher release digest 与上述四项。
最终 D 同时为全部原 CLOSED C 与本修订独立 C 的后代；manifest.amendment 仍指原绑定修订，
不改写为本 A。source-lineage 的新增第三条针对本修订，不替换任何既有 lineage 检查。

新发行路径不得接受旧 v1 或把其 guest_allocated 值静默转换为新语义；旧 v1 仅可历史只读解析，
不得使新现场达到 COMPLETE。新 v2 缺项、额外键、false 被改为 true、摘要/授权关系不符均拒绝。

### 5.2 32 个 pool 的严格记录

pools 恰为第 4 节固定顺序的 32 项，不接受调用方新增、删减或重排。每项 exact keys 为
`pool_id,case_id,measurement_kind,byte_limit,inode_limit,status,controlled_io,last_observation,bytes_maximum,inodes_maximum,missing`。
两个 shared pool 的 case_id 为 null，其余等于原 case ID；限额必须逐项等于第 4 节。
measurement_kind 仅为非 quota 池的 `OWNED_ALLOCATION` 或七根的 `PROJECT_QUOTA`。
status 仅为 `OBSERVED,ABSENT,INCOMPLETE`。

controlled_io 恰含 `written_bytes,created_inodes`，为非负整数或 null，只表示 dispatcher 已知的
受控 I/O 累计实际写入和成功创建，不包含子进程内部的未知写入；无此类写入时经事件账核验可为零。
它不与 `st_blocks` 相加，也不替代 allocated/maxima。未取得的事件账字段为 null，并进入 missing。

last_observation、bytes_maximum 与 inodes_maximum 各为 null 或一份完整 observation。
last_observation 是该池最后一个规定边界的完整观察，不能以较早最大值冒充；observation exact keys 为
`method,boundary,boottime_ns,monotonic_ns,allocated_bytes,allocated_inodes,identities,quota,source_sha256`。
method 只为 `OWNED_ALLOCATION,PROJECT_QUOTA,VERIFIED_ABSENCE`；两个时间必须来自原 guest clock
与原窗口，bytes/inodes 为非负整数。两份 observation 分别证明该池已取得完整观察中的最大 bytes
和最大 inodes，可来自不同观察时刻；相同 observation 可在两项中重复，不能再次计费。
boundary 只为 `ADMISSION,CONTROLLED_IO,CHILD_BEFORE,CHILD_AFTER,CASE_BOUNDARY,FINALIZATION`。
source_sha256 恰为 canonical JSON（无 LF）的
`{pool_id,case_id,observation}` SHA-256，其中 observation 是删除本 source_sha256 字段后的同一记录。
该摘要只绑定实际观测汇总/身份/时间，不读取或摘要 H11 业务 payload，也不声称提供未保存的逐文件 raw 证明。

identities 是 1–16 项按 path 排序、去重的受控根/absence-parent 绑定，每项恰含
`path,role,dev,ino,fs_uuid,project_id`。role 为 `POOL_ROOT` 或 `ABSENCE_PARENT`；非 quota 或 ABSENCE_PARENT 的
project_id 为 null，只有 PROJECT_QUOTA 的 POOL_ROOT 记录实际绑定的原固定 ID；未来计划 project
仅由固定 pool 映射表达，不能把它填成 existing absence parent 的观察属性。
dev 非负、ino 正整数、fs_uuid 使用原准入格式；
path 是该池固定分类路径或已核验的最近 existing parent，且必须与 admission/准备 identity 一致。
数组覆盖该池跨目录/设备的所有分类根；扫描必须排除其它专属 pool，禁止两个 pool 计同一对象。
observation 是完整扫描的实际汇总与根身份记录，不声称它保留了每项文件的独立 raw 证明。

quota 在非 quota/absence 观察中必须为 null；PROJECT_QUOTA 时恰含
`project_id,hard_bytes,hard_inodes,used_bytes,used_inodes,enforcement_flags`，来自原 readonly quota
查询；ID/限额必须匹配对应原根，enforcement 原 checks 均通过；used 值分别等于 observation 的
allocated 值。不能从硬上限反填 used。

OBSERVED 要求 last_observation 和两个 maxima 非 null、method 匹配 measurement_kind，且必要边界全部完成观察；
bytes_maximum.allocated_bytes 不小于 last_observation.allocated_bytes，inodes 对应同理；
两种原时钟中 maxima 的时间均不得晚于 last_observation，不能接受反序、不同 boot 或刷新窗口。
ABSENT 要求三份 observation 均为 VERIFIED_ABSENCE、用量为零并有原 absence 与无创建事件证明。
INCOMPLETE 保留已成功取得的 maxima，未取得者为 null；发生后续观察失败不能让较早 maxima
成为完整全程证明。每池 missing 与顶层 missing 沿用原 missing 的三字段严格形状，准确列出
缺失阶段/字段与原因；缺失、晚返、未知不能使用默认零、限额数或预期启动数替代。

observed_maxima_sum 恰含 `bytes,inodes`。仅当 32 池全部 OBSERVED/ABSENT、各池 missing 为空且
必要观察无遗漏时，分别等于各池 bytes_maximum.allocated_bytes 与 inodes_maximum.allocated_inodes
之和；任一池不完整时两项均为 null。bytes/inodes 是独立最大观测之和，既非同一时刻实际总量，
也非全生命周期真实峰值。每池与每 case、guest 总账阈值分别检查；任何超限不得 COMPLETE。
snapshot_sha256 恰为 canonical JSON（无 LF）的
`{completion_adjustment,pools,observed_maxima_sum}` SHA-256；完整报告必须保留这份 32 行记录本体，
不能只传摘要或总数。其所有 source_sha256 及 snapshot_sha256 均由 consumer 重算，原 output/remote-result
外部摘要继续绑定整个对象。不创建新的 output member 或文件；超出原大小限制即拒绝完整报告。

### 5.3 usage 的兼容与缺失规则

v2 的 usage 保留原全部字段：只有 guest_allocated_bytes/inodes 改为上述 observed_maxima_sum
的对应值。原字段未知时允许 null，并必须进入 missing；所有其余值仍按原来源和上限核验，
不得把上限当实际值。新语义不会扩大 CPU/memory/pids 的原证明范围。

carrier_cpu_ns、carrier_memory_peak_bytes、carrier_pids_peak 仍是原绑定 carrier cgroup 在
回传前观测时已知的真实计数/峰值，不是所有业务单元峰值之和，也不声称包含回传后的未来消耗。
pids.peak 必须在原 carrier 内实际可读并核验来源；缺失就 INCOMPLETE，不填 TasksMax、pids.max
或当前 pids.current，不升级内核或修改宿主。当前工具环境或别的 CI 内核有该文件不证明 guest 有。
各 started 字段记录真实启动，预算只作拒绝线；native_children_started 仍只计原 quota native
children。正常路径实际 job unit 数不能因为上限是 15 就填 15。

remote/local COMPLETE 要求原业务、stop/EOF、身份、来源、时间与输出条件全部通过，usage 没有
未知值，resource_accounting.missing 为空、32 池完整且阈值合格，同时严格保留
full_guest_filesystem_peak_proven=false。这是 Owner 接受的新保证，不是把缺失的严格峰值证明当 PASS。

## 6. 明确不变与排除

原 candidate `4b6e4a7c403362358192086b88679e1326dcb2e1`、tree、wheel、89 项 projection、
业务与恢复语义保持冻结。权限、安全校验、user/PID/程序/路径绑定、历史义务及 retained 对象保护不放宽。
原输入输出、CPU、memory、pids、900 秒 host / 750 秒 guest、45 秒 remote reserve、15 秒 local reserve、
315 秒 case gate、150 秒 preparation、120 秒 owner 以及更早的内部 deadline 均不变、不刷新。

复用原 SSH 和既有安装环境；只允许原 A 的新批次 create-only candidate placement，不重复安装历史目录。
不清理现场、不自动重试、不重连、不改账号、sudo、mount、系统配置或 quota 数值，不添加新 F1、marker、
carrier request 或任务次数。F1 仍是原已批准的条件性单次验收，只有全部旧、新离线门禁通过后才可消费。
namespace/watchdog 与其它分支功能保持暂停，production `E3_SUPERVISION_UNVERIFIED` 不解除。

## 7. 完成条件

在本 A 得到准确 Owner B、独立 CLOSED C 后，C1–C3 只补当前 guest 准入、资源证据和核心交付整合。
当前事实不能由历史文件、预算、mock 或未知值代替；既有普通 UID 只能取实际准入结果。
源码和 package 保持清晰可读、原验证全部通过，独立审查确认新保证被准确报告，并完成原 private
package 两次独立 build/parse 后，才可按原条件进入 H01 → Q4 → H11。
完整核心验收仍要求三个 case 各自满足原语义；本修订不将资源保证调整本身当成核心 PASS。
