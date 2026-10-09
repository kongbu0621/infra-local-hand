# DS1 声明目标检查与接续实现

对应 Owner 已批准的 `LH-Q2-CORE-DECLARED-STARTUP-CONTINUATION-v1`。准确 A
`2b13dd653ca19eaaf46a18e6ffc3f447b62eee59`，独立关闭 C
`a2a6d62de08b2d1d8fbf9da97e8ccf938e3777c1`；本实现直接承接 C。
[Owner B](../governance/Q2_CORE_DECLARED_STARTUP_CONTINUATION_OWNER_DECISION.md) 保存准确原文。
三文档字节及历史 OPEN 标签保持不变，原 R 不变。

维护 pre/post 仅查询声明域的严格属性，取消全量 unit/unit-file/template 枚举和
未知单元引用判定。返回 DECLARED_ONLY，明确未知单元及间接启动均 NOT_PERFORMED。
当前五字段 assurance 与原 QI/GS 四字段历史分开验证，缺项或虚报观察均拒绝。
覆盖缩减及管理前提来自本次明确批准，不能表示为持续排除已获证明。

GuestInventory 的 AST 比较确认仅 startup_manager 改变，删除 template_startup 及其
私有匹配诊断方法；collect 的两次 quiet_service/cgroup、当前进程/FD/maps/writer、
persistent 和数据校验全部保持原样。原 Q1 固定来源与 19/7/7 清单不变。

维护及独立核心消费者同步 08f、guest v3、manifest/receipt v10、短预检 v9、
transition v9、reconciliation/history v13 和 host-capacity v12。保留八代旧窗口的
40 原件、32 缺席名及全部消费/UNKNOWN。九代维护费用为 11664 MiB、3330 inodes、
1080 nominal CPU-s；原核心另计 64 MiB/16 inodes，无退费。
[旧08e五件最小索引](Q2_CORE_Q1_BINDING_ORIGINALS_INDEX_20261009.md) 按本次批准公开；
原文、机器信息和新08f记录仍私有。

## 离线验证

- 保护读取验证16个静态输入、20件原核心失败、4件诊断、4件容量及40件旧维护原件。
  没有新增现场查询、SSH、VM观察或维护 marker。
- 用真实保留来源和新源码核对：descriptor 26393 B，压缩 bundle 38929 B，
  展开 132828 B，远端 argv 54035 B；20位时钟下静态 marker 64518 B（待提交 D
  占位 WORKTREE）。这些是限额验证，不是当前 VM 状态或维护成功证据。
- 受影响核心/维护回归最终合计3116项通过、48项跳过。整组第二次运行3111通过、
  48跳过；剩余5个容量测试的替换数字错误已修正，该文件47项全部通过。
  首轮 fixture 旧协议、漏接 DS 权威和累计容量校验旧常量的失败均保留，不抹掉失败。
- 新用例覆盖声明域查询、pre/post范围记录错配或虚报、五字段保证的两侧验证、
  08e原四字段与七代嵌套历史、准确 R/A/B/C、来源与清单篡改，以及合成成功后
  双消费者接续。实际成功不能由合成数据代替。

## 本提交时的状态

准确 D 的 CI、独立安装、完整核心输入大小核对和两 caller 冻结尚待完成。
DS2 NOT_STARTED，DS3/H01/Q4/H11 NOT_RUN。全部 DS1 验证通过后才执行唯一08f；
完整维护原件 VERIFIED 后才可发行原07a核心包。任何失败 STOP_AND_RETAIN，
不重试、补采、清理或扩展。原所有窗口、预算和期限保持。

## 现场返回后的普通修复

上述为原 D 提交时状态；后续 DS1 已完成、08f 已消费失败，准确事实以
[现场返回](Q2_CORE_DECLARED_STARTUP_FIELD_20261009.md) 为准。本次基于其登记提交
`c2faa34f08541d08333c7d1bfc9efcbd584a9956` 修复现有接线和错误归因，无覆盖变更。

发现一处确定的后续阻断：guest 已生成 `lhq-journal-growth-guest/v3`，host 的
`MaintenanceTransport.receive_report()` 和 `finish()` 仍要求 v2。合成的真实 guest
v3 报告通过 guest 校验后，会被原 host 拒为 GROWTH_REPORT_BINDING。本次两处统一
引用 guest 的 REPORT_SCHEMA，仍只接受准确当前版本，旧历史协议校验保持原样。
该问题尚未在08f触发，因为08f先在进程检查停止；不能冒称它是08f的根因。

