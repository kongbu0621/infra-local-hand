# S1 结果尺寸与持久恢复链路复查

输入 main：`5050eb285750c1304ffb455886ce06cf01818dce`。
精确代码候选：`039935373db49b8b38c555fd00ab22fe21e99ca7`；tree：`0fc2d6ae0e615875437891563e47bdf8ceca85fd`。
Owner 要求再次检查并直接修复；延续“全部提交推送”及“不要走全量测试，走链路测试”的授权和范围。
本轮落实既有 A04 / A05 与 V03 / V05 / V06：Result 尺寸、验证输出、结果收据及不重执行。R/A、S1 范围、Task/Result v1 顶层和八项动作保持原义。

## 已复现的缺陷

stdout/stderr 各自的原始字节上限不能保证 JSON Result 小于 8 MiB。例如两个各 1 MiB 的 NUL 输出，转义后仅文本部分就约 12 MiB。

- 验证失败、输出超限或超时的异常附带较大诊断内容时，结果持久化再次抛出 result_too_large。完成收据未写入，后续任务被阻断；后续轮次只能看到没有完整结果的执行意图。
- 验证进程实际退出 0，但成功结果太大时，原实现把序列化错误变成 failed，混淆执行状态与完整结果能否交付。

## 修复行为

本地生成结果先执行原有 envelope、身份、来源及大小校验。仅对结构合法但超过 Result 上限的本地结果生成受限回退结果：

| 原执行状态 | 回退状态 | 保留的信息 |
| --- | --- | --- |
| failed / rejected / stale / indeterminate | 原状态 | 原状态、原错误码、原序列化字节数和 SHA-256 |
| succeeded | indeterminate | 原状态仍记为 succeeded，明确完整结果无法交付 |

回退错误码为 result_too_large，details 明确标记 original_details_omitted，并记录限制值。原错误码摘要最多 128 字符，发生截断时另有明确标志。原 Task/Result 身份及 provenance 不截断；受限 envelope 再次校验后，才按原有顺序持久化 outbox 和完成收据。重复任务从同一收据恢复，不再次执行。

该逻辑只处理本地执行结果；不修补不合法 envelope，不放宽远端结果大小或身份校验，不增加顶层协议字段、不提高尺寸上限，也不扩展旧 Task/Result 严格 JSON 解析范围。常规小结果保留全部原诊断内容。如果连身份 envelope 都不能满足既有上限，继续保留原失败路径。

## 验证证据

修复前首轮为 4 FAIL / 1 PASS，覆盖三个真实验证进程的失败路径、成功结果持久化边界及小诊断正向链路。另以真实退出 0 的验证进程复现错误状态，单独 1 FAIL。修复后对应 6 个用例全部 PASS；再加入远端超限拒绝和本地异常身份不被修补两个边界，进入本轮 18 个指定源码节点。失败轮次保留，未改写为产品 PASS。

精确候选使用新建独立 checkout、build venv、runtime venv；保留全部既有环境。没有执行全量 pytest。

| 精确提交验证 | 结果 | 耗时（秒） | 峰值 RSS（KiB） |
| --- | --- | ---: | ---: |
| 指定源码链路 | 18/18 PASS | 6.930 | 116512 |
| 编译 | PASS | 0.127 | 13696 |
| wheel 构建 | PASS | 0.993 | 25404 |
| 新 runtime 安装 | PASS | 2.431 | 40912 |
| 源码外安装态 CLI 链路 | 41 checks / 126 commands PASS | 108.434 | 54612 |

RSS 为 Linux wait4 ru_maxrss，不是同时运行的整棵进程树内存总和。

安装态以本地合成 Git mailbox 完成 controller → Worker → 固定 validation → 受限 Result → 收据 → Git 发布 → controller 返回。真实退出 7 的任务返回 failed，真实退出 0 但输出不可完整交付的任务返回 indeterminate；两者均返回 result_too_large 和明确的省略标记。分别重启 Worker、重新提交相同 Task 后，收据字节和返回内容不变，启动计数各为 1。源码链路另验证了超时、输出上限及后续 CAS 任务不中断。既有进程清理、冲突、损坏收据和丢失推送确认链路同时保留通过。

- 环境：云端 Linux x86_64 / overlay，Python 3.12.14、Git 2.51.1、pip 25.0.1；固定构建依赖版本清单保留。
- wheel SHA-256：`a83f5f1c3e9bb04969f1d318210e0f3f04f8c4fdba7d6346976e7e5eeb13d595`。
- 核心包摘要：`a3fc8c2420852d68e254e2b7a8347ada7cc86957a670b04ffbf985768c4aa5b2`。
- 独立复核 66 个 tracked Git blob、23 个 payload 文件、29 个 wheel 成员、28 项 wheel RECORD 哈希、33 项安装 RECORD 哈希和 20 个缓存代码对象。
- 14 个完成收据与对应 Task / Result / provenance 核对；本轮两个尺寸回退结果还与重复等待返回内容核对。
- 产物审计阶段重算 148 条命令的 296 份日志摘要，保存实际退出码、预期非零结果、耗时及 RSS；发布核对另行记录。初始记录器因证据父目录尚未创建而未启动 clone，补建本轮目录后重试，该准备过程有独立说明。
- 三份批准文档与 A `7246b850ffdc2709e359b09cac99f0fb88bda209` 字节一致，原 CI 工作流和依赖未修改。

提交使用单次 `[skip ci]` 标记遵守 Owner 的链路测试要求；未修改或禁用工作流，不宣称全量 CI PASS。云端合成证据不等同 GX10 / aarch64 / ext4 复验。Windows 仍为 DEFERRED / UNVERIFIED；现役服务切换、S2、artifact-ledger A2 未执行。不添加许可证，不发布 SOP 历史或实机原始证据。
