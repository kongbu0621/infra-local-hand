# 固定双归档输入与原核心链

**PROPOSED / Gate OPEN / NOT APPROVED**；`LH-Q2-CORE-RUNTIME-PREPARATION-CONTINUATION-v1`。
实现[需求](REQUIREMENTS.md)，复用现有维护、custodian、输入消费者及核心entry/dispatcher。

## 来源与持有关系

保留现有798720 B、19成员的 identity archive 原字节与解析器，继续通过原输入FD持有。
新增且仅新增一个固定失败归档输入FD，绑定旧11a的以下实际材料：

- 五原件：consumed marker、events、pre stdout、pre stderr、receipt；
- 十二记录：原件索引、IR1 immutable freeze、IR2独立terminal、summary、caller完成、
  caller started，以及caller/preflight/execute各stdout/stderr；
- 一份索引绑定上述十七成员。固定排序USTAR在内存中核算为 **409600 B / 18成员**。

两归档实际字节合计1208320 B，各自不超过既有1 MiB单输入上限。新归档不嵌套旧归档，
不增加压缩格式或通用归档功能；两条固定输入均持续持有并复核路径、文件身份和摘要。
新增成员分别按固定名称、准确大小与private pin验证；freeze 79635 B、terminal 91441 B
使用最多128 KiB的固定记录读取界限，其余原有字段界限不变。禁用链接、扩展头、重复/
额外成员、非零padding和追加数据，不在磁盘解包。现阶段仅做内存尺寸核算，未写执行归档。

新增输入使原19个父输入变为20；原55个custodian连续持有的原件及其open-file descriptions
不变。新归档的持续持有从本批打开开始，不追溯声称其外部保留原件此前已由custodian持有。
旧路径读取、保护读取及更早失败仍按原冻结/终态保留，不重复查询。

## 绑定及独立验证

旧11a marker的manifest/pre-description、preflight、receipt、原索引、guest失败与nonce/
source binding必须互相一致。receipt与execute原始返回及实际coordinator/custodian完成
绑定；caller原始双流、双EOF和退出绑定其实际完成记录及terminal。五原件与十二个旧
caller/dependency摘要已离线核对。实际3/3/0证明失败后的本地完成，不是维护成功；
remote_exit仍UNKNOWN。旧11a完整guest诊断按其当时版本核验，不套用旧10d诊断子集。

新失败归档与旧identity archive通过旧11a冻结中的准确archive pin绑定。新source proof
`local-hand-q2-runtime-preparation-continuation-archive/v1`包含两个输入pin、旧11a失败摘要
及固定历史引用。仅沿旧11a的manifest.resume和旧identity reader已定义的位置还原历史；
不引入任意递归、目录搜索或缺项fallback。旧v20记录用原规则读取，保留原canonical历史。

接线采用manifest/receipt v21、preflight v20、journal-transition v21、host-capacity v22、
historical-capacity-obligations/reconciliation v23、source binding input v7；approved-input
外层v1和guest报告v5保持。维护生产者、host消费者和独立core dispatcher均从固定原件
验证新失败来源、完整历史、全部费用和实际成功条件；不只信producer摘要。

## 执行与资源

普通slice修复只改变已确认缺少配置时的准备前判定。配置创建、daemon-reload、启动、
有效属性和kernel cgroup验证沿用原流程，不添加命令、观察、任务或修复重试。
现有四叶身份策略、当前账户/祖先/写位/metadata保护及原Q1/VM/install保持。

两个新caller冻结准确R/A/B/C/D、Owner请求、首次CI、安装、两个归档、来源、成本、
目的地及payload；旧caller和terminal不变。RP2成功接受器验证实际顶层caller与协调器/
custodian、原件和独立消费者；通过后才准备发行原07a，失败写独立终态并阻止两侧重放。
全批最多2次维护连接加1次条件核心连接，无独立诊断或就绪探测连接。

沿用档位2的source/bundle/manifest/receipt/stream、原核心包和Linux argv边界。基于
原完整生命周期计数新增一个持有FD，暂算maintenance handoff 129、core prepare 127，
guest原98；均小于256。此为待实现验证的静态预算，不是新代码已经通过的证明。
RP1须重新独立核对所有父/子峰值、真实256-FD生命周期、CPU/RSS/AS、序列化最大返回及
双归档同时存在时的完整载荷；超限或矛盾停止，不通过减证据或临时抬限解决。

费用由完整旧十七代加新11b、全部旧读取/准备、新source/archive准备及原core捕获组成，
严格采用需求中的25283 MiB/7364 inodes。非排他可用空间不表述为独占预留；一次正常
preflight及同窗准入验证现场条件。离线核对不能证明当前VM、空闲容量或静默条件。

当前dispatcher release pin保持。只有RP1完整源码审查后才能锁定新准确摘要；禁止
移除门禁或单改白名单。旧IR2终态不可转回可执行，RP3不能由合成维护结果释放。
