# S1 mailbox 提交状态与中断恢复链路复查

输入 main：`d20b7a756fdecfc272766a013f4c53c73b870190`。
精确代码候选：`90f86b26876ffa188da4c24338d98d2238cf40fa`；tree：`96de06f4b200d9cadadd346b7df2ab4e2e8749e0`。
Owner 再次要求检查并直接修复，延续“全部提交推送”和“不要走全量测试，走链路测试”的授权。
本轮修复既有 Git mailbox 的提交状态判定和本地持久化失败恢复，落实 A03 / A05 的交付与收据语义。R/A、S1 范围、Task/Result v1 和八项动作保持原义。

## 已复现的问题与修复

`git reset --hard` 不会清理全部 untracked 文件。控制文件创建后、Git 提交前中断，文件会遗留在 mailbox；旧实现可能将其当成已交付的远端证据。

| 发生位置 | 旧行为 | 修复后行为 |
| --- | --- | --- |
| controller submit | 远端没有 Task，却返回 already_present | 隔离本地遗留文件，按远端提交状态重新发布 |
| controller wait | 接受未提交的本地 Result | 隔离后等待真实已提交结果；不存在时返回 indeterminate / controller_wait_timeout |
| Worker 扫描 | 执行未提交的本地 Task | 本地遗留 Task 不进入执行链路 |
| Worker outbox | 将未提交的同内容 Result 当作已交付并删除 outbox | 从保留的 outbox / 收据恢复发布，不重复执行动作 |
| 原子写入 | write / 文件 fsync 失败留下本次临时文件，阻断同进程重试 | 清理本次创建的临时文件，返回 indeterminate，并允许重试 |
| 目录同步 | 吞掉目录 open / fsync 失败并报告成功 | 返回 mailbox_durability_unconfirmed；保留已链接目标，等待后续核对 |

每次 mailbox 同步前，只检查 tasks / results / conflicts 三个控制命名空间的 untracked 文件，包括被 ignore 规则匹配的遗留文件。合法普通文件移入私有 `.git/local-hand-untracked/record-…/payload`，同目录保存原路径、字节数、SHA-256 和隔离原因。文件与目录同步完成后才继续恢复已提交快照。每次使用新记录目录，保留原始字节，不覆盖历史记录，不上传到 Git。

隔离路径必须是真实目录；符号链接、reparse point、非法文件或超出既有读取上限的内容拒绝处理。保留失败不继续执行 Task。控制命名空间以外的本地文件保持原状。当前实现沿用独立普通 clone、既有单写者锁、Git 输出和 mailbox 磁盘预算。隔离记录需要本地保留；容量达到既有预算时继续拒绝推进，不自动删除证据。突发断电可能留下准备中的记录目录，不将不完整记录宣称为已完成隔离。

## 定向验证

修复前首轮 7 FAIL：其中 5 个直接复现产品缺陷，另 2 个因测试 profile 工具覆盖 transport_policy 而未到达目标链路。修正测试夹具后，这 2 个 Worker 链路分别复现未提交 Task 被执行及 outbox 被误清除，均 FAIL。修复后这 7 个用例全部 PASS；再加入 ignored 文件、非控制文件保留和隔离目录符号链接边界，并结合既有投递、冲突、收据和原子发布节点，形成 22 个指定源码用例。

扩展用例首次调用写错两个测试类名，退出 4、没有执行测试；原始 FAIL 记录保留，更正后 22/22 PASS。这是验证命令错误，不作为产品失败或通过结果。随后在全新 checkout 对精确候选再次执行同一组 22 个节点，未运行全量 pytest。

独立 build / runtime venv 均新建；wheel 构建、安装后在源码目录外以 runtime Python `-I` 执行安装态链路。保留全部旧环境和失败轮次。

| 精确提交验证 | 结果 | 耗时（秒） | 峰值 RSS（KiB） |
| --- | --- | ---: | ---: |
| 指定源码链路 | 22/22 PASS | 32.780 | 33168 |
| 编译 | PASS | 0.135 | 14032 |
| wheel 构建 | PASS | 1.067 | 25400 |
| 新 runtime 安装 | PASS | 0.479 | 41112 |
| 源码外安装态 CLI 链路 | 49 checks / 133 commands PASS | 115.867 | 54604 |

RSS 为 Linux wait4 ru_maxrss，不是同时运行的整棵进程树内存总和。

安装态通过真实本地 bare Git 和 controller / Worker CLI 验证：未提交 Task 不会误报投递或被执行，未提交 Result 不会被接受；完成任务的 outbox 能恢复发布，收据原字节保持一致，CAS 恢复标记不变。四份隔离 payload 与原文件字节、路径、大小及摘要逐一核对。安装态另注入三类 write / 文件 fsync / 目录 fsync 错误，确认失败状态、目标保留及同进程重试；这些是合成 I/O 故障，不宣称真实磁盘故障或断电试验。既有超时子进程清理、Result 尺寸回退、损坏收据、远端冲突和投递确认丢失链路继续通过。

- 环境：云端 Linux x86_64 / overlay，Python 3.12.14、Git 2.51.1、pip 25.0.1；固定构建依赖版本和命令清单保留。
- wheel SHA-256：`65534274fed6c63f91fa78f7242da812506b09927b010d339231fc1fc64ced0d`。
- 核心包摘要：`0caf4f2cb71cd0e574b1f6536f74410b7b3352537251a9045c8b1d8adfa229c6`。
- 独立核对 68 个 Git blob、23 个 payload 文件、29 个 wheel 成员、28 项 wheel RECORD、33 项安装 RECORD 哈希及 20 个缓存代码对象。
- 核对 15 个完成收据的 Task / Result / provenance，额外直接读取 bare Git 中本轮恢复的 Task / Result，并验证未提交 Task / Result 不存在于远端。
- 产物审计阶段重算 156 条命令、312 份日志摘要；实际退出码、预期非零结果、验证命令错误、耗时和 RSS 原样保留。发布和证据封装另有核对记录。
- 三份批准文档与 A `7246b850ffdc2709e359b09cac99f0fb88bda209` 字节一致；工作流和依赖未修改。

提交使用 `[skip ci]` 遵守链路测试要求；未修改或禁用工作流，不宣称全量 CI PASS。云端合成验证不等同 GX10 / aarch64 / ext4 复验。Windows 仍为 DEFERRED / UNVERIFIED；现役服务切换、S2、artifact-ledger A2 未执行。未添加许可证，未公开 SOP 历史或实机原始证据。
