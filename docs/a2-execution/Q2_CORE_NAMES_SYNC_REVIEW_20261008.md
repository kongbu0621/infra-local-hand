# Names 修复同步与四代历史长度核对

日期：2026-10-08，Asia/Shanghai。仅核对已有代码和保留副本，未访问现场或执行新窗口。
本地main从 `e4682d9f30892e8fd9b01573713d7f1ca30a2d99` 快进到
`82597b78824fe33cd0a1352954b36bb9a6f8041d`，包含修复
`13ba2757aef0f3e48d334c371c367db7dc61a7ec`。本轮没有另外改production/test source、
配置、旧caller、旧冻结副本或生成真实核心包。

## 已有修复验证

[首次准确CI 37710638042](https://github.com/kongbu0621/infra-local-hand/actions/runs/37710638042)
head_sha为上述修复，run_attempt=1，三个job均completed/success。
Linux保留日志 **6571 passed / 89 skipped**；独立安装 **PASS / 94 checks / 292 commands**。
这是输入修复的证据，不是未来新接续D的验证。没有重跑CI或重复完整安装。

本机只运行现有Names、模板、systemctl、template-continuation四个文件：
**175 passed / 12 skipped**，无失败；12项全因本机缺少原生systemd v255格式库，
不计为通过。本机普通Names编码/身份拒绝测试和私有临时模板总线测试通过，未查询
真实systemd manager。准确修复CI与前次开发的v255验证是另外的证据，不能抹去本机跳过。

## 保留副本核对与确定阻塞

仅用现有保护读取函数读取08a五件保留副本，保留O_NOATIME/O_NOFOLLOW、owner/0600、
单链接、上限、路径与前后元数据检查。逐件与原TC2私有索引一致；marker/manifest与
已有预检、receipt与已有execute、流长度/摘要和事件相互一致。准确08a仍是manifest/
receipt v5、原R/A/C/D，原三代resume在marker/manifest/inputs/receipt一致。
失败仍PRE_QUIESCENCE/GROWTH_SYSTEMCTL_NAMES、动作空、无关机token、SSH一次、
remote_exit UNKNOWN。没有读取VM、新查询、重连、补采、清理或重试。

本次用**实际保留五件的长度/摘要**作旧结构的第四条长度反例。既有生产构造器的
三代样本3915 B，第四条追加后4974 B；原钟和计量取最小正数后仍4917 B，超过4096 B。
大样本由现 `parse_preflight` 确认报 `JSON_SIZE`。反例只测旧表示的字节界限，
不是新schema/授权下的有效预检，也没有传给现场入口。

若仅在短交接用64位hex摘要替换完整resume，按现字段和canonical末尾LF作长度减加，
大时钟/最大计量样本的**设计估算708 B**。没有实现新构造器、解析器、测试或可执行原型，
不能把该算式称为摘要绑定已验证；实际D的生产者、解析器、execute及核心两侧完整验证
仍须在准确B/C后完成。旧完整manifest/原件链不缩减，4096 B上限保持。

私有附件事件 `TC2-08A-ORIGINALS-INDEX-REVIEW-20261008-01` 已保存最小索引供Owner
审阅，具体值尚未公开。原私有索引和全部旧证据不修改。

## 当前范围

[新准确A](../governance/Q2_CORE_NAMES_CONTINUATION_BASELINE.md)仅是待决文档：短交接的
固定摘要表示、四代完整历史、新08b一次维护，以及完整成功后原H01→Q4→H11。
旧08a及此前消费保持；没有新caller、现场预检或核心包。新格式与窗口的Gate保持OPEN。
三文档、登记、审查和OPEN声明仅在本地准备，发布和旧08a最小索引披露均待Owner决定。
