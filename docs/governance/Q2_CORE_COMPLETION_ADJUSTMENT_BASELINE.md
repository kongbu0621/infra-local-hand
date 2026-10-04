# 核心完成修订：准确 OPEN 基线

- Authority：Owner；scope `LH-Q2-CORE-COMPLETION-ADJUSTMENT-v1`，拟授权 C1–C3。
- R：`kongbu0621/engineering-sop`，`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，
  `docs/workflow/program-repository-documentation-gate.md`；direct source SHA-256
  `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- A：`851a1afe4e55196212aa6913e81e0722deed1032`，tree
  `5b6c8d3a55d8d0678f2b4543f13df32016630fdd`。A 仅增加以下三文档。
- Gate：**OPEN / NOT APPROVED**；本范围尚无 Owner B、独立 CLOSED C 或实施 D。
- 继承根 AGENTS 的 Owner mandate、可读 direct source/integrity、Owner-only Authority、无 exceptions
  及实质变化重新确认规则。本登记不能生成批准，也不改变既有不受影响 CLOSED 范围。

| 准确 authoritative 文档 | SHA-256 |
| --- | --- |
| [REQUIREMENTS](../a2-execution/q2-core-completion-adjustment/REQUIREMENTS.md) | `08bba40c9d9c49b2b8af3a15310597514ea61641512b5ca43c70de35f06d46d1` |
| [ARCHITECTURE](../a2-execution/q2-core-completion-adjustment/ARCHITECTURE.md) | `adc7e6be062c6b85deacc774d148bce515aa51c965b3dd31152cee4a73f1455f` |
| [IMPLEMENTATION_PLAN](../a2-execution/q2-core-completion-adjustment/IMPLEMENTATION_PLAN.md) | `a70d51557f034f5f0ec7e626eb6226064a4e604fd6f217267282fe524495f60c` |

## Owner 需要决定的两项变更

1. dispatcher 源码上限 **262144 → 524288 B**，仍为原三个可读 field 文件。
   当前源码 262072 B，准入闭包整合测量已超过旧上限，usage 还未完成。
   不增加原 package 输入、输出、运行资源或时限；最终源码和 package 仍须实际重新核验。
2. **11 个非 quota 存储池**改为应用记账与完整边界观察，保留原数值阈值；不再承诺未观察区间的
   瞬时物理硬峰值。停止时可能已超限，未观察峰值也可能更高。
   21 个 project quota roots 的原内核约束与全部权限、凭据、身份校验保留。
   每 case 36 MiB/2944、全 guest 180 MiB/13440 作为应用/观察总账阈值；276 MiB/16512 为
   单次逻辑准入基准，跨设备完整预算的保守重复不可消费，实际逐设备预留表合计可能更大。

资源记录在 remote-result/v2 内明确 `full_guest_filesystem_peak_proven=false`，保留 32 池的完整
观察记录和摘要；旧 v1 不得静默提升为新 COMPLETE。只有这个结果对象增加 inline 资源及本修订
authority，原 package v3、session、marker、HELLO/BIND、82 output members 和六个 host 文件保持。
H11 不为资源核算读取、stat 或摘要业务结果；原 ledger 不导出。

C1 接回实际 guest 准入；C2 完成真实计数和上述资源记录；C3 完成独立离线审查/冻结并交接原条件
单次 F1。不新增现场轮次、连接、安装重做、清理或自动重试，不改冻结 candidate/wheel/projection。
namespace/watchdog 与其它分支继续暂停，production E3 限制保持。

两项调整不能预先证明当前 guest 已满足全部条件，例如 carrier `pids.peak` 的实际可读性仍须在
原 carrier 内核验；缺失或任何原条件不符即 INCOMPLETE，不新增探针或系统升级路线。

## 已完成的原范围工作

独立修复 D `631677039af3b17392f3269e39a4b1f409fc4f08` 处理 executable binding 的晚返回 I/O，
未改变源码上限或存储语义；其 [CI 37199747854](https://github.com/kongbu0621/infra-local-hand/actions/runs/37199747854)
已 3/3 success。这项修复不依赖新提案批准，也不代表现场验收。
本轮无新 field marker、carrier request、H01/Q4/H11 或新现场证据。既有现场状态未重新观察。

## 准确决定请求

以下是待 Owner 决定的文本，**不是已经发生的批准**：

> 按原 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，批准 A
> `851a1afe4e55196212aa6913e81e0722deed1032` 的
> `LH-Q2-CORE-COMPLETION-ADJUSTMENT-v1`，关闭该范围 Gate，执行 C1–C3。
> 接受 dispatcher 524288 B 上限，以及 11 个非 quota 池的应用记账和观察保证；
> 不要求它们或 guest 聚合具备未观察的瞬时物理峰值证明，结果必须明确该保证未证明。
> 原 21 根 quota、权限/凭据/身份校验、其它运行数值和原条件单次 F1 保持。
> 先独立记录 B/C，再实施；不增加执行次数、不重复历史安装、不清理、不自动重试。

只有 Owner 对准确 R/A/scope 的明确 B 与独立 bookkeeping-only CLOSED C 完成后，才能实施本修订。
三份 A 的历史 DRAFT/OPEN 字节保持不改；后续状态记录引用 A，不能倒签或把 C 与实现混成一提交。
