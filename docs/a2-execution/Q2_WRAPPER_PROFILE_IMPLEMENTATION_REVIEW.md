# Q2 有限 wrapper profile 实现复核

2026-09-29 +08。**原 H1/H4 CLOSED 范围内的兼容组件已完成；现场执行仍未准入。**
它接续 [L1–L6 补证完成](Q2_LOCAL_SOURCE_EVIDENCE_COMPLETION_REVIEW.md)，
不重新采集原文，不更改原脚本，不消费原单次 startup batch。

## 准确实现与范围

| 项目 | 固定值 |
| --- | --- |
| 实现 D | `22efa42ab362ab3ea4b811fc1c1519ddc2ef2bb3` |
| D tree | `276c48f23c84f08cbe6457c9e27864f26d252d5e` |
| Parent | `9d4c03cc80be5b6b156b3b3cee2f3301b2d3d04d` |
| 原 R | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` |
| 原 H A / 独立 C | `8402f0cc82d8a0ac0b9a56716bf276f41cafea37` / `271c07cd16140aa5942dcf3fad468003c58b6b0e` |
| 显式 profile | `env-bash-literal-ssh-v1` |

实现只变更 `tests/e3_host/q2_host_window_delivery.py`，新增
`tests/test_e3_q2_wrapper_profile.py`。H 实施方案的 wrapper 适配与无 guest 隔离验证、
H 架构允许的必要交付修复覆盖这一组件；独立审查确认无需重批原 H。
准确 R、H/K/L 三组三层文件字节保持，H C 为 D 的祖先。冻结 runtime
`b49d3df3d1e76813faf08e59ab4975e25279c2fc`、Plugin、wheel 与既有准确私有交付包未更新。

## 现在支持什么

新增 `analyze_wrapper_profile` 在 RAM 中核对长度、摘要、UTF-8 和完整有限语法。
它只接受十行固定结构：`env bash` 入口、固定 shell 选项、唯一规范绝对字面目录赋值、
准确 SSH 参数顺序及引号、合法字面端口和目标、唯一末尾位置参数转交。
全文件必须匹配；额外命令、替换、自省、重定向、赋值、参数或未检查尾部均拒绝。
字面槽只用于验证收到的原文，不是覆盖 SSH 参数的配置接口。

只有显式传入新 profile 时，`memory_wrapper_argv` 才使用新分支：
`/usr/bin/env bash -c` 接原始 source，原 wrapper 定位为 `$0`，
既有远端 argv 的 `shlex.join` 结果为唯一 `$1`。原 source 字节完整保留，
不重读 wrapper 文件，不另造 SSH 配方。旧默认 API 及其拒绝行为保留。

分析返回 `supported_syntax=true` 时仍固定 `source_execution_admitted=false`。
调用者提供的摘要并不自带 Authority；该分析器没有采用现场执行来源，
也不证明实际工具、环境、cwd、受保护凭据或原生审计费用已经合格。
`env` 的查找机制被保留，不代表原现场 PATH 与受控环境已经证明等价。

## 验证与证据

本地 Python 3.12.14、pytest 8.4.2，依赖与仓库固定要求一致。

| 验证 | 结果与边界 |
| --- | --- |
| 新 profile 68 项 + 原 delivery 26 项 | **94 PASS**；完整语法、拒绝条件、参数边界、RAM-only、旧默认与入口拒绝 |
| contract / receiver / reconciliation entry / host inputs | **49 PASS**；独立的四文件回归 |
| 独立 reviewer 复跑 RAM / field gate / 合成进程 | **3 PASS**，属于上述 94 项子集，不额外累计 |
| 编译、diff whitespace、准确源摘要及冻结文件核对 | PASS |
| 独立源与测试审查 | 无 must-fix；旧默认函数体及五个受保护函数 AST 不变，contract / entry 字节不变 |
| 原 T01 | 328 bytes，仅静态匹配新 profile；旧默认仍拒绝，未执行原件 |

合计 **143 个不同的定向测试通过**，不等同于本地全仓测试通过。
合成进程验证在同一隔离 PATH 内使用 Bash 和无网络 SSH 记录桩，比对 argv、stdin、cwd、HOME；
替换合成源文件后，内存调用仍使用原字节，未重读该文件。
这是受控测试环境的兼容证明，不能转写成原机工具或原生 SSH 验证。

首轮 8 个新增测试失败来自两类测试装配错误：旧错误码断言不准确、拒绝测试未传入 model Window。
仅修正新增测试后得到 94 PASS；不以修改旧测试、放宽实现或跳过案例取得绿色结果。
机器核验、独立审查及脱敏静态原文分析见
[verification.json](evidence/q2-wrapper-profile-20260929/verification.json)、
[independent-review.json](evidence/q2-wrapper-profile-20260929/independent-review.json) 与
[static-source-validation.json](evidence/q2-wrapper-profile-20260929/static-source-validation.json)。

[GitHub CI 36527720495](https://github.com/kongbu0621/infra-local-hand/actions/runs/36527720495)
已在准确 D 完成，整体 SUCCESS，分类及 Linux/Windows 共 **3/3 jobs 成功**。

| 原生 CI | 准确结果 |
| --- | --- |
| Linux job `109274341501` | 源码 2401 PASS / 51 SKIP；独立强制 root collector 16 PASS / 0 SKIP；wheel 验收 94 checks / 292 commands PASS；Plugin 构建、启动 smoke 和归档成功 |
| Windows job `109274341500` | 源码 636 PASS / 879 SKIP；wheel 验收 10 checks / 10 commands PASS；bootstrap、ACL、Local Service、退出码、Junction 和归档成功 |

平台及权限 SKIP 保持原语义，不计为通过；Linux 普通全套中的 root collector 用例由单独强制步骤覆盖。
准确 job、结果与核验边界登记于 verification.json。后继纯文档提交不改变 D 的测试和工作流，
路径过滤不会为它另开这条 CI；不把 D 的结果标为文档提交自身跑过的测试。
旧 SHA 的失败记录保持，不因本次修复被改写为历史全绿。

## 仍未通过的现场条件

`controlled_environment`、`remote_deadline_proof`、`require_remote_deadline`、
`dispatch_original` 和 `capture_framed_memory` 未变更。
成功的 profile 分析不能解除 field readiness 或 H07 拒绝。
未执行私有 source、未读取其依赖、未连接 guest、未创建 marker、未派发现场调用。

后续按[执行准入差额与顺序](Q2_POST_SOURCE_ADMISSION_PLAN.md)继续：核对既有执行来源与依赖，
保留首次远端前独立截止/停止、普通身份 writer、完整费用及 FS 峰值/持久证明义务。
既有 CLOSED 内修复可继续；确有来源用途、内核入口或监督机制变化时，先形成准确受影响 A。
原新 startup batch 仍 NOT ISSUED；Q2/Q3、E3 及 production supported 均未因此通过。
