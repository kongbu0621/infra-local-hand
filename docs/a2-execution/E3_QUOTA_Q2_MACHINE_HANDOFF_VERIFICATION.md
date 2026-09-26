# Q2 第九批固定源码验证

2026-09-26（UTC）。本批交付 [现有实验机一次性交接](E3_QUOTA_Q2_MACHINE_HANDOFF.md)，
并修复完整 fixture 前检的正常缓存和普通账户路径兼容性。

## 准确源码与发布

- 本地固定源码：`6f8e7295b029f01d59571ebfcae334cb393779f6`。
- Public main 对应源码：`303f9ca027a883f62763ed23279afd3174293b5e`。
- 两者 tree：`14381818e52c1169318010affb6f90cc0adad3c1`。
- 原远端 main：`6caba637b1da8c0f24f82ed0487a3f939cc993d9`；非强制更新后准确读回 ref 和 tree。
- 完整回归在源码提交后的干净树执行，结束后仍干净；本报告和原始日志另行提交。
- 4 个变更 Python 文件的内存编译和 `git diff --check` 通过。
- 已批准的 quota/harness 三层文档与 A `415327ebdcc251bb055da9931a7a88990f750b7a` 无差异。
- 导出脚本 SHA-256：`a5265e00222eb9cea4a9675627650c4a51adeac69c6383732a3aac0e3a3b8deb`。

## 固定回归

Python `3.12.14`，Linux `6.18.44`；UTC `05:50:09.292437–05:50:35.919080`。
测试环境为 `PYTHONPATH=tools:tests PYTHONDONTWRITEBYTECODE=1`。

| 范围 | 收集 | 通过 | 跳过 | 退出 |
| --- | ---: | ---: | ---: | ---: |
| `python -B -m unittest discover -s tests -p 'test_local_hand_jobs*.py' -v` | 565 | 551 | 14 | 0 |
| `python -B -m unittest discover -s tests -p 'test_e3_quota*.py' -v` | 482 | 481 | 1 | 0 |
| 合计 | 1047 | 1032 | 15 | 0 |

本批新增 23 项：导出器 18、前检 5。开发期定向运行不重复计数。
15 项跳过仍为 14 项具名 AF_UNIX 场景和 1 项真实 systemd/cgroup 准入不足；
不能把这些跳过计作实际宿主通过。

八个独立默认入口以 `python -I -B` 无私有输入实际启动，均 exit 3/BLOCKED：
`q2_host_export.py`、`q2_fixture_check.py`、`q2_evidence_review.py`、
`q2_batch_check.py`、`q2_supervisor.py`、`q2_launcher.py`、`q2_resident.py`、`q2_phase_driver.py`。
导出器原因是 `EXPLICIT_PRIVATE_INPUTS_REQUIRED`，在宿主和 Q1 文件读取之前终止。
每条准确命令、退出和时间见 metadata。

## 实测与建模边界

1. 导出器使用实际本地 fd 测试 FIFO、symlink、hardlink、setid、超长及分块摘要读取，
   覆盖读取期间指纹改变、聚合输入和 stdout 上限。实际 3 MiB ELF 形状测试文件只用于摘要，未执行。
   原 Q1 配置内部绑定算法与保留准备源码核对一致；测试使用合成身份和字段。
   完整 guest 导出路径中的 systemd、DMI、namespace、cgroup 和现场身份明确建模，
   不计为真实 VM 已导出。`EXPORTED` 保持所有 Q2 准入和授权标记 false。
2. 前检接受当前解释器与固定源文件相符的正常 pip 风格缓存，使用有界 no-follow 读取和新编译字节比较。
   实际正常解释器会加载的时间戳有效篡改缓存被前检拒绝；前检本身不执行或反序列化缓存。
