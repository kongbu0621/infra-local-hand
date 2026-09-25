# 保留的首次执行器限制

日期：2026-09-25。本文件是工具输出的人工摘录，不是补造的完整原始日志。

首次命令：

```text
python3 -m unittest discover -s tests -p 'test_local_hand_jobs_quota_*.py' -v
```

当时尚未加入脚本化传输测试和环境 skip 处理：

```text
Ran 28 tests in 0.076s
FAILED (errors=11)
```

17 项通过；11 项真实 IPC 测试均在 setUp 创建 AF_UNIX / SOCK_STREAM socket 时失败：

```text
PermissionError: [Errno 1] Operation not permitted
```

同一命令以 require_escalated 请求受控测试权限，未执行。工具自动审批策略拒绝：

```text
approval policy is Granular ... sandbox_approval: false ...
reject command — you cannot ask for escalated permissions
```

后续处理：保留全部真实 IPC 用例；socket 创建权限拒绝明确 SKIP/IPC UNVERIFIED。
另行添加可运行的纯逻辑、元数据和脚本化传输故障测试。准确最终结果在同目录
targeted.log / targeted-command.json，未将此次错误或后续跳过计作真实 IPC 通过。
