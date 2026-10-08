# 保留目标保护，移除通用间接启动类别阻断

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-GUEST-STARTUP-CONTINUATION-v1` / GS1–GS3，依[需求](REQUIREMENTS.md)。
基于[已批准EX架构](../q2-core-exec-continuation/ARCHITECTURE.md)，复用协调器、固定SSH、
GuestInventory和核心消费者；不新增组件、服务、权限入口、cron解析器或观察框架。

## 检查与管理前提的边界

`GuestInventory.startup_manager`继续枚举既有单元并完整解析属性，执行正式身份、
别名/覆盖、受保护根直接引用、业务静止及domain检查。只移除最后对无已知直接业务
关联单元的Exec通用类别匹配及其阻断。六个Exec数组全部成员及顺序继续保留。
`template_startup`继续读取同一次cat的完整fragment/drop-in并检查受保护根；仅移除
为了通用间接类别判断而存在的Exec文本/编码判定。不得跳过完整文本、路径引用或读取校验。
不保留隐藏的类别阻断分支，也不按程序名逐项扩大白名单。

已声明业务的启动边、domain/cgroup、当前进程/writer、持久证据以及其前后复核保持。
NOT_PERFORMED仅标识间接启动穷尽观察，不把整个quiescence或已执行的直接检查标为未执行。
既有或新观察发现业务启动/写入冲突、身份变化、配置引用或管理前提不成立，仍停止。
没有自动停服务、杀进程或更改启动策略的恢复动作。

## 覆盖声明与协议绑定

新固定 `guest_startup_assurance` 对象只有四字段：
`mode=TRUSTED_SINGLE_ADMIN`、`indirect_startup_observation=NOT_PERFORMED`、
`no_undeclared_business_startup=true`、`continuous_exclusion_proven=false`。
true是执行者按Owner批准范围确认管理前提，不是自动探测结论。确认在原私有交接中完成，
不能由“未命中业务路径”或旧host单管理员记录推导；未知/否认时不能进入预检/execute。

该对象进入新manifest/receipt、guest descriptor及pre/post report、最终核心transition，
由source binding、manifest摘要及原件链覆盖；生产者、host验证者、独立guest消费者均
校验准确字段、类型和值及新R/A/C/D。不能只改显示字符串，或用老成功schema读入新保证。
每个实际manager的startup记录保留unit_count/related/domains，唯有原indirect_startup
从CLASSIFIED改为NOT_PERFORMED；pre/post验证者须核对该值与上述固定对象一致。
startup的manager集合必须恰含system，且仅在descriptor存在user域单元时另含user_1100；
缺少/额外manager、缺少标记、错类型或未绑定前提均拒绝，不能给旧报告默认补值。

维护manifest/receipt采用v8，短预检采用v7；短预检字段仍沿EX v6，完整resume的
canonical含LF摘要保持，新增覆盖对象通过准确授权、manifest及来源绑定，不扩大4096 B。
guest输入改 `lhq-journal-growth-input/v2`，报告改 `lhq-journal-growth-guest/v2`，
增加上述对象；pre/post/失败及关机事件使用同一新报告版本，消费者同时更新。
旧descriptor/report v1只用于准确历史校验，不自动升级为新成功证明。所有已存原字节不改。

## 历史与单次状态

新session固定 `lhqjgrow-20261008d`，只改变原九个输出、pidfile/backup的归属；其余
VM参数不改，部分marker也阻断。原状态链LOCAL_CHECKED→CONSUMED→GUEST_QUIET→
POWERED_OFF→BACKED_UP→IMAGE_GROWN→BOOTED→FILESYSTEM_GROWN→VERIFIED保持。
失败STOP_AND_RETAIN/UNKNOWN，不拆窗、续期或引入自动迁移/恢复。

六旧历史顺序06a→07a→07b→08a→08b→08c，逐代保留原schema/授权/嵌套resume。
08c按EX的manifest/receipt v7、descriptor/report v1及五代嵌套resume验证；其准确A
`5b14123206ced8117374d3fd2ef84b9f38784db3`、C
`987c77f6eb16e7ca41d8b1d4ccd7f89faf418d32`、D
`064bdd614db4224c8c7e9d3b011af90622c11066`，R保持。
原消费、动作空、流/事件/nonce、失败原因和UNKNOWN逐项保留，不把旧失败改成新覆盖结果。

预检、消费前同FD重读和核心读取覆盖旧30件、24个旧后续缺席名及新九名；普通文件、
owner/mode/单链接、O_NOATIME/O_NOFOLLOW、held FD/路径/元数据和跨集合inode去重保持。
08c pins只在获批后从保留原件和原私有索引一致性核验固定，不能为冲突更换pins。
普通预检和execute共用原钟/nonce/manifest/累计计量，摘要不代替原件或完整语义检查。

## 核心接线与未证明项

transition采用 `local-hand-q2-core-journal-transition/v7`，host完整核验旧30件、新八件
成功原件及覆盖对象，再投影完整六代历史。独立guest验证相同关系，不声称重读host原件。
reconciliation/historical-capacity-obligations采用v11，host-capacity-condition采用v10；
七代维护9072 MiB/2590 inodes，加核心为9136 MiB/2606（9579790336 bytes），旧UNKNOWN不释放。
四旧核心prior-attempt/prior-quiescence v2及八次SHOW保持；新HELLO等于08d post boot，
且不同于pre，旧四HELLO仍绑定pre。原runtime/wheel/projection/loader和case身份不改。

prior-attempt、contract/freezer、approved-input、package/entry、dispatcher/bootstrap及
返回消费者作为同一个批次更新；新dispatcher摘要按实际源码登记，全部旧pin保留。
核对A/C树、A三文件和B在准确祖先上的字节，D承接独立C；不把文档发布视为批准。

本选择降低间接启动观察覆盖，换取停止开发与核心需求不相称的全机分析。拒绝cron
特例白名单、穷尽脚本审计、提高预算、假报CLASSIFIED、停服务和旧caller重放。
管理前提是否成立由执行者确认；其余准入、实际容量/时限、维护及核心成功仍未证明。
离线证据推翻方案或出现新实质变化时按R评审；不能借本范围增添支线。
