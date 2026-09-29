# Q2 固定本地来源：首次回执与保护阻断复核

后续状态：2026-09-29已收到[rerun3完整回执](Q2_LOCAL_SOURCE_EVIDENCE_COMPLETION_REVIEW.md)，11项匹配、4份raw返回，限定补证完成。本文保留此前各次BLOCKED及维护收件记录，不改写历史结果。

2026-09-28 +08。Owner 上传本地 Codex 返回的完整 JSON，L5 首次调用已返回。
准确实现仍为 `411a9f054d0ee85c3e82296a1fdd3a9ed4ae6239`，tree
`21773876ef321eb70fdfd9dc24cbeed881efd2ef`；包 SHA-256
`b97112107193000ae36266b7d2179167fc60dcb38ecf8d4d62ff7dcb0c2dcdda`。
R/A/C 与已登记实现复核保持。本记录不创建新 Gate、业务批次或再次现场观察授权。

## 收到与核对的事实

原文件 `q2-local-source-result-20260928.json` 为 11,592 bytes，SHA-256
`4c91c9ac5bfcc0eb9923cd43a9ea61aee3e2e2f5fbefd792f63b05146ce268ba`。
原字节、机器身份、路径、内核事实及上传截图仅私有留存；公开只登记脱敏结论和摘要。

| 项目 | 本次结果 |
| --- | --- |
| 状态 / 阶段 | `LOCAL_SOURCE_EVIDENCE_BLOCKED` / `protected_parents` |
| 原因 | `RECONCILIATION_UNPROTECTED_PATH`，ValueError，errno 为 null |
| 固定目标 | 11项均 `NOT_ATTEMPTED`；尝试、观察、匹配、raw 返回各0 |
| 普通文件实际读取 | 0 bytes |
| 内核实际读取 | 首次固定 boot 37 bytes；mountinfo、最终 boot 未到达 |
| 父目录FS / marker | 均没有观察记录；不能据空数组认定 marker 不存在 |
| 输入 / 输出 | 原输入5,514,838 bytes；报告11,592，READY58，stdout合计11,650，stderr记录0 |
| 时间 | 接收原点到报告ended约0.15655秒，观察开始到ended约0.01704秒；不是超时 |
| 权限与验收 | wrapper、remote、持久写、批次消费及所有执行/验收许可仍false |

严格解析及规范字节重编码、报告自计量、D/tree/包及六工具摘要、固定 P/M/T、11项离线
派生、boot pin、双钟和完成计数已交叉核验。该核验确认回执内部一致及与准确交付相符，
不会把 BLOCKED 改为 PASS，也不提供独立签名 stdout 或原机器身份鉴证。

退出码2、唯一一次执行且无重试、无残留进程、结果文件0600及本地工作树干净等，
来自本地 Codex 截图自报。JSON 本身不证明这些进程、文件权限和调用次数事实。
回执的 namespace 对齐仍为 `ENVIRONMENT_ASSUMPTION_NOT_PROVEN`。

## 已定位的失败条件与诊断缺口

准确 D 的共享 `q2_reconciliation_io.protected` 仅在以下合取条件不成立时发出此原因：
属主属于 root/当前普通身份，且 `mode & 0o6022 == 0`。该mask检查group/other可写位
及setuid/setgid位。ACL检查有单独的错误原因；本次不能解释为ACL错误或NOATIME不足。

观察器按host parent、control parent顺序建立完整保护链，但旧报告不记录已完成的parent
检查或失败的chain层级。故无法判定是哪一个parent、哪一级祖先或哪一个谓词失败。
K4只记录较早时点的限定事实，不能代替本次失败时刻的目录状态。不能猜测具体目录、
要求chmod/chown/sudo，或通过改变保护规则让本次通过。

这个缺口属于原A L03/L10的错误定位/可复核性要求。限定修复只保存原检查已经取得的
角色、层级和metadata；不得追加系统调用、扫描、目标、权限变更或放宽任何保护条件。
原root层保存的metadata与保护谓词各有一次fstat，诊断必须保留二者可能不同的不确定性。

## 完成度与下一入口

