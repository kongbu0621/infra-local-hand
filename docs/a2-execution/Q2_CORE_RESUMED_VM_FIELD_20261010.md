# 当前 VM 的原核心接续

范围 `LH-Q2-CORE-RESUMED-VM-v1`，批准事件
`LH-Q2-CORE-RESUMED-VM-CLOSURE-20261010-01`。准确 A 与独立 C 的关系见
[基线](../governance/Q2_CORE_RESUMED_VM_BASELINE.md)。A 三文档保持原字节。

## RC1 接线

旧安装/v1、本次已完成启动、RC2 当前 guest 返回分别验证，生成 activation/v2。
新维护及独立核心消费者均拒绝用 v1 或缺失当前证明发行本批次。
10b 九份本地返回、freeze、失败及终态保持；未消费的预检不伪造维护原件。
旧 10a 的原始 resume 单独还原，不能带入后续 10b 的字段。

RC2 的固定只读命令查询当前内核、准确已安装包/版本及完整性、quota_v2 元数据、
仅展示的模块依赖，以及原 quota 挂载 UUID/文件系统/选项。挂载目标来自旧命令的
准确参数；旧报告没有设备名，不能补造设备名再声称它是历史事实。
固定宿主/VM/SSH 信任、源码、批准、nonce、原始流、前后身份与实际顶层完成均参与核验。
无安装、模块加载、启动、服务变更、扫描或重试。

组合归档仅存一份相同保护源码，用两个固定摘要引用无损还原旧索引的逻辑成员。
严格拒绝链接、重复/额外成员、PAX 扩展及非零尾数据。它复用原 activation 的一个 FD。
真实保留来源与合成未来返回的组合为 348160 B；按 RC2 各文件最大允许返回计算为
512000 B，均在原 524288 B 内。当前投影形状为 1864 B，原上限 4096 B 不变。
上述合成返回不是现场证据，不证明 guest 已通过。

保持十五份完整维护义务及 RC2 独立成本，合计 19505 MiB/5598 inodes。
保留 55 件 custodian、原 128 FD/256 MiB AS、CPU/RSS/子进程及全部 payload 上限。
维护交接峰值 128，核心准备上界 126；原件持有、移交、真实隔离管道和终态均需通过。

已验证私有调用器的实际失败/成功/重放控制流程，以及维护原件独立接受器和最终
数据槽写入器。真实 SSH、维护和核心操作均被合成返回替代；缺少顶层完成、身份/源码
漂移、截断和失败不能放行后续阶段。旧 caller 和原件不改。

## 执行状态

本实现记录时 RC1 验证中；准确 D 发布、自己的首次 CI、独立安装及三个 caller 的
最终冻结尚未完成。RC2/RC3 NOT_ISSUED，RC4/H01/Q4/H11 NOT_RUN。
完整 RC2 返回填入后，须以同一源码再次核验大小与数据冻结，才能调用唯一 10c。
完整维护原件和实际 coordinator completion 通过后，才可执行原 07a H01→Q4→H11。


首次候选 `0312b0002b538b340f5117ea393b7e54bb5a85d8` 本地完整回归为
7480 passed / 139 skipped；准确候选的独立干净构建与安装通过 94 检查/292 命令。
其首次 CI `38032801660` attempt 1 的 Windows 收集失败：新增 Linux 专用测试在
平台检查之前导入了依赖 `resource` 的 dispatcher。修正仅补齐该测试模块的 Linux
平台边界，与既有相同类型测试一致；不改生产执行、资源上限或证据判断。
保留此次失败，新准确候选须取得自己的首次 CI 和独立安装，不重跑旧 CI 代替。
此时 RC2/RC3 仍未发行，核心三案仍 NOT_RUN。


候选 `ca52a221f21f955065af37f52bed3f3c54000900` 首次 CI `38033068469` attempt 1
的 Windows 测试进一步报告 19 failed / 1862 passed / 1382 skipped / 26 errors：
统一错误为 `CORE_PRIOR_ACTIVATION_PATH`。离线证据包含 Linux 路径，旧校验使用
宿主 `os.path.normpath`，在 Windows 上将分隔符解释成 Windows 路径。
生产者和独立消费者改用明确 POSIX 规范化，仍拒绝非规范路径、穿越和路径别名。
新 guest 核验源同时将继承的 AS/FD/CPU ceiling 固定为原硬上限；私有传输入口也已
在运行该源码前设置同样上限。未增大任何限额。保留第二次 CI 失败及已通过的
该候选独立安装记录；新的准确 D 仍须完成自己的首次 CI 和独立安装。

