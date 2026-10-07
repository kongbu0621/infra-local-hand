# SY1 实现与隔离验证

范围 `LH-Q2-CORE-SYSTEMCTL-CONTINUATION-v1` / SY1–SY3，准确 A
`62666eeec9f2f28833876df3d68ce6e8b8e0af54`，独立 C
`7b342ced547639f93797e849b34ed3da4915c8d3`，其 tree 为
`ec1ed26d198c9226816ff00de6896eb3d7e102de`。准确决定见
[Owner B](../governance/Q2_CORE_SYSTEMCTL_CONTINUATION_OWNER_DECISION.md)。
本实现承接 C，三文档原字节不变；旧06a/07a消费不改变。

## 实现和审查

- 新维护固定为 `lhqjgrow-20261007b`，核心仍为原未发出的 `lhqcore-20261007a`。
  旧两代各五原件与四缺席名均保护读取、去重和重新校验；07a按旧SC协议解析，并严格
  绑定其内部06a resume。既有同FD重读先seek到起点的修复保持。
- 新manifest/receipt v4、preflight v3、transition v3、reconciliation/history v7和
  host capacity v6接齐；两侧独立消费者拒绝旧协议、错代次、缺失、错序及布尔冒充数字。
  增加准确新A/B/C及继承关系准入；保留原systemctl `--`及同次有界失败信息。
- 三代完整维护条件3888 MiB/1110 inodes，加原核心为3952 MiB/1126；旧费用/UNKNOWN
  不释放。原单次预算、权限、目标检查和期限保持；没有新增扫描、helper或通用组件。
- [旧07a最小索引](Q2_CORE_SERIAL_ORIGINALS_INDEX_20261007.md)已按本次Owner许可登记。
  原私有索引、保留副本及已有调用方输出关系一致；两代保留副本通过实际新解析器。
  原文和其它机器元数据未公开，也未补采。

审查后的独立dispatcher SHA-256为
`5a824dd169e73d3b35eb7307a6ae16920075c63c72338c8af09ecf5ea8608dc2`。
放行只固定此准确源码，仍要求该候选CI/冻结、完整SY2原件、新boot及所有准入。
原runtime/wheel/projection/loader与核心任务身份、取消/恢复语义保持。

## 验证事实和边界

受影响core/journal源码及原journal链组共2346项：2288 passed、35 skipped、23项因普通
宿主umask0002生成组可写测试文件而失败。在隔离测试子进程使用022，仅重验这23项，
23 passed。生产路径保护未修改。前期沙箱映射权限/只读目录失败及旧测试fixture协议
同步前失败日志均保留，没有描述成首次全绿。新增两代历史/嵌套resume和消费者拒绝测试
包含在本组内；独立目标组也为224 passed。

新完整预检使用实际构造，2798 B，原4096 B上限保持；两维护源63730/55793 B，均在
原98304 B内。完整transition、approved-input和包界限继续由原构造/消费者测试验证。

当前仅实现与本地隔离验证完成；准确候选发布后的首次CI、独立安装及静态八输入检查、
两段caller冻结仍须完成，不能把旧c1fa156 CI当作新候选CI。SY2尚未开始，SY3/H01/Q4/H11
尚未执行；CI或合成维护原件不构成现场成功。任一现场失败停止，不重试、补采或清理。


发布后逐条审查补齐了预检顶层准确R/A/C，除原D和完整resume外再显式绑定本次授权。
相关授权/双侧消费/协调器/历史准入组再次通过（300 passed），旧修正前提交不作为现场
冻结候选。最终准确D须包含此修正，并通过其自己的首次CI；现场尚未执行。