进程检查在进入清单和每个PID时更新context，记录PID、观察者PID、已读stat中的
启动时钟及PPID、准确cmdline/exe/cwd字段、cgroup摘要、保护根序号/摘要、匹配内容
字节数/摘要及位置。cmdline另记参数序号、参数内偏移和边界；exe/cwd记deleted后缀
处理。序号中根从1开始，参数和字节偏移从0开始。输出不含路径或参数原文。
命中时尚未进行末尾stat复核，明确identity_rechecked=false，不声称已证明PID稳定。
所有诊断来自原有读取；不新增进程扫描、SSH或子进程。诊断计算失败仍返回原拒绝。
成功后清空context，防止后续persistent失败被误归因进程；FD/maps等保护保持。

验证：相关journal、DS和QI回归568通过、2跳过；最后context清空调整后17项进程
用例再次通过。新增真实guest生成器→host管道测试覆盖pre/post和关机请求确认，
拒绝v1/v2/v4报告及旧v2确认。合成进程用例检查准确分支、读取次数、隐私、原拒绝
和成功路径；独立审查未发现覆盖放宽。没有访问原机或执行真实维护。

源码大小：host81541 B、guest62675 B、reader13357 B，低于原各自上限。
仅合成描述下的pre/post压缩bundle为34848/35867 B，展开105056/109908 B；
这不是私有真实输入冻结或下一窗口准入。08f的原冻结与五件原件保持，不更新pins。

本地Codex下一步限于已有原件和已保存启动命令的离线核对：能否从保留资料把保护根
引用定位到具体启动命令或工作目录；若材料没有该观察，就明确报告缺项，不猜PID，
不再把旧domain/unit当命中者，不停服务或补采。新诊断不能恢复过去未记录的PID。
准确CI另以本次修复提交为准。H01/Q4/H11仍NOT_RUN，现场具体进程未定位；
不能重放08f或发行条件核心包，任何进一步现场动作仍按原R及准确范围处理。

## 本地保留启动资料核对完成

