---
name: local-hand-preflight
description: 核对 Local Hand A2 的已授权连接、准确部署绑定、工具契约及可见引用；在首次提交、重连、版本变化或用户要求检查是否具备执行条件时使用。
---

先读取插件根的 `contract.json` 和 `scripts/workflow.py`，使用宿主提供的已认证工具调用回调。公开包的 `mcp.json` 没有真实连接；没有实际连接或私有准入记录时报告 BLOCKED。插件安装、订阅等级、工具出现均不授予执行权限。不要安装主机服务或自动投递作业。

1. 从已批准的私有准入记录读取可信 `authority`、profile 与完整六项 `expected`，不要把首次发现结果当信任来源。通过 `lh_capabilities` 取得版本、tool schema digest、按主体过滤的逻辑引用和预算；用 `Workflow.preflight` 校验目标与契约。
2. 目录分页必须保持同一版本；策略变化使旧游标无效时停止本轮发现。最多 32 页，达到上限报告未完成，不拼接版本。不得把私有路径写入公开文件。
3. 完整六项为 `node_id`、`install_uuid`、`deployment_epoch`、`profile_digest`、`policy_digest`、`registry_digest`。陌生 authority、错误目标、版本或摘要不符、`STALE_DEPLOYMENT` 时停止提交；不得自动接受新绑定、修改旧请求或换 id 重投。旧作业按原身份和当前读取权限查询。
4. 只使用可见且获准的 profile/source/build-cache/storage/prepared 逻辑引用。同时读取并报告 `Workflow.execution_support`；后端标为 UNSUPPORTED/BLOCKED 的 kind 不提交，即使 allowed_kinds 中有授权。发现到引用仍不代表已获准执行对应作业；后端独立核验。不要从日志提取路径并构造自由命令。
5. 核对执行阶段：E1–E3 只用合成身份和隔离 fixture；E4 实际连接、E5 GX10/S2、E6 真实 NAS 另有准确准入。不得通过旧 mailbox 的 validation 路径绕过。

报告目标与契约是否一致、准入作业和引用是否齐全、仍缺什么证据。`host.inspect` 也是作业：仅在已授权需要时用提交技能创建稳定身份并投递，不作为安装时动作。
