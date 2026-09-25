# Q2 第六批固定源码验证

2026-09-25。范围、接口和剩余源码缺口见 [第六批实现](E3_QUOTA_Q2_RESIDENT.md)。

## 准确源码和发布

- 本地源码提交：`7903607981189d530376cb1694ab18a2377944a5`。
- Public main 对应提交：`599d102d15e9a5fd9cefa38ccda7043efe17705e`。
- 两者 tree 均为 `5e5606c560ad3a7768c4448da1a36b32ad78a59a`。
- 原远端 main `e84ca1bfaa2a30e7e0ab23f7d8f19983cd272db4`，非强制更新后读回核验。
- 下述回归在本地源码提交后、干净工作树执行；本报告与原始日志是后续独立证据提交。
- quota/harness 三层批准文档与 A `415327ebdcc251bb055da9931a7a88990f750b7a` 比对无差异。

## 固定回归

Linux `6.18.44`、Python `3.12.14`，UTC 13:44:38–13:44:56。
`PYTHONPATH=tools:tests PYTHONDONTWRITEBYTECODE=1`。

| 命令范围 | 收集 | 通过 | 跳过 | 退出 |
| --- | ---: | ---: | ---: | ---: |
| `python -B -m unittest discover -s tests -p 'test_local_hand_jobs*.py' -v` | 538 | 524 | 14 | 0 |
| `python -B -m unittest discover -s tests -p 'test_e3_quota*.py' -v` | 334 | 333 | 1 | 0 |
| 合计 | 872 | 857 | 15 | 0 |

15 项跳过为 14 项具名 Unix socket 场景和 1 项实际 systemd/cgroup 准入不足。
不能将实际匿名 socketpair 测试结果转记为具名 listener 的实测。
本批增加 50 项测试，没有以删除既有测试减少验证范围。

新增验证包含实际 SQLite 绑定/调度竞争、子进程与匿名双管道、create-only/fsync 文件和管理 journal、
隔离 Python 源码导入。6 项源码加载测试包括构造真实且时间戳有效的恶意缓存：普通 `-I -B`
确实执行该合成 `.pyc`，固定字节 loader 则执行已验证源码；源码验证后磁盘变更也不能替换保留字节。

systemd 监督、账户/保护所有权、cgroup 与准入事实在相应用例中明确建模。16 项 launcher 测试
没有启动实际 setpriv/systemd；覆盖从 prepared 到装配、关闭、finish、原 EOF 的顺序，
并验证错身份、部分采集、错关闭摘要、持久化/清理异常和直接 Exception 均不会产生成功结论。
临时单元回收用例使用实际子进程/管道，但 systemd 的 `not-found` 及原身份观察仍是模型。
没有在本执行器运行真实 quota syscall 或完整三单元宿主验收。

三个默认入口也实际独立运行：

| `python -I -B` 入口 | 退出 | 结果 |
| --- | ---: | --- |
| `tests/e3_host/q2_launcher.py` | 3 | `BLOCKED / EXPLICIT_PRIVATE_FIXTURE_REQUIRED` |
| `tests/e3_host/q2_resident.py` | 3 | `BLOCKED / EXPLICIT_PRIVATE_FIXTURE_REQUIRED` |
| `tests/e3_host/q2_phase_driver.py` | 3 | `BLOCKED / EXPLICIT_PRIVATE_FIXTURE_REQUIRED` |

全部保持 `q3_accepted=false`、`production_supported=false`。
源码语法编译与 diff 检查通过。

原始结果：[jobs.log](validation/q2-resident-20260925/jobs.log)、
[quota.log](validation/q2-resident-20260925/quota.log)、
[launcher.log](validation/q2-resident-20260925/launcher.log)、
[resident.log](validation/q2-resident-20260925/resident.log)、
[driver.log](validation/q2-resident-20260925/driver.log)、
[metadata.json](validation/q2-resident-20260925/metadata.json)。

| 文件 | SHA-256 |
| --- | --- |
| jobs.log | `e216b95d27ad08b3c3e412a73f9e4acb9343b6c7919a28c1c22cdf153f9a9d64` |
| quota.log | `9741ebf1d755a1f52dfd3f166f5865131995442f13be8eb3e2ab77e802ae466f` |
| launcher.log | `a6d40666e6742373922c418627374110e0a620d60e182add16737c8101ede09c` |
| resident.log | `9a12bccfb52a29ba3bd568740befc2dbcc30ade5902c875b95e7d298c2b6fc48` |
| driver.log | `0d09cad73594dd5ff0349b86f84c58e43eb336225581bb5758f5b5fb7c484956` |

## 开发中发现的问题

装配初测的异常类型预期、合成 runner 路径和关闭摘要包装在开发期间被纠正；没有放宽原预算、
身份或关闭合同。独立源码复核还发现了 listener 发布顺序、有限轮询余额、bind/start 竞争、
临时单元停止后回收、旧字节码加载及直接 JobError 逃出异常边界的问题。本批分别修复并加入回归。
早期定向/开发回归只用于排错，不替代上表准确 clean commit 的最终结果。

## CI、接续点与限制

第五批 [36130605599](https://github.com/kongbu0621/infra-local-hand/actions/runs/36130605599)
本轮读回确认 classify-change、Linux semantic-core、Windows semantic-core 均 success。
这是补充第五批报告当时的排队状态，不将旧源码结果归给本批。

本批准确源码 CI [36142992108](https://github.com/kongbu0621/infra-local-hand/actions/runs/36142992108)
已触发；本报告写入时 `in_progress`，尚不宣称通过。

首个 preflight 的 resident 与装配入口已实现。后续应接上同一操作的 business/evidence 原始预留、
持久前驱 CLOSED 关联及总容量占用，再整合外部 root controller 的启动、独立停止和证据封存。
不得通过逐阶段新建独立 journal 绕过前驱，也不得重放历史 fixture 或恢复已消耗预算。
源码整链仍有上述缺口；当前环境也没有实际专用 systemd/委派/quota fixture。
H01–H05、随后 H06–H13 尚未执行，Q2 整体和 Q3/Q4 未完成，生产封堵保持。
