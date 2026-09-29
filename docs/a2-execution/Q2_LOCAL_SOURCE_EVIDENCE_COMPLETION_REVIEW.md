# Q2 固定本地来源补证：rerun3 完整回执与限定完成复核

2026-09-29 +08。**准确 89c725ef 的 rerun3 完整 JSON 已收到：11 项 MATCHED，四份控制原文已取得，结果为 OBSERVED_PARTIAL / final_local_recheck。**
本记录接续[六文件维护复核](Q2_FIXED_OBJECT_MAINTENANCE_REVIEW.md)。旧四份 BLOCKED 回执各自保留；
本次只在云端解析上传字节、准确 Git 源码和既有私有来源，没有再次访问原机或执行返回脚本。

## 收件与授权

| 原件 | bytes | SHA-256 |
| --- | ---: | --- |
| q2-local-source-diagnostic-result-89c725ef-rerun3.json | 32,439 | `700a17989fec4271973a0620e87dccee64ce30ef4f7082a97ab42e5b6648f119` |
| q2-local-source-diagnostic-rerun3-static-review-20260929.md | 8,383 | `93eebdd40ca102641fb1b2624ee9a17b8ed41c19cdebf510419bb1aedf127684` |

两份摘要与先前截图相符。完整 JSON、四份 raw、原路径、连接参数和机器身份均私有保留。
本地报告及截图保留 Owner 的准确指令：

> 授权获取提交 172bb13，按 Q2_POST_MAINTENANCE_OBSERVATION_HANDOFF.md 执行一次 89c725ef 本地观察；不再改权限、不重试，完整 JSON 以 0600 新文件保存到 Downloads，并保留旧回执。

交接准确提交 `172bb13fbb5ee4528d2566b0e1b5540ce847b53e`，tree
`9158eaf8c2d49608abed4b1b7bf63d3c4f38d6ae`，parent
`9cc25bccda9d631e3e6c5b975963523a283bec13`。此项 Owner 指令只发起这一次本地观察，
不产生下一次调用、wrapper 执行或 Q2 派发授权。

本地执行方报告一次调用、零重试、退出 0、结果文件 0600、无残留采集进程，
工作树保持 `777926655284e52db296fa0682d3c606e0671f25`，只获取新交接文档。
这些过程/权限事实属于执行方报告；JSON 本身不证明 shell 退出码、外部调用次数或进程清理。

## 准确绑定及逐项结果

观察器 D 为 `89c725efd61dad11b0cc9ae11c3c08a941e3111a`，tree
`15f5a0dceae0f534506abf7195562980459f3ee7`；原 R/A/C 与六工具闭包保持。
回执的包标识为 4,113,937 bytes、SHA-256
`e6ed13681e79492aae5ba8216996056ef03c987c901d4f23db4906989d92eeec`，与既有准确交付登记一致。
独立静态复核的 [73 项检查](evidence/q2-local-source-field-20260928/diagnostic-rerun3-independent-validation.json)
全部通过，未发现内部不一致。六工具的准确 D Git blob 及聚合摘要重新核对；P/M/T 私有原件
按完整长度/摘要校验，再通过 AST 字面值/JSON 独立推导 11 项及 manifest。
本轮恢复空间没有包 archive，包检查限于回执标识与既有准确交付登记一致，未重新散列 archive。
包本身不因收到 JSON 而重新执行或获得运行资格。

| 对象 | 完成情况 | 本次内容读取 bytes | 本次分配量 bytes |
| --- | --- | ---: | ---: |
| M01–M07 | 七项源摘要与实测摘要匹配；各自读前后元数据相同；无 raw 输出 | 10,488,668 | 10,502,144 |
| T01–T04 | 四项匹配并返回 raw；独立解码后长度及 SHA-256 与固定 T 相同 | 1,684 | 16,384 |
| 合计 | 11 attempted / 11 observed / 11 matched / 4 raw | 10,490,352 | 10,518,528 |

四份原文长度依次为 328、1,162、99、95 bytes；用途保持静态来源审查。
七项不返回原文，不能把收到它们的摘要解释为已重新取得七份内容副本。

