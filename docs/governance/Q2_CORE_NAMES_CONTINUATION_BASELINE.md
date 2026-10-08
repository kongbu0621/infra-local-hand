# Names 修复及有界预检接续的准确待决基线

状态：**PROPOSED / Gate OPEN / NOT APPROVED**。Decision Authority：Owner。
Scope `LH-Q2-CORE-NAMES-CONTINUATION-v1`，仅 NC1–NC3。
R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，沿根 AGENTS 的直接来源及完整性、
Owner mandate/authority、无例外和变更规则。本次已直接读取固定规则并核对既定SHA-256，
未复制私有SOP到公开仓库。

准确A：`68cae882e3b831aaa191e7a877278ccf6ba10e2b`。
Tree：`af1df36d31326ae041fd60f7c77499673aeb0cf9`。
父提交：`82597b78824fe33cd0a1352954b36bb9a6f8041d`。
输入修复：`13ba2757aef0f3e48d334c371c367db7dc61a7ec`。
A仅新增以下三份文档，没有production/test source、实现原型、配置、caller或现场命令。

| 文档 | 字节 | SHA-256 |
| --- | ---: | --- |
| [需求](../a2-execution/q2-core-names-continuation/REQUIREMENTS.md) | 5420 | `52fad6aec854cdce4031deb09feabf16fdb393c5f3a1e45fb43230afd12a320f` |
| [架构](../a2-execution/q2-core-names-continuation/ARCHITECTURE.md) | 6741 | `27883a8b69500fcdfa87e4b865faace1aac8849b5acc9802409fece28a4af4db` |
| [实施计划](../a2-execution/q2-core-names-continuation/IMPLEMENTATION_PLAN.md) | 5930 | `a24b97894fbdcd29da8228076ccedf5afc1cb2906e12ff70aa8d58c06a803a06` |

本A、登记与[本地离线审查](../a2-execution/Q2_CORE_NAMES_SYNC_REVIEW_20261008.md)仅本地准备，
未推送。拟请求将三文档、必要脱敏登记/验证/结果和AGENTS声明发布到
`kongbu0621/infra-local-hand` 的 `main`；该新范围的公开发布尚待明确批准。
这与输入修复已公开、旧TC记录已公开是不同事实。本轮没有发起被拒绝的推送。

另请求只公开旧08a五件basename/bytes/SHA-256最小索引，准确旧D
`d5b34316bc93b37442eb5db64ba265b965e68379`。私有附件事件
`TC2-08A-ORIGINALS-INDEX-REVIEW-20261008-01`，附件名
`TC2_08A_ORIGINALS_INDEX_REVIEW.json`，已核对保留副本、原TC2私有索引、已有预检/
execute与marker/manifest/receipt/流关系。五件具体pins仍私有；原文、绝对路径、boot/PID、
环境、诊断、流正文及其它机器元数据不在披露申请中，不回现场补证。

提案只修短预检的重复历史表示，4096 B上限及完整历史验证保持；固定新维护08b，
完整成功后同一冻结D执行原未发核心07a。四旧消费、二十原件、十六后续缺席名、旧
UNKNOWN和完整费用保留。每设备五代维护6480 MiB/1850 inodes，含核心6544 MiB/1866，
各代120 CPU-s及原所有单次限额、时限保持。两段完整实现/验证/发布/准确CI/冻结须先完成。

当前不存在本范围的Owner B或独立C，不得把截图的下一步方向当作准确closure。
需要Owner明确原R、此A、NC1–NC3与上述最小披露；随后独立C只登记准确B与CLOSED，
三文档原字节保持，D承接C。现有代码检查和长度算式不是新格式验证或现场授权。
