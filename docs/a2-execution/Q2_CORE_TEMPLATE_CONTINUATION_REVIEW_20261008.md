# TC1 实现与源码验证

范围 `LH-Q2-CORE-TEMPLATE-CONTINUATION-v1`，准确A
`80c7c8eaeda0853317c679b31b0ed1f1ac13e49b`；[Owner B](../governance/Q2_CORE_TEMPLATE_CONTINUATION_OWNER_DECISION.md)
已保存。独立C `bb9b3c6e9b397121220c22515e4ef637d12c7297`，tree
`d1e7261208ae8093971b6b127c1095c2e45b1b80`，仅含B及CLOSED登记。
A三文档字节保持；当前实现承接C，旧冻结候选与现场原件未改。

## 实现边界

固定新维护08a，仍条件接续原核心07a。旧06a/07a/07b分别按原v2/v3/v4、原R/A/C/D和
失败前缀校验；07a内层resume保留06a，07b内层resume严格保留06a→07a。
保护读取旧十五件、十二后续缺席名和新九名，同FD重读和身份/链接拒绝保持。
[公开07b最小索引](Q2_CORE_SYSTEMCTL_ORIGINALS_INDEX_20261008.md)与Owner批准的私有附件、
保留副本、原索引和既有调用方输出一致；原文、路径、boot/PID及诊断未公开。

维护manifest/receipt v5、preflight v4顶层绑定准确R/A/C/D及三代resume。
核心host和独立guest消费相同transition v4、reconciliation/history v8；host capacity v7
按四代维护5184 MiB/1480及原核心合5248 MiB/1496计，每代120 CPU-s保留。
来源冻结器追加准确A/B/C验证，入口只接受本次审查的dispatcher字节。
原runtime/wheel/projection/loader、任务身份、模板/别名修复、保护和单次限额不变。

## 已有源码证据与尚待冻结事项

首个相关组463 passed。扩展后的维护/核心全受影响组首次为2492 passed、35 skipped、
1 failed；唯一失败为协调器测试仍断言旧v4回执。更新测试期待至获批v5后，协调器组
37 passed。首次输出保留，不把首次全组描述为全绿。跳过仍为本机环境限制，不计通过。

新增测试覆盖第三代内部resume错序/错授权/类型/额外字段/当前代替换，延伸实际保护读取
和双侧语义拒绝至第三代；验证准确A/B字节、独立C祖先、完整三代预检原4096 B上限、
旧v1/v2/v3交接拒绝及旧消费不可退款。原生模板/别名测试仍只操作私有临时D-Bus和unit目录。
源码审查确认所有既有历史hash字面值保持；准确A和入口dispatcher摘要匹配。

本记录随实现提交，尚不宣称准确D发布、独立安装、真实保留输入核对、准确CI或冻结已完成。
这些完成前不得进入TC2。TC2/TC3尚未执行，旧三代消费及UNKNOWN保持。