六个维护对象 M01/M02/M04/M05/M06/M07 的路径、设备/inode、大小、mode 和 ctime-after
与 rerun3 对应 before 逐项相同；各项 before/after 又相等。当前摘要匹配支持本次读取内容
与固定来源一致，但不把各次观察之间未观察的时间段宣称为始终未变化。共享组写入依赖仍 UNKNOWN。

## 时限、计量与最终检查

| 项目 | 本轮核对 |
| --- | --- |
| 输入 | 5,523,278 = 27,191 启动 + 5,496,087 帧；不超过原 16 MiB |
| 普通读取 | 10,490,352；原含 EOF/超长检测上界为 10,490,363 |
| 内核读取 | 5,655 = boot 37 + mountinfo 5,581 + boot 37 |
| 输出声明 | 32,439 JSON + 58 READY = 32,497 stdout；stderr 声明为 0；不超过原 2 MiB |
| 接收原点至观察开始 | monotonic 95,234,514 ns |
| 观察开始至结束 | monotonic 31,087,539 ns |
| 接收原点至结束 | monotonic 126,322,053 ns；双钟与原 140/300 秒界限分别核对 |
| marker | before/after 均 ABSENT_AT_OBSERVATION；不证明其它时刻缺席 |
| namespace | ENVIRONMENT_ASSUMPTION_NOT_PROVEN；未升级为独立原机鉴证 |

本地报告另记 controller elapsed 0.153673 秒；其测量端点不与回执双钟原点混同。
界面整轮工作用时包含准备与复核，不是这次观察器运行时间。

按准确源码，OBSERVED_PARTIAL 只能在两条父链/ACL、最终 marker、boot 及 parent 复检
均返回后设置。11 个文件各自完成持有 fd 的前后元数据、名称绑定及 ACL 核验后关闭 fd；
最终阶段没有重新验证所有文件。因此本次为逐文件读取稳定，不是全体同时稳定的原子快照。
原始 mountinfo 文本未返回，其摘要及最长挂载匹配不在云端重新计算。

当前分配量仅覆盖本次 11 项，排除父目录及未知对象。不得与 K4 的异时 42 项拼成
同刻完整 49 项账单，更不代表历史实际用量、未来义务、原生日志或文件系统写前峰值。

## 四份原文带来的具体结论

控制原文缺失问题已解决。实际 SSH wrapper 的解释器行为和静态依赖现在可以审查，
但现有 `memory_wrapper_argv` 不支持该原件：第一行使用 `#!/usr/bin/env bash`，
超出现行解释器表；脚本中的固定局部变量也超出“不推断局部赋值”的变量支持范围。
第一确定拒绝为 `HOST_WINDOW_WRAPPER_INTERPRETER_UNSUPPORTED`；单独放开解释器后仍存在
`HOST_WINDOW_WRAPPER_ENVIRONMENT_UNSUPPORTED`。这是原适配器明确的支持限制，不能为通过而删检查、
改原脚本或重写 SSH 参数。

完整静态依赖与后续证明义务见[补证后的执行准入差额](Q2_POST_SOURCE_ADMISSION_PLAN.md)。
准确 P 的 wrapper 字面定位与 T01 一致，P 摘要与本次 M02 实测摘要一致；
四控制文本之间的固定定位和端点关系一致。该来源映射仅用于本轮静态审查。
四 raw 的匹配不证明历史某次调用执行了这些字节，也不授权访问脚本引用的其它文件。

## 限定完成度

L1–L4 的已有准确实现/验证/交付保持；本次 L5 的 11 项实际观察及四份原文均已收件核对，
L6 的原件登记、差额与 wrapper 静态依赖审查完成。**固定本地来源补证 L1–L6 的限定任务完成。**
这不把 OBSERVED_PARTIAL 改为完整 Q2 PASS，不创建新 Gate、实现 D 或业务批次。

H07 首次远端绝对截止与独立停止、完整账单、普通身份 writer、文件系统分配峰值/持久资格、
执行来源/环境等价关系仍需各自证据。全部 run/consume、Q2/Q3、production 许可仍 false；
原唯一新 startup batch 仍 NOT ISSUED 且未消费。下一步为离线形成准确执行准入方案，
无需再次采集同一 11 项、改权、启动 VM 或执行 wrapper。