首次L5已返回，L6收件、准确来源及阻断结果复核完成。四份控制原文均未取得，wrapper
静态依赖审查仍缺输入；这不表示11项事实采集目标达成，更不表示完整Q2/E3完成。
历史CPUQuota批次已消费失败及INCOMPLETE保持；原单次新startup batch仍NOT ISSUED且
未消费。本次已执行的本地观察与该业务批次是不同事项。

先完成上述限定诊断修复、隔离验证和准确交付准备，不自动重试原机。再次同范围观察
须由Owner明确发起，原A无需重复批准；原A需求的“资源、停止与非目标”及实施方案
“L5交付与回执复核”明确要求此边界。任何将来修改原机权限/所有权、保护合同或范围
的方案均不能从本次诊断修复自动取得授权。

完整账单、H07首次远端监督、普通writer、历史wrapper执行来源、FS分配峰值和durability
仍未证明；Q2/Q3及production状态保持false。没有新现场观察或远程连接。

## 诊断修复准确交付

新实现 D `89c725efd61dad11b0cc9ae11c3c08a941e3111a`，tree
`15f5a0dceae0f534506abf7195562980459f3ee7`，直接承接原登记 `2a3a6af2`。
仅观察器及其定向测试改变；三共享模块、来源contract、接收器、十五份冻结文档不变。
新增最多8KiB的 `parent_protection_failure`，仍计入原报告/双流限制；诊断出错或过大时
保留原拒绝原因，不新增观察。新字段不会追溯补进旧411回执。

定向78 PASS / 1 SKIP；三本地来源组161 PASS / 1 SKIP；六相关组**236 PASS / 3 SKIP**。
新增25个用例覆盖两个parent、祖先、root二次fstat、不同拒绝条件、坏诊断及原syscall序列。
三个环境SKIP原样保留：观察器/内核真实普通身份不可取得、映射测试UID/chown不支持。
这不是全仓CI或原机阳性；先前411的普通CI结果属于旧D，本轮不挪用为新D通过。

准确私有包4,113,937 bytes，SHA-256
`e6ed13681e79492aae5ba8216996056ef03c987c901d4f23db4906989d92eeec`；启动27,191，
帧5,496,087，完整输入5,523,278 bytes。同D两次独立组包逐字一致，源码/六模块、
Git祖先、P/M/T、11对象、启动/帧roundtrip、实际长度/摘要及封禁现场IO的离线核验通过。
接收器字节未变；未重跑无关PTY或原机调用，不宣称新增现场证据或全仓CI结果。

[本轮脱敏验证索引](evidence/q2-local-source-field-20260928/verification.json)登记准确回执和修复。
上述为诊断交付准备时的状态；后续已明确发起并回传，见下节。原A无需重批，
但已完成的调用不成为下一次调用或改动原机权限的授权。

## 后续诊断回执：已定位组写权限阻断

2026-09-28 +08，Owner 上传诊断原件及本地 Codex 执行截图。截图保留的明确指令为：
“先快进到远端 main 77792665，再执行一次 89c725ef 诊断观察；失败不重试，完整 JSON
以 0600 私存到 Downloads。”它只授权该次观察；本次收件不派发下一次执行。

新原件 `q2-local-source-diagnostic-result-89c725ef.json` 为 **12,231 bytes**，SHA-256
`3a2e4a0984eb7c8d3fc3c786ed62bc2491cf317647d8dd118bed7c99f539f637`。
D/tree、包及交付字节仍与前节准确89c725ef交付一致。机器路径、身份、inode和完整
metadata只留在私有原件；公开登记如下脱敏事实。

本轮另行完成[41项独立静态核验](evidence/q2-local-source-field-20260928/diagnostic-independent-validation.json)，
全部通过且未发现不一致：严格JSON/规范字节、自计量、D/tree/包及六工具逐字绑定、
启动/帧字节roundtrip、固定P/M/T、11目标与manifest、boot pin、双钟及计数。
来源派生只解析AST字面量/JSON，未执行包或采集入口。这41项属于本轮检查，
不是截图自报34项的明细或重计；静态核验通过不改变现场BLOCKED。

