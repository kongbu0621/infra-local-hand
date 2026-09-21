# S1 后续修复复核

本轮输入为公开 `main`：`a1bc0ebf05313c9bce4fc85ac7c315c4c417ed99`，
包含 GX10 修复候选 `1e2f9dce87e57c34a35fe3a6a75a8c784181ba83`。
本轮 executor 为云端 Linux x86_64；本记录不把云端结果计入 GX10 实机验收。

## 范围与发布指令

Owner 在本会话给出的原文：

> 全部提交推送。 你直接继续修复

沿用当前 S1 closure、已批准的规则 R / 文档 A 和主干发布方式。
该指令授权继续修复、验证、提交和推送；不改变原有八动作、配置权限、
阶段范围或治理摘录采用状态。Windows 延后，现役服务保持不变，
GX10 原始日志、wheel 和 evidence ZIP 不进入 Public。

## 已复现的问题与修复

| 问题 | 原行为及影响 | 修复与验证 |
| --- | --- | --- |
| call 参数校验太晚 | 等待 timeout/poll 非法时，任务已经投递到 Git mailbox，随后才报参数错误 | 在投递前校验；覆盖 NaN、Infinity、负数、布尔值、零 poll，核对远端 ref 与任务文件未变化 |
| 成功结果遮住冲突 | 同一任务已有成功结果与有效冲突时，控制端直接返回成功 | 优先核对准确任务 digest 对应的冲突；身份、来源、结构不符或冲突声称成功均拒绝 |
| 崩溃后冲突未补发 | durable marker 写入后、outbox 写入前失败，重启只跳过任务 | 从验证过的 marker 恢复缺失 outbox 并发布；保留 marker，不重执行原任务，后续任务继续处理 |
| 重复冲突覆盖原始字节 | 规范 JSON 摘要相同但原始排版不同的两轮结果落到同一路径，后一轮替换前一轮 | 碰撞时使用独立隔离路径；核对两份原始字节与远端 canonical result 均保留 |

原始基线完整源码测试为 **157 passed**。新增五项回归在修复前为
**5 failed**；失败日志保留，不改写为产品 PASS。修复后五项回归与既有
精确冲突查找用例均通过；完整源码测试达到 **162 passed**。
另在源码外安装态入口增加非法 call 不投递、冲突优先于成功两项 CLI/Git 检查。

## 验证与后续入口

冻结修复提交：`03a78e2b27463b049a81fd9eaffa8478faa8a6b3`。

Git tree：`c59ceb47e4c4d4dbd7c365ab8148c97fdbd0171d`。

wheel SHA-256：`c3a905c40568d3eb915e3bc77fc64936ab135f2a3e348bad42045de44680c8ea`。

以下结果来自该准确提交的全新 checkout、build venv 和 runtime venv，
环境为 Linux x86_64、Python 3.12.14、Git 2.51.1；文件系统为 overlay。

| 验证 | 结果 | 耗时（秒） | 峰值 RSS（KiB） |
| --- | --- | ---: | ---: |
| 完整源码测试 | 162 passed | 53.855 | 49,452 |
| compileall | PASS | 0.102 | 13,220 |
| Linux bootstrap Bash 语法 | PASS | 0.026 | 11,136 |
| wheel 构建 | PASS | 0.882 | 25,396 |
| 独立 runtime 安装 | PASS；无新增运行依赖 | 0.480 | 40,888 |
| 源码外安装态 | 27 checks / 74 commands PASS | 52.657 | 27,920 |
| 独立字节与证据复核 | PASS | 0.278 | 15,872 |

RSS 使用 Linux wait4 的进程峰值统计，不是同时进程树总内存，不设虚构预算。
每条验收命令保存 argv、cwd、工具版本、退出码、日志摘要、UTC 起止与耗时。

独立复核重新读取并核对 61 个 tracked Git blob、23 个载荷文件、wheel 的
29 个成员与 28 条 RECORD 哈希、安装后的 33 条 RECORD 哈希、20 个 Python
缓存与已核实源码的 code object 一致性，以及 10 份任务结果收据。
三份批准文档与 A 逐字节一致。复核覆盖此前 101 条命令记录和 202 份日志，
保留 9 条预期非零命令及一轮审计工具自身的失败。

首次独立审计因错误要求 pip 生成的缓存必须具有 RECORD 哈希而失败；
修正后按源码检查缓存内容，通过复核。失败脚本、日志与退出码原样保留。
后续仅修正审计摘要中的预期非零计数，原摘要也保留。产品代码未因此变化。

原始 `docs/GX10_S1_RUNBOOK.md` 的输入 D 不改写。后续 GX10 复验应使用本记录
最终列出的修复提交，沿用其隔离、证据和现役只读约束，单独记录新候选结果。
这不将后续代码的云端验证冒充为既有 `1e2f9dc` 的 GX10 证据。


## GitHub CI 独立验证

验证的准确提交为上述 `03a78e2`。
[Linux job](https://github.com/kongbu0621/infra-local-hand/actions/runs/35600713655/job/106335924232)
已完成并通过：源码测试 **162 passed in 51.67s**、wheel 构建安装、
源码外 **27 checks / 74 commands PASS**，以及 Linux bootstrap 检查。
证据 artifact ZIP SHA-256：
`d83cb3098aa9fdcdd6681501dc1a38c1f6fd1c6cd2333394bf494232df056538`。

本记录的后续发布提交只补充文档，不改变上述已验证产品候选的源码、测试、
构建依赖或工作流。不要把文档提交的 HEAD 冒充为 wheel 内的源码提交。


[Windows job](https://github.com/kongbu0621/infra-local-hand/actions/runs/35600713655/job/106335924241)
结果为 **2 failed、148 passed、12 skipped，186.70 秒**，所以完整工作流总体为
**FAIL**。新增五项回归通过，失败用例名称与输入基线的 Windows CI 一致：

- `test_clean_build_identity_allows_only_known_generated_ignored_files`：
  本轮报 `build requires a clean committed source checkout`；基线同一用例报
  `.gitignore` 的 Git blob 不一致。此处记录症状，尚未定位 Windows 根因。
- `test_linux_bootstrap_rejects_bad_profile_before_filesystem_mutation`：
  捕获的空 stderr 不包含 `invalid_profile`。

Windows 后续 wheel 与平台步骤未执行；Windows 仍为 DEFERRED / UNVERIFIED。
该候选尚未在 GX10 重新执行；未做新版服务切换、S2 或 artifact-ledger A2。
这些状态不能由 Linux 云端或 GitHub CI 的通过替代。
