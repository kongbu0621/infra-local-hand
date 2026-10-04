# Local Hand 核心交付：云端与本地 Codex 交接

2026-10-04 +08:00。本页是执行交接，不替代准确 A/B/C；只推进正常执行、取消、同任务恢复和结果收回。

最新接续：[writer 传输 D `0e72ffa`](Q2_CORE_WRITER_TRANSPORT_REVIEW_20261004.md)已在独立 C
`8e891e1` 后实现，准确 A `60756ca` 已获 Owner 批准；不再等待该协议的相同批准。
package v3、原 host writer、marker/BIND/session/host 交叉验证及双 C 来源链已接通。
核心真实链仍未执行，package 仍 null/NOT_ISSUED。只继续原 CLOSED D 的 collector、prepare/plan、
真实执行和全量 usage 缺项，再完成独立审查及原 D4；不能因协议修复而提前发行 F1。
[本机 v2 复核与 D `33de2cc`](Q2_CORE_LOCAL_V2_REVIEW_20261004.md)作为历史记录保留。

后续 Owner 已准确批准本页 A；独立 C `7598886`、部分 D1 输入组件与 D3 六文件终结现已落地。
[最新实施/验证记录](Q2_CORE_AMENDMENT_INPUT_CAPTURE_REVIEW_20261004.md)列出准确源码与未完成项；
不再等待相同 A 的批准，也不把这些输入检查当作 F1。

## 已收回的本地工作

本地已在 `c83dad17040e9f8cec148303083c47311f8b7fb9` 完成既有材料复核，
[准确回传](Q2_CORE_LOCAL_HANDOFF_RESULT_20261004.md)保持原样。准确 anchor 是历史 4 KiB control parent，
与 VM 镜像共享 ext4；专属 hard-limit 记录未找到，不能把 UNKNOWN 当作不存在或当前资格 PASS。
不再重复 K4/R3、不探测内核、不读取 VM 内容、不要求新建/格式化/迁移存储。

云端既有 core-entry 回归在 `1e1ecffb9e952f5210bcb0a40f2c85215e79b993` 已完成；本地也复核 18 项通过。
对应 [CI 37170034690](https://github.com/kongbu0621/infra-local-hand/actions/runs/37170034690) 成功。
这些是已有边界代码验证，H01/Q4/H11 的真实效果入口仍未补齐，不能写成业务已完成。

## 当前准确方案

最小修订 A 为 `0bdb49cae5586be60a7ba31d4a8e8367854d1e8c`，准确摘要与待决定事项见
[历史 OPEN 登记](../governance/Q2_CORE_BINDING_FINALIZATION_AMENDMENT_BASELINE.md)。后续准确 Owner B 已保留于
[独立决定记录](../governance/Q2_CORE_BINDING_FINALIZATION_AMENDMENT_OWNER_DECISION.md)；
它代替未批准的 4009e1b，不改变原核心 CLOSED A/B/C 的历史字节，也不追认部分 D 为可发行。

该 A 保留 approved-input/JIT/身份/安全检查，恢复六文件和原 live receipt v1；撤销第七文件、
local restart 验收、loaded-module/内核源码/完整分配模型支线。
host capture 改成应用限额与文件实际分配观测验收，**不再承诺共享 FS 全过程物理硬峰值**；
这项资源保证变化须明确批准，不能只因数字仍为 64 MiB/16 就声称未改变保证。
streams 合计 52 MiB，实际六文件 allocation 每次 create/write/fsync 后检查；guest 资源限额不变。

## 批准后直接执行的核心计划

准确 B 后先独立提交 bookkeeping-only C，再按三文档实施 D1–D4，首个 D 的 direct parent 必须是 C。
若未出现准确 B，不代造批准、改 gate 或提前新增实现。

| 执行方 | 直接交付内容 |
| --- | --- |
| 云端助手 | approved-input builder/parser、package/HELLO/JIT、真实 admission；dispatcher 八组效果；六文件 finalizer；定向及规定发布验证、独立审查 |
| 本地 Codex | 只能本机完成的私有源与 host binding 复算、准确 private package 独立 build/parse；全部门通过后的唯一现场执行 |

八组真实入口为 `admit`、`install`、`prepare_case`、`plan_case`、`run_h01`、`run_q4`、`recover_h11`，
以及 `phase_facts` + `usage`。完整实施判据见[实施计划](q2-core-binding-finalization-amendment/IMPLEMENTATION_PLAN.md)。
云端先把真实代码补齐，不能继续把 UNIMPLEMENTED/FakeEffects 留给本地冒充现场执行。
本批 candidate 的 create-only 隔离 placement 依原 A 保留，复用既有 SSH/机器准备，不重跑历史安装 batch，
不覆盖旧安装、不改系统配置、不清理现场、不自动重试。

F1 只有一次 marker 与一次 carrier：H01 正常执行并收回结果 → Q4 helper RUNNING 后取消一次 →
H11 对自己的 origin 原 ledger/request/execution/unit/grant/deadline 恢复查询。
前项不 PASS 不创建下一 intent。H11 不借用 Q4 ledger，不重启业务，不重新读取/封装原业务 result。
所有 current guest facts 都在同一 carrier 内读取，不先另行 SSH 探测；本地材料缺失定位准确原件，
不默认值补齐、不重采 guest、不扩大网络或权限能力。

两端接手先核对 HEAD 和未提交工作，干净且可快进时 `git pull --ff-only`；存在分叉或未提交内容则保留。
不 reset/clean/自动 stash/覆盖；合并时保留 c83dad1 回传，避免同时编辑同一文件。
源代码、包、现场分别核算：当前 package=null/NOT_ISSUED，核心批次尚无真实执行或结果收回。
最终报告须逐项列任务执行、退出、取消、同任务恢复、结果证据收回及 live COMPLETE，
同时报告 capture 计费方式和 `full_filesystem_peak_proven=false`。

namespace/watchdog、旧版扩建、存储建设、生产切换、E4–E6 与 NAS 支线继续暂停。
