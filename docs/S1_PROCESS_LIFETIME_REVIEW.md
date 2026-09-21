# S1 进程生命周期与结果链路复查

输入 main：`2bfdf0f30e550b503ac7421c03e2b5d6868f3900`。
精确代码候选：`ab1801c0966585e0dbb1ac7f3cdd5776eff4919c`；tree：`4b9ffd8245d623232cd7c5e6092376be27d97d47`。
Owner 要求再次检查、直接修复，延续“全部提交推送”及“不要走全量测试，走链路测试”的授权与范围。
R/A、S1 闭合及八项动作保持原义；对应既有 R06 / A04 / V05 的固定命令、输出上限和超时清理约束。

## 已修复的实际问题

1. 通用命令和 validation 只等待启动进程退出。同进程组的子进程仍运行时，可能返回成功；子进程继承输出管道时，配置的超时不再被监控。
2. 控制线程在读取线程阻塞时关闭 BufferedReader，会等待读锁，导致清理本身阻塞。validation 还可能在阻塞结束后将不完整的清理重新认作成功。

两个入口现在持续监控启动进程、POSIX 进程组及输出读取线程，沿用同一个截止时间。POSIX 使用非阻塞管道读取；读取线程拥有管道并负责关闭，控制线程通过取消信号和有界 join 收尾。清理或输出收集无法确认时保留 indeterminate，取消读取不能升级为 PASS。正常结束仍保留完整的限额内尾部输出。

## 验证证据

修复前运行记录为 7 FAIL：其中 6 个用例暴露上述产品问题，另 1 个正向夹具存在生成代码的引号错误。已保留原记录及夹具版本；仅修正该夹具后，未修改产品代码的正向基线为 1 PASS。修复产品后，7 个新回归全部 PASS。失败记录未改写或计为产品 PASS。

仅运行 18 个明确选定的源码节点：父进程提前退出、继承管道、重定向管道、清理不能确认、正常尾部输出、输出限额、进程树超时、环境隔离，以及相连的收据和推送恢复。没有执行全量 pytest。
精确候选使用全新的独立 checkout、build venv、runtime venv，原有环境全部保留。

| 精确提交验证 | 结果 | 耗时（秒） | 峰值 RSS（KiB） |
| --- | --- | ---: | ---: |
| 指定源码链路 | 18/18 PASS | 28.377 | 33572 |
| 编译 | PASS | 0.129 | 13456 |
| wheel 构建 | PASS | 0.830 | 25396 |
| 新 runtime 安装 | PASS | 0.478 | 40920 |
| 源码外安装态 CLI 链路 | 37 checks / 114 commands PASS | 92.139 | 27848 |

RSS 是 Linux wait4 ru_maxrss，不代表同时运行的整棵进程树内存总和。

安装态链路使用本地合成 Git mailbox，经 controller → Worker → 固定 validation profile → 超时清理 → 收据 → 远端 Result → controller 返回完成闭环。启动进程已退出、子进程仍运行的任务明确得到 failed / validation_timeout；termination_confirmed 和 pipes_closed 均为 true，子进程心跳停止。同一任务再次提交并重启 Worker 后，收据字节与 Result 内容保持一致，启动计数仍为 1。既有冲突、损坏收据及 Git 接收后超时的恢复链路一并通过。

- 环境：云端 Linux x86_64 / overlay，Python 3.12.14、Git 2.51.1、pip 25.0.1；固定构建依赖的完整版本与命令日志保留。
- wheel SHA-256：`10d2afeb2f4ff149b3fa5afd10b4ab8b94c970d3f180529b133a255d23c07476`。
- 核心包摘要：`77b2f01f07af2df7fa3aa9329b79db76b121801edb24ec074ca15b07c0491483`。
- 独立复核 64 个 tracked Git blob、23 个 payload 文件、29 个 wheel 成员、28 项 wheel RECORD 哈希、33 项安装 RECORD 哈希和 20 个缓存代码对象。
- 12 个完成收据与 Task / Result / provenance 对应；超时任务收据、远端结果与返回内容一致，后续核对没有重执行。
- 产物审计阶段重算 136 条命令的 272 份日志摘要；退出码、耗时、RSS 与预期非零结果均逐项核验。发布核对命令另行保留。
- 三份批准文档与 A `7246b850ffdc2709e359b09cac99f0fb88bda209` 字节一致；没有增加依赖、动作或权限。

本轮提交使用单次 `[skip ci]` 标记落实链路测试范围，未修改或禁用现有工作流，不宣称全量 CI PASS。本轮证据属于云端合成夹具，不能替代 GX10 / aarch64 / ext4 实机验收。Windows 仍为 DEFERRED / UNVERIFIED。现役服务切换、S2 和 artifact-ledger A2 未执行；不添加许可证，不发布 SOP 历史或实机原始证据。