| 项目 | 诊断结果 |
| --- | --- |
| 状态 / 阶段 / 原因 | `LOCAL_SOURCE_EVIDENCE_BLOCKED` / `protected_parents` / `RECONCILIATION_UNPROTECTED_PATH` |
| 失败位置 | `control_parent`，`component_index=3`，`component_kind=ancestor`；root索引为0 |
| 失败谓词 | 仅 `FORBIDDEN_MODE_BITS`；保留属主在原允许集合内 |
| 保留权限 | 目录 `0775`；与原 `06022` mask 相交仅 `00020`，即group-write |
| metadata来源 | 已打开fd的初始化保留值；`metadata_is_exact_check_input=true`，未追加文件系统观察 |
| 目标与原文 | 11项全部 `NOT_ATTEMPTED`；attempted/observed/matched/raw均0 |
| 实际读取 | 普通文件0 bytes；固定初始boot37 bytes；marker、parent FS和最终复检未到达 |
| 输出 | 报告12,231 bytes，READY58，stdout合计12,289；报告记载stderr0 |
| 权限与验收 | wrapper、remote、持久写、消费及所有执行/验收许可仍false |

该非root层的保留metadata正是失败保护谓词的输入，因此能定位该次拒绝为group-write；
不能倒填第一次411回执的具体原因。失败发生在该组件后续name↔fd重检及全链稳定核验
之前，故不证明路径从那时至今一直绑定同一inode或权限未变，也不证明后续祖先、ACL、
NOATIME、原文匹配或文件系统资格会通过。将该位去除本身不能保证完整观察成功。

按源码顺序可知host_parent的先行检查已返回，control_parent随后失败；JSON未保留
前者完整链的metadata，不能把此推断升级为独立父目录资格证据。空marker/FS数组表示
未观察，不表示不存在。Q2业务startup batch仍NOT ISSUED且未消费；本地诊断不是该批次。

退出码2、唯一一次诊断、无重试、文件0600、PTY及进程清理、现场HEAD为77792665和
工作树干净来自本地Codex截图自报，不能由JSON独立证明。namespace对齐仍为环境假设。

## 首轮诊断后的维护候选（历史）

现有A的只读补证不授权修改原机目录权限。当前可以继续做回执／准确源码的离线复核
并形成修复候选；不能自动chmod/chown、递归改权限、移动来源、放宽保护规则或重跑。

优先候选是对**这一处祖先目录**做最小环境整改：先确认最新身份、mode、ACL、挂载与
该目录的实际组共享／写入依赖；若确认组写权限无需保留，再提出仅移除该目录group-write
位的明确变更。按本次保留值其预期为0775→0755，保留属主、组、其它权限和所有子项。
这仍是候选，不是已授权命令。它涉及共享祖先目录，影响评估必须先于变更；事实不符即停。
整改后再按明确发起的同范围一次观察重新验证，不能沿用本次metadata作通过证据。

若组共享必须保留，则该候选不适用；另行形成来源布局或保护合同方案，并按原R复审。
直接复制四份文件到新位置不能证明原执行来源，也不会自动满足固定P/M/T的来源绑定。
本轮不关闭任何新的环境整改范围，不宣称wrapper、H07、完整账单或Q2验收完成。

## 后续 rerun1 回执：推进至下一祖先，仍为 BLOCKED

2026-09-28 +08，Owner再次上传完整原件与本地Codex截图。新原件
`q2-local-source-diagnostic-result-89c725ef-rerun1.json` 为 **12,236 bytes**，SHA-256
`b6754ed53bf7e5d0b4a3b058fe128f29b3b80e83e1004ad061d13bf2a3b87b91`。
准确D/tree/包、六工具、P/M/T、11对象与目标manifest均与上次交付相同。
这是第三份收到的本地观察回执，不覆盖前两份结果，也不是Q2业务窗口的消费记录。

[本轮41项独立静态核验](evidence/q2-local-source-field-20260928/diagnostic-rerun1-independent-validation.json)
全部通过、无不一致；只做JSON/AST/字节核对，未执行包或任何现场入口。
截图自报的67/67不等同于本轮41项，其明细未独立取得。

| 项目 | rerun1结果 |
| --- | --- |
| 状态 / 阶段 / 原因 | `LOCAL_SOURCE_EVIDENCE_BLOCKED` / `protected_parents` / `RECONCILIATION_UNPROTECTED_PATH` |
| 新失败位置 | `control_parent`，`component_index=4`，`component_kind=ancestor`（root=0） |
| 失败谓词 | 属主允许；目录mode `0775` 与 `06022` 相交仅 `00020`，仅group-write |
| 诊断 | 616 bytes；保留值为该次失败fd检查的准确输入，未追加观察 |
| 读取 | 11项全部未尝试，raw 0、普通文件0 bytes；初始boot37 bytes |
| 输出 | JSON12,236，READY58，报告记载stdout12,294、stderr0 |
| 时间 | receiver至ended约71.449787秒；observer开始至ended约0.017191秒，原140/300秒界限均满足 |
| 后续步骤 | marker、父目录FS、11文件及最终复检未到达；所有执行/消费/验收许可仍false |

