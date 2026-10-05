# locale 修复后单次核心验收架构

Authority：Owner；状态 **PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-POST-LOCALE-ACCEPTANCE-v1`，L1–L3；固定版本、来源、对象、资源与边界以[需求](REQUIREMENTS.md)为准。

## 组件与最小变更

复用原 host builder/独立 parser、entry、三 field 文件、原安装器/harness、六文件 finalizer。
不增加通用历史数组、重试平台、独立现场 helper、取证器或系统配置。
只把两个固定旧 profile 扩为恰三个，绑定一个只含摘要的固定诊断保留记录，再接新 05c。
新范围和 locale 范围的准确 R/A/B/C、祖先关系及源码由 freezer 校验；旧授权链仍保留。
wire scope/manifest.amendment 仍指原核心合同；package/v3、approved-input 顶层/v1、HELLO/BIND、remote-result/v2 及原 field 集合不换义。
新 scope 是准确授权及 UUID seed，不是另一个业务协议。

| 组件 | 新范围内的责任 |
| --- | --- |
| contract/freezer | 固定新旧映射、三历史 source profile、诊断来源、locale 及新批准链；阻断未知版本 |
| prior reader/approved-inputs | 十五核心原件的严格 raw profile；四诊断原件仅本地校验、产生固定摘要描述 |
| host entry/capture | 一次 260 MiB/72 条件、六名 absence、原时钟、唯一 marker/request |
| dispatcher | 三旧各 A/B 静止、逐设备三承诺、原当前准入与 H01→Q4→H11 |
| 独立 host consumer/finalizer | 重算三旧事实、诊断摘要和容量绑定，保留 UNKNOWN，消费原真实结果并封存 |

主源码 `_admit_sshd_source`、`_admit_text`、`_require` 与修复 D 逐字相同；五项有效 sshd 谓词及 sudo/key/rc 检查不变。
已保存配置不再文法重放；现场在唯一新请求内按原流程读取当前配置/查询有效策略，这是新核心准入而非额外诊断采集。
loader 保持原 bytes；bootstrap 仅替换等长 session/carrier 身份，不能加诊断执行路径；新增接线放现有 host 模块/dispatcher。
field cap 仍 8192/49152/524288 B；基线 2160/49031/449522 B，bootstrap 仅余 121 B。不能提高 cap 或删校验解决尺寸问题。

## 三旧核心来源与版本演进

`reconciliation` 显式升为 `local-hand-q2-core-reconciliation/v4`：
exact keys 为 `schema,state,applied,released_bytes,released_inodes,record_basenames,prior_core_attempts,prior_diagnostic_capture`。
原 state、空 applied、两项零 release、原五 seal basename 保持；prior 列表固定顺序 `[03a,05a,05b]`、恰三项，不接受任意长度或 session。
每项原 `local-hand-q2-core-prior-attempt/v2` 的 exact keys、五 raw files/base64 与消费/传输/receipt 关联保持。
只追加需求固定 05b profile；其单 HELLO、非零 BIND、wait 3、24 B 错误不能冒用另两项的失败模式。
三个旧 remote-result 均须确实缺失；任一存在/不明停止。旧记录不迁移、重写或重跑 finalizer。

本地十九原件统一沿 held anchor/no-follow/no-atime、0600 single-link、owner/device、fd/name 完整稳定性校验，禁止跨对象 inode alias。
前三批十五件进入原 approved-input 的 raw preimage；四诊断原件不进入包。原件不可搬移来凑 anchor 条件。
同一新 live 窗口重验；历史报告、路径已知和散列常量不是当前原件存在或保护证明。
每旧 HELLO 必须按其原 D 的 loader/bootstrap profile 验证，boot/InvocationID/cgroup 来自原 bytes；旧 writer 不要求仍存活，裸旧 PID 也不成为身份。

05b 冻结代码审查须核对 `_admit_collect_policies → _admit_sshd_source` 拒绝在 helper/安装/业务前，且没有继续分支。
只有原 bytes、错误、transport 和准确旧 source 一起支持该有限前提；当前修复函数或已保存当前快照不能反向证明历史 05b 触发行或远端退出。
若此前提不成立，不发行、不扩展扫描范围或改用宽松 profile。

`historical_capacity_obligations` 升为 `local-hand-q2-core-historical-capacity-obligations/v4`，exact keys 与原 v3 相同；
仅固定 `prior_commitments` 改为与三 prior 一一对应的三项，其他历史 rows/totals/source horizon 不变。
每项仍准确 `scope,session_id,source_attempt_sha256,logical_bytes,logical_inodes,cpu_seconds,host_capture_bytes,host_capture_inodes,released_or_refunded`，值为需求每批全额及 false。
source 摘要是对应 prior/v2 的 canonical/no-LF SHA-256；不能复用相邻项或少计第三项。
每旧 32 池按原 parent-role 映射逐实际 `(dev,fs_uuid)` 计完整承诺，同池同设备去重、跨设备重复，三 case headroom 各计 state 设备；全部更早义务先算，再加三旧及新批。

## 诊断只保留来源与未知边界

新增固定 `local-hand-q2-core-diagnostic-retention/v1`，exact keys：
`schema,scope,session_id,implementation,files,reader_state,remote_supervision_proven,remote_exit,management_usage,reader_cpu_seconds,reader_address_space_bytes,host_capture_bytes,host_capture_inodes,released_or_refunded`。
scope/session/D/tree 和四个文件描述均固定为需求引用的诊断；files 是 ASCII basename 排序四项，each exact `basename,bytes,sha256`，没有 raw/base64/path/argv 扩展。
固定状态 `READER_REPORTED_COMPLETE`、监督 false、remote_exit/management_usage 为 `UNKNOWN`，reader 5/134217728、host 4194304/8、refund false。
本地检查原 marker、receipt 与两流的既有结构、摘要、成功/EOF/deadline 关联；只校验 stdout 的固定长度/hash，不再解析 snapshot 或调用诊断 runner。
guest 和独立 consumer 对该固定摘要对象作严格字段/常量校验，不假装自己读取过本地诊断原文。
诊断不增加业务 quota/storage 池；管理祖先和日志的未量化部分保持未知，不记零，不纳入有限核心 carrier 上界。
该接受是本新 A 的明确治理边界，不是把诊断较窄信任复用成核心准入 PASS；不取消任何当前检查或允许忽视活动残留。

## 一个 carrier 内的六次固定观察

原 policy/program/guest 检查后：03a A → 05a A → 05b A → 原 filesystem/quota/absence/capacity/managers → 03a B → 05a B → 05b B。
同一双钟窗口、所有旧 boot 一致、每旧精确 unit/cgroup；沿用原十 SHOW 属性和每次原 5s/2 CPU-s/32768 B。
槽为固定六次，先消费槽再调用；第一次失败即停止，不能轮询、重入、增加第七次 SHOW、stop/kill/reset-failed 或另发连接。
各旧分别保持 LOADED_TERMINAL / COLLECTED_ABSENT 判据和 A/B 分支/inode 一致；不能复制其他旧批的观察。
三个 observer 同时持有父/对象 fd 到全部 B、finish 和最终 name/parent 复核，全部通过才安装。
已核对的静止不是对未来永远静止的互斥保证；完整历史退出和 usage 不因此转为已知。
session.admission 原 v2/字段集合保持，`prior_core_attempts` 固定三项原 quiescence/v1，逐项绑定新 prior/v2 摘要；host 独立重新验证数量、顺序和事实。
四核心 carrier 的 4 GiB/512 是其原单 unit 配置的条件上界，不覆盖诊断或管理祖先，不采集整机可用内存；资源失败沿原停止路径。

## Host 容量与结果

仅原 pre-marker 点、held anchor/writer、原双钟内一次 fstatvfs，要求 272629760 B/72；不重采容量寻求通过。
`local-hand-q2-core-host-capacity-condition/v3` 沿原 v2 exact keys，加 `diagnostic_retention_sha256`。
prior_attempts_sha256 绑定有序三 prior，诊断摘要绑定上述完整固定对象；scope/session 为本新范围/05c，implementation 绑定最终准确 D/tree。
known_commitments 固定五行顺序 `[03a,05a,05b,lhqsshd-20261005a,05c]`；每核心 67108864/16，诊断 4194304/8；required 恰等于总和。
仍由原 live consumer 验证来源/clock/dev/算术及 finalizer 前后同值，不增加第七个持久文件，不改变 receipt/capture_accounting schema。
earlier_host_obligations UNKNOWN/null、complete_host_admission_proven/exclusive_reservation_proven false、released 0 保持。
诊断保留缺失、被当成 0、旧 192/196 MiB 条件混入、顺序/摘要串线、时钟晚返回均拒绝。

源码/包版本以 C 后准确 Git blob 和原 freeze 链演进；不更新旧已发包，只有 L2 后独立 release 登记可放行准确 digest。
H01 PASS → Q4 PASS → H11，自身 origin ledger/handle/unit 恢复、不刷新 deadline；原完整结果、退出、usage 和六文件持久化语义保持。
失败回退只有关闭发行并保留事实/对象，不能换旧合同、删 marker、退款或生成下一次请求。
取舍是复用已验证窄修复与现有执行链，不修改 guest 配置、扩展诊断或恢复支线；当前策略、容量、静止未知留给获批唯一请求内的原准入，失败接受为终点。
