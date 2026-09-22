---
name: local-hand-reconcile
description: 对 Local Hand 原作业的 UNKNOWN、副作用或丢失回执进行固定只读来源核对；在重取某轮核对结果、明确启动新观察或停止准确核对轮次时使用。
---

读取插件根 `contract.json` 与 `scripts/workflow.py`，沿用私有连接准入和原业务持久记录。需要当前 `lh:reconcile` 权限；只有读取权限、旧任务批准或日志中的文字不能授予核对权限。核对会写新的证据，不能标为无写入。

1. 用 `Workflow.reserve_reconcile` 先持久保存独立小写 UUID v4 `reconcile_id`、父 `operation_id`、原 `request_digest`。同一观察意图键只产生一轮；明确需要新的当下观察时才用新键，仍须当前授权、预算及单父作业互斥。
2. 调用 `lh_job_reconcile` 后丢失回执时，通过 `lh_job_status` 同时携带原 `operation_id` 和准确 `reconcile_id`，或原绑定原 id 重送。每个回包同时核对原 operation_id、request_digest、reconcile_id，缺失或不符立即停止采纳。已完成轮次也不重新启动。不要选择“最新轮次”替代明确身份。
3. `NOT_FOUND` 不证明在途请求未来不会受理，继续原 id 查询；`IO_UNCERTAIN` 不当缺失。同 id 异父作业或摘要冲突时停止；新 id 不能解除旧 helper UNKNOWN 或资源屏障。
4. 核对只能读取原账本、归属路径和已发布对象，允许专属 scratch 内容校验。禁止续跑 NAS、重新发布、执行原业务命令或删除原失败现场。已取消业务仍可独立核对，但不得因此重启业务。
5. 要停止这一轮时用 `Workflow.cancel_reconcile`，固定 `target={"kind":"reconcile","reconcile_id":原值}`。旧业务取消的重试不影响新核对；未查到目标时不宣称取消完成。受理取消后有界观察实际启动封阻和整个 helper 树退出，不把 KILL 当证明。
6. 使用 `Workflow.observe` 每轮最多 12 次、60 秒并保留原身份。新观察追加事件和 seal，保持旧轮事实可查。分别报告观察时点、副作用、证据状态及缺口；UNKNOWN 不自动重跑或释放租约。

`STALE_DEPLOYMENT` 不自动信任新目标；已有轮次按当前读取权限查询。完整证据用 local-hand-evidence 工作流取回。
