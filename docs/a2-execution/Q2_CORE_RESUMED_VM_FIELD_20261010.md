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
