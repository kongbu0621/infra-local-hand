# Systemctl 修复后单次接续的准确待决基线

状态：**PROPOSED / Gate OPEN / NOT APPROVED**。Decision Authority：Owner。
Scope `LH-Q2-CORE-SYSTEMCTL-CONTINUATION-v1`，SY1–SY3。

R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，沿用根 AGENTS 的可读取直接规则来源、
已登记完整性、Owner mandate/authority、无例外和变更规则。本会话再次读取直接固定来源，
没有复制私有 SOP，也不改变公开摘录的采用状态。

准确 A：`62666eeec9f2f28833876df3d68ce6e8b8e0af54`。
Tree：`52ebb86280484d16e51aa40aca32f43cfceb4458`。
父提交/输入修复源码：`c1fa156e68cf4b9e1909881f859736a933310794`。
A 只新增以下三文档，没有 production/test source、可执行交接、配置或现场操作。

| 文档 | 字节 | SHA-256 |
| --- | ---: | --- |
| [需求](../a2-execution/q2-core-systemctl-continuation/REQUIREMENTS.md) | 5991 | `2656889d68132bf0698c03f1aff77842be7255fa8c7dd5876070029e78f0d5ee` |
| [架构](../a2-execution/q2-core-systemctl-continuation/ARCHITECTURE.md) | 5723 | `ba25e87046caf0ccadbb8792fe8b8390d4df891a88bbd95e93ad48799be5fcb5` |
| [实施计划](../a2-execution/q2-core-systemctl-continuation/IMPLEMENTATION_PLAN.md) | 4796 | `b69186abe3daf2cb9d7457750c15b2f9d4781e2cdc328bab6b1d0c949c87ef6b` |

只提请批准一次固定新维护 `lhqjgrow-20261007b`、保留两代失败和完整费用、同步维护及
核心消费者、准确验证/发布/冻结，以及完整维护通过后同一个尚未执行的核心批
`lhqcore-20261007a`。旧 06a/07a marker 和各五件失败原件保留，不增加第二个核心批。
三代维护保守 host 条件为 3888 MiB/1110 inodes，加原核心 capture 为
3952 MiB/1126 inodes；单次动作、资源和现场期限沿三文档明确的原上限。
没有重试、补采、清理或扩展支线；旧 UNKNOWN 不释放。

A 同时明确请求仅公开旧 07a 五件的 basename/bytes/SHA-256 最小索引，以固化历史身份。
Owner 本机审阅附件事件为 `SC2-07A-ORIGINALS-INDEX-REVIEW-20261007-01`，其五件已与
原 SC2 私有索引及保留副本核对一致。当前这些值未公开；原文、绝对路径、boot/PID、
环境、流正文和其它机器元数据不在披露申请内。没有批准前不得发布该索引。

输入修复 c1fa156 的[首次准确 CI](https://github.com/kongbu0621/infra-local-hand/actions/runs/37635861016)
三 job 全部成功；本地既有 systemctl 定向测试 18 项通过。只隔离验证已存在的修复，
没有运行维护预检、访问 VM/guest 或消费新窗口。此证据不代替未来 SY1 的新 D 验证。

本登记不是 B、C 或执行授权。Owner 决定须准确指明原 R、本 A 和 SY1–SY3，包含上述
最小索引披露边界；随后独立 C 只能登记准确决定与 CLOSED，保持三文件原字节，D 承接 C。
未批准前不得实现新代次、准备可执行交接或消耗新窗口。
