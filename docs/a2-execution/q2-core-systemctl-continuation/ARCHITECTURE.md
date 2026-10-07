# 两代失败保留与固定07b维护接线

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-SYSTEMCTL-CONTINUATION-v1` / SY1–SY3，边界以[需求](REQUIREMENTS.md)为准。
复用已有协调器、普通预检、固定SSH、原核心消费者，不引入服务、权限代理或新通用组件。

## 状态与信任边界

06a和07a均固定为consumed/failed，不参与新状态机前移。07b仍沿原
LOCAL_CHECKED→CONSUMED→GUEST_QUIET→POWERED_OFF→BACKED_UP→IMAGE_GROWN→
BOOTED→FILESYSTEM_GROWN→VERIFIED；任何失败为STOP_AND_RETAIN/UNKNOWN，不接续其它动作。
新九后缀沿原规则；pidfile和backup使用固定07b名称，其它启动参数和serial=null保持。
不存在可自由选择session或output-prefix的CLI，也不迁移、删除或重命名旧原件。

在已有保护读取组件内核验两代各五原件、各四缺席名及新九名。读取保持
O_NOATIME/O_NOFOLLOW、固定大小上限、held FD、同FD从头有界重读、路径/元数据身份和
跨集合inode去重。预检、消费前及核心源读取使用相同绑定；任何缺失、变化、别名或
旧后续名称出现均拒绝。只核对固定名，不遍历新目录、扫描进程或联系guest补证据。

06a解析仍按旧minimal授权、manifest/receipt v2和serial失败前缀；07a解析按旧SC授权、
manifest/receipt v3和systemctl失败前缀。严格核对各自R/A/C/D、nonce、manifest摘要、
输入关系、三状态事件加pre阶段、空stdout、失败stderr与receipt的流绑定。07a的旧resume
还须精确指向06a。不能将当前新授权套进旧原件，也不能用旧失败receipt生成新成功。
旧transport exit UNKNOWN不造退出证明，不增加进程查询、杀进程或回收动作。

07a最小索引只在Owner批准需求中的具体披露范围后发布；实施先对原私有索引、保留副本
和已有调用方输出交叉比对，固定其五件basename/长度/摘要。后续不能自动更新pins以适配
文件变化。原文保持私有，不进公开源码、测试fixture或guest包。

## 协议与数据关系

新 `lhq-journal-growth-manifest/v4`、`lhq-journal-growth-receipt/v4` 和
`lhq-journal-growth-preflight/v3` 的顶层R/A/C/D绑定本范围准确批准与最终D。
保留原growth、minimal和serial授权作为历史。三个协议、marker和source binding携带同一
严格resume对象：本scope、新07b session、按06a→07a固定顺序的两条previous-maintenance，
每条包含准确旧D/授权、五件最小索引和对应失败状态、消费及UNKNOWN；无任意附件。
新resume字段固定为 `scope/session/previous_maintenance`；列表行字段为
`session/D/authority/originals/state/stage/reason/remote_exit/window_consumed`，authority为
R/A/C，originals为五条basename/bytes/sha256。旧resume按旧形状解析，禁止自动升级。
字段集合、类型、顺序固定，布尔不冒充数字。预检仍≤4096 B，其余既有上限不增；
超界即阻断，不通过裁剪、缺项或扩额迁就新关系。

普通交接继续绑定准确D、manifest、host boot、原双钟、nonce及累计CPU/峰值RSS。
拒绝旧schema、跨代/跨窗、重置计量和过期交接。guest原descriptor/report v1形状保持，
仅session/来源改为07b，保留c1fa156的systemctl操作数分隔和同次有界错误信息。
不为再次定位增加查询，不放宽原systemctl结果要求。

核心 `local-hand-q2-core-journal-transition/v3` 仍≤65536 B。host先完整验证旧十件和
新八件成功原件，再生成两代previous-maintenance与新维护关系；八件仍为
consumed/events/pre两流/post两流/receipt/vm.pid。备份通过原实际动作、比较和镜像检查绑定，
不将备份正文塞进包。独立guest只验证准确结构、授权/来源和HELLO关系，不冒称重读host原件。

`local-hand-q2-core-reconciliation/v7`、`local-hand-q2-core-historical-capacity-obligations/v7`
保留三代维护完整承诺；`local-hand-q2-core-host-capacity-condition/v6`按每个相关设备计
3888 MiB/1110加核心64/16，合3952/1126。不得抵销旧费用或用实际旧文件大小替代完整条件。
历史CPU三代各120独立记录；旧UNKNOWN不释放。四旧prior-attempt v2、prior-quiescence v2
及八次SHOW固定顺序不变，新HELLO必须等于07b post boot且异于pre，四旧HELLO绑定pre。

## 模块职责与一致性

维护host负责准确来源、新代次、两代固定原件和交接；guest保留原目标验证/动作。
prior-attempt负责两代失败关系和新完整成功投影；approved-input、contract/freezer负责
来源权威、累计条件和静态构造；package、entry、独立dispatcher/bootstrap及返回消费者
通过原入口消费相同新投影。能复用的字节不机械修改；准确已审dispatcher摘要在验证后登记。
原runtime/wheel/projection/loader、07a核心身份、任务/取消/恢复、sudo/sshd文法不变。

两段实现一起完成准确源码/独立安装/CI与冻结后才开始SY2。维护前只做静态构造检查，
不生成真实核心包；SY2完整成功后，使用同一冻结D读取原件、双构包、独立解析与原
BIND/HELLO/全部准入，最多发送一次原核心请求。任何阶段失败保持已有原件和未执行项。

固定新代次解决已消费旧marker无法重放的问题，保守费用避免把失败当作资源释放。
删除旧marker、放宽设备或静止检查、重跑修复前caller、先发旧核心包均不是备选执行路径。
没有迁移、自动rollback或通用resume框架；若方案假设被证据推翻，停止并按原变更规则处理。
