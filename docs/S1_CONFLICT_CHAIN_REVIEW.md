# S1 冲突与恢复链路复查

本轮从 `8d6a337a7f22e77de5cb4b6b604c528dd9e5f2af` 开始。
Owner 本轮指令：“你再思考和检查一遍。有问题直接修复，不要走全量测试，走链路测试。”
沿用先前“全部提交推送。你直接继续修复”的发布授权。R/A 和 S1 范围保持不变；Windows 延期，未切换现役服务。

## 已复现的问题与修复

1. Worker 在没有本地收据/冲突标记时忽略已发布的远端冲突，仍可能执行 CAS。现在先验证与当前任务绑定的远端冲突，保存本地持久标记并停止执行该任务；后续正常任务继续处理。
2. 恢复逻辑只检查远端冲突文件存在，未检查内容。现在校验身份、摘要、状态及完整语义内容；不一致保留两边记录并报 indeterminate。JSON 排版差异不构成内容冲突。
3. 本地冲突 outbox 未校验文件名与 task digest 一致，且允许成功状态。现在这些无效记录在 Git 发布之前隔离，保存原始字节。

无效远端冲突或与本地标记不一致的冲突会中止当前 poll，并保持 indeterminate；不会把该轮标为成功，也不会执行该任务。此变更不增加任何动作、允许列表或控制协议。

## 验证范围

修复前只运行新增的 5 个定向链路用例：4 FAIL、1 PASS；修复后 5 PASS。完整失败日志保存在独立私有证据目录。
本轮选择 15 个具体测试节点，覆盖真实 Git mailbox、CAS 不重放、收据、outbox、冲突恢复以及控制端关联与 provenance 校验，不运行源码全量测试。
精确代码提交：`8bc59ab653a949c637362879fdbd318cd51b4052`；tree：`67eaca7297a957052050b867f2ad7e6125c3c2a5`。
已从该提交创建新的独立 checkout、build venv、runtime venv；所有已有环境保留。

| 精确提交验证 | 结果 | 耗时（秒） | 峰值 RSS（KiB） |
| --- | --- | ---: | ---: |
| 15 个指定源码链路测试 | 15/15 PASS | 27.808 | 33024 |
| 编译 | PASS | 0.101 | 13216 |
| wheel 构建 | PASS | 0.882 | 25404 |
| 新 runtime 安装 | PASS | 0.530 | 40908 |
| 源码外 CLI / 安装态链路 | 31 checks / 97 commands PASS | 59.789 | 27932 |

RSS 使用 Linux wait4 ru_maxrss，表示命令及已等待子进程的峰值记录，不表示同时运行的整棵进程树内存总和。

- 平台：云端 Linux x86_64、overlay 文件系统；Python 3.12.14、Git 2.51.1、pip 25.0.1。构建工具版本均按 requirements-build.txt 安装并保留完整 freeze 记录。
- wheel SHA-256：`f521e3ea06b8425741cb8d4b306d4d4716e96dae0c1eeec695f148e64f4f0daa`。
- 核心包摘要：`63effa9e2d6e9af8d452a6388e17d3d72dc01a2e828e65bde20c6b72821e6352`。
- 独立复核：62 个 tracked Git blob、23 个 payload 文件、29 个 wheel 成员、28 项 wheel RECORD 哈希、33 项安装 RECORD 哈希、20 个 Python 缓存代码对象与源码一致。
- 10 个完成收据逐一与 Task、Result、安装 provenance 关联；新增冲突 CAS 没有执行收据或 canonical 成功结果，目标文件保持原样。本地冲突标记与恢复后的远端字节一致。
- 已复核 118 条命令记录及 236 份日志摘要；其中 10 条非零退出均为明确记录的预期反例，包括修复前失败轮、冲突漂移和配置漂移。修复前 4 FAIL 保留原始状态，不计为产品 PASS。
- 安装态实际走过：任务 submit → worker → controller wait；无收据的远端冲突阻止 CAS；远端冲突丢失 → worker 重启补发 → controller 再读；远端内容漂移时 Worker 明确退出 3，stderr 为 remote_conflict_content_conflict；恢复原冲突后正常轮询。
- 三份批准文档与 A `7246b850ffdc2709e359b09cac99f0fb88bda209` 字节一致；代码与 wheel 保持精确提交关联。


现有 push 工作流会执行全量 pytest；本轮源码提交携带单次 `[skip ci]` 标记以遵守 Owner 的测试范围指令，未修改或禁用工作流。该提交不具有全量 CI PASS 结论。
GitHub 对该标记的说明：[Skipping workflow runs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs)。

所有验证使用隔离的合成夹具。云端 Linux 结果不等同于 GX10 / aarch64 / ext4 实机验收。未提交 SOP 历史、凭据或实机原始证据；未添加许可证。
