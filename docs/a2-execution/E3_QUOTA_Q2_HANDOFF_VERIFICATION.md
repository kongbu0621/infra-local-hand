# Q2 第八批固定源码验证

2026-09-25（UTC）。入口、输入与实际执行限制见 [批量前检与保留证据复核](E3_QUOTA_Q2_HANDOFF.md)。

## 准确源码和发布

- 本地源码提交：`edaa3a7692f4ca3187e06c6f244af8c5962ef1cb`。
- Public main 对应提交：`bd9d952f598ac2c1fa568425c5333c2d42af9444`。
- 两者 tree 均为 `ff75a116f1242d6f40aa55d06351da505b10b46a`。
- 原远端 main `c719bbac2eee017b616fc605ca81291d3c2bb136`，非强制更新后读回核对提交和 tree。
- 固定回归在上述本地源码提交后的干净工作树执行，结束后仍干净。本报告及日志另行提交。
- 已批准的 quota/harness 三层文档与 A `415327ebdcc251bb055da9931a7a88990f750b7a` 比对无差异。
- 变更的 8 个 Python 文件内存语法编译和 `git diff --check` 通过。

## 固定回归

Linux `6.18.44`、Python `3.12.14`，UTC `17:26:29.470184–17:26:57.322343`。
环境为 `PYTHONPATH=tools:tests PYTHONDONTWRITEBYTECODE=1`。

| 命令范围 | 收集 | 通过 | 跳过 | 退出 |
| --- | ---: | ---: | ---: | ---: |
| `python -B -m unittest discover -s tests -p 'test_local_hand_jobs*.py' -v` | 565 | 551 | 14 | 0 |
| `python -B -m unittest discover -s tests -p 'test_e3_quota*.py' -v` | 459 | 458 | 1 | 0 |
| 合计 | 1024 | 1009 | 15 | 0 |

本批新增 64 项：完整 fixture 前检 22、离线证据复核 26、旧入口读取/源码导入 9、
supervisor 修复 7。开发期定向运行不重复计数。
15 项跳过仍为 14 项具名 Unix socket 场景，以及 1 项实际 systemd/cgroup 准入不足；
jobs 中分别为 13 和 1，quota 中为 1 项 listener。跳过不计作通过。

七个入口均以独立进程 `python -I -B` 实际执行，不提供 fixture：

| 入口 | 退出 | 默认结果 |
| --- | ---: | --- |
| `q2_fixture_check.py` | 3 | `BLOCKED / EXPLICIT_PRIVATE_FIXTURE_REQUIRED` |
| `q2_evidence_review.py` | 3 | `BLOCKED / EXPLICIT_REVIEW_INPUTS_REQUIRED` |
| `q2_batch_check.py` | 3 | `BLOCKED / ValueError:EXPLICIT_PRIVATE_FIXTURE_REQUIRED` |
| `q2_supervisor.py` | 3 | `BLOCKED / EXPLICIT_PRIVATE_FIXTURE_REQUIRED` |
| `q2_launcher.py` | 3 | `BLOCKED / EXPLICIT_PRIVATE_FIXTURE_REQUIRED` |
| `q2_resident.py` | 3 | `BLOCKED / EXPLICIT_PRIVATE_FIXTURE_REQUIRED` |
| `q2_phase_driver.py` | 3 | `BLOCKED / EXPLICIT_PRIVATE_FIXTURE_REQUIRED` |

## 本批修复和验证范围

1. fixture 前检采用 supervisor/v1 + launcher/v2，一次汇总源码、安装、policy、既存 ledger、
   三阶段路径、程序、容量、父 cgroup 及原监督身份的独立缺口。实际 SQLite 文件只读取后复制至
   RAM，WAL/SHM/rollback 侧车存在即保留并阻塞，不连接或写主机数据库。
2. 离线复核只读显式 output/declarations 两目录的 13 个固定成员和 seal，要求独立给定 seal 摘要。
   复核原实例、停止、EOF、固定交付 argv 摘要、累计声明容量及 seal 字节。实际 producer v1/v2
   产物经过真实子进程、SIGTERM、管道 EOF、文件保存和副本读取往返。嵌套阶段结果、systemd、
   权限和 cgroup 事实仍明确建模；没有实际运行 systemd unit 或 quota syscall。
