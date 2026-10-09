# 宿主 FD 与核心接续：已批准基线

**CLOSED for FD1–FD3 only**，scope
`LH-Q2-CORE-HOST-FD-CONTINUATION-v1`，FD1–FD3。
真实[Owner B](Q2_CORE_HOST_FD_CONTINUATION_OWNER_DECISION.md)事件
`LH-Q2-CORE-HOST-FD-CONTINUATION-CLOSURE-20261009-01`保留紧邻准确请求与回复“批准”。
本独立C只登记闭合，不含实现；D必须继承C，不能squash。
R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`及其直接来源/完整性、Owner mandate/authority、
无例外与实质变更规则不变。

准确 A `0ed9ba0a8eefa4d1a88ee46192fc18a5ad3fafc8`，tree
`c29e7439e85229d926a7c632ef1da1a40e95ef7e`，父提交
`f67d3076e0bc6717dd94bf1db7e3ecfaba95e290`。A仅含以下三文档，已发布main：

| 文档 | bytes | SHA-256 |
| --- | ---: | --- |
| [REQUIREMENTS.md](../a2-execution/q2-core-host-fd-continuation/REQUIREMENTS.md) | 5838 | 06cdab5674d06eb614425585e7c45327fe65975f808800eb8432170626fdd718 |
| [ARCHITECTURE.md](../a2-execution/q2-core-host-fd-continuation/ARCHITECTURE.md) | 7419 | 48ade8d19b733ed167f056e83b232ad2c41030add31354d9323f613128c30557 |
| [IMPLEMENTATION_PLAN.md](../a2-execution/q2-core-host-fd-continuation/IMPLEMENTATION_PLAN.md) | 4698 | 1cd7d46c870ee630edd883a9cc00104a90a6f2edfde62304327e36a5155d391c |

普通修复见[离线复核](../a2-execution/Q2_CORE_HOST_FD_REVIEW_20261009.md)，只防止已知
FD不足时继续消费，未实现新所有权协议，也未取得新的现场结果。
后续普通修复候选 `2c3982fab8a8d2330a0e161e77d67d2413e43de7` 的首次
[CI 37945349804](https://github.com/kongbu0621/infra-local-hand/actions/runs/37945349804)
attempt 1为3/3成功；先前f67的首次失败保持，不代替未来FD1准确D验证。

A请求一个完整批次：55件历史原件的有界子进程连续FD持有、重复history引用及全部两端
验证/发行，随后唯一新09c维护及仅成功后原07a H01/Q4/H11。原128 FD等限制与保护保持；
每进程上限和父子累计CPU/RSS/进程成本必须完整验证。新子进程安排属于明确待审变化。
十二代加核心捕获底线15616 MiB/4456 inodes，所有旧消费、UNKNOWN和原件继续保留。

新09c caller/package/window **NOT_ISSUED**，FD1 **NOT_STARTED**，FD2 **NOT_ISSUED**，
FD3/H01/Q4/H11 **NOT_RUN**。旧09b CONSUMED_FAILED，原冻结及终态门不变。
Owner已明确同意仅公开下方已核验旧09b最小索引；原文及其它机器信息保持私有。

真实B及本独立C只闭合A规定范围；C与实现D分离。不得改动A的历史OPEN字节，普通修复或
旧CI不能代替FD1完整验证。批内子步骤无需重复批准；完整FD2成功原件验证前不允许FD3。
此前OPEN/待批准描述是审批前事实，不构成第二道待批。旧所有窗口、原冻结和UNKNOWN不变。

## 仅获准公开的旧09b最小索引

准确旧D `547bbb05816e17525470b1a3c136b328ff96adc1`。事件
`RT2-09B-ORIGINALS-INDEX-REVIEW-20261009-01`已与原私有索引和已留存副本一致核对。
只公开三列；旧原文、机器元数据和新09c索引仍私有。

| basename | bytes | SHA-256 |
| --- | ---: | --- |
| .lhqjgrow-20261009b.consumed.json | 63853 | 30aa04638c3682a3317a5e83ba5769a167e98ea0e32053b204812ae0a0c03f45 |
| .lhqjgrow-20261009b.events.jsonl | 441 | 9852dffa8014fd2e1385f7aa1d46b6ec37849773830fa13b3d065af0372aa6fd |
| .lhqjgrow-20261009b.pre.stderr | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| .lhqjgrow-20261009b.pre.stdout | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| .lhqjgrow-20261009b.receipt.json | 17254 | cd87d061060c3fdbaad785c46f598ec31f5f806f2b0f88a490e1bf4a7a1261e3 |
