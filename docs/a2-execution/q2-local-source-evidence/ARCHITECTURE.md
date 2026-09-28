# Q2 固定本地来源补证：架构

- Authority：Owner；状态：**PROPOSED / Gate OPEN / 尚无本 scope 的 A/B/C/D**。
- Scope：`LH-Q2-LOCAL-SOURCE-EVIDENCE-v1`；R及固定来源/上限与[需求](REQUIREMENTS.md)一致。
- 本架构只建立独立local-only读取分支；旧K4、消费入口、wrapper执行适配与远端链保持分开。

## 组件与职责

| 组件 | 责任 | 明确边界 |
| --- | --- | --- |
| 精确离线包验证器 | 验证新旧批准链、准确D工具闭包、P/M/T bytes与固定角色，派生目标 | 私有数据不当成代码执行，不接受caller任意目标/命令 |
| 固定目标派生器 | 从P/M/T生成7+4清单、两个父目录及固定消费名 | 只提供定位/原文匹配关系，不提供费用采用或历史执行证明 |
| 本地观察器 | 单一双钟链下核验身份、boot、marker不存在、保护与11文件事实 | 普通证据坚持noatime；不写、不remote、不调用wrapper |
| 已有固定内核读者 | 为该local-only分支提供两固定视图 | 沿用K01–K07相关读取/ABI/挂载资格语义；不扩到writer |
| 有界回执编码器 | 整合逐项事实、raw、缺项、来源与实际时序 | 回执不是持久seal/历史鉴证/消费权；不输出READY或ADMITTED |

新分支用独立报告schema；不能在旧K4报告里悄悄扩目标，或让旧解释器接受新scope。
原public/private数据边界保留：代码与脱敏合同不含真实路径/boot/连接参数，准确私有
目标由固定输入解析；私有原件和机器回执不复制到公共仓库。

## 离线目标派生

### P：父目录与消费定位

只AST解析顶层唯一字符串常量HOST_RESULT、HOST_OLD。二者均须为规范绝对路径、
父目录相同，沿用原host合同派生唯一父目录。固定消费名仍由原startup C
`d4a925c883672fadc7d1b10a8dfe58df18b922cd` 的UTF-8无换行文本SHA派生。
不执行AST代码；路径/常量冲突、重复赋值或未知结构拒绝。

### M：七个直接相邻文件

严格JSON无重复key/浮点/非有限数；49条entries必须唯一且每项source_path与
source_metadata.path一致。确认原结构为5个直接子目录、7个位于P父目录的直接普通
文件、其余项为五目录内既有成员。选择这七项并按source_path字典序分配M01–M07；类型必须regular，留存size
及SHA从固定M解析且与需求长度表一致。返回路径保留定位来源M及源entry索引。
不扫描五树、不允许按glob发现新文件，也不把M的stat升级为需当前完全相等的历史身份。
原七份旧pin只在离线输入中核对，不触发额外现场文件读；本地内容读取始终只有11项。

### T：四原件与预期boot

严格解析T.boot_id，保持已有boot pin。只从vm_control_files选择准确四个basename；
每项路径规范且互异、parent相同、长度和SHA与需求表完全一致；重复、缺项、额外
控制项或路径别名均拒绝。两个父目录若意外重合或11文件路径重合也拒绝，不自行合并范围。
T的其它字段不得成为程序决策输入。新分支只采用上述四项定位/匹配用途。

目标证明清单在RAM包含源原件SHA、源字段/entry、逻辑ID、准确目标路径、读取模式、
size cap与比较SHA；其规范编码摘要进入回执。清单由原件重算，不接受caller自报摘要。

## 观察顺序与身份

1. 接收器在最早载荷接收前取得本次MONOTONIC/BOOTTIME，准确原点传到全部验证；
   总界300秒、准备界140秒，严禁解包完成后重置。离线失败不读现场。
2. 记录并核验当前真实/有效/保存uid/gid与supplementary groups稳定性，限定原普通
   身份；不以K4历史uid数值当永久pin。namespace对齐沿用K合同的明确环境假设。
3. 固定boot专用读取并匹配T的原boot。沿held no-follow祖先持有两个精确父目录，
   验证root/当前owner、非群组/其它用户可写及现有ACL规则；不降低保护。祖先ACL采用准确local preflight的metadata-only fd流程（只fstat及固定两项getxattr，无read/readdir），不能误用writer的root-only祖先重开流程；普通文件仍NOATIME。普通权限不能完成这些检查时保持BLOCKED。
4. 在P父目录仅stat固定消费名；既存/不确定停止。不创建目录/文件，不试删或接管。
5. 读取一次自身mountinfo，给两个held父目录匹配最具体挂载；分别fstat/statvfs/
   FS_IOC_GETFLAGS，保留不支持错误。这些查询只产生当前事实。
