# 固定新维护代次与原核心链的接线

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-SERIAL-CONTINUATION-v1` / SC1–SC3；范围由[需求](REQUIREMENTS.md)限定。
复用现有维护协调器、普通预检、固定管理SSH和核心消费者，无新服务或权限代理。

## 新旧状态分离

原 `lhqjgrow-20261006a` 永远是 consumed/failed，只读保留。
五件原件为 consumed.json、events.jsonl、pre.stdout、pre.stderr、receipt.json；准确
长度/摘要及旧D绑定使用[已公开现场索引](../Q2_CORE_MINIMAL_CONTINUATION_FIELD_20261007.md)。
固定有界读取交叉验证旧R/A/C/D、nonce、来源、事件顺序、空stdout、失败stderr与receipt，
只接受已登记的PRE_IDENTITY/serial失败前缀。读取保持O_NOATIME/O_NOFOLLOW、held FD、
路径/元数据身份复核；原件缺失、变更、重复inode或关系不符即拒绝。
还检查旧post两流、旧新增vm.pid和旧备份这四个精确名称仍缺席；任何一个出现即阻断，
不猜测新的执行经过。固定名称核对不是目录遍历、进程扫描或额外远程采集。

新 `lhqjgrow-20261007a` 使用原九后缀的独立create-only文件。普通预检要求新九名全部
缺席，execute同窗复核后创建新marker；局部创建或任何既有新文件均永久阻断再次消费。
旧五件在预检、execute消费前及核心接续读取时保持相同绑定。新旧证据不迁移、不重命名。
不增加CLI自由session/output-prefix参数，不允许缺旧marker时假装首次维护。

新状态仍为 LOCAL_CHECKED→CONSUMED→GUEST_QUIET→POWERED_OFF→BACKED_UP→
IMAGE_GROWN→BOOTED→FILESYSTEM_GROWN→VERIFIED。任一步失败为STOP_AND_RETAIN/UNKNOWN；
其余动作不执行。旧状态不参与此状态机的前移，只作为必须保留的前提。
对旧transport exit UNKNOWN不补造退出证明，也不为消除UNKNOWN新增查询或终止进程。

## 权威、接口与数据

新manifest/receipt分别使用 `lhq-journal-growth-manifest/v3` 和
`lhq-journal-growth-receipt/v3`，普通交接为 `lhq-journal-growth-preflight/v2`。
顶层R/A/C/D绑定本范围的准确批准和最终实现，保存原minimal批准为历史授权。
marker、manifest、receipt、预检及source binding带同一个严格resume对象：本scope、
新维护session、旧维护session/准确D、旧五原件的固定basename/长度/摘要及旧失败状态。
字段集合、类型和列表顺序固定；不携带原件正文或任意附件。原现有大小上限不增。
预检仍绑定host boot、双钟原点/期限、nonce、manifest、累计CPU/峰值RSS；旧handoff拒绝。

guest原两阶段descriptor/report形状与有界动作保持，session及来源指向新代次；
序列号只作完整ASCII原字节比较、限制20 B，禁止strip、前缀或截断替代身份验证。
沿已有失败stderr保存同次读取的有界差异，不增加sysfs读取或诊断命令。
新启动只把pidfile改到新代次固定名，并保持serial=null；其余完整参数与原配置等价。

core的 `local-hand-q2-core-journal-transition/v2` 在原≤65536 B内绑定新完整成功原件、
新旧boot和上述previous-maintenance摘要对象。host完整验证旧五件与新八件原件，再构建
投影；guest独立验证结构、准确授权/来源及与HELLO的关系，不冒称重新读取host原件。
新八件沿原成功集合：consumed/events/pre两流/post两流/receipt/vm.pid；完整备份由原
备份/比较/镜像检查结果绑定，不把备份正文塞进包。旧失败或旧v1 transition不能当新成功。

`local-hand-q2-core-reconciliation/v6` 和
`local-hand-q2-core-historical-capacity-obligations/v6` 携带新维护及previous-maintenance；
`local-hand-q2-core-host-capacity-condition/v5` 保留两代完整费用及新核心费用；四旧prior-attempt仍v2、
prior-quiescence仍v2。批准输入仍≤1 MiB、包仍≤32 MiB，超界即阻断而不是裁剪或扩额。
host BIND前、独立dispatcher和最终返回消费者均核对相同transition：新HELLO等于新维护
post boot且不同于pre，四旧HELLO绑定旧boot。四旧八次当前缺席检查、历史UNKNOWN和
完整承诺不变。原runtime/wheel/projection/loader、任务/取消/恢复语义、sudo/sshd文法不改。

## 来源、资源与交付

由维护模块负责新代次/普通交接/旧五件准入，`q2_core_prior_attempt.py`负责旧失败原件
及新完整维护关系，approved-input负责固定投影，contract/freezer/package/entry/
dispatcher/bootstrap及独立返回消费者负责准确授权和端到端消费一致性。
不机械替换所有旧session字符串：旧历史对象保持06a，新动作和新成功原件指向07a，
核心仍lhqcore-20261007a。两段实现必须在维护前一起验证、发布并冻结准确D。

容量计算在既有每设备保守分组中加入旧维护完整1296 MiB/370与新维护同额；核心再加64/16。
不读取或证明其它宿主writer，不假设旧SSH已退出，不抵销重复项，不扩大实际对象和单次限额。
新旧原件的保护读取及解析都计入当前原窗口/CPU/RSS；既有输入/行数/复杂度限制保持。

备选的删除旧marker、沿旧名覆盖输出、放松设备身份、直接执行旧核心包均被排除。
固定新代次使失败历史可审计，同时避免新增通用恢复机制。代价是保守容量门槛更高；
不足、原件变化、审批不符或新对象已存在均停止，不自动选择另一策略。
本范围无迁移、自动回滚或重试路径；出现部分维护失败时保持原恢复边界，另行决定。
