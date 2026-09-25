# Q2 第五批固定源码验证

2026-09-25。范围与剩余缺口见 [第五批实现](E3_QUOTA_Q2_BRIDGE.md)。

## 准确源码和发布

- 本地源码提交：`43f9ec5667af39a795185b71114d1f5c3c094a83`。
- Public main 对应提交：`b8178fc9488a746b4daf160183bf5ef006551c19`。
- 两者 tree 均为 `0cabf78d82d8c98c674f917252807ca2825c5355`。
- 远端原 main `fa1ca9779d82f5a2874fc8277799d5a76aa3075f`，非强制更新并读回核验。
- 测试在本地源码提交后、干净工作树执行；本报告和原始日志为后续独立证据提交。
- 批准的 quota/harness 三层文档与 A `415327ebdcc251bb055da9931a7a88990f750b7a` 比对无差异。

## 固定回归

Linux `6.18.44`、Python `3.12.14`，UTC 11:38:45–11:39:00。
`PYTHONPATH=tools:tests PYTHONDONTWRITEBYTECODE=1`。

| 命令范围 | 收集 | 通过 | 跳过 | 退出 |
| --- | ---: | ---: | ---: | ---: |
| `python -B -m unittest discover -s tests -p 'test_local_hand_jobs*.py' -v` | 526 | 512 | 14 | 0 |
| `python -B -m unittest discover -s tests -p 'test_e3_quota*.py' -v` | 296 | 295 | 1 | 0 |
| 合计 | 822 | 807 | 15 | 0 |

15 项跳过：14 项具名 Unix socket 场景被执行器拒绝，1 项真实 systemd/cgroup 准入不足。
它们不影响本批实际匿名 socketpair、SCM_CREDENTIALS、继承 FD、pidfd 和双管道测试的执行，
但不能把匿名通信结果转记为具名 listener 的实测。

新增 20 项：6 项真实 credentialed socketpair/子进程/FD 拒绝；4 项真实 SQLite 原事件桥接；
6 项显式 modeled 管理监督/账本顺序及失败场景；4 项真实外层子进程/双流/超时/超限采集。
SQLite 用例中的 unit/cgroup 证明仍为模型，管理 coordinator 用例的 systemd/parent/管理员账本存储也为模型。
没有真实 systemd 三单元链或 quota syscall 在此执行。

默认入口实际运行：`python -I -B tests/e3_host/q2_phase_driver.py`，退出 3，
`BLOCKED / EXPLICIT_PRIVATE_FIXTURE_REQUIRED`，`q3_accepted=false`、`production_supported=false`。

原始结果：[jobs.log](validation/q2-bridge-20260925/jobs.log)、
[quota.log](validation/q2-bridge-20260925/quota.log)、
[driver.log](validation/q2-bridge-20260925/driver.log)、
[metadata.json](validation/q2-bridge-20260925/metadata.json)。

| 文件 | SHA-256 |
| --- | --- |
| jobs.log | `1fd32a295fcb63a1b5e273eea928ac44002089e324ab8fde93e97eca690c1730` |
| quota.log | `b36294feb6c072d00cc18d7bd7ac53971e24496fcc13a1d18481c32b09e7d00b` |
| driver.log | `0d09cad73594dd5ff0349b86f84c58e43eb336225581bb5758f5b5fb7c484956` |

## 开发中保留的问题

首轮 coordinator/capture 定向 10 项中 2 项错误：合成 fixture 的 `received_ns` 比
其 receipt `finished_ns` 少 10 ns，准确解码按预期拒绝。修正测试时间为原 receipt 结束时刻后通过，
未放宽时间检查。另在代码复核中修正了 EOF/RemainAfterExit 的等待顺序；最终模型让
客户端在停止服务前保持未 settled，验证新顺序。最终定向 20 项全部通过，再执行上表固定源码回归。

## CI 与限制

上一批 [36125012802](https://github.com/kongbu0621/infra-local-hand/actions/runs/36125012802)
本轮读回确认 classify-change、Linux semantic-core、Windows semantic-core 均 success。
这补充上一批报告当时的 pending 状态，不改变其准确源码范围。

本批 CI [36130605599](https://github.com/kongbu0621/infra-local-hand/actions/runs/36130605599)
已触发；本报告写入时排队，尚不宣称通过。

本批完成了已准备阶段的通信和控制连接，但尚未实现完整常驻 broker test-only composition、
原预算 grant/config/journal 装配及 fixture 启动生命周期。外层采集只记录字节和原客户端退出，
独立服务停止仍由 fixture 监督方提供。Q2 整体未完成；Q3/Q4 未运行，生产封堵不变。
