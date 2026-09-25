# Q2 第七批固定源码验证

2026-09-25。实现、接口和结论边界见 [同一操作三阶段与外层控制器监督](E3_QUOTA_Q2_CHAIN.md)。

## 准确源码和发布

- 本地源码提交：`8d26e12c6bce3f003c978a080a448d15f2093f2e`。
- Public main 对应提交：`b881f6ea3079706da026c548a3a60bc95738f474`。
- 两者 tree 均为 `2775a3df88ddaa2d520004c75c793baa8b176cd3`。
- 原远端 main `56a8ef85c99bb020ef9147f52a007d14facb396a`，非强制更新后读回核验。
- 下述回归在本地源码提交后的干净工作树执行，结束后仍干净；本报告和原始日志单独提交。
- quota/harness 三层批准文档与 A `415327ebdcc251bb055da9931a7a88990f750b7a` 比对无差异。

## 固定回归

Linux `6.18.44`、Python `3.12.14`，UTC `15:15:48.138682–15:16:13.955134`。
环境为 `PYTHONPATH=tools:tests PYTHONDONTWRITEBYTECODE=1`。

| 命令范围 | 收集 | 通过 | 跳过 | 退出 |
| --- | ---: | ---: | ---: | ---: |
| `python -B -m unittest discover -s tests -p 'test_local_hand_jobs*.py' -v` | 565 | 551 | 14 | 0 |
| `python -B -m unittest discover -s tests -p 'test_e3_quota*.py' -v` | 395 | 394 | 1 | 0 |
| 合计 | 960 | 945 | 15 | 0 |

比第六批增加 88 项测试。15 项跳过共包括 14 项具名 Unix socket 场景和 1 项实际
systemd/cgroup 准入不足：jobs 中分别为 13 和 1，quota 中为 1 项具名 listener 场景。
跳过项不计入通过数，匿名 socketpair 实测不替代具名 listener 或真实宿主验收。

四个默认入口实际独立运行：

| `python -I -B` 入口 | 退出 | 结果 |
| --- | ---: | --- |
| `tests/e3_host/q2_supervisor.py` | 3 | `BLOCKED / EXPLICIT_PRIVATE_FIXTURE_REQUIRED` |
| `tests/e3_host/q2_launcher.py` | 3 | `BLOCKED / EXPLICIT_PRIVATE_FIXTURE_REQUIRED` |
| `tests/e3_host/q2_resident.py` | 3 | `BLOCKED / EXPLICIT_PRIVATE_FIXTURE_REQUIRED` |
| `tests/e3_host/q2_phase_driver.py` | 3 | `BLOCKED / EXPLICIT_PRIVATE_FIXTURE_REQUIRED` |

全部固定 `q3_accepted=false`、`production_supported=false`。变更 Python 源码的内存语法编译、
`git diff --check` 和批准文档不变检查通过。开发期定向回归不重复计入上表。

## 实测与模型边界

本批在实际 SQLite 中串联同一操作的 preflight、business 和 evidence；使用实际本地文件、
create-only/fsync、竞争进程 flock、匿名 socketpair、SCM_CREDENTIALS、pidfd、子进程和输出管道。
其中一个整合用例将真实 Python 子进程的 `_capture_stage` 结果写入 SQLite pending proof，
经 phase v2 和逐包凭据通道传递，核对原 proof 摘要及实际小数 `elapsed_seconds` 保持不变。

上述用例中的 systemd 管理器、quota 观察、宿主权限、cgroup 停止和 seal 准入事实仍明确建模。
supervisor 的 20 项用例含实际 Python 子进程、SIGTERM 和 EOF；这不证明真实 systemd
StopUnit、实际专用父 cgroup 为空或 supervisor 自身原独立退出。launcher 三阶段、累计 journal、
容量拒绝、原预算不重置、前驱 CLOSED、失败保留、载荷编解码和封存失败均有回归。
本执行器未运行真实 quota syscall、H01–H13 或完整宿主三单元验收。

