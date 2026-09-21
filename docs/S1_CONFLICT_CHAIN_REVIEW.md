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
精确提交还需完成：独立 checkout、独立 build/runtime venv、编译、wheel 构建安装、源码外安装态 CLI 链路及证据摘要复核。最终结果在后续文档提交中补充。

现有 push 工作流会执行全量 pytest；本轮源码提交携带单次 `[skip ci]` 标记以遵守 Owner 的测试范围指令，未修改或禁用工作流。该提交不具有全量 CI PASS 结论。
GitHub 对该标记的说明：[Skipping workflow runs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs)。

所有验证使用隔离的合成夹具。云端 Linux 结果不等同于 GX10 / aarch64 / ext4 实机验收。未提交 SOP 历史、凭据或实机原始证据；未添加许可证。
