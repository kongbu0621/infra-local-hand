# Q2 历史证据恢复与仓库索引

2026-09-27。Owner 要求“你自己找不到吗？”、“这些既然这么重要，应该进仓库阿”。
本次完成既有 Q2 载体的深入检索、证据恢复和版本化归档，更正先前缺项判断。
新 startup 批次仍 **NOT ISSUED**，一次运行授权未消费，未连接原 guest。

## 复核结论

| 内容 | 已确认事实 | 仍未证明的边界 |
| --- | --- | --- |
| 原准备、恢复外层服务身份 | 已上传 CPUQuota 回传内各有三条一致的历史 InvocationID 记录 | 本次未检查当前 boot、实例、job/PID 或父树 |
| 两项服务退出 | 各自原 host stderr 记录 code=exited/status=3 | 身份查询记录本身不含 ExecMainCode/ExecMainStatus；不可冒称同一查询返回了退出码 |
| 原准备的 5 份文件 | stdout、stderr、host intent、host report 和失败回执均直接恢复，逐份匹配历史 SHA-256 | host intent 与 guest preparation intent 是不同文件 |
| 原准备的 5 份 step/command 记录 | 反转诊断投影后，逐份匹配原历史 SHA-256 | 不接受只有语义近似、没有摘要匹配的重建值 |
| preflight | 从已验证原回执和固定原写入/校验代码恢复预期字节 | 尚无独立原文件捕获或本次现场比较；与上述 10 份恢复原件分开标记 |
| 剩余 reservation | 六份原始值尚缺，另有上述 preflight 比较待完成 | 其他前序文档和 ledger 的 raw/来源缺口仍存在；六份不是全部准入缺口 |

之前只检查了部分解包层，漏读 command-result 的十六进制 stdout，以及
original-capture-proof 内嵌的完整原字节。先前 commit
`e25a5c4d008511d974c2817b5767714bd727a1ba` 的缺项判断由本索引更正；历史版本保留。
既有回传已包含的材料无需 Owner 再次提供。

## 原件、索引与来源

[manifest.json](manifest.json) 是公开机器可读索引，记录载体和恢复文件的 SHA-256、
长度、来源关系、恢复类型及私有 Git 归档 commit/tree/bundle 摘要。公开不包含机器
路径、账户、unit 名、InvocationID 或私人计划。没有把任何私有仓库历史复制进来。

原始载体与解码文件保存在 `q2-history-evidence-20260927.bundle`，这是完整的私有
Git 数据仓库快照，可用 `git clone` 恢复；尚未声称已推送到私有远端或部署到 NAS。
其中 `evidence-index.json` 按 SHA-256 定位原件，并保留原路径、附件身份和来源关系；
`input-inventory.json` 保存精确缺项；README 说明逐层解码和复算方法。恢复检验已从
bundle 独立 clone，通过 Git 对象校验及全部 **715 个逻辑条目、396 个去重对象**
的字节数/SHA-256 检查。bundle 的访问应沿用原机器证据的私有边界。

本次保留 11 个原始文件载体和 4 张相关原截图；CPUQuota 嵌套 collection 中
638 份文件、恢复 diagnostic 中 7 份 host 文件和 21 份 guest 文件均通过载体内
既有摘要校验。截图恢复结果与后来找到的完整字节一致，最终来源采用直接字节链。

复核顺序：先验证 bundle 摘要与 Git commit，再按私有索引取对象，验证每份长度和
SHA-256，最后核对原载体内引用。解码不执行历史交付脚本。Git/哈希证明归档内容和
绑定关系，不能补造未捕获的历史事实，也不能替代现在的 guest 状态。

## 保留边界与后续

当前安装承诺下界仍为 **192 + 64 + 新 64 = 320 MiB > 256 MiB**。恢复阶段的
192 MiB 属于原承诺，计一次。这里计算的是承诺，实际占用另行核实。没有释放旧
承诺、提高上限或改变冻结 runtime；旧 INCOMPLETE、Q2/Q3/production 未验收均保留。

剩余原始值未在本次检索的已上传 Q2 载体中找到，原 host 留存位置已经定位但当前
环境不能访问。下一步按固定私有清单取得留存字节/可信历史树展开，完成来源和账单
核验，再形成完整的[对账提案](../../q2-installation-reservation-reconciliation/REQUIREMENTS.md)。
提案仍 PROPOSED / Gate OPEN；归档工作没有实现对账算法，也没有关闭该范围。

后续关键证据应同步保留仓库索引、原件版本、摘要、来源关系和真实可用性。
索引中的“已恢复”“仅预期值”“尚缺”“未做现场检查”分别保留，不能统一写成完成。
