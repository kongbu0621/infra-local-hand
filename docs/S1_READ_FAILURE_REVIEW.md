# S1 内容读取失败与 Git 自动维护链路复查

日期：2026-09-22 UTC。输入 main：`ccc3b77720e9bcc2806a509140bd1354323056d6`。
首个代码候选：`71014fc3ddee2bccf6e60e4893729397e455a2b5`，安装态失败，记录保留。
最终代码候选：`3caf3721ee6b9a08517506d0cb124f5a239f2c43`；tree：`1db9174da0eb1e03f04901503ff33ec5a7cd69ac`。
最终候选继承首个候选；随后仅补充本报告、AGENTS 和发布索引，不改变已验证代码。

Owner 要求复查、有问题直接修复，沿用“全部提交推送”和“不要走全量测试，走链路测试”的授权。范围仍是 S1 既有读取、持久化恢复与受控 Git 操作；R/A、八项动作和 Task/Result v1 不变。

## 已复现的问题和修复

### 读取失败被误当作内容无效

原有有界文件读取将 lstat/open 的 OSError 包成普通 LocalHandError，fstat/read/close 的 OSError 则直接逃逸；JSON 加载随后把这些错误归入调用方的“内容无效”错误。上层部分恢复分支由此静默跳过任务、持久标记冲突或隔离本来有效的成功 Result。

新增八条定向源码链路在旧实现上全部失败；修复后八条通过。这里包含底层错误传播、五条 Worker 分支和两条 Controller 分支。Controller 原本已经停止操作，问题主要是读取错误身份被覆盖；不能将其描述成原本会继续执行。

新增 FileReadUnavailable 类型，以 `json_read_unavailable / indeterminate` 向上传播 JSON 读取不确定性，CLI 返回 3。会跳过、隔离或改写错误的分支先传播该类型，避免制造永久业务冲突。底层保留 errno，不用清理时的 close 错误覆盖此前的读取错误，并且只关闭一次描述符。

源码定点覆盖 lstat、open、fstat、read、close 及 read+close 同时失败。畸形 JSON、非法 UTF-8、超限内容和悬空符号链接仍按原校验拒绝；没有放宽尺寸、类型、路径或协议校验。

| 读取失败位置 | 故障期间应保留 | 健康恢复要求 |
| --- | --- | --- |
| 待执行 Task | 无新回执，业务文件未修改，不能当作空闲成功 | 正常执行一次 |
| 已完成回执 | 原回执及原成功结果，不能新增永久冲突 | 不再执行 CAS |
| 成功 outbox，仅有执行意图回执 | 成功载荷及原意图，不能隔离成功结果 | 发布原成功 Result 并补全回执 |
| 远端成功 Result，本地回执缺失 | 远端事实，不新增冲突或回执 | 从远端恢复回执，不重执行 |
| outbox 发布确认读取远端 Result | 待发送载荷，不能误认远端损坏 | 确认后清除 pending |
| Controller wait / submit | 状态文件、远端 HEAD 与业务文件 | 分别返回原结果 / already_present |

安装态七组场景使用已安装 Worker/Controller CLI、真实本地 Git 远端和合成 CAS 任务，只对指定文件注入底层 EIO。每组都记录故障前后状态文件清单、业务文件摘要、远端 HEAD、真实退出码及健康恢复结果。已执行场景写入 recovery-sentinel 后恢复，确认没有重放；Task 首次执行场景则确认正常执行一次。

### 受控 Git 操作会启动自动维护

首候选源码 23 条链路、编译、wheel 和安装通过，但首次安装态在 **56 checks / 169 commands** 时失败。第 169 条 Controller wait 的实际退出码为 3、期望为 0，报告保持 FAIL；错误为 `mailbox_disk_quota_exceeded / indeterminate`，具体是遍历 `.git/objects/pack` 时某个 pack 文件已不存在。该轮耗时 160.512 秒、峰值 RSS 54592 KiB，整个失败 fixture 与日志保留。

事后 pack 清单与时间信息符合并发重新打包的可能性，但没有取得原失败时删除该文件的进程记录，不能断言原始消失已被唯一归因。

进一步独立使用真实 Git Trace2 复现：受控 fetch 在本地显式启用自动维护并降低阈值时，确实启动 `maintenance run --auto`、`gc --auto` 和 `rerere gc`。两条新增源码测试在修复前为 **1 FAIL / 1 PASS**，修复后为 **2 PASS**；原本通过的一条要求文件扫描失败继续返回不确定，不能跳过缺失文件计算配额。

