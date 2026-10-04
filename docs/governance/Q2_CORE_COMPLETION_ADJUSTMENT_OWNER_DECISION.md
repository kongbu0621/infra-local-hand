# 核心完成修订 Owner 决定 B

- Decision Authority：Owner（本仓库 Owner 的当前对话用户）。
- Event：`LH-Q2-CORE-COMPLETION-ADJUSTMENT-CLOSURE-20261004-01`。
- 登记日期：2026-10-04，Asia/Shanghai；事件 ID 定位本次决定，不伪造消息平台时间。
- 稳定来源：本仓库本地 Codex 对话中，紧接下列准确请求的 Owner 文字回复；
  原文保存在此 committed record，可由 Owner 核实，不依赖截图作为批准证据。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；原文直接读取，完整性与根 AGENTS 采用记录一致。
- A：`851a1afe4e55196212aa6913e81e0722deed1032`；tree `5b6c8d3a55d8d0678f2b4543f13df32016630fdd`。
- Scope：`LH-Q2-CORE-COMPLETION-ADJUSTMENT-v1`，C1–C3；准确三文档摘要见
  [原 OPEN 基线登记](Q2_CORE_COMPLETION_ADJUSTMENT_BASELINE.md)。

## 紧邻的准确请求

前一回复说明：修复 `6316770` 已合入远端 `main d32f799`，CI 3/3 通过；新 A 仍是 OPEN。
需要 Owner 接受 dispatcher 从 256 KiB 增至 512 KiB，以及 11 个非 quota 池改为应用记账和
边界观察，不再保证瞬时物理硬峰值、可能发现超限后才停止；21 个 quota 根及安全校验保持。
其请求文本为：

> 按原 R，批准 A `851a1afe4e55196212aa6913e81e0722deed1032` 的 `LH-Q2-CORE-COMPLETION-ADJUSTMENT-v1`，接受其中披露的源码上限、存储保证及逐设备保守预留变化，关闭该范围 Gate，执行 C1–C3；先独立 C 再实施。其他预算、时限及原条件单次 F1 不变，支线暂停，生产 E3 限制保持。

前一回复同时明确其仅核对，未实施新 A、未执行现场任务或消耗 F1。

## Owner 回复原文

> 按原 R，批准 A `851a1afe4e55196212aa6913e81e0722deed1032` 的 `LH-Q2-CORE-COMPLETION-ADJUSTMENT-v1`，接受其中披露的源码上限、存储保证及逐设备保守预留变化，关闭该范围 Gate，执行 C1–C3；先独立 C 再实施。其他预算、时限及原条件单次 F1 不变，支线暂停，生产 E3 限制保持。

## CLOSED 登记边界

本独立 bookkeeping-only C 仅保留 B 与更新根 Gate 声明；不修改准确 A 的三份文档及历史 OPEN
基线登记，不包含实施源码、测试、配置、package、marker 或 request。后续 D 必须以 C 为祖先。

批准包括准确 A 中的 524288-byte dispatcher 上限、11 个非 quota 池应用记账与边界观察保证、
逐设备保守预留，以及 remote-result/v2 的明确有限保证和新增准确授权绑定；不把这些要求当成
已经完成的实现或现场事实。跨设备重复预留不可消费，不提高任一 pool 的可写/观察阈值。
未观察的瞬时物理峰值不被证明，停止时可能已经超限；21 个 project quota 根的原约束不变。

原固定 candidate/wheel/projection、权限/凭据/身份/路径/摘要检查、其它数值预算、原时钟与
条件单次 F1 保持。C1–C3 完成及全部旧、新门通过前，release allowlist 仍空、package 不发行。
不新增现场轮次、探针、连接、执行次数、重试、历史重装、清理或系统配置变更；不提升 UNKNOWN。
H11 只使用自己的原 ledger 与 unit 身份，不重启业务、不延长 deadline，不为记账重读业务结果。
namespace/watchdog 与其它支线保持暂停，production `E3_SUPERVISION_UNVERIFIED` 不解除。

本次登记没有创建现场 marker、发出 carrier、运行 guest case 或收回新现场结果。既有 guest
状态未重新观察；治理关闭不是实机验收。R 的原实质变化重新确认规则继续适用。
