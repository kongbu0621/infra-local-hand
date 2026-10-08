# Core execution progress and local Codex handoff — 2026-10-08

## 当前：GS1 完成，唯一 08d 在未声明业务单元检查停止

Owner 已批准 A `7ea9aed6a4f8be6d6fee0ee549e1e02378f32672`，准确 B 与独立 C
`001bd4f7baedf115ce67feba87a21d8e259c8d1d` 先于实现登记。候选
`341796561a6aaa6f95779f438b57d958a1fd5954` 完成两侧实现、发布、首次 CI 3/3、
独立安装、固定原件/来源/大小核对和冻结。Linux 7133 passed / 89 skipped，独立安装
94 checks / 292 commands。早期本地与 Windows CI 失败均保留，未作为现场候选执行。

[准确现场返回](../Q2_CORE_GUEST_STARTUP_CONTINUATION_FIELD_20261008.md)：GS2 普通预检通过，
同窗 execute 创建 marker 并发一次 SSH 后停止；已有 guest v2 报告为
`PRE_QUIESCENCE / GROWTH_UNDECLARED_BUSINESS_UNIT`，actions_started 为空。
无关机令牌、备份、扩容或重启；remote_exit 仍 UNKNOWN，journal 扩容未完成。
未追加现场查询或改变检查，GS3/H01/Q4/H11 均 NOT_RUN，没有真实核心包。

私有 gate 已终止为 GS2_CONSUMED_FAILED_GS3_NOT_RUN。七代维护消费、完整费用和所有
旧原件/UNKNOWN 保持。获批旧 08c 五件最小索引已公开，新 08d 原文及索引保持私有。
不重放 caller、不重试、不补采、不清理、不恢复、不扩展支线，也不单独发行条件核心批。

### 当前可做的下一步