修复在受控命令前缀中加入 `-c maintenance.auto=false` 和 `-c gc.auto=0`。这是单次命令配置，不修改用户全局配置或仓库持久配置。安装态分别跟踪 Controller 和 Worker 邮箱的真实 fetch，各记录 260 个 Trace2 事件，没有 maintenance/gc 子进程；两套仓库本地 `maintenance.auto=true` 与低阈值仍保留，随后整条安装态链路通过。

代价是这些受控操作不再顺便执行自动压缩整理；未来如需维护，应在独立、明确协调的维护窗口安排。本轮没有执行实机维护或扩展动作集。外部进程仍可能修改对象库，遇到无法测量的目录继续严格返回不确定，本修复不提供对外部进程的排他锁保证。

配置语义参考 Git 的[maintenance.auto 文档](https://git-scm.com/docs/git-config/2.52.0#Documentation/git-config.txt-maintenanceauto)和[gc 配置源码文档](https://github.com/git/git/blob/master/Documentation/config/gc.adoc)；本轮运行结论来自 Git 2.51.1 的实际 Trace2 和命令结果。

## 最终精确候选验证

再次创建独立 checkout、新 build venv、新 runtime venv 和新合成 fixture，未复用或删除旧环境。源码仅运行明确列出的 25 个节点；安装态使用 runtime Python -I，在源码目录外执行。所有步骤记录命令、UTC 时间、版本、退出码、完整日志、耗时、RSS 和摘要。

| 验证 | 结果 | 耗时（秒） | 峰值 RSS（KiB） |
| --- | --- | ---: | ---: |
| 指定源码链路 | 25/25 PASS | 69.061 | 33516 |
| 编译 | PASS | 0.102 | 15616 |
| wheel 构建 | PASS | 0.831 | 25524 |
| 新 runtime 安装 | PASS | 0.480 | 41156 |
| 源码外安装态链路 | 71 checks / 227 commands PASS | 217.303 | 54728 |

- 环境：云端 Linux x86_64 / overlay，Python 3.12.14、Git 2.51.1、pip 25.0.1。固定构建依赖清单与版本输出随证据保留。
- wheel SHA-256：`65680dba3455683b7360dc3adf6117ae3370afc9049c95305e9af30da7de9ff4`。
- 核心包摘要：`3f983571f3f9f0012266aa53db0ea9f2a1ddf12413c449606ea4f33337f214c3`。
- 独立核对 78 个 Git blob、23 个 payload、29 个 wheel 成员、28 项 wheel RECORD、33 项安装 RECORD 和 20 个缓存代码对象。
- 独立核对 26 个完成回执、七组读取故障恢复、两份真实 Git Trace2、5 份未跟踪文件隔离记录，并对照远端 Task/Result blob、Controller 返回与来源摘要。
- 审计时核对 433 条命令、重新计算 866 份日志摘要，区分预期错误与首次意外失败；发布、封装步骤另行记录。首次失败的外层验证命令及内层 wait 命令均保留原退出码。
- 最终候选源码工作树干净，`git fsck --full`、差异空白检查和 runtime 依赖一致性通过。
- 三份批准文档仍与 A `7246b850ffdc2709e359b09cac99f0fb88bda209` 字节一致，构建依赖及 CI 工作流不变。
- RSS 为 Linux wait4 ru_maxrss，按命令及已等待后代统计，不是同时运行的进程树内存之和。

## 验收范围与未决观察

本轮不将前述 pack 消失唯一归因于自动维护，也不将新的 PASS 用来解释[上轮报告](S1_STATE_PERSISTENCE_REVIEW.md)中的未跟踪副本、`.rsync-tmp` 或其他历史文件异常。已修复边界有独立复现与恢复证据，历史异常的底层进程来源仍未全部确定。

提交使用 [skip ci] 遵守定向链路验证要求，未修改或禁用工作流；没有运行全量 pytest，不声称全量 CI 通过。结果属于云端合成 fixture，不是 GX10 / aarch64 / ext4 或断电验收。Windows 为 DEFERRED / UNVERIFIED。未切换现役服务、执行 S2 或 artifact-ledger A2，未新增许可证，未公开 SOP 历史或实机原始证据。
