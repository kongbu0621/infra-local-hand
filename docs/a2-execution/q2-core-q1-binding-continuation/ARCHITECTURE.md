# 接回已有 Q1 服务及父域，沿原链完成维护和核心执行

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-Q1-BINDING-CONTINUATION-v1` / QI1–QI3，依[需求](REQUIREMENTS.md)。
基线为已完成 C10 核对的 `5d8e5db79ebd137716145a60e71e85fe0252fe1d`。
复用现有协调器、受保护输入读取、GuestInventory 和核心消费者；只修已确认的
一个 Q1 服务及其父 slice 漏声明，并接续一个新维护窗口和原未发出的核心批次。

## 固定原件进入现有输入冻结

`q2_journal_growth.freeze_growth_inputs` 增加一个固定角色的 Q1 来源输入组；本地
调用者显式提供已有原件位置及此前私有索引，不搜索目录、归档或 guest。角色仅含
C10 原报告、当前单单元读取的 prepared/返回记录和 stdout/stderr、其原私有摘要索引。
已经生成的声明候选只用于比较，不能成为绕过原件的权威输入，也不接受任意 unit 列表。

C10 是已找到的直接 report.json，固定 9632 B / SHA-256
`0183b985fdab6a755e96c916617484e274f38e284e575dcb298349d44ccba1e9`。
解释 C10 的 C11 固定 20208 B / SHA-256
`a5265e00222eb9cea4a9675627650c4a51adeac69c6383732a3aac0e3a3b8deb`；
`growth_sources` 核对候选 commit 中 `q2_host_export.py` 的准确 blob 与该 pin，
不执行 exporter，也不将它加入远端加载器或另建 reader。固定 report 由现有严格 JSON
解析器读取；重键、非法数字、结构/深度/数量超限都拒绝。

当前读取的 pins 必须来自该次已经留存的 prepared、返回记录和原私有索引，交叉核对
准确请求名称、原 08d 引用、两流长度/摘要、退出码 0、完整 EOF、无截断及空 stderr。
原索引自身的准确引用与摘要在 QI1 的私有来源采用记录中冻结，先核对旧留存关系，再生成
新候选；不得当场为任意文件生成一套自洽 pins 并称为原来源。缺项、冲突或对象不可用即
停止输入冻结，不发现场命令。云端没有这些私有值，文档不填占位值冒充真实 pin。

沿用 `prior.Inputs.read` / 已有受保护目录读取：O_NOFOLLOW、O_NOATIME、普通文件、
权限/owner、长度/摘要、held FD 与命名对象身份和元数据复核。结构记录各限 65536 B，
原 stdout/stderr 各限原 1 MiB，空 stderr 仍核对原 pin；既有累计内存/读取/时限限制
不提高。输入组与已有来源跨角色 inode 去重，同 FD 在预检及消费前复核；新旧调用者
必须冻结相同来源，不能只校验候选 JSON 的外壳。实际路径、票据、单元名和原始流留私有。

## 在内存中从原始响应重算唯一声明

复用 `GuestInventory.show_many` 的原解析器，ctl 只返回上述已固定 stdout，绝不构造
远端查询。保留原 30 项、全部 Exec 成员及别名规则，实际 Id 必须等于已固定请求名。
只接受唯一、无歧义的 ExecStart Q1 worker 调用，按照原 `unit_command` 的固定七参数
形状识别 python、`-I`、`-B`、worker、runtime 路径、runtime SHA、规范 ticket。
不做通用 shell/脚本解释，不执行字符串，不通过分词猜测带转义或额外参数的命令。
worker/runtime 必须仍是原命中保护根下的严格子路径；同配置 C10 的 OBSERVED
program_python/program_worker 路径与这两个程序参数一致。多调用、歧义、缺字段或
不相等均拒绝，不能只在整串中搜一个 hash 或 base64 后采用。

C10 必须为 `local-hand-q2-host-export/v1`、
`scope=READ_ONLY_SELECTED_Q1_HOST_HANDOFF`、`status=EXPORTED`、
`source_config_status=Q1_EVIDENCE_ONLY`。original_config/revision_config 各唯一，
均 OBSERVED；仅有 original_config 的 `facts.files['runtime.json']` 等于捕获的
runtime SHA。该行必须为 Q1_CONFIG_BYTES_LINKED_ONLY，取其同一行 manifest SHA。
不跨配置拼接；保留 independent_authority_proven=false、q2_reusable_allocation=false。
按 C11 的字段/类型核对顶层 q1_history_reassessed、q2_accepted、q3_accepted、
production_supported、complete_q1_domain_inventory、quota_observed、
current_capacity_is_new_budget、fixture_generated 均为 false，
independent_supervision_required 为 true；q2_input_groups 仍为原 NOT_DELIVERED。

票据须符合原 ticket v1 的准确字段集合、类型、格式和规范 base64/紧凑 JSON 编码，
整数不接受 bool，issued_ns/deadline_ns 的内部先后关系有效。用同条 manifest SHA
和票据 slot_ref、generation、request_id、allocation_digest、execution_id、phase，
严格按原七项数组顺序和无换行紧凑 JSON 作 SHA-256。得到的完整 `lhq-<摘要>.service`
必须同时等于实际 Id 和 prepared 请求名。不反推 hash，不造 Manifest 或 intent，
不把已过期历史票据重新用作执行权限。

对应 original_query_parent、original_source_head、original_current_boot 及
declared_guest 均唯一 OBSERVED；config source_commit 等于同条 declared_commit，
detached_head 相等，source_bytes_verified/clean_tree_verified 仍为 false；
config boot 等于报告 guest boot 和冻结 original_boot。
parent 严格为 `/sys/fs/cgroup/<query_slice>`，slice 符合
`lhq[a-z0-9]{1,40}\.slice`。只去固定前缀得到逻辑父路径，保留 q2_parent_admitted=false。
这些是历史配置/名称关联；source-head 不提升为完整源码验证，C10 不能补齐 Manifest
的全部 slot/deadline 或 intent 验证，也不能证明当前 cgroup、持续静止或 Q2 配额可用。

## 只合并三个准确增量，保留全部实际准入

原 `_growth_inventory` 先按原来源重建；本次固定基线必须仍为 18 个 expected_units、
6 个 domain_units、6 个 domain_cgroups，原保护根/essential 集合不变。纯合并步骤只添加：

| 清单 | 唯一增量 | 结果数量 |
| --- | --- | ---: |
| expected_units | `{name: 准确服务名, control_group: 逻辑父路径 + '/' + 服务名}` | 19 |
| domain_units | `{name: 准确父slice, manager: 'system', control_group: 逻辑父路径}` | 7 |
| domain_cgroups | 同一逻辑父路径 | 7 |

任何已存在名称、同名不同 manager/path、路径别名/冲突或不符合准确增量都拒绝；
不覆盖原行、不填 null、不放行名称前缀。按原规范顺序排序，保持原条目上限和描述符
大小上限。将来源原件 pins、选中的 C10 行、runtime/manifest SHA、票据/捕获摘要、
准确三项增量及其摘要纳入 `source_binding`；重算 inventory/source binding 摘要。
私有来源记录声明范围仅为这次配置关联和前向 inventory 声明，保留上述未证明项。

`growth_descriptor` 已携带这三张表及 source_binding_sha256，不增字段。
GuestInventory 的保护根匹配、quiet、启动边、域/cgroup、当前 writer 和持久数据检查
原样执行。实际 service 当前 ControlGroup 为空不能替代非 null 声明；父域与服务在
维护时仍由原检查验证，当前读取通过纯属性检查不能直接作为 GUEST_QUIET。
不停止/重置服务，不安装，不降低容量或时间准入，不新增第二条单元读取。

## 一个新窗口及完整消费者

新 session 固定 `lhqjgrow-20261008e`。维护 manifest/receipt 为 v9，短预检 v8，
仍用准确新 R/A/C/D、原钟、nonce、manifest 摘要及完整 resume 的摘要；短预检不超过
4096 B。guest descriptor/report 继续 v2，仅准确 session 改为 08e；清单结构及
guest_startup_assurance 四字段语义不变，所有原报告检查保留。

七旧历史顺序 06a→07a→07b→08a→08b→08c→08d，旧字节、授权及嵌套 resume 不改。
08d 按原 manifest/receipt v8、descriptor/report v2、GS 覆盖对象核验，准确 A/C/D
为 GS A `7ea9aed6a4f8be6d6fee0ee549e1e02378f32672`、C
`001bd4f7baedf115ce67feba87a21d8e259c8d1d`、D
`341796561a6aaa6f95779f438b57d958a1fd5954`。历史解析明确区分旧 v1 与 08d v2，
不能将全部旧报告交给当前 08e 描述符，或给旧记录自动补覆盖对象。
08d 五原件 pins 仅从原件和既有私有索引一致核对取得；保留动作空、
PRE_QUIESCENCE/GROWTH_UNDECLARED_BUSINESS_UNIT、一次 SSH、消费与 UNKNOWN。
预检/消费前同 FD 复核/核心读取覆盖旧 35 件、28 个旧后续缺席名及新九名。

维护成功原件由 `build_journal_transition` 核对 manifest.inputs 与重新冻结的
source_binding 完全一致、inventory 摘要相等、descriptor 逐项清单相等，再验证全部
pre/post、状态链、原件、容量和重启关系。传入核心的 journal_frozen 必须由同一受保护
原件组重建并再次运行绑定变换，不能信任外部给出的已修改 inventory 字典。
transition 为 v8，reconciliation/historical-capacity-obligations 为 v12，
host-capacity-condition 为 v11；host 和独立 guest 消费者一起更新。独立 guest 只验证
host 完整核验后的投影与摘要，不声称它重新读过私有 C10/当前响应。

八代完整维护义务为 10368 MiB/2960 inodes/960 nominal CPU seconds；加原核心
为 10432 MiB/2976 inodes（10938744832 bytes）。旧消费和 UNKNOWN 不释放义务。
core contract/freezer/approved-input、package/entry、dispatcher/bootstrap 和返回
验证者必须在 QI2 前全部完成接线；dispatcher 摘要从真实字节更新，旧 pin 保留。
每个 host/guest 源 98304 B、原加载/包/捕获限制及全部执行时限不提高。

QI2 仍只有一次维护、原两固定 SSH 阶段和原状态链；失败停止，不重试、补采、清理或
自动恢复。仅完整验证成功后才构造并发出原 `lhqcore-20261007a` 核心包，依次 H01→Q4→H11。
新业务启动前的实际准入仍可能失败，声明修复不是核心成功证明。R→A→Owner B→独立 C→D
顺序保留；本架构不批准新窗口或来源采用，也不增设子步骤审批或旁路功能。