3. 普通 resident 路径检查覆盖入口、policy、安装内容/缓存、程序和声明目录。
   runtime 逐层 O_RDONLY 打开目录需 read+search；policy 的普通路径查找只需 search，分别核验。
   权限测试使用实际目录模式和建模的普通 UID/GID；当前执行器 UID 切换返回 EPERM，
   没有冒称真实普通账户执行通过。ACL 依赖仍保留未证明状态。
4. 独立审阅核对了配置摘要配方、原始/revision 字段、所选 slot 范围和目录权限读取语义。
   没有将配置声明、detached HEAD 或现有可用空间冒充独立管理授权、干净源码或新预算。

固定证据不覆盖实际 quota/syscall、用户委派、完整 Q2 fixture 或 H01–H13 宿主验收。

## 结果文件

[metadata.json](validation/q2-machine-handoff-20260926/metadata.json) 保留干净源码、时间、准确命令和摘要。
下列日志为云端测试结果，不含原实验 VM 原始记录。

| 文件 | SHA-256 |
| --- | --- |
| [host-export.log](validation/q2-machine-handoff-20260926/host-export.log) | `4178d4f103f904cb96f38579f3f629863f9293f6bc415d34d1e367e6dc7fe99f` |
| [jobs.log](validation/q2-machine-handoff-20260926/jobs.log) | `92859e9d439549b9f50a92ff39b51e6a4c3109ac74f69f5686771c064e17e3a3` |
| [quota.log](validation/q2-machine-handoff-20260926/quota.log) | `e653149e3470bff5352933a68e8e31759b6fd9f194a71200d9e75688443a2dac` |
| [fixture-check.log](validation/q2-machine-handoff-20260926/fixture-check.log) | `a2b05975499c3f3cbec491963e97b9c0d53c47565800a502c1e434bf46273f96` |
| [evidence-review.log](validation/q2-machine-handoff-20260926/evidence-review.log) | `4d153081ebd74d3ce03af1ba5d7870debfa5fd30b08d6846d13dda9c255ec19d` |
| [batch-check.log](validation/q2-machine-handoff-20260926/batch-check.log) | `9ee84b877edd04cec4c83430a446aa6870cf895dba444244da651eefa08caa30` |
| [supervisor.log](validation/q2-machine-handoff-20260926/supervisor.log) | `51aa1248c02fd8d86d3b64230ed3c9e1b851a6377294b26b50475755eb31dcb8` |
| [launcher.log](validation/q2-machine-handoff-20260926/launcher.log) | `a6d40666e6742373922c418627374110e0a620d60e182add16737c8101ede09c` |
| [resident.log](validation/q2-machine-handoff-20260926/resident.log) | `9a12bccfb52a29ba3bd568740befc2dbcc30ade5902c875b95e7d298c2b6fc48` |
| [driver.log](validation/q2-machine-handoff-20260926/driver.log) | `0d09cad73594dd5ff0349b86f84c58e43eb336225581bb5758f5b5fb7c484956` |

## CI 与下一次现场交接

第八批 [CI 36167230650](https://github.com/kongbu0621/infra-local-hand/actions/runs/36167230650)
本轮已读回 classify-change、Linux semantic-core、Windows semantic-core 全部 success；
补充上一报告当时仍在运行的状态，不将其归属本批源码。

本批源码 [CI 36222011920](https://github.com/kongbu0621/infra-local-hand/actions/runs/36222011920)
已触发；本报告生成时仍在运行。以此准确源码提交的后续任务状态为准。

云端 PID 1 为 `supervisord`，没有用户实验 VM 的现有 SSH helper 或 Q1 安装。
下一步由用户沿既有入口一次执行标准库只读导出，返回一个私有 JSON，集中核对实际装配缺口。
导出脚本支持 stdin；不在 VM 写脚本、创建服务或重放 Q1。有限读取仍需调用侧独立监督。
原 Q1 scoped 收口保持；旧 UNKNOWN/INCOMPLETE 与全部历史对象不变。
Q2 整体、Q3/Q4 和生产验收均未完成，生产封堵继续保留。