## 最终 RC1 冻结与 RC2 返回

最终 D `0eece27637930dfc31f724c7dd1392e11a47cad9`，tree
`a0ecd06f7f8d86ba8d0405f08b27b577dec11423`，下降自独立 C；已发布 main。
其首次 CI `38033862859` attempt 1 三项全部成功：Linux 7531 passed / 89 skipped，
Windows 1908 passed / 1382 skipped，两端独立安装也成功。本地准确 D 的独立干净构建、
安装通过 94 检查/292 命令，路径修复相关检查 261 passed。
此前两个候选的 Linux 均为 7530 passed / 89 skipped，并通过独立安装；各自 Windows
失败仍保留。未用 CI 重跑替换失败，亦未把旧候选的本地全量结果写成最终 D 的结果。

真实保留来源、完整大小/成本和 FD 生命周期复核通过；RC1 最终冻结绑定三个调用器及
十项依赖。归档最坏返回形状仍为 512000 B，交接峰值仍为 128 FD；未提高任何上限。
唯一 RC2 随后调用一次，顶层退出 3，返回 `STOP_AND_RETAIN`，错误
`CaptureError / LOCAL_PARENT`，diagnostic 为 null。SSH 计数为 0，消费标记未创建。
原始返回没有标出具体失败目录，不补造当时目录元数据或 guest 原因。

八份已存在的调用器/输入/返回记录及其索引保留私有；消费标记与两条 guest 原始流
均缺失，不创建空文件补充它们。实际顶层退出与本地 stdout/stderr EOF 另行保留；
EOF 不代表 guest 完成。remote_exit 仍 UNKNOWN，没有 guest report 或新的 activation/v2。
未调用 RC3 维护，未发行 RC4 核心包，H01/Q4/H11 全部 NOT_RUN。
RC2 为 INVOKED_FAILED_UNCONSUMED，终态为 `RC2_LOCAL_INPUT_FAILED_RC3_RC4_NOT_RUN`。
原 RC1 freeze 与十项 caller/dependency 摘要核对不变。十二代已消费维护及全部十五份
维护义务保持；本次不增加维护消费次数。没有重试、补采、清理、恢复或新窗口。

## 返回后的调用器普通修复

仅用已经保存的调用器、批准/冻结文件和仓库源码复核文件打开路径，不进入现场 main，
不读取 VM、端点或 guest。沙箱内复现先在私有输入路径被拒绝；原生环境的独立复核中，
四份私有输入读取通过，随后在工作区 guest 核验源码路径复现同一 `LOCAL_PARENT`。
两次复核分开保留，不把沙箱表现当作原生历史现场事实，也不推断当时具体哪个祖先目录
的权限或所有者。源码表明调用器对工作区源码使用了严格受保护目录遍历；原控制流测试
模拟了这一层，未覆盖真实路径准入。

已准备独立私有修复候选：十四份源码按精确 D 校验后放入私有受保护目录，调用器持有
这些副本的 FD，并继续核对源码字节、名称和身份。目录权限、所有者、链接、原 128 FD/
256 MiB AS 及资源限制保持；没有通过放宽目录保护使工作区路径被接受。既有失败返回
路径增加有界阶段/路径上下文，不新增读取。失败调用器与原始冻结均未修改。

在真实 128 FD/256 MiB AS 下，全部十四份源码的打开、持有、重检通过；可写父目录、
符号链接、名称替换和内容漂移四种反例均被拒绝。候选实际 main 的八组合成成功/失败/
重放控制流通过，SSH、VM 读取和现场调用均为零。候选的直接执行入口被禁用，状态为
UNISSUED_OFFLINE_REPAIR；没有新的执行授权。该普通修复不恢复这次失败的 RC2，也不允许
进入 RC3/RC4。后续只保留该核心阻塞项，不新增外围功能或独立诊断项目。

## 普通修复的完整本地准入补验