receiver至observer开始约71.432596秒；回执不能区分此段具体耗在粘贴、接收或校验的哪一步。
不得将其全部标为观察耗时，也不得把本次正常时限解释成全部现场流程通过。

截图自报：前一index=3祖先已由0775改为0755，属主/组保持、无额外ACL；随后在
“如需再次诊断观察，请另行明确授权”的上下文中，Owner回复“另行明确授权”。
本地Codex报告本次只执行一次、退出2、无自动重试、临时会话已清理、结果0600，
现场HEAD仍77792665且工作树干净，新失败目录未修改。这些是截图自报，不是JSON的
独立进程／维护鉴证；本段不补造未展示的维护授权全文。

按准确源码顺序，本次到达index=4意味着index=3的初始保护及紧接的name↔fd检查
已返回。这是源码顺序推断；JSON没有保留index=3的新mode，不能单靠它证明0755。
index=4失败后其name↔fd和控制目录全链稳定／ACL核验未完成；后续层级仍未知。
三份回执各自保持原时点与结论，不能互相拼成一次完整稳定观察或追溯改写原失败。

## rerun1之后提出的维护候选：先核对完整固定目录链

不再以“修一层、跑一次完整诊断”作为下一步。先由本地Codex在独立主机维护检查中，
从私有固定来源提取两个parent，去重列出它们至root的**8个确定目录节点**，一次性
只读记录各节点的类型、device/inode、符号链接／路径解析情况、属主/组、mode、access/default ACL、
挂载属性及已知组共享写入依赖。范围限这8个明确节点；不递归枚举、不读取11目标
内容、不运行wrapper、远端、marker或原诊断，不借此修改原A的观察器或证据准入。
遇符号链接、对象替换、无法读取或不稳定状态，应记录UNKNOWN，不跟随链接或改查
替代路径。仅在对象仍可安全定位时继续其它明确节点的维护盘点；collector仍按原合同
遇首个失败就停止，不能改成继续读取来源。

目录用途和共享依赖若无法从已有资料及有限只读检查确认，应保留UNKNOWN；不能仅凭
当前未见写进程就断言没有共享。维护检查输出只用于环境差额与变更影响评估，不能当作
L5来源读取、原子快照、完整路径资格或Q2验收证据；维护前仍需重新核对相关对象身份。

根据完整差额清单再形成一次可审阅的精确维护方案：只列需调整的具体目录及每项前后
权限和影响，不把对index=3的既有维护外推为其它节点的修改授权，不递归chmod/chown、
不清除ACL、不改系统祖先或挂载策略。若共享必须保留，则另行设计来源采用方案。
维护获明确授权并完成后，另行明确发起一次原scope观察；遇新事实先返回，不自动重试。
原A无需重复批准，原机维护也不能从上传回执或静态核验通过自动获得授权。

## 后续 rerun2 回执：推进至首个固定文件

2026-09-28 +08，Owner上传第四份本地观察完整回执及两张本地Codex截图。
`q2-local-source-diagnostic-result-89c725ef-rerun2.json` 为 **17,522 bytes**，SHA-256
`437cea426cd19e8026ed7646457674516360bb00c2cea930eb5ad128fdbc5221`。
准确D仍为`89c725efd61dad11b0cc9ae11c3c08a941e3111a`，tree/package/六工具/P/M/T/
目标manifest与前两份诊断交付相同。四份现场回执分别保留，不覆盖或拼接成同刻快照。