已补 `GROWTH_UNDECLARED_BUSINESS_UNIT` 同次诊断：属性、根序号/摘要、内容摘要/字节位置，
模板物理行号；无新查询，无条件放宽。相关本地回归 **1374 passed / 5 skipped**。
它不能补回 08d 当时未保存的 show 属性。见[具体字段与处理顺序](../Q2_CORE_GUEST_STARTUP_CONTINUATION_REVIEW_20261008.md#未声明业务引用的同次诊断补齐)。
本地 Codex 先对照已保留 stderr 的 manager/unit、原 manifest 的声明/保护根和已有
配置原件，定位漏声明或相似子串的具体证据，再作针对性修复。原件不足时只列准确缺项，
不猜白名单、不为日志盲跑下一窗口。当前只完成诊断补齐，现场阻断仍未解决。

以下提案与“下一步”均为历史记录，不构成新执行入口或待重复审批事项。


## 先前提案：08c保持失败；提出删除通用间接启动类别阻断

只读审查确认当前代码会有意拒绝cron等类别；既有准确scheduler回归 **1 passed**。
这不是上一轮Exec解析修复未生效的证据，也不能据此断言有定时任务在写业务数据。
不再向主线加入cron队列/脚本穷尽分析。已发布三文档A
`7ea9aed6a4f8be6d6fee0ee549e1e02378f32672`，scope
`LH-Q2-CORE-GUEST-STARTUP-CONTINUATION-v1` / GS1–GS3，**PROPOSED / OPEN**。

[方案](../q2-core-guest-startup-continuation/REQUIREMENTS.md)只删除两个入口的通用类别
阻断及其专用模板编码判定；以明确的guest管理前提承接该部分，准确标记NOT_PERFORMED。
保留直接业务路径、声明unit/启动边、domain/cgroup、当前writer、持久证据和目标维护保护。
独立审查核对三层范围、双方覆盖绑定、完整历史和七代费用；没有新源码/配置/caller。

下一步只有Owner对准确A及覆盖缩减作一次明确决定。若批准，先独立C，再完整实现两侧、
静态核验/验证/发布/冻结，一次08d维护成功后接原H01→Q4→H11；范围内不逐项重新审批。
08c和所有旧窗口仍已消费，不能从本提案推导重试或现场权限。实际是否满足guest前提须
本地执行者基于既有管理交接确认，云端不替用户证明；相反证据或未知即停止。

## 先前现场：EX1完成，唯一08c在间接启动入口检查停止

[准确返回](../Q2_CORE_EXEC_CONTINUATION_FIELD_20261008.md)：Owner批准A
`5b14123206ced8117374d3fd2ef84b9f38784db3` 的EX1–EX3；准确B及独立C
`987c77f6eb16e7ca41d8b1d4ccd7f89faf418d32` 先于直接实现子提交
`064bdd614db4224c8c7e9d3b011af90622c11066`。D完成发布、准确首次CI 3/3、独立安装、
静态输入/原件核验及冻结。Linux6960 passed/89 skipped，独立安装94 checks/292 commands。
完整五代历史保留，708 B短预检样本低于原4096 B上限，全部原准入和期限保持。

EX2 `lhqjgrow-20261008c` 普通预检通过，同窗execute创建marker、发一次SSH后停止。
已有guest报告为 `PRE_QUIESCENCE / GROWTH_INDIRECT_STARTUP_UNVERIFIED`，指向定时任务类
间接启动入口；并不证明有任务正在写入镜像。动作空，无关机token，未备份、扩容或重启。
没有追加查询或修改检查，remote_exit保持UNKNOWN。EX2为CONSUMED/FAILED；EX3及
H01/Q4/H11均NOT_RUN，未生成或发送真实核心包。

六代消费、完整费用、原件及UNKNOWN保持；本次五件原件和索引私有，获批旧08b最小索引
已公开。私有gate终止，不能重放任何caller或单独执行条件核心批。没有重试、补采、清理、
恢复或扩展支线，本轮不自动申请另一窗口。以下“下一步”等只描述历史，不构成当前入口。

## 先前：修正 systemctl 多命令属性解析，08b失败状态保持

离线检查确认 v255 的 systemctl 对每条 Exec 命令分别输出同名属性；原解析器把合法
多条命令当成重复标量拒绝。现仅六个既有 Exec 属性可多行，按原顺序保留全部值；
Id、Names、状态等标量及未知键仍不允许重复，身份、别名、覆盖和下游检查保持。
FORMAT 失败直接记录同一已捕获响应的具体子条件、响应块/行号、已知属性名及行长度/摘要，
不输出命令参数或整段响应，不增加现场查询。见[修复与验证](../Q2_CORE_NAMES_CONTINUATION_REVIEW_20261008.md#systemctl-多命令属性解析修复)。

这是已确认的代码兼容性修复，不能证明缺少原响应的08b只有这一原因。H01/Q4/H11
仍未运行；本地 Codex 可先同步修复候选核对既有私料，原冻结caller和消费不变。
本次不产生新窗口、caller或核心包。以下保留最近一次现场返回及历史。

## 先前：NC1完成，唯一08b在systemctl响应格式校验停止

[准确返回](../Q2_CORE_NAMES_CONTINUATION_FIELD_20261008.md)：Owner批准A
`68cae882e3b831aaa191e7a877278ccf6ba10e2b` 的NC1–NC3；准确B及独立C
`eba5023b13e42d4610533b7e7c4eede3ebd658db` 先于直接实现子提交
`dc538b9034f00c635344defae57b7054319c2184`。D完成发布、准确首次CI 3/3、独立安装、
静态输入/原件核验及冻结。Linux6740 passed/89 skipped，独立安装94 checks/292 commands。
短预检仅摘要绑定重复resume，完整四代历史和所有原件保留；708 B样本低于原4096 B上限。

NC2 `lhqjgrow-20261008b` 普通预检通过，同窗execute创建marker、发一次SSH后停止。
已有guest报告为 `PRE_QUIESCENCE / GROWTH_SYSTEMCTL_FORMAT`，动作空，无关机token，
未备份、扩容或重启。具体格式失败子条件没有保留，不补采；remote_exit保持UNKNOWN。
NC2为CONSUMED/FAILED；NC3及H01/Q4/H11均NOT_RUN，未生成或发送真实核心包。

五代消费、完整费用、原件及UNKNOWN保持；本次五件原件和索引私有，获批旧08a最小索引
已公开。私有gate终止，不能重放任何caller或单独执行条件核心批。没有重试、补采、清理、
恢复或扩展支线，本轮不自动申请另一窗口。以下“下一步”等只描述历史，不构成当前入口。

## 先前：修正 Names 显示格式解析，现场仍停在已消费08a

最新现场仍为下述 TC2 失败；没有再次查询或运行维护。
已用本机 systemd v255 的原生 `shell_maybe_quote(..., 0)` 确认：Names 数组会给含反斜杠
的合法单元名加引号并转义，旧 `.split()` 将显示引号误当成名称。现在只解码这层显示，
保留字面 `\\xNN`、重复/名称/正式 Id/覆盖/冲突检查，拒绝非规范编码。
同次失败额外保存具体校验条件、单元与响应序号、Names 字节数/摘要和最多512 B前缀，
没有新增命令或重试。详见[源码验证](../Q2_CORE_TEMPLATE_CONTINUATION_REVIEW_20261008.md#names-显示格式修复)。

相关本地765项通过、5项环境跳过；新增Names的46项全部通过，含原生格式验证。
旧现场没有被拒绝Names值，不能认定这就是08a唯一原因。
本地 Codex 下一步同步修复候选，复用既有安装、SSH和私料，只准备容量维护成功后直接
接 H01→Q4→H11；原08a窗口已消费，按AGENTS不能重放。本次不产生新caller或新现场权限。

**下次接续前必须离线处理：预检重复历史会超界。** 现三条历史的实际预检为3915 B，
把时钟/计量取许可最小正整数仍为3858 B。沿当前结构追加08a第四条，即使五件原件的
bytes全部按0作极保守长度下界，新预检仍至少4906 B（大时钟样本4963 B），必定超过
4096 B并被现解析器以JSON_SIZE拒绝。这是纯内存构造/解析已复现的问题，不需现场试跑。
因此不能只同步Names修复就再开维护窗口，也不能机械追加第四条完整历史。

下一接续方案应只处理这个既有交接的重复表示：完整历史仍由原manifest/原件链严格验证，
预检可用固定长度摘要绑定该完整历史，同时保留D、manifest摘要、nonce、双钟与累计用量。
此为待审的表示调整方向，**尚未实现或授权**；不提高4096上限、不删历史、不改变旧消费。
本地持有私料的一方应在后续准确方案中先完成这项离线构造和双方绑定检查，再考虑现场。
这不是新增功能或允许跳过维护；成功后仍只执行原H01→Q4→H11。

## 先前：TC1完整冻结，唯一08a维护在Names校验停止

[准确返回](../Q2_CORE_TEMPLATE_CONTINUATION_FIELD_20261008.md)：Owner已批准准确A
`80c7c8eaeda0853317c679b31b0ed1f1ac13e49b` 的TC1–TC3，独立C为
`bb9b3c6e9b397121220c22515e4ef637d12c7297`。执行D
`d5b34316bc93b37442eb5db64ba265b965e68379` 已完成离线输入、源码、独立安装、发布、
准确首次CI3/3和冻结。Linux6525 passed/89 skipped，独立安装94 checks/292 commands。

TC2 `lhqjgrow-20261008a` 普通预检通过，同窗execute创建marker、发一次SSH后失败。
本次已有guest报告为PRE_QUIESCENCE/GROWTH_SYSTEMCTL_NAMES，动作空，无关机token。
原上下文未保存被拒绝Names值或具体单元，不追加查询补证。没有备份、扩容或重启；
远端整体退出仍UNKNOWN，TC3及H01/Q4/H11均NOT_RUN，没有生成或发送真实核心包。

四代维护的原件、完整费用、消费及UNKNOWN均保留；08a已消耗，不能重放其任一caller，
也不能把尚未发出的条件核心批单独执行。本次没有重试、补采、清理、恢复或扩展支线。
以下“当前/最新/下一步”仅为对应历史检查点，不是执行旧交接的入口。

## 先前：模板查询原因已明确，完成针对性源码修复

最新[现场记录](../Q2_CORE_SYSTEMCTL_CONTINUATION_FIELD_20261007.md)为 `531bf0a`：
准确执行候选 `b2bc054` 的 SY1 完成；SY2 `lhqjgrow-20261007b` 预检通过后一次执行失败。
已有同次诊断确认 systemctl show 退出1、双流EOF完整、stderr拒绝未实例化模板单元。
没有关机 token、扩容或 H01/Q4/H11；远端整体退出仍 UNKNOWN。

修复只处理这条核心准备路径的单元语义：模板通过 cat 检查完整fragment/drop-ins，
实际实例与普通单元继续 show；别名通过同次返回的 Id/Names 验证，不能丢失请求单元、
接受冲突属性或替换已声明业务/域单元身份。原返回码/EOF/stderr要求、资源上限和现场
次数不变。详见[源码修复与验证](../Q2_CORE_SYSTEMCTL_CONTINUATION_REVIEW_20261007.md#模板与别名的源码修复)。

本地 Codex 下一步同步修复候选，只接续 journal 容量修复与原 H01→Q4→H11。
已有安装、SSH、三个维护代次的原件/marker/消费均保留。AGENTS 明确禁止重放已消费
SY2；本次没有生成新现场 caller 或授权新窗口，不能直接重跑旧07b命令。

以下“当前/最新”均为历史检查点，不是恢复扫描支线或执行旧交接的入口。

## 先前：序列号已通过，修复 systemctl 单元名参数阻塞

最新[现场记录](../Q2_CORE_SERIAL_CONTINUATION_FIELD_20261007.md)为 `acd62cb`：
SC1 完成，准确执行候选 `a20bf2a` 的 CI 3/3；SC2 单次 `lhqjgrow-20261007a`
已消费且失败。序列号校验通过，随后在 `PRE_QUIESCENCE / GROWTH_SYSTEMCTL_STDERR`
停止；没有关机 token、扩容或 H01/Q4/H11 执行，远端退出仍 UNKNOWN。

已离线复现 `show_many` 漏传 `--`：根单元 `-.slice` 会被 systemctl 当成选项拒绝。
修复只正确分隔单元名，保留原退出码/双流EOF/空stderr和身份检查，并在同一次失败输出中
保留命令序号、manager、verb、参数摘要、退出码、流长度/摘要和最多512 B stderr字节。
详见[修复与验证](../Q2_CORE_SERIAL_CONTINUATION_REVIEW_20261007.md#systemctl-单元名参数修复)。
旧现场缺少这层原始命令信息，当前不能证明该代码缺陷是此次现场失败的唯一原因。

本地 Codex 下一步同步准确修复，复用既有输入核对生成 guest payload 的参数和诊断，
只准备 journal 维护成功后接 H01→Q4→H11 的核心接续。SC2 及旧 K2 原件、marker 和消费
均保留；AGENTS 明确禁止在已消费范围内重放 caller。源码修复不发出新现场请求。

以下“当前/最新”均为历史检查点，不是恢复扫描支线或执行旧交接的入口。

## 当前：DR1 已完成，DR2 因 task 成员列表变化失败并消耗

[准确 A](../../governance/Q2_CORE_JOURNAL_DRIFT_RESUME_BASELINE.md)
`4f2a6a37ad5afd027dbde0f1656a3552750cb3b2` 已取得
[Owner B](../../governance/Q2_CORE_JOURNAL_DRIFT_RESUME_OWNER_DECISION.md)，
`LH-Q2-CORE-JOURNAL-DRIFT-RESUME-v1` / DR1–DR2 Gate 已关闭。
独立 C `e13f8efcb8dee4e4280dd722f7836ea94a27b83b` 后直接提交实现
D `309c6e1cacfdf05cabeeac9d27f487acad524b61`，只新增准确授权来源与 manifest 绑定。
相关 106 项本地验证通过、0 跳过；生成 payload 在相同 D 下与诊断修复字节相同。
准确 D 的 CI `37575372661` 首次 3/3 success，含两平台源码与独立安装验证。
十二源成员和八份原静态输入核对通过，独立源码检出与最终私有交接已冻结。
详见 [DR1 验证与冻结](../Q2_CORE_JOURNAL_DRIFT_RESUME_REVIEW_20261007.md)。

交接时 DR2 尚未开始；最新 [DR2 返回](../Q2_CORE_JOURNAL_DRIFT_RESUME_FIELD_20261007.md)
已记录本次唯一替代窗口 CONSUMED / FAILED。准确候选在 checkpoint 1 返回
`GROWTH_PROC_DRIFT_PID_TASK_SET`，明确为同一数字 PID 路径的前后排序 task 成员列表不同。
后续 PID starttime 和最终全局 PID 集合复核尚未执行；具体 PID/线程差集及原因仍未知。
失败前缀为 PID 338/618、task 1322、FD stat 104007、maps 132547020 B，scan_complete false。
最后成功双钟样本约 12.175s，不是最终耗时或全量可行性证明。
marker false、SSH0、成功 writer 报告0；未进入 execute 或 journal 维护。
原检查、预算、15s/900s/780s、原 session 和累计维护次数保持，全部旧窗口继续消耗。
本次最终交接、旧 W2 和待决草稿均禁止执行；不重试、补采、提额、停宿主应用、清理或恢复。
原始流未独立认证，历史 W2 的具体分支仍 UNKNOWN。没有 journal 维护成功证明；
新 boot 核心采用与 H01/Q4/H11 不在
本范围，原后续接线缺口保留，支线继续暂停。

以下保留本次批准前的历史检查点，其中“当前/尚未/没有新交接”仅指对应登记时刻。

## 当前离线修复：一致性错误已按具体检查项区分

在下述已消费 W2 的基础上，直接修复原扫描器诊断：重复枚举、task 集合、PID/task starttime、
FD 身份/fdinfo/snapshot、最终 PID 集合分别返回明确原因。原判定、短路读取、计数、预算与
v2 协议保持，源码与实际生成 payload 同时验证。详见
[诊断修复记录](../Q2_CORE_JOURNAL_DRIFT_DIAGNOSTICS_REVIEW_20261007.md)。
这是已有 CLOSED 范围的离线代码修复；历史具体分支仍 UNKNOWN，W2 仍 CONSUMED / FAILED。
没有新的现场调用、journal 维护或 H01/Q4/H11 PASS，也不授权再次执行旧交接。

本地已同步准确修复 `711932aae3370c7f2ed5c1a51ac82d3b0f67a6e5` 并完成离线核对：
十五文件 663 passed / 0 skipped；host 与生成 payload 的独立 AST 对比通过；八份原静态
输入绑定不变。准确提交 CI `37569620992` 首次 3/3 success，含两平台源码与独立安装验证。
旧 W2 冻结源码及终端交接摘要不变；没有生成新现场交接或消费新窗口。
详见同一诊断修复记录的本地核对节；上文云端计数和本地实际命令分别保留。

## 当前：W1 已完成，W2 在 PID 复核阶段失败并消耗，业务核心尚未进入

此前现场登记为 `8c58f093a3fc923fb078811622fb2691448e81fc`。
maps修正MB1已完成，执行候选 `68b63da88d70cfb8151f66a75c7f523baaf012d2`；
唯一MB2窗口已消费，在checkpoint1以 `FD_TOTAL=262145>262144` 失败。
marker false、SSH0，journal未扩容，H01/Q4/H11没有真实PASS。
详见[MB2返回](../Q2_CORE_JOURNAL_MAPS_BUDGET_FIELD_20261007.md)；其原始流未独立认证。

当前[准确 A](../../governance/Q2_CORE_JOURNAL_SCAN_WORK_BASELINE.md)
`42a66be98c45e817e866d3fb86a1c184c2ce55f9` 已获
[Owner 批准](../../governance/Q2_CORE_JOURNAL_SCAN_WORK_OWNER_DECISION.md)，W1–W2 Gate 已关闭。
独立 C 为 `1f656f7dab12ddb02c6927d3fc08c2fbe81ffebc`，其直接实现子提交 D 为
`57c7f8e19e047d8caeea401593d8e4bbd4dc373d`。实际 FD stat 尝试计费、严格 v2 进度和两源长度界
已实现；完整覆盖与原期限保持。相关本地 635 项及补充 2 项通过，准确 D CI `37555791202`
首次 3/3 success，包含源码及独立安装验证；原八份静态输入绑定不变，准确候选和交接已冻结。
详见 [W1 验证记录](../Q2_CORE_JOURNAL_SCAN_WORK_REVIEW_20261007.md)。

最新 [W2 现场返回](../Q2_CORE_JOURNAL_SCAN_WORK_FIELD_20261007.md)记录 checkpoint 1 的
`GROWTH_PROC_DRIFT` / `PID_RECHECK`，scan_complete false；初始 PID 594、完成 419，
task 完成 1549，FD stat 尝试合计 114545，maps 完整读取 137564054 B。
该阶段可在 task 重枚举重复、前后 task 列表或 PID starttime 的检查处拒绝，具体分支未确定。
这些仅是失败前缀，不能宣称全量预算足够或 writer 准入通过。marker false、SSH0、成功报告0，
本次唯一 W2 窗口已消耗，journal 未扩容。原始流未独立认证，完整输出保留私有终端。
全部旧窗口和本次交接均禁止重跑；没有补采、放宽一致性、清理、恢复或支线授权。

同时已确认：扩容重启后的新boot尚无核心consumer，现dispatcher仍绑定三旧profile，
还缺已消费05c的第四旧接入。因此下文历史“源码缺口清空”仅对应当时版本，不能用来
宣称目前收到维护receipt即可直接运行旧核心包。下一核心修订需验证完整维护原件与
新旧boot/VM关系、保留四旧承诺，再发行一个准确新批；设计可提前准备，执行依赖真实维护成功。
本次W1–W2不包含该第五批授权。核心目标仍为H01正常任务→Q4取消→H11自身原ledger恢复。

以下保留2026-10-05及更早历史检查点，其中“当前/最新”均只描述其登记时刻。

## 当前：sudo修复已全绿，固定单次核心验收待准确批准

准确修复 `432f3f4` 的CI现已3/3 success：Linux 5157 passed / 88 skipped、installed 94 checks / 292 commands；Windows 1808 passed / 1327 skipped、installed 10/10。
Owner最新截图报告本地321通过/10跳过、两次私料内存构包一致，未发现场包；不能把这次离线验证当成业务PASS。
下一步已收敛为固定05b的一次H01→Q4→H11，不继续支线。准确提案A为 `f9ba6fbc2fa983c46322a00f3385af172fed7cb4`，
范围S1–S3，详见[基线、三文档与可直接回复的决定文字](../../governance/Q2_CORE_POST_SUDO_ACCEPTANCE_BASELINE.md)。
两旧批十原件/UNKNOWN/完整承诺保持；新批只在同一carrier核对两旧scope后继续。
该新范围仍OPEN，尚无Owner B和独立C，不能写新批次实现或发请求。已有sudo修复不需再次批准；批准后云端接齐必要实现，本地Codex验证私料并执行唯一新请求。
以下保留历史检查点，其中“CI仍运行”只描述当时状态。

## 当前：包已传入，修复 sudo 输出解析阻塞

`d846c72` 记录新一轮唯一请求已完成 HELLO、BIND 和包传输，随后在
`CORE_ADMIT_SUDO_OUTPUT` 停止，尚未进入 H01。现场原始 sudo stdout 未保留，
不能确定具体失败断言。本轮已离线复现并修复新版来源文件标题、原始 TAB 命令缩进
以及无 Defaults 标题的兼容问题，并加上固定阶段、行号、结构计数和摘要诊断。
权限、来源和凭据校验保留；8 组相关测试 **248 passed**。

具体证据和本地 Codex 交接见 [sudo 解析修复记录](../Q2_CORE_SUDO_LISTING_REPAIR_20261005.md)。
本地下一步先同步修复并用已保留材料做离线发行复核。两次现场机会均已消费，
release allowlist 保持空；新增现场请求仍须新的准确批准链。未取得真实 H01/Q4/H11 PASS，
不得重试、重连、重装或清理现场；核心以外工作继续暂停。以下为历史检查点。

## 最新：原单次 F1 已消费并停止，禁止重试

新来源修订已按准确 A → Owner B → 独立 C `6013436` → D `0293c46` 实施。
发行 D `605a2a3` 经完整源码/安装与真实私有包双 build/parse，CI 3/3 success 后，
在原窗口创建唯一 marker、发出唯一 carrier 并收到真实有效 HELLO。
host 的 BIND 构造器遗漏 v3 entry 的 `writer` 字段，故在发送 BIND/package 前停止，输入 0 B。
H01/Q4/H11 未进入提交阶段，没有业务结果包；原回执两项业务 truth 与远端退出闭合保持 UNKNOWN。
原五个 capture 文件及 marker 保留，未重连、重试、安装或清理。

已在原核心开发范围修复该接线，准确修复 D `a6638424c5de2ea59f39cf6e24f07b06040d0884` 已推送。
旧源新增回归 2 failed；修复后定向 82 passed，完整源码 4905 passed / 126 skipped，
独立安装 PASS（94 checks / 292 commands）；修复 CI 37220038272 在登记时仍运行。
release allowlist 重新置空：修复/测试不能授权第二 request；再次验收必须有新的准确批次 A/B/C，
不能复用本批次或刷新 deadline。生产 E3 保持，支线暂停。
详见 [完整实测、失败及修复记录](../Q2_CORE_SINGLE_F1_RESULT_20261005.md)。以下均为历史检查点。

## 最新本地包复核发现固定来源前提冲突

已同步并核对 `e2a40bd4b0e0b17ebe2a2ad3f533bdace318cc05`，CI 3/3 success，
本地 core 回归 953 passed / 35 skipped。原 859 静态成员、wheel/projection、历史来源与
本地管理入口身份均复核通过，但完整 approved-input 聚合被 `CORE_POLICY_BASIS_SOURCE_GRANT` 拒绝。
固定 cloud-init 将 name 和 sudo 分列于同一 users mapping；原批准要求的完整 sudoers 字面行不存在。
这不是 guest 不支持，也不是删除生产 E3 的理由。详见 [准确复核与最小提案](../Q2_CORE_PRIVATE_PACKAGE_REVIEW_20261005.md)。

只重新打开固定来源转换范围；待 Owner 对其准确 A 批准并独立 C 后才实施。
原其他批准、预算、时限和条件单次 F1 保留。没有完整 package、marker、carrier 或真实任务结果；
release allowlist 仍空，支线保持暂停。以下源码接齐记录不代表真实原件或现场门已通过。

## 最新：核心资源与结果链源码已接齐，进入 C3 私有发行复核

在已批准 A `851a1afe4e55196212aa6913e81e0722deed1032` 的同一范围内，
已接齐 32 池实际观察、受控 I/O 记账、真实启动与 carrier 计数，以及 v2 结果生成/独立校验。
修复落盘超时、准入身份交叉绑定，以及冻结产出中的 Q4/H11 兼容问题。
整合核心回归 **985 passed / 1 skipped / 2 deselected**；两个云 PID 映射测试保留原断言并交普通 CI。
完整扫描减少重复父目录打开；每次全量观察、fresh boot 读取和原双时钟校验保留。
dispatcher **412466 / 524288 B**。源码缺口清单已清空，host release allowlist 仍为空。

下一步由本地 Codex 使用已有私有材料完成准确包的两次独立 build/parse 与原 C3 复核，
全部通过后继续原条件单次 H01→Q4→H11。无需再次批准同一 A；不新增现场轮次或分支功能。
本次没有发行现场包、连接 guest 或取得真实 case PASS，不能把源码测试写成现场完成。
具体改动、证据局限与本地执行任务见
[资源/结果整合与交接](../Q2_CORE_COMPLETION_RESOURCE_REVIEW_20261004.md)。

以下保留各历史检查点，其“尚未接齐”描述对应当时版本。

## 当前完成调整：已独立关闭，准入源码已接入

Owner 已明确批准完成调整 A `851a1afe4e55196212aa6913e81e0722deed1032`。
独立 bookkeeping-only C 为 `c32799c03a32d81deec02f7492c1b71eb47b2b6d`；
首个实现 D `53533accbf834d489c773d2a037c008059c90c4f` 直接继承 C，tree
`4207e1e5317f7b7f69818f3aba476dc85dc9cc44`。

本轮接入 current-guest admission、固定 32 池逐设备保守预留、身份/输入交叉绑定，以及
carrier 实际 cgroup 计数读取组件；同步第三条 A/B/C→D 校验和批准的 524288-byte dispatcher cap。
实际 dispatcher 为 331928 B。原 runtime candidate/wheel、预算、时限、单次 F1 和生产 E3 不变。

**这不是 C1–C3 全部完成。**完整 32 池受控 I/O/分配观察、remote-result/v2 和聚合 usage
尚未接齐，`usage()` 仍拒绝不完整结果，release allowlist 仍为空。未连接 guest、未消费 marker/request，
没有真实 H01/Q4/H11 或结果收回。详细版本、验证及可执行后续接线见
[本轮实施记录](../Q2_CORE_COMPLETION_ADMISSION_REVIEW_20261004.md)。已有批准有效，
后续只继续这些核心缺口，不需要再次批准同一 A，不转去支线。

## 保留的批准前复核与提案

已发布修复 D `631677039af3b17392f3269e39a4b1f409fc4f08`，tree
`8408d12541a9bb421373e43a3ea801f6dd59ccfa`，父提交为本地 Codex 的
`342c0a59ce9c7b7709ee08e70f7f4cdf2fb8dfe6`。只继续既有 CLOSED 核心范围。

安装执行身份绑定中的 open、fstat、capability xattr、pread、最后按名称 stat 现在各自使用
原双时钟 guard；晚返回、晚异常后不继续下一次读取或启动子进程。晚取得的 fd 立即关闭，
原 inode、字节内容、所有者、capability 和名称绑定校验保留。没有增加宽限期或重试。
这仍不能中断阻塞中的内核调用。

精确旧源 `342c0a5` 的新增回归为 **6 failed / 2 passed**；修复后 **8 passed**，与原三组
安装测试合计 **65 passed**。核心回归 **680 passed / 1 skipped / 1 deselected**。
被 deselect 的仍是已记录的云执行环境 PID 与 `/proc/self/stat` 差异测试，其断言没有改动；
普通 runner 的 CI 仍运行它。准确 D 的
[CI 37199747854](https://github.com/kongbu0621/infra-local-hand/actions/runs/37199747854)
已 **3/3 success**：Linux **4599 passed / 85 skipped**，独立 installed verifier
**94 checks / 292 commands**；Windows **1721 passed / 1253 skipped**，独立 installed
verifier **10 checks / 10 commands**。前一实现 `3f1c474` 的 CI 37197973710 也已全部成功。

当前 dispatcher **262072 / 262144 B**，SHA-256
`cd5fd46627c4090ab35c8e81e137c9c51d8b99fdcf00a338aafe790bbcfd731f`。
本修复没有改源码上限、其他资源限额、固定候选/wheel 或原条件单次 F1。

本轮还定位了两个不能靠追加小修复消除的设计问题：

1. 原 262144 B 源码上限仅剩 72 B。旧完整开发祖先的 admission 最小引用闭包与当前实现合并，
   在修复前基线已为 **319323 B**，还没有包含移植修正与实际 usage；这是已存在代码的测量，
   不是“所有可能实现都不能压缩”的证明。继续为该上限反复改写不等于补齐核心链。
2. 原全过程磁盘物理峰值保证缺少观测来源。外部 compiler/venv 的中途临时文件、SQLite
   DB/WAL/SHM，以及 journal/capture/carrier 的非 quota 文件，都没有全过程物理峰值证据。
   目录前后扫描、逻辑大小和结束 seal 不能替代该保证。七根 project quota 的原约束另行保留。

最窄完成调整见 [需求](../q2-core-completion-adjustment/REQUIREMENTS.md)、
[架构](../q2-core-completion-adjustment/ARCHITECTURE.md)、
[实施方案](../q2-core-completion-adjustment/IMPLEMENTATION_PLAN.md)。准确 A 为
`851a1afe4e55196212aa6913e81e0722deed1032`，其
[OPEN 登记](../../governance/Q2_CORE_COMPLETION_ADJUSTMENT_BASELINE.md)列明全部摘要及决定请求。
这是 **OPEN 文档提案**，
不是已批准实现：源码 cap 和存储保证尚未修改，原 blocker 与空 release allowlist 保持。
既有不受影响 CLOSED 工作可以继续；不能把本轮常规“推进核心”指令编造成对新精确保证的批准。

完成核心的实际顺序是：明确这两项边界后接回 current admission，完成 carrier 实际计数和
完整资源观察，独立核对最终源码/包，再由本地 Codex 用既有连接执行原条件单次
H01→Q4→H11。H11 只恢复自己的原 ledger，不能为统计重读业务 result。
本轮未连接 guest、未发行 marker/request、未运行任何真实核心 case。测试不是现场验收。
namespace/watchdog 及其他分支功能继续暂停，production E3 限制不变。

## Current preparation capacity collector followup

Implementation D is `3f1c4745d8ee888f0c0057794532aa78cfcddbbe`, tree
`476b9f7b87978945059ffb8c86b8e38cd6e4487b`, directly following main
`34c579bbb0c5edd465341abde861b9d592b8ff77`. This continues the already CLOSED
core D1–D4 development scope. The direct pinned R was read again. Exact Git-blob
verification passed both independent C ancestry chains and unchanged A/B pins.
The preceding D `247d3ab7de8c323db883a5ed877ab06311ab1cc3`
has completed [CI 37196149601](https://github.com/kongbu0621/infra-local-hand/actions/runs/37196149601)
successfully in all three jobs. No runtime candidate, approved field wheel,
budget, deadline, new approval or field authorization is substituted.

### Preparation collectors now have concrete implementations

The three existing preparation dependencies now collect retained-root snapshots,
project-quota inventory and quota-enforcement flags. Retained-root selection still
comes from the exact approved 16-root envelope, not caller-selected paths.
Held directory descriptors, approved device/inode pins, protected ancestors,
bounded no-atime enumeration and regular-file reads retain the original checks.
Each observed file and directory is checked again by name or held identity;
metadata drift, aliases, hardlinked files, special files and incomplete reads fail.
Depth-first traversal bounds outstanding descriptors. A regular-file-to-FIFO
replacement cannot block the open waiting for a writer. No O_NOATIME fallback,
atime repair, cleanup or quota mutation was introduced.

Quota observations require the admitted quota mount before I/O, bind its block
device identity, retain the bounded read-only quota cursor, and reject late EOF,
late errors, reordered rows and an incomplete inventory. This does not establish
that the real guest currently has the required mount or enforcement state.

All three collectors accept the original preparation guard, which is passed by
`prepare_case` and the quota-root preparation helper. Late returns and exceptions
are checked before any subsequent effect; late-opened handles are closed. The
guard helper's own positional parameters no longer collide with a nested
collector's `guard` keyword. The initial two preparation regressions exposed
that collision; it was fixed, not ignored or treated as a successful preparation.
These guards reject late returns; they cannot interrupt a blocked kernel call
and do not replace the original outer supervision or refresh its deadline.

### Verification boundary and remaining work

The new 35 regressions use actual fd-relative temporary-file operations for
retained snapshots. Quota calls and device stat records are explicit doubles;
no real block device was created, opened or changed. Core regression passes
650 tests, with 24 OS/root-dependent skips. These results are not field PASS.

The full source suite passed **4561 tests / 115 skipped, 430.46 s**. Its retained
local report `lh-core-capacity-source.ZsKKeO/results.xml` has SHA-256
`1dfbc9970a59721399a48b21f7daeae972975f4ba9139b8e90673c7dd8937193`.

An independent clone of exact D built and installed a test wheel. The existing
installed verifier returned **PASS, 94 checks / 292 commands**. Its retained
local report `lh-core-capacity-installed.4ThFVL/acceptance/report.json` has SHA-256
`449778693fa921444b3292b1f62f7847d8c7f91e90792c11084390a37f8e0f37`.
The test wheel binds source commit D and has SHA-256
`3ffe3bb99173bada5c0476584e9c3e03b107394a06e1879e027a7acf3c68412e`;
it does not replace the approved field wheel. D was pushed to main. Its
[CI 37197973710](https://github.com/kongbu0621/infra-local-hand/actions/runs/37197973710)
was in progress when this record was prepared, not yet claimed successful.

The dispatcher remains within the unchanged limit at **262044 / 262144 bytes**,
SHA-256 `8330044bead3ba2db0e801e102e57e8a4fb6ccafd8c0298166e41626ea352add`.
Existing prefixed validation calls and whitespace were factored without removing
their predicates or changing their diagnostic codes; the mechanical conversion
was checked by reverse AST expansion. Shared stat comparison removes duplicate
field ordering. The new collectors intentionally add behavior; this is not a
claim that the whole revised module is behaviorally identical. Loader and
bootstrap remain unchanged at 2160 and 49102 bytes. No fourth field module,
compressed executable or larger source cap is used.

Only `preparation.current_capacity_collectors` is removed from the implementation
gap list. Current-guest admission is still fail-closed, its approved-input binding
work remains, and the complete shared installation-pool peak and aggregate
CPU/memory/pids/storage/stream usage accounting are unresolved. Preparation also
requires the original admitted retained snapshot; implementing a collector does
not supply an admitted baseline or bypass the existing current-facts check.

After those gaps, complete release review and independent private package
build/parse are still required before the conditional single H01→Q4→H11 run.
The release allowlist remains empty, the package is NOT_ISSUED, and this invocation
created no field marker, sent no carrier/SSH request, ran no guest task and
recovered no new guest result/evidence. Existing guest state was not re-observed.
Do not replay historical batches or open a separate guest probe to fill current
facts. Namespace/watchdog remain paused and production
`E3_SUPERVISION_UNVERIFIED` remains enforced.

## Earlier frozen installer deadline followup

Implementation D is `247d3ab7de8c323db883a5ed877ab06311ab1cc3`, tree
`f5798cf1c97eb0174f0339eb4e73b503eaa4b285`, directly following
`0d2b7c73bd2ff46b666e16e018b2ebc6c7f8898e`. The latter's
[CI 37193722314](https://github.com/kongbu0621/infra-local-hand/actions/runs/37193722314)
completed successfully. This continues the existing CLOSED core D2 scope;
the original R was read directly and the exact Git-blob verifier passed both
independent C ancestry chains and the unchanged A documents/B decision digests.
No new approval, runtime candidate, field wheel, budget or deadline is inferred.

### Frozen installer I/O now uses the original clocks

The private held-byte loader supplies only `q2_prepare_build` with guarded OS
and Path bindings. Its original source remains byte-identical to frozen runtime
`4b6e4a7c403362358192086b88679e1326dcb2e1`; no candidate function body, wheel,
projection or extra field module is substituted. Other modules and process-wide
stdlib bindings are untouched. Source verification, inventory, copies, native
input reads, metadata and final fsync pass through the original paired-clock
guard; the existing bounded command runner still owns child execution.

Late opens close the returned descriptor. Late reads, metadata operations,
writes and fsync stop subsequent operations, including when an operation raises
ENOENT or a missing-capability error. The frozen writer uses unbuffered chunks
of at most 65536 bytes and handles short writes; exception cleanup cannot flush
another buffered write. Only the original owner closes its file descriptor.
Partial files and directories remain retained, without overwrite or retry.
The two fixed systemd resolve paths retain admission's no-alias requirement;
the guarded directory walk rejects aliases rather than following them.

This implements `installation.deadline_guarding`; it does not make a blocked
kernel call interruptible, prove shared-pool peaks, or complete field admission.
The original clocks and guest 45-second final reserve are not refreshed.

### Source validation and fixed field size

New frozen-installer regressions: **29 passed**. They execute actual temporary
file I/O through the frozen code with explicitly injected late returns, plus
private-loader and alias checks. They are not an installation on the guest.
Initial test failures used incorrect inventory field names and a 0700 mkdir
expectation; the assertions were corrected to the unchanged installer's
`entries` and 0755 behavior, without weakening its checks.

Core regression: **615 passed / 24 skipped**. Full source suite:
**4526 passed / 115 skipped, 429.73 s**. The retained local report is
`lh-core-frozen-install-source.EKTYdB/results.xml`, SHA-256
`4abdd09c3cd3c4df52db2cd116c41a9b9bca91d08cce12bcbd7a7ee9110d32e3`.
Skipped root/OS-dependent checks remain skipped, not field PASS.

An independent clone of the exact D built and installed a test wheel, then the
existing installed verifier returned **PASS, 94 checks / 292 commands**. Its
local report `lh-core-frozen-install-installed.W6o0Mo/acceptance/report.json`
has SHA-256 `c94a084d31e5afb6a68e2b3d2dd12a73ab3af9342ac9b33c8f906c9c7b6c388d`.
The test wheel binds source commit D and has SHA-256
`af572510b1241497878dd7139ce5606735a226ca458d8af35c6914e40596a7cb`;
it is not a replacement for the approved field wheel. D was pushed to main;
its [CI 37196149601](https://github.com/kongbu0621/infra-local-hand/actions/runs/37196149601)
was in progress when this record was prepared, not yet claimed successful.

The dispatcher is **257264 / 262144 bytes**, SHA-256
`bf3bb0d9d292b7b68fa04c7f5d9a7247bf281c5779cc679162381c8280a192fe`.
Fixed ordered field-name literals and hanging-indent formatting recover space
without increasing the cap. Reverse expansion matched the entire preceding
module AST after excluding only the new I/O adapter, its loader binding, the
field-name helper and the completed blocker entry. Existing checks, diagnostic
codes and data ordering remain intact. Loader and bootstrap remain unchanged
at 2160 and 49102 bytes. No compressed executable payload was introduced.

### Remaining direct field blockers

Current-guest admission and preparation's current-capacity collectors still
need implementation. Complete shared installation-pool peak accounting and
aggregate CPU/memory/pids/storage/stream usage evidence are also unresolved.
Existing private historical inputs are retained; do not ask for those originals
again or open a separate guest connection to fill current facts. Current guest
checks belong inside the original single carrier after all offline gates pass.

After these implementation gaps, perform the complete release review and
independent private package build/parse before permitting the conditional single
H01→Q4→H11 run. The release allowlist remains empty and no field package was
issued. This invocation created no field marker, sent no carrier/SSH request,
and ran no guest core task; it collected no new guest result/evidence. Existing
guest state was not re-observed. Namespace/watchdog remain paused, and production
`E3_SUPERVISION_UNVERIFIED` remains enforced.

## Current cancellation and installation followup

This core-only D followup descends from `5208e43d785f1c3eaacedf632029ed144b37833c`.
It continues the existing CLOSED scopes; candidate, wheel, projection, budgets,
deadlines, field allowlist and conditional single F1 are unchanged. The preceding
implementation `0c786ac` has now completed [CI 37191629497](https://github.com/kongbu0621/infra-local-hand/actions/runs/37191629497)
successfully in all three jobs.

### Corrected original Q4 cancellation

The frozen candidate's runner deliberately does not start a result-reader after
successful helper-running cancellation. The previous adapter indexed that absent
receipt and required an InvocationID for it. Q4 now requires the actual bootstrap
and helper receipts, matching helper boot/unit/InvocationID to the original
trigger and final report. It also binds durable delivery events to the original
report and rejects any reader or delivery after cancel. H01/H11 retain their
three-stage requirements. All three static authorized names remain in the plan.

This follows the original A requirements: static names at lines 176–182, launch
upper bounds at 200–203, actual identity array at 803–804, and Q4 PASS at
1132–1140. It changes no authority or acceptance contract. Regression evidence
uses the original Broker, SQLite ledger and cancellation report code; manager
and OS observations in that test are explicit doubles, not field evidence.

### Installation execution and internal I/O

Each installation/owner child now executes an already-opened, verified ELF
descriptor. The six admitted program identities remain checked. New runtime and
ABI programs are permitted only during the active original installation; their
held execution identities are retained and checked against its returned receipt.
The installed runtime also binds the receipt's device/inode. Equal-content inode
replacement, file capabilities and identity drift are rejected.

The original setpriv flags and credential checks remain. Its second Python hop
uses the held interpreter descriptor and a fixed `__PYVENV_LAUNCHER__` value to
preserve the original venv path. No wrapper executable, shell, extra runtime
module, new privilege, refreshed deadline or retry was added. Actual child exit,
wait4 usage and both EOFs remain mandatory; descriptors close on failures.

Dispatcher-owned extraction, scans, reads, creates, mkdir, metadata and fsync
now check the original paired clocks around each operation. Late opens and
iterators are closed; late writes leave partial objects without further writes.
Even a late ENOENT is checked before a caller can treat it as an absent object.
This cannot interrupt a blocked kernel call. Frozen `q2_prepare_build` internal
multi-step I/O still needs integration, so `installation.deadline_guarding`
remains a blocker. Directory samples remain observations, not a complete peak.

### Exact validation and remaining work

Dispatcher: **261898 / 262144 bytes**, SHA-256
`ba990dbac0c1fb9f63f25a353686124aa4f8035535f9b2055e6931fa99041653`.
Readable shared checks and data construction recovered space without dropping
predicates or changing diagnostic codes. Independent reverse expansion verified
the unchanged AST of 40 pure functions and the effect methods before the final
late-exception fix; ordered source lists, budgets, intents and session values
were also checked for equality. No compressed executable payload was added.

Local final core result: **608 passed, 1 skipped, 1 deselected (12.98 s)**.
The deselected unchanged writer test encounters the already-recorded cloud
`os.getpid()` versus `/proc/self/stat` discrepancy; it remains enabled in CI.
Installation binding/deadline regression files together: **28 passed**. Real
held Python created and ran a real temporary venv; the second Python hop retained
the venv identity. This executor has `CapEff=0`, so full setpriv credential
transition was not validated here. Root-owned ELF tests explicitly skip on an
ordinary CI account; two permission-independent rejection tests still run there.
The exact published commit must additionally complete the ordinary full source
and installed CI gates. These component results do not establish field PASS.

`installation.program_execution_binding` is implemented. Remaining code gaps are
current-guest admission, preparation's current-capacity collectors, complete
shared-pool peak accounting, frozen installer internal deadlines and aggregate
usage/peak evidence. Continue those core items before D4 release review. The
oversized development ancestor is a reference, not a deployable replacement.

The release allowlist stays empty. This followup issued no field package, marker,
request, SSH command or H01/Q4/H11 run. Existing guest state was not re-observed.
No reinstall, cleanup or automatic retry was performed. Namespace/watchdog and
other side features remain paused; production E3 remains restricted.

## Current preparation adapter followup

The current implementation D is `0c786ac2389291f488c60ccc32e7eb468d5e30d0`, tree
`5579ae72c83cd928e3e21e13944ad65924a6b82f`, directly following `ca4199e2` below.
This is continued D2 work under the existing core amendment, not a new Gate,
completed D1–D4, or field acceptance. The original R was read directly again.
The exact Git-blob verifier passed both independent C ancestry chains and the
unchanged A document/B decision digests. The approved runtime candidate, wheel,
projection, budgets, deadlines and conditional single F1 remain unchanged.

The selected dispatcher now contains the existing-account preparation adapter:

- Verify installation, current-capacity dependencies, persisted intent, retained
  objects, unused project IDs and parent identities before creating case resources.
- Create only the case/reservation ancestry, persist the preparation preimage,
  then create the fixed directories and seven quota roots. Limit mutation accepts
  only the original 21 IDs and their original 1 MiB/128-inode limits.
- Recheck retained inputs and quota inventory, invoke the original candidate
  constructors, save policy/authority, and initialize one empty ledger through
  the bounded ordinary child. Existing or partial objects are retained, not
  overwritten, cleared or retried. H11 recovery still uses its own origin ledger;
  this preparation entry is not called again during recovery.
- Guard individual directory/file/quota effect calls against the original paired
  clocks. Late-opened descriptors are retained for closure; a late return stops
  subsequent writes. This does not prove the still-incomplete installer/collector
  internals or that blocking kernel calls always return on time.

The dispatcher is **261960 / 262144 bytes**, SHA-256
`ca0efe77e6651a95afaa7a4853caf5f085b50e584fa96dbfc6050b257d02b4c9`.
The unchanged loader is 2160/8192 bytes and bootstrap is 49102/49152 bytes.
Common preparation error prefixes and concise comments keep the code within the
existing limit. No existing predicate was dropped, no extra field module was
introduced, and no byte ceiling was raised.
Only 184 dispatcher bytes remain. Remaining integration needs a reviewable
refactor within the same boundary, not restoration of the oversized checkpoint.

Validation of this D's source/test bytes: preparation **70 passed**; core
**567 passed / 9 skipped**; full source **4478 passed / 100 skipped, 434.30 s**.
The full report is retained locally at
`lh-core-preparation-source.GgTh1C/results.xml`, SHA-256
`9ba029170912963c5006896fac7c1142f983d8b2d63c22032b18c33278fb82aa`.
The new tests exercise actual temporary-file effects and one actual SQLite child
under the existing ordinary test account. Quota/service observations and
orchestration OS facts are explicit test doubles; they are not a guest measurement.
Initial failures retained in the execution transcript concerned an unnecessary
O_NOATIME requirement on directory traversal, then fixture file protection and
synthetic inode aliasing. Regular preparation-file O_NOATIME and the production
ownership/alias checks remain; no privilege fallback was introduced.

An isolated clone of the exact D built and installed a test wheel, then the
existing installed verifier returned **PASS, 94 checks / 292 commands**. The
local report `lh-core-preparation-installed.IouVnM/acceptance/report.json` has
SHA-256 `56a9d8bc94bc2e0cb3f54554d01f957daabed8f2c86b03b342a9c3852f8cc684`;
the test wheel SHA-256 is
`dd51d4c7ce98c30fcb527a88504cc9700290a84a474785d920a0a5c1fd37e7e6`.
This disposable installation does not replace the frozen field wheel or prove
an E3 business chain. At record time, the exact D's [CI run](https://github.com/kongbu0621/infra-local-hand/actions/runs/37191629497)
had passed classification; Linux and Windows semantic jobs were still running.
Skipped, pending and modeled checks are not field PASS or independent review.

### Direct remaining blockers

`admit()` still refuses: current guest, policy entities and historical obligations
must be independently collected and charged per live pool. Preparation refuses
before clock/file effects if its three current-capacity collectors are missing;
these are now named `preparation.current_capacity_collectors` in readiness.
Shared installation peak/usage accounting, installer internal deadlines and
executable binding also remain unproved. Neither the new adapter nor tests
remove these release predicates. Independent review and the complete original D4
checks still precede final private package construction and field admission.

The release allowlist is empty, the field package is null/NOT_ISSUED, and this
followup issued no marker, carrier request, H01, Q4 or H11. No real field task was
executed and no business result/evidence was collected. Existing physical guest
state was not newly observed; absence of a marker cannot be inferred from this
record. namespace/watchdog remain paused and production E3 remains restricted.

## Retained ca4199e2 checkpoint

This commit advances the approved core only. It does not declare Q2 accepted,
production support, or permission to ignore any existing field check. The runtime
candidate, wheel/projection identities, field protocol and resource limits remain
unchanged. The field allowlist remains empty.

Main now contains executable adapters for:

- H01 original normal handoff, Q4 running cancellation, and H11 same-ledger recovery;
- protected candidate module loading, including delayed imports;
- empty-ledger admission before submit and H01/Q4 closed-ledger logical export;
- original request, quota, phase, stage and controller fact extraction;
- preparation contract construction and original candidate handoff decoding.

The adapters retain single-attempt execution, original dual-clock deadlines,
wait4 and both pipe EOFs, original ledger identity, exact source sets and strict
result/stop/seal checks. H11 does not read a business result or export the ledger.
Prepared source objects are reread around the original owner execution.

Two concrete implementation defects were corrected: the root-owned session
container permits ordinary traversal while carrier/intents remain private; the
controller's original deadline is bounded by, rather than incorrectly equated to,
the longer owner deadline. The original controller envelope is still validated.
Independent review also reproduced SQLite creating WAL/SHM sidecars during an H11
`mode=ro` read. The selected-main reader now uses the already-quiescent immutable
held-fd view and rechecks both sidecars and file identity afterward. A real WAL
fixture and a pathname replacement regression cover that repair.

### Boundary at ca4199e2

Current-guest `admit()` and actual `prepare_case()` remain fail-closed in main.
Their full development implementation is retained in commit
`f342f325e5fc4ac2fc27795045813735fc1a2302`, a non-releasable ancestor, with admission
and capacity tests. Do not restore that whole dispatcher as a field artifact:
its 326139 bytes exceed the unchanged 262144-byte maximum.

Main selects the complete core execution/evidence dependency closure within that
maximum. Removing the oversized integration from the field artifact does not
authorize an alternate runtime module, compressed executable payload, larger
limit, fake admission result, or skipped predicate. The historical development
checkpoint is preserved to avoid repeating the work.

Guest shared installation physical allocation peak and complete usage accounting
remain unproven. Directory sampling is not a complete peak measurement. Existing
installation deadline/executable-binding blockers remain. Q4 must retain real
original stage InvocationIDs; do not invent a result-reader identity when running
cancellation precedes its startup.

### Validation and handoff at ca4199e2

The first selected-main core run produced **532 passed, 1 failed**. The unchanged
writer process-identity test fails because this cloud execution surface exposes
different `/proc/self/stat` and `os.getpid()` identities. The original assertion is
retained for ordinary-host CI. All field-size assertions passed. Further CI results
must identify the exact published commit; these local results are not field PASS.

The new SQLite/persistence fixtures use the actual test account. The production
writer continues to require its original owner. The root-owned carrier directory
test explicitly requires root. A local ordinary-user test launch was unavailable
(`runuser` could not set supplementary groups); ordinary-account validation remains
the GitHub runner's responsibility.

Local Codex should continue these core steps, in order:

1. Fetch main and preserve these fixes. Compare the development ancestor for the
   `_admit_*`, `_capacity_*`, actual preparation and associated tests; integrate
   them only with a reviewable implementation that remains within the existing
   field boundary. Do not replace the selected dispatcher wholesale.
2. Close real shared-pool/usage evidence and the remaining installation guards.
   Keep observed values and enforced limits distinct; never fill unknown peaks,
   PID counts or unit counts with zeros or inferred success.
3. Re-run core and installed checks on the exact resulting commit, then review
   field readiness and the original source/identity/deadline bindings.
4. Only after every release condition is satisfied, use the existing authorized
   single F1 sequence on the original fixture. Preserve original evidence and
   identifiers. No reinstall, cleanup, replacement identity or automatic retry
   is authorized by this progress note.

No side-feature development, SSH connection or actual original-chain execution
was performed in this turn.