Owner 再次要求直接修复并推进核心后，使用同一私有候选完成六组完整控制流补验。
这次保留真实目录遍历、文件打开/持有/重检、准确 Git 来源、资源计量、结果保存与
finally；仅 VM 身份、SSH 及密钥命令的现场效应由合成 peer 替代。所有输入与输出
位于隔离私有夹具，未使用实际私钥执行命令，没有 VM/guest 观察或现场调用。

成功、可写源码父目录、源码变更、持有后内容漂移、传输失败和 EOF 缺失六种场景均
符合预期；正常流程实际持有十四份源码，原 128 FD/256 MiB AS 下通过，并拒绝重放。
此前失败记录、终态及十项冻结依赖摘要保持。外围发现隐藏、新 NAS 作业前置拒绝及
历史记录可查询/取消的四项回归通过；未扩展或重写外围功能。

下一次现场操作需要与旧失败分开的有限接续。已固定[准确 A](../governance/Q2_CORE_PROTECTED_SOURCE_BASELINE.md)，
只覆盖修复采用/验证、一次新 guest 核验及条件执行原维护/核心；当前 OPEN，尚无新的
Owner B/C。没有把本轮继续推进的请求补写成尚未形成时的准确 A 批准。

## PS1：受保护源码接入的批准采用

准确 A `eabffdbfbdc1c2d041f35dd9371714625380bf3f` 经 Owner 相邻回复“批准”，
独立 C `a6532946abf9e4f1364622398112e681c35de2ec` 只记录 PS1–PS3 关闭，保留 A
三文档原字节。当前实现下降自 C，继续原 10c 维护与 07a 核心任务。

私有新调用器采用原普通修复：十四份源码在私有受保护目录逐项打开、持有、重检，
与准确 D 和冻结 pins 比较。原所有者、权限、单链接、大小、O_NOFOLLOW 和资源条件
全部保留。旧 RC2 八件、原 RC1 freeze/terminal 及十项依赖离线校验，失败事实与摘要
同时绑定新批准和冻结；旧件不进入新 guest 成功槽，也不增加到 55-FD custody。

producer 与独立消费者改用 PS 授权；activation/v2 增加经验证的源码准备/旧失败绑定
摘要。原 RC 历史常量和原件保持。当前 manifest/receipt 为 v17、preflight v16、
transition v16、host-capacity v19、reconciliation/historical-capacity v20。十五维护义务
加原核心、新旧 guest 读取及一次最终源码准备共 19507 MiB/5662 inodes，不退款、不提限。

首轮相关验证在 preflight 解析处发现旧 RC 权限比较，已对齐 PS 后重新通过 186 项。
测试包含重哈希后错误旧授权、虚构 marker、缺失来源、准备费用超界及独立消费者拒绝。
保留原件与合成未来成功组合的归档最大值仍为 512000 B，小于 524288 B；投影 1972 B。
工作区版本的原件/生命周期核算通过；准确 D 的最终核算、首次 CI、独立安装及三调用器
冻结尚待完成。此段不宣称 PS1 完成，不发行 PS2/PS3，也不把测试当作核心 PASS。


候选 `11e855d0bd4313b586211b2724b152d7755e5ebd` 的完整本地回归为
7489 passed / 139 skipped / 1 failed；失败仅为批准缺失用例仍期待旧
`GROWTH_RC_NOT_AUTHORIZED`，实际正确拒绝并返回 `GROWTH_PS_NOT_AUTHORIZED`。
下一提交只对齐测试期待并覆盖 PS 批准缺失；生产实现和拒绝行为不改。
旧失败日志保留，新提交仍须取得自己的首次 CI 与独立安装，不能复用旧提交成功标记。

## PS1 最终冻结与 PS2/PS3 实际返回