3. supervisor 原启动可以有限观察 `activating`、尚无 MainPID 的状态；最多 8 次，不重新提交，
   不刷新 deadline，拒绝 InvocationID/PID 更换。首次写入前预留固定记录、seal、目录及块取整；
   封存校验准确成员、目录/文件身份和实际分配量。未获存储准入时保留空目录。
4. 旧单阶段入口先以 nonblocking 打开再验证普通文件，真实 FIFO 不再等待写方。源码使用保留的
   已校验字节加载；实际有效时间戳的恶意 pyc 对照、校验后源码替换、未固定模块和预导入均有回归。
5. 审阅纠正了交接顺序：独立前检退出后不能复用其原 MainPID/InvocationID 再执行 supervisor。
   `CHECKED` 仅为当时快照，正式执行仍需准确原监督服务并自行重新准入；没有新增同进程接续运行器。

严格离线成功状态仅为 `OFFLINE_ARTIFACTS_CONSISTENT`，不审查完整 launcher 三阶段证据，
不证明当前宿主、宿主来源、历史总容量峰值或外层 supervisor 自身原退出。
原 `CONTROLLER_CLOSED` 仍仅限 `TARGET_CONTROLLER_CLOSURE_ONLY`；
`independent_supervisor_stop_required=true`、Q3/生产接纳 false 保持。

## 原始结果

[metadata.json](validation/q2-handoff-20260925/metadata.json) 记录每条准确命令、时间、退出码和日志摘要。
全部原始日志位于 [validation/q2-handoff-20260925](validation/q2-handoff-20260925)。

| 文件 | SHA-256 |
| --- | --- |
| [jobs.log](validation/q2-handoff-20260925/jobs.log) | `dcb603c5ca0dce20737977f434184996f11cc81713c05a619adc3923e3836236` |
| [quota.log](validation/q2-handoff-20260925/quota.log) | `09051f2e4b5cad279e37e5b052fc54c196e029883cbee3a9df74dd6132f0dcd9` |
| [fixture-check.log](validation/q2-handoff-20260925/fixture-check.log) | `a2b05975499c3f3cbec491963e97b9c0d53c47565800a502c1e434bf46273f96` |
| [evidence-review.log](validation/q2-handoff-20260925/evidence-review.log) | `4d153081ebd74d3ce03af1ba5d7870debfa5fd30b08d6846d13dda9c255ec19d` |
| [batch-check.log](validation/q2-handoff-20260925/batch-check.log) | `9ee84b877edd04cec4c83430a446aa6870cf895dba444244da651eefa08caa30` |
| [supervisor.log](validation/q2-handoff-20260925/supervisor.log) | `51aa1248c02fd8d86d3b64230ed3c9e1b851a6377294b26b50475755eb31dcb8` |
| [launcher.log](validation/q2-handoff-20260925/launcher.log) | `a6d40666e6742373922c418627374110e0a620d60e182add16737c8101ede09c` |
| [resident.log](validation/q2-handoff-20260925/resident.log) | `9a12bccfb52a29ba3bd568740befc2dbcc30ade5902c875b95e7d298c2b6fc48` |
| [driver.log](validation/q2-handoff-20260925/driver.log) | `0d09cad73594dd5ff0349b86f84c58e43eb336225581bb5758f5b5fb7c484956` |

## CI 和实际接续限制

第七批 [36153093866](https://github.com/kongbu0621/infra-local-hand/actions/runs/36153093866)
本轮读回确认 classify-change、Linux semantic-core、Windows semantic-core 全部 success，
补充其报告当时仍运行中的状态；该结果不归属于本批源码。

本批源码 CI [36167230650](https://github.com/kongbu0621/infra-local-hand/actions/runs/36167230650)
已触发，本报告生成时 classify-change 成功，Linux/Windows semantic-core 仍在运行；
后续以该准确提交的任务结果为准。

当前执行器 PID 1 不是 systemd，也没有用户实验 VM 的 SSH 脚本及既有 Q1 安装目录。
真实宿主 fixture 尚未交付到此环境；本轮没有执行 H01–H13、实际 project quota 或完整宿主验收。
后续集中交付准确私有输入和保留证据后，可使用两个检查入口汇总缺口，
再按既定顺序完成真实正常链、故障恢复、全程容量和外层原退出验收。
Q2 整体验收及 Q3/Q4 未完成；生产仍为 `E3_SUPERVISION_UNVERIFIED`。
历史 Q1 UNKNOWN/INCOMPLETE、payload、reservation 和已消费预算继续保留；不重放、不退款。