## 本批修复和验证重点

- 原操作三阶段共享 resident、broker session、总预算及永久账本；前驱原 CLOSED 持久确认后才推进。
  三阶段成本在首次启动前累计计入，关闭阶段不退款，旧 journal pin 不能重用。
- 修正三阶段管理控制输出与文件数累计，以及静态管理时间、quota 几何信息和最终 receipt 开销。
  receipt 及文件系统块大小在任何 marker 写入前检查，不扩大原预算。
- 实际 SQLite 证据载荷约 200 KiB，暴露旧 bootstrap 限制；加入有界 canonical JSON/zlib 编码，
  精确保留固定历史事件时间。ordinary proof 仅在固定测量字段保留有限小数，权限字段仍为整数。
  重复键、尾随流、压缩炸弹、非 canonical 编码、凭据和超额载荷均拒绝。
- 外层 controller 完成标记改为 fsync 后原子、不可覆盖发布；磁盘结果在有效 seal 前明确为
  `CLOSURE_OBSERVED_SEAL_PENDING`。部分采集、身份变化、错误退出或 seal 失败不能冒充完成。

原始结果：
[jobs.log](validation/q2-chain-20260925/jobs.log)、
[quota.log](validation/q2-chain-20260925/quota.log)、
[supervisor.log](validation/q2-chain-20260925/supervisor.log)、
[launcher.log](validation/q2-chain-20260925/launcher.log)、
[resident.log](validation/q2-chain-20260925/resident.log)、
[driver.log](validation/q2-chain-20260925/driver.log)、
[metadata.json](validation/q2-chain-20260925/metadata.json)。

| 文件 | SHA-256 |
| --- | --- |
| jobs.log | `8076b9ab27dda99374607fdc1dd4746dfe1db46843a7fd47adf5faa534516322` |
| quota.log | `94b26e297d442e34549c4be6320f4630d6dd08ea4541f17db9aaad7e77c3f88a` |
| supervisor.log | `51aa1248c02fd8d86d3b64230ed3c9e1b851a6377294b26b50475755eb31dcb8` |
| launcher.log | `a6d40666e6742373922c418627374110e0a620d60e182add16737c8101ede09c` |
| resident.log | `9a12bccfb52a29ba3bd568740befc2dbcc30ade5902c875b95e7d298c2b6fc48` |
| driver.log | `0d09cad73594dd5ff0349b86f84c58e43eb336225581bb5758f5b5fb7c484956` |

## CI、接续点与限制

第六批 [36142992108](https://github.com/kongbu0621/infra-local-hand/actions/runs/36142992108)
本轮读回确认 classify-change、Linux semantic-core、Windows semantic-core 均 success。
这是补充第六批报告当时的状态，不把旧源码 CI 归给本批。

本批准确源码 CI [36153093866](https://github.com/kongbu0621/infra-local-hand/actions/runs/36153093866)
已触发；本报告初稿时 classify-change 成功，Linux/Windows semantic-core 仍运行中。

本批补上源码中的同一操作三阶段、累计永久账本，以及外层目标 controller 启停与封存入口。
其结论上限分别为 `CHAIN_CLOSED` 和 `CONTROLLER_CLOSED / TARGET_CONTROLLER_CLOSURE_ONLY`。
仍保留 `independent_supervisor_stop_required=true`；外层 supervisor 自身原退出必须由其独立所有者证明。

后续实机接续需要准确私有 fixture、相同 clean source 安装、现有专用账户/委派/quota 和原监督者。
还需按顺序完成 H01–H05、H06–H13、总容量峰值和外层原退出验收；当前 Q2 整体验收及 Q3/Q4 未完成。
历史 Q1 verdict、payload、reservation 和已消耗预算保留；不重放历史请求、写入实验或退款。
生产仍为 `E3_SUPERVISION_UNVERIFIED`；不扩展到主机 provisioning、GX10 安装/切换或 E4–E6。
