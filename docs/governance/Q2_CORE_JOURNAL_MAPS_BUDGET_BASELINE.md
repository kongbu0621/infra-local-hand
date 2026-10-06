# Journal maps 累计预算修正：准确待决基线

2026-10-06。**OPEN / NOT APPROVED**。Scope：
`LH-Q2-CORE-JOURNAL-MAPS-BUDGET-v1`，仅 MB1–MB2。没有本范围 Owner B 或独立 CLOSED C。
本文登记已审阅提案，不批准源码、配置、现场观察、窗口或维护。

- R / source：`kongbu0621/engineering-sop`，
  `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- 已直接读取[固定规则](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)；
  既有源 SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- Mandate / decision authority：Owner；exceptions：none；采用及实质变化重审规则不变。
- 准确 A：`d18b490a7cdb63ee43044a29a89746ef78fccff3`，tree
  `6e3bf87b8e3a62344de0ebf93e1d51e099a56320`；parent
  `45cf07df283560493bd211c265aee8cfca029f18`。只包含三文档，无源码/测试/配置。
- [需求](../a2-execution/q2-core-journal-maps-budget/REQUIREMENTS.md)、
  [架构](../a2-execution/q2-core-journal-maps-budget/ARCHITECTURE.md)、
  [计划](../a2-execution/q2-core-journal-maps-budget/IMPLEMENTATION_PLAN.md)。

| A 文档 | SHA-256 |
| --- | --- |
| REQUIREMENTS.md | `868f86ddb157a693aa4ae29267b6d65434dac0c3656b08c94b10d86476974b12` |
| ARCHITECTURE.md | `6d6d455a38666287bf886a39ccf0f0756f4ca34020bd3c00b7b3b139886fcc41` |
| IMPLEMENTATION_PLAN.md | `92fda90f23db943cbafb241c5579ecab53da223b2120f8777908ebf5ae20679f` |

## 定位与具体取舍

[v2 返回](../a2-execution/Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_V2_FIELD_20261006.md)已定位
checkpoint 1 的 maps 累计读取上限：67,115,642 B >64 MiB。6,778 B 为首次越界量，
完整需求未知。marker false、SSH 0；本路径未开始 journal 维护或 H01/Q4/H11。
原始输出未独立认证，早期失败原因及历史 UNKNOWN 不据此补写，全部旧窗口保持消耗。

两项独立只读审阅分别检查资源边界与扫描覆盖，一致支持最小 cap-only 修正。审阅发现的
host-read A 拼写、I/O 预算措辞和原时钟起点歧义已在冻结 A 前修正。
三文档链接、准确提交引用和差异格式检查通过；未修改源码或新增测试、未调用现场。
文档审阅不等于实现验证或 CI/现场 PASS。

具体请求是将每次累计 maps 接受额从 64 MiB 改为固定 **512 MiB**，以及实现验证后的一次
替代预检。512 MiB 为有限工程预算选择，不是假装量得完整扫描需求；仍可能因字节、期限、
drift 或其它原门失败。所有 task 仍逐个检查，单文件 1 MiB 和其它 cap、身份、覆盖、锁、
认证与维护次数保持；禁止自动调额。只在全门通过后同窗完成原维护。

成功扫描最多512 MiB；一次拒绝读取含原单文件探读最多513 MiB+1 B。八次全成功最多4 GiB，
七成功加末次失败最多4097 MiB+1 B。这是 maps 文本工作量，非RSS/落盘额度；不增加其它
输入输出、存储、AS、FD 或时间预算。原15s为协作式期限，不声称强制退出或必定完成。
新方案继续保持原终端资格→Window→输入冻结顺序，不推迟双钟起点。

## 可供 Owner 核实的决定文本

以下为待批准请求，**不是已收到的决定**：

> 按原 R，批准 A `d18b490a7cdb63ee43044a29a89746ef78fccff3` 的
> `LH-Q2-CORE-JOURNAL-MAPS-BUDGET-v1`，关闭 MB1–MB2 范围 Gate。
> 允许累计 maps 读取预算由64 MiB改为固定512 MiB，保留完整逐task扫描、单文件1 MiB
> 和其它检查、认证、15s/900s/780s及预算。先记录准确 B 和独立 C，再实现验证、发布、
> 通过准确候选相关 CI并冻结；之后沿用原session再一次替代预检，全门通过才同窗完成
> 未消费的原journal维护。旧窗口继续消耗，不去重、跳过、自动调参或增加权限，
> 不重试、补采、清理或回滚，不执行H01/Q4/H11或扩展支线。

收到准确决定前仅可继续提案/既有未受影响 CLOSED 开发。新源码实现须在独立 C 后开始。
本地 Codex 接续顺序已经写入 MB1–MB2；不能把一般“继续”当成对准确新预算的批准。
