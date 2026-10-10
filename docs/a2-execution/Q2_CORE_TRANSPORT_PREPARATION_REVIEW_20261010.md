# 传输修复接续的保留源核验

本轮依据[本地接续任务](CORE_TRANSPORT_CONTINUATION_TASK_20261010.txt)，从
`65ff2b7` 无冲突快进到 `4a59bb75712f8d7982c5ba4596424b83fe6a6067`。
原 `.codex` 本地未跟踪项未修改。没有SSH、VM/服务操作、现场进程读取、原调用器执行、
新维护窗口或核心包。本轮生产代码与测试源码未改变。

## 已完成的事实核验

只使用已经保留的副本与记录，不补查现场缺失位置：

- old10a四原件与原私有索引/失败记录的大小及SHA一致；两份pre流为空，缺失receipt
  仍按原缺失记录保留，没有补造第五件。
- 八份本地返回与原失败记录索引一致；preflight的manifest与实际marker完全相同，
  D/nonce/摘要及四条事件顺序一致。preflight通过，execute退出3，marker true、SSH1。
- execute、caller原始输出及summary完整保留相同diagnostic，错误为
  `GROWTH_USAGE_UNKNOWN`，失败身份阶段为`process_identity / GROWTH_USAGE_IDENTITY`。
  远端退出、guest进度和coordinator completion仍未知或未捕获。
- 原immutable freeze摘要与已公开记录一致；五份caller摘要均与该freeze一致。
  terminal gate恰为原freeze的真实state/uc2/uc3终态替换，其它字段未改变。
- 现有解析器验证old09c九成员归档，与原freeze中的来源投影一致。没有重开custodian
  已交接的原件，未运行旧维护/核心caller。

四维护原件、八本地返回、freeze、失败记录和terminal gate共十五成员，保存为独立私有
USTAR核验归档，153600 B，成员逻辑字节合计136598 B。该归档和逐文件索引不公开。
这是证据装配，不是新运行时输入准入：现有old09c解析器只支持其九成员/131072 B规则，
不能静默套用或提高其限制。新归档类型的196608 B边界已单独列入待确认准确A。

## 已有代码的隔离检查

基线4a59bb7的tests/tools与最终修复b65ecb3字节相同。Python 3.12.14、pytest 8.4.2：

| 检查 | 实际结果 |
| --- | --- |
| usage continuation、host-FD continuation、host FD、owned command usage四文件 | 106 passed |
| 原custodian真实121/122 FD生命周期和失败拒绝 | 38 passed |

合计144 passed，无skip。custodian在普通用户原生环境使用隔离临时目录、本地管道与
Unix socket；原128 FD/256 MiB AS限制及生产检查不变。日志/XML私有保留。这里验证的是
既有路径；没有用修改测试字符串或前向原型冒充新归档装配的全生命周期证明。
云端此前79 passed/5 failed及原修复CI失败记录仍保留；本轮不替换它们，不重跑CI。

## 新方案的确定内容与未完成项

源码顺序存在一个明确装配位置：`anchor.start_custody`成功之后、`maintenance.preflight`
之前。新归档只在此打开，可避免简单提前增加一个FD所推导的129峰值；并未观察到新方案
EMFILE。原交接前122、交接峰值保守128保持，交接后父持续持有70、含原20余量90，核心
准备上界126。新路径必须在TC1用准确输入数验证，当前只是静态推导。

十二代已消费维护与old09c未消费预检的区别不变。新增10b后十四份义务核算为维护
18144 MiB/5180 inodes/1680 CPU-s，加原核心捕获18208 MiB/5196 inodes，不退款。

原UC1准确A只覆盖old09c九成员来源、新10a、既有版本与十三份成本。新的old10a无receipt
类型、输入装配、版本与十四份义务是受影响方案变化。按AGENTS.md固定R的change control，
不能由executor把接续任务推断为准确新B/C，也不能先写新实现再补闭合记录。因此已完成
允许的来源核验/既有测试/具体方案，并固定[新准确A](../governance/Q2_CORE_TRANSPORT_CONTINUATION_BASELINE.md)。
新producer/consumer、全生命周期证明、准确候选CI/独立安装和新caller冻结仍未完成。

**原UC2 CONSUMED_FAILED / STOP_AND_RETAIN；TC1 NOT_STARTED；TC2 NOT_ISSUED；
TC3/H01/Q4/H11 NOT_RUN。** 只有真实Owner决定与独立C才能开始新受影响实现；请求以
TC1–TC3一个完整批次确认，范围内不再逐步骤审批。
