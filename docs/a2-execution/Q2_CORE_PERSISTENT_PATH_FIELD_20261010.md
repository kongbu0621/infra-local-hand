# PP1 原核心接续实现与返回

授权为 [persistent-path baseline](../governance/Q2_CORE_PERSISTENT_PATH_CONTINUATION_BASELINE.md)，
Owner 事件 `LH-Q2-CORE-PERSISTENT-PATH-CONTINUATION-CLOSURE-20261010-01`。
准确 A 三文档原字节保持，独立 C 为 `d77315e5792c54c406b000b2179ef179ec900c94`。
本实现系列下降自 C；本节是实现记录，不是现场成功或核心验收。

## 最小实现

PR #4 的准确修复 `47183cc310cbab15cf78bdb8f3f26cc935c1fb66` 已经正常 merge commit
合入 main，合入提交 `48a5ba15bc61ad930fbea60bfda740aa2db4e4dc`。
A/C 通过 PR #5 正常合入，合入提交 `1bc2122055f0f860cc1350984b92678f3986a106`。
未直接推送 main，未使用管理员 override，未 squash C 与实现。

固定外层归档采用旧 activation 完整字节、旧10c五个实际原件及冻结/终态/完成记录，
共 12 成员、522240 B，在原 524288 B 上限内。只替换原 activation 输入 FD；
旧55原件的 custodian、连续持有协议与 128 FD 上限保持。归档只在内存按固定
USTAR 顺序消费，不解包到文件系统。原 coordinator 3/custodian 0、UNKNOWN、
缺失 post 原件及 H01/Q4/H11 NOT_RUN 均保留，不能解释为新维护成功。

新 manifest v18 通过归档内固定前代 marker 的 `manifest.resume` 及准确摘要引用
完整旧历史；仅一层引用，重建后的 canonical 内容与完整逻辑历史逐字比较。
receipt v18、preflight v17、transition v17、capacity v20、reconciliation v21
及独立 dispatcher 同步更新。旧10a消费者明确使用旧历史格式，避免新字段污染旧证据。
为保留 host 源码原 98304 B 上限，仅将纯 preflight 编解码移入既有 prior 模块。

十六份完整维护义务、两次路径读取及全部准备费用、原核心合计 20809 MiB/6224 inodes；
无退款。两次路径读取原件在原处保持，不进入外层归档或55-FD custody。
NAS discovery/new-job admission 继续关闭，未增加外围功能或现场观察。

## 发布前验证

实际留存输入的离线生命周期验证通过：19 个输入、55 个旧维护原件、20 个旧核心
原件、4 个诊断原件及4个容量原件；无 VM/SSH 查询。工作区版本的静态上界为
marker 52179 B、receipt 44848 B、pre/post argv 47676/52204 B、guest FD 98、
维护交接峰值128、核心准备126。准确 D 冻结后仍须复核，不以此替代最终发行门槛。

归档篡改、错误来源/完成/历史、缺失/循环引用、两个完成消费者及完整费用有离线
回归覆盖。两个新私有调用器的实际结果写入与门控经18项合成测试通过，包括已有
diagnostic 的完整保留、create-only 拒绝重复、一次 preflight/PASS 同窗 execute、
独立完成消费者后才生成 PP3 可执行门控。旧调用器保持不变。

首轮完整 Q2 检查为5123通过、88跳过、8个旧测试输入/断言失败：它们仍将新压缩引用
直接作为完整 resume。已修正测试为从固定前代还原或使用已验证逻辑输入，不改变
生产校验。全库回归、准确 D 首次 CI、独立安装、最终来源准备和双调用器冻结尚待完成。
归档准备脚本初次加载因错误的 Inputs 模块定位停止，尚未访问原件或创建准备池；
修正后一次实际准备完成，原错误记录私有保留。没有因此创建新现场窗口。

首个本地实现提交 `eb8384174253d21b8731d3b01fb0aa8148b3676e` 的真实准确来源核对
在 `GROWTH_DEPENDENCY_CHANGED` 停止：维护入口仍将 `q2_core_obligation_inputs.py`
与旧版本比较，无法采用已批准的 PR #4 分类修复。该单个依赖现在准确绑定到
`47183cc310cbab15cf78bdb8f3f26cc935c1fb66`；其他固定依赖和完整 A/C/D 校验不变。
此发现来自保留来源与 Git 字节，无新现场观察。原本地提交/失败日志保留，尚未推送
实现 CI 或消耗 PP2。独立 wheel 构建改在准确提交的隔离 checkout 完成，保留用户
工作区的既有未跟踪条目，不改动构建器的 clean-source 要求。

