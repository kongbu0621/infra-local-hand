# S1 投递与收据恢复链路复查

输入基线：`7fc3789f817157cc90484c0754722a650d6d7e09`。
Owner 本轮指令：“你再思考和检查一遍。有问题直接修复，不要走全量测试，走链路测试。”
继续沿用“全部提交推送。你直接继续修复”的主干发布授权。R/A、S1 范围及八项动作不变；Windows 延期，未切换现役服务。

## 实际缺陷与修复

1. 收据路径使用 exists 检查，悬空链接会被视为没有收据；Worker 随后执行 CAS 并覆盖收据位置。改为检查目录项是否存在，使损坏收据进入既有 local_receipt_invalid 隔离路径，保留原链接、发布 indeterminate 冲突并阻止重放。
2. Worker 的 Git push 返回非零时报告 failed，但远端可能已经接收结果。现在报告 mailbox_publish_failed / indeterminate，保留 outbox 和已经完成的业务收据，等待下一轮与远端核对。
3. Worker 和 controller 的 Git push 抛出超时／输出上限等 LocalHandError 时，会把底层 failed 状态直接传出。现在只在推送边界将其包装为投递结果不确定，保留底层错误码与错误信息。控制端不会因此自动重新投递。

投递不确定与业务 Result 分别记录：成功执行的 Result 保持成功，不因传输异常被改写为执行失败。Worker 重启及同一 Task 的显式重核对不触发业务重放。
以上修复对应既有 R07 / A05 / V06 的收据、outbox、失败恢复约束，没有增加协议或授权范围。

## 验证范围与初步证据

修复前 4 个新增定向链路用例全部 FAIL；修复后 4 PASS。用例包含真实 Git 接收后客户端返回错误、抛出超时和输出上限异常，并检查收据、远端结果、outbox 与 CAS 文件内容。
本轮仅执行 15 个指定源码测试节点，不运行全量 pytest。
精确代码提交：`4c58c10f96a3477c06a549795916eb607c6d7f5a`；tree：`5915764da118a2090839abaf75810c90d1084d66`。
已从该提交创建独立 checkout、新 build venv 和新 runtime venv，保留全部既有环境。

| 精确提交验证 | 结果 | 耗时（秒） | 峰值 RSS（KiB） |
| --- | --- | ---: | ---: |
| 指定源码链路测试 | 15/15 PASS | 32.927 | 33492 |
| 编译 | PASS | 0.102 | 13388 |
| wheel 构建 | PASS | 0.957 | 25400 |
| 新 runtime 安装 | PASS | 0.453 | 40908 |
| 源码外安装态 CLI 链路 | 35 checks / 108 commands PASS | 83.309 | 27932 |

RSS 为 Linux wait4 ru_maxrss，不能解释为同时运行的整棵进程树内存总和。

- 环境：云端 Linux x86_64 / overlay，Python 3.12.14、Git 2.51.1、pip 25.0.1；构建依赖按 requirements-build.txt 安装，版本清单完整保留。
- wheel SHA-256：`28344196974891b1abb3cbf7eb668840a67d77a414b6ec9e160f57b2a98b0373`。
- 核心包摘要：`e903586e79500616f4b55c33e262925d1f3bb3f5ba58d3c5e88223eb9ed07998`。
- 独立复核 63 个 tracked Git blob、23 个 payload 文件、29 个 wheel 成员、28 项 wheel RECORD 哈希、33 项安装 RECORD 哈希及 20 个 Python 缓存代码对象，均与精确源码关联。
- 11 个完成收据与 Task / Result / provenance 逐项核对。新增成功 CAS 的本地收据、远端结果完全一致；outbox 在恢复核对后清空；人工写入的恢复哨兵文件未被任务重放覆盖。
- 控制端与 Worker 分别完成真实本地 Git 接收后的超时：两份 receive-pack 完成标记、远端 Task / Result、CLI 退出码 3、底层 git_timeout 以及对应 publish_failed 均匹配。
- 悬空收据链接仍保留，目标没有被创建；对应远端冲突为 local_receipt_invalid / indeterminate，原业务文件不变。证据包以链接目标及其摘要保留该目录项信息，不跟随悬空链接读取。
- 产物复核时重算 129 条命令记录的 258 份日志摘要；12 条预期非零命令包含修复前失败轮和明确的反例。修复前的 4 FAIL 保留原状态，不计为产品 PASS。
- 三份批准文档与 A `7246b850ffdc2709e359b09cac99f0fb88bda209` 字节一致。未修改工作流、动作列表或授权配置。


安装态 CLI 夹具已让本地 Git receive-pack 实际完成，然后延迟 SSH 夹具退出，触发配置为 2 秒的 Git 超时；远端接收证据、错误退出、收据及后续恢复已共同核对。夹具不访问实机 mailbox，不授予任何额外产品能力。

本轮提交使用单次 `[skip ci]` 标记，遵守 Owner 的链路测试范围；未修改或禁用现有工作流，不宣称全量 CI PASS。云端 Linux 测试不等同 GX10 / aarch64 / ext4 验收。旧环境、失败轮次和原证据保留；不添加许可证，不上传 SOP 历史或实机原始证据。
