# GX10 S1 修复候选直接发布主干：Owner 决定

- Decision authority: repository Owner（本会话用户）。
- Event ID: `LOCAL-HAND-Q6-MAIN-PUSH-20260921-01`（本仓库记录标识，不冒充平台 message ID）。
- Observation time: `2026-09-21T11:23:36Z`，executor 记录已收到决定的 UTC 时间，不声称是平台原始发信时间。
- 决定来源：本会话中，在 GX10 S1 Q6 全新 checkout/build/runtime 验收进行期间，Owner 连续两次给出相同指令。
- 原始产品输入：`b763bd6714721d22278086db559fa3f6684aad7b`。
- 获准直接进入主干的修复候选：`1e2f9dce87e57c34a35fe3a6a75a8c784181ba83`。
- 修复候选 Git tree：`12190df12ec03c120e397b6f6606168cce337197`。

## Owner 原文

> 提交推送到主干，不要分支

该指令随后由 Owner 原文重复一次。此前 Owner 另明确要求：

> 不要中断，有问题直接修复

## 生效范围

本决定授权把上述已验收修复候选的五个后继提交保留原始边界合入并推送 Public 仓库的 `main`，不创建功能分支、不 squash 原始 S1 closure 与实现历史。

该决定不授权把 GX10 原始命令日志、机器身份、fixture、wheel、venv 或 evidence ZIP 提交到 Public 仓库；不添加许可证；不改变规则 R、批准文档 A、独立 closure C 或八动作范围；不批准治理摘录的等价采用。Windows 仍为 DEFERRED / UNVERIFIED，现役服务切换、S2 和 artifact-ledger A2 均不在本决定范围。