此记录版本：PP1 IN_PROGRESS，PP2 NOT_ISSUED，PP3/H01/Q4/H11 NOT_RUN。
只有完整 PP1 后执行本批唯一10d；其完整成功原件及实际 coordinator/custodian
完成通过独立校验，才发行原未发行07a。失败/未知立即停止并保留，无重试或补采。

## 最终 PP1 冻结

最终 D `a3f9dbeca268de80124f524ccee4f1437bd61784` 下降自独立 C，保留初始实现
`eb8384174253d21b8731d3b01fb0aa8148b3676e` 及真实来源核对失败。PR #6 通过正常
merge commit `e8868806dfc9ef413177420eb1157bcd4131da07` 合入 main。
其自身首次 CI [38052327972](https://github.com/kongbu0621/infra-local-hand/actions/runs/38052327972)，
attempt 1，head 为准确 D，三项全部成功；没有用 rerun 替换首次记录。

- Linux：源码7612通过/89跳过，独立 cgroup fixture 另有16项通过；独立安装94项
  检查/292条命令通过。Windows：1940通过/1384跳过，独立安装10项检查/10条命令通过。
- 本地完整回归7561通过/140跳过；这是依赖 pin 修正前的实现，最后唯一源码差异
  另经54项针对性检查、准确 D 真实来源验证以及上述准确 D CI 覆盖。
  本地准确 D 独立安装94项检查/292条命令通过；最终私有调用器18项合成检查通过。
- 准确 D 的实际留存输入、归档/历史、两个完成消费者、完整 FD 生命周期和大小/费用
  上界核对通过。维护交接峰值128、核心准备126；synthetic transition 53861 B、
  approved input 438037 B、核心包上界19480174 B，原限额不变。未提前创建核心现场包。
- 最终13个受保护来源副本准备占704512 B/16 inodes；固定归档准备占532480 B/3 inodes。
  两个池均在各自原1 MiB/32-inode及 CPU/RSS/时间预算内。原件和旧准备费用不退款。
- 42437 B 的私有 `pp1-freeze.json` 绑定12个调用器/依赖、批准记录、准确提交/CI/安装、
  固定出站槽、全部来源、两次路径读取原件核对及预算。旧文件不改，两个新调用器冻结。

PP1 完成；以下是冻结后的唯一 PP2 实际返回，不将准备成功解释为维护成功。

## 唯一 PP2 返回与终态

新 `lhqjgrow-20261010d` 调用器只调用一次。一次 local preflight 返回
`LOCAL_PREFLIGHT_PASSED`，随后同窗 execute 一次；新 marker 已创建，pre SSH 请求为1。
execute 返回 `STOP_AND_RETAIN / GROWTH_REPORT_MISSING`，调用器实际 exit 3。
实际 coordinator completion 为 returncode 3，custodian returncode 0；receipt 摘要绑定一致。
聚合完成用量为 CPU 2280254000 ns / RSS upper 157270016 B，在原上限内。

已捕获 guest stderr 与本次 nonce/source/session 绑定，其 failure 为
`PRE_RUNTIME_PREPARATION / GROWTH_PATH_PROTECTION`；已有诊断完整穿过
receipt、调用结果和 summary。persistent_inventory 的 path_index 73、component_index 3
均为零基，operation 为 `qualify_component`，对应最后一级对象。该对象已打开并进入
既有 fstat 后的所有者/写权限谓词；errno 为 null，实际 UID/GID/mode 未记录，不能
判定是所有者集合不符、group/other write 位，或二者。它不是 ENOENT 返回。

guest `actions_started` 为 runtime_preparation；已完成的 guard_units 命令有 exit 0/
双 EOF。其余配置/目录/父域/池/manager 记录为空，不能据此声称准备完成。失败时
stderr EOF 为 false，remote_exit 为 UNKNOWN；不以 guest 自述或 custodian 0 冒充远端成功。
未发送 poweroff token，未备份/增长 journal，未维护重启，未发行原核心包。

实际五原件：marker、events、空 pre stdout、pre stderr、receipt。post stdout/stderr、
maintenance pidfile 和 journal backup 均不存在；没有伪造补件。五原件、大小/摘要索引、
caller stdout/stderr、实际退出及终态均私有保留。原 immutable freeze 与12个哈希保持；
另写 `PP2_MAINTENANCE_CONSUMED_FAILED_PP3_NOT_RUN` 终态 gate，阻止两调用器重放。

当前 PP2 **CONSUMED_FAILED / STOP_AND_RETAIN**；PP3/H01/Q4/H11 **NOT_RUN**。
维护已消费代数为14；old09c/old10b仍为调用过但未消费的预检。16份完整维护义务、
原核心、读取与准备费用全部保持20809 MiB/6224 inodes，不退款。本次没有平台审批拒绝。

## 仅保留来源的后续定位

只用本次已保存 marker/guest 返回，将索引、长度、摘要定位到原配额边界证据对象的
最后一级；未读取当前 guest 元数据。随后校验原六个固定 archive/26个准确文档和两个
原计划/准备文档，得到九个准确引用：七个 plan 的 `retained` 项及原 before/after 根身份。
这证明它属于原来明确保留的证据，不是 PR #4 修正的两个未发行位置；不能将该修复扩大为
删除此必备对象。上述旧根身份只有原路径/device/inode，不能填补当前 UID/mode 的缺失。

该离线来源核对已完成，私有映射保留。没有额外 SSH、探测、chmod/chown、权限放宽、
服务停止、清理、回滚、恢复或新窗口。已获批实现修复和准备均已交付，但核心仍未跑通。
本批失败即停止的边界不允许另读当前权限或再次执行；下一现场动作需要另一个准确、
有界的 Owner 决定，不能从本次测试、CI、普通修复或旧“批准”中推导新窗口。

## 所有者与权限返回的普通修复

已确认的源码缺口是 `open_path` 丢弃了触发拒绝的同一次 `fstat` 值。现在错误返回
保留该样本的 device/inode、UID/GID/mode、允许 UID 集合与禁止的写位；原拒绝谓词、
路径集合、读取次数及资源上限不变。进入下一分量前清空样本，open/fstat 失败不能
误带上一级目录的元数据。原 guest→pipe→coordinator receipt 接线保留这些字段，
错误返回仍使用原大小上限；没有新增现场读取或改动旧返回。

正常宿主环境相关回归433项通过，覆盖所有者错误、group/other write、同时不符、
根/祖先拒绝、各级 fstat 失败、真实 FD 关闭、真实管道与 receipt 写入，以及既有
NAS discovery/new-job admission 屏蔽。此前受限环境428通过/5失败，五个既有配置
测试因祖先目录身份提前拒绝；原日志保留，未修改这些测试或生产权限检查。

这项修复不能补回旧10d未记录的实际 UID/mode，不改变 PP2 已消费失败和
H01/Q4/H11 NOT_RUN。定位当前具体权限需要新的固定对象读取；现有调用器不可重放。

## 获准固定对象读取完成

Owner 对相邻完整请求回复“批准”，事件为
`LH-CORE-PATH-PROTECTION-READ-20261010-01`，唯一标识 `lhqprotect-20261010a`。
请求明确给出固定 VM 目的地、三个源码载荷、一个准确证据对象及身份绑定；完整请求与
原回复私有保留。本次只批准 PR #8 正常合入和一次当前元数据读取，没有批准维护、
权限/所有者修改或核心发行。批内启用、冻结、执行与保留不再逐项询问。

[PR #8](https://github.com/kongbu0621/infra-local-hand/pull/8) 的准确修复 D
`f1481261fdd05ba4641c89c04ec10a6baae1fea7`、tree
`804b23c365ad19fe1c09ec553798e0a58e5e03a2`，已通过正常 merge commit
`860424779e90df9d952b5986a2d1839a18747dc9` 合入 main。
其首次 CI [38054688735](https://github.com/kongbu0621/infra-local-hand/actions/runs/38054688735)，
attempt 1，三项成功：Linux 7622通过/89跳过，另有 root fixture 16项通过，独立安装
94检查/292命令通过；Windows 1940通过/1384跳过，独立安装10检查/10命令通过。
未直接推 main、使用管理员 override 或 rerun 替换首次记录。

私有候选的19项实际本地文件/管道流程与12项 guest/loader 检查通过；调用器 main 和
guest 已测字节保持，只启用已审直接入口并绑定实际批准。原 prepared freeze 保留，
另有最终3844 B immutable freeze 绑定准确来源、首 CI、合入、准备费、载荷与原限额。
准备池实际856064 B/28 inodes；单路径输入502 B，SSH argv 47803 B，合成峰值41 FD。
原 CPU120秒、RSS512 MiB、FD128 和120秒窗口保持。source/output各1 MiB/32 inodes，
旧费用不退款，合计20811 MiB/6288 inodes；维护消费代数仍为14，完整维护义务仍为16份。

唯一调用器实际 exit 0，marker 已创建，SSH calls 为1。结果为
`CURRENT_OBJECT_OBSERVED`：guest returncode 0、stdout/stderr 双 EOF、两层 stderr 均空，
errors 为空，固定 host/VM 身份前后一致，guest boot 两次绑定一致。
remote exit 为 `REPORTED_HELPER_RETURN_WITH_SSH_EOF`。
对象当前写位谓词通过，**只有所有者不在原允许集合内**；保护结果仍为 `REJECTED`。
当前 device/inode 与旧引用相同，不能据此证明内容连续性或所有者合法性；本次新样本
也不能倒填旧10d的缺失字段。原始路径、UID/GID/mode、device/inode 等机器元数据保持私有。

聚合 CPU 1528398999 ns、RSS upper 430723072 B，在原上限内；覆盖范围是 guest 到报告、
host 到最后一次检查，不将其夸大为完整生命周期逐时测量。guest commands 与 maintenance
actions 均为0。没有 chmod/chown、内容修改、poweroff、journal 增长、重启或核心包发行。

八份实际原件为 marker、guest stdout/stderr、result、caller stdout/stderr、实际顶层
完成记录和启动请求记录；启动请求不冒充完成。原件及索引私有保留。prepared/final
freeze 保持原字节，另写终态 `CONSUMED_READ_COMPLETE_PROTECTION_REJECTED`，禁止重放。
本次批准已完成，未发生新的平台审批拒绝。PP2 旧失败不变；H01/Q4/H11 仍 **NOT_RUN**。

## 所有者来源的离线核对

本次只读保留的本地源码：原 Q1 创建脚本将该目录及关联 canary 交给专用历史账户，
分别设置受保护目录/文件权限；后续脚本核对并保持已有所有权。脚本通过运行时账户查询
取得 UID/GID，没有固定本次观察到的数值。它们可解释设计意图，不能单独证明原执行、
当前账户名映射或当前数字身份的可信性。脚本摘要及准确语句位置已私有固定，未执行脚本。
已准确 pin 的 Q1 handoff 原报告另有两个历史根由不同专用账户持有；不能套用当前账户
集合来解释全部历史对象，也不能由此推断这些根当前状态。

当前实现对全部 essential_paths 统一使用当前 owner 集合，因此缺少显式的历史对象
所有权绑定。下一修复应将历史对象与其可信来源、准确路径和身份逐项绑定，维护生产方
与独立核心消费者采用同一规则，并保留严格祖先、禁止写位、完整路径覆盖、process/writer
和原预算检查。当前材料尚不能充当完整的历史 UID/GID 授权表；不得直接全局加入本次
UID、删除该证据对象或改写其所有权。该策略变更及后续现场窗口均未由本次读取授权。
已有八原件和离线核对可供下一步使用，不重复读取或重放。NAS 新入口继续关闭，外围工作暂停。

## 核心身份绑定修复候选（未发行）

Owner 随后明确要求直接修复并只推进核心。本候选把历史配额证据目录的校验接到实际
生产方和两个完成消费者，未新增现场查询或外围功能。原计划已有四个准确的保留配额根；
纯变换先验证整份原计划摘要，再固定四条原 path/device/inode 记录的完整有序摘要。
输入派生提交为 `4e9b9cc225285aa9a2d785b23e8344d9a120d5eb`，维护源验证准确引用它。
没有从当前观察的 UID 猜账户名，也没有将任何旧账户加入全局允许集合。

输入 v5 必须携带完整绑定，删除、追加、改名、改身份、覆盖缺项或降回 v4 均拒绝。
只有四个准确命中的只读目录叶节点按原设备/inode 核验；祖先与其他路径仍按原 owner
规则校验，禁止 group/other write、NOFOLLOW/NOATIME、类型及文件系统检查保留。
这是明确的准入模型变化：四个历史叶节点的当前 owner 白名单谓词被原对象身份绑定
和当前元数据向前保持替代，不宣称原历史 UID/GID 已经恢复或验证。

既有两次 fstat 之间若身份或 owner/group/mode 变化立即拒绝，没有增加读取或命令。
当前四根的 UID/GID/mode、device/inode、路径摘要和 filesystem UUID 进入独立摘要；
第一次既有扫描固定它，准备后的复查、关机前复查、post 准备/扩容前及完成复查都必须
相同。pre/post 报告验证与 host/独立 dispatcher 的 transition v18 同时要求完整四根、
原计划/四根摘要、相同前后样本及准确报告绑定。旧 transition v17 不能代替新证据。

实际保留来源的离线核对通过：四根全部来自准确原计划；当前已保存的那个拒绝样本
与其中一个原对象的设备/inode 相同。其余三个根当前是否匹配仍须未来获准批次检查，
本次没有补采。178条必需路径、230条保护路径、19/7/7声明均保持。
guest 源码97945 B，仍在98304 B内；原 pre descriptor 增加固定绑定后为28700 B，
合成目的地的 pre argv canonical 为49118 B，小于65536 B。这只是离线形状/大小核对，
不是新准确来源冻结、post 上界、完整现场生命周期或新窗口准入。

针对性回归首轮127项通过，覆盖真实文件描述符、旧规则误拒绝、四根身份通过以及 owner/
group/mode 漂移、两次 stat 间变化、symlink、缺失、弱祖先、错误设备/inode、绑定篡改和
两侧完成消费拒绝。首轮全部 Q2 为5151通过/88跳过/25失败：24项使用公共合成描述符
但尚未采用新的四根摘要；另1项仍假定任何当前 dispatcher 都已发行。修正公共夹具的
摘要传播，并使发行测试明确验证本候选仍被实际 gate 拒绝；生产 release pin 未变。
中间回归344通过/1失败定位到隔离加载的第二个 dispatcher 夹具未同步，已补齐同一边界。
随后全部 Q2及 NAS/broker 为5240通过/88跳过/1失败，唯一剩余断言仍指向被替换的旧输入
派生提交；现已准确引用上述 `4e9b9cc`，不修改生产源码。最终身份、依赖来源与发行闸门
针对性回归112项通过。全部真实返回保留，准确提交 CI 实际结果随候选 PR 留存。

候选 `04990fcbb016cfe07925b30737ba99ff900c10f2` 的首次 CI `38058671049` attempt 1
中，Windows 源码测试为1877通过/1385跳过/37失败/26 setup errors；新增公共夹具主动
导入 Linux dispatcher，触发 Windows 缺少 `resource`。修正仅让夹具更新已经加载的
平台模块及显式传入的 dispatcher，不改生产源码或减少测试。禁止 `resource` 导入的
纯输入回归38项通过，Linux 路径/消费者/发行闸门相关181项通过；旧 CI 失败保留。

此前测试命令含一个不存在的额外 glob，退出4且零测试；修正测试路径后才产生上述结果。
没有将该命令计为测试成功。原八读取原件、prepared/final freezes、所有旧调用器和已消费
维护终态保持；没有 SSH、chmod/chown、维护/关机/扩容/重启或核心包发行。
当前核心 dispatcher 放行摘要保持旧准确值，本候选明确不能发行核心包。

本候选提供可审查的核心修复；采用这项准入变化和新的维护窗口仍需准确接续范围，包含
old10d实际原件、完整费用和最终来源/调用器冻结。不能用本次代码或测试重放旧10d、
旧只读入口或直接执行07a。H01/Q4/H11仍为NOT_RUN，外围工作保持暂停。