6. 按逻辑ID稳定顺序读取七项，再读取四项。每项操作前后guard身份/双钟/held关系。
   普通文件使用O_NOATIME|O_NOFOLLOW等原保护标志，核对类型、单链接与完整metadata。
   禁止脚本执行、外部进程、目录枚举、依赖扩读或任何持久输出。
7. 最后复核两父目录保护/身份、消费名和固定boot，编码一个有界回执；终端与fd清理
   仍在原窗口，不能超时另起collector补完。

不把步骤6的不同对象解释为原子文件系统快照。每项观察记录其实际双钟范围，当前总量
仅对本次成功观察成员去重；不与旧K4合并宣称同一时刻完整准入。
回执显式记录`k4_trees_reread=false`、`full_host_inventory_complete=false`，旧42对象
只保存其既有回执引用；没有“旧42+新7=本次完整49”的统计通过字段。

## 有界文件读取

七相邻项若当前size不同于固定M长度，记录metadata和`CURRENT_LENGTH_CHANGED`，
不读内容；缺失/权限/保护/身份变化同样保留限定失败。等长才读取到该固定上限并要求
EOF、名称/fd与前后metadata稳定；输出SHA及与旧SHA是否相符，不回传raw。

四原件先检查准确size，读到各自上限并验证EOF/前后metadata及指定SHA。仅全部单项
条件成立时允许该项base64 raw进入回执；不匹配项只输出失败与可得metadata/实际SHA，
不得把新内容自动当替代来源。已匹配项不因另一项失败而伪称整个scope通过。

只有在持有的受保护父目录稳定时确认的目标ENOENT、已固定长度变化、稳定等长内容摘要变化，可记录单项差异并继续剩余固定目标。EACCES/EPERM、未知ACL、对象替换、别名、短读/超长或其它I/O失败均立即停止整个观察；未尝试项明确为NOT_ATTEMPTED。

普通文件有效内容合计上限10,490,352 bytes，各对象一次；每项最多读取其上限加1 byte作为超长检测，实际内容读取总上限10,490,363 bytes。额外检测字节不进入原文回执。实现须独立累计实际read；不能把会重新读取内容的HeldRead.verify直接当成一次读取，前后完整性复核使用held/name元数据，不额外重读内容。不存在补读、降级无NOATIME、
忽略变化、atime恢复或内容变长时再分配预算的路径。观察器遇保护/boot/身份/时钟
不确定立即终止；普通“某项当前size变化”可记录后按剩余固定目标继续，不扩范围。

## 内核与FS资格保持分层

内核读者仅内部枚举boot或自身mountinfo，继续fd/procfs/statx mount ID资格先于内容，
ABI/返回mask不支持则拒绝。内核动态metadata按原K规则记录，不作为历史保全对象。
新scope明确允许该读者用于这里的11对象local-only分支；这不是通用调用权。

两父目录FS结果包括mount匹配、metadata、statvfs、flags及不支持原因。始终输出
`allocation_peak_proven=false`、`durability_proven=false`。普通身份不能读raw device
不会触发提权/变更权限；本scope没有superblock、试写、fsync/掉电试验或write-support。
父目录geometry看似符合实现也不能直接生成消费资格或caller-supplied admission。

## 回执合同与失败

建议独立schema `local-hand-q2-local-source-evidence/v1`，严格字段包括：

- R/A/C、准确D/tree/tools digest、准确package digest、P/M/T来源摘要、目标证明清单摘要；
- 原点/双截止、实际开始结束双钟、阶段、当前身份记录及namespace环境假设；
- 两次boot/一次mountinfo资格详情、两个父目录FS事实、固定marker观察；
- payload输入、普通文件实际read、kernel实际read和输出的独立字节计数；
- 11项逐项source role、目标ID、前后metadata、实际读取字节/时点、SHA/匹配结果、
  四项条件raw、当前allocated/inode去重与未完成项；
- `allow_consume=false`、`allow_run=false`、`wrapper_executed=false`、
  `remote_attempted=false`、`host_persistence_attempted=false`、
  `window_consumed_by_this_invocation=false`、Q2/Q3/production false；
- 历史费用采用、完整共同账单、H07及FS资格仍未证的固定声明。

成功观察为`OBSERVED_PARTIAL`（整个Q2仍partial）；局部阻断为
`LOCAL_SOURCE_EVIDENCE_BLOCKED`。另用逐项完成计数表达本scope完成度，禁止READY/
ADMITTED、未知量0填充。外部双流2MiB共池，报告上限2MiB减16KiB；超限返回有界
错误和已处理计数，不截断后声称完整原文齐全。

## 未采用路线

不追加整个目录扫描；不先执行wrapper看是否工作；不读取私钥或活动VM镜像；不新增
QMP/QGA；不通过sudo/chown/noatime降级解决普通身份问题；不将新观察接入full-run。
这些排除与目标直接相关：L1只补源材料，避免在来源未明时引入执行或新的未知状态。
