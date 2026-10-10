# Owner 决定：受保护源码修复后的原核心接续

Authority：本仓库 Owner，本次对话用户；日期 2026-10-10；事件
`LH-Q2-CORE-PROTECTED-SOURCE-CLOSURE-20261010-01`。
R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；准确 A
`eabffdbfbdc1c2d041f35dd9371714625380bf3f`，tree
`0de0a04ed246bbbc95b20f30696214a1ed6354d9`；scope `LH-Q2-CORE-PROTECTED-SOURCE-v1`，PS1–PS3。
R 的直接来源/完整性、Owner mandate/authority、无例外及变更控制保持。

## 准确相邻请求

以下保存完整请求，仅将本地链接目标转为仓库相对链接：

> 源码接入修复已通过六组真实本地准入检查；外围入口继续屏蔽，相关四项回归通过。核心三案仍未运行。
>
> 已固定[整批方案 A `eabffdb`](Q2_CORE_PROTECTED_SOURCE_BASELINE.md)：修复采用 → 一次 guest 核验 → 原维护 → H01→Q4→H11，批内不逐项审批。
>
> **是否批准整批实施、执行及必要源码和脱敏记录发布 main？**
>
> 需要确认，是因为你提供的 [AGENTS.md](../../AGENTS.md) 明确禁止失败后重放或新增窗口，并要求新接续取得准确基线授权。

## 准确 Owner 回复

> 批准

本回复对上述准确 R/A 关闭且仅关闭 PS1–PS3。独立 C 只记闭合；D 必须以 C 为祖先，
不得 squash。PS1 完成准确来源、旧失败保留、所有调用器接线、完整边界核验、main
发布、准确 D 自己首次 CI、独立安装和冻结后，PS2 仅一次新固定 guest 核验。
仅完整成功和真实数据冻结后，PS3 执行原未发行 10c 的一次 preflight/PASS 同窗 execute；
完整维护原件及实际顶层完成独立通过后直接接原未发行 07a H01→Q4→H11。
批内不再逐项审批；失败/未知/矛盾停止保留，不重放、补采、重试、清理、回滚或加窗。
原所有保护与硬上限保持，新增输出/源码准备按 A 另计，无退款；十五维护义务不变。
授权必要三文档、实现和脱敏记录发布 main；原件、索引、调用器、机器资料保持私有。
本决定不证明 PS1 已实现、guest 就绪、维护成功或核心 PASS；在 C，PS1 NOT_STARTED，
PS2/PS3 NOT_ISSUED，H01/Q4/H11 NOT_RUN。旧 RC2 失败与原冻结仍原样保留。
