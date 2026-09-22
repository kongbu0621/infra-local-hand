---
name: local-hand-evidence
description: 经 Local Hand 已认证工具回调取回原作业或指定核对轮次的私有封存证据，完成断点续传、全件摘要和 ZIP 成员核验后交付实际文件。
---

读取插件根 `contract.json` 和 `scripts/workflow.py`，复用宿主已认证回调及有界私有文件 writer。使用同版 `local_hand_jobs.evidence_client` 的 `EvidenceClient(authenticated_tool_callback).download(artifact, writer)`，writer 为 `BoundedFileWriter(private_directory, max_bytes=已准入有限预算)`。artifact 必须来自封存 manifest，包含 artifact_id、role、size、sha256、seal_sha256 和 seal_id；不要导出 ChatGPT/OAuth/Tunnel/GitHub 凭据，不建立第二条 HTTP 登录路径，不把 base64 逐块输出给模型。

1. 查询准确 `operation_id`，核对指定 `reconcile_id`（如有）的 seal 引用；原业务与不同核对轮次的事件序号不能混用。STAGING、DURABILITY_UNKNOWN、NOT_SEALED 保持未交付；partial/cutoff 诊断快照必须明确为部分证据。
2. 调用 `lh_evidence_manifest` 固定 seal、artifact 身份、全件摘要、大小与成员清单。每页最多 100 项，游标与版本一致；策略或目录版本变化时停止该轮。保留上游夹具 `EPHEMERAL_BY_UPSTREAM_TOOL` 覆盖限制。
3. 调用 `lh_evidence_read_chunk`，默认 64 KiB、最大 256 KiB、单次 JSON 上限 512 KiB。原始结果由回调直接交 writer；逐块校验身份、偏移、长度、块 SHA-256 和固定全件摘要。artifact_id 不授予访问权，每块仍须授权。
4. 断线后从私有断点记录的同 artifact、同摘要、已校验偏移重取。拒绝摘要漂移、重复或错偏移、错误长度、非法 base64；不要换作业重跑。UNAUTHORIZED 停止下载，重新授权后仍沿用原 artifact。
5. 通过客户端组件核验最终大小、全件 SHA-256、外部 seal、内部 manifest 及逐件成员；拒绝 ZIP 绝对路径、..、重复名、链接或超出预算。只有全部通过才 create-only 发布最终文件；不覆盖既有文件，不删除他人的并发文件。
6. 交付实际文件链接，并附全件摘要、大小和 seal/覆盖限制。只有哈希、截图、structuredContent 或隐藏 `_meta` 不算完成文件交付。宿主缺原始 chunk 到 writer 桥接时报告 BLOCKED，不改用公开 URL。

E2 合成 callback 测试只证明组件行为；E4 必须在实际当前客户端取回至少 16 MiB 非高压缩率 ZIP，并验证中断续传。插件不默认已经满足这个门槛。
