# Q2 固定本地来源：首次回执与保护阻断复核

2026-09-28 +08。Owner 上传本地 Codex 返回的完整 JSON，L5 首次调用已返回。
准确实现仍为 `411a9f054d0ee85c3e82296a1fdd3a9ed4ae6239`，tree
`21773876ef321eb70fdfd9dc24cbeed881efd2ef`；包 SHA-256
`b97112107193000ae36266b7d2179167fc60dcb38ecf8d4d62ff7dcb0c2dcdda`。
R/A/C 与已登记实现复核保持。本记录不创建新 Gate、业务批次或再次现场观察授权。

## 收到与核对的事实

原文件 `q2-local-source-result-20260928.json` 为 11,592 bytes，SHA-256
`4c91c9ac5bfcc0eb9923cd43a9ea61aee3e2e2f5fbefd792f63b05146ce268ba`。
原字节、机器身份、路径、内核事实及上传截图仅私有留存；公开只登记脱敏结论和摘要。

| 项目 | 本次结果 |
| --- | --- |
| 状态 / 阶段 | `LOCAL_SOURCE_EVIDENCE_BLOCKED` / `protected_parents` |
| 原因 | `RECONCILIATION_UNPROTECTED_PATH`，ValueError，errno 为 null |
| 固定目标 | 11项均 `NOT_ATTEMPTED`；尝试、观察、匹配、raw 返回各0 |
| 普通文件实际读取 | 0 bytes |
| 内核实际读取 | 首次固定 boot 37 bytes；mountinfo、最终 boot 未到达 |
| 父目录FS / marker | 均没有观察记录；不能据空数组认定 marker 不存在 |
| 输入 / 输出 | 原输入5,514,838 bytes；报告11,592，READY58，stdout合计11,650，stderr记录0 |
| 时间 | 接收原点到报告ended约0.15655秒，观察开始到ended约0.01704秒；不是超时 |
| 权限与验收 | wrapper、remote、持久写、批次消费及所有执行/验收许可仍false |

严格解析及规范字节重编码、报告自计量、D/tree/包及六工具摘要、固定 P/M/T、11项离线
派生、boot pin、双钟和完成计数已交叉核验。该核验确认回执内部一致及与准确交付相符，
不会把 BLOCKED 改为 PASS，也不提供独立签名 stdout 或原机器身份鉴证。

退出码2、唯一一次执行且无重试、无残留进程、结果文件0600及本地工作树干净等，
来自本地 Codex 截图自报。JSON 本身不证明这些进程、文件权限和调用次数事实。
回执的 namespace 对齐仍为 `ENVIRONMENT_ASSUMPTION_NOT_PROVEN`。

## 已定位的失败条件与诊断缺口

准确 D 的共享 `q2_reconciliation_io.protected` 仅在以下合取条件不成立时发出此原因：
属主属于 root/当前普通身份，且 `mode & 0o6022 == 0`。该mask检查group/other可写位
及setuid/setgid位。ACL检查有单独的错误原因；本次不能解释为ACL错误或NOATIME不足。

观察器按host parent、control parent顺序建立完整保护链，但旧报告不记录已完成的parent
检查或失败的chain层级。故无法判定是哪一个parent、哪一级祖先或哪一个谓词失败。
K4只记录较早时点的限定事实，不能代替本次失败时刻的目录状态。不能猜测具体目录、
要求chmod/chown/sudo，或通过改变保护规则让本次通过。

这个缺口属于原A L03/L10的错误定位/可复核性要求。限定修复只保存原检查已经取得的
角色、层级和metadata；不得追加系统调用、扫描、目标、权限变更或放宽任何保护条件。
原root层保存的metadata与保护谓词各有一次fstat，诊断必须保留二者可能不同的不确定性。

## 完成度与下一入口

首次L5已返回，L6收件、准确来源及阻断结果复核完成。四份控制原文均未取得，wrapper
静态依赖审查仍缺输入；这不表示11项事实采集目标达成，更不表示完整Q2/E3完成。
历史CPUQuota批次已消费失败及INCOMPLETE保持；原单次新startup batch仍NOT ISSUED且
未消费。本次已执行的本地观察与该业务批次是不同事项。

先完成上述限定诊断修复、隔离验证和准确交付准备，不自动重试原机。再次同范围观察
须由Owner明确发起，原A无需重复批准；原A需求的“资源、停止与非目标”及实施方案
“L5交付与回执复核”明确要求此边界。任何将来修改原机权限/所有权、保护合同或范围
的方案均不能从本次诊断修复自动取得授权。

完整账单、H07首次远端监督、普通writer、历史wrapper执行来源、FS分配峰值和durability
仍未证明；Q2/Q3及production状态保持false。没有新现场观察或远程连接。

## 诊断修复准确交付

新实现 D `89c725efd61dad11b0cc9ae11c3c08a941e3111a`，tree
`15f5a0dceae0f534506abf7195562980459f3ee7`，直接承接原登记 `2a3a6af2`。
仅观察器及其定向测试改变；三共享模块、来源contract、接收器、十五份冻结文档不变。
新增最多8KiB的 `parent_protection_failure`，仍计入原报告/双流限制；诊断出错或过大时
保留原拒绝原因，不新增观察。新字段不会追溯补进旧411回执。

定向78 PASS / 1 SKIP；三本地来源组161 PASS / 1 SKIP；六相关组**236 PASS / 3 SKIP**。
新增25个用例覆盖两个parent、祖先、root二次fstat、不同拒绝条件、坏诊断及原syscall序列。
三个环境SKIP原样保留：观察器/内核真实普通身份不可取得、映射测试UID/chown不支持。
这不是全仓CI或原机阳性；先前411的普通CI结果属于旧D，本轮不挪用为新D通过。

准确私有包4,113,937 bytes，SHA-256
`e6ed13681e79492aae5ba8216996056ef03c987c901d4f23db4906989d92eeec`；启动27,191，
帧5,496,087，完整输入5,523,278 bytes。同D两次独立组包逐字一致，源码/六模块、
Git祖先、P/M/T、11对象、启动/帧roundtrip、实际长度/摘要及封禁现场IO的离线核验通过。
接收器字节未变；未重跑无关PTY或原机调用，不宣称新增现场证据或全仓CI结果。

[本轮脱敏验证索引](evidence/q2-local-source-field-20260928/verification.json)登记准确回执和修复。
诊断版仅准备就绪，原机再次观察尚未发起；原A无需重批，仍等待明确再次观察指令。
