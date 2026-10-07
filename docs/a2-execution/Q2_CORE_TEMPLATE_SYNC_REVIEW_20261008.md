# 模板与别名修复的本地同步审查

日期：2026-10-08（Asia/Shanghai）。这是输入修复的既有代码验证及待决方案登记，
不是新执行授权，也没有消耗新窗口。

本地main从 `531bf0a5dc49d88157c283b6e5788a03194f0372` 快进到已发布修复
`94f289e8da83d3d79e2dc1fc09069a1c19eed871`，tree
`87521ea92fe8f88eed904f2591f9c7b70ca51a13`。源码改动仅既有guest模板/别名路径及测试，
修复说明见[此前审查的追加节](Q2_CORE_SYSTEMCTL_CONTINUATION_REVIEW_20261007.md)。
本次未另改production/test source、运行配置或任何旧冻结副本。

## 准确验证

[准确修复首次CI 37650335186](https://github.com/kongbu0621/infra-local-hand/actions/runs/37650335186)
head_sha为上述完整修复SHA，run_attempt=1，三个job均completed/success。
Linux、Windows的源码与独立安装步骤均completed/success。Linux保留日志为
**6419 passed / 89 skipped**；独立安装 **PASS / 94 checks / 292 commands**。
未重跑CI；这不是待实现新接续候选的CI。

本机仅跑现有systemctl/模板两组：第一次 **100 passed / 3 errors**。
三项错误来自隔离临时目录过长，私有D-Bus报abstract socket name too long，尚未启动
配置读取。保留该输出和JUnit，改用短隔离临时路径只验证这三项后 **3 passed**。
没有修改源码、放宽断言、连接真实systemd manager或重跑其余100项。
原生测试读取临时fragment/drop-in/mask；既有参数测试在离线root下拒绝show。
由此本机103项不同测试均取得通过证据，但不把首次运行写成全绿。

既有host/guest维护源为63730/59175 B，均在原98304 B以内；这不证明未来新D大小。
未重复完整源码/安装测试，因为准确CI已完成且本次没有新增实现。

## 已保留数据与下一范围

07b五保留副本用O_NOATIME/O_NOFOLLOW保护读取，核对普通文件、原owner/0600、
界限及前后元数据，逐件匹配原SY2私有索引。marker/manifest与既有预检一致，receipt
与既有execute一致，流长度/摘要一致；已有guest报告仍为PRE_QUIESCENCE/
GROWTH_SYSTEMCTL_STDERR、动作空、无关机token、remote_exit UNKNOWN。
没有读取现场新状态、重连、补采或清理。

另存私有最小索引审阅附件事件 `SY2-07B-ORIGINALS-INDEX-REVIEW-20261008-01`，
仅用于Owner决定五件索引的披露。原索引、原件和终止caller保持不变；新索引值尚未公开。

旧06a/07a/07b均已消费，扩容与H01/Q4/H11仍未完成。原窗口不得重放。
[新三文档的准确A登记](../governance/Q2_CORE_TEMPLATE_CONTINUATION_BASELINE.md)
仅提出一次固定08a维护、保留三代历史和完整费用，成功后原核心接续。
按既有交接与固定新增历史行的长度算式为3902 B，余194 B；最终D仍须实测4096 B上限。
未创建新代次源码、测试、配置、caller、真实核心包或现场预检。Gate保持OPEN，
Owner准确决定和独立C都尚不存在。
