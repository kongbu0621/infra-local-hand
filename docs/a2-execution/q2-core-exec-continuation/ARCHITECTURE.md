# 五代完整历史与原核心消费者绑定

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-EXEC-CONTINUATION-v1` / EX1–EX3，依[需求](REQUIREMENTS.md)。
复用[NC架构](../q2-core-names-continuation/ARCHITECTURE.md)的普通协调器、保护读取、
固定SSH及独立核心消费者，未列明改变的接口与信任边界保持。

## 历史、状态和来源

新session固定08c，仅其九个原后缀和新pidfile/backup归属改变，其余启动参数保持。
LOCAL_CHECKED→CONSUMED→GUEST_QUIET→POWERED_OFF→BACKED_UP→IMAGE_GROWN→BOOTED→
FILESYSTEM_GROWN→VERIFIED不变，失败STOP_AND_RETAIN/UNKNOWN；任何部分marker阻断。
无任意session/output-prefix、迁移、自动重试或释放旧窗口。

原06a/07a/07b/08a各保留minimal v2/serial v3/systemctl v4/template v5及原嵌套resume。
新增第五代08b只按原manifest/receipt v6解析，准确R/A/C/D分别为原R、
`68cae882e3b831aaa191e7a877278ccf6ba10e2b`、
`eba5023b13e42d4610533b7e7c4eede3ebd658db`、
`dc538b9034f00c635344defae57b7054319c2184`。
它的嵌套resume仍为NC scope/08b/原四代历史，不改为新五代或新授权。
原nonce、manifest、流摘要、事件、消费、动作空和UNKNOWN必须逐项验证。

旧五代25件、20个旧后续缺席名及新九名贯穿预检、消费前同FD重读和核心读取。
保留O_NOATIME/O_NOFOLLOW、普通文件/owner/mode/单链接、固定上限、held FD、路径与
前后元数据、跨集合inode去重。只用既有固定名称，不扫目录、查询VM或guest补证。
08b五pins仅获批后固定，实施时须与原私有索引和保留副本再次一致；冲突停止，不改pins。

准确新A/B/C来源须由contract/freezer和维护入口同时验证：固定R及所有历史授权、
A/C准确树、A三文件在A/C/D的字节、B在C/D的字节、独立C及D祖先。
新D准确dispatcher摘要按实际实现登记，保留旧全部来源pin及原输入关系。

## 维护协议

新manifest/receipt为 `lhq-journal-growth-manifest/v7` / `lhq-journal-growth-receipt/v7`。
完整resume保留于manifest、marker、receipt、inputs/source binding；新scope/08c、
固定06a→07a→07b→08a→08b顺序及每行全部原字段、授权、五pins、消费和UNKNOWN不删减。

新短预检为 `lhq-journal-growth-preflight/v6`，字段与既有v5相同：
`schema/R/A/C/D/manifest_sha256/window_binding/nonce/usage/window_seconds/change_seconds/resume_sha256`。
摘要仍SHA-256(原canonical(完整新resume))，包括末尾LF，64位小写hex。v6只绑定本
准确授权及五代；拒绝旧v1–v5作为新交接。旧历史协议保留，不自动升级。

预检从实际已验证manifest.resume构造摘要；解析器验证候选固定完整五代；execute按
原起点与累计usage恢复，重读原件、来源、目标、容量，重建完整manifest并同时核对D、
manifest摘要、window binding、nonce、完整resume及其摘要。摘要不能代替原件或权限。
维护host生产者、解析器、execute和私有caller必须一起更新；所有差异在marker/SSH前拒绝。
4096 B上限与原字段类型、双钟、CPU/RSS边界不变，不能换caller重置计量或时钟。

现v5四代最大计量/20位钟样本已验证708 B；新schema版本号和授权字段宽度相同，摘要
固定64字符，因此v6长度预计不增长。此为设计估算，未来D仍需真实五代数据与严格双方
解析验证。完整manifest、transition、approved-input和包不得用短交接长度替代大小检查。

## 原核心投影和累计准入

transition为 `local-hand-q2-core-journal-transition/v6`，仍≤65536 B；host完整验证
旧25件及新八件成功原件，再投影完整五代历史与新维护。新八件仍consumed/events/pre
两流/post两流/receipt/vm.pid；备份沿原完整动作及比较验证。独立guest验证同一完整投影，
不把短摘要当原件，也不声称在guest重新读取host文件。

`local-hand-q2-core-reconciliation/v10`、`local-hand-q2-core-historical-capacity-obligations/v10`
保留六代完整义务；`local-hand-q2-core-host-capacity-condition/v9`按每相关设备计
7776 MiB/2220 inodes，加原核心64/16为7840 MiB/2236（8220835840 bytes）。各120 CPU-s，
UNKNOWN不释放。四旧核心prior-attempt/prior-quiescence v2、八次SHOW固定顺序及原guest费用保持。
新HELLO等于08c post boot且异于pre；四旧核心HELLO仍绑定pre。核心原钟独立于维护。

prior-attempt、contract/freezer、approved-input、package/entry、dispatcher/bootstrap、
返回消费者同步这些版本；guest descriptor/report仍v1，只固定08c和准确来源。
保留输入修复全部Exec成员和顺序、标量唯一性、Names显示解码、身份和动作检查。
原runtime/wheel/projection/loader、安装、SSH/sudo/sshd文法及核心case/project/UUID不变。

## 取舍和未证明项

采用现有短交接表示和固定五代绑定；拒绝通用历史框架、删历史、提高限额、复用旧caller、
多开连接或将维护/核心拆成可独立滥用的权限。没有新组件、迁移、rollback或自动恢复。
修复能否通过完整现场静止检查，以及累计容量和原时限能否满足，仍须唯一获批窗口验证。
离线证据若推翻设计先按R评审，不静默改预算、语义或范围。
