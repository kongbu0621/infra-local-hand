# 原证据、修复来源与一次核心接续

**PROPOSED / Gate OPEN / NOT APPROVED**；`LH-Q2-CORE-PERSISTENT-PATH-CONTINUATION-v1`。
实现[需求](REQUIREMENTS.md)；复用现有维护协调器、guest、custodian 和原核心发行器。
既有修复只改变两个准确历史位置的分类，guest 对缺失必备证据的拒绝保持不变。

## 固定证据与来源

继续采用 PS2 的成功核验及已有 VM/安装身份。其旧 authority、原源码和返回保持原值，
不能改写成新批准或当前观察；PP2 原有准入仍核对实际身份与保护条件。新 Owner B/C
授权的是采用这些原件和新 10d，不能使旧 PS3 或路径读取重新可执行。

旧五十五原件继续由原 custodian 继承相同 open-file descriptions；协议、进程计量、
128 FD 限制均不变。旧09c归档和旧10a传输失败归档保持原字节。将原 activation 输入
等量替换为一个固定外层 USTAR，仍只占一个输入 FD，不新增 helper 或原件 FD：

- 内层为完整旧 activation 归档字节；旧 parser、逻辑成员、两个固定源码引用和旧
  PS2 授权原样验证。
- 外层加入 10c 五个实际原件、其原索引、PS1 freeze、terminal release gate、实际
  caller summary 和已有脱敏现场摘要对应的私有原记录；不伪造 post 流或成功返回。
- 一份固定索引绑定上述准确字节。标准 USTAR 对当前固定原件的内存尺寸核算为
  **522240 B / 12 成员**，原上限 **524288 B**；不是可变返回的通用容器。所有成员
  名、原件大小/摘要、顺序及编码固定，不允许链接、扩展头、重复成员、额外尾部数据、
  任意路径或递归归档。唯一内层只调用既有 activation reader，禁止文件系统解包。

完整持有外层 FD 并执行原名称/身份/内容重检；独立维护/核心消费者均验证固定外层及
内层，真实 coordinator 3 / custodian 0 仅作为旧失败保留事实，不能当作新维护成功。
不能将旧 receipt 的 EOF 或自述状态替代实际顶层完成。固定归档不能在执行期扩充。

两次路径读取的实际原件、caller、freeze、index、terminal 留在各自原位置；新冻结
绑定已完成的离线保留核对、准确摘要及缺件事实。它们不进入 55-FD custody 或维护
成功槽；不声称这些外部记录被外层归档连续持有，不减掉其保留及准备/读取成本。

## 无损历史引用

旧 10c marker 为 64729 B，原 65536 B 上限余量不足以直接扩写完整下一代历史。
新版本采用一个固定前代引用：外层内准确 10c marker 的 `manifest.resume`，固定
marker pin、字段及原 canonical 摘要。该旧字段本身含完整历史，不再递归引用新历史。
消费者从同一个已持有归档解析并验证原 v17 记录，再重建新逻辑 resume：原十五份
义务/已消费与未消费事实、10c 的准确失败摘要、新会话 10d 及十六份完整费用。
路径读取/准备费用另行保留，不虚构为维护代数。写入和读回必须逐字 canonical 等价。

这是固定的一层引用，不是新查找器。缺失、替换、循环、另一字段、另一会话、错误
来源摘要或重建差异均拒绝。旧格式仍按原规则消费。新 marker/receipt/transition 和
approved-input 绑定版本、来源与重建摘要；不能只让 producer 接受而漏改独立 consumer。
不得丢历史、删诊断、压低对象数或扩大限制来腾出空间。最终实际及最大输出仍须重算。

本批新格式固定为 manifest/receipt v18、preflight v17、journal-transition v17、
host-capacity-condition v20、historical-capacity-obligations/reconciliation v21；
approved-input 外层仍为 v1，按内部版本准确分派。新固定外层索引使用
`local-hand-q2-persistent-continuation-archive/v1` 的消费契约；磁盘索引保持固定
`files` 映射，版本由绑定它的外层 source binding 指明，不能增加运行期成员。
旧 activation/v2 与 guest report schema 不升级，旧失败按其原版本验证。

## 发行、完成与预算

来源、权限、实测预算和实际 catch/finally 必须覆盖完整 caller 路径。最终准确 D 的
受保护依赖副本在 1 MiB / 32 inodes 内准备，保留原 O_NOFOLLOW、父目录、所有者、
单链接、大小/摘要、持有与重检要求；不得绕过已发生过故障的本地文件边界。
固定归档另占上述独立 1 MiB / 32 inodes 准备池。已存在的副本、原件和成本全部保留。

先 PP1 完成，再 PP2 一次 preflight/PASS 同窗 execute；仅完整原件、独立消费者、
实际 coordinator 与 custodian 成功、最终用量及 EOF 一致，才允许 PP3 原核心发行。
任一步未知/矛盾/失败进入终态，冻结、返回与缺失事实保留，不隐含回滚或重试。
核心执行、取消、同任务恢复和结果语义不变；字段诊断仅传播已有观察，无额外读取。

原维护 FD 交接峰值 128、核心准备上界 126 必须通过完整生命周期重新验证；原累计
CPU/RSS/进程/输出/时间限额不变。原源码 host/guest/custodian 98304/98304/16384 B、
marker/receipt/描述/transition 65536 B、压缩/展开 49152/393216 B、argv 65536 B、
preflight 4096 B、approved-input 1048576 B、核心包 33550320 B、v2 投影 4096 B 不变。
既有 host 源码已接近其上限，只允许必要的内部责任拆分，不能靠增加限额继续。

当前尺寸核算只证明固定旧字节的归档可容纳；新解析器、完整新 manifest、最终依赖
大小及实际现场就绪尚未证明。PP1 必须消除实现和资源未知后才发行。若边界被推翻，
保持停止并按原变更规则处理，不能自动改方案、增加观察、另一窗口或新的产品功能。
