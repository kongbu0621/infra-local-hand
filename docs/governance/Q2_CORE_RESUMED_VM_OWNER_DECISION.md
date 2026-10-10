# Owner 决定：当前 VM 的原核心接续

Authority：本仓库 Owner，本次对话用户；日期 2026-10-10；事件
`LH-Q2-CORE-RESUMED-VM-CLOSURE-20261010-01`。
R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；A：
`b0aa74f9f7a75d70a82575a2e679e540bb47dc1f`，tree
`ab4861032919d3db94c937100d713e3a35b81ba1`；scope `LH-Q2-CORE-RESUMED-VM-v1`，RC1–RC4。
R 的直接来源/完整性、mandate、Owner authority、无例外和变更控制保持。

## 准确相邻请求

以下保留完整请求，仅将本地链接目标转换为仓库相对链接：

> 外围入口屏蔽已提交本地：`c39ad63`。
>
> 核心接续已固定为[整批方案 A `b0aa74f`](../a2-execution/q2-core-resumed-vm/REQUIREMENTS.md)：接线修复与验证 → 一次 guest 核验 → 一次 journal 扩容及原配置重启 → H01→Q4→H11。失败即停，批内不再逐项审批。
>
> **是否批准该整批实施、执行及必要源码和脱敏记录发布 main？**
>
> 需要这次确认，是因为现有 [AGENTS.md](../../AGENTS.md) 明确终止了旧窗口，并要求新接续单独批准。当前尚未执行新的现场动作。

## 准确 Owner 回复

> 批准

真实回复关闭上述准确 R/A 的 RC1–RC4。独立 C 只登记决定与 CLOSED；D 必须以 C 为
祖先，不 squash。RC1 完成全部实现/验证/发布/安装/冻结后，RC2 仅一次固定 guest 核验；
完整通过才执行 RC3 唯一 10c 维护，完整成功及顶层完成独立通过才执行原 07a 核心三案。
批内不重复审批；失败停止保留，不重放、重试、补采、清理、回滚或增加窗口。
采用原 VM/安装及全部原保护；原件、索引、归档、caller 和机器信息私有。
本决定不证明实现或就绪；在 C，RC1 NOT_STARTED、RC2/RC3 NOT_ISSUED、RC4/H01/Q4/H11 NOT_RUN。
