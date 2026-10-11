# HR1 新基线冻结与 HR2 实际返回

## 当前结果：启动通过，guest传输失败（2026-10-12）

HR1已完成。准确D `0b84bbcf8108522305d1e23c9378f6d0a8f50bcc`，tree
`61a3bda99259c406eaaff2e2e7dc37d763979866`，下降自独立C且没有squash；
[PR #25](https://github.com/kongbu0621/infra-local-hand/pull/25)正常merge为
`3d3d8075cdd45665217a2be9c269eed6ccbbb998`。
它自己的[首次CI `38152488046`](https://github.com/kongbu0621/infra-local-hand/actions/runs/38152488046)
attempt1三项成功：Linux7950通过/89跳过，Windows2089通过/1391跳过；两平台独立安装
成功，本地独立安装94检查/292命令通过。此前候选`8440020`的首次CI `38151005286`
保留Windows2087通过/1391跳过/3错误：131073字节输入被pytest当作完整用例名，超过
Windows环境变量长度。后续只缩短该测试的参数标识，未删校验、取消或重跑覆盖旧失败。

新基线原件消费、独立核心消费者、null参数重建、三归档持有和全部费用已接齐。
定向验证为64项来源检查、14项真实FD生命周期、64项私有四阶段/资源检查、5项数据门检查。
实际保留来源的完整维护/核心上界在512 MiB AS、256 FD、240秒限制内通过，记录CPU约8.04秒、
RSS峰值355106816 B；维护交接上界130 FD，核心准备上界128 FD。明确合成的未来原件
归档471040 B，固定成功结构保守上界849920 B，均低于1 MiB；这些不是现场执行归档。

工作树保持既有稳定读取和准确Git字节校验；启动/guest阶段只从17份受保护源码副本加载。
准备中的工作树保护和相对路径索引错误均在发行前修正，既有请求/nonce未替换。
24个私有程序、全部来源/目标/载荷和四阶段数据槽在现场前冻结。
不可变freeze为32672 B，SHA256
`0d5bb5140b7687dd77714a0ce1f5f30f956e431aadce702e9bc1ab6ba2305d98`。
两版A的六份文档字节保持；旧阻塞gate、HB2/RP2及更早终态均未覆盖。

### HR2实际顺序与证据范围

唯一`lhqstart-20261011b`完成一次临启动检查和一次原配置启动，serial为null，原VM限额保持。
caller和外层工具实际退出0，双EOF；19件启动核验原件重新消费通过，新VM身份、监听和
host绑定一致，得到`START_VERIFIED_GUEST_READY`。没有新串口文件或转发器。

随后唯一`lhqguest-20261011c`按原端点、host-key信任和冻结六命令载荷发起一次SSH。
caller与外层工具实际退出3，caller双EOF完整；guest stdout为0 B，stderr为103 B，
记录`kex_exchange_identification: read: Connection reset by peer`及原固定端口连接重置。
本地失败为`HOST_REBIND_COMMAND_COMPLETION`，没有guest核验报告。
这能确认传输在握手阶段失败，不能确定guest侧原因、证明sshd故障或推断它只需再等一次。
SSH子进程的完成行未在capture异常后写入结果，不能把caller退出3当作SSH子进程或远端退出；
remote exit继续UNKNOWN。没有成功的六命令结果、最终v3数据冻结或后续释放。

9件guest原件、其索引及独立`GUEST_FAILED_STOP_AND_RETAIN`终态保持私有。返回后核对
不可变freeze、24个程序摘要、17份源码和两个原请求均未变化；维护/核心槽仍为空。
本批自动审批拒绝为0；记录的是实际SSH传输失败，不据此归因于审批系统。

HR2为CONSUMED_FAILED / STOP_AND_RETAIN；HR3 NOT_ISSUED，HR4/H01/Q4/H11 NOT_RUN。
没有维护关机、备份、journal扩容、维护重启或原核心包。依照原批准方案的失败边界，
不重试、不补采、不重置信任、不额外启动/开窗，不清理、回滚、恢复或停止业务服务；
不能修改冻结caller再继续。后续只使用现有返回和源码离线核对，连接重置原因保留未知。
十九份完整维护义务和27497 MiB/8214 inodes预留无退款；历史文件系统/内容连续性仍UNKNOWN。
NAS发现/新任务准入继续禁用，外围暂停。

## 修订批准后的历史准备进度

Owner已明确批准修订A `4af01900cfe462cec4762cb04966dab139a0a31c` 的null串口调整，
并连续推进原HR1–HR4。[准确决定](../governance/Q2_CORE_HOST_REBIND_NULL_OWNER_DECISION.md)
由独立C `4acf0dbfe99d0c7e170b6102f861fa9671d09da2`登记；两版A的六份文档均保持原字节。
下面的串口阻塞及旧私有gate保留为历史，不再表示待批准。

当前候选新增v3原件消费者，重新消费固定HB2来源、RP2终态及两份旧归档，采用六镜像
当前身份；历史文件系统/内容连续性继续UNKNOWN。启动和维护参数分别重建，v3只允许null，
旧v1/v2语义保持。第三份有界归档持续持有，完整费用为27497 MiB/8214 inodes、十九份维护
义务；原核心捕获只计一次。核心独立消费者要求新版转移及其准确activation摘要。

实际保留来源离线重验一致：完整逻辑来源425652 B，去除两个同字节引用后340313 B，
持续持有54个来源文件；无现场动作。三归档真实256-FD交接/漂移/退出生命周期通过14项，
新原件核验及核心包解析/收回链路定向通过142项。私有启动候选7项真实本地文件/管道
控制流测试通过；合成宿主、镜像、旧串口、工具、pidfile及owner不符均阻止启动。

第一轮Q2集成保留93失败/5374通过/88跳过；接线与合成夹具修正后为7失败/5468通过/
88跳过。后七项仍引用旧授权或旧费用的测试期望已定位，后续结果另记，不替换历史失败。
准确D发布、首次CI、独立安装、私有四阶段验证和最终冻结仍在进行；HR1未完成，HR2/HR3
NOT_ISSUED，HR4/H01/Q4/H11 NOT_RUN。现场启动、SSH、维护和核心包均未发行。
NAS发现/新任务准入继续禁用，外围暂停。

## 历史离线发现

2026-10-11；范围 `LH-Q2-CORE-HOST-REBIND-CONTINUATION-v1` / HR1–HR4。
Owner 已明确批准 A `ee69dc80db82c3fbf3bd2c5d5c0e0ad0882a84c0`；
[准确决定](../governance/Q2_CORE_HOST_REBIND_CONTINUATION_OWNER_DECISION.md)由独立 C
`608f8d70c8fd43b82b613f49b26d6870e5e7f944` 登记，三文档字节保持。

## 最早阻塞及可核对依据

HR1 在离线核对启动器时确认，原方案关于串口已有边界的前提不成立。
原私有启动源码19,465 B / SHA256
`e3967e1aec61d4c35ac57ac0e56028e131ff8e3b51a2cde1496292c36dcd055d`，
原提议10,795 B / SHA256
`9b5d9a300452632232903e76ca359b192841eae1266f9e27c1d88af0474f4e81`，
均逐字节匹配旧 immutable freeze 和实际返回 index，未运行旧代码或读取新现场。

- 原 `save()` 在源码第49–58行限制单记录64 KiB、累计256 KiB；只覆盖其管理写入。
- 第240、297–301行以 `-serial file:…` 让 QEMU 直接写新文件，没有进入 `save()`。
- 第206–208行要求 VM 的 CPU/FSIZE无限；child只恢复原AS/FD，不为串口设文件上限。
- 新串口文件不在实际返回索引；源码没有持续监管该文件增长。旧串口保护不等于新输出有界。
- 保留控制流测试10,441 B / SHA256
  `3f60c289bc22a099f5442ee6aeec432be144e5c95aa481f7946bdf54ebf90082`
  模拟了创建和启动，没有建立实际串口写入上界。

因此不能证明原 HR2 file 后端在4 MiB启动捕获池内，也不能声称继承了已验证监督。
这不是实际超限或现场失败，未测量当前日志大小，旧启动成功记录仍保持其原有范围。

## 最小修订与实际状态

已准备[修订需求](q2-core-host-rebind-null-continuation/REQUIREMENTS.md)、
[修订架构](q2-core-host-rebind-null-continuation/ARCHITECTURE.md)、
[修订实施计划](q2-core-host-rebind-null-continuation/IMPLEMENTATION_PLAN.md)：
HR2将新启动串口后端改为现有维护已使用的null，不新增日志文件或转发进程。
原六镜像基线、启动/guest/维护/核心会话、出站目的地与载荷、次数、资源和费用保持。
修订后的v3和两侧argv消费者须明确支持null；不得改变旧v1/v2含义。

这个变化超出原A“只改pidfile/serial输出位置”，按固定R的Document evolution与原计划
第9项，受影响的启动接线/HR2及其依赖释放保持OPEN，等待准确修订的Owner决定。
原批准不撤销、不伪装未批准；未受影响的保留来源核对保持有效。

私有离线复核2,234 B，SHA256
`2f65af8a20d3462d9bead1c40e62e853eb37cac40b934625997814fdac349263`，
与独立私有release gate保留。HR1 OFFLINE_REVIEW_BLOCKED，HR2/HR3 NOT_ISSUED，
HR4/H01/Q4/H11 NOT_RUN。新caller/marker/启动/SSH/现场查询均0；自动审批拒绝0。
不存在被消费的新现场窗口。旧HB2/RP2、两归档及旧caller保持，不重放、不清理。
已批准十九份义务及27497 MiB/8214 inodes全额保持，无退款、新窗口或另一个准备池。
NAS及外围继续暂停。本提交只含批准登记、来源核对事实和待审最小修订，无运行实现。
