# 固定历史 FD 与原核心继续执行实现

本实现继承独立 C `26a89a1a11a958c24987eb590944331a9769b2ad`，对应
[已批准 A](../governance/Q2_CORE_HOST_FD_CONTINUATION_BASELINE.md) 的 FD1–FD3。
A 的三份文档及历史 OPEN 字节保持不变。十一代已消费窗口、原失败与 UNKNOWN 均保留。

## 实现

固定宿主模块 `q2_journal_retained_fds.py` 在原进程已完整核验 55 份旧维护原件后，
使用一次匿名 socketpair/fork 继承其 open-file descriptions。父进程验证 READY、
pidfd 和 PID/start 后才关闭自身的 55 份副本。子进程关闭其余继承 FD，不运行其它程序，
不重新打开原件。每个原身份检查边界继续核对原文件名、metadata、owner/mode/nlink、
dev/inode、大小和哈希；其它源、锚路径、禁止出现的后续输出和跨集合不同 inode 保护保留。

协议绑定 D、nonce、源码、完整历史和原件身份集合，最多 64 次 CHECK，固定帧长及
2 MiB 总 IPC 上限；每个交互受五秒及原剩余窗口共同约束。进程、协议、文件或计量异常
停止，不重启子进程或退回重新打开路径。子进程继承原 128 FD/256 MiB AS，存活 CPU/RSS
与 wait4 费用计入原 120 CPU-s、512 MiB、八个控制子进程预算。RSS 保留存活观测和退出
统计的较大值；wait 后不重复累加 CPU。预检收尾成本进入同窗 execute 的费用输入。

原件持有覆盖最终检查及 receipt 保存；随后释放本调用自己的 FD，RELEASE 并收回准确
子进程。顶层输出保留实际收尾、累计费用和 receipt 哈希，收尾失败不能返回成功。
独立原件验收及核心消费者同时要求维护成功、该准确 receipt 的顶层成功退出和子进程退出。
原件身份列表还必须等于独立保留源读取的 metadata，不能仅接受回执自报。
原 pre SSH 已允许完整报告、ack 和 VM 真实退出后的 255；总进程验收现在以准确 transport
PID/退出绑定保持同一规则，其余工具仍要求 0，并拒绝缺失、重复或错绑 transport 进程。

manifest/receipt v13、preflight v12、transition v12、reconciliation/history v16、
host-capacity v15 已同步生成与消费端。manifest 仅在顶层 resume 保存完整十一代历史，
inputs 通过 resume_sha256 引用；消费者先验证完整历史，再重建原 source binding 并核对
原摘要。guest input/report 仍为 v4，运行时准备语义不变。portable/独立 dispatcher 的
验证不导入 Linux FD 子进程模块。

旧 09b 使用固定公开最小索引核验其 v12 原件，准确保留 errno 24、空 pre 流、无完成
transport、无 guest 报告和远端 UNKNOWN；不据此推断 SSH 是否实际启动。前十代验证
保持各自原 schema 和原拒绝条件。新维护唯一 session 为 09c，原核心仍为 07a。

## 离线证据与发行要求

隔离合成回归在真实 128 FD/256 MiB AS 下，从 121 FD 开始完成交接、pre 双向管道、
九个持有输出、备份/模拟 VM pidfd、post、receipt 和收尾，交接后父进程为 68 FD。
共享文件偏移验证交接继承同一 open-file description。替换、删除、内容/权限变化、
硬链接、错误 READY/序号/nonce/D、截断、超时、子进程死亡和计量缺失均须拒绝。
另验证实际存活 CPU/RSS 与退出费用，以及双端拒绝历史遗漏、错误摘要和失败顶层退出。
这些均为合成测试，不是维护或核心现场结果。

已用既有私有副本核验全部 55 份历史原件及原固定输入，未新增现场查询。保留历史的
单份编码样本约 54.7 KB，在原 65536 B marker 上限内；最终准确 D 仍须重新核算完整
marker、receipt、pre/post 描述、压缩/展开 bundle、argv、transition、approved-input
和核心包上界。原限额不变，十二代维护加原核心占用按 15616 MiB/4456 inodes 保留，
维护历史 CPU 义务为 1440 秒，与当前单窗 120 CPU-s 限额分别核对。

FD1 的最终发行记录还必须包含准确 D 首次 CI、同 D 独立安装验收和两份冻结调用器。
最后的维护/核心定向回归为 3287 passed / 48 skipped；此前完整本地回归为
7273 passed / 139 skipped，另两处旧历史数量断言失败，已修正并由该定向回归覆盖。
真实 guest 生成的 pre/post 报告已贯通两端独立核心验收；这些结果不替代准确 D CI。
只有这些完成后才执行已批准的唯一 FD2；只有完整 FD2 实际成功原件通过独立验收后才
执行 FD3 的 H01→Q4→H11。此实现记录不代表已使用新窗口或取得任何核心 PASS。

首个实现 `b7fa3745bfd188a37ab6e740cdf5cdd0d440978d` 的首次 CI `37954183544`
在 Windows 收集新测试时提前导入 Linux dispatcher，因缺少 `resource` 失败。
后续修正仅调整测试加载边界：portable prior 消费者在两平台继续测试，独立现场 dispatcher
在 Linux 测试。该失败保留，不重跑替换；修正后的准确候选仍须自己的首次完整 CI。

候选 `951d346e4ff8fed0662f2a18944db501e69b73e7` 的首次 CI `37954649663`
在 Windows 完成新测试后，既有进程树超时测试返回 `tree_termination_unconfirmed`，
该平台为 1832 passed / 1369 skipped / 1 failed。保留这次失败；返回未确认不能视为成功。
仅将该合成场景固定为基础解释器直接启动的 parent/child，避免 Windows venv redirector
增加中间进程，并给测试启动留两秒。仍要求准确 `tree_timeout` 和子进程停止写入。
生产终止实现、现场预算和 FD1–FD3 范围不变；最终准确候选仍需自己的首次全套 CI。