最终 D `b10cdae51f098b12e62c7ca5fbd971b0dab7b56e` 下降自独立 C，未 squash。
[自己的首次 CI 38040883977](https://github.com/kongbu0621/infra-local-hand/actions/runs/38040883977)
attempt 1 三项成功：Linux 7541 passed / 89 skipped，Windows 1908 passed / 1382 skipped。
Linux CI 和本地独立安装各 94 checks / 292 commands；Windows 独立安装 10 / 10。
此前候选 11e855d 的首次 CI 38040299309 保留为失败：Linux 7539 passed / 89 skipped /
1 failed，仍是旧错误名断言；Windows 1908 passed / 1382 skipped 且独立安装通过。
最终改动只有该测试和脱敏说明，生产实现未变；修正后相关 72 项通过。

最终十四份源码 647328 B；准备池实际计入 692224 B、17 inodes，CPU 306556999 ns、
RSS 峰值 45613056 B、双时钟 elapsed 374524556 ns，均在原上限内。全部源码按准确 D
准备、打开持有并重检；三调用器及十二项依赖形成不可变 PS1 freeze。准确来源的
真实本地 I/O 六组、维护/核心条件接续、完整原件消费和尺寸/FD 验证均通过。
PS1 COMPLETE；旧 RC2 八件、旧冻结及十项依赖、终态保持原样。

PS2 唯一调用实际退出 0，一次 SSH，两个流完整 EOF；原六命令核验通过，返回
`CURRENT_GUEST_VERIFIED`，host/VM 前后身份一致。没有启动、安装、模块加载或重试。
原始流、调用器实际顶层完成及新源码准备原件均保留私有；成功归档仅装入本次 guest
返回，旧 RC2 失败通过新批准/冻结绑定，未伪称被归档或 custodian 连续持有。

首次离线 finalizer 使用了缺少 pytest 的独立安装解释器，在剩余边界检查导入时退出 1；
不是新的 guest 调用失败。四个已写数据输出及失败日志保留。随后使用已验证离线环境，
重新计算冻结代码的只读前缀并逐字节比较既存四件，执行同一冻结代码尚未完成的后缀。
没有改冻结代码、mock 校验、覆盖原件、重跑 PS2 或新增现场观察。完整边界与依赖重检
通过后才 create-only 写入最终数据冻结和放行门；离线接续顶层退出 0。
实际归档 348160 B，允许的最大归档 512000 B（上限 524288）；v2 投影 1972 B。
实际数据重核 marker 64753 B、receipt 保守形状 44408 B、transition 52253 B、
approved-input 435395 B，核心包保守上界 19477377 B。128-FD 维护交接及 126-FD
核心准备上界保持；这一步没有创建或发行真实核心包。

PS3 原未发行 `lhqjgrow-20261010c` 调用一次。本地 preflight PASS 后同窗 execute；
消费 marker、一次 pre SSH，顶层退出 3，`STOP_AND_RETAIN / GROWTH_REPORT_MISSING`。
pre stdout 0 B，pre stderr 2840 B。已保存 stderr 是结构化 guest/v4 不完整报告：
`PRE_RUNTIME_PREPARATION / GROWTH_GUEST_IO_OR_RUNTIME`、errno 2、context 空。
它仅记录 `runtime_preparation` 意图和成功的 `guard_units` 命令；configs/directories/pools
为空，parents/manager/bus 尚无记录。没有完整 GUEST_QUIET 报告或 poweroff token。
不把“开始准备”当作配置、启动或维护成功，不从 errno 2 推断具体缺失路径。

维护 transport 退出 3；实际 coordinator completion 为 3，custodian child 为 0，
不等于维护成功；`remote_exit` 保持 UNKNOWN。marker、events、空 pre stdout、pre stderr、
receipt 五份实际维护原件及新索引保留私有。post 流、维护 pidfile 和 journal backup
未生成。没有 journal 增长、维护重启或原 07a 核心发行；H01/Q4/H11 均 NOT_RUN。
PS3 为 CONSUMED_FAILED / STOP_AND_RETAIN，terminal 为
`PS3_MAINTENANCE_CONSUMED_FAILED_CORE_NOT_RUN`，原不可变 PS1 freeze 和十二项依赖重检未变。

现在十三代维护已消费，old09c 和 old10b 仍是已调用但未消费的 preflight；十五维护
义务和 19507 MiB/5662 inodes 总义务不退款。当前批次不允许重放任一调用器、重新连接、
补采、放宽数据保护、清理、恢复、另起窗口或发行核心包。已保存返回没有指出具体
缺失对象；不能把它直接归因为运行目录、配置、持久性条目或进程退出竞态。
后续仅可用保留返回/源码离线复核，不以 PS2 或测试成功恢复已经消费的维护许可。

## 10c 返回后的普通错误传递修复

保留源码复核确认，历史计划中的 candidate 回执已有对应保留摘要/原件；没有依据
把它们从 essential_paths 删除。10c 的 errno 2 仍不能归属到某一缺失路径。
普通修复只处理确定的错误传递缺口：受保护路径遍历保留目标 SHA-256、字节数、
从零开始的分量序号及失败操作；persistent 和运行池检查保留当前检查阶段，成功后
清除上下文。运行池 fstat 移入已有 finally 保护，异常时关闭刚打开的 FD。
原检查、读取次数、必需对象集合和失败停止判定不变，不补读或忽略 ENOENT。

不完整 guest 报告携带当前 nonce/source binding。宿主在原 stdout EOF 拒绝点只解析
已经捕获的 stderr：完整 canonical JSON、当前 schema/session/phase/nonce/source
全部相符时，向原 diagnostic 传递原因、阶段和最多 4096 B 的精简诊断。
完整 runtime 记录仍留在原 stderr；无绑定、旧 schema、截断、畸形或超长内容只保留
已捕获字节的摘要/EOF 状态。不会追加 pump、读取、等待或重试，原错误码和远端
UNKNOWN 保持；这不是成功报告，不能放行 poweroff token 或后续维护。

真实临时文件遍历、真实管道和原 coordinator receipt 测试覆盖缺失叶/祖先、路径
保护拒绝、成功后清除上下文、FD 释放及伪造/不完整返回拒绝。最初相关 200 项通过；
扩大回归发现宿主源码超原 98304 B 上限 24 B 和旧 fixture 缺 nonce 的四项失败。
仅缩短注释并补齐该 fixture 的请求绑定，未提高限制或改生产拒绝条件。
修正后同组 1041 passed / 16 skipped，含原 128-FD 隔离生命周期、核心准入、
运行中取消、同任务恢复和 NAS 拒绝回归。两份维护源码分别为 98264/95131 B，
均在原 98304 B 上限内。
保留输入重核确认不可变 PS1 freeze、十二项依赖及五份 10c 原件均未改变。
新 pre bundle 为 34081 B 压缩/145251 B 展开，仍在原上限内；精简宿主诊断上界
4608 B，旧失败 receipt 加此上界为 43308 B，低于 65536 B。
本轮 SSH/现场步骤均为零，PS3 仍已消费失败，H01/Q4/H11 仍 NOT_RUN。

## 固定路径读取的本地返回与预算修复

Owner 对前一请求中“PR #3 合入 main 和一次固定路径只读核验”回复原文“批准”。
新读取事件为 `LH-CORE-RUNTIME-PATH-READ-20261010-01`，标识 `lhqpaths-20261010a`；
完整请求文档、相邻决定绑定和原提案字节保留私有。它只授权沿用固定身份和端点，
读取旧 pre_description 的原 180 个 essential_paths，并仅在全部通过后读取 `/run`
池；不授权维护、服务/VM 变更、旧调用重放或原核心包。

[PR #3](https://github.com/kongbu0621/infra-local-hand/pull/3) 已按本次批准准确快进到
`e03f6a674c3e5592a708b323a14540ac80759095`，GitHub 确认为 merged。
[首次 CI 38043996956](https://github.com/kongbu0621/infra-local-hand/actions/runs/38043996956)
attempt 1 三项成功：Linux 7561 passed / 89 skipped，Windows 1908 passed / 1383 skipped；
Linux 独立安装 94 checks / 292 commands，Windows 10 / 10。此前默认分支发布自动审批
拒绝已由本次明确发布批准解决，没有强制推送或关闭平台保护。

新入口冻结前，12 项真实本地文件持有/重检/管道流程和 8 项客体/源码装载验证通过。
客体使用现有 `GuestInventory.persistent()` 和 `RuntimePreparation.pool()`；首错即停，
没有调用 maintenance pre/run、systemctl、进程扫描或配置/服务变更。
13 份准确来源共 643499 B；准备目录最终 790528 B、25 inodes，低于预留 1 MiB/32。
隔离测试 FD 峰值 41，原上限 128；完整 SSH argv 为 52417 B，低于 65536 B。
源码准备时的沙箱父目录拒绝、随后原生验证的度量断言失败和合成目录权限夹具失败
均保留私有；同一批源码字节的最终验证通过。未用准备失败构造任何现场结果。
新来源准备及输出各预留 1 MiB/32，总义务为 19509 MiB/5726 inodes，无退款。

实际新入口只调用一次，顶层退出 3，`STOP_AND_RETAIN / PATH_READ_HOST_PARTITION`。
拒绝发生在第一个 protected input open 前的 usage 检查，SSH 计数为 0。
记录值为 CPU 55785001 ns、RSS 峰值 395350016 B；入口额外划分的宿主 RSS 子预算
为 268435456 B，而原聚合上限为 536870912 B。因此已知拒绝原因是新增子预算过严；
不能把这个高水位记录解释为当前 RSS，或推断其具体来源。没有 guest 检查、PID 结果
或路径结果；历史 10c 的具体缺失对象仍 UNKNOWN。

实际只有 caller stdout、空 caller stderr、result 和实际 completion 四份原件；
consumed marker、guest stdout、guest stderr 全部缺失，不能虚构为零字节客体原件。
不可变读取 freeze、原件/私有索引和终态分别保留，状态为
`INVOKED_FAILED_UNCONSUMED / STOP_AND_RETAIN`。未重放、重连或补采。
原 PS1 freeze、十二项依赖、五份 10c 原件和原维护终态均未改变。
十三代维护已消费、两次旧未消费 preflight、十五完整维护义务保持；本次读取不是
新的维护代。没有发出维护或核心包，H01/Q4/H11 仍 NOT_RUN。

后续普通修复只准备独立私有候选：宿主 RSS 子预算 448 MiB、客体 64 MiB，合计仍为
原 512 MiB；宿主每进程 AS 256 MiB，客体 AS 收紧至 64 MiB。CPU 保持宿主（含准备）
90 秒加客体 30 秒的原 120 秒总上限，FD 仍为 128，不重置历史核算或替换未知值。
预算拒绝现在通过实际 result 保留测量值、子预算和聚合上限，无额外进程读取。

候选 15 项完整调用流程及 8 项客体/加载验证通过。真实先分配内存再 exec 的启动
用例保留了高于现场返回的 RSS 历史峰值，仍在原总上限内完成合成管道；同时验证超限
必须拒绝。客体完整 180 对象及运行池、首错停止和 FD 关闭在 64 MiB AS 下通过。
这些是离线合成结果，不是 guest PASS。候选入口禁用、批准状态 NOT_APPROVED；
不得重放本次失败调用或把普通修复当作新的读取/维护/核心许可。原外围入口屏蔽保持。

## 新入口准备完成但出站审批拒绝

在具体新读取请求之后，Owner 指示直接修复、直接推进核心并屏蔽外围。助手将该回复
原文绑定到事件 `LH-CORE-RUNTIME-PATH-READ-20261010-02` / `lhqpaths-20261010b` 的准备。
新来源来自已发布 e03f6a6 的独立干净 checkout，13 份源码字节不变；实际准备计量和
完整受保护打开/持有/重检通过。最终输入目录为 786432 B、24 inodes，在本次已列明的
1 MiB/32 准备池内；原准备失败和历史义务不作退款。总预留仍为 19511 MiB/5790 inodes。

真实 caller 原文绑定/来源/文件/管道流程 16 项通过，包含替换 Owner 原文必须拒绝，
以及真实继承高 RSS 峰值的启动验证。客体包装器与之前 8 项 64 MiB 验证的准确字节
相同，合计 24 项相关验证。原 10a 冻结以及 PS1 十二项依赖、五份 10c 原件均未改变。
准备产生独立不可变 freeze；这不等于工具平台准许出站，也不构成任何 guest PASS。

随后调用执行工具时，自动审批在进程创建前拒绝：泛化的直接推进指令未明确授权
这次新 SSH 事件、私有源码/路径载荷及固定 VM 目的地，不能替代具体敏感出站批准。
这不是 caller exit 3，也不是连接拒绝。未创建 caller 或 guest 流、result、completion
或 consumed marker，调用和 SSH 均为零。准备时 authority 文件的 APPROVED 是助手
对回复的解释，已由独立 release gate 明确阻止执行；原文件/冻结保留，不覆盖历史。
没有通过其他包装器、工具或连接方式重试。新事件保持 NOT_ISSUED，要求明确出站
确认后才能继续同一已准备读取，不因此增开窗口、复制源码池或重放任何旧入口。

不依赖现场的核心检查完成：真实本地子进程执行/EOF、运行取消、同任务恢复、结果
读取，以及 NAS 发现隐藏和规划/资源预留前拒绝，共 191 passed / 1 skipped。
首次测试命令因误写一个不存在的测试文件而未收集用例，该返回保留；修正文件名后
运行上述检查。没有新增生产功能或现场观察，H01/Q4/H11 仍 NOT_RUN。

## 明确出站批准后的实际读取与历史路径分类修复

Owner 对相邻请求中明确列出的固定 Q1 VM 目的地、私有源码/路径载荷及唯一一次只读
SSH 回复“批准”。单独记录这次明确出站决定，并放行同一已冻结的 02 / 10b 事件；
没有覆盖此前拒绝、原准备 authority 或不可变 freeze，也未换入口或新增准备池。
执行前复核 13 份源码、调用器、包装器、准备和冻结摘要均不变。工具审批通过后，
原冻结入口仅运行一次，创建 consumed marker、启动一次 SSH，调用器实际退出 3。

返回的请求绑定 guest report 为 `STOP_AND_RETAIN / PERSISTENT /
PATH_READ_IO_OR_RUNTIME`，具体为 `FileNotFoundError` / errno 2；原 180 个目标中
索引 45 的路径，在 `open_component` 索引 1 失败。目标长度/摘要与保留描述逐字对应，
当前缺少的是一个历史启动核对任务的 staging 目录。SSH 返回 3 且两个流完整 EOF，
host/VM 前后身份一致，guest boot、nonce 和来源绑定正确。没有执行外部客体控制命令
或维护动作，`runtime_pool` 尚未到达，不能宣称全部 180 项或运行池检查通过。

主机计量包含准备：CPU 728584001 ns、RSS 峰值 403214336 B；客体报告截止点记录
CPU 35741 us、RSS 峰值 27639808 B。返回内聚合为 764325001 ns / 430854144 B，
标明 `GUEST_THROUGH_REPORT_HOST_THROUGH_LAST_CHECK`，不是客体退出后的完整计量证明。
原聚合 CPU 120 秒/RSS 512 MiB/FD 128 与主机 448 MiB、客体 64 MiB 子限额未提高。

七份实际原件为 caller stdout/stderr、marker、result、guest stdout/stderr 和调用器
顶层 completion；对应私有索引及独立 terminal 已保存。此次读取为
`CONSUMED_FAILED / STOP_AND_RETAIN`，禁止重放或补查。旧 10a、PS1 冻结、10c 五份
维护原件及其失败终态保持。没有 journal 增长、维护重启或核心发行，H01/Q4/H11
仍 NOT_RUN。本次定位只说明当前读取，不追认原 10c 的空诊断对应同一路径。

离线核验六个固定摘要归档、26 份指定文档和八份 Q1 原件后，定位到来源分类错误：
六份旧计划的 `retained_inputs` 包含两个未发行 transfer 位置；它们不在已观察到的
`retained` 对象中，也不是任何已发行容量义务的 evidence。五份 observed 与末次
preflight/snapshot 一致记录关联发行标记不存在。`retained_inputs` 表示需要保护的
位置，不能直接等同于已存在且必须打开的证据。

普通修复保留原历史 inventory 和 Q1 来源逐项比较，再用这两个位置的精确长度/摘要
纠正当前存在性分类。主机 producer 和独立完成消费者都执行此来源变换；部分匹配、
重复或保护缺失拒绝。178 项真正必需对象仍使用原 guest 检查，230 项保护路径、19/7/7
声明、历史 horizon/全额义务及硬上限全部保持。没有按 ENOENT 动态跳过、删除路径
保护、创建空目录或伪造原件。缺失其他证据和修改保护集合仍被拒绝。

真实保留输入重建通过 180→178 对比，16 个输入绑定及八份 Q1 原件重新校验通过，
独立 Q1 消费者接受准确变换；四个 carrier 的后续完成步骤没有执行，此验证不是新现场
冻结或许可。首轮 88 项相关检查通过。此前一个新文件夹具受调用环境 umask 影响被
原保护正确拒绝，已显式设置该夹具权限；生产保护未改。原生完整相关回归完成：
1946 passed / 21 skipped，覆盖 journal 生命周期、全部核心接续、固定输入和交付链。
主机源码 98263 B，保留原 98304 B 上限；未改任何载荷或资源限额。这次代码修复、
测试和后续发布均不释放新读取/维护窗口，不改变已消费失败或核心 NOT_RUN。
