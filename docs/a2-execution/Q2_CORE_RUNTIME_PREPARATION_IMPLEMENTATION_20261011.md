# RP1 原核心运行准备接续实现

准确A `e64d4d73488026247b03fd7d41387ef8f3887dd8`，独立闭合C
`4ae2b8f83f65b3262015e46f43d64ea035e89c91`；Owner准确相邻回答“批准”，见
[闭合记录](../governance/Q2_CORE_RUNTIME_PREPARATION_CONTINUATION_OWNER_DECISION.md)。
本实现下降自C，保留A三文档原字节、旧IR2消费失败及全部旧原件/冻结/终态。

## 固定接线

保留798720 B/19成员identity archive原字节和原解析器；新增独立409600 B/18成员
old11a失败归档。生产者逐项验证五原件、原索引、完整guest诊断、原冻结/终态、实际
caller/coordinator/custodian返回及双EOF。旧冻结的archive pin把两个输入绑定；
新归档不嵌套旧归档，不在磁盘解包，不增加现场观察。固定USTAR拒绝成员替换、重复、
链接、扩展头、非零padding及尾随数据。两输入在preflight、execute和core preparation
持续持有并复核，父输入19→20；原55份持续持有原件不变。

新会话固定11b；manifest/receipt v21、preflight v20、transition v21、host-capacity
v22、historical-capacity/reconciliation v23、guest input v7；guest report v5和
approved-input外层v1保持。历史11a的v20与原诊断独立解析，历史resume无损还原。
生产者和独立dispatcher要求完整旧失败来源、全部历史和实际维护成功条件。

十六份原1296 MiB/370 inode/CPU120秒义务、旧11a及新11b各2200 MiB/402 inode/
CPU240秒均计入；维护CPU总2400秒。旧15 MiB/480 inode读取/准备保持，新source/
archive各2 MiB/64 inode，原core捕获128 MiB/32 inode。总25283 MiB/7364 inodes，
维护准入25155 MiB/7332 inodes；旧费用无退款，两个904 MiB/32 inode余量各计一次。

普通slice修复沿用已合入PR #14。除固定新session/input版本外guest无新行为；命令、
限制、Q1、19/7/7、四叶身份和祖先/写位、进程/写入者/数据检查保持。NAS发现和新提交
屏蔽继续保持，外围开发暂停。

## 当前离线验证与发行门禁

定向双归档/历史/费用/核心准入233通过；完整核心与维护首轮3688通过、48跳过、
16失败，原输出保留。失败均为当前authority/session/schema/费用或发行摘要的旧断言。
修正后的相关回归1018通过，余下一项是进程已加载的旧发行pin断言；锁定新pin并更新
准确摘要断言后，发行门禁及未审核摘要拒绝2通过。中间1失败/1通过的旧字面摘要断言
返回也保留，不作为成功运行替代。私有新caller控制流程24通过，无现场进程。

真实256-FD双归档测试6通过：129和250个起始FD下，55原件custody交接、pre/post
本地管道、输出和完成生命周期；任一归档内容漂移均拒绝。保留的真实原件离线读取
确认20输入/55原件/20旧core文件/4诊断/4容量原件，未观察VM或发送SSH。

固定归档已私有创建，409600 B，实际分配421888 B/3 inodes，在2 MiB/64 inode内。
首次沙箱读取因根目录属主映射在读入前失败，未创建归档；原返回保留。同一受限脚本
在正常主机身份下完成，未改路径保护或增加准备池。新归档来源通过生产者及独立消费者。

完整dispatcher AST与既有审核发行逐项比对：384个顶层节点保持，变化仅为当前会话、
新失败/历史、authority、schema及费用验证；H01/Q4/H11执行backend、任务参数、限制、
身份/结果检查保持。新准确发行摘要为
`5a0ba993039908220a56ab9c5c6649c942f15689242eb0b464a6b9b9da459a8a`，
旧摘要及任意编辑摘要仍拒绝。私有审核记录保留全部前后节点摘要和变化清单。

本记录处于RP1验证阶段。准确D源码/完整生命周期及载荷边界、正常PR发布、自己的首次
CI、两平台与本地独立安装、最终source和两个新caller冻结仍须全部完成后才RP2。
新维护及原core尚未发行；RP2 NOT_ISSUED，RP3/H01/Q4/H11 NOT_RUN。
所有raw、索引、归档、caller及机器元数据保持私有；这里不是容量准入或现场PASS。
