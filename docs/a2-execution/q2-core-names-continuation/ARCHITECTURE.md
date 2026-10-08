# 四代完整历史与短预检摘要绑定

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-NAMES-CONTINUATION-v1` / NC1–NC3，以[需求](REQUIREMENTS.md)为边界。
复用现有普通身份协调器、受保护读取、固定SSH、核心消费者及独立dispatcher。
未明确改变的目标保护、信任边界和接口沿[TC架构](../q2-core-template-continuation/ARCHITECTURE.md)。

## 历史身份和持久状态

四旧代次永久consumed/failed。新08b独占原九后缀，保留LOCAL_CHECKED→CONSUMED→
GUEST_QUIET→POWERED_OFF→BACKED_UP→IMAGE_GROWN→BOOTED→FILESYSTEM_GROWN→VERIFIED；
失败STOP_AND_RETAIN/UNKNOWN。仅新pidfile/backup按08b命名，其余启动参数保持。
无任意session/output-prefix、自动重试或旧数据迁移；部分marker同样阻断。

原06a按minimal v2、07a按serial v3、07b按systemctl v4、08a按template manifest/receipt
v5逐代解析。08a准确R/A/C/D、nonce、原manifest、流摘要、事件次序、动作空和UNKNOWN
保持；其嵌套resume仍为原06a→07a→07b，不能改写成新四代或替换新授权。
前三代各自的嵌套关系同样保持。08a原诊断不含具体Names，不能补造字段或假定修复成功。

维护预检、消费前同FD重读及核心读取核对旧二十件、十六个旧后续缺席名和新九名。
保留O_NOATIME/O_NOFOLLOW、普通文件/owner/mode/单链接、固定上限、held FD、路径与
前后元数据和跨集合inode去重。仅处理既有固定名称，不扫目录、不查VM或guest补证。
08a公开pins只有获批后才固定，须再次与原私有索引/保留副本一致；冲突停止，不更新pins。

## 唯一短交接变更

完整新resume仍为 `scope/session/previous_maintenance`：scope为本范围，session固定08b，
历史固定06a→07a→07b→08a。每行仍仅
`session/D/authority/originals/state/stage/reason/remote_exit/window_consumed`；
authority为R/A/C，originals五条有序basename/bytes/sha256。类型、字段、顺序和每一
历史值精确绑定，拒绝bool替代数值、额外/缺少字段、重复行、错序或旧消费退款。

新manifest/receipt分别 `lhq-journal-growth-manifest/v6`、`lhq-journal-growth-receipt/v6`。
完整resume仍在两者、marker及source binding中，准确新R/A/C/D同时绑定。它们的表示
不缩减为摘要，原件读取和逐代语义校验是准入前置条件。

唯一短预检schema为 `lhq-journal-growth-preflight/v5`，字段准确为：
`schema/R/A/C/D/manifest_sha256/window_binding/nonce/usage/window_seconds/change_seconds/resume_sha256`。
除把 `resume` 换为 `resume_sha256` 及准确新schema/授权外，其余字段形状保持。
摘要是**SHA-256(既有canonical(完整新resume))**，包含canonical的末尾单个LF；
canonical仍为键排序、无多余空白、ensure_ascii、禁止NaN。摘要必须是64个小写hex。
不能使用其它编码、无LF摘要、截断摘要、调用方自选历史、旧三代或嵌套旧resume的摘要。
这只是交接表示，不是新的签名或授权来源；信任仍来自准确候选、原件及全部原检查。

绑定顺序：

1. 普通预检保护读取全部二十件并逐代验证，形成精确完整resume；所有manifest/source
   binding副本一致后，生产者从该**实际已验证manifest.resume**计算摘要。
2. 输出和输入均经严格4096 B原解析器；只接受v5准确字段/类型及本R/A/C，摘要须等于
   候选内固定完整四代历史的canonical摘要。保留D/manifest/nonce格式、900/780、
   boot UUID、两个正整数原钟、正整数CPU/峰值RSS及原最大值，不接受旧v1–v4。
3. execute按原起点及交接usage恢复，重新完成原来源/原件/目标/容量检查，重建完整
   manifest；核对D、expected_manifest、handoff manifest摘要、window binding、nonce、
   完整resume及其摘要的一致性。不得把摘要匹配代替完整历史校验，也不得从摘要合成
   缺失历史。任何差异在marker/SSH/动作前拒绝；消费前仍同FD有界重读并核对缺席名。
4. 私有caller按相同新schema交接，严核旧/新授权、session和输出状态；不把错误转成
   下一次预检，不拆包、重置原钟或清零用量。最终完整manifest的摘要仍覆盖完整历史。

生产者/短交接解析器/execute三处绑定一起实现。按现字段作纯长度算式，大时钟、最大
计量样本约708 B；这是设计估算，尚无新构造器或双侧验证证据。未来D必须以实际四代
数据和真实解析器证实边界及反例；过大、超时或不匹配一律停，不放宽限额。

## 原核心消费链

`local-hand-q2-core-journal-transition/v5`仍≤65536 B，host完整核验旧二十件及新八件
成功原件后投影**完整**四代历史和新维护。八件仍为consumed/events/pre两流/post两流/
receipt/vm.pid；备份经原动作和比较验证。独立guest验证相同四代、准确授权/来源、
原新boot关系及所有原字段，不以短预检摘要代替完整投影，不声称重读host原件。

`local-hand-q2-core-reconciliation/v9`、`local-hand-q2-core-historical-capacity-obligations/v9`
保留五代完整义务；`local-hand-q2-core-host-capacity-condition/v8`按每相关设备计
6480 MiB/1850，加核心64/16为6544 MiB/1866（6861881344 bytes）。不释放UNKNOWN。
四旧prior-attempt/prior-quiescence v2、八次SHOW固定顺序和原guest费用保持。
新HELLO等于08b post boot且异于pre；四旧核心HELLO仍绑定pre，核心时钟独立于维护。
guest descriptor/report仍v1，仅新session和来源绑定08b，Names修复及全部原命令检查保持。

prior-attempt负责四旧失败及完整新成功投影；contract/freezer、approved-input、package/
entry、独立dispatcher/bootstrap及返回消费者一致消费这些版本。维护host拥有短交接
的构造和校验；核心两侧仍消费完整投影，不新增摘要查询服务或通用历史框架。
原runtime/wheel/projection/loader、安装、sudo/sshd文法、核心case/project/UUID保持。
新D的dispatcher摘要必须按实际源码登记；两段冻结完备后才允许唯一维护。

## 取舍与停止

只去除短预检中的重复表示，保留现有完整证据链。拒绝提高4096上限、裁剪历史、
把所有记录改成摘要、拆分窗口或复用旧caller。旧协议保留给准确历史，不作自动升级。
没有迁移、自动rollback或恢复分支；任何设计假设被实际离线证据推翻先按R评审。
修复能否解除现场拒绝、所有累计容量和原时限能否满足仍需唯一获批现场验证，不能预称PASS。
