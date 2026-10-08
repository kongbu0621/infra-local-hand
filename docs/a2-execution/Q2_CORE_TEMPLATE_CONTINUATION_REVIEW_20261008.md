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

## Names 显示格式修复

上文是TC1开发时记录；[后续TC2返回](Q2_CORE_TEMPLATE_CONTINUATION_FIELD_20261008.md)
已登记08a消费失败、PRE_QUIESCENCE/GROWTH_SYSTEMCTL_NAMES、动作空及H01/Q4/H11未运行。
原现场未保存具体Names或单元，所以无法证明历史错误的唯一子条件；没有为此补查现场。

确定的源码缺陷是把 `Names` 字符串数组显示直接 `.split()`。官方v255
[数组属性输出](https://github.com/systemd/systemd/blob/v255/src/shared/bus-print-properties.c)
逐项调用 [shell_maybe_quote](https://github.com/systemd/systemd/blob/v255/src/basic/escape.c)，
而 [Id/Names 属性](https://github.com/systemd/systemd/blob/v255/src/core/dbus-unit.c) 中 Id 是
普通字符串。合法字面名称 `system-systemd\x2dfsck.slice` 的 Names 显示会带双引号并双写
反斜杠；旧解析将引号算进名称，必然触发原格式拒绝。已调用本机系统自带v255纯格式函数
复现，无systemd manager、D-Bus、SSH或真实配置查询。

修复只用标准库 shlex 解码 Names 的显示层，再保留原重复、名称格式、Id成员关系、请求
完整覆盖、属性冲突和声明身份检查。额外逐字校验规范重编码，避免未正确转义的反斜杠被
静默删除；不使用 unicode_escape，不把名称的字面 `\xNN` 转成另一个字符，不扩大名称
后缀或长度范围。普通标量 Id 和其余属性不改写，命令次数不变。

Names仍拒绝时，原错误码不变；在同次已读响应中记录parse/duplicate/format/id_member/
encoding具体条件、单元、响应序号、名称数量、Names完整字节数和SHA-256，以及最多512 B
十六进制前缀和截断标志。不会保存其它属性正文或再发命令。原ctl的返回码、双EOF、
stderr、工具身份检查及全部现场目标/资源/次数限制保持。

最终本地journal全组加minimal/serial/systemctl/template核心接续组：**765 passed / 5 skipped**，
6.75s。新增Names组**46 passed**，无跳过，包含原生格式、转义身份、反例和日志边界。
五个既有环境跳过为PID/proc映射1项、qcow2/ext4工具1项、禁止私有Unix socket的3项模板
原生测试，不计通过。独立审查核对76个原生格式样例；Python -I -B实际装载含shlex的guest
成功；合成最大Id/大Names故障报告2192 B，未带出其它属性。以上小组不重复加进765计数。
`git diff --check`通过；host/guest源64353/60268 B，均低于原98304 B限额。

本次不修改准确批准A或旧冻结D，不创建新维护代次、caller、真实核心包或现场窗口。
准确修复CI须单独核验；代码验证不是现场扩容或核心验收成功。下一步仍只接续容量维护
和原H01→Q4→H11，旧08a及之前所有消费和原件保持，不重放、不补采、不清理。

### 后续交接的确定长度冲突（只读核对）

使用现 `test_e3_q2_core_template_continuation.preflight()` 调用的生产构造器，三条历史
大时钟/最大用量样本为3915 B；将两时钟、CPU、RSS取许可最小正整数后仍为3858 B。
仅在内存复制上一条固定结构，换成同长度08a标识和实际已知的Names失败类别，并把五件
原件bytes全部取0作为长度下界：该第四条无LF为1047 B，连逗号新增1048 B。
因此追加后分别至少4963 B和4906 B，超过4096上限867 B和810 B；两者经实际
`parse_preflight` 都在JSON大小入口报JSON_SIZE，尚未进入schema/授权校验。
这些是合成长度下界，不是08a真实索引或新的有效预检，未生成现场文件或读取私有原件。

本轮不修改该合同或限额。已在[核心交接](q2-core-acceptance-delivery/CORE_EXECUTION_PROGRESS.md)
要求本地下次先离线解决重复历史表示与上限冲突，并提出固定摘要绑定完整manifest历史的
待审方向；完整证据、旧消费和所有身份/时钟/用量检查仍须保留。不能以Names修复CI通过
代替这个准备条件，不能为了验证已知JSON_SIZE而消耗另一个现场窗口。
