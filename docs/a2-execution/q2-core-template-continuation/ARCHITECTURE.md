# 三代失败保留与固定08a维护接线

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-TEMPLATE-CONTINUATION-v1` / TC1–TC3，以[需求](REQUIREMENTS.md)为边界。
复用现有协调器、保护读取、固定SSH、预检交接和原核心消费者，不新增常驻组件或权限。
未在本文明确改变的接口、保护和限额沿[上一架构](../q2-core-systemctl-continuation/ARCHITECTURE.md)。

## 状态、历史与存储

06a/07a/07b永久consumed/failed。仅08a沿原LOCAL_CHECKED→CONSUMED→GUEST_QUIET→
POWERED_OFF→BACKED_UP→IMAGE_GROWN→BOOTED→FILESYSTEM_GROWN→VERIFIED；
失败STOP_AND_RETAIN/UNKNOWN。固定08a九后缀、pidfile和backup，其余启动参数不变。
无可自由指定session/output-prefix的入口，不迁移、重命名、删除或更新旧原件。

已有保护读取核验旧十五件、十二个旧缺席名、新九名。保持O_NOATIME/O_NOFOLLOW、
大小上限、held FD、同FD从头有界重读、路径/元数据身份及跨集合inode去重；
预检、消费前、核心读取均一致绑定。只处理已知名称，不遍历新目录或访问guest补证。

06a按minimal manifest/receipt v2，07a按serial v3，07b按systemctl v4逐代严格解析，
核对各自R/A/C/D、nonce、manifest摘要、输入和事件次序、空stdout、失败stderr/receipt
流关系及UNKNOWN。07a旧resume精确指向06a；07b旧resume按06a→07a顺序精确包含两代。
07b同次有界systemctl诊断保持原形状，不把模板失败改写为成功或假造远端监督退出。
旧协议不自动升级，不能用新授权套旧原件。

仅获明确批准后，固定发布旧07b五件最小索引；实施时再次与原私有索引、保留副本、
既有调用方输出一致核对。冲突即停，不自动改pins。原始内容保持私有，不进公开fixture。

## 新协议与完整消费链

新manifest/receipt采用 `lhq-journal-growth-manifest/v5`、`lhq-journal-growth-receipt/v5`，
预检 `lhq-journal-growth-preflight/v4`；顶层准确R/A/C/D绑定本范围。
manifest、receipt、预检、marker/source binding使用同一严格resume：
`scope/session/previous_maintenance`，session固定08a，历史按06a→07a→07b排序。
每行仍仅 `session/D/authority/originals/state/stage/reason/remote_exit/window_consumed`；
authority为R/A/C，originals五条basename/bytes/sha256。字段、类型、顺序固定，
拒绝bool冒充数字、额外字段、旧schema或跨窗关系。保留全部历史授权，禁止自动补齐。
预检≤4096 B；新增历史实际构造超界即阻断，不能裁剪字段、拆交接或扩额。
按既有2842 B预检、第三代1060 B固定行及scope长度差计算，新交接约3902 B；
这只是保留数据的长度算式，TC1仍须验证最终D及实际计量字段，不能当作新实现已通过。

交接仍绑定准确D、manifest、host boot、原双钟、nonce及累计CPU/峰值RSS，拒绝重置。
guest descriptor/report仍v1，仅session和来源改为08a；保留输入修复的模板cat配置检查、
show别名验证、正式目标身份、`--`和同次有界诊断。原返回码/双EOF/空stderr要求不变；
不得添加失败后查询、模拟实例、启动/重载操作或绕过配置检查。

`local-hand-q2-core-journal-transition/v4`仍≤65536 B：host完整核验旧十五件与新八件
成功原件后才投影三代历史和新维护。八件为consumed/events/pre两流/post两流/receipt/vm.pid；
备份由原动作、比较及镜像检查绑定。独立guest核对结构、准确授权/来源和HELLO关系，
不能声称重读host原件，也不把备份正文塞入包。

`local-hand-q2-core-reconciliation/v8`、`local-hand-q2-core-historical-capacity-obligations/v8`
保留四代完整义务；`local-hand-q2-core-host-capacity-condition/v7`每相关设备计
5184 MiB/1480，加核心64/16合5248/1496（5502926848 bytes）。旧UNKNOWN不释放。
四旧prior-attempt/prior-quiescence v2、八次SHOW固定顺序保持；新HELLO等于08a post boot
且异于pre，四旧HELLO绑定pre。原核心身份和核心单次窗口独立于维护时钟。

## 责任与失败边界

维护host负责来源、固定代次、三代原件和交接；guest继续原目标验证及动作。
prior-attempt负责逐代失败解析和完整新成功投影；contract/freezer/approved-input负责
权威来源、累计条件及静态构造；package/entry、独立dispatcher/bootstrap和返回消费者
消费相同新投影。原runtime/wheel/projection/loader、sudo/sshd文法、核心任务语义不变。
实际审过的dispatcher摘要在新D验证后登记，不能挪用旧冻结值。

两段实现、准确CI及冻结全部完成后才进入TC2；之前只做静态检查，不生成真实核心包。
完整维护成功后由同一D保护读取、双构包、独立解析、BIND/HELLO及全部原准入后最多
发一次原核心请求。任何失败保留首因、已有原件及NOT_RUN项。
新固定代次与累计记账为唯一提案路径；旧caller重放、删marker或跳过维护都不可替代。
没有自动rollback、迁移、通用resume框架；假设被推翻即停止并走原变更规则。