本地已同步准确修复提交 `c1a47acb0442f874b308f317829f3c9b510abfb0`，核实其首次
[CI 37819888525](https://github.com/kongbu0621/infra-local-hand/actions/runs/37819888525)
三个作业全部成功；Linux、Windows 的准确 checkout、源码验证与独立 wheel 验收
步骤均成功。本次没有重跑 CI 或重复执行这些测试。

仅用保护 reader 读取已保留资料，验证08f五件原件的字节数、摘要及
marker/manifest/receipt关系。按原 D 的来源 pin 和实际 pre descriptor 重建保存的
维护启动 argv，其摘要与原消费 marker 的 pre_command_sha256 相同；该准确命令
字节中没有保护根的明文匹配。这不证明现场进程的 cmdline、exe 或 cwd，也不能
排除父进程或其他进程命中。

随后仅核对原 QI 已采用、DS 冻结已绑定的那份 Q1 启动属性原件：保存的 ExecStart
引用一个保护根，且该 Q1 单元已在08f声明目标清单中。这是历史启动配置关联，
没有现场 PID 或进程身份关联，不能认定该单元就是08f命中者。没有重复单元采集
或 C10 查找，也没有据此追加声明、修改进程检查或停止服务。

结论：旧返回只保存沿用的 manager/unit context，没有 PID、准确匹配字段、命中根
及进程工作目录；现有材料不能完成当时的进程定位。离线核对已完成，具体命中者
仍未确定，不将缺失观察解释为误报或通过。新诊断只能改善以后获准执行的返回，
不能恢复旧窗口遗漏的数据。本次 /proc 读取、SSH、新窗口及核心发行均为零。
08f继续 CONSUMED_FAILED / STOP_AND_RETAIN，DS3/H01/Q4/H11仍 NOT_RUN。
核对脚本、结果及关联原文保留在私有交接目录；新08f索引和机器原文未公开。

## 只读调用前的本地预算拒绝

2026-10-09 07:56（Asia/Shanghai）提供的截图报告：私有
`lhqcore-process-current-once-20261009.py` 在本地返回 GROWTH_MANAGEMENT_BUDGET，
SSH请求0，guest进程检查未启动，也未取得PID。此为截图报告，私有脚本及失败原件
尚未提供给云端；不能据此认定是哪项资源或哪个接线错误。远端main当时仍为5237ff1。

源码中该错误仅有两类检查，不是RLIMIT设置错误：

| 位置 | CPU | RSS |
| --- | --- | --- |
| management_usage | 当前进程及已回收子进程累计CPU，限120秒 | 当前进程历史峰值加已观测存活非VM子进程RSS，限536870912 B |
| Usage.sample | previous加当前累计CPU（保留原+1ns取整），限120000000000ns | last、当前管理RSS和已回收子进程峰值的最大值，限536870912 B |

本次普通修复仅为这两处原拒绝附加diagnostic：触发位置、CPU/RSS实际值、上限、
单位、各自是否超限，以及self/children/live/previous等原统计分量。拒绝时保留
原异常类型和原因，usage.last仍保持最后一次通过值；新增diagnostic保存真正触发
拒绝的采样值。没有新增/proc/getrusage读取，没有调高预算、减去历史或改峰值算法。
现有main和维护主流程异常输出会传递该字段；私有wrapper必须在已有异常输出处
保存error.diagnostic，不能假定其200行代码已这样做。

相关journal、DS、QI回归579通过、2跳过；其中coordinator文件48项通过，新增11例
覆盖CPU/RSS单项与双项超限、边界、previous与子进程峰值、无额外读取及拒绝快照。
独立源码审查确认原计量与阈值保持。host源码82665 B，低于原98304 B上限。
本次没有原机、SSH或VM动作；准确CI以该修复提交的运行结果为准。

交给本地Codex的下一步是读取已保存的私有脚本与拒绝记录，找出首次预算调用位置、
Usage(previous)来源、check回调绑定，以及调用前已完成的本地准备工作。优先解释
原记录中的数值；若缺失，明确缺项，在隔离合成验证中核对调用边界，不重新执行
现场入口。只修已证明的接线错误：不能把可能的历史统计混入当成既定根因，也不能
为通过而清零合法历史。实际所需工作若确实超过原预算，需明确报告数值与工作范围。
旧08f状态保持；当前进程定位及H01/Q4/H11均不能因这项日志修复而标为通过。

## 本地调用脚本与预算返回核对完成

本地已同步准确修复 `aa4e43c7d25022824f5f83d1aa71ff3b66950996`，核实其首次
[CI 37862742006](https://github.com/kongbu0621/infra-local-hand/actions/runs/37862742006)
三个作业全部成功，两个平台的准确checkout、源码测试和独立安装验收均成功。
本次没有重跑CI，也没有重新执行现场入口。

保护读取已保存的200行私有caller及其八件配套记录，核对operator、adapter、guest
loader、prepared、start、result、summary和空stdout/stderr之间的摘要绑定；两个
guest来源成员与原固定修复c1a47ac的Git字节一致。原件读取前后的身份、内容元数据
和atime均保持。消费记录存在，原结果明确SSH请求0、exit_code为null、两路流为空。
这次单独的当前观察已经消费失败；不能因SSH未发送而退回未使用状态。

源码定位到caller第146行的首次`usage=host.Usage();usage.sample()`。此前顺序是模块
导入、prepared和来源校验、创建当前观察消费记录、建立本地Anchor并复核、设置原
资源限制；Anchor内部还执行本地ssh-keygen公私钥绑定。此后才会把SSH计数设为1
并调用Popen。`Usage()`没有previous参数，初始CPU与RSS均为0，没有从08f或其他
旧窗口读入用量。Anchor收到的是Admission的纯时钟检查，未绑定usage.sample回调；
COMMANDS在SSH子进程创建后才追加，首次采样没有已登记的存活子进程。

这排除了该caller通过`Usage(previous)`混入旧账本的解释，但没有排除本进程及其
已回收子进程在首次采样前的真实累计用量或峰值。原结果只记录异常类型、errno和
reason，没有CPU/RSS实际值、失败stage或最后通过用量，无法区分management_usage
与Usage.sample中的拒绝，也无法判断具体资源和来源。设置RLIMIT_AS不会补出这些
历史数值，不能把原失败认定为guest资源耗尽、误报或预算确实不足。

隔离验证仅抽取两版现有预算函数和原caller的异常序列化语句，资源输入全部合成，
不加载或执行现场入口。六组检查通过：self CPU、已回收子进程CPU、self峰值RSS、
已回收子进程峰值RSS、CPU取整边界，以及正常路径。两版的判定、统计调用次数和
最后通过值一致；不同拒绝分支都能产生原记录相同的三字段异常。因此这些合成结果
不能反推原失败分支。原wrapper确实没有保存error.diagnostic；即使异常带有新诊断，
它的原序列化语句也会丢弃该字段。已消费caller及其c1a47ac冻结保持原样，不能靠
更新仓库源码让原返回补出诊断或直接重放。

本次完成交接要求的离线核对，未发现可据以清零历史、提高限额或改动预算接线的
证据。核对脚本、原件索引和结果保留私有，不发布新原件索引。没有新增/proc读取、
SSH、服务操作、维护或核心发行。08f继续CONSUMED_FAILED，当前观察同样消费失败；
PID及准确匹配字段仍未取得，H01/Q4/H11仍NOT_RUN。旧资料核对至此完成，不再重复；
新的现场观察仍需单独明确授权，日志修复与上述合成检查不提供该权限。

## 私有调用候选的诊断返回修复完成

已完成[具体修复交接](CORE_PROCESS_CALLER_REPAIR_TASK_20261009.txt)。原已消费caller及
配套原件保留；新候选位于独立私有目录，来源改为准确
`aa4e43c7d25022824f5f83d1aa71ff3b66950996`。候选记录和准确SHA-256保留本地。
没有再修改公开预算函数，没有重复旧现场资料核对。

最小返回修复是在原异常处理处保留完整`error.diagnostic`以及原reason/type/errno，
将原结果落盘段提取为同一实际输出函数，并在其中写入summary。summary保存完整
error对象，同时绑定最终result的basename、bytes和SHA-256；打印输出与落盘result
经解析后完全相同。旧Owner决定没有被复制为新的授权：候选的Owner决定为空，
prepare和execute首先拒绝未授权调用，候选输出目录仍不存在。

对候选源码的AST比较证明，实际执行try主体（包括Usage初始化、采样位置、时钟、
限额、运输及调用顺序）与旧caller一致，guest adapter字节也一致。八个注册导入
通过原来源核对，整个tests/e3_host目录与aa4e43c没有差异；host、guest、reader
的准确来源字节和摘要另存私有验证记录。候选语法检查通过。

六类合成输入全部通过：self CPU、已回收子进程CPU、self RSS峰值、已回收子进程
RSS峰值、CPU取整边界及正常路径。测试从候选AST直接提取首次采样语句、完整
except和finally，调用候选实际put和结果/summary写入函数，没有手抄序列化逻辑。
现场入口、运输、Anchor、guest相关读取等设置一调用即失败的哨兵，资源与时间
输入全部合成，模拟输出仅写隔离目录；没有调用prepare或execute。

五种拒绝逐字段核对stage、CPU/RSS的actual/limit/unit/exceeded及全部components，
同时核对reason/type/errno、摘要绑定和最后通过用量不变。正常路径error为null，
没有伪造预算拒绝或派发现场调用。每例最终输出四件，最大逻辑1872 B、分配8192 B；
完整打印结果最大1147 B，均在原限制内。合成完整失败示例与六例输出保留本地，
不作为历史真实用量，也不发布私有路径或原件索引。

候选修复与离线返回链验证已完成，现场发行仍NOT_ISSUED。本次SSH、/proc读取和
现场入口调用均为0，没有创建现场消费记录。08f和后来的当前观察仍消费失败，
PID仍未知，H01/Q4/H11仍NOT_RUN。下一步仅提交一次新的现有进程只读检查供Owner
确认；本记录、候选或测试本身均不授权现场读取、维护、扩容、关机或核心发行。

## 修复候选获准的一次只读观察返回

Owner在候选修复与返回链验证完成后，明确批准一次新的只读定位。事件为
`LH-CURRENT-PROCESS-READ-20261009-02`，准确请求、回复、候选摘要与来源绑定保留
私有授权记录。回复原文为：

> **批准一次只读定位”**。我将使用已验证候选，沿用原限额，最多一次 SSH，完整保存诊断，失败即停，不重试、不停服务、不执行维护或扩容。

本地通过独立调用器将该决定绑定到已验证候选，候选源码字节及原预算、检查和
guest adapter均未改变。prepare仅完成保存输入和源码核对；发行前再次核对准确
prepared摘要、授权和候选绑定、原命令/环境长度上限及消费记录尚未创建。
随后execute只调用一次，创建新观察的消费记录，原08f与上一观察均未重放。

本次首次预算采样通过，发起唯一一次SSH后立即返回退出码255；已保存stderr
明确是连接被拒绝，stdout为空。guest进程检查未进入，没有取得PID或匹配字段。
当前管理CPU与RSS采样值已完整保存且在原上限内，但不能据此还原或否定前一次
预算失败。拒绝连接不足以证明VM停机或其他具体原因，本次没有追加端口、进程、
VM或服务查询。

原结果中的complete=true仅表示两路运输流都到达EOF，error=null仅表示本地没有
抛出捕获异常；二者不能作为远端成功。运输退出码255、remote_exit=UNKNOWN保持，
终态为CONSUMED_FAILED / STOP_AND_RETAIN。result、summary、消费记录、prepared和
两路原始流已保护读取并完成摘要关系验证；八件原件及新的索引全部保留私有。

没有重试、重连、补采、服务操作、维护、扩容、关机或核心发行。新观察同样已消费，
不得再次执行该caller。当前直接阻断是已记录的SSH连接拒绝，进一步定位或恢复
不在这次单次只读授权内。PID仍未知，H01/Q4/H11仍NOT_RUN，所有旧失败与UNKNOWN
保持。本段现场事实更新上节NOT_ISSUED的历史状态，不改变原候选或先前冻结记录。