| 项目 | rerun2结果 |
| --- | --- |
| 状态 / 阶段 / 原因 | `LOCAL_SOURCE_EVIDENCE_BLOCKED` / `fixed_objects` / `RECONCILIATION_UNPROTECTED_PATH` |
| 首个阻断对象 | M01；保留的常规文件mode `0664`与`06022`相交仅`00020`（group-write）；属主符合允许集合 |
| 元数据来源 | 相对已持有parent fd的no-follow `os.stat`，尚未打开文件fd；不是打开后fstat或已完成文件稳定性检查 |
| 完成度 | 尝试1、观察0、匹配0、raw返回0；其余10项`NOT_ATTEMPTED` |
| 内容读取 | 普通文件0 bytes；固定kernel读取5,618 bytes（boot37、mountinfo5,581） |
| 新增有限事实 | marker前检`ABSENT_AT_OBSERVATION`；两个固定父目录的metadata、挂载、statvfs和flags观察已返回 |
| 输出 | JSON17,522，READY58，回执记载stdout17,580、stderr0 |
| 时间 | receiver至ended约103.828024秒；observer约0.017687秒，原140/300秒界限均满足 |
| 未到达 | M01打开/文件ACL/内容读取/稳定完成、其余10目标、最终parent/marker/boot复检 |

按准确源码顺序，`fixed_objects`及M01的`before`说明两条父链的初始保护、名称↔fd、
全链ACL检查、marker前检和两个父目录FS观察已经返回；不证明目录永久合格，亦不
证明11文件的资格。本轮未收到独立8节点维护盘点报告或完整目录维护前后明细，不能
据此补造哪一步实施过何种chmod/ACL操作。

M01的类型/单链接元数据虽已保留，但`io.protected`在其第一个属主/mode谓词即失败，
不能记为后续文件type/device/alias/ACL检查已经执行通过。该失败前未打开目标文件
内容fd；普通读取0与完成计数相符。初始marker缺席不是最终缺席证明；FS的可用容量
及ext4等观察不是完整账单、分配峰值、durability或Q2资格。

本轮独立静态核验47项全部通过、无内部矛盾，记录见
[diagnostic-rerun2-independent-validation.json](evidence/q2-local-source-field-20260928/diagnostic-rerun2-independent-validation.json)。
这类核验验证回执与准确来源的绑定及一致性，不会把BLOCKED改为PASS；截图自报的
72/72明细未取得，不以独立核验冒充其复现。mountinfo原文未返回，其摘要及最长匹配
选择不能独立重算；仅核对返回字段和设备/容量计算一致。namespace仍为环境假设未证明。
receiver至observer开始约103.810337秒，回执不区分接收、粘贴和验证各自耗时。

截图保留Owner明确回复“授权再执行一次 89c725ef 诊断观察；失败不重试，完整 JSON
以 0600 私存到 Downloads。”本地Codex自报唯一一次、退出2、无重试、旧回执未覆盖、
终端已清除、仓库干净、回执0600。这些过程/文件权限是截图自报，不是独立主机鉴证。
回执报告的wrapper/远端/持久化/窗口消费及执行、Q2/Q3/生产许可均false；本地诊断
不消费另一个仍未派发的Q2业务startup batch。

## rerun2收件时的下一步（历史）：11个固定文件的完整维护差额

后续交接已整理为[固定文件维护盘点](Q2_FIXED_OBJECT_METADATA_HANDOFF.md)：原机
本地Codex仅盘点11个准确文件并复检必要8节点父链，记录元数据、ACL及共享依赖，
形成精确最小维护方案。本次云端复核未派发主机任务，未修改权限或再次观察。

截图中“0644/0600通过”只能解释为可能排除本项mode阻断，不是完整读取资格。
`0664→0644`保留属主读写，同时移除组写，不能声称对所有用途无影响；统一0600
还会改变其他人的读取权限。不能以“全部可读可写”解决禁止组/其他写入的来源保护。
维护及后续一次观察待具体方案和明确授权，原A不重复批准；范围内不逐文件反复询问。

## 2026-09-29维护原件收件更新

两份原件现已收到并完成[跨报告静态复核](Q2_FIXED_OBJECT_MAINTENANCE_REVIEW.md)：11文件及
8目录盘点完整，六项0664→0644的对象/前值/身份/大小一致；执行方报告维护完成，没有运行诊断。
共享依赖UNKNOWN及ctime变化原样保留，内容不变未升级为独立字节证明。旧BLOCKED不改写；
[准确单次观察交接](Q2_POST_MAINTENANCE_OBSERVATION_HANDOFF.md)已准备，尚未发起。无需再次盘点或改权。
